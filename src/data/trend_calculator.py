"""
Temperature trend calculator using linear regression.
Calculates temperature trends from historical METAR readings.
"""
import numpy as np
from typing import Optional, Dict, Any, NamedTuple
from datetime import datetime, timedelta
from src import config
from src.db import fetch_all


class TrendResult(NamedTuple):
    """Result of trend calculation."""
    station_icao: str
    trend_per_hour: float
    projected_high: float
    projected_low: float
    confidence: float  # R² value
    num_readings: int


async def calculate_trend(station_icao: str) -> Optional[TrendResult]:
    """
    Calculate temperature trend for a station using linear regression.
    
    Args:
        station_icao: 4-letter ICAO airport code
        
    Returns:
        TrendResult with trend statistics, or None if insufficient data
        
    Algorithm:
        1. Query last N hours of METAR readings
        2. Extract temperature and timestamps
        3. Fit linear regression: temp = slope * hours + intercept
        4. Calculate R² (coefficient of determination) for confidence
        5. Project high/low for next 24 hours
    """
    # Query recent readings
    lookback = datetime.utcnow() - timedelta(hours=config.TREND_LOOKBACK_HOURS)
    
    query = """
        SELECT observation_time, temperature_c
        FROM metar_readings
        WHERE station_icao = %s
          AND observation_time > %s
          AND temperature_c IS NOT NULL
        ORDER BY observation_time ASC
    """
    
    readings = await fetch_all(query, (station_icao, lookback))
    
    # Check if we have enough data
    if len(readings) < config.MIN_READINGS_FOR_TREND:
        if config.DEBUG:
            print(f"Insufficient data for {station_icao}: {len(readings)} readings")
        return TrendResult(
            station_icao=station_icao,
            trend_per_hour=0.0,
            projected_high=None,
            projected_low=None,
            confidence=0.0,
            num_readings=len(readings)
        )
    
    # Extract data for regression
    times = []
    temps = []
    
    base_time = readings[0]['observation_time']
    
    for reading in readings:
        # Convert timestamp to hours since first reading
        time_diff = (reading['observation_time'] - base_time).total_seconds() / 3600.0
        times.append(time_diff)
        temps.append(float(reading['temperature_c']))
    
    # Convert to numpy arrays
    X = np.array(times)
    y = np.array(temps)
    
    # Fit linear regression: y = mx + b
    # Using numpy's polyfit (degree 1 = linear)
    coefficients = np.polyfit(X, y, 1)
    slope = coefficients[0]  # trend per hour
    intercept = coefficients[1]
    
    # Calculate R² (coefficient of determination)
    y_pred = slope * X + intercept
    ss_res = np.sum((y - y_pred) ** 2)  # residual sum of squares
    ss_tot = np.sum((y - np.mean(y)) ** 2)  # total sum of squares
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    
    # Ensure R² is between 0 and 1
    r_squared = max(0.0, min(1.0, r_squared))
    
    # Project temperature for next 24 hours
    current_temp = temps[-1]
    hours_ahead = 24
    
    # Project range based on trend
    if slope > 0:
        # Temperature rising
        projected_high = current_temp + (slope * hours_ahead)
        projected_low = current_temp
    else:
        # Temperature falling
        projected_high = current_temp
        projected_low = current_temp + (slope * hours_ahead)  # slope is negative
    
    # Add uncertainty based on confidence
    # Lower confidence = wider range
    uncertainty = (1.0 - r_squared) * 5.0  # up to ±5°C for zero confidence
    projected_high += uncertainty
    projected_low -= uncertainty
    
    result = TrendResult(
        station_icao=station_icao,
        trend_per_hour=slope,
        projected_high=projected_high,
        projected_low=projected_low,
        confidence=r_squared,
        num_readings=len(readings)
    )
    
    return result


async def store_trend(trend: TrendResult) -> bool:
    """
    Store temperature trend in database.
    
    Args:
        trend: TrendResult object
        
    Returns:
        True if stored successfully, False otherwise
    """
    from src.db import execute
    
    try:
        query = """
            INSERT INTO temperature_trends (
                station_icao, calculated_at,
                trend_per_hour, projected_high, projected_low,
                confidence, num_readings
            ) VALUES (%s, NOW(), %s, %s, %s, %s, %s)
        """
        
        await execute(query, (
            trend.station_icao,
            trend.trend_per_hour,
            trend.projected_high,
            trend.projected_low,
            trend.confidence,
            trend.num_readings
        ))
        
        return True
        
    except Exception as e:
        print(f"Error storing trend for {trend.station_icao}: {e}")
        return False


async def calculate_and_store_trend(station_icao: str) -> Optional[TrendResult]:
    """
    Calculate and store temperature trend.
    
    Args:
        station_icao: 4-letter ICAO code
        
    Returns:
        TrendResult if successful, None otherwise
    """
    trend = await calculate_trend(station_icao)
    if trend and trend.num_readings >= config.MIN_READINGS_FOR_TREND:
        await store_trend(trend)
    return trend


async def calculate_all_trends(stations: list[str]) -> Dict[str, Any]:
    """
    Calculate trends for all stations.
    
    Args:
        stations: List of ICAO codes
        
    Returns:
        Dictionary with statistics:
        {
            'total': int,
            'calculated': int,
            'high_confidence': int,
            'trends': list[TrendResult]
        }
    """
    trends = []
    
    for station in stations:
        trend = await calculate_and_store_trend(station)
        if trend:
            trends.append(trend)
    
    # Count high confidence trends
    high_confidence = sum(1 for t in trends if t.confidence >= config.MIN_CONFIDENCE_THRESHOLD)
    
    calculated = sum(1 for t in trends if t.num_readings >= config.MIN_READINGS_FOR_TREND)
    
    return {
        'total': len(stations),
        'calculated': calculated,
        'high_confidence': high_confidence,
        'trends': trends
    }


if __name__ == "__main__":
    # Test trend calculator
    import asyncio
    
    async def test():
        print("Testing trend calculator...")
        print("(Note: Requires database with METAR readings)")
        
        # Test single station
        station = "KJFK"
        print(f"\n1. Calculating trend for {station}:")
        
        trend = await calculate_trend(station)
        if trend:
            print(f"   Readings: {trend.num_readings}")
            print(f"   Trend: {trend.trend_per_hour:+.2f}°C/hour")
            print(f"   24h projection: {trend.projected_low:.1f}°C to {trend.projected_high:.1f}°C")
            print(f"   Confidence: {trend.confidence:.2%} (R²)")
        else:
            print("   ✗ No trend data available")
    
    asyncio.run(test())
