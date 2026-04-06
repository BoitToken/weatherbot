"""
Market Matcher — Fuzzy Matching Between Polymarket & Sportsbook Events
Handles: 'LA Lakers' vs 'Los Angeles Lakers', 'Man City' vs 'Manchester City'
Links via polymarket_id in sportsbook_odds table.
"""
import logging
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
import re

logger = logging.getLogger(__name__)


class MarketMatcher:
    """Fuzzy match Polymarket markets to sportsbook events."""
    
    # Common team name aliases
    TEAM_ALIASES = {
        # NHL
        'avalanche': ['colorado avalanche', 'avs'],
        'bruins': ['boston bruins'],
        'rangers': ['new york rangers', 'ny rangers'],
        'maple leafs': ['toronto maple leafs', 'leafs'],
        'canadiens': ['montreal canadiens', 'habs'],
        'oilers': ['edmonton oilers'],
        'golden knights': ['vegas golden knights', 'vegas', 'vgk'],
        'lightning': ['tampa bay lightning', 'tb lightning'],
        'panthers': ['florida panthers'],
        
        # NBA
        'lakers': ['los angeles lakers', 'la lakers', 'l.a. lakers'],
        'celtics': ['boston celtics'],
        'warriors': ['golden state warriors', 'gs warriors'],
        'nets': ['brooklyn nets'],
        'heat': ['miami heat'],
        'nuggets': ['denver nuggets'],
        'bucks': ['milwaukee bucks'],
        '76ers': ['philadelphia 76ers', 'sixers'],
        'suns': ['phoenix suns'],
        'knicks': ['new york knicks', 'ny knicks'],
        
        # MLB
        'yankees': ['new york yankees', 'ny yankees'],
        'dodgers': ['los angeles dodgers', 'la dodgers'],
        'red sox': ['boston red sox'],
        'astros': ['houston astros'],
        'mets': ['new york mets', 'ny mets'],
        'braves': ['atlanta braves'],
        'padres': ['san diego padres'],
        
        # Soccer
        'man city': ['manchester city', 'city'],
        'man utd': ['manchester united', 'united'],
        'arsenal': ['arsenal fc'],
        'liverpool': ['liverpool fc'],
        'chelsea': ['chelsea fc'],
        'barcelona': ['fc barcelona', 'barça', 'barca'],
        'real madrid': ['real madrid cf'],
        'bayern': ['bayern munich', 'fc bayern'],
        'psg': ['paris saint-germain', 'paris sg'],
    }
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
    
    @staticmethod
    def normalize_team_name(team: str) -> str:
        """Normalize team name for comparison."""
        if not team:
            return ''
        
        # Convert to lowercase
        normalized = team.lower().strip()
        
        # Remove common suffixes
        for suffix in [' fc', ' cf', ' sc', ' united', ' city']:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        
        # Remove punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        return normalized
    
    @staticmethod
    def similarity_score(a: str, b: str) -> float:
        """Calculate similarity between two strings (0.0 to 1.0)."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def match_team(self, polymarket_team: str, sportsbook_team: str) -> float:
        """
        Match a Polymarket team name to a sportsbook team name.
        Returns similarity score (0.0 to 1.0).
        """
        if not polymarket_team or not sportsbook_team:
            return 0.0
        
        poly_normalized = self.normalize_team_name(polymarket_team)
        sports_normalized = self.normalize_team_name(sportsbook_team)
        
        # Direct match
        if poly_normalized == sports_normalized:
            return 1.0
        
        # Check aliases
        for base_name, aliases in self.TEAM_ALIASES.items():
            base_normalized = self.normalize_team_name(base_name)
            
            if poly_normalized == base_normalized or poly_normalized in [self.normalize_team_name(a) for a in aliases]:
                if sports_normalized == base_normalized or sports_normalized in [self.normalize_team_name(a) for a in aliases]:
                    return 1.0
        
        # Fuzzy match
        similarity = self.similarity_score(poly_normalized, sports_normalized)
        
        # Boost if one contains the other
        if poly_normalized in sports_normalized or sports_normalized in poly_normalized:
            similarity = max(similarity, 0.85)
        
        return similarity
    
    async def find_match(self, market_id: str, market_question: str, sport: str) -> Optional[str]:
        """
        Find best matching sportsbook event for a Polymarket market.
        Returns sportsbook event_name if match found, else None.
        """
        # Extract team(s) from Polymarket question
        from src.sports.polymarket_sports_scanner import PolymarketSportsScanner
        scanner = PolymarketSportsScanner(None)
        team_a, team_b = scanner.extract_teams(market_question, sport)
        
        if not team_a:
            return None
        
        try:
            async with self.db_pool.acquire() as conn:
                # Get recent sportsbook events for this sport
                rows = await conn.fetch("""
                    SELECT DISTINCT event_name, outcome
                    FROM sportsbook_odds
                    WHERE sport = $1
                    AND fetched_at > NOW() - INTERVAL '2 hours'
                """, sport)
                
                if not rows:
                    return None
                
                # Score each event
                best_match = None
                best_score = 0.0
                
                for row in rows:
                    event_name = row['event_name']
                    outcome = row['outcome']
                    
                    # Match team_a
                    score_a = self.match_team(team_a, outcome)
                    
                    # If there's a team_b, require both to match
                    if team_b:
                        score_b = self.match_team(team_b, event_name.replace(outcome, ''))
                        combined_score = (score_a + score_b) / 2
                    else:
                        combined_score = score_a
                    
                    if combined_score > best_score:
                        best_score = combined_score
                        best_match = event_name
                
                # Require at least 0.7 similarity to confirm match
                if best_score >= 0.7:
                    logger.info(f"✅ Matched '{market_question}' → '{best_match}' (score: {best_score:.2f})")
                    return best_match
                else:
                    logger.debug(f"⚠️ No good match for '{market_question}' (best: {best_score:.2f})")
                    return None
        
        except Exception as e:
            logger.error(f"Failed to find match for market {market_id}: {e}")
            return None
    
    async def link_markets_to_sportsbooks(self) -> int:
        """
        Link Polymarket sports markets to sportsbook events.
        Updates polymarket_id in sportsbook_odds table.
        """
        linked_count = 0
        
        try:
            async with self.db_pool.acquire() as conn:
                # Get all active sports markets
                markets = await conn.fetch("""
                    SELECT market_id, question, sport
                    FROM sports_markets
                    WHERE is_active = true
                """)
                
                for market in markets:
                    market_id = market['market_id']
                    question = market['question']
                    sport = market['sport']
                    
                    # Find matching sportsbook event
                    event_name = await self.find_match(market_id, question, sport)
                    
                    if event_name:
                        # Update sportsbook_odds with polymarket_id
                        await conn.execute("""
                            UPDATE sportsbook_odds
                            SET polymarket_id = $1
                            WHERE event_name = $2
                            AND sport = $3
                            AND polymarket_id IS NULL
                        """, market_id, event_name, sport)
                        
                        linked_count += 1
        
        except Exception as e:
            logger.error(f"Failed to link markets: {e}")
        
        logger.info(f"✅ Linked {linked_count} Polymarket markets to sportsbook events")
        return linked_count
    
    async def get_sportsbook_price_for_market(self, market_id: str) -> Optional[float]:
        """
        Get consensus de-vigged probability from sportsbooks for a Polymarket market.
        Uses the polymarket_id link created by link_markets_to_sportsbooks().
        """
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT implied_probability
                    FROM sportsbook_odds
                    WHERE polymarket_id = $1
                    AND fetched_at > NOW() - INTERVAL '1 hour'
                """, market_id)
                
                if not rows:
                    return None
                
                # Average probabilities across bookmakers
                probabilities = [float(row['implied_probability']) for row in rows]
                consensus = sum(probabilities) / len(probabilities)
                
                return consensus
        
        except Exception as e:
            logger.error(f"Failed to get sportsbook price: {e}")
            return None
