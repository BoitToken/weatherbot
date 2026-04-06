"""
METAR fetcher module for WeatherBot.
Fetches METAR data from NOAA Aviation Weather API with rate limiting.
"""
import asyncio
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime
from src import config

# NOAA Aviation Weather API endpoint
METAR_API_URL = "https://aviationweather.gov/api/data/metar"


async def fetch_metar(station_icao: str) -> Optional[Dict[str, Any]]:
    """
    Fetch latest METAR for a single station.
    
    Args:
        station_icao: 4-letter ICAO airport code
        
    Returns:
        Dictionary containing METAR data, or None if fetch failed
        
    Example return:
        {
            'icao': 'KJFK',
            'raw_text': 'KJFK 061451Z 27015G25KT 10SM FEW250 08/M03 A3012',
            'observation_time': '2026-04-06T14:51:00Z',
            'temp_c': 8.0,
            'dewpoint_c': -3.0,
            'wind_speed_kt': 15,
            'wind_gust_kt': 25,
            'wind_dir_degrees': 270,
            'visibility_statute_mi': 10.0,
            'altim_in_hg': 30.12
        }
    """
    url = f"{METAR_API_URL}?ids={station_icao}&format=json"
    
    try:
        async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            # API returns array of results
            if not data or len(data) == 0:
                if config.DEBUG:
                    print(f"No METAR data for {station_icao}")
                return None
            
            # Return first result
            metar_data = data[0]
            
            # Ensure station_icao is in the result
            metar_data['icao'] = station_icao
            
            return metar_data
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP error fetching METAR for {station_icao}: {e}")
        return None
    except httpx.RequestError as e:
        print(f"Request error fetching METAR for {station_icao}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error fetching METAR for {station_icao}: {e}")
        return None


async def fetch_all_metars(stations: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch METAR data for multiple stations with rate limiting.
    
    Args:
        stations: List of ICAO airport codes
        
    Returns:
        List of METAR data dictionaries (excluding failed fetches)
    """
    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)
    
    async def fetch_with_limit(station: str):
        """Fetch with semaphore rate limiting."""
        async with semaphore:
            return await fetch_metar(station)
    
    # Fetch all stations concurrently (but rate-limited)
    tasks = [fetch_with_limit(station) for station in stations]
    results = await asyncio.gather(*tasks)
    
    # Filter out None results (failed fetches)
    successful = [r for r in results if r is not None]
    
    if config.DEBUG:
        print(f"Fetched {len(successful)}/{len(stations)} stations successfully")
    
    return successful


async def store_metar_reading(metar_data: Dict[str, Any]) -> bool:
    """
    Store METAR reading in database.
    
    Args:
        metar_data: METAR data dictionary from fetch_metar
        
    Returns:
        True if stored successfully, False otherwise
    """
    from src.db import execute
    
    try:
        # Extract fields with defaults
        icao = metar_data.get('icao', metar_data.get('station_id', ''))
        raw_text = metar_data.get('raw_text', metar_data.get('rawOb', ''))
        obs_time = metar_data.get('observation_time', metar_data.get('obsTime', ''))
        
        # Convert observation time to datetime
        if isinstance(obs_time, str):
            # Handle ISO format or epoch timestamp
            try:
                if obs_time.isdigit():
                    obs_datetime = datetime.fromtimestamp(int(obs_time))
                else:
                    obs_datetime = datetime.fromisoformat(obs_time.replace('Z', '+00:00'))
            except:
                obs_datetime = datetime.utcnow()
        else:
            obs_datetime = datetime.utcnow()
        
        # Extract weather parameters (handle different API response formats)
        temp_c = metar_data.get('temp_c', metar_data.get('temp'))
        dewpoint_c = metar_data.get('dewpoint_c', metar_data.get('dewp'))
        wind_speed = metar_data.get('wind_speed_kt', metar_data.get('wspd'))
        wind_dir = metar_data.get('wind_dir_degrees', metar_data.get('wdir'))
        visibility = metar_data.get('visibility_statute_mi', metar_data.get('visib'))
        altimeter = metar_data.get('altim_in_hg', metar_data.get('altim'))
        
        # Convert visibility to meters if in statute miles
        visibility_m = None
        if visibility is not None:
            try:
                visibility_m = float(visibility) * 1609.34  # miles to meters
            except (ValueError, TypeError):
                pass
        
        # Convert altimeter to hPa if in inHg
        pressure_hpa = None
        if altimeter is not None:
            try:
                pressure_hpa = float(altimeter) * 33.8639  # inHg to hPa
            except (ValueError, TypeError):
                pass
        
        # Extract cloud cover from raw text (simplified)
        cloud_cover = "UNKNOWN"
        if raw_text:
            if "SKC" in raw_text or "CLR" in raw_text:
                cloud_cover = "CLEAR"
            elif "FEW" in raw_text:
                cloud_cover = "FEW"
            elif "SCT" in raw_text:
                cloud_cover = "SCATTERED"
            elif "BKN" in raw_text:
                cloud_cover = "BROKEN"
            elif "OVC" in raw_text:
                cloud_cover = "OVERCAST"
        
        # Insert into database (ON CONFLICT DO NOTHING to avoid duplicates)
        query = """
            INSERT INTO metar_readings (
                station_icao, observation_time, raw_metar,
                temperature_c, dewpoint_c, wind_speed_kt, wind_dir,
                visibility_m, pressure_hpa, cloud_cover
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (station_icao, observation_time) DO NOTHING
        """
        
        await execute(query, (
            icao, obs_datetime, raw_text,
            temp_c, dewpoint_c, wind_speed, wind_dir,
            visibility_m, pressure_hpa, cloud_cover
        ))
        
        return True
        
    except Exception as e:
        print(f"Error storing METAR for {metar_data.get('icao', 'UNKNOWN')}: {e}")
        return False


async def fetch_and_store_all(stations: List[str]) -> Dict[str, int]:
    """
    Fetch and store METAR data for all stations.
    
    Args:
        stations: List of ICAO codes
        
    Returns:
        Dictionary with stats: {'fetched': N, 'stored': M}
    """
    # Fetch all METAR data
    metar_results = await fetch_all_metars(stations)
    
    # Store each result
    store_tasks = [store_metar_reading(metar) for metar in metar_results]
    store_results = await asyncio.gather(*store_tasks)
    
    stored_count = sum(1 for r in store_results if r)
    
    return {
        'fetched': len(metar_results),
        'stored': stored_count,
        'total_stations': len(stations)
    }


if __name__ == "__main__":
    # Test the fetcher
    async def test():
        print("Testing METAR fetcher...")
        
        # Test single fetch
        print("\n1. Fetching METAR for KJFK:")
        result = await fetch_metar("KJFK")
        if result:
            print(f"   ✓ {result.get('icao')}: {result.get('raw_text', 'N/A')[:60]}...")
        else:
            print("   ✗ Failed to fetch")
        
        # Test batch fetch
        print("\n2. Fetching METAR for KJFK, EGLL, RJTT:")
        results = await fetch_all_metars(["KJFK", "EGLL", "RJTT"])
        for r in results:
            print(f"   ✓ {r.get('icao')}: {r.get('raw_text', 'N/A')[:60]}...")
        
        print(f"\n✅ Fetched {len(results)}/3 stations")
    
    asyncio.run(test())
