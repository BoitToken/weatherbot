"""
Polymarket Sports Market Scanner
Fetches, categorizes, and groups sports markets from Polymarket.
"""
import httpx
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class PolymarketSportsScanner:
    """Scan and categorize Polymarket sports markets."""
    
    POLYMARKET_API = "https://gamma-api.polymarket.com/markets"
    
    # Sport category keywords
    SPORTS_KEYWORDS = {
        'NHL': ['nhl', 'stanley cup', 'hockey', 'avalanche', 'bruins', 'rangers', 'maple leafs', 'canadiens', 'oilers'],
        'NBA': ['nba', 'basketball', 'finals mvp', 'lakers', 'celtics', 'warriors', 'nets', 'heat', 'nuggets'],
        'MLB': ['mlb', 'baseball', 'world series', 'yankees', 'dodgers', 'red sox', 'astros', 'mets'],
        'Soccer': ['premier league', 'champions league', 'la liga', 'serie a', 'bundesliga', 'world cup', 'uefa', 'fifa', 'arsenal', 'manchester', 'liverpool', 'barcelona', 'real madrid'],
        'NFL': ['nfl', 'super bowl', 'football', 'quarterback', 'patriots', 'chiefs', 'cowboys', 'packers'],
        'Tennis': ['wimbledon', 'us open', 'french open', 'australian open', 'grand slam', 'djokovic', 'nadal', 'federer'],
        'Cricket': ['cricket', 'ipl', 'world cup cricket', 'test match', 'odi'],
        'F1': ['formula 1', 'f1', 'grand prix', 'verstappen', 'hamilton', 'ferrari', 'red bull racing'],
        'Combat': ['ufc', 'boxing', 'mma', 'fight', 'heavyweight', 'mcgregor', 'mayweather'],
    }
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
    
    def categorize_sport(self, question: str) -> str:
        """Detect sport category from question text."""
        q_lower = question.lower()
        
        for sport, keywords in self.SPORTS_KEYWORDS.items():
            if any(kw in q_lower for kw in keywords):
                return sport
        
        return 'Other'
    
    def detect_event_type(self, question: str) -> str:
        """Detect event type: championship, match, mvp, draft, etc."""
        q_lower = question.lower()
        
        if 'championship' in q_lower or 'cup' in q_lower or 'finals' in q_lower:
            return 'championship'
        elif 'mvp' in q_lower or 'most valuable' in q_lower:
            return 'mvp'
        elif 'draft' in q_lower or 'pick' in q_lower:
            return 'draft'
        elif ' vs ' in q_lower or ' vs. ' in q_lower or ' v ' in q_lower:
            return 'match'
        elif 'win' in q_lower and ('season' in q_lower or 'league' in q_lower):
            return 'season'
        else:
            return 'other'
    
    def extract_teams(self, question: str, sport: str) -> tuple[Optional[str], Optional[str]]:
        """Extract team names from question."""
        q_lower = question.lower()
        
        # For match questions (vs)
        if ' vs ' in q_lower or ' vs. ' in q_lower:
            parts = q_lower.replace(' vs. ', ' vs ').split(' vs ')
            if len(parts) == 2:
                team_a = parts[0].strip().split()[-1].title()  # Last word before "vs"
                team_b = parts[1].strip().split()[0].title()   # First word after "vs"
                return (team_a, team_b)
        
        # For championship questions, extract the team
        if sport in self.SPORTS_KEYWORDS:
            for keyword in self.SPORTS_KEYWORDS[sport]:
                if keyword in q_lower and keyword not in ['nba', 'nhl', 'mlb', 'nfl']:
                    # This is likely a team name
                    return (keyword.title(), None)
        
        return (None, None)
    
    def generate_group_id(self, question: str) -> str:
        """Generate group ID for related markets (e.g., all Stanley Cup teams)."""
        q_lower = question.lower()
        
        # Extract core event (e.g., "2026 nhl stanley cup")
        if 'stanley cup' in q_lower:
            # Extract year if present
            import re
            year_match = re.search(r'20\d{2}', question)
            year = year_match.group() if year_match else '2026'
            return f"nhl_stanley_cup_{year}"
        
        if 'nba finals' in q_lower or 'nba championship' in q_lower:
            import re
            year_match = re.search(r'20\d{2}', question)
            year = year_match.group() if year_match else '2026'
            return f"nba_finals_{year}"
        
        if 'world series' in q_lower:
            import re
            year_match = re.search(r'20\d{2}', question)
            year = year_match.group() if year_match else '2026'
            return f"mlb_world_series_{year}"
        
        if 'champions league' in q_lower:
            if 'winner' in q_lower or 'champion' in q_lower:
                import re
                year_match = re.search(r'20\d{2}', question)
                year = year_match.group() if year_match else '2026'
                return f"ucl_winner_{year}"
        
        if 'premier league' in q_lower:
            if 'winner' in q_lower or 'champion' in q_lower:
                import re
                year_match = re.search(r'20\d{2}', question)
                year = year_match.group() if year_match else '2026'
                return f"epl_winner_{year}"
        
        # Hash the question for unique grouping
        return hashlib.md5(q_lower.encode()).hexdigest()[:16]
    
    async def fetch_sports_markets(self) -> List[Dict]:
        """Fetch all active sports markets from Polymarket."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {
                    'limit': 500,
                    'active': 'true',
                    'closed': 'false'
                }
                resp = await client.get(self.POLYMARKET_API, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                markets = data if isinstance(data, list) else data.get('data', [])
                logger.info(f"✅ Fetched {len(markets)} markets from Polymarket")
                return markets
        except Exception as e:
            logger.error(f"❌ Failed to fetch Polymarket markets: {e}")
            return []
    
    async def scan_and_store(self) -> int:
        """Scan Polymarket, categorize sports markets, and store in DB."""
        markets = await self.fetch_sports_markets()
        if not markets:
            return 0
        
        sports_count = 0
        
        async with self.db_pool.acquire() as conn:
            for market in markets:
                question = market.get('question', '')
                if not question:
                    continue
                
                # Categorize
                sport = self.categorize_sport(question)
                if sport == 'Other':
                    continue  # Skip non-sports markets
                
                sports_count += 1
                
                # Parse market data
                market_id = market.get('condition_id') or market.get('id') or market.get('market_id')
                event_type = self.detect_event_type(question)
                team_a, team_b = self.extract_teams(question, sport)
                group_id = self.generate_group_id(question)
                
                # Extract prices
                tokens = market.get('tokens', [])
                yes_price = float(tokens[0].get('price', 0.5)) if tokens else 0.5
                no_price = float(tokens[1].get('price', 0.5)) if len(tokens) > 1 else 0.5
                
                # Extract volume & liquidity
                volume_usd = float(market.get('volume', 0) or 0)
                liquidity_usd = float(market.get('liquidity', 0) or 0)
                
                # Resolution date
                resolution_date = market.get('end_date_iso') or market.get('closed_time')
                
                # Detect league
                league = None
                if sport == 'NHL':
                    league = 'NHL'
                elif sport == 'NBA':
                    league = 'NBA'
                elif sport == 'MLB':
                    league = 'MLB'
                elif sport == 'Soccer':
                    if 'premier league' in question.lower():
                        league = 'Premier League'
                    elif 'champions league' in question.lower():
                        league = 'UEFA Champions League'
                    elif 'la liga' in question.lower():
                        league = 'La Liga'
                
                # Store in DB
                try:
                    await conn.execute("""
                        INSERT INTO sports_markets (
                            market_id, question, sport, league, event_type,
                            team_a, team_b, yes_price, no_price,
                            volume_usd, liquidity_usd, resolution_date,
                            group_id, metadata, last_updated, is_active
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, NOW(), true)
                        ON CONFLICT (market_id) DO UPDATE SET
                            yes_price = EXCLUDED.yes_price,
                            no_price = EXCLUDED.no_price,
                            volume_usd = EXCLUDED.volume_usd,
                            liquidity_usd = EXCLUDED.liquidity_usd,
                            last_updated = NOW(),
                            is_active = EXCLUDED.is_active
                    """, market_id, question, sport, league, event_type,
                        team_a, team_b, yes_price, no_price,
                        volume_usd, liquidity_usd, resolution_date,
                        group_id, None)
                except Exception as e:
                    logger.error(f"Failed to store market {market_id}: {e}")
        
        logger.info(f"✅ Stored {sports_count} sports markets")
        return sports_count
