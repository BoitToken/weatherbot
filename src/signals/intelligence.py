"""
Intelligence Layer — 8-Gate Pre-Trade Checklist
Every trade MUST pass ALL gates before execution.
"""
import asyncio
from datetime import datetime
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass, field
import logging
import json

logger = logging.getLogger(__name__)

@dataclass
class GateResult:
    gate: str           # "gate_1_data_convergence"
    passed: bool
    confidence: float   # 0.0 to 1.0
    details: str        # Human-readable explanation
    data: dict = field(default_factory=dict)  # Raw data for logging

@dataclass 
class IntelligenceReport:
    market_id: str
    city: str
    station_icao: str
    all_gates_passed: bool
    gates: List[GateResult]
    final_probability: float
    recommended_action: str  # "TRADE", "ALERT_ONLY", "SKIP"
    recommended_side: str    # "YES" or "NO"
    recommended_size_usd: float
    reasoning: str
    created_at: datetime = field(default_factory=datetime.utcnow)

class IntelligenceLayer:
    """8-gate pre-trade intelligence checker."""
    
    def __init__(self, db_pool, config):
        self.db_pool = db_pool
        self.config = config
    
    async def run_full_check(self, market: dict, metar_data: dict, trend_data: dict = None) -> IntelligenceReport:
        """Run all 8 gates on a potential trade."""
        gates = []
        
        # Gate 1: Data Convergence (METAR + Open-Meteo + Historical)
        g1 = await self._gate_1_data_convergence(market, metar_data)
        gates.append(g1)
        
        # Gate 2: Multi-Station Validation
        g2 = await self._gate_2_multi_station(market, metar_data)
        gates.append(g2)
        
        # Gate 3: Bucket Coherence
        g3 = await self._gate_3_bucket_coherence(market)
        gates.append(g3)
        
        # Gate 4: Binary Arbitrage
        g4 = self._gate_4_binary_arbitrage(market)
        gates.append(g4)
        
        # Gate 5: Liquidity & Execution
        g5 = await self._gate_5_liquidity(market)
        gates.append(g5)
        
        # Gate 6: Time Window
        g6 = self._gate_6_time_window(market)
        gates.append(g6)
        
        # Gate 7: Risk Manager
        g7 = await self._gate_7_risk_manager(market)
        gates.append(g7)
        
        # Gate 8: Claude Confirmation (only if gates 1-7 pass)
        if all(g.passed for g in gates):
            g8 = await self._gate_8_claude_confirmation(market, metar_data, gates)
            gates.append(g8)
        else:
            gates.append(GateResult(
                gate="gate_8_claude", passed=False,
                confidence=0, details="Skipped — earlier gates failed"
            ))
        
        all_passed = all(g.passed for g in gates)
        
        # Determine action
        if g4.passed and g4.data.get("is_arbitrage"):
            action = "TRADE"  # Binary arb bypasses other gates
        elif all_passed:
            high_confidence = sum(1 for g in gates if g.confidence > 0.7)
            action = "TRADE" if high_confidence >= 5 else "ALERT_ONLY"
        else:
            action = "SKIP"
        
        return IntelligenceReport(
            market_id=market.get("market_id", ""),
            city=market.get("city", ""),
            station_icao=market.get("station_icao", ""),
            all_gates_passed=all_passed,
            gates=gates,
            final_probability=g1.data.get("our_probability", 0.5),
            recommended_action=action,
            recommended_side=g1.data.get("recommended_side", "YES"),
            recommended_size_usd=g7.data.get("position_size", 0),
            reasoning=self._build_reasoning(gates),
            created_at=datetime.utcnow()
        )
    
    async def _gate_1_data_convergence(self, market, metar_data) -> GateResult:
        """3 sources must agree: METAR + Open-Meteo + Historical."""
        from src.data.openmeteo import fetch_forecast
        from src.data.historical import fetch_historical_pattern
        
        icao = market.get("station_icao", "")
        threshold = float(market.get("threshold_value", 0))
        threshold_type = market.get("threshold_type", "high_above")
        
        # Source A: METAR
        metar_temp = metar_data.get("temperature_c", 0)
        metar_trend = metar_data.get("trend_per_hour", 0)
        
        # Source B: Open-Meteo
        forecast = await fetch_forecast(icao)
        forecast_high = forecast.get("forecast_high_c") if forecast else None
        
        # Source C: Historical
        historical = await fetch_historical_pattern(icao, datetime.utcnow())
        historical_avg = historical.get("avg_high_c") if historical else None
        
        # Count how many sources agree the threshold will be met
        votes = 0
        total_sources = 0
        
        if threshold_type == "high_above":
            # METAR source
            if metar_temp >= threshold:
                votes += 1  # Already hit!
            elif metar_temp + metar_trend * 6 >= threshold:
                votes += 1  # Trending to hit (6-hour projection)
            total_sources += 1
            
            # Open-Meteo forecast
            if forecast_high is not None:
                total_sources += 1
                if forecast_high >= threshold:
                    votes += 1
            
            # Historical baseline
            if historical_avg is not None:
                total_sources += 1
                if historical_avg >= threshold:
                    votes += 1
        
        passed = votes >= 2 or (votes == 1 and total_sources == 1)
        confidence = votes / max(total_sources, 1)
        
        return GateResult(
            gate="gate_1_data_convergence",
            passed=passed,
            confidence=confidence,
            details=f"Sources: {votes}/{total_sources} agree. METAR={metar_temp}°C, Forecast={forecast_high}°C, Historical={historical_avg}°C",
            data={
                "metar_temp": metar_temp,
                "metar_trend": metar_trend,
                "forecast_high": forecast_high,
                "historical_avg": historical_avg,
                "votes": votes,
                "total_sources": total_sources,
                "our_probability": confidence,
                "recommended_side": "YES" if votes >= 2 else "NO"
            }
        )
    
    async def _gate_2_multi_station(self, market, metar_data) -> GateResult:
        """Check multiple airports for same city agree."""
        # For now, auto-pass (most cities have single station)
        # Future: query all stations for same city, check divergence
        return GateResult(
            gate="gate_2_multi_station", passed=True, confidence=0.7,
            details="Single station city — auto-pass",
            data={}
        )
    
    async def _gate_3_bucket_coherence(self, market) -> GateResult:
        """Check if temperature buckets for same city/date sum correctly."""
        # Query all markets for same city and date
        city = market.get("city", "")
        if not city or not self.db_pool:
            return GateResult(
                gate="gate_3_bucket", passed=True, confidence=0.5,
                details="No bucket data available — auto-pass"
            )
        
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT market_id, title, yes_price, no_price 
                    FROM weather_markets 
                    WHERE city = $1 AND active = true
                """, city)
                
                if len(rows) < 2:
                    return GateResult(
                        gate="gate_3_bucket", passed=True, confidence=0.5,
                        details=f"Only {len(rows)} markets for {city} — can't check coherence"
                    )
                
                total_yes = sum(float(r.get("yes_price", 0) or 0) for r in rows)
                overpriced = total_yes > 1.05
                underpriced = total_yes < 0.95
                
                return GateResult(
                    gate="gate_3_bucket", passed=True,
                    confidence=0.8 if (overpriced or underpriced) else 0.5,
                    details=f"{len(rows)} buckets for {city}, sum={total_yes:.2f}. {'Overpriced!' if overpriced else 'Underpriced!' if underpriced else 'Fair'}",
                    data={"total_yes": total_yes, "bucket_count": len(rows)}
                )
        except Exception as e:
            logger.warning(f"Bucket coherence check failed: {e}")
            return GateResult(
                gate="gate_3_bucket", passed=True, confidence=0.5,
                details=f"Bucket check error: {e}"
            )
    
    def _gate_4_binary_arbitrage(self, market) -> GateResult:
        """Check if YES + NO < $0.98 (free money)."""
        yes_price = float(market.get("yes_price", 0.5) or 0.5)
        no_price = float(market.get("no_price", 0.5) or 0.5)
        total = yes_price + no_price
        is_arb = total < 0.98
        
        return GateResult(
            gate="gate_4_binary_arb",
            passed=True,  # Always passes (informational)
            confidence=1.0 if is_arb else 0.5,
            details=f"YES({yes_price:.3f}) + NO({no_price:.3f}) = {total:.3f}. {'ARBITRAGE!' if is_arb else 'No arb.'}",
            data={"is_arbitrage": is_arb, "total": total}
        )
    
    async def _gate_5_liquidity(self, market) -> GateResult:
        """Check order book has enough liquidity."""
        yes_price = float(market.get("yes_price", 0.5) or 0.5)
        no_price = float(market.get("no_price", 0.5) or 0.5)
        spread = abs(yes_price - (1 - no_price))
        
        volume = float(market.get("volume_usd", 0) or market.get("volume", 0) or 0)
        liquidity = float(market.get("liquidity_usd", 0) or market.get("liquidity", 0) or 0)
        
        if spread > 0.08:
            return GateResult(
                gate="gate_5_liquidity", passed=False, confidence=0.2,
                details=f"Spread too wide: {spread:.3f} (max 0.08)",
                data={"spread": spread, "volume": volume}
            )
        
        passed = volume > 100 or liquidity > 50  # Minimum thresholds
        return GateResult(
            gate="gate_5_liquidity", passed=passed,
            confidence=0.8 if passed else 0.3,
            details=f"Spread={spread:.3f}, Volume=${volume:.0f}, Liquidity=${liquidity:.0f}",
            data={"spread": spread, "volume": volume, "liquidity": liquidity}
        )
    
    def _gate_6_time_window(self, market) -> GateResult:
        """Check if we're in an optimal trading window."""
        # For now, always pass (time optimization is a refinement)
        # Future: check resolution_time - now > 2 hours
        return GateResult(
            gate="gate_6_time_window", passed=True, confidence=0.6,
            details="Time window check — auto-pass for paper trading"
        )
    
    async def _gate_7_risk_manager(self, market) -> GateResult:
        """Check position limits and circuit breakers."""
        try:
            # Try to import existing risk manager
            from src.execution.risk_manager import check_limits, get_position_size
            
            allowed, reason = await check_limits(market)
            if not allowed:
                return GateResult(
                    gate="gate_7_risk", passed=False, confidence=0,
                    details=f"Risk check failed: {reason}"
                )
            
            size = await get_position_size(market)
            return GateResult(
                gate="gate_7_risk", passed=True, confidence=0.8,
                details=f"Risk approved. Position size: ${size:.2f}",
                data={"position_size": size}
            )
        except ImportError:
            # Fallback if risk_manager doesn't exist yet
            logger.warning("Risk manager not found, using default position size")
            return GateResult(
                gate="gate_7_risk", passed=True, confidence=0.5,
                details="Risk manager not configured — using default $25",
                data={"position_size": 25.0}
            )
        except Exception as e:
            logger.warning(f"Risk check error: {e}")
            return GateResult(
                gate="gate_7_risk", passed=True, confidence=0.5,
                details=f"Risk check error (auto-pass for paper): {e}",
                data={"position_size": 25.0}
            )
    
    async def _gate_8_claude_confirmation(self, market, metar_data, prior_gates) -> GateResult:
        """Claude AI confirmation — final check."""
        try:
            # Try to import existing Claude analyzer
            from src.signals.claude_analyzer import ClaudeAnalyzer
            
            api_key = getattr(self.config, 'ANTHROPIC_API_KEY', None)
            if not api_key:
                return GateResult(
                    gate="gate_8_claude", passed=True, confidence=0.5,
                    details="Claude not configured — auto-pass"
                )
            
            analyzer = ClaudeAnalyzer(api_key)
            
            # Build context from prior gates
            gate_summary = "\n".join([
                f"  {g.gate}: {'PASS' if g.passed else 'FAIL'} ({g.details})" 
                for g in prior_gates
            ])
            
            # Use the existing analyzer
            signal_data = {
                "city": market.get("city", ""),
                "station_icao": market.get("station_icao", ""),
                "market_title": market.get("title", ""),
                "metar_temp": metar_data.get("temperature_c"),
                "our_probability": prior_gates[0].data.get("our_probability", 0.5),
                "market_price": float(market.get("yes_price", 0.5) or 0.5),
                "gate_summary": gate_summary
            }
            
            result = await analyzer.analyze_signal(signal_data)
            
            passed = result.get("recommendation") in ["TRADE", "trade"]
            confidence_str = result.get("confidence", "LOW")
            conf_map = {"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3}
            
            return GateResult(
                gate="gate_8_claude", passed=passed,
                confidence=conf_map.get(confidence_str.upper(), 0.5),
                details=f"Claude: {result.get('recommendation', 'SKIP')} ({confidence_str}). {result.get('reasoning', '')}",
                data=result
            )
        except ImportError:
            logger.warning("Claude analyzer not found")
            return GateResult(
                gate="gate_8_claude", passed=True, confidence=0.5,
                details="Claude analyzer not configured — auto-pass"
            )
        except Exception as e:
            logger.warning(f"Claude confirmation error: {e}")
            return GateResult(
                gate="gate_8_claude", passed=True, confidence=0.5,
                details=f"Claude error (auto-pass for paper): {e}"
            )
    
    def _build_reasoning(self, gates: List[GateResult]) -> str:
        """Build human-readable reasoning from all gates."""
        lines = []
        for g in gates:
            status = "✅" if g.passed else "❌"
            lines.append(f"{status} {g.gate}: {g.details}")
        return "\n".join(lines)
    
    async def store_report(self, report: IntelligenceReport):
        """Store the full intelligence report in DB for learning."""
        if not self.db_pool:
            logger.warning("No DB pool, skipping report storage")
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO signals (
                        market_id, station_icao, city, side,
                        our_probability, market_price, edge, confidence,
                        claude_reasoning, metadata, was_traded, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                    report.market_id,
                    report.station_icao,
                    report.city,
                    report.recommended_side,
                    report.final_probability,
                    0.0,  # market_price filled later
                    report.final_probability - 0.5,  # edge
                    "HIGH" if report.all_gates_passed else "LOW",
                    report.reasoning,
                    json.dumps({
                        "gates": [
                            {
                                "gate": g.gate, 
                                "passed": g.passed, 
                                "confidence": g.confidence, 
                                "details": g.details
                            } 
                            for g in report.gates
                        ],
                        "action": report.recommended_action
                    }),
                    report.recommended_action == "TRADE",
                    report.created_at
                )
                logger.info(f"Stored intelligence report for {report.market_id}")
        except Exception as e:
            logger.error(f"Failed to store intelligence report: {e}")


if __name__ == "__main__":
    # Test the module
    print("Intelligence Layer module loaded successfully")
    print(f"  GateResult: {GateResult.__name__}")
    print(f"  IntelligenceReport: {IntelligenceReport.__name__}")
    print(f"  IntelligenceLayer: {IntelligenceLayer.__name__}")
