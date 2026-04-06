"""
Risk Manager for WeatherBot.
Checks position limits, daily exposure, and circuit breakers.
"""
import logging
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any

from src import config
from src.db import fetch_one, fetch_all

logger = logging.getLogger(__name__)

# Risk parameters
MAX_POSITION_USD = 50.0
MAX_POSITION_PCT = 0.05  # 5% of bankroll
DAILY_LOSS_LIMIT_PCT = 0.10  # 10% of bankroll
MAX_CONSECUTIVE_LOSSES = 5


async def get_bankroll() -> float:
    """
    Get current bankroll.
    TODO: Implement proper bankroll tracking table.
    For now, use fixed amount.
    """
    return 1000.0


async def get_daily_pnl() -> float:
    """Get today's P&L."""
    today = datetime.utcnow().date()
    tomorrow = today + timedelta(days=1)
    
    query = """
        SELECT COALESCE(SUM(pnl), 0.0) as daily_pnl
        FROM trades
        WHERE closed_at IS NOT NULL
        AND closed_at >= %s
        AND closed_at < %s
    """
    
    try:
        result = await fetch_one(query, (today, tomorrow))
        return result['daily_pnl'] if result else 0.0
    except Exception as e:
        logger.error(f"Failed to get daily P&L: {e}")
        return 0.0


async def get_active_positions_value() -> float:
    """Get total value in active positions."""
    query = """
        SELECT COALESCE(SUM(size_usd), 0.0) as total_exposure
        FROM trades
        WHERE status IN ('paper_open', 'live_open')
    """
    
    try:
        result = await fetch_one(query)
        return result['total_exposure'] if result else 0.0
    except Exception as e:
        logger.error(f"Failed to get active positions: {e}")
        return 0.0


async def get_consecutive_losses() -> int:
    """Count consecutive losses from most recent trades."""
    query = """
        SELECT pnl
        FROM trades
        WHERE closed_at IS NOT NULL
        ORDER BY closed_at DESC
        LIMIT 10
    """
    
    try:
        results = await fetch_all(query)
        
        consecutive = 0
        for trade in results:
            if trade['pnl'] <= 0:
                consecutive += 1
            else:
                break
        
        return consecutive
    except Exception as e:
        logger.error(f"Failed to get consecutive losses: {e}")
        return 0


async def check_limits(signal: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Check if trade is allowed based on risk limits.
    
    Args:
        signal: Signal dictionary with edge, size, etc.
        
    Returns:
        Tuple of (allowed: bool, reason: str)
    """
    # Get current risk metrics
    bankroll = await get_bankroll()
    daily_pnl = await get_daily_pnl()
    active_exposure = await get_active_positions_value()
    consecutive_losses = await get_consecutive_losses()
    
    # 1. Check daily loss limit
    daily_loss_limit = bankroll * DAILY_LOSS_LIMIT_PCT
    if daily_pnl < -daily_loss_limit:
        return (False, f"Daily loss limit hit: {daily_pnl:.2f} < -{daily_loss_limit:.2f}")
    
    # 2. Check consecutive losses circuit breaker
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        return (False, f"Circuit breaker: {consecutive_losses} consecutive losses")
    
    # 3. Check position size limits (will be calculated in paper_trade)
    # Just verify we have capacity
    max_allowed_exposure = bankroll * 0.50  # Max 50% in positions
    if active_exposure >= max_allowed_exposure:
        return (False, f"Max exposure reached: ${active_exposure:.2f} / ${max_allowed_exposure:.2f}")
    
    # 4. Check signal quality
    min_edge = 5.0  # Minimum 5% edge
    if signal.get('edge_pct', 0) < min_edge:
        return (False, f"Edge too low: {signal.get('edge_pct', 0):.1f}% < {min_edge}%")
    
    # All checks passed
    logger.info(f"✅ Risk checks passed. Bankroll: ${bankroll:.2f}, Daily P&L: ${daily_pnl:.2f}, Exposure: ${active_exposure:.2f}")
    return (True, "All risk checks passed")


async def get_position_size(signal: Dict[str, Any]) -> float:
    """
    Calculate position size using Kelly Criterion.
    
    Args:
        signal: Signal with edge_pct and market price
        
    Returns:
        Position size in USD
    """
    bankroll = await get_bankroll()
    edge = signal['edge_pct'] / 100.0  # Convert to decimal
    market_price = signal.get('market_price', 0.5)
    
    # Kelly formula: f = (edge * kelly_fraction) / (1 - market_price)
    # Simplified Kelly for binary outcome
    kelly_fraction = config.KELLY_FRACTION
    
    if market_price >= 0.99:
        # Market too certain, avoid division by near-zero
        raw_size = bankroll * 0.01
    else:
        raw_size = bankroll * (edge * kelly_fraction) / (1 - market_price)
    
    # Apply caps
    size = min(raw_size, MAX_POSITION_USD)
    size = min(size, bankroll * MAX_POSITION_PCT)
    
    # Reduce size if consecutive losses
    consecutive = await get_consecutive_losses()
    if consecutive >= 3:
        reduction = 0.5 ** (consecutive - 2)  # 50% reduction per loss after 3
        size *= reduction
        logger.info(f"Position size reduced by {(1-reduction)*100:.0f}% due to {consecutive} consecutive losses")
    
    return round(size, 2)
