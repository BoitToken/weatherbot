"""
Invite-only access gate for Telegram bot.
Adds /invite, /approve, /revoke, /subscribers commands and code verification.
"""
import logging
import secrets
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class InviteGate:
    """Manages invite-only access for the Telegram bot."""
    
    def __init__(self, pool, admin_chat_id: str):
        self.pool = pool
        self.admin_chat_id = str(admin_chat_id)
    
    def is_admin(self, chat_id) -> bool:
        return str(chat_id) == self.admin_chat_id
    
    async def is_approved(self, chat_id: int) -> bool:
        if self.is_admin(chat_id):
            return True
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT approved FROM telegram_subscribers WHERE chat_id = %s AND is_active = true",
                        (chat_id,)
                    )
                    row = await cur.fetchone()
                    return row is not None and row[0] is True
        except Exception as e:
            logger.error(f"is_approved error: {e}")
            return False
    
    async def try_invite_code(self, chat_id: int, code: str) -> bool:
        code = code.strip().upper()
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT id FROM invite_codes WHERE code = %s AND is_used = false",
                        (code,)
                    )
                    row = await cur.fetchone()
                    if row:
                        await cur.execute(
                            "UPDATE invite_codes SET is_used = true, used_by = %s, used_at = NOW() WHERE id = %s",
                            (chat_id, row[0])
                        )
                        await cur.execute(
                            "UPDATE telegram_subscribers SET approved = true WHERE chat_id = %s",
                            (chat_id,)
                        )
                        await conn.commit()
                        return True
                    return False
        except Exception as e:
            logger.error(f"try_invite_code error: {e}")
            return False

    async def approve_admin(self, chat_id: int):
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE telegram_subscribers SET approved = true WHERE chat_id = %s",
                        (chat_id,)
                    )
                    await conn.commit()
        except Exception as e:
            logger.error(f"approve_admin error: {e}")

    async def cmd_invite(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not self.is_admin(chat_id):
            await update.message.reply_text("\u26d4 Admin only.")
            return
        count = 1
        if context.args:
            try:
                count = min(int(context.args[0]), 20)
            except:
                pass
        codes = []
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    for _ in range(count):
                        code = f"ARB-{secrets.token_hex(3).upper()}"
                        await cur.execute(
                            "INSERT INTO invite_codes (code, created_by) VALUES (%s, %s)",
                            (code, chat_id)
                        )
                        codes.append(code)
                    await conn.commit()
        except Exception as e:
            logger.error(f"cmd_invite error: {e}")
            await update.message.reply_text(f"Error generating codes: {e}")
            return
        codes_text = "\n".join(f"<code>{c}</code>" for c in codes)
        await update.message.reply_text(
            f"\U0001f511 <b>{count} invite code(s):</b>\n\n{codes_text}\n\nSingle-use. Share privately.",
            parse_mode='HTML'
        )

    async def cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not self.is_admin(chat_id):
            await update.message.reply_text("\u26d4 Admin only.")
            return
        if not context.args:
            await update.message.reply_text("Usage: /approve &lt;chat_id&gt;")
            return
        target = int(context.args[0])
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("UPDATE telegram_subscribers SET approved = true WHERE chat_id = %s", (target,))
                    await conn.commit()
            await update.message.reply_text(f"\u2705 User {target} approved.")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def cmd_revoke(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not self.is_admin(chat_id):
            await update.message.reply_text("\u26d4 Admin only.")
            return
        if not context.args:
            await update.message.reply_text("Usage: /revoke &lt;chat_id&gt;")
            return
        target = int(context.args[0])
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("UPDATE telegram_subscribers SET approved = false, is_active = false WHERE chat_id = %s", (target,))
                    await conn.commit()
            await update.message.reply_text(f"\u274c User {target} revoked.")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def cmd_subscribers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not self.is_admin(chat_id):
            await update.message.reply_text("\u26d4 Admin only.")
            return
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT chat_id, username, first_name, approved, subscribed_at FROM telegram_subscribers WHERE is_active = true ORDER BY subscribed_at DESC LIMIT 25"
                    )
                    rows = await cur.fetchall()
            if not rows:
                await update.message.reply_text("No subscribers yet.")
                return
            lines = [f"\U0001f4cb <b>Subscribers ({len(rows)}):</b>\n"]
            for r in rows:
                status = "\u2705" if r[3] else "\u23f3"
                name = r[1] or r[2] or "unknown"
                lines.append(f"{status} @{name} \u2014 <code>{r[0]}</code>")
            await update.message.reply_text("\n".join(lines), parse_mode='HTML')
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def cmd_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not self.is_admin(chat_id):
            await update.message.reply_text("\u26d4 Admin only.")
            return
        if not context.args:
            await update.message.reply_text("Usage: /broadcast <message>")
            return
        msg = " ".join(context.args)
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT chat_id FROM telegram_subscribers WHERE is_active = true AND approved = true")
                    subs = await cur.fetchall()
            sent = 0
            from telegram import Bot
            bot = Bot(token=update.get_bot().token)
            for sub in subs:
                try:
                    await bot.send_message(chat_id=sub[0], text=msg, parse_mode='HTML')
                    sent += 1
                except:
                    pass
            await update.message.reply_text(f"\u2705 Broadcast sent to {sent}/{len(subs)} subscribers.")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
