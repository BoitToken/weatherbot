"""
Sports Signal Loop
Main orchestrator for sports intelligence module.
Runs every 3 minutes to:
1. Scan Polymarket for sports markets
2. Update live scores from ESPN
3. Run correlation engine (logical arbitrage)
4. Run cross-odds engine (value plays)
5. Store signals in DB
6. Auto-execute qualifying trades per INTELLIGENCE.md protocols

Protocols (loaded from INTELLIGENCE.md at startup):
- Protocol 1: Internal Arb (YES+NO < $1, risk-free, every 2 min)
- Protocol 2: Cross-Market Arb (sportsbook vs PM, >7% raw / >5% after 2% fee)
- Protocol 3: Edge Decay Monitor (exit if edge < 2%)
- Protocol 4: Line Movement (sharp money detection)
- Protocol 5: Settlement + Learning (post-trade feedback loop)
- Protocol 6: Risk Management (circuit breaker, Kelly sizing, position caps)
"""
import logging
from datetime import datetime
from .polymarket_sports_scanner import PolymarketSportsScanner
from .espn_live import ESPNLiveScores
from .correlation_engine import CorrelationEngine
from .cross_odds_engine import CrossOddsEngine

logger = logging.getLogger(__name__)


class SportsSignalLoop:
    """Main sports scanning loop."""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.scanner = PolymarketSportsScanner(db_pool)
        self.espn = ESPNLiveScores(db_pool)
        self.correlation = CorrelationEngine(db_pool)
        self.cross_odds = CrossOddsEngine(db_pool)
    
    async def run_once(self):
        """Run one complete sports intelligence cycle.
        
        Follows INTELLIGENCE.md protocols:
        - Protocol 2: Cross-Market Arb (sportsbook vs PM, fee-adjusted edge >5%)
        - Protocol 4: Line Movement (sharp money detection via odds changes)
        - Protocol 6: Risk Management (circuit breaker, position caps, Kelly sizing)
        Auto-execute all qualifying trades. No human approval for paper mode.
        """
        logger.info("🏀 Sports signal loop starting — Protocol 2+4+6 active")
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Scan Polymarket for sports markets
            markets_count = await self.scanner.scan_and_store()
            logger.info(f"  ✅ Scanned {markets_count} sports markets")
            
            # Step 2: Update live scores from ESPN
            events_count = await self.espn.update_live_events()
            logger.info(f"  ✅ Updated {events_count} live events")
            
            # Step 3: Run correlation engine (logical arbitrage)
            correlation_signals = await self.correlation.run_all_checks()
            logger.info(f"  ✅ Found {len(correlation_signals)} correlation signals")
            
            # Step 4: Run cross-odds engine (includes sportsbook comparison + line movement)
            cross_odds_signals = await self.cross_odds.run_analysis()
            logger.info(f"  ✅ Found {len(cross_odds_signals)} cross-odds signals")
            
            # Step 5: Detect momentum signals from live scores
            momentum_signals = await self.espn.detect_momentum_signals()
            logger.info(f"  ✅ Found {len(momentum_signals)} momentum signals")
            
            # Step 6: Store all signals in DB
            all_signals = correlation_signals + cross_odds_signals + momentum_signals
            stored_count = await self.store_signals(all_signals)
            logger.info(f"  ✅ Stored {stored_count} signals")
            
            # Step 7: Create paper trades for high-confidence signals
            trades_created = await self.create_paper_trades(all_signals)
            logger.info(f"  ✅ Created {trades_created} paper trades")
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"✅ Sports signal loop complete ({elapsed:.1f}s)")
            
            return {
                'markets_scanned': markets_count,
                'live_events_updated': events_count,
                'signals_generated': len(all_signals),
                'signals_stored': stored_count,
                'paper_trades_created': trades_created,
                'elapsed_seconds': elapsed,
            }
        except Exception as e:
            logger.error(f"❌ Sports signal loop failed: {e}")
            raise
    
    async def store_signals(self, signals: list) -> int:
        """Store signals in sports_signals table."""
        if not signals:
            return 0
        
        stored = 0
        
        try:
            async with self.db_pool.acquire() as conn:
                for signal in signals:
                    try:
                        await conn.execute("""
                            INSERT INTO sports_signals (
                                edge_type, sport, market_id, market_title,
                                group_id, polymarket_price, fair_value, edge_pct,
                                confidence, signal, reasoning, data_sources, created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
                        """,
                            signal.get('edge_type'),
                            signal.get('sport'),
                            signal.get('market_id'),
                            signal.get('market_title'),
                            signal.get('group_id'),
                            signal.get('polymarket_price'),
                            signal.get('fair_value'),
                            signal.get('edge_pct'),
                            signal.get('confidence'),
                            signal.get('signal'),
                            signal.get('reasoning'),
                            None  # data_sources as JSON (convert dict to JSONB manually if needed)
                        )
                        stored += 1
                    except Exception as e:
                        logger.error(f"Failed to store signal: {e}")
        except Exception as e:
            logger.error(f"Failed to store signals: {e}")
        
        return stored
    
    async def create_paper_trades(self, signals: list) -> int:
        """
        Auto-execute paper trades for qualifying signals.
        Criteria from INTELLIGENCE.md:
          - Edge >= 7%
          - Confidence HIGH, or MEDIUM with edge >= 10%
          - No duplicate open trade for same market_id
          - Circuit breaker: daily loss < -$200
          - Max 50 concurrent positions
        Position sizing: $25 base, $50 if edge > 15%
        """
        from src.execution.paper_trader import PaperTrader
        from src.execution.orderbook import OrderbookChecker

        trader = PaperTrader(self.db_pool)
        checker = OrderbookChecker()
        trades_created = 0

        # --- Pre-flight risk checks (run once, not per-signal) ---
        try:
            daily_pnl = await trader.get_daily_pnl()
            if daily_pnl <= -200:
                logger.warning(f"🛑 Circuit breaker tripped: daily P&L ${daily_pnl:.2f} <= -$200. No new trades.")
                for s in signals:
                    trader.skipped_reasons.append({"market_id": s.get("market_id"), "reason": "circuit_breaker"})
                trader.signals_evaluated_today += len(signals)
                return 0

            open_count = await trader.get_open_count()
        except Exception as e:
            logger.error(f"❌ Risk pre-flight failed: {e}")
            return 0

        for signal in signals:
            trader.signals_evaluated_today += 1
            market_id = signal.get("market_id")
            edge_pct = signal.get("edge_pct")
            confidence = signal.get("confidence", "LOW")
            trade_signal = signal.get("signal", "")

            # --- Qualifying filters ---
            # 1. Must have actionable signal direction
            if trade_signal not in ("BUY", "SELL"):
                logger.debug(f"  ⏭ Skip {market_id}: signal={trade_signal} (not BUY/SELL)")
                trader.skipped_reasons.append({"market_id": market_id, "reason": f"signal_type_{trade_signal}"})
                continue

            # 2. Edge >= 7% and <= 50% (>50% is futures overpricing artifact)
            if edge_pct is None or abs(edge_pct) < 7:
                logger.debug(f"  ⏭ Skip {market_id}: edge={edge_pct} < 7%")
                trader.skipped_reasons.append({"market_id": market_id, "reason": f"low_edge_{edge_pct}"})
                continue
            if abs(edge_pct) > 50:
                logger.debug(f"  ⏭ Skip {market_id}: edge={edge_pct} > 50% (futures artifact)")
                trader.skipped_reasons.append({"market_id": market_id, "reason": f"edge_artifact_{edge_pct}"})
                continue

            # 3. Confidence gate
            if confidence == "HIGH":
                pass  # always ok
            elif confidence == "MEDIUM" and abs(edge_pct) >= 10:
                pass  # medium ok if bigger edge
            else:
                logger.debug(f"  ⏭ Skip {market_id}: confidence={confidence} edge={edge_pct}")
                trader.skipped_reasons.append({"market_id": market_id, "reason": f"confidence_{confidence}_edge_{edge_pct}"})
                continue

            # 4. Max concurrent positions
            if open_count >= 50:
                logger.warning(f"  ⏭ Skip {market_id}: max 50 positions ({open_count} open)")
                trader.skipped_reasons.append({"market_id": market_id, "reason": "max_positions"})
                continue

            # 5. Duplicate check
            try:
                is_dup = await trader.check_duplicate(market_id)
                if is_dup:
                    logger.debug(f"  ⏭ Skip {market_id}: duplicate open trade")
                    trader.skipped_reasons.append({"market_id": market_id, "reason": "duplicate"})
                    continue
            except Exception as e:
                logger.error(f"  Dup check error for {market_id}: {e}")

            # --- Position sizing ---
            size_usd = 50.0 if abs(edge_pct) > 15 else 25.0

            # --- Orderbook depth check (best-effort for paper mode) ---
            depth_info = {}
            try:
                depth_info = await checker.check_depth(
                    token_id=None,
                    side=trade_signal,
                    size_usd=size_usd,
                    market_id=market_id,
                    db_pool=self.db_pool,
                )
                if depth_info.get('has_depth') is False and depth_info.get('available_depth_usd', 0) > 0:
                    old_size = size_usd
                    size_usd = min(size_usd, depth_info['available_depth_usd'] * 0.5)
                    logger.info(f"  📉 Reduced size ${old_size} → ${size_usd:.2f} (thin book: ${depth_info['available_depth_usd']:.0f} available)")
                elif depth_info.get('has_depth') is False and depth_info.get('available_depth_usd', 0) == 0:
                    logger.warning(f"  ⚠️ Empty orderbook for {market_id} — paper trade anyway")
            except Exception as e:
                logger.warning(f"  ⚠️ Depth check error for {market_id}: {e}")

            # --- Execute ---
            try:
                trade_metadata = {
                    "signal": trade_signal,
                    "confidence": confidence,
                    "edge_pct": edge_pct,
                    "reasoning": signal.get("reasoning"),
                    "sport": signal.get("sport"),
                    "fair_value": signal.get("fair_value"),
                    "depth_checked": depth_info.get("depth_checked", False),
                    "has_depth": depth_info.get("has_depth"),
                    "available_depth": depth_info.get("available_depth_usd"),
                    "slippage_pct": depth_info.get("slippage_pct"),
                }
                trade_id = await trader.create_trade(
                    market_id=market_id,
                    market_title=signal.get("market_title", ""),
                    side=trade_signal,
                    entry_price=signal.get("polymarket_price", 0.5),
                    size_usd=size_usd,
                    edge_pct=abs(edge_pct),
                    strategy=signal.get("edge_type", "unknown"),
                    metadata=trade_metadata,
                )
                if trade_id:
                    trades_created += 1
                    open_count += 1  # track locally so we don't re-query every iteration
                    logger.info(
                        f"  📈 Trade #{trade_id}: {trade_signal} {signal.get('market_title','')[:50]} "
                        f"edge={edge_pct:.1f}% ${size_usd}"
                    )
            except Exception as e:
                logger.error(f"  ❌ Trade creation failed for {market_id}: {e}")
                trader.skipped_reasons.append({"market_id": market_id, "reason": f"error: {e}"})

        # Store stats for status endpoint
        self._last_auto_trade_stats = {
            "trades_placed": trades_created,
            "signals_evaluated": trader.signals_evaluated_today,
            "skipped": trader.skipped_reasons,
        }

        return trades_created
