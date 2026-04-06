"""
ESPN Live Scores Integration
Fetches real-time scores from ESPN's free API for NHL, NBA, MLB, Soccer.
"""
import httpx
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ESPNLiveScores:
    """Fetch live scores from ESPN API."""
    
    ESPN_ENDPOINTS = {
        'NHL': 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard',
        'NBA': 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',
        'MLB': 'https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard',
        'Soccer_UCL': 'https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard',
        'Soccer_EPL': 'https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard',
    }
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
    
    async def fetch_scores(self, sport: str) -> List[Dict]:
        """Fetch live scores for a sport."""
        endpoint = self.ESPN_ENDPOINTS.get(sport)
        if not endpoint:
            logger.warning(f"No ESPN endpoint for sport: {sport}")
            return []
        
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(endpoint)
                resp.raise_for_status()
                data = resp.json()
                
                events = data.get('events', [])
                logger.info(f"✅ Fetched {len(events)} {sport} events from ESPN")
                return events
        except Exception as e:
            logger.error(f"❌ Failed to fetch {sport} scores: {e}")
            return []
    
    def parse_event(self, event: Dict, sport: str) -> Optional[Dict]:
        """Parse ESPN event into standardized format."""
        try:
            event_id = event.get('id')
            status = event.get('status', {}).get('type', {}).get('state', 'scheduled')
            
            # Get teams
            competitions = event.get('competitions', [])
            if not competitions:
                return None
            
            competition = competitions[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) < 2:
                return None
            
            # Determine home/away
            home_team = None
            away_team = None
            home_score = 0
            away_score = 0
            
            for comp in competitors:
                team_name = comp.get('team', {}).get('displayName', '')
                score = int(comp.get('score', 0) or 0)
                is_home = comp.get('homeAway') == 'home'
                
                if is_home:
                    home_team = team_name
                    home_score = score
                else:
                    away_team = team_name
                    away_score = score
            
            # Get period/minute info
            status_detail = event.get('status', {})
            period = status_detail.get('period', 0)
            minute = status_detail.get('displayClock', '')
            
            # Parse key events (goals, etc)
            key_events = []
            # ESPN doesn't always provide detailed play-by-play in scoreboard API
            # Store what we have
            
            return {
                'sport': sport.replace('Soccer_', ''),
                'event_id': event_id,
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'status': status,
                'minute': minute,
                'period': str(period) if period else None,
                'key_events': key_events,
            }
        except Exception as e:
            logger.error(f"Failed to parse event: {e}")
            return None
    
    async def match_to_polymarket(self, event_data: Dict) -> List[str]:
        """Find Polymarket markets linked to this live event."""
        home_team = event_data.get('home_team', '')
        away_team = event_data.get('away_team', '')
        sport = event_data.get('sport', '')
        
        if not home_team or not away_team:
            return []
        
        try:
            async with self.db_pool.acquire() as conn:
                # Search for markets mentioning these teams
                home_pattern = f'%{home_team}%'
                away_pattern = f'%{away_team}%'
                
                rows = await conn.fetch("""
                    SELECT market_id FROM sports_markets
                    WHERE sport = $1
                    AND (
                        question ILIKE $2
                        OR question ILIKE $3
                        OR (team_a IS NOT NULL AND (team_a ILIKE $2 OR team_a ILIKE $3))
                        OR (team_b IS NOT NULL AND (team_b ILIKE $2 OR team_b ILIKE $3))
                    )
                    AND is_active = true
                """, sport, home_pattern, away_pattern)
                
                return [row['market_id'] for row in rows]
        except Exception as e:
            logger.error(f"Failed to match event to Polymarket: {e}")
            return []
    
    async def update_live_events(self) -> int:
        """Fetch live scores for all sports and update DB."""
        total_updated = 0
        
        for sport_key in self.ESPN_ENDPOINTS.keys():
            events = await self.fetch_scores(sport_key)
            
            for event in events:
                parsed = self.parse_event(event, sport_key)
                if not parsed:
                    continue
                
                # Find linked Polymarket markets
                linked_markets = await self.match_to_polymarket(parsed)
                
                # Store in DB
                try:
                    async with self.db_pool.acquire() as conn:
                        await conn.execute("""
                            INSERT INTO live_events (
                                sport, event_id, home_team, away_team,
                                home_score, away_score, status, minute, period,
                                key_events, linked_market_ids, last_updated
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
                            ON CONFLICT (event_id) DO UPDATE SET
                                home_score = EXCLUDED.home_score,
                                away_score = EXCLUDED.away_score,
                                status = EXCLUDED.status,
                                minute = EXCLUDED.minute,
                                period = EXCLUDED.period,
                                linked_market_ids = EXCLUDED.linked_market_ids,
                                last_updated = NOW()
                        """, parsed['sport'], parsed['event_id'],
                            parsed['home_team'], parsed['away_team'],
                            parsed['home_score'], parsed['away_score'],
                            parsed['status'], parsed['minute'], parsed['period'],
                            None, linked_markets)
                        
                        total_updated += 1
                except Exception as e:
                    logger.error(f"Failed to store live event: {e}")
        
        logger.info(f"✅ Updated {total_updated} live events")
        return total_updated
    
    async def detect_momentum_signals(self) -> List[Dict]:
        """
        Detect score changes in live games and check if Polymarket markets adjusted.
        If score changes significantly but price hasn't moved, emit signal.
        """
        signals = []
        
        try:
            async with self.db_pool.acquire() as conn:
                # Get live events with recent score changes
                rows = await conn.fetch("""
                    WITH recent_scores AS (
                        SELECT DISTINCT ON (event_id)
                            event_id, home_score, away_score, last_updated,
                            LAG(home_score) OVER (PARTITION BY event_id ORDER BY last_updated) as prev_home,
                            LAG(away_score) OVER (PARTITION BY event_id ORDER BY last_updated) as prev_away
                        FROM live_events
                        WHERE status = 'in'
                        AND last_updated > NOW() - INTERVAL '15 minutes'
                        ORDER BY event_id, last_updated DESC
                    )
                    SELECT 
                        e.sport, e.event_id, e.home_team, e.away_team,
                        e.home_score, e.away_score, e.linked_market_ids,
                        s.prev_home, s.prev_away
                    FROM live_events e
                    JOIN recent_scores s ON e.event_id = s.event_id
                    WHERE e.status = 'in'
                    AND (e.home_score != s.prev_home OR e.away_score != s.prev_away)
                    AND e.linked_market_ids IS NOT NULL
                    AND array_length(e.linked_market_ids, 1) > 0
                """)
                
                for row in rows:
                    home_score = row['home_score']
                    away_score = row['away_score']
                    prev_home = row['prev_home'] or 0
                    prev_away = row['prev_away'] or 0
                    
                    # Calculate momentum shift
                    home_momentum = home_score - prev_home
                    away_momentum = away_score - prev_away
                    
                    # Determine which team has momentum
                    if home_momentum > away_momentum:
                        momentum_team = row['home_team']
                        momentum_shift = home_momentum
                    else:
                        momentum_team = row['away_team']
                        momentum_shift = away_momentum
                    
                    # Check linked Polymarket markets
                    market_ids = row['linked_market_ids']
                    
                    for market_id in market_ids:
                        # Get current and previous Polymarket price
                        market_data = await conn.fetchrow("""
                            SELECT question, yes_price, last_updated
                            FROM sports_markets
                            WHERE market_id = $1
                        """, market_id)
                        
                        if not market_data:
                            continue
                        
                        # If market is about the momentum team winning
                        if momentum_team.lower() in market_data['question'].lower():
                            # Check if price has moved in last 5 minutes
                            # (We'd need historical price tracking for this)
                            # For now, we'll signal if momentum is strong
                            
                            if momentum_shift >= 2:  # At least 2 points scored
                                signals.append({
                                    'edge_type': 'momentum',
                                    'sport': row['sport'],
                                    'market_id': market_id,
                                    'market_title': market_data['question'],
                                    'group_id': None,
                                    'polymarket_price': float(market_data['yes_price'] or 0.5),
                                    'fair_value': None,  # Unknown fair value
                                    'edge_pct': None,
                                    'signal': 'BUY',  # Buy the team with momentum
                                    'confidence': 'LOW',  # Momentum can reverse
                                    'reasoning': f"{momentum_team} scored {momentum_shift} point(s) recently in live game. Score now {home_score}-{away_score}. Market may not have adjusted yet.",
                                    'data_sources': {'espn_live_scores': True},
                                })
            
            logger.info(f"  ✅ Found {len(signals)} momentum signals")
        
        except Exception as e:
            logger.error(f"Failed to detect momentum signals: {e}")
        
        return signals
