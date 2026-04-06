"""
Signal Loop — Main scanning loop for weather signal generation
"""
import asyncio
import sys
import json
from datetime import datetime, timedelta
from typing import Optional
import logging

# Import signal components
from .mismatch_detector import MismatchDetector, Signal
from .claude_analyzer import ClaudeAnalyzer, AnalysisResult
from .signal_bus import SignalBus, TradingSignal
from .intelligence import IntelligenceLayer, IntelligenceReport

# Import market components
from ..markets.polymarket_scanner import PolymarketScanner
from ..markets.market_matcher import MarketMatcher

logger = logging.getLogger(__name__)


class SignalLoop:
    """
    Main signal scanning loop
    
    Runs every 5 minutes:
    1. Refresh market prices from Polymarket
    2. Get latest METAR data from DB (fetched by data loop)
    3. Run mismatch detector
    4. For flagged signals: run Claude analyzer
    5. Emit confirmed signals to signal bus
    """
    
    def __init__(
        self,
        db_pool,
        city_map: dict,
        anthropic_api_key: Optional[str] = None,
        bankroll_usd: float = 2000.0,
        min_edge_for_claude: float = 0.15,
        min_edge_for_trade: float = 0.15
    ):
        """
        Initialize signal loop
        
        Args:
            db_pool: Database connection pool
            city_map: City → ICAO mapping
            anthropic_api_key: Claude API key
            bankroll_usd: Current bankroll for position sizing
            min_edge_for_claude: Minimum edge to trigger Claude analysis
            min_edge_for_trade: Minimum edge to emit trade signal
        """
        self.db_pool = db_pool
        self.bankroll_usd = bankroll_usd
        self.min_edge_for_claude = min_edge_for_claude
        self.min_edge_for_trade = min_edge_for_trade
        
        # Initialize components
        self.scanner = PolymarketScanner(db_pool)
        self.matcher = MarketMatcher(city_map)
        self.detector = MismatchDetector(db_pool)
        self.signal_bus = SignalBus(db_pool)
        
        # Initialize Claude (optional)
        self.claude = None
        if anthropic_api_key:
            try:
                self.claude = ClaudeAnalyzer(anthropic_api_key)
                logger.info("Claude analyzer initialized")
            except Exception as e:
                logger.warning(f"Claude analyzer not available: {e}")
        
        # Initialize Intelligence Layer (8-gate system) - Strategy B
        self.intelligence = IntelligenceLayer(db_pool, config)
        logger.info("Intelligence layer initialized (8-gate pre-trade system)")
        
        # Initialize Strategy A (Forecast Edge) - DUAL STRATEGY
        try:
            from .strategy_a import StrategyA
            from ..data import noaa_forecast, openmeteo
            self.strategy_a = StrategyA(
                db_pool=db_pool,
                noaa_module=noaa_forecast,
                openmeteo_module=openmeteo,
                polymarket_scanner=self.scanner
            )
            logger.info("✅ Strategy A (Forecast Edge) initialized")
        except Exception as e:
            logger.error(f"⚠️ Strategy A init failed: {e}")
            self.strategy_a = None
        
        self.running = False
        self.loop_count = 0
        self.last_strategy_a_scan = None
        self.last_strategy_b_scan = None
    
    async def refresh_markets(self) -> int:
        """
        Refresh market prices from Polymarket
        Returns number of markets updated
        """
        logger.info("Refreshing market prices from Polymarket...")
        
        try:
            markets = await self.scanner.scan_weather_markets()
            logger.info(f"Scanner found {len(markets)} total weather markets")
            
            # Match each market to ICAO station and store enriched data
            stored = 0
            async with self.db_pool.acquire() as conn:
                for market in markets:
                    match_result = self.matcher.match_market(market.title)
                    if not match_result:
                        continue  # Skip unmatched markets
                    
                    # Only store active markets with valid metadata
                    meta = market.metadata or {}
                    if meta.get('closed') or meta.get('archived'):
                        continue
                    if not meta.get('accepting_orders', True):
                        continue
                    
                    try:
                        # Store with city/station enrichment
                        await conn.execute("""
                            INSERT INTO weather_markets (
                                market_id, title, city, station_icao,
                                threshold_type, threshold_value, threshold_unit,
                                resolution_date, yes_price, no_price,
                                volume_usd, liquidity_usd, active, metadata, last_updated
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, NOW())
                            ON CONFLICT (market_id) DO UPDATE SET
                                title = EXCLUDED.title,
                                city = EXCLUDED.city,
                                station_icao = EXCLUDED.station_icao,
                                yes_price = EXCLUDED.yes_price,
                                no_price = EXCLUDED.no_price,
                                volume_usd = EXCLUDED.volume_usd,
                                liquidity_usd = EXCLUDED.liquidity_usd,
                                active = EXCLUDED.active,
                                last_updated = NOW()
                        """,
                            market.market_id,
                            market.title,
                            match_result.city,
                            match_result.icao,
                            match_result.threshold_type,
                            match_result.threshold_value,
                            match_result.threshold_unit,
                            market.resolution_date,
                            market.yes_price,
                            market.no_price,
                            market.volume,
                            market.liquidity,
                            market.active,
                            json.dumps(meta) if isinstance(meta, dict) else '{}'
                        )
                        stored += 1
                    except Exception as e:
                        logger.error(f"Error storing market {market.market_id}: {e}")
            
            logger.info(f"✅ Refreshed and stored {stored}/{len(markets)} matched markets")
            return stored
            
        except Exception as e:
            logger.error(f"Error refreshing markets: {e}")
            return 0
    
    async def analyze_with_claude(self, signal: Signal) -> Optional[AnalysisResult]:
        """
        Analyze signal with Claude
        Fetches METAR/TAF data from database
        """
        if not self.claude:
            return None
        
        try:
            # Fetch METAR raw data
            async with self.db_pool.acquire() as conn:
                metar_row = await conn.fetchrow("""
                    SELECT raw_text
                    FROM metar_readings
                    WHERE icao = $1
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, signal.icao)
            
            metar_raw = metar_row['raw_text'] if metar_row else ""
            
            # Use Sonnet for high-edge signals (>25%)
            use_sonnet = abs(signal.edge) > 0.25
            
            # Analyze
            result = await self.claude.analyze_signal(
                signal,
                metar_raw=metar_raw,
                taf_summary="",  # Could fetch TAF here
                use_sonnet=use_sonnet
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing with Claude: {e}")
            return None
    
    def should_emit_signal(self, signal: Signal, claude_result: Optional[AnalysisResult]) -> bool:
        """
        Determine if signal should be emitted to signal bus
        
        Criteria:
        - Edge >= min_edge_for_trade
        - If Claude analyzed: recommendation = TRADE, confidence >= MEDIUM
        - If no Claude: edge >= 20% (higher bar without confirmation)
        """
        # Minimum edge requirement
        if abs(signal.edge) < self.min_edge_for_trade:
            return False
        
        # If Claude analyzed
        if claude_result:
            if claude_result.recommendation != 'TRADE':
                logger.info(f"Claude says {claude_result.recommendation} - skipping {signal.city}")
                return False
            if claude_result.confidence == 'LOW':
                logger.info(f"Claude confidence LOW - skipping {signal.city}")
                return False
            return True
        
        # No Claude analysis - require higher edge
        if abs(signal.edge) < 0.20:
            logger.info(f"No Claude confirmation and edge < 20% - skipping {signal.city}")
            return False
        
        return True
    
    def signal_to_trading_signal(
        self,
        signal: Signal,
        claude_result: Optional[AnalysisResult] = None
    ) -> TradingSignal:
        """
        Convert mismatch Signal to standardized TradingSignal
        """
        # Determine confidence
        if claude_result:
            confidence = claude_result.confidence
            reasoning = claude_result.reasoning
        else:
            # Auto-assign based on edge
            if abs(signal.edge) > 0.30:
                confidence = 'HIGH'
            elif abs(signal.edge) > 0.20:
                confidence = 'MEDIUM'
            else:
                confidence = 'LOW'
            reasoning = "No Claude analysis - high edge detected"
        
        # Calculate expiry (use market resolution date if available)
        expires_at = signal.metadata.get('resolution_date')
        if not expires_at:
            expires_at = datetime.utcnow() + timedelta(hours=signal.hours_to_resolution)
        elif isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        return TradingSignal(
            bot='weather',
            market_id=signal.market_id,
            market_title=signal.market_title,
            side=signal.recommended_side,
            our_probability=signal.our_probability,
            market_price=signal.yes_price if signal.recommended_side == 'YES' else signal.no_price,
            edge=signal.edge,
            confidence=confidence,
            claude_reasoning=reasoning,
            source='gaussian_metar',
            recommended_size_usd=0.0,  # Will be calculated by signal_bus
            expires_at=expires_at,
            created_at=datetime.utcnow(),
            metadata={
                'city': signal.city,
                'icao': signal.icao,
                'current_temp': signal.current_temp_c,
                'threshold': signal.threshold_c,
                'threshold_type': signal.threshold_type,
                'trend': signal.trend_per_hour,
                'hours_to_resolution': signal.hours_to_resolution
            }
        )
    
    async def run_once(self):
        """Run one iteration of the signal loop - DUAL STRATEGY version"""
        self.loop_count += 1
        start_time = datetime.utcnow()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Signal Loop Iteration #{self.loop_count}")
        logger.info(f"Time: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info(f"{'='*60}\n")
        
        # Step 1: Refresh market prices (shared by both strategies)
        markets_updated = await self.refresh_markets()
        
        # DUAL STRATEGY EXECUTION
        # Strategy A: every 120 seconds
        # Strategy B: every 300 seconds
        
        strategy_a_ran = False
        strategy_b_ran = False
        
        # Run Strategy A if 120+ seconds have passed
        if self.strategy_a is not None:
            should_run_a = (
                self.last_strategy_a_scan is None or 
                (start_time - self.last_strategy_a_scan).total_seconds() >= 120
            )
            if should_run_a:
                try:
                    logger.info("🚨 Running Strategy A (Forecast Edge)...")
                    await self.run_strategy_a()
                    self.last_strategy_a_scan = start_time
                    strategy_a_ran = True
                except Exception as e:
                    logger.error(f"Strategy A error: {e}")
        
        # Run Strategy B if 300+ seconds have passed
        should_run_b = (
            self.last_strategy_b_scan is None or 
            (start_time - self.last_strategy_b_scan).total_seconds() >= 300
        )
        if should_run_b:
            try:
                logger.info("🧠 Running Strategy B (Intelligence Layer)...")
                await self.run_strategy_b()
                self.last_strategy_b_scan = start_time
                strategy_b_ran = True
            except Exception as e:
                logger.error(f"Strategy B error: {e}")
        
        # Summary
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Loop #{self.loop_count} Complete")
        logger.info(f"  Markets scanned: {markets_updated}")
        logger.info(f"  Strategy A ran: {strategy_a_ran}")
        logger.info(f"  Strategy B ran: {strategy_b_ran}")
        logger.info(f"  Duration: {elapsed:.1f}s")
        logger.info(f"{'='*60}\n")
    
    async def run_strategy_a(self):
        """Run Strategy A (Forecast Edge) scan"""
        if not self.strategy_a:
            return
        
        result = await self.strategy_a.run_scan()
        
        # Store signals in DB with strategy='forecast_edge'
        for signal in result['signals']:
            try:
                async with self.db_pool.acquire() as conn:
                    if signal['action'] == 'BUY':
                        # Store BUY signal
                        await conn.execute("""
                            INSERT INTO signals (
                                market_id, city, side, our_probability,
                                market_price, edge, confidence, strategy,
                                entry_price, exit_threshold, was_traded, created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, false, NOW())
                        """,
                            signal['market_id'],
                            signal['city'],
                            signal['side'],
                            signal['forecast']['confidence'],
                            signal['entry_price'],
                            signal['edge'],
                            'MEDIUM',
                            'forecast_edge',
                            signal['entry_price'],
                            0.45
                        )
                    elif signal['action'] == 'SELL':
                        # Update position to exited
                        await conn.execute("""
                            UPDATE positions SET
                                status = 'exited',
                                exit_price = $1,
                                exited_at = NOW()
                            WHERE id = $2
                        """,
                            signal['exit_price'],
                            signal['position_id']
                        )
            except Exception as e:
                logger.error(f"Error storing Strategy A signal: {e}")
    
    async def run_strategy_b(self):
        """Run Strategy B (Intelligence Layer - 8 gates) scan"""
        # This is the existing signal detection logic (8-gate system)
        
        # Detect mismatches (uses latest METAR from DB)
        flagged_signals = await self.detector.detect_mismatches()
        
        logger.info(f"\n📊 Scan Results:")
        logger.info(f"  Markets scanned: {markets_updated}")
        logger.info(f"  Mismatches found: {len(flagged_signals)}")
        
        # Step 3: Run flagged signals through 8-gate intelligence layer
        confirmed_count = 0
        skipped_count = 0
        alert_count = 0
        
        for signal in flagged_signals:
            try:
                # Build market dict from signal
                market = {
                    "market_id": signal.market_id,
                    "title": signal.market_title,
                    "city": signal.city,
                    "station_icao": signal.icao,
                    "threshold_value": signal.threshold_c,
                    "threshold_type": signal.threshold_type,
                    "yes_price": signal.yes_price,
                    "no_price": signal.no_price,
                    "volume_usd": signal.metadata.get("volume_usd", 0),
                    "liquidity_usd": signal.metadata.get("liquidity_usd", 0),
                }
                
                # Build METAR data dict
                metar_data = {
                    "temperature_c": signal.current_temp_c,
                    "trend_per_hour": signal.trend_per_hour,
                }
                
                # Run through intelligence layer (ALL 8 gates)
                logger.info(f"\n🧠 Intelligence check: {signal.city} ({signal.icao}) | Edge: {signal.edge:+.1%}")
                report = await self.intelligence.run_full_check(market, metar_data, None)
                
                # Store report in DB for learning
                await self.intelligence.store_report(report)
                
                # Log gate results
                logger.info(f"  Gates passed: {sum(1 for g in report.gates if g.passed)}/8")
                for gate in report.gates:
                    status = "✅" if gate.passed else "❌"
                    logger.info(f"  {status} {gate.gate}: {gate.details[:80]}...")
                
                # Take action based on recommendation
                if report.recommended_action == "TRADE":
                    trading_signal = self.signal_to_trading_signal(signal, None)
                    trading_signal.recommended_size_usd = report.recommended_size_usd
                    trading_signal.confidence = "HIGH" if report.all_gates_passed else "MEDIUM"
                    trading_signal.claude_reasoning = report.reasoning
                    
                    signal_id = await self.signal_bus.emit_signal(trading_signal, self.bankroll_usd)
                    confirmed_count += 1
                    logger.info(f"✅ TRADE: {signal.city} | {report.recommended_side} | ${report.recommended_size_usd:.0f}")
                    
                elif report.recommended_action == "ALERT_ONLY":
                    # High potential but missing some gates — alert CEO
                    logger.info(f"⚠️  ALERT: {signal.city} | Edge {signal.edge:+.1%} | Manual review needed")
                    alert_count += 1
                    # TODO: Send alert to CEO (Telegram/Discord)
                    
                else:  # SKIP
                    logger.info(f"⏭️  SKIP: {signal.city} | {report.reasoning.split(chr(10))[0][:60]}...")
                    skipped_count += 1
                
            except Exception as e:
                logger.error(f"Error processing signal for {signal.city}: {e}")
                skipped_count += 1
        
        # Summary
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Loop #{self.loop_count} Complete")
        logger.info(f"  Scanned: {markets_updated} markets")
        logger.info(f"  Mismatches: {len(flagged_signals)}")
        logger.info(f"  ✅ Trades: {confirmed_count}")
        logger.info(f"  ⚠️  Alerts: {alert_count}")
        logger.info(f"  ⏭️  Skipped: {skipped_count}")
        logger.info(f"  Duration: {elapsed:.1f}s")
        logger.info(f"{'='*60}\n")
    
    async def run(self, interval_seconds: int = 300):
        """
        Run signal loop continuously
        
        Args:
            interval_seconds: Seconds between iterations (default 300 = 5 minutes)
        """
        self.running = True
        logger.info(f"🚀 Signal loop starting (interval: {interval_seconds}s)")
        
        while self.running:
            try:
                await self.run_once()
                
                # Wait for next iteration
                logger.info(f"💤 Sleeping for {interval_seconds}s...\n")
                await asyncio.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Received interrupt - stopping loop")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in signal loop: {e}", exc_info=True)
                logger.info("Continuing after error...")
                await asyncio.sleep(60)  # Wait 1 minute before retry
        
        # Cleanup
        await self.scanner.close()
        logger.info("Signal loop stopped")
    
    def stop(self):
        """Stop the signal loop"""
        self.running = False


async def main():
    """
    Test signal loop (requires database)
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # This would normally come from src.db and src.data.city_map
    # For testing, we'll use mocks
    
    logger.info("Signal Loop Test")
    logger.info("Note: Requires database and METAR data to run properly")
    logger.info("This is a skeleton test - full integration requires Agent 1 deliverables\n")
    
    # Mock city map
    city_map = {
        "New York": "KJFK",
        "Tokyo": "RJTT",
        "London": "EGLL",
        "Chicago": "KORD",
        "Los Angeles": "KLAX"
    }
    
    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set - Claude analysis will be skipped")
    
    logger.info("Signal loop initialized (dry run mode)")
    logger.info("In production, this would:")
    logger.info("  1. Connect to PostgreSQL database")
    logger.info("  2. Scan Polymarket every 5 minutes")
    logger.info("  3. Compare to METAR data")
    logger.info("  4. Analyze with Claude")
    logger.info("  5. Emit trading signals")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
