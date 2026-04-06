"""
Strategy A: "Forecast Edge" (Simple Strategy)
Dead simple: Forecast says X, market says Y, buy X.

Entry: ≤15¢ when forecast confidence >70%
Exit: ≥45¢ (don't wait for resolution)
Scan: Every 2 minutes
"""
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class StrategyA:
    """
    Strategy A: Forecast Edge
    
    Core logic:
    1. Get NOAA forecast for each target city
    2. Get Polymarket temperature BUCKET markets for that city/date
    3. Find the bucket containing the forecasted high temperature
    4. If bucket price ≤ 15¢ → BUY signal
    5. Check held positions: if any position ≥ 45¢ → SELL signal
    """
    
    TARGET_CITIES = [
        # Primary (must have active markets)
        "NYC", "KJFK", "KLGA",
        "London", "EGLL",
        "Chicago", "KORD",
        "Seoul", "RKSI",
        # Secondary
        "Atlanta", "KATL",
        "Dallas", "KDFW",
        "Miami", "KMIA",
        "Seattle", "KSEA",
    ]
    
    ENTRY_THRESHOLD = 0.15  # Buy at ≤15¢
    EXIT_THRESHOLD = 0.45   # Sell at ≥45¢
    POSITION_SIZE_USD = 2.00  # Start small, scale after proof
    FORECAST_CONFIDENCE_MIN = 0.70  # Only trade when forecast confidence > 70%
    
    def __init__(self, db_pool, noaa_module, openmeteo_module, polymarket_scanner):
        """
        Initialize Strategy A
        
        Args:
            db_pool: Database connection pool (async wrapper)
            noaa_module: src.data.noaa_forecast module
            openmeteo_module: src.data.openmeteo module
            polymarket_scanner: src.markets.polymarket_scanner.PolymarketScanner
        """
        self.db = db_pool
        self.noaa = noaa_module
        self.openmeteo = openmeteo_module
        self.scanner = polymarket_scanner
    
    async def get_forecast(self, city: str) -> Optional[Dict]:
        """
        Get forecast for a city.
        Priority: NOAA (primary) → Open-Meteo (secondary for international)
        """
        # Try NOAA first
        forecast = await self.noaa.fetch_noaa_forecast(city)
        if forecast:
            return forecast
        
        # Fall back to Open-Meteo
        logger.debug(f"{city} not in NWS coverage, falling back to Open-Meteo")
        om_forecast = await self.openmeteo.fetch_forecast(city)
        if om_forecast:
            # Convert Open-Meteo format to Strategy A format
            return {
                "city": city,
                "forecast_high_c": om_forecast["forecast_high_c"],
                "forecast_high_f": om_forecast["forecast_high_c"] * 9/5 + 32,
                "forecast_low_c": om_forecast.get("forecast_low_c"),
                "forecast_low_f": om_forecast.get("forecast_low_c") * 9/5 + 32 if om_forecast.get("forecast_low_c") else None,
                "confidence": 0.80,  # Open-Meteo slightly lower confidence than NOAA
                "source": "open_meteo",
                "fetched_at": om_forecast["fetched_at"]
            }
        
        logger.warning(f"No forecast available for {city}")
        return None
    
    async def get_temp_bucket_markets(self, city: str, target_date: date) -> List[Dict]:
        """
        Get temperature bucket markets for a city and date.
        Queries DB for markets matching pattern: "What will the high temperature be in [city]"
        
        Returns:
            List of market dicts with parsed bucket ranges
        """
        # Query weather_markets table for bucket markets
        async with self.db.acquire() as conn:
            results = await conn.fetch("""
                SELECT market_id, title, city, threshold_type, threshold_value,
                       yes_price, no_price, volume_usd, liquidity_usd,
                       resolution_date, metadata
                FROM weather_markets
                WHERE active = true
                  AND city ILIKE $1
                  AND threshold_type LIKE '%bucket%'
                  AND resolution_date::date >= $2
                  AND resolution_date::date <= $3
            """, 
                f"%{city}%",
                target_date,
                target_date + timedelta(days=1)
            )
        
        markets = []
        for row in results:
            # Parse bucket from title
            # Example: "What will the high temperature be in New York on 2026-04-07? 40-45°F"
            title = row['title']
            bucket_low, bucket_high = self._parse_bucket_from_title(title)
            
            if bucket_low is not None and bucket_high is not None:
                markets.append({
                    'market_id': row['market_id'],
                    'title': title,
                    'city': row['city'],
                    'bucket_low_f': bucket_low,
                    'bucket_high_f': bucket_high,
                    'yes_price': float(row['yes_price']),
                    'no_price': float(row['no_price']),
                    'volume': float(row['volume_usd'] or 0),
                    'liquidity': float(row['liquidity_usd'] or 0),
                    'resolution_date': row['resolution_date'],
                })
        
        return markets
    
    def _parse_bucket_from_title(self, title: str) -> tuple:
        """
        Parse bucket range from market title.
        
        Examples:
        - "Will NYC high be 40-45°F?" → (40, 45)
        - "NYC temperature bucket: 55-60F" → (55, 60)
        - "What will the high temperature be in London on 2026-04-07? 8-9°C" → (8, 9)
        
        Returns:
            (low, high) as floats, or (None, None) if can't parse
        """
        import re
        
        # Pattern: "X-Y°F" or "X-Y°C" or "X-YF" or "X-YC"
        pattern = r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*°?[FC]'
        match = re.search(pattern, title, re.IGNORECASE)
        
        if match:
            low = float(match.group(1))
            high = float(match.group(2))
            
            # If in Celsius, convert to Fahrenheit for consistency
            if '°C' in match.group(0) or '°c' in match.group(0):
                low = low * 9/5 + 32
                high = high * 9/5 + 32
            
            return (low, high)
        
        return (None, None)
    
    def find_target_bucket(self, markets: List[Dict], forecast_temp_f: float) -> Optional[Dict]:
        """
        Find the bucket market that contains the forecasted temperature.
        
        Args:
            markets: List of bucket markets
            forecast_temp_f: Forecasted temperature in Fahrenheit
        
        Returns:
            Market dict if found, else None
        """
        for market in markets:
            if market['bucket_low_f'] <= forecast_temp_f < market['bucket_high_f']:
                return market
        
        return None
    
    async def check_open_positions(self) -> List[Dict]:
        """
        Check all open positions for exit signals (≥45¢).
        
        Returns:
            List of positions that should be exited
        """
        async with self.db.acquire() as conn:
            positions = await conn.fetch("""
                SELECT id, market_id, city, side, entry_price, current_price,
                       size_usd, strategy, entered_at
                FROM positions
                WHERE status = 'open'
                  AND strategy = 'forecast_edge'
            """)
        
        exit_signals = []
        for pos in positions:
            current_price = float(pos['current_price'] or pos['entry_price'])
            
            # If current price ≥ 45¢, exit
            if current_price >= self.EXIT_THRESHOLD:
                exit_signals.append(dict(pos))
        
        return exit_signals
    
    async def update_position_prices(self):
        """
        Update current_price for all open positions by querying markets.
        """
        async with self.db.acquire() as conn:
            positions = await conn.fetch("""
                SELECT id, market_id, side FROM positions
                WHERE status = 'open' AND strategy = 'forecast_edge'
            """)
        
        for pos in positions:
            # Get current market price
            async with self.db.acquire() as conn:
                market = await conn.fetchrow("""
                    SELECT yes_price, no_price FROM weather_markets
                    WHERE market_id = $1
                """, pos['market_id'])
            
            if market:
                current = float(market['yes_price']) if pos['side'] == 'YES' else float(market['no_price'])
                
                # Update position
                async with self.db.acquire() as conn:
                    await conn.execute("""
                        UPDATE positions SET current_price = $1 WHERE id = $2
                    """, current, pos['id'])
    
    async def generate_signals(self) -> List[Dict]:
        """
        Generate buy/sell signals for Strategy A.
        
        Returns:
            List of signal dicts:
            {
                "action": "BUY" | "SELL",
                "market_id": str,
                "city": str,
                "side": "YES" | "NO",
                "entry_price": float,
                "size_usd": float,
                "reason": str,
                "forecast": dict,
                "strategy": "forecast_edge"
            }
        """
        signals = []
        
        # 1. Check exit signals first (sell positions ≥45¢)
        await self.update_position_prices()
        exit_positions = await self.check_open_positions()
        
        for pos in exit_positions:
            signals.append({
                "action": "SELL",
                "position_id": pos['id'],
                "market_id": pos['market_id'],
                "city": pos['city'],
                "side": pos['side'],
                "exit_price": pos['current_price'],
                "size_usd": float(pos['size_usd']),
                "reason": f"Early exit at {pos['current_price']:.2f} (≥{self.EXIT_THRESHOLD})",
                "strategy": "forecast_edge"
            })
        
        # 2. Generate buy signals for each target city
        for city in self.TARGET_CITIES:
            try:
                # Get forecast
                forecast = await self.get_forecast(city)
                if not forecast:
                    continue
                
                # Check confidence
                if forecast['confidence'] < self.FORECAST_CONFIDENCE_MIN:
                    logger.debug(f"{city}: forecast confidence {forecast['confidence']} < {self.FORECAST_CONFIDENCE_MIN}, skipping")
                    continue
                
                # Get bucket markets for tomorrow
                tomorrow = date.today() + timedelta(days=1)
                markets = await self.get_temp_bucket_markets(city, tomorrow)
                
                if not markets:
                    logger.debug(f"{city}: no active temperature bucket markets")
                    continue
                
                # Find target bucket
                target = self.find_target_bucket(markets, forecast['forecast_high_f'])
                
                if not target:
                    logger.debug(f"{city}: forecast {forecast['forecast_high_f']}°F not in any bucket")
                    continue
                
                # Check if price ≤ entry threshold
                if target['yes_price'] <= self.ENTRY_THRESHOLD:
                    # BUY signal
                    signals.append({
                        "action": "BUY",
                        "market_id": target['market_id'],
                        "market_title": target['title'],
                        "city": city,
                        "side": "YES",
                        "entry_price": target['yes_price'],
                        "size_usd": self.POSITION_SIZE_USD,
                        "reason": f"Forecast {forecast['forecast_high_f']}°F, bucket {target['bucket_low_f']}-{target['bucket_high_f']}°F at {target['yes_price']:.2f}",
                        "forecast": forecast,
                        "strategy": "forecast_edge",
                        "edge": forecast['confidence'] - target['yes_price']  # Rough edge estimate
                    })
                    
                    logger.info(f"🎯 BUY signal: {city} {target['bucket_low_f']}-{target['bucket_high_f']}°F at {target['yes_price']:.2f} (forecast: {forecast['forecast_high_f']}°F)")
            
            except Exception as e:
                logger.error(f"Error processing {city}: {e}")
        
        return signals
    
    async def run_scan(self) -> Dict:
        """
        Run one scan cycle for Strategy A.
        
        Returns:
            {
                "strategy": "forecast_edge",
                "scan_time": datetime,
                "signals": list of signals,
                "buy_count": int,
                "sell_count": int
            }
        """
        logger.info("🔍 Strategy A (Forecast Edge) scan starting...")
        start_time = datetime.utcnow()
        
        signals = await self.generate_signals()
        
        buy_signals = [s for s in signals if s['action'] == 'BUY']
        sell_signals = [s for s in signals if s['action'] == 'SELL']
        
        logger.info(f"✅ Strategy A scan complete: {len(buy_signals)} BUY, {len(sell_signals)} SELL")
        
        return {
            "strategy": "forecast_edge",
            "scan_time": start_time,
            "signals": signals,
            "buy_count": len(buy_signals),
            "sell_count": len(sell_signals)
        }


if __name__ == "__main__":
    # Test Strategy A
    import sys
    sys.path.insert(0, '/data/.openclaw/workspace/projects/weatherbot')
    from src.db_async import get_async_pool
    from src.data import noaa_forecast, openmeteo
    from src.markets.polymarket_scanner import PolymarketScanner
    
    async def test():
        logging.basicConfig(level=logging.INFO)
        print("Testing Strategy A (Forecast Edge)...\n")
        
        db = get_async_pool()
        scanner = PolymarketScanner(db)
        
        strategy_a = StrategyA(
            db_pool=db,
            noaa_module=noaa_forecast,
            openmeteo_module=openmeteo,
            polymarket_scanner=scanner
        )
        
        result = await strategy_a.run_scan()
        
        print(f"\n📊 Scan Results:")
        print(f"  Strategy: {result['strategy']}")
        print(f"  Time: {result['scan_time']}")
        print(f"  Buy signals: {result['buy_count']}")
        print(f"  Sell signals: {result['sell_count']}")
        
        if result['signals']:
            print(f"\n🎯 Signals:")
            for sig in result['signals']:
                print(f"  {sig['action']} {sig['city']} - {sig['reason']}")
        
        await scanner.close()
    
    asyncio.run(test())
