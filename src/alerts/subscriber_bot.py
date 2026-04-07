"""
Telegram Subscriber Bot — Arbitrage Alert System
Handles subscriber commands, broadcasts signals, and sends daily summaries.

Uses python-telegram-bot v21.5 async style.
Database encoding is SQL_ASCII — no emoji in DB strings, only in message text.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import asyncio
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import TelegramError

from src import config
from src.db_async import get_async_pool
from src.alerts.invite_gate import InviteGate

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Calcutta')


class SubscriberBot:
    """Telegram bot for sports arbitrage alerts."""
    
    def __init__(self, bot_token: str, admin_chat_id: str):
        self.bot_token = bot_token
        self.admin_chat_id = admin_chat_id
        self.invite_gate = None  # Set after pool init
        self.app: Optional[Application] = None
        self.pool = get_async_pool()
    
    # ═════════════════════════════════════════════════════════════
    # DATABASE HELPERS
    # ═════════════════════════════════════════════════════════════
    
    async def get_subscriber(self, chat_id: int) -> Optional[Dict]:
        """Get subscriber record from DB."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM telegram_subscribers WHERE chat_id = %s",
                    (chat_id,)
                )
                row = await cur.fetchone()
                if row:
                    columns = [desc[0] for desc in cur.description]
                    return dict(zip(columns, row))
        return None
    
    async def subscribe_user(self, chat_id: int, username: str, first_name: str):
        """Add or re-activate subscriber."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO telegram_subscribers (chat_id, username, first_name, is_active)
                    VALUES (%s, %s, %s, true)
                    ON CONFLICT (chat_id) DO UPDATE SET is_active = true, subscribed_at = NOW()
                """, (chat_id, username, first_name))
                await conn.commit()
    
    async def unsubscribe_user(self, chat_id: int):
        """Deactivate subscriber."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE telegram_subscribers SET is_active = false WHERE chat_id = %s",
                    (chat_id,)
                )
                await conn.commit()
    
    async def update_settings(self, chat_id: int, **kwargs):
        """Update subscriber preferences."""
        fields = []
        values = []
        for key, val in kwargs.items():
            fields.append(f"{key} = %s")
            values.append(val)
        
        if not fields:
            return
        
        values.append(chat_id)
        query = f"UPDATE telegram_subscribers SET {', '.join(fields)} WHERE chat_id = %s"
        
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, values)
                await conn.commit()
    
    async def get_all_subscribers(self, instant_only: bool = False) -> List[Dict]:
        """Get all active subscribers."""
        query = "SELECT * FROM telegram_subscribers WHERE is_active = true"
        if instant_only:
            query += " AND alert_frequency = 'instant'"
        
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                rows = await cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in rows]
    
    async def increment_alert_count(self, chat_id: int):
        """Increment total_alerts_sent and update last_alert_at."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE telegram_subscribers 
                    SET total_alerts_sent = total_alerts_sent + 1, last_alert_at = NOW()
                    WHERE chat_id = %s
                """, (chat_id,))
                await conn.commit()
    
    # ═════════════════════════════════════════════════════════════
    # COMMAND HANDLERS
    # ═════════════════════════════════════════════════════════════
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Subscribe (invite-only)."""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        await self.subscribe_user(
            chat_id=chat_id,
            username=user.username or "",
            first_name=user.first_name or ""
        )
        
        # Admin auto-approve
        if str(chat_id) == str(self.admin_chat_id):
            await self.invite_gate.approve_admin(chat_id)
            msg = (
                "👑 <b>Welcome, Boss!</b>\n\n"
                "Full access. Admin commands:\n"
                "/invite — Generate codes\n"
                "/approve &lt;chat_id&gt; — Approve user\n"
                "/revoke &lt;chat_id&gt; — Kick user\n"
                "/subscribers — List all\n"
                "/broadcast <msg> — Send to all\n\n"
                "Regular: /signals /trades /ipl /arb /stats"
            )
            await update.message.reply_text(msg, parse_mode='HTML')
            return
        
        if await self.invite_gate.is_approved(chat_id):
            await update.message.reply_text("✅ <b>Already subscribed!</b> Use /help for commands.", parse_mode='HTML')
            return
        
        # Not approved - ask for code
        msg = (
            "🔒 <b>Private Bot — Invite Only</b>\n\n"
            "PolyEdge Arbitrage Alerts is invite-only.\n\n"
            "Send your access code now.\n\n"
            "No code? Contact @ahswaat"
        )
        await update.message.reply_text(msg, parse_mode='HTML')
    
    async def handle_code_entry(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input - check if invite code."""
        chat_id = update.effective_chat.id
        if self.invite_gate and not await self.invite_gate.is_approved(chat_id):
            text = (update.message.text or "").strip()
            if await self.invite_gate.try_invite_code(chat_id, text):
                await update.message.reply_text(
                    "✅ <b>Access Granted!</b>\n\n"
                    "Welcome to PolyEdge Arbitrage Alerts.\n\n"
                    "/signals /trades /ipl /arb /stats /settings /help\n\n"
                    "Alerts start now!",
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text("❌ Invalid code. Contact @ahswaat", parse_mode='HTML')

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unsubscribe from alerts."""
        chat_id = update.effective_chat.id
        await self.unsubscribe_user(chat_id)
        
        message = (
            "👋 <b>Unsubscribed</b>\n\n"
            "You will no longer receive alerts.\n"
            "Use /start to re-subscribe anytime."
        )
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot stats for today."""
        # Query today's signals
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT COUNT(*) as signals_today
                    FROM sports_signals
                    WHERE created_at >= CURRENT_DATE
                """)
                signals_row = await cur.fetchone()
                signals_today = signals_row[0] if signals_row else 0
                
                # Active trades
                await cur.execute("""
                    SELECT COUNT(*) as active_trades, COALESCE(SUM(size_usd), 0) as deployed
                    FROM paper_trades_live
                    WHERE status = 'open'
                """)
                trades_row = await cur.fetchone()
                active_trades = trades_row[0] if trades_row else 0
                deployed = float(trades_row[1]) if trades_row else 0
                
                # Today's P&L
                await cur.execute("""
                    SELECT COALESCE(SUM(pnl_usd), 0) as pnl
                    FROM paper_trades_live
                    WHERE closed_at >= CURRENT_DATE
                """)
                pnl_row = await cur.fetchone()
                pnl = float(pnl_row[0]) if pnl_row else 0
                
                # Win rate
                await cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins
                    FROM paper_trades_live
                    WHERE closed_at IS NOT NULL
                """)
                win_row = await cur.fetchone()
                total = win_row[0] if win_row else 0
                wins = win_row[1] if win_row else 0
                win_rate = (wins / total * 100) if total > 0 else 0
                
                # Next match (IPL)
                await cur.execute("""
                    SELECT event_name, start_time
                    FROM live_events
                    WHERE sport = 'IPL' AND status = 'scheduled'
                    ORDER BY start_time ASC
                    LIMIT 1
                """)
                match_row = await cur.fetchone()
                if match_row:
                    next_match = f"{match_row[0]} @ {match_row[1].strftime('%I:%M %p IST')}"
                else:
                    next_match = "No upcoming matches"
        
        pnl_sign = "+" if pnl >= 0 else ""
        message = (
            f"📊 <b>Bot Status</b>\n\n"
            f"<b>Today:</b>\n"
            f"Signals: {signals_today} generated\n"
            f"Active Trades: {active_trades} (${deployed:.0f} deployed)\n"
            f"P&amp;L: {pnl_sign}${pnl:.2f}\n"
            f"Win Rate: {win_rate:.1f}% ({wins}/{total})\n\n"
            f"<b>Next Match:</b>\n{next_match}"
        )
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show last 5 signals."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT sport, market_title, polymarket_price, fair_value, edge_pct, signal, reasoning, created_at
                    FROM sports_signals
                    ORDER BY created_at DESC
                    LIMIT 5
                """)
                rows = await cur.fetchall()
        
        if not rows:
            await update.message.reply_text("No signals yet.", parse_mode='HTML')
            return
        
        message = "<b>📊 Last 5 Signals</b>\n\n"
        for row in rows:
            sport, title, pm_price, fair, edge, signal, reasoning, created = row
            edge_pct = float(edge) if edge else 0
            message += (
                f"<b>{sport}: {title[:40]}</b>\n"
                f"{signal} | Edge: {edge_pct:+.1f}%\n"
                f"PM: {pm_price:.2f} | Fair: {fair:.2f}\n"
                f"{reasoning[:80]}...\n"
                f"<i>{created.strftime('%H:%M IST')}</i>\n\n"
            )
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show active paper trades."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT market_title, side, entry_price, size_usd, 
                           (current_price - entry_price) * size_usd / entry_price as unrealized_pnl
                    FROM paper_trades_live
                    WHERE status = 'open'
                    ORDER BY entered_at DESC
                    LIMIT 10
                """)
                rows = await cur.fetchall()
        
        if not rows:
            await update.message.reply_text("No active trades.", parse_mode='HTML')
            return
        
        message = "<b>💼 Active Trades</b>\n\n"
        total_pnl = 0
        for row in rows:
            title, side, entry, size, pnl = row
            total_pnl += pnl if pnl else 0
            pnl_sign = "+" if pnl >= 0 else ""
            message += (
                f"<b>{title[:35]}</b>\n"
                f"{side} @ {entry:.2f}¢ | ${size:.0f}\n"
                f"P&amp;L: {pnl_sign}${pnl:.2f}\n\n"
            )
        
        pnl_sign = "+" if total_pnl >= 0 else ""
        message += f"<b>Total Unrealized:</b> {pnl_sign}${total_pnl:.2f}"
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_ipl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show today's IPL analysis."""
        # Get today's IPL match
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT event_name, start_time
                    FROM live_events
                    WHERE sport = 'IPL' 
                      AND start_time::date = CURRENT_DATE
                    ORDER BY start_time ASC
                    LIMIT 1
                """)
                match_row = await cur.fetchone()
                
                if not match_row:
                    await update.message.reply_text("No IPL match today.", parse_mode='HTML')
                    return
                
                event_name, start_time = match_row
                
                # Find related signal
                await cur.execute("""
                    SELECT market_title, polymarket_price, fair_value, edge_pct, signal, reasoning
                    FROM sports_signals
                    WHERE sport = 'IPL' 
                      AND market_title LIKE %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (f"%{event_name}%",))
                signal_row = await cur.fetchone()
        
        message = f"🏏 <b>IPL Today</b>\n\n<b>{event_name}</b>\n⏰ {start_time.strftime('%I:%M %p IST')}\n\n"
        
        if signal_row:
            title, pm_price, fair, edge, signal, reasoning = signal_row
            edge_pct = float(edge) if edge else 0
            message += (
                f"<b>Our Analysis:</b>\n"
                f"{signal} | Edge: {edge_pct:+.1f}%\n"
                f"PM: {pm_price:.2f} | Fair: {fair:.2f}\n\n"
                f"<b>Reasoning:</b>\n{reasoning[:200]}..."
            )
        else:
            message += "No signal yet. Scanning sportsbooks..."
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_arb(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current arbitrage opportunities."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT sport, market_title, edge_pct, signal, polymarket_price, fair_value
                    FROM sports_signals
                    WHERE edge_pct > 5 AND created_at >= NOW() - INTERVAL '1 hour'
                    ORDER BY edge_pct DESC
                    LIMIT 10
                """)
                rows = await cur.fetchall()
        
        if not rows:
            await update.message.reply_text("No arbitrage opportunities right now.", parse_mode='HTML')
            return
        
        message = "<b>💰 Arbitrage Opportunities</b>\n\n"
        for row in rows:
            sport, title, edge, signal, pm, fair = row
            edge_pct = float(edge) if edge else 0
            message += (
                f"<b>{sport}: {title[:30]}</b>\n"
                f"{signal} | Edge: {edge_pct:+.1f}%\n"
                f"PM: {pm:.2f} vs Fair: {fair:.2f}\n\n"
            )
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings menu with inline keyboard."""
        subscriber = await self.get_subscriber(update.effective_chat.id)
        
        if not subscriber:
            await update.message.reply_text("Not subscribed. Use /start first.")
            return
        
        sports_filter = subscriber.get('sports_filter') or ['ALL']
        min_edge = subscriber.get('min_edge', 5)
        alert_freq = subscriber.get('alert_frequency', 'instant')
        
        message = (
            f"⚙️ <b>Alert Settings</b>\n\n"
            f"<b>Sports Filter:</b> {', '.join(sports_filter)}\n"
            f"<b>Min Edge:</b> {min_edge}%\n"
            f"<b>Frequency:</b> {alert_freq}\n\n"
            f"Use buttons below to adjust:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🏏 IPL Only", callback_data="filter:IPL"),
                InlineKeyboardButton("🏀 NBA Only", callback_data="filter:NBA"),
            ],
            [
                InlineKeyboardButton("🏒 NHL Only", callback_data="filter:NHL"),
                InlineKeyboardButton("⚽ Soccer Only", callback_data="filter:Soccer"),
            ],
            [
                InlineKeyboardButton("🌍 All Sports", callback_data="filter:ALL"),
            ],
            [
                InlineKeyboardButton("Edge: 5%+", callback_data="edge:5"),
                InlineKeyboardButton("Edge: 10%+", callback_data="edge:10"),
                InlineKeyboardButton("Edge: 15%+", callback_data="edge:15"),
            ],
            [
                InlineKeyboardButton("⚡ Instant", callback_data="freq:instant"),
                InlineKeyboardButton("📅 Daily", callback_data="freq:daily"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot performance stats."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                # Overall performance
                await cur.execute("""
                    SELECT 
                        COUNT(*) as total_signals,
                        COUNT(DISTINCT sport) as sports_covered
                    FROM sports_signals
                """)
                signal_row = await cur.fetchone()
                total_signals = signal_row[0] if signal_row else 0
                sports_covered = signal_row[1] if signal_row else 0
                
                # Trade performance
                await cur.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                        COALESCE(SUM(pnl_usd), 0) as total_pnl
                    FROM paper_trades_live
                    WHERE closed_at IS NOT NULL
                """)
                trade_row = await cur.fetchone()
                total_trades = trade_row[0] if trade_row else 0
                wins = trade_row[1] if trade_row else 0
                total_pnl = float(trade_row[2]) if trade_row else 0
                win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
                
                # Backtest results
                await cur.execute("""
                    SELECT result_json->>'total_roi' as roi
                    FROM backtest_results
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                backtest_row = await cur.fetchone()
                roi = float(backtest_row[0]) if backtest_row and backtest_row[0] else 0
        
        pnl_sign = "+" if total_pnl >= 0 else ""
        message = (
            f"📈 <b>Bot Performance</b>\n\n"
            f"<b>Signals:</b>\n"
            f"Total: {total_signals:,}\n"
            f"Sports: {sports_covered}\n\n"
            f"<b>Trades:</b>\n"
            f"Total: {total_trades}\n"
            f"Win Rate: {win_rate:.1f}%\n"
            f"P&amp;L: {pnl_sign}${total_pnl:.2f}\n\n"
            f"<b>Backtest ROI:</b> {roi:+.1f}%"
        )
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all commands."""
        message = (
            "<b>🤖 Bot Commands</b>\n\n"
            "<b>Core:</b>\n"
            "/start — Subscribe to alerts\n"
            "/stop — Unsubscribe\n"
            "/status — Today's performance\n"
            "/help — This message\n\n"
            "<b>Signals:</b>\n"
            "/signals — Last 5 signals\n"
            "/trades — Active positions\n"
            "/arb — Current arbitrage opps\n\n"
            "<b>Sports-Specific:</b>\n"
            "/ipl — Today's IPL analysis\n\n"
            "<b>Settings & Stats:</b>\n"
            "/settings — Configure alerts\n"
            "/stats — Performance history"
        )
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    # ═════════════════════════════════════════════════════════════
    # CALLBACK HANDLERS (for inline buttons)
    # ═════════════════════════════════════════════════════════════
    
    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks."""
        query = update.callback_query
        await query.answer()
        
        chat_id = update.effective_chat.id
        data = query.data
        
        if data.startswith("filter:"):
            sport = data.split(":")[1]
            sports_filter = [sport] if sport != "ALL" else None
            await self.update_settings(chat_id, sports_filter=sports_filter)
            await query.edit_message_text(f"✅ Sports filter set to: {sport}")
        
        elif data.startswith("edge:"):
            min_edge = float(data.split(":")[1])
            await self.update_settings(chat_id, min_edge=min_edge)
            await query.edit_message_text(f"✅ Min edge set to: {min_edge}%")
        
        elif data.startswith("freq:"):
            frequency = data.split(":")[1]
            await self.update_settings(chat_id, alert_frequency=frequency)
            await query.edit_message_text(f"✅ Alert frequency set to: {frequency}")
    
    # ═════════════════════════════════════════════════════════════
    # BROADCAST FUNCTIONS
    # ═════════════════════════════════════════════════════════════
    
    async def broadcast_signal_alert(self, signal: Dict):
        """Broadcast a HIGH confidence signal to instant subscribers."""
        sport_emoji = {
            'IPL': '🏏',
            'NBA': '🏀',
            'NHL': '🏒',
            'Soccer': '⚽',
        }.get(signal.get('sport', ''), '🎯')
        
        message = (
            f"🚨 <b>ARBITRAGE ALERT</b>\n\n"
            f"{sport_emoji} <b>{signal.get('sport', '')}: {signal.get('market_title', '')[:50]}</b>\n"
            f"📊 {signal.get('signal', 'BUY')}\n\n"
            f"Entry: {signal.get('polymarket_price', 0):.2f}¢ (Polymarket)\n"
            f"Fair Value: {signal.get('fair_value', 0):.2f}¢ ({signal.get('source_count', 0)} sportsbooks)\n"
            f"Edge: {signal.get('edge_pct', 0):+.1f}%\n\n"
            f"📚 Books: {signal.get('sportsbooks', 'DraftKings, Pinnacle, Betfair')}\n"
            f"⏰ Match: {signal.get('start_time', 'TBD')}\n\n"
            f"#{signal.get('sport', 'Sports')} #Arbitrage"
        )
        
        subscribers = await self.get_all_subscribers(instant_only=True)
        
        # Filter by sports_filter and min_edge
        for sub in subscribers:
            sports_filter = sub.get('sports_filter')
            min_edge = sub.get('min_edge', 5)
            
            # Check sport filter
            if sports_filter and signal.get('sport') not in sports_filter:
                continue
            
            # Check edge threshold
            if signal.get('edge_pct', 0) < min_edge:
                continue
            
            # Rate limit: max 1 alert per 3 minutes
            last_alert = sub.get('last_alert_at')
            if last_alert and (datetime.utcnow() - last_alert).total_seconds() < 180:
                continue
            
            # Send alert
            try:
                await self.app.bot.send_message(
                    chat_id=sub['chat_id'],
                    text=message,
                    parse_mode='HTML'
                )
                await self.increment_alert_count(sub['chat_id'])
            except TelegramError as e:
                logger.error(f"Failed to send to {sub['chat_id']}: {e}")
    
    async def broadcast_daily_summary(self):
        """Send daily summary at 9 AM IST."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                # Today's stats
                await cur.execute("""
                    SELECT COUNT(*) as signals FROM sports_signals WHERE created_at >= CURRENT_DATE
                """)
                signals = (await cur.fetchone())[0]
                
                await cur.execute("""
                    SELECT COUNT(*), COALESCE(SUM(size_usd), 0) 
                    FROM paper_trades_live WHERE status = 'open'
                """)
                active_row = await cur.fetchone()
                active_trades = active_row[0]
                deployed = float(active_row[1])
                
                await cur.execute("""
                    SELECT COALESCE(SUM(pnl_usd), 0), COUNT(*), SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END)
                    FROM paper_trades_live 
                    WHERE closed_at >= CURRENT_DATE - INTERVAL '1 day' AND closed_at < CURRENT_DATE
                """)
                yesterday_row = await cur.fetchone()
                yesterday_pnl = float(yesterday_row[0])
                yesterday_trades = yesterday_row[1]
                yesterday_wins = yesterday_row[2]
                win_rate = (yesterday_wins / yesterday_trades * 100) if yesterday_trades > 0 else 0
                
                # Total ROI from backtest
                await cur.execute("""
                    SELECT result_json->>'total_roi' FROM backtest_results ORDER BY created_at DESC LIMIT 1
                """)
                roi_row = await cur.fetchone()
                total_roi = float(roi_row[0]) if roi_row and roi_row[0] else 0
                
                # Today's IPL match
                await cur.execute("""
                    SELECT event_name, start_time FROM live_events
                    WHERE sport = 'IPL' AND start_time::date = CURRENT_DATE
                    ORDER BY start_time ASC LIMIT 1
                """)
                match_row = await cur.fetchone()
                if match_row:
                    ipl_match = f"{match_row[0]} @ {match_row[1].strftime('%I:%M %p IST')}"
                    
                    # Get our pick
                    await cur.execute("""
                        SELECT signal, fair_value, polymarket_price
                        FROM sports_signals
                        WHERE sport = 'IPL' AND market_title LIKE %s
                        ORDER BY created_at DESC LIMIT 1
                    """, (f"%{match_row[0]}%",))
                    pick_row = await cur.fetchone()
                    if pick_row:
                        our_pick = f"{pick_row[0]} ({pick_row[1]:.1f}% fair, {pick_row[2]:.2f}¢ entry)"
                    else:
                        our_pick = "Scanning..."
                else:
                    ipl_match = "No match today"
                    our_pick = ""
        
        pnl_sign = "+" if yesterday_pnl >= 0 else ""
        message = (
            f"📊 <b>Daily Report — {datetime.now(IST).strftime('%b %d, %Y')}</b>\n\n"
            f"<b>Signals:</b> {signals:,} generated\n"
            f"<b>Active Trades:</b> {active_trades} (${deployed:.0f} deployed)\n"
            f"<b>Yesterday's P&amp;L:</b> {pnl_sign}${yesterday_pnl:.2f}\n"
            f"<b>Win Rate:</b> {win_rate:.0f}% ({yesterday_wins}/{yesterday_trades})\n\n"
            f"<b>🏏 IPL Today:</b>\n{ipl_match}\n"
            f"{f'Our pick: {our_pick}' if our_pick else ''}\n\n"
            f"<b>💰 Total ROI:</b> {total_roi:+.0f}%"
        )
        
        subscribers = await self.get_all_subscribers()
        for sub in subscribers:
            if sub.get('alert_frequency') not in ('daily', 'instant'):
                continue
            
            try:
                await self.app.bot.send_message(
                    chat_id=sub['chat_id'],
                    text=message,
                    parse_mode='HTML'
                )
            except TelegramError as e:
                logger.error(f"Failed to send daily summary to {sub['chat_id']}: {e}")
    
    async def broadcast_trade_result(self, trade: Dict):
        """Broadcast trade result after match ends."""
        won = trade.get('pnl_usd', 0) > 0
        emoji = "✅" if won else "❌"
        status_text = "TRADE WON" if won else "TRADE LOST"
        
        message = (
            f"{emoji} <b>{status_text}!</b>\n\n"
            f"🏏 {trade.get('market_title', '')}\n"
            f"Entry: {trade.get('entry_price', 0):.2f}¢ → Exit: {trade.get('exit_price', 0):.2f}¢\n"
            f"P&amp;L: {trade.get('pnl_usd', 0):+.2f} ({trade.get('pnl_pct', 0):+.1f}%)\n\n"
            f"Running Record: {trade.get('wins', 0)}W-{trade.get('losses', 0)}L ({trade.get('win_rate', 0):.0f}%)"
        )
        
        subscribers = await self.get_all_subscribers(instant_only=True)
        for sub in subscribers:
            try:
                await self.app.bot.send_message(
                    chat_id=sub['chat_id'],
                    text=message,
                    parse_mode='HTML'
                )
            except TelegramError as e:
                logger.error(f"Failed to send trade result to {sub['chat_id']}: {e}")
    
    async def broadcast_pre_match_alert(self, match: Dict):
        """Send 1-hour pre-match alert."""
        message = (
            f"⏰ <b>MATCH STARTING IN 1 HOUR</b>\n\n"
            f"🏏 {match.get('event_name', '')}\n\n"
            f"<b>Our Position:</b> ${match.get('size_usd', 0):.0f} on {match.get('pick', '')}\n"
            f"<b>Current Odds:</b> {match.get('odds_display', '')}\n"
            f"<b>Edge:</b> {match.get('edge_pct', 0):+.1f}%\n\n"
            f"{match.get('source_count', 0)} sportsbooks backing this call"
        )
        
        subscribers = await self.get_all_subscribers(instant_only=True)
        for sub in subscribers:
            # Filter by sport
            if sub.get('sports_filter') and match.get('sport') not in sub.get('sports_filter'):
                continue
            
            try:
                await self.app.bot.send_message(
                    chat_id=sub['chat_id'],
                    text=message,
                    parse_mode='HTML'
                )
            except TelegramError as e:
                logger.error(f"Failed to send pre-match alert to {sub['chat_id']}: {e}")
    
    # ═════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═════════════════════════════════════════════════════════════
    
    async def start(self):
        """Start the bot."""
        if not self.bot_token:
            logger.warning("Telegram bot disabled: no token")
            return
        
        self.app = Application.builder().token(self.bot_token).build()
        
        # Add command handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("signals", self.cmd_signals))
        self.app.add_handler(CommandHandler("trades", self.cmd_trades))
        self.app.add_handler(CommandHandler("ipl", self.cmd_ipl))
        self.app.add_handler(CommandHandler("arb", self.cmd_arb))
        self.app.add_handler(CommandHandler("settings", self.cmd_settings))
        self.app.add_handler(CommandHandler("stats", self.cmd_stats))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        
        # Admin commands (invite-only system)
        if self.invite_gate:
            self.app.add_handler(CommandHandler("invite", self.invite_gate.cmd_invite))
            self.app.add_handler(CommandHandler("approve", self.invite_gate.cmd_approve))
            self.app.add_handler(CommandHandler("revoke", self.invite_gate.cmd_revoke))
            self.app.add_handler(CommandHandler("subscribers", self.invite_gate.cmd_subscribers))
            self.app.add_handler(CommandHandler("broadcast", self.invite_gate.cmd_broadcast))
            # Catch text messages for invite code entry
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_code_entry))
        
        # Add callback handler for inline buttons
        self.app.add_handler(CallbackQueryHandler(self.callback_handler))
        
        # Initialize the bot
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        logger.info("✅ Telegram subscriber bot started")
    
    async def stop(self):
        """Stop the bot."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info("🛑 Telegram subscriber bot stopped")


# Global bot instance
_bot_instance: Optional[SubscriberBot] = None


def get_bot() -> Optional[SubscriberBot]:
    """Get global bot instance."""
    return _bot_instance


async def init_bot(bot_token: str, admin_chat_id: str):
    """Initialize and start the bot."""
    global _bot_instance
    
    if not bot_token:
        logger.warning("Telegram bot disabled: no token provided")
        return None
    
    _bot_instance = SubscriberBot(bot_token, admin_chat_id)
    await _bot_instance.start()
    return _bot_instance


async def shutdown_bot():
    """Shutdown the bot."""
    global _bot_instance
    if _bot_instance:
        await _bot_instance.stop()
        _bot_instance = None
