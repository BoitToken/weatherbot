"""
NOAA GFS Forecast Integration — FREE, no API key needed
Primary forecast source for Strategy A (Forecast Edge)
Fetches from api.weather.gov gridpoints endpoint
"""
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.weather.gov"

# City to NWS grid mapping (office, gridX, gridY)
# Format: {"city_name": ("NWS_OFFICE", gridX, gridY)}
CITY_GRIDS = {
    # US cities with NWS coverage
    "NYC": ("OKX", 33, 37),  # New York - Upton NY office
    "New York": ("OKX", 33, 37),
    "KJFK": ("OKX", 33, 37),
    "KLGA": ("OKX", 34, 37),
    "KEWR": ("OKX", 34, 36),
    
    "Chicago": ("LOT", 76, 73),  # Chicago - Romeoville IL office
    "KORD": ("LOT", 76, 73),
    "KMDW": ("LOT", 76, 72),
    
    "Los Angeles": ("LOX", 154, 44),  # LA - Oxnard CA office
    "KLAX": ("LOX", 154, 44),
    "KBUR": ("LOX", 158, 46),
    
    "Seattle": ("SEW", 124, 67),  # Seattle - Seattle WA office
    "KSEA": ("SEW", 124, 67),
    
    "Dallas": ("FWD", 78, 107),  # Dallas - Fort Worth TX office
    "KDFW": ("FWD", 78, 107),
    
    "Atlanta": ("FFC", 51, 87),  # Atlanta - Peachtree City GA office
    "KATL": ("FFC", 51, 87),
    
    "Miami": ("MFL", 110, 50),  # Miami - Miami FL office
    "KMIA": ("MFL", 110, 50),
    
    "Denver": ("BOU", 65, 61),  # Denver - Boulder CO office
    "KDEN": ("BOU", 65, 61),
    
    "Phoenix": ("PSR", 158, 64),  # Phoenix - Phoenix AZ office
    "KPHX": ("PSR", 158, 64),
    
    "Houston": ("HGX", 67, 100),  # Houston - Dickinson TX office
    "KIAH": ("HGX", 67, 100),
    
    "Philadelphia": ("PHI", 49, 75),  # Philadelphia - Mount Holly NJ office
    "KPHL": ("PHI", 49, 75),
    
    "San Diego": ("SGX", 56, 19),  # San Diego - San Diego CA office
    "KSAN": ("SGX", 56, 19),
    
    "San Francisco": ("MTR", 86, 103),  # SF - Monterey CA office
    "KSFO": ("MTR", 86, 103),
    
    "San Jose": ("MTR", 87, 105),
    "KSJC": ("MTR", 87, 105),
}

# Cache to prevent excessive API calls (10-minute cache per city)
_forecast_cache: Dict[str, Dict] = {}
_cache_timeout = 600  # 10 minutes


async def fetch_noaa_forecast(city: str) -> Optional[Dict]:
    """
    Fetch NOAA GFS forecast for a city.
    
    Args:
        city: City name or ICAO code (e.g., "NYC", "KJFK", "Chicago")
    
    Returns:
        {
            "city": str,
            "forecast_high_f": float,
            "forecast_high_c": float,
            "forecast_low_f": float,
            "forecast_low_c": float,
            "confidence": float,  # 0.85-0.90 for 1-2 day NOAA forecasts
            "source": "noaa_gfs",
            "fetched_at": str (ISO timestamp),
            "raw_periods": list  # Raw forecast periods
        }
        
        Returns None if:
        - City not in US/not covered by NWS
        - API error
        - No forecast data available
    """
    # Check cache
    cache_key = city.upper()
    if cache_key in _forecast_cache:
        cached = _forecast_cache[cache_key]
        age = (datetime.utcnow() - cached["_cached_at"]).total_seconds()
        if age < _cache_timeout:
            logger.debug(f"Using cached NOAA forecast for {city} (age: {age:.0f}s)")
            return cached
    
    # Check if city is covered by NWS
    grid_info = CITY_GRIDS.get(city.upper()) or CITY_GRIDS.get(city)
    if not grid_info:
        logger.debug(f"City {city} not in NWS coverage - use Open-Meteo instead")
        return None
    
    office, grid_x, grid_y = grid_info
    
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            # Fetch forecast from gridpoints API
            url = f"{BASE_URL}/gridpoints/{office}/{grid_x},{grid_y}/forecast"
            
            # Set User-Agent (required by api.weather.gov)
            headers = {
                "User-Agent": "WeatherBot/1.0 (weatherbot@polyedge.ai)",
                "Accept": "application/json"
            }
            
            resp = await client.get(url, headers=headers)
            
            if resp.status_code == 404:
                logger.warning(f"NOAA grid not found for {city} ({office}/{grid_x},{grid_y})")
                return None
            
            resp.raise_for_status()
            data = resp.json()
            
            # Extract forecast periods
            properties = data.get("properties", {})
            periods = properties.get("periods", [])
            
            if not periods:
                logger.warning(f"No forecast periods for {city}")
                return None
            
            # Parse forecast: look for today/tonight/tomorrow
            high_f = None
            low_f = None
            
            for period in periods[:6]:  # Check first 6 periods (3 days)
                name = period.get("name", "").lower()
                temp = period.get("temperature")
                
                # Skip if no temperature
                if temp is None:
                    continue
                
                # "Today" or "Monday" (daytime) = high
                if period.get("isDaytime", False):
                    if high_f is None:
                        high_f = float(temp)
                # "Tonight" or "Monday Night" (nighttime) = low
                else:
                    if low_f is None:
                        low_f = float(temp)
                
                # Stop once we have both
                if high_f is not None and low_f is not None:
                    break
            
            # If we don't have both, use what we have
            if high_f is None and low_f is not None:
                high_f = low_f + 15  # Estimate high as low + 15°F
            elif low_f is None and high_f is not None:
                low_f = high_f - 15  # Estimate low as high - 15°F
            
            if high_f is None:
                logger.warning(f"Could not parse temperature from NOAA forecast for {city}")
                return None
            
            # Convert F to C
            high_c = (high_f - 32) * 5/9
            low_c = (low_f - 32) * 5/9 if low_f else None
            
            result = {
                "city": city,
                "forecast_high_f": round(high_f, 1),
                "forecast_high_c": round(high_c, 1),
                "forecast_low_f": round(low_f, 1) if low_f else None,
                "forecast_low_c": round(low_c, 1) if low_c else None,
                "confidence": 0.87,  # NOAA GFS is 85-90% accurate at 1-2 day horizon
                "source": "noaa_gfs",
                "fetched_at": datetime.utcnow().isoformat(),
                "raw_periods": periods[:6],
                "_cached_at": datetime.utcnow()
            }
            
            # Cache it
            _forecast_cache[cache_key] = result
            
            logger.info(f"✅ NOAA forecast for {city}: {high_f}°F / {high_c}°C")
            return result
            
    except httpx.HTTPStatusError as e:
        logger.error(f"NOAA API HTTP error for {city}: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"NOAA forecast error for {city}: {e}")
        return None


async def store_noaa_forecast(forecast: Dict, db_pool) -> bool:
    """
    Store NOAA forecast in database.
    
    Args:
        forecast: Dict from fetch_noaa_forecast()
        db_pool: Database pool (async wrapper)
    
    Returns:
        True if stored successfully
    """
    if not forecast:
        return False
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO noaa_forecasts (
                    city, forecast_date, high_c, low_c, high_f, low_f,
                    confidence, source, raw_data
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (city, forecast_date, source) DO UPDATE SET
                    high_c = EXCLUDED.high_c,
                    low_c = EXCLUDED.low_c,
                    high_f = EXCLUDED.high_f,
                    low_f = EXCLUDED.low_f,
                    confidence = EXCLUDED.confidence,
                    raw_data = EXCLUDED.raw_data,
                    fetched_at = NOW()
            """,
                forecast["city"],
                datetime.utcnow().date(),  # Today's date
                forecast["forecast_high_c"],
                forecast.get("forecast_low_c"),
                forecast["forecast_high_f"],
                forecast.get("forecast_low_f"),
                forecast["confidence"],
                forecast["source"],
                forecast  # Store entire forecast as JSONB
            )
        return True
    except Exception as e:
        logger.error(f"Error storing NOAA forecast: {e}")
        return False


async def fetch_all_noaa_forecasts(cities: List[str], db_pool=None) -> Dict[str, Dict]:
    """
    Fetch NOAA forecasts for multiple cities concurrently.
    
    Args:
        cities: List of city names or ICAO codes
        db_pool: Optional database pool to store results
    
    Returns:
        Dict mapping city to forecast dict
    """
    results = {}
    sem = asyncio.Semaphore(3)  # Limit concurrent requests (be nice to NWS)
    
    async def fetch_one(city):
        async with sem:
            forecast = await fetch_noaa_forecast(city)
            if forecast:
                results[city] = forecast
                # Store in DB if pool provided
                if db_pool:
                    await store_noaa_forecast(forecast, db_pool)
    
    await asyncio.gather(*[fetch_one(c) for c in cities], return_exceptions=True)
    
    logger.info(f"NOAA: fetched {len(results)}/{len(cities)} forecasts")
    return results


if __name__ == "__main__":
    # Test the module
    import asyncio
    
    async def test():
        logging.basicConfig(level=logging.INFO)
        print("Testing NOAA GFS integration...\n")
        
        # Test US cities (should work)
        test_cities = ["NYC", "Chicago", "Los Angeles", "Seattle"]
        
        print(f"Fetching NOAA forecasts for: {', '.join(test_cities)}\n")
        results = await fetch_all_noaa_forecasts(test_cities)
        
        for city, forecast in results.items():
            print(f"✅ {city}:")
            print(f"   High: {forecast['forecast_high_f']}°F / {forecast['forecast_high_c']}°C")
            print(f"   Low: {forecast.get('forecast_low_f')}°F / {forecast.get('forecast_low_c')}°C")
            print(f"   Confidence: {forecast['confidence'] * 100}%")
            print(f"   Source: {forecast['source']}")
            print()
        
        # Test non-US city (should return None, fall back to Open-Meteo)
        print("Testing London (not in NWS coverage)...")
        london = await fetch_noaa_forecast("London")
        if london is None:
            print("✅ Correctly returned None for London (use Open-Meteo fallback)\n")
        
        print(f"Total fetched: {len(results)}/{len(test_cities)}")
    
    asyncio.run(test())
