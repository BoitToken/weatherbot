"""
Mismatch Detector — Compare model probability vs market price
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import logging

from .gaussian_model import calculate_probability, calculate_range_probability

logger = logging.getLogger(__name__)


MIN_EDGE_ALERT = 0.15  # Flag signals with >15% edge


@dataclass
class Signal:
    """Trading signal from mismatch detection"""
    market_id: str
    market_title: str
    icao: str
    city: str
    
    # Market data
    yes_price: float
    no_price: float
    
    # Our model
    our_probability: float
    edge: float
    recommended_side: str  # 'YES' or 'NO'
    
    # Weather data
    current_temp_c: float
    trend_per_hour: float
    hours_to_resolution: float
    threshold_c: float
    threshold_type: str
    
    # Signal metadata
    flagged: bool  # True if edge > MIN_EDGE_ALERT
    created_at: datetime
    metadata: dict


class MismatchDetector:
    """Detect market mispricings by comparing model probability to market price"""
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
    
    async def get_latest_metar_data(self, icao: str) -> Optional[dict]:
        """
        Get latest METAR reading and trend for a station
        Returns dict with: temp_c, trend_per_hour, hours_since_reading
        """
        if not self.db_pool:
            return None
        
        async with self.db_pool.acquire() as conn:
            # Get latest METAR reading
            row = await conn.fetchrow("""
                SELECT temp_c, timestamp
                FROM metar_readings
                WHERE icao = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """, icao)
            
            if not row:
                return None
            
            # Get temperature trend
            trend_row = await conn.fetchrow("""
                SELECT trend_1h, trend_3h, trend_6h
                FROM temperature_trends
                WHERE icao = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """, icao)
            
            # Calculate hours since reading
            hours_since = (datetime.utcnow() - row['timestamp']).total_seconds() / 3600
            
            # Use most recent available trend (prefer shorter window)
            trend = 0.0
            if trend_row:
                trend = trend_row['trend_1h'] or trend_row['trend_3h'] or trend_row['trend_6h'] or 0.0
            
            return {
                'temp_c': row['temp_c'],
                'trend_per_hour': trend,
                'hours_since_reading': hours_since,
                'timestamp': row['timestamp']
            }
    
    async def get_active_markets(self) -> List[dict]:
        """Get all active weather markets from database"""
        if not self.db_pool:
            return []
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    market_id, title, yes_price, no_price,
                    resolution_date, metadata
                FROM weather_markets
                WHERE active = true
                ORDER BY volume DESC
            """)
            
            return [dict(row) for row in rows]
    
    def calculate_edge(
        self, 
        our_probability: float,
        yes_price: float,
        no_price: float
    ) -> tuple[float, str]:
        """
        Calculate edge for both YES and NO sides
        Returns (best_edge, recommended_side)
        
        Edge = our_probability - market_probability
        Positive edge means market underprices our estimate
        """
        # YES side edge
        yes_edge = our_probability - yes_price
        
        # NO side edge (bet against)
        no_edge = (1.0 - our_probability) - no_price
        
        # Pick side with higher edge
        if yes_edge > no_edge:
            return (yes_edge, 'YES')
        else:
            return (no_edge, 'NO')
    
    async def detect_mismatches(self) -> List[Signal]:
        """
        Main detection logic:
        1. Get latest METAR + trend for each station
        2. Get all active weather markets
        3. For each matched market: calculate our probability
        4. Calculate edge = our_probability - market_price
        5. Flag if |edge| > MIN_EDGE_ALERT
        
        Returns list of flagged signals
        """
        signals = []
        flagged_signals = []
        
        # Get all active markets
        markets = await self.get_active_markets()
        logger.info(f"Analyzing {len(markets)} active markets")
        
        for market in markets:
            try:
                # Parse market (we'll need the matcher and match result here)
                # For now, assume metadata contains parsed match result
                match_data = market.get('metadata', {}).get('match')
                if not match_data:
                    continue
                
                icao = match_data.get('icao')
                city = match_data.get('city')
                threshold_type = match_data.get('threshold_type')
                threshold_c = match_data.get('threshold_value')
                threshold_max = match_data.get('threshold_max')
                
                if not icao or not threshold_c:
                    continue
                
                # Get latest METAR data
                metar_data = await self.get_latest_metar_data(icao)
                if not metar_data:
                    logger.debug(f"No METAR data for {icao}")
                    continue
                
                # Calculate hours to resolution
                resolution_date = market.get('resolution_date')
                if not resolution_date:
                    continue
                
                hours_to_resolution = (resolution_date - datetime.utcnow()).total_seconds() / 3600
                if hours_to_resolution < 0:
                    continue  # Market already resolved
                
                # Calculate our probability using Gaussian model
                if threshold_type == 'range' and threshold_max:
                    our_probability = calculate_range_probability(
                        metar_data['temp_c'],
                        metar_data['trend_per_hour'],
                        hours_to_resolution,
                        threshold_c,
                        threshold_max
                    )
                elif 'above' in threshold_type:
                    our_probability = calculate_probability(
                        metar_data['temp_c'],
                        metar_data['trend_per_hour'],
                        hours_to_resolution,
                        threshold_c,
                        'above'
                    )
                elif 'below' in threshold_type:
                    our_probability = calculate_probability(
                        metar_data['temp_c'],
                        metar_data['trend_per_hour'],
                        hours_to_resolution,
                        threshold_c,
                        'below'
                    )
                else:
                    continue
                
                # Calculate edge
                edge, recommended_side = self.calculate_edge(
                    our_probability,
                    market['yes_price'],
                    market['no_price']
                )
                
                # Create signal
                signal = Signal(
                    market_id=market['market_id'],
                    market_title=market['title'],
                    icao=icao,
                    city=city,
                    yes_price=market['yes_price'],
                    no_price=market['no_price'],
                    our_probability=our_probability,
                    edge=edge,
                    recommended_side=recommended_side,
                    current_temp_c=metar_data['temp_c'],
                    trend_per_hour=metar_data['trend_per_hour'],
                    hours_to_resolution=hours_to_resolution,
                    threshold_c=threshold_c,
                    threshold_type=threshold_type,
                    flagged=abs(edge) > MIN_EDGE_ALERT,
                    created_at=datetime.utcnow(),
                    metadata={
                        'metar_timestamp': metar_data['timestamp'].isoformat(),
                        'hours_since_reading': metar_data['hours_since_reading'],
                        'resolution_date': resolution_date.isoformat()
                    }
                )
                
                signals.append(signal)
                
                if signal.flagged:
                    flagged_signals.append(signal)
                    logger.info(
                        f"🚨 Flagged: {city} ({icao}) | "
                        f"Market: {market['yes_price']:.3f} | "
                        f"Our prob: {our_probability:.3f} | "
                        f"Edge: {edge:+.1%} | "
                        f"Side: {recommended_side}"
                    )
                
            except Exception as e:
                logger.error(f"Error analyzing market {market.get('market_id')}: {e}")
                continue
        
        # Store all signals in database
        if self.db_pool and signals:
            await self.store_signals(signals)
        
        logger.info(
            f"Scan complete: {len(markets)} markets analyzed, "
            f"{len(signals)} signals generated, {len(flagged_signals)} flagged"
        )
        
        return flagged_signals
    
    async def store_signals(self, signals: List[Signal]) -> int:
        """Store signals in database"""
        if not self.db_pool:
            return 0
        
        stored = 0
        async with self.db_pool.acquire() as conn:
            for signal in signals:
                try:
                    await conn.execute("""
                        INSERT INTO signals (
                            market_id, icao, city, our_probability, market_price,
                            edge, recommended_side, threshold_c, threshold_type,
                            current_temp_c, trend_per_hour, hours_to_resolution,
                            flagged, created_at, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    """,
                        signal.market_id, signal.icao, signal.city,
                        signal.our_probability,
                        signal.yes_price if signal.recommended_side == 'YES' else signal.no_price,
                        signal.edge, signal.recommended_side,
                        signal.threshold_c, signal.threshold_type,
                        signal.current_temp_c, signal.trend_per_hour,
                        signal.hours_to_resolution, signal.flagged,
                        signal.created_at, signal.metadata
                    )
                    stored += 1
                except Exception as e:
                    logger.error(f"Error storing signal: {e}")
        
        return stored


async def test_detector():
    """Test detector without real DB"""
    detector = MismatchDetector()
    
    # Mock scenario: Tokyo market
    print("\nMismatch Detector Test\n")
    
    # Scenario 1: Strong YES signal
    print("Scenario 1: Tokyo high > 16°C")
    print("Current: 15.8°C, Trend: +0.3°C/hr, Hours: 6")
    print("Market YES price: $0.03 (3%)")
    
    our_prob = calculate_probability(15.8, 0.3, 6, 16.0, 'above')
    edge_yes = our_prob - 0.03
    edge_no = (1.0 - our_prob) - 0.97
    
    print(f"Our probability: {our_prob:.1%}")
    print(f"YES edge: {edge_yes:+.1%}")
    print(f"NO edge: {edge_no:+.1%}")
    print(f"Recommended: {'YES' if edge_yes > edge_no else 'NO'}")
    print(f"Flagged: {abs(max(edge_yes, edge_no)) > MIN_EDGE_ALERT}\n")
    
    # Scenario 2: Strong NO signal
    print("Scenario 2: New York high > 30°C")
    print("Current: 18°C, Trend: +0.2°C/hr, Hours: 8")
    print("Market YES price: $0.85 (85%)")
    
    our_prob = calculate_probability(18.0, 0.2, 8, 30.0, 'above')
    edge_yes = our_prob - 0.85
    edge_no = (1.0 - our_prob) - 0.15
    
    print(f"Our probability: {our_prob:.1%}")
    print(f"YES edge: {edge_yes:+.1%}")
    print(f"NO edge: {edge_no:+.1%}")
    print(f"Recommended: {'YES' if edge_yes > edge_no else 'NO'}")
    print(f"Flagged: {abs(max(edge_yes, edge_no)) > MIN_EDGE_ALERT}\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_detector())
