"""
Main data collection loop for WeatherBot.
Fetches METAR/TAF data and calculates trends periodically.
"""
import asyncio
from datetime import datetime
from typing import Dict, Any
from src import config
from src.data.city_map import get_all_stations
from src.data.metar_fetcher import fetch_and_store_all
from src.data.trend_calculator import calculate_all_trends
from src.db import init_tables


async def run_data_collection_cycle() -> Dict[str, Any]:
    """
    Run a single data collection cycle:
    1. Fetch METAR for all stations
    2. Parse and store in DB
    3. Calculate trends for all stations
    4. Store trends in DB
    
    Returns:
        Dictionary with cycle statistics
    """
    start_time = datetime.utcnow()
    
    # Get all station codes
    stations = get_all_stations()
    
    print(f"\n{'='*70}")
    print(f"Data Collection Cycle - {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'='*70}")
    print(f"Target stations: {len(stations)}")
    
    # Step 1 & 2: Fetch and store METAR data
    print("\n[1/2] Fetching METAR data...")
    metar_stats = await fetch_and_store_all(stations)
    
    print(f"   ✓ Fetched: {metar_stats['fetched']}/{metar_stats['total_stations']} stations")
    print(f"   ✓ Stored: {metar_stats['stored']} readings")
    
    # Step 3 & 4: Calculate and store trends
    print("\n[2/2] Calculating temperature trends...")
    trend_stats = await calculate_all_trends(stations)
    
    print(f"   ✓ Calculated: {trend_stats['calculated']}/{trend_stats['total']} stations")
    print(f"   ✓ High confidence: {trend_stats['high_confidence']} trends (R² ≥ {config.MIN_CONFIDENCE_THRESHOLD})")
    
    # Print summary of interesting trends
    print("\n📊 Notable Trends:")
    trends = trend_stats['trends']
    
    # Filter to high-confidence trends with significant movement
    significant_trends = [
        t for t in trends 
        if t.confidence >= config.MIN_CONFIDENCE_THRESHOLD 
        and abs(t.trend_per_hour) >= 0.5  # At least 0.5°C/hour change
    ]
    
    if significant_trends:
        # Sort by absolute trend (most volatile first)
        significant_trends.sort(key=lambda t: abs(t.trend_per_hour), reverse=True)
        
        for trend in significant_trends[:10]:  # Top 10
            direction = "rising" if trend.trend_per_hour > 0 else "falling"
            print(f"   {trend.station_icao}: {direction} {abs(trend.trend_per_hour):.2f}°C/hr "
                  f"(confidence: {trend.confidence:.0%})")
    else:
        print("   No significant trends detected")
    
    # Print current temperatures for a few key cities
    print("\n🌡️  Current Temperatures (sample):")
    sample_stations = ["KJFK", "EGLL", "RJTT", "VIDP", "YSSY"]
    
    from src.db import fetch_one
    
    for station in sample_stations:
        query = """
            SELECT temperature_c, observation_time
            FROM metar_readings
            WHERE station_icao = %s
            ORDER BY observation_time DESC
            LIMIT 1
        """
        reading = await fetch_one(query, (station,))
        
        if reading and reading['temperature_c'] is not None:
            # Find matching trend
            station_trend = next((t for t in trends if t.station_icao == station), None)
            trend_str = ""
            if station_trend and station_trend.num_readings >= 3:
                trend_str = f" ({station_trend.trend_per_hour:+.1f}°C/hr)"
            
            print(f"   {station}: {reading['temperature_c']:.1f}°C{trend_str}")
    
    # Calculate cycle duration
    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()
    
    print(f"\n⏱️  Cycle completed in {duration:.1f}s")
    print(f"{'='*70}\n")
    
    return {
        'timestamp': start_time,
        'duration_seconds': duration,
        'metar_stats': metar_stats,
        'trend_stats': trend_stats,
        'significant_trends': len(significant_trends)
    }


async def run_continuous_loop(interval_seconds: int = None):
    """
    Run data collection loop continuously.
    
    Args:
        interval_seconds: Time between cycles (default: config.METAR_SCAN_INTERVAL)
    """
    if interval_seconds is None:
        interval_seconds = config.METAR_SCAN_INTERVAL
    
    print(f"\n🤖 WeatherBot Data Loop Starting")
    print(f"   Interval: {interval_seconds}s ({interval_seconds/60:.1f} minutes)")
    print(f"   Stations: {len(get_all_stations())}")
    print(f"   Press Ctrl+C to stop\n")
    
    # Initialize database tables
    await init_tables()
    print("✓ Database initialized\n")
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            print(f"\n🔄 Cycle #{cycle_count}")
            
            # Run collection cycle
            stats = await run_data_collection_cycle()
            
            # Wait for next cycle
            print(f"⏳ Next cycle in {interval_seconds}s...")
            await asyncio.sleep(interval_seconds)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping data loop...")
        print(f"   Total cycles completed: {cycle_count}")
        print("   Goodbye!\n")
    except Exception as e:
        print(f"\n❌ Error in data loop: {e}")
        raise


async def run_single_cycle():
    """
    Run a single data collection cycle (useful for testing).
    """
    # Initialize database tables
    await init_tables()
    
    # Run one cycle
    stats = await run_data_collection_cycle()
    
    return stats


if __name__ == "__main__":
    # Run continuous loop
    asyncio.run(run_continuous_loop())
