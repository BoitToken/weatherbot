"""
BTC Trading Performance Reporter
Sends YTD + Daily + Top 10 trades every 8 hours
"""
import asyncio
import asyncpg
import subprocess
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

async def send_btc_trading_report():
    """
    Generate and send BTC trading report to Telegram
    Called by scheduler every 8 hours
    """
    try:
        # Run the report script
        result = subprocess.run(
            ['/bin/bash', '/data/.openclaw/workspace/scripts/send-btc-report-telegram.sh'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"✅ BTC trading report sent at {datetime.now()}")
        else:
            logger.error(f"❌ BTC report failed: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ BTC report error: {e}")
