#!/usr/bin/env python3
"""
Bootstrap script to populate initial data and verify pipeline.
Run this ONCE to get the bot working.
"""
import asyncio
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Bootstrap data pipeline"""
    logger.info("="*70)
    logger.info("WeatherBot Data Bootstrap")
    logger.info("="*70)
    
    # Import modules
    from src.db_async import get_async_pool
    from src.data import noaa_forecast, openmeteo
    from src.markets.polymarket_scanner import PolymarketScanner
    
    db_pool = get_async_pool()
    
    # Step 1: Fetch NOAA forecasts
    logger.info("\n[1/4] Fetching NOAA forecasts...")
    cities = ["NYC", "KJFK", "Chicago", "KORD", "Atlanta", "KATL", 
              "Dallas", "KDFW", "Miami", "KMIA", "Seattle", "KSEA"]
    
    noaa_results = {}
    for city in cities:
        try:
            forecast = await noaa_forecast.fetch_noaa_forecast(city)
            if forecast:
                # Store in DB
                async with db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO noaa_forecasts (
                            city, forecast_date, high_c, low_c, high_f, low_f,
                            confidence, source, raw_data, fetched_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
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
                        datetime.utcnow().date(),
                        forecast["forecast_high_c"],
                        forecast.get("forecast_low_c"),
                        forecast["forecast_high_f"],
                        forecast.get("forecast_low_f"),
                        forecast["confidence"],
                        forecast["source"],
                        forecast
                    )
                noaa_results[city] = forecast
                logger.info(f"  ✅ {city}: {forecast['forecast_high_f']}°F")
        except Exception as e:
            logger.error(f"  ❌ {city}: {e}")
    
    logger.info(f"\n✅ Stored {len(noaa_results)} NOAA forecasts")
    
    # Step 2: Fetch Open-Meteo forecasts for international cities
    logger.info("\n[2/4] Fetching Open-Meteo forecasts...")
    intl_cities = ["EGLL", "RJTT", "RKSI", "VIDP", "YSSY"]
    
    om_results = {}
    for icao in intl_cities:
        try:
            forecast = await openmeteo.fetch_forecast(icao)
            if forecast:
                om_results[icao] = forecast
                logger.info(f"  ✅ {icao}: {forecast['forecast_high_c']}°C")
        except Exception as e:
            logger.error(f"  ❌ {icao}: {e}")
    
    logger.info(f"\n✅ Fetched {len(om_results)} Open-Meteo forecasts")
    
    # Step 3: Scan Polymarket for weather markets
    logger.info("\n[3/4] Scanning Polymarket for weather markets...")
    scanner = PolymarketScanner(db_pool)
    
    try:
        markets = await scanner.scan_weather_markets()
        stored = await scanner.store_markets(markets)
        logger.info(f"✅ Found {len(markets)} weather markets")
        logger.info(f"✅ Stored {stored} markets to DB")
        
        if markets:
            logger.info(f"\n📊 Sample markets:")
            for m in markets[:5]:
                logger.info(f"  - {m.title[:80]}...")
                logger.info(f"    YES: ${m.yes_price:.3f}  Volume: ${m.volume:,.0f}")
        else:
            logger.warning("⚠️  No active weather markets found (may be seasonal)")
    except Exception as e:
        logger.error(f"❌ Market scan failed: {e}")
    finally:
        await scanner.close()
    
    # Step 4: Verify DB state
    logger.info("\n[4/4] Verifying database state...")
    
    async with db_pool.acquire() as conn:
        for table in ['noaa_forecasts', 'weather_markets', 'metar_readings', 'signals', 'trades']:
            result = await conn.fetchrow(f"SELECT COUNT(*) as count FROM {table}")
            count = result['count'] if result else 0
            status = "✅" if count > 0 else "⚠️ "
            logger.info(f"  {status} {table}: {count} rows")
    
    logger.info("\n" + "="*70)
    logger.info("Bootstrap complete!")
    logger.info("="*70)
    logger.info("\nNext steps:")
    logger.info("1. Check dashboard at http://localhost:6010")
    logger.info("2. Restart brobot: pm2 restart brobot")
    logger.info("3. Watch logs: pm2 logs brobot")
    logger.info("")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ Bootstrap failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
