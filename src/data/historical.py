"""
Historical temperature patterns — what did this city do on this date historically?
Uses Open-Meteo historical API (free, no key needed).
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"

async def fetch_historical_pattern(icao: str, target_date: datetime, years_back: int = 5) -> Optional[Dict]:
    """Fetch what this city's temperature was on this date in past years.
    
    Returns: {
        "avg_high_c": float (average high on this date over past N years),
        "avg_low_c": float,
        "max_high_c": float (hottest this date has ever been),
        "min_low_c": float,
        "data_points": int,
        "yearly_highs": {2021: 22.5, 2022: 24.1, ...}
    }
    """
    from src.data.openmeteo import CITY_COORDS
    coords = CITY_COORDS.get(icao)
    if not coords:
        logger.warning(f"No coordinates for {icao}")
        return None
    
    lat, lon = coords
    highs = {}
    lows = {}
    
    for years_ago in range(1, years_back + 1):
        # Don't go into the future
        if target_date.year - years_ago < 1940:  # Historical data limit
            continue
            
        past_date = target_date.replace(year=target_date.year - years_ago)
        start = past_date.strftime("%Y-%m-%d")
        end = start  # Single day
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(HISTORICAL_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": start,
                    "end_date": end,
                    "daily": "temperature_2m_max,temperature_2m_min",
                    "timezone": "UTC"
                })
                
                if resp.status_code == 200:
                    data = resp.json()
                    daily = data.get("daily", {})
                    h = daily.get("temperature_2m_max", [None])[0]
                    l = daily.get("temperature_2m_min", [None])[0]
                    if h is not None:
                        highs[past_date.year] = h
                    if l is not None:
                        lows[past_date.year] = l
                else:
                    logger.debug(f"Historical API returned {resp.status_code} for {icao} {start}")
                    
        except Exception as e:
            logger.warning(f"Historical fetch failed for {icao} {start}: {e}")
            continue
    
    if not highs:
        logger.warning(f"No historical data found for {icao}")
        return None
    
    return {
        "avg_high_c": sum(highs.values()) / len(highs),
        "avg_low_c": sum(lows.values()) / len(lows) if lows else None,
        "max_high_c": max(highs.values()),
        "min_low_c": min(lows.values()) if lows else None,
        "data_points": len(highs),
        "yearly_highs": highs,
        "yearly_lows": lows,
        "source": "open-meteo-historical",
        "fetched_at": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    # Test the module
    import asyncio
    
    async def test():
        print("Testing Open-Meteo Historical integration...")
        
        # Test NYC historical pattern for today
        print("\nFetching NYC (KJFK) historical pattern for today's date...")
        result = await fetch_historical_pattern("KJFK", datetime.utcnow(), years_back=5)
        
        if result:
            print(f"  Average high: {result['avg_high_c']:.1f}°C")
            print(f"  Max high: {result['max_high_c']:.1f}°C")
            print(f"  Min low: {result['min_low_c']:.1f}°C")
            print(f"  Data points: {result['data_points']}")
            print(f"  Yearly highs: {result['yearly_highs']}")
        else:
            print("  FAILED")
    
    asyncio.run(test())
