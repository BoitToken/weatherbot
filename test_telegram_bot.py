#!/usr/bin/env python3
"""
Quick test script to verify Telegram bot is working.
Run: .venv/bin/python test_telegram_bot.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from src.db_async import get_async_pool
from src.alerts.subscriber_bot import get_bot
from src import config


async def main():
    print("🤖 Telegram Bot Verification\n")
    
    # 1. Check config
    print(f"✓ Config loaded:")
    print(f"  TELEGRAM_BOT_TOKEN: {'Set ✅' if config.TELEGRAM_BOT_TOKEN else 'Not set ⚠️'}")
    print(f"  TELEGRAM_ADMIN_CHAT_ID: {'Set ✅' if config.TELEGRAM_ADMIN_CHAT_ID else 'Not set ⚠️'}")
    print()
    
    # 2. Check database table
    pool = get_async_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) as count FROM telegram_subscribers")
        print(f"✓ Database: telegram_subscribers table exists with {row['count']} subscribers")
    
    # 3. Check bot instance
    bot = get_bot()
    if bot:
        print(f"✓ Bot instance: Running (admin: {bot.admin_chat_id})")
        
        # Get subscriber stats
        subscribers = await bot.get_all_subscribers()
        print(f"  - Total subscribers: {len(subscribers)}")
        print(f"  - Active: {len([s for s in subscribers if s.get('is_active')])}")
        print(f"  - Instant alerts: {len([s for s in subscribers if s.get('alert_frequency') == 'instant'])}")
    else:
        print("⚠️  Bot instance: Not initialized (likely no token in .env)")
    
    print()
    
    # 4. Check recent signals
    async with pool.acquire() as conn:
        signals = await conn.fetch("""
            SELECT COUNT(*) as count, MAX(created_at) as latest
            FROM sports_signals
            WHERE created_at >= NOW() - INTERVAL '1 hour'
        """)
        signal = signals[0] if signals else {}
        print(f"✓ Signals: {signal.get('count', 0)} generated in last hour")
        if signal.get('latest'):
            print(f"  - Latest: {signal['latest']}")
    
    # 5. Summary
    print("\n" + "="*50)
    if config.TELEGRAM_BOT_TOKEN and bot:
        print("✅ Telegram bot is READY")
        print("\nTo subscribe:")
        print(f"1. Find your bot on Telegram")
        print(f"2. Send /start")
        print(f"3. You'll receive HIGH confidence signals automatically")
    else:
        print("⚠️  Telegram bot is NOT configured")
        print("\nTo enable:")
        print("1. Message @BotFather on Telegram")
        print("2. Create a new bot and get your token")
        print("3. Add TELEGRAM_BOT_TOKEN to .env")
        print("4. pm2 restart weatherbot")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())
