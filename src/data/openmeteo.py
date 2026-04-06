"""
Open-Meteo API integration — free weather forecast, no API key needed.
Used as Gate 1 Source B in the intelligence layer.
"""
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.open-meteo.com/v1/forecast"

# City coordinates (lat/lon for Open-Meteo) - All 50 cities from city_map.py
CITY_COORDS = {
    # United States (15 cities)
    "KJFK": (40.6413, -73.7781),   # New York JFK
    "KLGA": (40.7769, -73.8740),   # New York LaGuardia
    "KEWR": (40.6895, -74.1745),   # New York Newark
    "KLAX": (33.9425, -118.4081),  # Los Angeles
    "KBUR": (34.2007, -118.3587),  # Los Angeles Burbank
    "KSNA": (33.6757, -117.8682),  # Los Angeles John Wayne
    "KORD": (41.9742, -87.9073),   # Chicago O'Hare
    "KMDW": (41.7868, -87.7522),   # Chicago Midway
    "KIAH": (29.9902, -95.3368),   # Houston
    "KPHX": (33.4342, -112.0080),  # Phoenix
    "KPHL": (39.8729, -75.2437),   # Philadelphia
    "KSAT": (29.5337, -98.4698),   # San Antonio
    "KSAN": (32.7338, -117.1933),  # San Diego
    "KDFW": (32.8998, -97.0403),   # Dallas
    "KSJC": (37.3626, -121.9290),  # San Jose
    "KAUS": (30.1945, -97.6699),   # Austin
    "KJAX": (30.4941, -81.6879),   # Jacksonville
    "KSFO": (37.6213, -122.3790),  # San Francisco
    "KSEA": (47.4502, -122.3088),  # Seattle
    "KDEN": (39.8561, -104.6737),  # Denver
    
    # Europe (8 cities)
    "EGLL": (51.4700, -0.4543),    # London Heathrow
    "EGSS": (51.8850, 0.2350),     # London Stansted
    "EGLC": (51.5053, 0.0553),     # London City
    "LFPG": (49.0097, 2.5479),     # Paris CDG
    "LFPO": (48.7252, 2.3597),     # Paris Orly
    "EDDB": (52.3667, 13.5033),    # Berlin
    "LEMD": (40.4983, -3.5676),    # Madrid
    "LIRF": (41.8003, 12.2389),    # Rome Fiumicino
    "EHAM": (52.3086, 4.7639),     # Amsterdam
    "EBBR": (50.9010, 4.4844),     # Brussels
    "LOWW": (48.1103, 16.5697),    # Vienna
    
    # Asia-Pacific (7 cities)
    "RJTT": (35.5494, 139.7798),   # Tokyo Haneda
    "RJAA": (35.7647, 140.3864),   # Tokyo Narita
    "RKSI": (37.4602, 126.4407),   # Seoul Incheon
    "ZBAA": (40.0801, 116.5846),   # Beijing
    "ZSSS": (31.1434, 121.8052),   # Shanghai Pudong
    "VHHH": (22.3080, 113.9185),   # Hong Kong
    "WSSS": (1.3644, 103.9915),    # Singapore
    "YSSY": (-33.9399, 151.1753),  # Sydney
    
    # India (10 cities)
    "VIDP": (28.5665, 77.1031),    # Delhi
    "VIDD": (28.5562, 77.0999),    # Delhi alternate
    "VABB": (19.0896, 72.8656),    # Mumbai
    "VOBL": (12.9496, 77.6682),    # Bangalore
    "VECC": (22.6547, 88.4467),    # Kolkata
    "VOMM": (12.9941, 80.1709),    # Chennai
    "VOHS": (17.2403, 78.4294),    # Hyderabad
    "VAPO": (18.5821, 73.9197),    # Pune
    "VAAH": (23.0772, 72.6347),    # Ahmedabad
    "VIJP": (26.8242, 75.8122),    # Jaipur
    "VOGO": (15.3808, 73.8314),    # Goa
    
    # Americas (5 cities)
    "CYYZ": (43.6777, -79.6248),   # Toronto
    "MMMX": (19.4363, -99.0721),   # Mexico City
    "SBGR": (-23.4356, -46.4731),  # São Paulo Guarulhos
    "SBSP": (-23.6261, -46.6564),  # São Paulo Congonhas
    "SAEZ": (-34.8222, -58.5358),  # Buenos Aires
    "SPJC": (-12.0219, -77.1143),  # Lima
    
    # Middle East & Africa (5 cities)
    "OMDB": (25.2528, 55.3644),    # Dubai
    "LLBG": (32.0114, 34.8867),    # Tel Aviv
    "FAJS": (-26.1392, 28.2460),   # Johannesburg
    "HECA": (30.1219, 31.4056),    # Cairo
    "LTFM": (41.2751, 28.7519),    # Istanbul
    "LTBA": (40.9769, 28.8146),    # Istanbul Atatürk
}

async def fetch_forecast(icao: str) -> Optional[Dict]:
    """Fetch Open-Meteo hourly forecast for a station.
    
    Returns: {
        "forecast_high_c": float,
        "forecast_low_c": float,
        "hourly_temps": [list of temps for next 24h],
        "precipitation_probability": float,
        "source": "open-meteo"
    }
    """
    coords = CITY_COORDS.get(icao)
    if not coords:
        logger.warning(f"No coordinates for {icao}")
        return None
    
    lat, lon = coords
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation_probability,windspeed_10m",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "UTC",
        "forecast_days": 2
    }
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(BASE_URL, params=params)
            if resp.status_code != 200:
                logger.error(f"Open-Meteo error for {icao}: {resp.status_code}")
                return None
            
            data = resp.json()
            daily = data.get("daily", {})
            hourly = data.get("hourly", {})
            
            return {
                "forecast_high_c": daily.get("temperature_2m_max", [None])[0],
                "forecast_low_c": daily.get("temperature_2m_min", [None])[0],
                "hourly_temps": hourly.get("temperature_2m", [])[:24],
                "precipitation_probs": hourly.get("precipitation_probability", [])[:24],
                "wind_speeds": hourly.get("windspeed_10m", [])[:24],
                "source": "open-meteo",
                "fetched_at": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to fetch Open-Meteo data for {icao}: {e}")
        return None

async def fetch_all_forecasts(stations: list) -> Dict[str, Dict]:
    """Fetch forecasts for multiple stations concurrently."""
    results = {}
    sem = asyncio.Semaphore(5)  # Rate limit
    
    async def fetch_one(icao):
        async with sem:
            result = await fetch_forecast(icao)
            if result:
                results[icao] = result
    
    await asyncio.gather(*[fetch_one(s) for s in stations])
    logger.info(f"Open-Meteo: fetched {len(results)}/{len(stations)} forecasts")
    return results


if __name__ == "__main__":
    # Test the module
    import asyncio
    
    async def test():
        print("Testing Open-Meteo integration...")
        print(f"Total coordinates: {len(CITY_COORDS)}")
        
        # Test NYC
        print("\nFetching NYC (KJFK) forecast...")
        result = await fetch_forecast("KJFK")
        if result:
            print(f"  Forecast high: {result['forecast_high_c']}°C")
            print(f"  Forecast low: {result['forecast_low_c']}°C")
            print(f"  Hourly temps (24h): {len(result['hourly_temps'])} data points")
        else:
            print("  FAILED")
        
        # Test multiple
        print("\nFetching multiple cities...")
        results = await fetch_all_forecasts(["KJFK", "EGLL", "RJTT", "VIDP"])
        print(f"  Fetched: {len(results)}/4 cities")
        for icao, data in results.items():
            print(f"  {icao}: {data['forecast_high_c']}°C")
    
    asyncio.run(test())
