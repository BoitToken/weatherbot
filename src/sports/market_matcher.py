"""
Market Matcher — Links Polymarket sports markets to sportsbook odds.

For daily match markets (e.g., "Will Delhi Capitals win? (DC vs GT)"):
  → Match team name against sportsbook outcome column
  → Link polymarket_id so cross-odds engine can compare prices

For championship futures (e.g., "Will Lakers win 2026 NBA Finals?"):
  → We only have H2H daily odds, NOT futures odds
  → Do NOT match these to daily games (that's comparing apples to oranges)
  → These are handled by group fair value analysis instead
"""
import logging
import re
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# Patterns that indicate a championship/futures market (NOT a daily match)
FUTURES_PATTERNS = [
    r'win the \d{4}',        # "win the 2026 NHL Stanley Cup"
    r'stanley cup',
    r'nba finals',
    r'nba championship',
    r'world series',
    r'champions league.*win',
    r'win.*champions league',
    r'fifa world cup',
    r'premier league.*finish',
    r'finish in.*place',
]

# Compiled once
_FUTURES_RE = [re.compile(p, re.IGNORECASE) for p in FUTURES_PATTERNS]


def is_futures_market(question: str) -> bool:
    """Check if a Polymarket question is about a championship/futures outcome."""
    for pat in _FUTURES_RE:
        if pat.search(question):
            return True
    return False


def extract_team_from_daily_market(question: str) -> Optional[Tuple[str, str]]:
    """
    Extract (team_to_match, event_hint) from a daily match question.
    
    Formats we handle:
      "Will Rajasthan Royals win? (Rajasthan Royals vs Mumbai Indians)"
      "Will Delhi Capitals win? (Delhi Capitals vs Gujarat Titans)"
    
    Returns (team_name, "TeamA vs TeamB") or None.
    """
    # Pattern: "Will <TEAM> win? (<TEAM_A> vs <TEAM_B>)"
    m = re.match(
        r"Will (.+?) win\??\s*\((.+?)\s+vs\.?\s+(.+?)\)",
        question, re.IGNORECASE
    )
    if m:
        team = m.group(1).strip()
        team_a = m.group(2).strip()
        team_b = m.group(3).strip()
        event_hint = f"{team_a} vs {team_b}"
        return (team, event_hint)
    
    # Pattern: "Will <TEAM> win on <date>?"
    m = re.match(
        r"Will (.+?) win on \d{4}-\d{2}-\d{2}\??",
        question, re.IGNORECASE
    )
    if m:
        team = m.group(1).strip()
        return (team, None)
    
    # Pattern: "Will <TEAM> win? (<anything>)"
    m = re.match(
        r"Will (.+?) win\??\s*\((.+?)\)",
        question, re.IGNORECASE
    )
    if m:
        team = m.group(1).strip()
        return (team, m.group(2).strip())
    
    return None


def fuzzy_score(a: str, b: str) -> float:
    """Similarity score 0.0–1.0 between two strings."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


class MarketMatcher:
    """Link Polymarket daily match markets to sportsbook H2H odds."""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
    
    async def link_markets_to_sportsbooks(self) -> int:
        """
        Link Polymarket daily-match markets to sportsbook events.
        
        Strategy:
        1. Get all active Polymarket sports markets
        2. Skip futures/championship markets (no sportsbook futures data)
        3. For daily match markets, extract team name
        4. Fuzzy match team against sportsbook outcomes for the same sport
        5. Update polymarket_id in sportsbook_odds for the matching outcome row
        """
        linked_count = 0
        
        try:
            async with self.db_pool.acquire() as conn:
                # Clear stale links (re-link fresh each run)
                await conn.execute("UPDATE sportsbook_odds SET polymarket_id = NULL")
                
                # Get all active Polymarket sports markets
                markets = await conn.fetch("""
                    SELECT market_id, question, sport, yes_price
                    FROM sports_markets
                    WHERE is_active = true
                """)
                
                # Get all recent sportsbook outcomes grouped by sport
                sportsbook_rows = await conn.fetch("""
                    SELECT id, sport, event_name, outcome, bookmaker, implied_probability
                    FROM sportsbook_odds
                    WHERE fetched_at > NOW() - INTERVAL '48 hours'
                """)
                
                # Index sportsbook by sport
                sb_by_sport: Dict[str, List] = {}
                for row in sportsbook_rows:
                    sport = row['sport']
                    if sport not in sb_by_sport:
                        sb_by_sport[sport] = []
                    sb_by_sport[sport].append(row)
                
                for market in markets:
                    market_id = market['market_id']
                    question = market['question']
                    sport = market['sport']
                    
                    # Skip futures/championship markets — no sportsbook futures data
                    if is_futures_market(question):
                        continue
                    
                    # Extract team name from daily match question
                    extracted = extract_team_from_daily_market(question)
                    if not extracted:
                        logger.debug(f"Could not extract team from: {question}")
                        continue
                    
                    team_name, event_hint = extracted
                    
                    # Get sportsbook rows for this sport
                    sport_rows = sb_by_sport.get(sport, [])
                    if not sport_rows:
                        logger.debug(f"No sportsbook data for sport: {sport}")
                        continue
                    
                    # Find best matching outcome
                    best_score = 0.0
                    best_matches = []  # (score, row)
                    
                    for sb_row in sport_rows:
                        outcome = sb_row['outcome']
                        event_name = sb_row['event_name']
                        
                        # Score team name against sportsbook outcome
                        score = fuzzy_score(team_name, outcome)
                        
                        # Boost: if one contains the other
                        if team_name.lower() in outcome.lower() or outcome.lower() in team_name.lower():
                            score = max(score, 0.90)
                        
                        # If we have an event hint like "DC vs GT", also check event_name
                        if event_hint and score > 0.6:
                            event_score = fuzzy_score(event_hint, event_name)
                            if event_score > 0.7:
                                score = max(score, score + 0.05)  # Small boost for event match
                        
                        if score > best_score:
                            best_score = score
                            best_matches = [(score, sb_row)]
                        elif score == best_score and score > 0.7:
                            best_matches.append((score, sb_row))
                    
                    # Require at least 0.7 similarity
                    if best_score < 0.7:
                        logger.debug(f"No match for '{question}' (best score: {best_score:.2f})")
                        continue
                    
                    # Link all matching rows (same outcome from different bookmakers)
                    # Get the outcome name from best match
                    matched_outcome = best_matches[0][1]['outcome']
                    matched_event = best_matches[0][1]['event_name']
                    
                    # Update ALL sportsbook rows with this outcome + event
                    await conn.execute("""
                        UPDATE sportsbook_odds
                        SET polymarket_id = $1
                        WHERE outcome = $2
                        AND event_name = $3
                        AND sport = $4
                        AND fetched_at > NOW() - INTERVAL '48 hours'
                    """, market_id, matched_outcome, matched_event, sport)
                    
                    linked_count += 1
                    logger.info(
                        f"✅ Linked '{question[:60]}' → "
                        f"'{matched_outcome}' in '{matched_event}' "
                        f"(score: {best_score:.2f})"
                    )
        
        except Exception as e:
            logger.error(f"Failed to link markets: {e}", exc_info=True)
        
        logger.info(f"✅ Linked {linked_count} Polymarket markets to sportsbook outcomes")
        return linked_count
    
    async def get_sportsbook_price_for_market(self, market_id: str) -> Optional[float]:
        """
        Get consensus de-vigged probability from sportsbooks for a linked market.
        Averages across all bookmakers that have this outcome linked.
        """
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT implied_probability
                    FROM sportsbook_odds
                    WHERE polymarket_id = $1
                    AND fetched_at > NOW() - INTERVAL '48 hours'
                """, market_id)
                
                if not rows:
                    return None
                
                probabilities = [float(row['implied_probability']) for row in rows]
                consensus = sum(probabilities) / len(probabilities)
                
                return consensus
        
        except Exception as e:
            logger.error(f"Failed to get sportsbook price for {market_id}: {e}")
            return None
