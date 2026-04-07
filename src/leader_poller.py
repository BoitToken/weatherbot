"""
Leader Strategy — Copy-trade Polymarket's top performers.
Polls leader wallet activity and mirrors trades at configured scale.
"""
import asyncio
import json
import logging
import httpx
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger(__name__)

LEADER_WALLET = "0x492442eab586f242b53bda933fd5de859c8a3782"
POLL_INTERVAL = 60  # seconds
DATA_API = "https://data-api.polymarket.com/v1"
GAMMA_API = "https://gamma-api.polymarket.com"


class LeaderPoller:
    def __init__(self, db_pool, telegram_bot=None):
        self.pool = db_pool
        self.telegram_bot = telegram_bot
        self.running = False
        self._last_seen_trades = set()  # Track conditionId+timestamp combos
        self._client: Optional[httpx.AsyncClient] = None
    
    async def start(self):
        """Start polling leader activity."""
        self.running = True
        self._client = httpx.AsyncClient(timeout=15)
        logger.info("Leader Poller started — tracking wallet %s", LEADER_WALLET[:10])
        
        # Load initial state (last 50 trades as "already seen")
        await self._seed_known_trades()
        
        while self.running:
            try:
                await self._poll_cycle()
            except Exception as e:
                logger.error(f"Leader poll error: {e}")
            await asyncio.sleep(POLL_INTERVAL)
    
    async def stop(self):
        self.running = False
        if self._client:
            await self._client.aclose()
    
    async def _seed_known_trades(self):
        """Load recent trades to avoid duplicate alerts on startup."""
        try:
            resp = await self._client.get(
                f"{DATA_API}/activity",
                params={"user": LEADER_WALLET, "limit": 50}
            )
            data = resp.json()
            for a in data:
                if a.get('type') == 'TRADE':
                    key = f"{a.get('conditionId')}_{a.get('timestamp')}"
                    self._last_seen_trades.add(key)
            logger.info(f"Seeded {len(self._last_seen_trades)} known trades")
        except Exception as e:
            logger.error(f"Seed error: {e}")
    
    async def _poll_cycle(self):
        """Single poll cycle — fetch leader activity, detect new trades."""
        resp = await self._client.get(
            f"{DATA_API}/activity",
            params={"user": LEADER_WALLET, "limit": 30}
        )
        data = resp.json()
        
        new_trades = []
        for a in data:
            if a.get('type') != 'TRADE':
                continue
            key = f"{a.get('conditionId')}_{a.get('timestamp')}"
            if key not in self._last_seen_trades:
                self._last_seen_trades.add(key)
                new_trades.append(a)
        
        if not new_trades:
            return
        
        # Group by conditionId (market)
        by_market = {}
        for t in new_trades:
            cid = t.get('conditionId', '')
            if cid not in by_market:
                by_market[cid] = {
                    'trades': [],
                    'total_size': 0,
                    'title': t.get('title', ''),
                    'slug': t.get('slug', ''),
                    'outcome_index': t.get('outcomeIndex', -1),
                    'side': t.get('side', 'BUY'),
                }
            by_market[cid]['trades'].append(t)
            by_market[cid]['total_size'] += float(t.get('usdcSize', 0))
        
        # Process each new market entry
        for cid, info in by_market.items():
            await self._process_leader_trade(cid, info)
    
    async def _process_leader_trade(self, condition_id, info):
        """Process a detected leader trade — classify, store, create copy signal."""
        slug = info['slug'].lower()
        title = info['title']
        total_size = info['total_size']
        
        # Classify
        if 'spread' in slug:
            trade_type = 'SPREAD'
        elif 'total' in slug or 'o-u' in slug:
            trade_type = 'TOTAL'
        else:
            trade_type = 'MONEYLINE'
        
        # Sport detection
        sport = 'OTHER'
        for s, kw in [('NBA', 'nba'), ('NHL', 'nhl'), ('NCAA', 'ncaa'), ('MLB', 'mlb'), ('NFL', 'nfl'), ('SOCCER', 'soccer')]:
            if kw in slug:
                sport = s
                break
        
        # Average entry price
        prices = [float(t.get('price', 0)) for t in info['trades'] if float(t.get('price', 0)) > 0]
        avg_price = sum(prices) / len(prices) if prices else 0.5
        
        # Calculate our copy size (scale_factor from config)
        # Default: $25 per $100K leader position = 0.00025 scale
        our_size = total_size * 0.00025
        our_size = min(our_size, 50.0)  # cap at $50
        our_size = max(our_size, 1.0)   # min $1
        
        # Get current market price from Gamma API
        current_price = avg_price
        polymarket_url = f"https://polymarket.com/event/{info['slug']}"
        
        # Store in DB
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchrow("""
                    INSERT INTO leader_trades 
                    (wallet, condition_id, market_slug, market_title, trade_type, sport,
                     side, outcome_index, leader_price, leader_size, leader_total_position,
                     our_size, our_price, status, polymarket_url)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT (wallet, condition_id, detected_at) DO NOTHING
                    RETURNING id
                """, 
                    LEADER_WALLET, condition_id, info['slug'], title, trade_type, sport,
                    info['side'], info['outcome_index'], avg_price, total_size, total_size,
                    round(our_size, 2), current_price, 'detected', polymarket_url
                )
                
                if result:
                    logger.info(f"LEADER TRADE: {trade_type} {sport} | ${total_size:,.0f} @ {avg_price:.3f} | {title[:50]}")
                    
                    # Also update daily performance
                    today = date.today().isoformat()
                    await conn.execute("""
                        INSERT INTO leader_performance (wallet, date, trades_count, volume, avg_entry_price)
                        VALUES ($1, $2, 1, $3, $4)
                        ON CONFLICT (wallet, date) DO UPDATE SET
                            trades_count = leader_performance.trades_count + 1,
                            volume = leader_performance.volume + EXCLUDED.volume
                    """, LEADER_WALLET, today, total_size, avg_price)
                    
        except Exception as e:
            logger.error(f"DB insert error: {e}")
            return
        
        # Broadcast to Telegram if significant ($10K+)
        if self.telegram_bot and total_size >= 10000:
            msg = (
                f"🎯 <b>LEADER TRADE DETECTED</b>\n\n"
                f"<b>{trade_type}</b> | {sport}\n"
                f"📊 {title}\n"
                f"💰 Leader: ${total_size:,.0f} @ {avg_price:.3f}\n"
                f"📋 Our copy: ${our_size:.2f}\n"
                f"🔗 <a href='{polymarket_url}'>View on Polymarket</a>"
            )
            try:
                await self.telegram_bot.broadcast_to_subscribers(msg)
            except Exception as e:
                logger.error(f"Telegram broadcast error: {e}")
