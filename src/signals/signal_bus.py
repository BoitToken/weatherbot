"""
Signal Bus — Standardized signal format for all trading bots
"""
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradingSignal:
    """
    Standardized trading signal format for all bots (weather, sports, crypto)
    
    This is the universal signal format that the execution engine will consume
    """
    # Signal identification
    bot: str              # 'weather', 'sports', 'crypto'
    market_id: str        # Polymarket market ID
    market_title: str     # Human-readable market title
    
    # Trade recommendation
    side: str             # 'YES' or 'NO'
    our_probability: float  # Our calculated probability (0.0 to 1.0)
    market_price: float   # Current market price for recommended side
    edge: float           # our_probability - market_price
    
    # Confidence and risk
    confidence: str       # 'HIGH', 'MEDIUM', 'LOW'
    claude_reasoning: str # Claude's analysis (or empty if not analyzed)
    source: str           # 'gaussian_metar', 'poisson_sports', 'black_scholes', etc.
    
    # Position sizing
    recommended_size_usd: float  # Suggested position size in USD
    
    # Timing
    expires_at: datetime  # When signal expires (market close, kick-off, etc.)
    created_at: datetime  # When signal was generated
    
    # Additional context
    metadata: Dict[str, Any]  # Bot-specific data (city, team, strike, etc.)


class SignalBus:
    """
    Signal bus for storing and retrieving trading signals
    All bots emit signals to this bus
    Execution engine consumes signals from this bus
    """
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
    
    def calculate_position_size(
        self,
        edge: float,
        confidence: str,
        bankroll_usd: float,
        kelly_fraction: float = 0.25,
        max_position_pct: float = 0.05
    ) -> float:
        """
        Calculate recommended position size using fractional Kelly Criterion
        
        Args:
            edge: Our edge (our_prob - market_price)
            confidence: Signal confidence level
            bankroll_usd: Total bankroll in USD
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly, conservative)
            max_position_pct: Maximum position as % of bankroll (0.05 = 5%)
            
        Returns:
            Recommended position size in USD
        """
        # Confidence multiplier
        confidence_multiplier = {
            'HIGH': 1.0,
            'MEDIUM': 0.7,
            'LOW': 0.4
        }.get(confidence, 0.5)
        
        # Full Kelly: edge / decimal_odds
        # For simplicity, assume decimal odds ~2.0 (fair)
        # Kelly = edge (simplified for binary markets close to 50/50)
        
        # Fractional Kelly with confidence adjustment
        kelly_size = abs(edge) * kelly_fraction * confidence_multiplier
        
        # Apply max position limit
        kelly_size = min(kelly_size, max_position_pct)
        
        # Convert to USD
        position_usd = kelly_size * bankroll_usd
        
        # Minimum $10, maximum per limit
        position_usd = max(10.0, min(position_usd, bankroll_usd * max_position_pct))
        
        return round(position_usd, 2)
    
    async def emit_signal(self, signal: TradingSignal, bankroll_usd: float = 2000.0) -> int:
        """
        Emit a trading signal to the bus (store in database)
        
        Args:
            signal: TradingSignal to emit
            bankroll_usd: Current bankroll for position sizing
            
        Returns:
            Signal ID (database row ID)
        """
        if not self.db_pool:
            logger.warning("No database pool - signal not stored")
            return -1
        
        # Calculate position size if not set
        if signal.recommended_size_usd <= 0:
            signal.recommended_size_usd = self.calculate_position_size(
                signal.edge,
                signal.confidence,
                bankroll_usd
            )
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO signals (
                    bot, market_id, market_title, side,
                    our_probability, market_price, edge,
                    confidence, claude_reasoning, source,
                    recommended_size_usd, expires_at, created_at,
                    metadata, flagged
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id
            """,
                signal.bot, signal.market_id, signal.market_title, signal.side,
                signal.our_probability, signal.market_price, signal.edge,
                signal.confidence, signal.claude_reasoning, signal.source,
                signal.recommended_size_usd, signal.expires_at, signal.created_at,
                json.dumps(signal.metadata), True  # Always flagged (only emit actionable signals)
            )
            
            signal_id = row['id']
            
            logger.info(
                f"📡 Signal emitted #{signal_id}: {signal.bot} | "
                f"{signal.market_title[:50]}... | "
                f"Side: {signal.side} | Edge: {signal.edge:+.1%} | "
                f"Size: ${signal.recommended_size_usd:.0f}"
            )
            
            return signal_id
    
    async def get_pending_signals(
        self,
        bot: Optional[str] = None,
        min_confidence: Optional[str] = None,
        limit: int = 50
    ) -> List[TradingSignal]:
        """
        Get pending (untraded) signals from the bus
        
        Args:
            bot: Filter by bot type (optional)
            min_confidence: Minimum confidence level (optional)
            limit: Maximum number of signals to return
            
        Returns:
            List of TradingSignal objects
        """
        if not self.db_pool:
            return []
        
        # Build query
        conditions = ["flagged = true"]
        params = []
        param_idx = 1
        
        # Filter by bot
        if bot:
            conditions.append(f"bot = ${param_idx}")
            params.append(bot)
            param_idx += 1
        
        # Filter by confidence
        if min_confidence:
            confidence_order = ['LOW', 'MEDIUM', 'HIGH']
            min_idx = confidence_order.index(min_confidence)
            allowed = confidence_order[min_idx:]
            conditions.append(f"confidence = ANY(${param_idx})")
            params.append(allowed)
            param_idx += 1
        
        # Only pending signals (not yet traded)
        conditions.append("""
            NOT EXISTS (
                SELECT 1 FROM trades 
                WHERE trades.signal_id = signals.id
            )
        """)
        
        # Not expired
        conditions.append("expires_at > NOW()")
        
        query = f"""
            SELECT 
                id, bot, market_id, market_title, side,
                our_probability, market_price, edge,
                confidence, claude_reasoning, source,
                recommended_size_usd, expires_at, created_at,
                metadata
            FROM signals
            WHERE {' AND '.join(conditions)}
            ORDER BY edge DESC, created_at DESC
            LIMIT ${param_idx}
        """
        params.append(limit)
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        signals = []
        for row in rows:
            metadata = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
            
            signal = TradingSignal(
                bot=row['bot'],
                market_id=row['market_id'],
                market_title=row['market_title'],
                side=row['side'],
                our_probability=row['our_probability'],
                market_price=row['market_price'],
                edge=row['edge'],
                confidence=row['confidence'],
                claude_reasoning=row['claude_reasoning'],
                source=row['source'],
                recommended_size_usd=row['recommended_size_usd'],
                expires_at=row['expires_at'],
                created_at=row['created_at'],
                metadata=metadata
            )
            signals.append(signal)
        
        logger.info(f"Retrieved {len(signals)} pending signals")
        return signals
    
    async def mark_signal_traded(self, signal_id: int, trade_id: int):
        """Mark signal as traded (prevents duplicate trades)"""
        if not self.db_pool:
            return
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE signals 
                SET traded_at = NOW()
                WHERE id = $1
            """, signal_id)


async def test_signal_bus():
    """Test signal bus without real DB"""
    bus = SignalBus()
    
    print("\nSignal Bus Test\n")
    
    # Test position sizing
    print("Position Sizing Tests:")
    test_cases = [
        (0.80, 'HIGH', 2000),   # 80% edge, high confidence
        (0.25, 'MEDIUM', 2000), # 25% edge, medium confidence
        (0.15, 'LOW', 2000),    # 15% edge, low confidence
    ]
    
    for edge, confidence, bankroll in test_cases:
        size = bus.calculate_position_size(edge, confidence, bankroll)
        print(f"  Edge: {edge:+.0%}, Confidence: {confidence}, Bankroll: ${bankroll}")
        print(f"  → Position size: ${size:.2f} ({size/bankroll:.1%} of bankroll)\n")
    
    # Create sample signal
    signal = TradingSignal(
        bot='weather',
        market_id='tokyo_temp_123',
        market_title="Will Tokyo's high temperature exceed 16°C on April 6?",
        side='YES',
        our_probability=0.85,
        market_price=0.03,
        edge=0.82,
        confidence='HIGH',
        claude_reasoning="Strong aviation data support. No cold fronts expected.",
        source='gaussian_metar',
        recommended_size_usd=100.0,
        expires_at=datetime.utcnow() + timedelta(hours=6),
        created_at=datetime.utcnow(),
        metadata={
            'city': 'Tokyo',
            'icao': 'RJTT',
            'current_temp': 15.8,
            'threshold': 16.0
        }
    )
    
    print("Sample Signal:")
    for key, value in asdict(signal).items():
        if key == 'metadata':
            print(f"  {key}: {json.dumps(value, indent=4)}")
        else:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_signal_bus())
