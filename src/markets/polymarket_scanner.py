"""
Polymarket Scanner — Fetch and store weather markets
FIXED: Uses CLOB API pagination instead of broken Gamma tag filtering
"""
import httpx
import asyncio
import json
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
    """Scan Polymarket for active weather markets using CLOB API pagination"""
    
    CLOB_API = "https://clob.polymarket.com/markets"
    GAMMA_EVENTS_API = "https://gamma-api.polymarket.com/events"
    
    # Comprehensive weather keywords for text filtering (more specific)
    WEATHER_KEYWORDS = [
        'temperature', 'high temp', 'low temp', '°f', '°c',
        'fahrenheit', 'celsius', 'will it rain', 'will it snow', 
        'weather forecast', 'precipitation', 'degrees celsius',
        'degrees fahrenheit', 'climate', 'atmospheric',
        'reach 100', 'reach 90', 'reach 80', 'reach 70',  # Temperature thresholds
        'high of', 'low of', 'temperature in',  # Weather phrasing
    ]
    
    # Temperature BUCKET market patterns (for Strategy A targeting)
    BUCKET_PATTERNS = [
        r'\d+\s*-\s*\d+\s*°?[FC]',  # "40-45°F" or "8-9°C"
        r'between\s+\d+\s+and\s+\d+',  # "between 40 and 45"
        r'high temperature be',  # "What will the high temperature be..."
        r'temperature bucket',  # "NYC temperature bucket"
    ]
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    def is_weather_market(self, question: str) -> bool:
        """Check if market question is weather-related (stricter filtering)"""
        question_lower = question.lower()
        
        # Exclude obvious sports markets
        sports_keywords = ['nba', 'nfl', 'mlb', 'nhl', 'formula', 'soccer', 'football', 
                          'basketball', 'baseball', 'hockey', 'game', 'match', 'vs.']
        if any(kw in question_lower for kw in sports_keywords):
            return False
        
        # Must contain weather keywords
        return any(kw in question_lower for kw in self.WEATHER_KEYWORDS)
    
    def is_temp_bucket_market(self, question: str) -> bool:
        """Check if market is specifically a temperature BUCKET market (for Strategy A)"""
        import re
        question_lower = question.lower()
        
        # Must match bucket patterns
        for pattern in self.BUCKET_PATTERNS:
            if re.search(pattern, question_lower, re.IGNORECASE):
                return True
        
        return False
    
    def _parse_market(self, raw: Dict) -> Optional[WeatherMarket]:
        """Parse raw CLOB API response into WeatherMarket"""
        try:
            # Extract core fields
            market_id = raw.get("condition_id") or raw.get("id") or raw.get("market_id")
            question = raw.get("question") or raw.get("title") or raw.get("description", "")
            
            if not market_id or not question:
                return None
            
            # Filter out non-weather markets
            if not self.is_weather_market(question):
                return None
            
            # Tag if it's a bucket market (important for Strategy A)
            is_bucket = self.is_temp_bucket_market(question)
            if 'metadata' not in raw:
                raw['metadata'] = {}
            elif isinstance(raw['metadata'], str):
                import json
                try:
                    raw['metadata'] = json.loads(raw['metadata'])
                except:
                    raw['metadata'] = {}
            raw['metadata']['is_bucket_market'] = is_bucket
            
            # Parse tokens array for YES/NO prices
            tokens = raw.get("tokens", [])
            yes_price = 0.5
            no_price = 0.5
            
            if len(tokens) >= 2:
                # Tokens typically have YES at index 0, NO at index 1
                yes_price = float(tokens[0].get("price", 0.5))
                no_price = float(tokens[1].get("price", 0.5))
            elif "outcomes" in raw and len(raw["outcomes"]) >= 2:
                yes_price = float(raw["outcomes"][0].get("price", 0.5))
                no_price = float(raw["outcomes"][1].get("price", 0.5))
            
            # Parse volume and liquidity
            volume = float(raw.get("volume", 0) or 0)
            liquidity = float(raw.get("liquidity", 0) or 0)
            
            # Parse resolution date (end_date_iso in CLOB API)
            resolution_date = None
            end_date_field = raw.get("end_date_iso") or raw.get("end_date") or raw.get("endDate")
            if end_date_field:
                try:
                    resolution_date = datetime.fromisoformat(
                        end_date_field.replace("Z", "+00:00")
                    )
                except Exception as e:
                    logger.debug(f"Failed to parse date {end_date_field}: {e}")
            
            active = raw.get("active", True)
            
            return WeatherMarket(
                market_id=str(market_id),
                title=question,
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
        Fetch ALL active weather markets from Polymarket using CLOB API pagination.
        Returns list of WeatherMarket objects.
        """
        all_markets = []
        seen_ids = set()
        
        # Method 1: CLOB API pagination with text filter
        logger.info("🔍 Scanning CLOB API for weather markets...")
        cursor = "MA=="  # Initial cursor
        page_count = 0
        max_pages = 50  # Safety limit (5000 markets max)
        
        while cursor and page_count < max_pages:
            try:
                params = {
                    "next_cursor": cursor,
                    "limit": 100
                }
                
                resp = await self.client.get(self.CLOB_API, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                markets_data = data.get("data", [])
                logger.info(f"  Page {page_count + 1}: {len(markets_data)} markets")
                
                for market_raw in markets_data:
                    question = market_raw.get("question", "")
                    if self.is_weather_market(question):
                        parsed = self._parse_market(market_raw)
                        if parsed and parsed.market_id not in seen_ids:
                            all_markets.append(parsed)
                            seen_ids.add(parsed.market_id)
                
                # Get next cursor
                next_cursor = data.get("next_cursor")
                
                # Prevent infinite loop (cursor unchanged)
                if next_cursor == cursor or not next_cursor:
                    break
                    
                cursor = next_cursor
                page_count += 1
                
            except Exception as e:
                logger.error(f"CLOB API error on page {page_count}: {e}")
                break
        
        logger.info(f"📊 CLOB scan complete: {len(all_markets)} weather markets from {page_count} pages")
        
        # Method 2: Try events endpoint for temperature/weather events
        logger.info("🔍 Checking Gamma events API...")
        try:
            # Try a few event searches
            search_terms = ["temperature", "weather", "rain"]
            for term in search_terms:
                try:
                    params = {
                        "active": "true",
                        "closed": "false",
                        "limit": 100
                    }
                    resp = await self.client.get(self.GAMMA_EVENTS_API, params=params)
                    resp.raise_for_status()
                    events = resp.json()
                    
                    if isinstance(events, list):
                        for event in events:
                            # Events may contain markets array
                            event_title = event.get("title", "").lower()
                            if term in event_title:
                                logger.info(f"  Found weather event: {event.get('title')}")
                                # Extract markets from event
                                for market_raw in event.get("markets", []):
                                    # Skip if market_raw is a string (id only)
                                    if isinstance(market_raw, str):
                                        continue
                                    parsed = self._parse_market(market_raw)
                                    if parsed and parsed.market_id not in seen_ids:
                                        all_markets.append(parsed)
                                        seen_ids.add(parsed.market_id)
                    
                except Exception as e:
                    logger.debug(f"Events search for '{term}' failed: {e}")
                    
        except Exception as e:
            logger.error(f"Gamma events API error: {e}")
        
        logger.info(f"✅ Total weather markets found: {len(all_markets)}")
        return all_markets
    
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
                        market.created_at, market.updated_at, json.dumps(market.metadata) if isinstance(market.metadata, dict) else market.metadata
                    )
                    stored += 1
                except Exception as e:
                    logger.error(f"Error storing market {market.market_id}: {e}")
        
        logger.info(f"💾 Stored {stored} markets to database")
        return stored


async def main():
    """Test scanner without DB"""
    scanner = PolymarketScanner()
    try:
        markets = await scanner.scan_weather_markets()
        print(f"\n✅ Found {len(markets)} weather markets:\n")
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
