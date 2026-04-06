"""
TAF (Terminal Aerodrome Forecast) fetcher module.
Fetches TAF data from NOAA Aviation Weather API.
"""
import asyncio
import httpx
from typing import Optional, Dict, Any
from datetime import datetime
from src import config
from src.data.metar_parser import parse_taf

# NOAA Aviation Weather API endpoint
TAF_API_URL = "https://aviationweather.gov/api/data/taf"


async def fetch_taf(station_icao: str) -> Optional[Dict[str, Any]]:
    """
    Fetch TAF forecast for a single station.
    
    Args:
        station_icao: 4-letter ICAO airport code
        
    Returns:
        Dictionary containing TAF data, or None if fetch failed
        
    Example return:
        {
            'icao': 'KJFK',
            'raw_text': 'TAF KJFK 061120Z 0612/0718 27015G25KT...',
            'issue_time': '2026-04-06T11:20:00Z',
            'valid_from': '2026-04-06T12:00:00Z',
            'valid_to': '2026-04-07T18:00:00Z',
            'forecast_high': 15.0,
            'forecast_low': 5.0,
            'significant_weather': [],
            'wind_changes': []
        }
    """
    url = f"{TAF_API_URL}?ids={station_icao}&format=json"
    
    try:
        async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            # API returns array of results
            if not data or len(data) == 0:
                if config.DEBUG:
                    print(f"No TAF data for {station_icao}")
                return None
            
            # Get first result
            taf_data = data[0]
            
            # Parse the raw TAF text
            raw_text = taf_data.get('raw_text', taf_data.get('rawTAF', ''))
            parsed = parse_taf(raw_text)
            
            # Extract timing information
            issue_time = taf_data.get('issue_time', taf_data.get('issueTime', ''))
            valid_from = taf_data.get('valid_time_from', taf_data.get('validTimeFrom', ''))
            valid_to = taf_data.get('valid_time_to', taf_data.get('validTimeTo', ''))
            
            # Convert to datetime objects
            try:
                if isinstance(issue_time, str):
                    if issue_time.isdigit():
                        issue_dt = datetime.fromtimestamp(int(issue_time))
                    else:
                        issue_dt = datetime.fromisoformat(issue_time.replace('Z', '+00:00'))
                else:
                    issue_dt = datetime.utcnow()
            except:
                issue_dt = datetime.utcnow()
            
            try:
                if isinstance(valid_from, str):
                    if valid_from.isdigit():
                        valid_from_dt = datetime.fromtimestamp(int(valid_from))
                    else:
                        valid_from_dt = datetime.fromisoformat(valid_from.replace('Z', '+00:00'))
                else:
                    valid_from_dt = datetime.utcnow()
            except:
                valid_from_dt = datetime.utcnow()
            
            try:
                if isinstance(valid_to, str):
                    if valid_to.isdigit():
                        valid_to_dt = datetime.fromtimestamp(int(valid_to))
                    else:
                        valid_to_dt = datetime.fromisoformat(valid_to.replace('Z', '+00:00'))
                else:
                    valid_to_dt = datetime.utcnow()
            except:
                valid_to_dt = datetime.utcnow()
            
            # Combine API data with parsed forecast
            result = {
                'icao': station_icao,
                'raw_text': raw_text,
                'issue_time': issue_dt,
                'valid_from': valid_from_dt,
                'valid_to': valid_to_dt,
                'forecast_high': parsed['forecast_high'],
                'forecast_low': parsed['forecast_low'],
                'significant_weather': ', '.join(parsed['significant_weather']) if parsed['significant_weather'] else None,
                'wind_changes': ', '.join(parsed['wind_changes']) if parsed['wind_changes'] else None,
            }
            
            return result
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP error fetching TAF for {station_icao}: {e}")
        return None
    except httpx.RequestError as e:
        print(f"Request error fetching TAF for {station_icao}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error fetching TAF for {station_icao}: {e}")
        return None


async def store_taf_forecast(taf_data: Dict[str, Any]) -> bool:
    """
    Store TAF forecast in database.
    
    Args:
        taf_data: TAF data dictionary from fetch_taf
        
    Returns:
        True if stored successfully, False otherwise
    """
    from src.db import execute
    
    try:
        query = """
            INSERT INTO taf_forecasts (
                station_icao, issue_time, valid_from, valid_to,
                raw_taf, forecast_high, forecast_low,
                significant_weather, wind_changes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (station_icao, issue_time) DO NOTHING
        """
        
        await execute(query, (
            taf_data['icao'],
            taf_data['issue_time'],
            taf_data['valid_from'],
            taf_data['valid_to'],
            taf_data['raw_text'],
            taf_data['forecast_high'],
            taf_data['forecast_low'],
            taf_data['significant_weather'],
            taf_data['wind_changes']
        ))
        
        return True
        
    except Exception as e:
        print(f"Error storing TAF for {taf_data.get('icao', 'UNKNOWN')}: {e}")
        return False


async def fetch_and_store_taf(station_icao: str) -> bool:
    """
    Fetch and store TAF forecast for a station.
    
    Args:
        station_icao: 4-letter ICAO code
        
    Returns:
        True if successful, False otherwise
    """
    taf_data = await fetch_taf(station_icao)
    if taf_data:
        return await store_taf_forecast(taf_data)
    return False


if __name__ == "__main__":
    # Test the TAF fetcher
    async def test():
        print("Testing TAF fetcher...")
        
        # Test single fetch
        print("\n1. Fetching TAF for KJFK:")
        result = await fetch_taf("KJFK")
        if result:
            print(f"   ✓ {result['icao']}: {result['raw_text'][:80]}...")
            print(f"   Valid: {result['valid_from']} to {result['valid_to']}")
            print(f"   Forecast: {result['forecast_low']}°C to {result['forecast_high']}°C")
        else:
            print("   ✗ Failed to fetch (TAF may not be available)")
        
        # Test another station
        print("\n2. Fetching TAF for EGLL:")
        result = await fetch_taf("EGLL")
        if result:
            print(f"   ✓ {result['icao']}: {result['raw_text'][:80]}...")
            print(f"   Forecast: {result['forecast_low']}°C to {result['forecast_high']}°C")
        else:
            print("   ✗ Failed to fetch (TAF may not be available)")
    
    asyncio.run(test())
