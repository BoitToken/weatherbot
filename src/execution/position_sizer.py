"""
Kelly Criterion Position Sizer
Calculates optimal position sizes based on strategy track record.

Uses Half-Kelly for safety. Falls back to minimum sizing for unproven strategies.
"""
import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

# Position limits (paper mode)
MIN_POSITION = 10.0   # $10 minimum
MAX_POSITION = 50.0   # $50 maximum
MIN_TRADES_FOR_KELLY = 10  # Need at least 10 trades before Kelly kicks in
HALF_KELLY = 0.5  # Safety multiplier


def calculate_kelly(win_rate: float, avg_win: float, avg_loss: float, bankroll: float) -> float:
    """
    Calculate Kelly Criterion optimal fraction.
    
    Kelly % = (bp - q) / b
    Where:
      b = ratio of avg win / avg loss
      p = win probability
      q = loss probability (1 - p)
    
    Returns fraction of bankroll to bet (0.0 to 1.0).
    """
    if win_rate <= 0 or win_rate >= 1:
        return 0.0
    if avg_loss <= 0 or avg_win <= 0:
        return 0.0
    
    p = win_rate
    q = 1.0 - p
    b = avg_win / avg_loss  # Win/loss ratio
    
    kelly = (b * p - q) / b
    
    # Kelly can be negative (don't bet) or > 1 (impossible)
    kelly = max(0.0, min(kelly, 1.0))
    
    return kelly


def get_position_size(
    edge_pct: float,
    confidence: float,
    strategy_win_rate: Optional[float],
    bankroll: float,
    strategy_trades: int = 0,
    avg_win: float = 0.0,
    avg_loss: float = 0.0,
) -> float:
    """
    Calculate position size in USD.
    
    Args:
        edge_pct: Expected edge percentage (e.g., 12.5 for 12.5%)
        confidence: Confidence score 0-1 (from signal)
        strategy_win_rate: Historical win rate for this strategy (0-1), or None
        bankroll: Current bankroll in USD
        strategy_trades: Number of historical trades for this strategy
        avg_win: Average win amount in USD
        avg_loss: Average loss amount in USD
    
    Returns:
        Position size in USD, clamped to [MIN_POSITION, MAX_POSITION]
    """
    if bankroll <= 0:
        return MIN_POSITION
    
    # If strategy has insufficient track record, use minimum
    if strategy_trades < MIN_TRADES_FOR_KELLY or strategy_win_rate is None:
        logger.info(
            f"Strategy has {strategy_trades} trades (need {MIN_TRADES_FOR_KELLY}), "
            f"using minimum position ${MIN_POSITION}"
        )
        return MIN_POSITION
    
    # Calculate full Kelly fraction
    kelly_fraction = calculate_kelly(strategy_win_rate, avg_win, avg_loss, bankroll)
    
    if kelly_fraction <= 0:
        # Kelly says don't bet — but we still allow minimum if there's positive edge
        if edge_pct > 0:
            return MIN_POSITION
        return 0.0
    
    # Apply half-Kelly for safety
    safe_fraction = kelly_fraction * HALF_KELLY
    
    # Scale by confidence
    adjusted_fraction = safe_fraction * max(confidence, 0.5)
    
    # Calculate position size
    position = bankroll * adjusted_fraction
    
    # Clamp to limits
    position = max(MIN_POSITION, min(position, MAX_POSITION))
    
    logger.info(
        f"Kelly: {kelly_fraction:.4f}, Half-Kelly: {safe_fraction:.4f}, "
        f"Confidence-adj: {adjusted_fraction:.4f}, "
        f"Position: ${position:.2f} (bankroll: ${bankroll:.2f})"
    )
    
    return round(position, 2)


async def get_strategy_sizing_params(pool, strategy: str) -> dict:
    """
    Fetch strategy performance data needed for position sizing.
    Returns dict with win_rate, avg_win, avg_loss, total_trades.
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Get rolling stats from last 30 resolved trades for this strategy
            await cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                    AVG(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE NULL END) as avg_win,
                    AVG(CASE WHEN pnl_usd <= 0 THEN ABS(pnl_usd) ELSE NULL END) as avg_loss
                FROM (
                    SELECT pnl_usd FROM trades 
                    WHERE strategy = %s AND status IN ('won', 'lost')
                    ORDER BY resolved_at DESC 
                    LIMIT 30
                ) recent
            """, (strategy,))
            row = await cur.fetchone()
            
            if not row or not row[0]:
                return {
                    'total_trades': 0,
                    'win_rate': None,
                    'avg_win': 0.0,
                    'avg_loss': 0.0,
                }
            
            total = row[0]
            wins = row[1] or 0
            avg_win = float(row[2]) if row[2] else 0.0
            avg_loss = float(row[3]) if row[3] else 0.0
            win_rate = wins / total if total > 0 else 0.0
            
            return {
                'total_trades': total,
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
            }
