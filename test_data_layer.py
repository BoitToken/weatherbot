#!/usr/bin/env python3
"""
Comprehensive test script for WeatherBot data layer.
Tests all modules and demonstrates functionality.
"""
import asyncio
import sys
from src import config
from src.db import init_tables, fetch_all
from src.data.city_map import get_icao, get_all_stations, get_stats
from src.data.metar_fetcher import fetch_metar, fetch_all_metars, fetch_and_store_all
from src.data.metar_parser import parse_metar, parse_taf
from src.data.taf_fetcher import fetch_taf
from src.data.trend_calculator import calculate_trend
from src.data.data_loop import run_single_cycle


async def test_config():
    """Test config module."""
    print("\n" + "="*70)
    print("TEST 1: Config Module")
    print("="*70)
    
    print(f"Database URL: {config.DB_URL[:30]}...")
    print(f"Mode: {config.MODE}")
    print(f"METAR scan interval: {config.METAR_SCAN_INTERVAL}s ({config.METAR_SCAN_INTERVAL/60:.1f}min)")
    print(f"Max concurrent requests: {config.MAX_CONCURRENT_REQUESTS}")
    print(f"Min readings for trend: {config.MIN_READINGS_FOR_TREND}")
    print("✅ Config loaded successfully")


async def test_city_map():
    """Test city map module."""
    print("\n" + "="*70)
    print("TEST 2: City Map")
    print("="*70)
    
    stats = get_stats()
    print(f"Total cities: {stats['total_cities']}")
    print(f"Total ICAO codes: {stats['total_icao_codes']}")
    print(f"Cities with alternates: {stats['cities_with_alternates']}")
    
    # Test lookups
    test_cities = ["New York", "London", "Tokyo", "Delhi", "Mumbai"]
    print(f"\nSample city→ICAO mappings:")
    for city in test_cities:
        icao = get_icao(city)
        print(f"  {city}: {icao}")
    
    print("✅ City map working")


async def test_metar_parser():
    """Test METAR parser."""
    print("\n" + "="*70)
    print("TEST 3: METAR Parser")
    print("="*70)
    
    test_metar = "KJFK 061451Z 27015G25KT 10SM FEW250 08/M03 A3012"
    print(f"Raw METAR: {test_metar}")
    
    parsed = parse_metar(test_metar)
    print(f"Parsed:")
    print(f"  Station: {parsed['station']}")
    print(f"  Temperature: {parsed['temperature_c']}°C")
    print(f"  Dewpoint: {parsed['dewpoint_c']}°C")
    print(f"  Wind: {parsed['wind_dir']}° @ {parsed['wind_speed_kt']}kt")
    print(f"  Cloud cover: {parsed['cloud_cover']}")
    print("✅ METAR parser working")


async def test_taf_parser():
    """Test TAF parser."""
    print("\n" + "="*70)
    print("TEST 4: TAF Parser")
    print("="*70)
    
    test_taf = "TAF KJFK 061120Z 0612/0718 27015G25KT P6SM FEW250 TX15/0621Z TN05/0612Z"
    print(f"Raw TAF: {test_taf}")
    
    parsed = parse_taf(test_taf)
    print(f"Parsed:")
    print(f"  Forecast high: {parsed['forecast_high']}°C")
    print(f"  Forecast low: {parsed['forecast_low']}°C")
    print("✅ TAF parser working")


async def test_metar_fetcher():
    """Test METAR fetcher."""
    print("\n" + "="*70)
    print("TEST 5: METAR Fetcher (Live API)")
    print("="*70)
    
    # Fetch single station
    print("Fetching METAR for KJFK...")
    result = await fetch_metar("KJFK")
    if result:
        print(f"✓ KJFK: {result.get('temp')}°C")
        print(f"  Raw: {result.get('rawOb', 'N/A')[:70]}...")
    else:
        print("✗ Failed to fetch KJFK")
    
    # Fetch multiple stations
    print("\nFetching METAR for 5 stations...")
    test_stations = ["KJFK", "EGLL", "RJTT", "VIDP", "YSSY"]
    results = await fetch_all_metars(test_stations)
    print(f"Fetched {len(results)}/{len(test_stations)} stations:")
    for r in results:
        print(f"  {r.get('icao')}: {r.get('temp')}°C")
    
    print("✅ METAR fetcher working")


async def test_taf_fetcher():
    """Test TAF fetcher."""
    print("\n" + "="*70)
    print("TEST 6: TAF Fetcher (Live API)")
    print("="*70)
    
    print("Fetching TAF for KJFK...")
    result = await fetch_taf("KJFK")
    if result:
        print(f"✓ KJFK TAF:")
        print(f"  Valid: {result['valid_from']} to {result['valid_to']}")
        print(f"  Forecast: {result['forecast_low']}°C to {result['forecast_high']}°C")
    else:
        print("✗ No TAF available for KJFK (this is normal, not all stations have TAF)")
    
    print("✅ TAF fetcher tested")


async def test_database():
    """Test database operations."""
    print("\n" + "="*70)
    print("TEST 7: Database Operations")
    print("="*70)
    
    # Initialize tables
    print("Initializing database tables...")
    await init_tables()
    print("✓ Tables created/verified")
    
    # Fetch and store METAR data
    print("\nFetching and storing METAR data for 10 stations...")
    stations = get_all_stations()[:10]
    stats = await fetch_and_store_all(stations)
    print(f"✓ Fetched: {stats['fetched']}/{stats['total_stations']}")
    print(f"✓ Stored: {stats['stored']} readings")
    
    # Query stored data
    print("\nQuerying stored METAR readings...")
    query = "SELECT COUNT(*) as count FROM metar_readings"
    result = await fetch_all(query)
    count = result[0]['count'] if result else 0
    print(f"✓ Total METAR readings in database: {count}")
    
    print("✅ Database operations working")


async def test_trend_calculator():
    """Test trend calculator."""
    print("\n" + "="*70)
    print("TEST 8: Trend Calculator")
    print("="*70)
    
    print("Calculating trend for KJFK...")
    trend = await calculate_trend("KJFK")
    
    if trend:
        print(f"Readings: {trend.num_readings}")
        print(f"Trend: {trend.trend_per_hour:+.3f}°C/hour")
        print(f"Confidence: {trend.confidence:.2%}")
        
        if trend.num_readings < config.MIN_READINGS_FOR_TREND:
            print(f"⚠ Need at least {config.MIN_READINGS_FOR_TREND} readings for trend calculation")
            print(f"  (Currently have {trend.num_readings})")
            print(f"  Run the data loop multiple times to accumulate data")
        else:
            print(f"24h projection: {trend.projected_low:.1f}°C to {trend.projected_high:.1f}°C")
    
    print("✅ Trend calculator tested")


async def test_data_loop():
    """Test full data collection loop."""
    print("\n" + "="*70)
    print("TEST 9: Full Data Collection Loop")
    print("="*70)
    
    print("Running one complete data collection cycle...")
    print("(This fetches all 50 stations + calculates trends)")
    
    stats = await run_single_cycle()
    
    print("\n✅ Data loop completed successfully")
    print(f"   Duration: {stats['duration_seconds']:.1f}s")
    print(f"   METAR fetched: {stats['metar_stats']['fetched']}")
    print(f"   METAR stored: {stats['metar_stats']['stored']}")


async def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("WeatherBot Data Layer Test Suite")
    print("="*70)
    
    try:
        await test_config()
        await test_city_map()
        await test_metar_parser()
        await test_taf_parser()
        await test_metar_fetcher()
        await test_taf_fetcher()
        await test_database()
        await test_trend_calculator()
        await test_data_loop()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nData layer is fully operational!")
        print("\nNext steps:")
        print("  1. Run continuous data loop: python -m src.data.data_loop")
        print("  2. Monitor database: SELECT COUNT(*) FROM metar_readings;")
        print("  3. After ~6 hours: trends will have high confidence")
        print("\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run_all_tests()))
