"""
Paper Trader for WeatherBot.
Simulates trades without real money.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import uuid

from src import config
from src.db import execute, fetch_one
from src.execution.risk_manager import check_limits, get_position_size
from src.alerts.telegram_bot import send_trade_placed_alert, send_circuit_breaker_alert

logger = logging.getLogger(__name__)


async def paper_trade(signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Execute a paper trade based on signal.
    
    Args:
        signal: Signal dictionary with:
            - signal_id: int
            - city: str
            - side: str ('YES' or 'NO')
            - market_price: float (0-1)
            - edge_pct: float
            - confidence: str
            
    Returns:
        Trade record dict if successful, None if rejected
    """
    # 1. Check risk limits
    allowed, reason = await check_limits(signal)
    
    if not allowed:
        logger.warning(f"❌ Trade rejected: {reason}")
        
        # Send circuit breaker alert if daily limit hit
        if "Daily loss limit" in reason or "Circuit breaker" in reason:
            await send_circuit_breaker_alert()
        
        return None
    
    # 2. Calculate position size
    size_usd = await get_position_size(signal)
    
    if size_usd < 1.0:
        logger.warning(f"❌ Position size too small: ${size_usd:.2f}")
        return None
    
    # 3. Simulate fill at current market price
    entry_price = signal.get('market_price', 0.5) * 100  # Convert to cents
    
    # 4. Create trade record in database
    trade_id = str(uuid.uuid4())
    
    query = """
        INSERT INTO trades (
            id,
            signal_id,
            city,
            side,
            entry_price,
            size_usd,
            edge_pct,
            status,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    try:
        await execute(query, (
            trade_id,
            signal.get('signal_id'),
            signal.get('city'),
            signal.get('side'),
            entry_price,
            size_usd,
            signal.get('edge_pct'),
            'paper_open',
            datetime.utcnow()
        ))
        
        logger.info(f"✅ Paper trade placed: {signal['city']} {signal['side']} @ {entry_price:.1f}¢ (${size_usd:.2f})")
        
        # 5. Send Telegram alert
        await send_trade_placed_alert(
            city=signal['city'],
            side=signal['side'],
            price=entry_price,
            size=size_usd
        )
        
        # 6. Fetch and return the created trade
        fetch_query = """
            SELECT 
                id,
                signal_id,
                city,
                side,
                entry_price,
                size_usd,
                edge_pct,
                status,
                created_at
            FROM trades
            WHERE id = %s
        """
        trade = await fetch_one(fetch_query, (trade_id,))
        
        return trade
        
    except Exception as e:
        logger.error(f"❌ Failed to create paper trade: {e}")
        return None


async def close_trade(trade_id: str, outcome: str, final_price: float) -> bool:
    """
    Close a paper trade and calculate P&L.
    
    Args:
        trade_id: Trade ID
        outcome: 'win' or 'loss'
        final_price: Settlement price (0-100 cents)
        
    Returns:
        True if successful
    """
    # Fetch the trade
    query = """
        SELECT 
            id,
            city,
            side,
            entry_price,
            size_usd,
            status
        FROM trades
        WHERE id = %s
    """
    
    try:
        trade = await fetch_one(query, (trade_id,))
        
        if not trade:
            logger.error(f"Trade {trade_id} not found")
            return False
        
        if trade['status'] not in ('paper_open', 'live_open'):
            logger.warning(f"Trade {trade_id} already closed")
            return False
        
        # Calculate P&L
        # If we bought YES at 60¢ and it resolves YES (100¢), we make 40¢ per $1 bet
        # If we bought NO at 40¢ and it resolves NO (100¢), we make 60¢ per $1 bet
        
        if outcome == 'win':
            # We win: payout is (100 - entry_price) per dollar bet
            pnl = trade['size_usd'] * (100 - trade['entry_price']) / 100
        else:
            # We lose: we lose our entire bet
            pnl = -trade['size_usd']
        
        # Update trade record
        update_query = """
            UPDATE trades
            SET 
                status = %s,
                exit_price = %s,
                pnl = %s,
                closed_at = %s
            WHERE id = %s
        """
        
        new_status = 'paper_won' if outcome == 'win' else 'paper_lost'
        
        await execute(update_query, (
            new_status,
            final_price,
            pnl,
            datetime.utcnow(),
            trade_id
        ))
        
        logger.info(f"✅ Trade closed: {trade['city']} {trade['side']} → {outcome} (${pnl:+.2f})")
        
        # Send Telegram alert
        from src.alerts.telegram_bot import send_trade_won_alert, send_trade_lost_alert
        
        if outcome == 'win':
            await send_trade_won_alert(trade['city'], trade['side'], pnl)
        else:
            await send_trade_lost_alert(trade['city'], trade['side'], pnl)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to close trade: {e}")
        return False
