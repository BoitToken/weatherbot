"""
Telegram Alert Bot for WeatherBot.
Sends notifications about signals, trades, and daily summaries.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
import asyncio

from src import config
from src.db import fetch_all, fetch_one

# Setup logging
logger = logging.getLogger(__name__)

# Only import telegram if token is configured
try:
    from telegram import Bot
    from telegram.error import TelegramError
    
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        TELEGRAM_ENABLED = True
    else:
        bot = None
        TELEGRAM_ENABLED = False
        logger.warning("Telegram disabled: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
except ImportError:
    bot = None
    TELEGRAM_ENABLED = False
    logger.warning("Telegram disabled: python-telegram-bot not installed")


async def send_alert(message: str) -> bool:
    """
    Send alert message to Telegram.
    
    Args:
        message: Alert text to send
        
    Returns:
        True if sent successfully, False otherwise
    """
    if not TELEGRAM_ENABLED:
        # Just log to console if Telegram not configured
        logger.info(f"📢 ALERT: {message}")
        return False
    
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode='HTML'
        )
        logger.info(f"✅ Telegram alert sent: {message[:50]}...")
        return True
    except TelegramError as e:
        logger.error(f"❌ Telegram error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to send alert: {e}")
        return False


async def send_signal_alert(city: str, threshold: str, temp: float, price: float, edge: float):
    """
    Send signal found alert.
    Template: 🌡️ Signal found: "{city} {threshold}: METAR {temp}°C, market {price}¢, edge {edge}%"
    """
    message = f"🌡️ <b>Signal Found</b>\n{city} {threshold}\nMETAR: {temp:.1f}°C\nMarket: {price:.1f}¢\nEdge: {edge:.1f}%"
    await send_alert(message)


async def send_trade_placed_alert(city: str, side: str, price: float, size: float):
    """
    Send trade placed alert.
    Template: 🟢 Trade placed: "{city} {side} @ {price}¢ (${size})"
    """
    message = f"🟢 <b>Trade Placed</b>\n{city} {side}\nPrice: {price:.1f}¢\nSize: ${size:.2f}"
    await send_alert(message)


async def send_trade_won_alert(city: str, side: str, pnl: float):
    """
    Send trade won alert.
    Template: ✅ Trade won: "+${pnl} on {city} {side}"
    """
    message = f"✅ <b>Trade Won</b>\n+${pnl:.2f} on {city} {side}"
    await send_alert(message)


async def send_trade_lost_alert(city: str, side: str, pnl: float):
    """
    Send trade lost alert.
    Template: ❌ Trade lost: "-${pnl} on {city} {side}"
    """
    message = f"❌ <b>Trade Lost</b>\n-${abs(pnl):.2f} on {city} {side}"
    await send_alert(message)


async def send_circuit_breaker_alert():
    """
    Send circuit breaker alert.
    Template: 🚨 Circuit breaker: "Daily loss limit hit. All trading halted."
    """
    message = "🚨 <b>CIRCUIT BREAKER</b>\nDaily loss limit hit.\nAll trading halted."
    await send_alert(message)


async def send_daily_summary():
    """
    Send daily summary of trades.
    Template: 📊 Daily summary: "8W/3L, +${pnl}, avg edge {edge}%"
    
    Queries DB for today's trades and formats summary.
    """
    # Get today's date range
    today = datetime.utcnow().date()
    tomorrow = today + timedelta(days=1)
    
    # Query today's trades
    query = """
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
            SUM(pnl) as total_pnl,
            AVG(edge_pct) as avg_edge
        FROM trades
        WHERE closed_at IS NOT NULL
        AND closed_at >= %s
        AND closed_at < %s
    """
    
    try:
        result = await fetch_one(query, (today, tomorrow))
        
        if not result or result['total_trades'] == 0:
            message = "📊 <b>Daily Summary</b>\nNo trades today."
        else:
            wins = result['wins'] or 0
            losses = result['losses'] or 0
            total_pnl = result['total_pnl'] or 0.0
            avg_edge = result['avg_edge'] or 0.0
            
            pnl_sign = "+" if total_pnl >= 0 else ""
            
            message = (
                f"📊 <b>Daily Summary</b>\n"
                f"{wins}W/{losses}L\n"
                f"{pnl_sign}${total_pnl:.2f}\n"
                f"Avg Edge: {avg_edge:.1f}%"
            )
        
        await send_alert(message)
        
    except Exception as e:
        logger.error(f"Failed to send daily summary: {e}")
        await send_alert("📊 <b>Daily Summary</b>\nError generating report.")


# Convenience function for testing
async def test_alert():
    """Send a test alert."""
    await send_alert("🤖 <b>WeatherBot Test Alert</b>\nTelegram is working!")


if __name__ == "__main__":
    # Test the alert system
    asyncio.run(test_alert())
