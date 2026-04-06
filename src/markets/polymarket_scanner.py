"""
Polymarket Scanner — Fetch and store weather markets
"""
import httpx
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class WeatherMarket:
    """Polymarket weather market data structure"""
    market_id: str
    title: str
    yes_price: float
    no_price: float
    volume: float
    liquidity: float
    resolution_date: Optional[datetime]
    active: bool
    created_at: datetime
    updated_at: datetime
    metadata: dict


class PolymarketScanner:
    """Scan Polymarket for active weather markets"""
    
    CLOB_API = "https://clob.polymarket.com/markets"
    GAMMA_API = "https://gamma-api.polymarket.com/markets"
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    async def fetch_from_clob(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Fetch markets from CLOB API"""
        try:
            params = {
                "limit": limit,
                "offset": offset,
                "active": "true"
            }
            response = await self.client.get(self.CLOB_API, params=params)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("data", [])
        except Exception as e:
            logger.error(f"CLOB API error: {e}")
            return []
    
    async def fetch_from_gamma(self, tag: str = "weather") -> List[Dict]:
        """Fetch weather markets from Gamma API"""
        try:
            params = {
                "tag": tag,
                "active": "true",
                "limit": 1000
            }
            response = await self.client.get(self.GAMMA_API, params=params)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("data", [])
        except Exception as e:
            logger.error(f"Gamma API error: {e}")
            return []
    
    def is_weather_market(self, title: str) -> bool:
        """Check if market title is weather-related"""
        weather_keywords = [
            "temperature", "weather", "rain", "snow", "precipitation",
            "high", "low", "degrees", "°f", "°c", "celsius", "fahrenheit"
        ]
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in weather_keywords)
    
    def parse_market(self, raw: Dict) -> Optional[WeatherMarket]:
        """Parse raw API response into WeatherMarket"""
        try:
            market_id = raw.get("condition_id") or raw.get("id") or raw.get("market_id")
            title = raw.get("question") or raw.get("title") or raw.get("description", "")
            
            if not market_id or not title:
                return None
            
            # Filter out non-weather markets
            if not self.is_weather_market(title):
                return None
            
            # Parse prices
            outcomes = raw.get("outcomes", [])
            yes_price = 0.5
            no_price = 0.5
            
            if len(outcomes) >= 2:
                yes_price = float(outcomes[0].get("price", 0.5))
                no_price = float(outcomes[1].get("price", 0.5))
            elif "yes_price" in raw:
                yes_price = float(raw["yes_price"])
                no_price = float(raw.get("no_price", 1.0 - yes_price))
            
            # Parse volume and liquidity
            volume = float(raw.get("volume", 0) or 0)
            liquidity = float(raw.get("liquidity", 0) or 0)
            
            # Parse resolution date
            resolution_date = None
            if raw.get("end_date"):
                try:
                    resolution_date = datetime.fromisoformat(
                        raw["end_date"].replace("Z", "+00:00")
                    )
                except:
                    pass
            
            active = raw.get("active", True)
            
            return WeatherMarket(
                market_id=str(market_id),
                title=title,
                yes_price=yes_price,
                no_price=no_price,
                volume=volume,
                liquidity=liquidity,
                resolution_date=resolution_date,
                active=active,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata=raw
            )
        except Exception as e:
            logger.error(f"Error parsing market: {e}")
            return None
    
    async def scan_weather_markets(self) -> List[WeatherMarket]:
        """
        Scan Polymarket for all active weather markets
        Returns list of WeatherMarket objects
        """
        markets = []
        
        # Try Gamma API first (has weather tag)
        logger.info("Fetching from Gamma API...")
        gamma_data = await self.fetch_from_gamma(tag="weather")
        
        for raw in gamma_data:
            market = self.parse_market(raw)
            if market:
                markets.append(market)
        
        # Also try CLOB API with pagination
        logger.info("Fetching from CLOB API...")
        offset = 0
        while True:
            clob_data = await self.fetch_from_clob(limit=100, offset=offset)
            if not clob_data:
                break
            
            for raw in clob_data:
                market = self.parse_market(raw)
                if market and market.market_id not in [m.market_id for m in markets]:
                    markets.append(market)
            
            # Handle pagination
            if len(clob_data) < 100:
                break
            offset += 100
            
            # Safety limit
            if offset > 1000:
                break
        
        logger.info(f"Found {len(markets)} weather markets")
        return markets
    
    async def store_markets(self, markets: List[WeatherMarket]) -> int:
        """
        Store/update weather markets in database
        Returns number of markets stored
        """
        if not self.db_pool:
            logger.warning("No database pool configured")
            return 0
        
        stored = 0
        async with self.db_pool.acquire() as conn:
            for market in markets:
                try:
                    await conn.execute("""
                        INSERT INTO weather_markets (
                            market_id, title, yes_price, no_price,
                            volume, liquidity, resolution_date, active,
                            created_at, updated_at, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (market_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            yes_price = EXCLUDED.yes_price,
                            no_price = EXCLUDED.no_price,
                            volume = EXCLUDED.volume,
                            liquidity = EXCLUDED.liquidity,
                            resolution_date = EXCLUDED.resolution_date,
                            active = EXCLUDED.active,
                            updated_at = EXCLUDED.updated_at,
                            metadata = EXCLUDED.metadata
                    """, 
                        market.market_id, market.title, market.yes_price, market.no_price,
                        market.volume, market.liquidity, market.resolution_date, market.active,
                        market.created_at, market.updated_at, market.metadata
                    )
                    stored += 1
                except Exception as e:
                    logger.error(f"Error storing market {market.market_id}: {e}")
        
        logger.info(f"Stored {stored} markets to database")
        return stored


async def main():
    """Test scanner without DB"""
    scanner = PolymarketScanner()
    try:
        markets = await scanner.scan_weather_markets()
        print(f"\nFound {len(markets)} weather markets:\n")
        for m in markets[:10]:  # Show first 10
            print(f"ID: {m.market_id}")
            print(f"Title: {m.title}")
            print(f"YES: ${m.yes_price:.3f}  NO: ${m.no_price:.3f}")
            print(f"Volume: ${m.volume:,.0f}  Liquidity: ${m.liquidity:,.0f}")
            print(f"Resolution: {m.resolution_date}")
            print()
    finally:
        await scanner.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
