"""
Learning Engine — Post-trade analysis, strategy scorecards, threshold optimization,
auto-disable, and weekly reports.

The ONLY priority: make the qualifying criteria more accurate.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _edge_bucket(edge: float) -> str:
    """Classify an edge percentage into a bucket."""
    if edge < 5:
        return '<5%'
    elif edge < 7:
        return '5-7%'
    elif edge < 10:
        return '7-10%'
    elif edge < 15:
        return '10-15%'
    else:
        return '15%+'


class LearningEngine:
    """Sports-focused post-trade learning engine."""

    def __init__(self, db_pool):
        """
        Args:
            db_pool: AsyncPoolWrapper (from db_async.get_async_pool())
        """
        self.db_pool = db_pool

    # ── helpers ──────────────────────────────────────────────────

    async def _execute(self, query: str, *args):
        async with self.db_pool.acquire() as conn:
            await conn.execute(query, *args)

    async def _fetch(self, query: str, *args) -> List[Dict]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows] if rows else []

    async def _fetchrow(self, query: str, *args) -> Optional[Dict]:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    # ── 1. Post-Trade Analysis ───────────────────────────────────

    async def post_trade_analysis(
        self,
        trade_id: int,
        strategy: str,
        sport: str,
        predicted_edge: float,
        actual_outcome: str,   # 'won' or 'lost'
        pnl: float,
    ) -> Dict:
        """
        Called after every trade settlement.
        Logs to trade_learnings, computes whether signal was correct.
        """
        edge_pct = abs(predicted_edge) if predicted_edge else 0.0
        bucket = _edge_bucket(edge_pct)
        signal_correct = actual_outcome == 'won'

        notes_parts = []
        if signal_correct:
            notes_parts.append(f"Signal correct - edge {edge_pct:.1f}% delivered +${pnl:.2f}")
        else:
            notes_parts.append(f"Signal wrong - edge {edge_pct:.1f}% but lost ${abs(pnl):.2f}")

        analysis_notes = "; ".join(notes_parts)

        try:
            await self._execute(
                """
                INSERT INTO trade_learnings
                    (trade_id, strategy, sport, predicted_edge, actual_outcome,
                     pnl_usd, edge_bucket, signal_was_correct, analysis_notes)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                trade_id, strategy or 'unknown', sport or 'unknown',
                edge_pct, actual_outcome, round(pnl, 2),
                bucket, signal_correct, analysis_notes,
            )
            logger.info(
                f"📘 Learning logged: trade #{trade_id} strategy={strategy} "
                f"sport={sport} edge={edge_pct:.1f}% outcome={actual_outcome} pnl=${pnl:+.2f}"
            )
        except Exception as e:
            logger.error(f"Failed to log trade learning for #{trade_id}: {e}")

        return {
            "trade_id": trade_id,
            "signal_correct": signal_correct,
            "edge_bucket": bucket,
            "notes": analysis_notes,
        }

    # ── 2. Strategy Scorecard ────────────────────────────────────

    async def strategy_scorecard(self, strategy: str, lookback_days: int = 30) -> Dict:
        """
        Rolling scorecard for a given strategy.
        Returns win_rate, avg_edge for winners/losers, best/worst sport, sample_size.
        """
        since = datetime.utcnow() - timedelta(days=lookback_days)

        rows = await self._fetch(
            """
            SELECT sport, predicted_edge, actual_outcome, pnl_usd, signal_was_correct
            FROM trade_learnings
            WHERE strategy = $1 AND created_at >= $2
            ORDER BY created_at DESC
            """,
            strategy, since,
        )

        if not rows:
            return {
                "strategy": strategy,
                "sample_size": 0,
                "win_rate": 0.0,
                "avg_edge_winners": 0.0,
                "avg_edge_losers": 0.0,
                "best_sport": None,
                "worst_sport": None,
                "total_pnl": 0.0,
            }

        total = len(rows)
        wins = [r for r in rows if r.get('signal_was_correct')]
        losses = [r for r in rows if not r.get('signal_was_correct')]
        win_rate = len(wins) / total if total else 0.0

        avg_edge_w = (
            sum(float(r.get('predicted_edge', 0) or 0) for r in wins) / len(wins)
            if wins else 0.0
        )
        avg_edge_l = (
            sum(float(r.get('predicted_edge', 0) or 0) for r in losses) / len(losses)
            if losses else 0.0
        )

        # Per-sport win rates
        sport_stats: Dict[str, Dict] = {}
        for r in rows:
            s = r.get('sport', 'unknown')
            if s not in sport_stats:
                sport_stats[s] = {'wins': 0, 'total': 0}
            sport_stats[s]['total'] += 1
            if r.get('signal_was_correct'):
                sport_stats[s]['wins'] += 1

        sport_wr = {
            s: d['wins'] / d['total'] for s, d in sport_stats.items() if d['total'] > 0
        }
        best_sport = max(sport_wr, key=sport_wr.get) if sport_wr else None
        worst_sport = min(sport_wr, key=sport_wr.get) if sport_wr else None

        total_pnl = sum(float(r.get('pnl_usd', 0) or 0) for r in rows)

        return {
            "strategy": strategy,
            "sample_size": total,
            "win_rate": round(win_rate, 4),
            "avg_edge_winners": round(avg_edge_w, 2),
            "avg_edge_losers": round(avg_edge_l, 2),
            "best_sport": best_sport,
            "worst_sport": worst_sport,
            "total_pnl": round(total_pnl, 2),
            "sport_breakdown": {
                s: {"wins": d["wins"], "total": d["total"],
                    "win_rate": round(d["wins"] / d["total"], 4)}
                for s, d in sport_stats.items() if d["total"] > 0
            },
        }

    # ── 3. Threshold Optimization ────────────────────────────────

    async def optimize_thresholds(self) -> Dict:
        """
        Analyze resolved trades by edge bucket.
        Find the minimum edge where win rate > 55%.
        Store recommendation in bot_settings.
        """
        rows = await self._fetch(
            """
            SELECT edge_bucket, signal_was_correct, predicted_edge, pnl_usd
            FROM trade_learnings
            ORDER BY created_at DESC
            """
        )

        if not rows:
            return {"status": "no_data", "recommendation": None}

        # Group by bucket
        buckets_order = ['<5%', '5-7%', '7-10%', '10-15%', '15%+']
        bucket_stats: Dict[str, Dict] = {b: {'wins': 0, 'total': 0, 'pnl': 0.0} for b in buckets_order}

        for r in rows:
            b = r.get('edge_bucket', '<5%')
            if b not in bucket_stats:
                bucket_stats[b] = {'wins': 0, 'total': 0, 'pnl': 0.0}
            bucket_stats[b]['total'] += 1
            if r.get('signal_was_correct'):
                bucket_stats[b]['wins'] += 1
            bucket_stats[b]['pnl'] += float(r.get('pnl_usd', 0) or 0)

        analysis = {}
        for b in buckets_order:
            d = bucket_stats[b]
            wr = d['wins'] / d['total'] if d['total'] > 0 else 0.0
            analysis[b] = {
                'total': d['total'],
                'wins': d['wins'],
                'win_rate': round(wr, 4),
                'total_pnl': round(d['pnl'], 2),
            }

        # Edge thresholds mapped to bucket lower bounds
        edge_map = {'<5%': 0, '5-7%': 5, '7-10%': 7, '10-15%': 10, '15%+': 15}
        recommended_min_edge = 7  # default

        for b in buckets_order:
            d = bucket_stats[b]
            if d['total'] >= 5:
                wr = d['wins'] / d['total']
                if wr > 0.55:
                    recommended_min_edge = edge_map.get(b, 7)
                    break

        # Store recommendation
        try:
            value_json = json.dumps(recommended_min_edge)
            async with self.db_pool.acquire() as conn:
                # Use two separate params for INSERT and UPDATE
                await conn.execute(
                    """
                    INSERT INTO bot_settings (key, value, updated_at)
                    VALUES ($1, $2::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = $3::jsonb, updated_at = NOW()
                    """,
                    'recommended_min_edge', value_json, value_json,
                )
            logger.info(f"🎯 Threshold optimization: recommended_min_edge = {recommended_min_edge}%")
        except Exception as e:
            logger.error(f"Failed to store recommended_min_edge: {e}")

        # Store report
        report_data = {
            "bucket_analysis": analysis,
            "recommended_min_edge": recommended_min_edge,
            "total_trades_analyzed": len(rows),
            "generated_at": datetime.utcnow().isoformat(),
        }

        try:
            await self._execute(
                """
                INSERT INTO learning_reports (report_type, report_data, recommendations, status)
                VALUES ('threshold_optimization', $1::jsonb, $2::jsonb, 'pending')
                """,
                json.dumps(report_data),
                json.dumps({"recommended_min_edge": recommended_min_edge}),
            )
        except Exception as e:
            logger.error(f"Failed to store threshold report: {e}")

        return {
            "status": "completed",
            "bucket_analysis": analysis,
            "recommendation": recommended_min_edge,
            "total_trades_analyzed": len(rows),
        }

    # ── 4. Auto-Disable Check ────────────────────────────────────

    async def auto_disable_check(self) -> Dict:
        """
        Disable underperforming strategies and flag bad sports.
        Strategy: win_rate < 48% over 30+ trades → disable.
        Sport: win_rate < 45% over 20+ trades → flag.
        """
        disabled_strategies = []
        flagged_sports = []

        # ── Strategy check ──
        strat_rows = await self._fetch(
            """
            SELECT strategy, 
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_was_correct THEN 1 ELSE 0 END) as wins
            FROM trade_learnings
            GROUP BY strategy
            """
        )

        for row in strat_rows:
            total = row['total']
            wins = row['wins']
            strategy = row['strategy']
            if total >= 30:
                wr = wins / total
                if wr < 0.48:
                    # Disable in strategy_performance
                    try:
                        await self._execute(
                            """
                            UPDATE strategy_performance SET is_active = false, updated_at = NOW()
                            WHERE strategy = $1
                            """,
                            strategy,
                        )
                        disabled_strategies.append({
                            "strategy": strategy,
                            "win_rate": round(wr, 4),
                            "sample_size": total,
                            "action": "disabled",
                        })
                        logger.warning(
                            f"🚫 Auto-disabled strategy '{strategy}': "
                            f"win_rate={wr:.1%} over {total} trades"
                        )
                    except Exception as e:
                        logger.error(f"Failed to disable strategy {strategy}: {e}")

        # ── Sport check ──
        sport_rows = await self._fetch(
            """
            SELECT sport,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_was_correct THEN 1 ELSE 0 END) as wins
            FROM trade_learnings
            GROUP BY sport
            """
        )

        for row in sport_rows:
            total = row['total']
            wins = row['wins']
            sport = row['sport']
            if total >= 20:
                wr = wins / total
                if wr < 0.45:
                    flagged_sports.append({
                        "sport": sport,
                        "win_rate": round(wr, 4),
                        "sample_size": total,
                        "action": "flagged_for_review",
                    })
                    logger.warning(
                        f"⚠️ Sport '{sport}' flagged: win_rate={wr:.1%} over {total} trades"
                    )

        # Log all actions to learning_reports
        if disabled_strategies or flagged_sports:
            try:
                await self._execute(
                    """
                    INSERT INTO learning_reports (report_type, report_data, recommendations, status)
                    VALUES ('strategy_review', $1::jsonb, $2::jsonb, 'applied')
                    """,
                    json.dumps({
                        "disabled_strategies": disabled_strategies,
                        "flagged_sports": flagged_sports,
                        "generated_at": datetime.utcnow().isoformat(),
                    }),
                    json.dumps({
                        "disable": [s["strategy"] for s in disabled_strategies],
                        "review": [s["sport"] for s in flagged_sports],
                    }),
                )
            except Exception as e:
                logger.error(f"Failed to log auto-disable report: {e}")

        return {
            "disabled_strategies": disabled_strategies,
            "flagged_sports": flagged_sports,
            "checked_at": datetime.utcnow().isoformat(),
        }

    # ── 5. Weekly Report ─────────────────────────────────────────

    async def weekly_report(self) -> Dict:
        """
        Comprehensive weekly report:
        - Per-strategy performance
        - Edge threshold analysis
        - Recommendations
        - Calibration check
        """
        seven_days = datetime.utcnow() - timedelta(days=7)

        # ── per-strategy ──
        strat_rows = await self._fetch(
            """
            SELECT strategy,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_was_correct THEN 1 ELSE 0 END) as wins,
                   SUM(pnl_usd) as total_pnl,
                   AVG(predicted_edge) as avg_edge
            FROM trade_learnings
            WHERE created_at >= $1
            GROUP BY strategy
            """,
            seven_days,
        )

        strategy_performance = []
        for r in strat_rows:
            total = r['total']
            wins = r['wins']
            strategy_performance.append({
                "strategy": r['strategy'],
                "total_trades": total,
                "wins": wins,
                "losses": total - wins,
                "win_rate": round(wins / total, 4) if total > 0 else 0,
                "total_pnl": round(float(r.get('total_pnl', 0) or 0), 2),
                "avg_edge": round(float(r.get('avg_edge', 0) or 0), 2),
            })

        # ── edge threshold analysis ──
        threshold_data = await self.optimize_thresholds()

        # ── calibration ──
        calibration = await self._calibration_check()

        # ── recommendations ──
        recommendations = []

        for sp in strategy_performance:
            if sp['total_trades'] >= 10 and sp['win_rate'] < 0.50:
                recommendations.append(
                    f"⚠️ Strategy '{sp['strategy']}' has {sp['win_rate']:.0%} win rate "
                    f"over {sp['total_trades']} trades — consider raising edge threshold or disabling."
                )
            if sp['total_trades'] >= 20 and sp['win_rate'] > 0.60:
                recommendations.append(
                    f"✅ Strategy '{sp['strategy']}' performing well at {sp['win_rate']:.0%} — "
                    f"consider increasing position size."
                )

        rec_edge = threshold_data.get('recommendation')
        if rec_edge and rec_edge != 7:
            recommendations.append(
                f"🎯 Threshold analysis suggests min edge = {rec_edge}%"
            )

        if calibration.get('overconfident'):
            recommendations.append(
                "📊 Calibration check: we may be overconfident — "
                "predicted edges are higher than actual win rates suggest."
            )

        # ── build report ──
        report = {
            "period": "7_days",
            "period_start": seven_days.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            "strategy_performance": strategy_performance,
            "threshold_analysis": threshold_data.get('bucket_analysis', {}),
            "recommended_min_edge": rec_edge,
            "calibration": calibration,
            "recommendations": recommendations,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Store report
        try:
            await self._execute(
                """
                INSERT INTO learning_reports (report_type, report_data, recommendations, status)
                VALUES ('weekly', $1::jsonb, $2::jsonb, 'pending')
                """,
                json.dumps(report),
                json.dumps(recommendations),
            )
            logger.info("📊 Weekly learning report generated and stored")
        except Exception as e:
            logger.error(f"Failed to store weekly report: {e}")

        return report

    # ── internal: calibration ────────────────────────────────────

    async def _calibration_check(self) -> Dict:
        """Check if predicted edges are calibrated to actual outcomes."""
        rows = await self._fetch(
            """
            SELECT predicted_edge, signal_was_correct
            FROM trade_learnings
            WHERE created_at >= NOW() - INTERVAL '30 days'
            """
        )

        if len(rows) < 10:
            return {"status": "insufficient_data", "sample_size": len(rows)}

        # Bucket by predicted edge and check actual win rates
        buckets_order = ['<5%', '5-7%', '7-10%', '10-15%', '15%+']
        bucket_data: Dict[str, Dict] = {b: {'wins': 0, 'total': 0} for b in buckets_order}

        for r in rows:
            edge = float(r.get('predicted_edge', 0) or 0)
            b = _edge_bucket(edge)
            if b not in bucket_data:
                bucket_data[b] = {'wins': 0, 'total': 0}
            bucket_data[b]['total'] += 1
            if r.get('signal_was_correct'):
                bucket_data[b]['wins'] += 1

        calibration_buckets = {}
        overconfident = False
        for b in buckets_order:
            d = bucket_data[b]
            if d['total'] > 0:
                wr = d['wins'] / d['total']
                calibration_buckets[b] = {
                    'total': d['total'],
                    'wins': d['wins'],
                    'actual_win_rate': round(wr, 4),
                }
                # High-edge trades winning less than 55% = overconfident
                if b in ('10-15%', '15%+') and d['total'] >= 5 and wr < 0.55:
                    overconfident = True

        total_wins = sum(1 for r in rows if r.get('signal_was_correct'))
        overall_wr = total_wins / len(rows)

        return {
            "status": "completed",
            "sample_size": len(rows),
            "overall_win_rate": round(overall_wr, 4),
            "overconfident": overconfident,
            "calibration_buckets": calibration_buckets,
        }

    # ── Public: get current thresholds ───────────────────────────

    async def get_current_thresholds(self) -> Dict:
        """Return the latest threshold analysis without re-optimizing."""
        row = await self._fetchrow(
            """
            SELECT report_data FROM learning_reports
            WHERE report_type = 'threshold_optimization'
            ORDER BY created_at DESC LIMIT 1
            """
        )
        if row:
            data = row.get('report_data')
            if isinstance(data, str):
                data = json.loads(data)
            return data or {}

        # Fallback: run optimization
        return await self.optimize_thresholds()

    # ── Public: get latest report ────────────────────────────────

    async def get_latest_report(self) -> Optional[Dict]:
        """Return the latest weekly report."""
        row = await self._fetchrow(
            """
            SELECT id, report_type, report_data, recommendations, status, created_at
            FROM learning_reports
            WHERE report_type = 'weekly'
            ORDER BY created_at DESC LIMIT 1
            """
        )
        if not row:
            return None
        result = dict(row)
        for key in ('report_data', 'recommendations'):
            if isinstance(result.get(key), str):
                result[key] = json.loads(result[key])
        return result


if __name__ == "__main__":
    print("Learning Engine module loaded successfully")
    print(f"  LearningEngine: {LearningEngine.__name__}")
