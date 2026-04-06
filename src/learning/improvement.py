"""
Improvement Loop — learns from trade outcomes and proposes strategy changes.
Changes are proposed only. CEO must approve before they're applied.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)

class ImprovementEngine:
    def __init__(self, db_pool, config):
        self.db_pool = db_pool
        self.config = config
    
    async def daily_analysis(self) -> Dict:
        """Run daily performance analysis."""
        if not self.db_pool:
            return {"error": "No DB pool"}
        
        async with self.db_pool.acquire() as conn:
            # Today's trades
            today = datetime.utcnow().date()
            trades = await conn.fetch("""
                SELECT * FROM trades 
                WHERE DATE(entry_at) = $1
                ORDER BY entry_at DESC
            """, str(today))
            
            # Resolved trades (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            resolved = await conn.fetch("""
                SELECT * FROM trades 
                WHERE resolved_at IS NOT NULL AND resolved_at >= $1
            """, week_ago)
            
            # Station accuracy
            try:
                accuracy = await conn.fetch("""
                    SELECT station_icao, city, total_signals, correct_signals, accuracy
                    FROM station_accuracy
                    ORDER BY total_signals DESC
                """)
            except Exception as e:
                logger.warning(f"Station accuracy table not found: {e}")
                accuracy = []
        
        total = len(resolved)
        wins = sum(1 for t in resolved if float(t.get("pnl_usd", 0) or 0) > 0)
        losses = total - wins
        total_pnl = sum(float(t.get("pnl_usd", 0) or 0) for t in resolved)
        
        report = {
            "date": str(today),
            "period": "7_days",
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / total if total > 0 else 0,
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / total if total > 0 else 0,
            "today_trades": len(trades),
            "station_accuracy": [dict(a) for a in accuracy],
            "needs_attention": total > 20 and wins / total < 0.55,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return report
    
    async def weekly_review(self) -> Dict:
        """Generate weekly strategy review with findings for CEO."""
        daily = await self.daily_analysis()
        
        findings = []
        proposals = []
        
        # Check if win rate is below target
        if daily["win_rate"] < 0.55 and daily["total_trades"] > 10:
            findings.append(
                f"Win rate {daily['win_rate']:.1%} is below 55% target over {daily['total_trades']} trades"
            )
            proposals.append(
                "PROPOSAL: Increase min_edge_auto_trade from 0.25 to 0.30 to filter weaker signals"
            )
        
        # Check station accuracy
        bad_stations = [
            s for s in daily["station_accuracy"] 
            if s.get("accuracy") and float(s["accuracy"]) < 0.5 
            and int(s.get("total_signals", 0)) > 5
        ]
        if bad_stations:
            for s in bad_stations:
                findings.append(
                    f"Station {s['station_icao']} ({s['city']}) accuracy only "
                    f"{float(s['accuracy']):.1%} over {s['total_signals']} signals"
                )
            proposals.append(
                f"PROPOSAL: Exclude stations with <50% accuracy: "
                f"{[s['station_icao'] for s in bad_stations]}"
            )
        
        # Check if PnL is negative
        if daily["total_pnl"] < 0:
            findings.append(f"Net P&L is negative: ${daily['total_pnl']:.2f}")
            proposals.append(
                "PROPOSAL: Reduce max_position_usd from $50 to $25 until win rate improves"
            )
        
        # Check if we're winning but position sizes are too small
        if daily["win_rate"] > 0.60 and daily["total_trades"] > 20:
            if daily["avg_pnl"] < 5:  # Average win < $5
                findings.append(
                    f"Win rate is strong ({daily['win_rate']:.1%}) but avg P&L is only ${daily['avg_pnl']:.2f}"
                )
                proposals.append(
                    "PROPOSAL: Increase max_position_usd from $50 to $75 to capture more value"
                )
        
        review = {
            "type": "weekly_review",
            "date": str(datetime.utcnow().date()),
            "summary": daily,
            "findings": findings,
            "proposals": proposals,
            "status": "PENDING_CEO_APPROVAL",
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return review
    
    async def update_station_accuracy(self, station_icao: str, was_correct: bool):
        """Update accuracy tracking for a station after trade resolves."""
        if not self.db_pool:
            logger.warning("No DB pool, skipping station accuracy update")
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                existing = await conn.fetchrow(
                    "SELECT * FROM station_accuracy WHERE station_icao = $1", 
                    station_icao
                )
                
                if existing:
                    total = int(existing.get("total_signals", 0)) + 1
                    correct = int(existing.get("correct_signals", 0)) + (1 if was_correct else 0)
                    await conn.execute("""
                        UPDATE station_accuracy 
                        SET total_signals = $1, correct_signals = $2, 
                            accuracy = $3, last_updated = NOW()
                        WHERE station_icao = $4
                    """, total, correct, correct / total, station_icao)
                    logger.info(f"Updated {station_icao} accuracy: {correct}/{total} = {correct/total:.1%}")
                else:
                    await conn.execute("""
                        INSERT INTO station_accuracy (
                            station_icao, city, total_signals, correct_signals, accuracy
                        )
                        VALUES ($1, $2, 1, $3, $4)
                    """, 
                        station_icao, 
                        "", 
                        1 if was_correct else 0, 
                        1.0 if was_correct else 0.0
                    )
                    logger.info(f"Created {station_icao} accuracy: {1 if was_correct else 0}/1")
        except Exception as e:
            logger.error(f"Failed to update station accuracy: {e}")
    
    async def calibrate_probability_model(self) -> Dict:
        """Analyze if our probability estimates are calibrated.
        
        Returns calibration metrics:
        - For trades we predicted 70% win rate, did we actually win 70%?
        - Brier score (lower is better, 0 = perfect)
        - Suggested adjustments to Gaussian model
        """
        if not self.db_pool:
            return {"error": "No DB pool"}
        
        try:
            async with self.db_pool.acquire() as conn:
                # Get all resolved signals with our probability estimate
                signals = await conn.fetch("""
                    SELECT 
                        our_probability,
                        market_price,
                        side,
                        was_traded,
                        (SELECT outcome FROM trades WHERE trades.signal_id = signals.id LIMIT 1) as outcome
                    FROM signals
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    AND was_traded = true
                """)
        except Exception as e:
            logger.warning(f"Failed to fetch signals for calibration: {e}")
            return {"error": str(e)}
        
        if not signals:
            return {"error": "No signals to calibrate"}
        
        # Bucket probabilities into deciles
        buckets = {i: {"predicted": i/10, "correct": 0, "total": 0} for i in range(1, 11)}
        
        total_brier = 0
        count = 0
        
        for sig in signals:
            prob = float(sig.get("our_probability", 0.5) or 0.5)
            outcome = sig.get("outcome")
            
            if outcome is None:
                continue
            
            # Which bucket?
            bucket = min(10, max(1, int(prob * 10) + 1))
            buckets[bucket]["total"] += 1
            
            # Did we win?
            won = (outcome == "win")
            if won:
                buckets[bucket]["correct"] += 1
            
            # Brier score component
            predicted_prob = prob
            actual = 1.0 if won else 0.0
            total_brier += (predicted_prob - actual) ** 2
            count += 1
        
        brier_score = total_brier / count if count > 0 else None
        
        # Calculate actual win rate per bucket
        calibration = {}
        for bucket, data in buckets.items():
            if data["total"] > 0:
                actual_rate = data["correct"] / data["total"]
                calibration[f"{int(data['predicted']*100)}%"] = {
                    "predicted": data["predicted"],
                    "actual": actual_rate,
                    "n": data["total"],
                    "delta": actual_rate - data["predicted"]
                }
        
        return {
            "brier_score": brier_score,
            "calibration_buckets": calibration,
            "total_signals": count,
            "recommendation": (
                "WELL_CALIBRATED" if brier_score and brier_score < 0.15 
                else "OVERCONFIDENT" if brier_score and brier_score > 0.25 
                else "NEEDS_MORE_DATA"
            ),
            "generated_at": datetime.utcnow().isoformat()
        }


if __name__ == "__main__":
    # Test the module
    print("Improvement Engine module loaded successfully")
    print(f"  ImprovementEngine: {ImprovementEngine.__name__}")
