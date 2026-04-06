"""
The Odds API Integration
Fetches sportsbook odds from DraftKings, FanDuel, Pinnacle, etc.
Includes de-vig engine to convert American odds → implied probability → remove bookmaker margin.
"""
import httpx
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class OddsFetcher:
    """Fetch and store sportsbook odds from The Odds API."""
    
    BASE_URL = "https://api.the-odds-api.com/v4"
    
    SPORTS_MAP = {
        'NHL': 'icehockey_nhl',
        'NBA': 'basketball_nba',
        'MLB': 'baseball_mlb',
        'Soccer': 'soccer_epl',
        'UCL': 'soccer_uefa_champions',
    }
    
    # Top US bookmakers
    PREFERRED_BOOKMAKERS = [
        'fanduel',
        'draftkings',
        'pinnacle',
        'betmgm',
        'caesars',
    ]
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.api_key = os.environ.get('ODDS_API_KEY', '')
        
        if not self.api_key:
            logger.warning("⚠️ ODDS_API_KEY not set — sportsbook odds fetching is DISABLED")
            logger.warning("   Set ODDS_API_KEY in .env to enable cross-odds arbitrage")
    
    @staticmethod
    def american_to_decimal(american_odds: int) -> float:
        """Convert American odds to decimal odds."""
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1
    
    @staticmethod
    def decimal_to_probability(decimal_odds: float) -> float:
        """Convert decimal odds to implied probability."""
        if decimal_odds <= 0:
            return 0.0
        return 1 / decimal_odds
    
    @staticmethod
    def remove_vig(prob_a: float, prob_b: float) -> tuple[float, float]:
        """
        Remove bookmaker margin (vig) from two-sided market.
        prob_a + prob_b > 1.0 because of overround.
        Normalize so they sum to 1.0 to get true probabilities.
        """
        total = prob_a + prob_b
        if total <= 0:
            return (0.5, 0.5)
        
        # Normalize
        fair_prob_a = prob_a / total
        fair_prob_b = prob_b / total
        
        return (fair_prob_a, fair_prob_b)
    
    async def fetch_odds(self, sport_key: str) -> List[Dict]:
        """
        Fetch odds for a sport from The Odds API.
        Returns list of events with odds from multiple bookmakers.
        """
        if not self.api_key:
            return []
        
        try:
            url = f"{self.BASE_URL}/sports/{sport_key}/odds/"
            params = {
                'apiKey': self.api_key,
                'regions': 'us',  # US bookmakers only
                'markets': 'h2h',  # Head-to-head (moneyline)
                'oddsFormat': 'american',
            }
            
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                logger.info(f"✅ Fetched {len(data)} events from The Odds API ({sport_key})")
                return data
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("❌ The Odds API: Invalid API key")
            elif e.response.status_code == 429:
                logger.warning("⚠️ The Odds API: Rate limit exceeded")
            else:
                logger.error(f"❌ The Odds API error: {e}")
            return []
        
        except Exception as e:
            logger.error(f"❌ Failed to fetch odds for {sport_key}: {e}")
            return []
    
    async def parse_and_store_odds(self, events: List[Dict], sport: str) -> int:
        """
        Parse odds data and store in sportsbook_odds table.
        Apply de-vig to get fair probabilities.
        """
        if not events:
            return 0
        
        stored_count = 0
        
        async with self.db_pool.acquire() as conn:
            for event in events:
                def _ascii_safe(s): return s.encode('ascii', errors='replace').decode('ascii') if s else ''
                event_name = _ascii_safe(event.get('home_team', '')) + ' vs ' + _ascii_safe(event.get('away_team', ''))
                home_team = _ascii_safe(event.get('home_team', ''))
                away_team = _ascii_safe(event.get('away_team', ''))
                
                bookmakers = event.get('bookmakers', [])
                
                for bookmaker in bookmakers:
                    bookie_name = bookmaker.get('key', '')
                    
                    # Prefer top US bookmakers
                    if bookie_name not in self.PREFERRED_BOOKMAKERS:
                        continue
                    
                    markets = bookmaker.get('markets', [])
                    
                    for market in markets:
                        if market.get('key') != 'h2h':
                            continue  # Only head-to-head for now
                        
                        outcomes = market.get('outcomes', [])
                        
                        if len(outcomes) < 2:
                            continue
                        
                        # Parse odds for both teams
                        home_odds = None
                        away_odds = None
                        
                        for outcome in outcomes:
                            team = outcome.get('name', '')
                            american_odds = outcome.get('price', 0)
                            
                            if team == home_team:
                                home_odds = american_odds
                            elif team == away_team:
                                away_odds = american_odds
                        
                        if home_odds is None or away_odds is None:
                            continue
                        
                        # Convert to decimal
                        home_decimal = self.american_to_decimal(home_odds)
                        away_decimal = self.american_to_decimal(away_odds)
                        
                        # Calculate implied probabilities
                        home_prob = self.decimal_to_probability(home_decimal)
                        away_prob = self.decimal_to_probability(away_decimal)
                        
                        # Remove vig (normalize)
                        home_fair, away_fair = self.remove_vig(home_prob, away_prob)
                        
                        # Store both outcomes
                        try:
                            # Home team
                            await conn.execute("""
                                INSERT INTO sportsbook_odds (
                                    sport, event_name, bookmaker, market_type, outcome,
                                    odds_decimal, implied_probability, fetched_at
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                            """, sport, event_name, bookie_name, 'h2h', home_team,
                                home_decimal, home_fair)
                            
                            # Away team
                            await conn.execute("""
                                INSERT INTO sportsbook_odds (
                                    sport, event_name, bookmaker, market_type, outcome,
                                    odds_decimal, implied_probability, fetched_at
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                            """, sport, event_name, bookie_name, 'h2h', away_team,
                                away_decimal, away_fair)
                            
                            stored_count += 2
                        
                        except Exception as e:
                            logger.error(f"Failed to store odds: {e}")
        
        logger.info(f"✅ Stored {stored_count} sportsbook odds entries")
        return stored_count
    
    async def fetch_all_sports(self) -> int:
        """Fetch odds for all configured sports and store in DB."""
        if not self.api_key:
            logger.info("⚠️ Skipping sportsbook odds fetch (no API key)")
            return 0
        
        total_stored = 0
        
        for sport, sport_key in self.SPORTS_MAP.items():
            logger.info(f"📊 Fetching odds for {sport}...")
            events = await self.fetch_odds(sport_key)
            
            if events:
                stored = await self.parse_and_store_odds(events, sport)
                total_stored += stored
        
        return total_stored
    
    async def get_consensus_odds(self, sport: str, team: str) -> Optional[float]:
        """
        Get consensus de-vigged probability for a team from multiple bookmakers.
        Average across bookmakers for more accurate fair value.
        """
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT implied_probability
                    FROM sportsbook_odds
                    WHERE sport = $1
                    AND outcome ILIKE $2
                    AND fetched_at > NOW() - INTERVAL '1 hour'
                    ORDER BY fetched_at DESC
                    LIMIT 10
                """, sport, f'%{team}%')
                
                if not rows:
                    return None
                
                # Average probabilities
                probabilities = [float(row['implied_probability']) for row in rows]
                consensus = sum(probabilities) / len(probabilities)
                
                return consensus
        
        except Exception as e:
            logger.error(f"Failed to get consensus odds: {e}")
            return None
