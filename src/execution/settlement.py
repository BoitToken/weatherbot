"""
Trade Settlement Service
Checks completed matches and settles open trades with P&L.

Data sources:
1. The Odds API /scores endpoint (completed=true, daysFrom=3)
2. ESPN Cricket API (league 8048 for IPL)
3. Manual settlement via API endpoint

Runs periodically (every 5 min) or on-demand via /api/trades/settle
"""
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# STRATEGY PERFORMANCE TRACKING (Sprint 2)
# ═══════════════════════════════════════════════════════════════

async def update_strategy_stats(db_fetch_all, db_execute, db_fetch_one, strategy: str, sport: str, pnl: float, edge: float):
    """
    Update strategy_performance table after each settled trade.
    - Upserts today's period record
    - Recalculates rolling win rate (last 30 trades)
    - Auto-disables strategies with <48% win rate over 30+ trades
    """
    from datetime import date
    today = date.today()
    sport = sport or 'ALL'
    
    try:
        # 1. Get rolling stats for this strategy (last 30 trades)
        rolling = await db_fetch_one("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl_usd <= 0 THEN 1 ELSE 0 END) as losses,
                AVG(edge_at_entry) as avg_edge,
                AVG(pnl_usd) as avg_pnl,
                SUM(pnl_usd) as total_pnl
            FROM (
                SELECT pnl_usd, edge_at_entry FROM trades 
                WHERE strategy = %s AND status IN ('won', 'lost')
                ORDER BY resolved_at DESC 
                LIMIT 30
            ) recent
        """, (strategy,))
        
        total = int(rolling.get('total', 0) or 0)
        wins = int(rolling.get('wins', 0) or 0)
        losses = int(rolling.get('losses', 0) or 0)
        avg_edge = float(rolling.get('avg_edge', 0) or 0)
        avg_pnl = float(rolling.get('avg_pnl', 0) or 0)
        total_pnl_rolling = float(rolling.get('total_pnl', 0) or 0)
        win_rate = (wins / total) if total > 0 else 0.0
        
        # 2. Calculate Sharpe ratio (simple: mean/std of returns)
        sharpe = None
        if total >= 5:
            pnl_rows = await db_fetch_all("""
                SELECT pnl_usd FROM trades 
                WHERE strategy = %s AND status IN ('won', 'lost')
                ORDER BY resolved_at DESC 
                LIMIT 30
            """, (strategy,))
            if pnl_rows:
                pnls = [float(r.get('pnl_usd', 0) or 0) for r in pnl_rows]
                mean_pnl = sum(pnls) / len(pnls)
                if len(pnls) > 1:
                    variance = sum((p - mean_pnl) ** 2 for p in pnls) / (len(pnls) - 1)
                    std_pnl = variance ** 0.5
                    if std_pnl > 0:
                        sharpe = round(mean_pnl / std_pnl, 3)
        
        # 3. Calculate max drawdown from cumulative P&L
        max_drawdown = 0.0
        if total >= 2:
            all_pnls = await db_fetch_all("""
                SELECT pnl_usd FROM trades 
                WHERE strategy = %s AND status IN ('won', 'lost')
                ORDER BY resolved_at ASC
            """, (strategy,))
            if all_pnls:
                cumulative = 0.0
                peak = 0.0
                for r in all_pnls:
                    cumulative += float(r.get('pnl_usd', 0) or 0)
                    if cumulative > peak:
                        peak = cumulative
                    dd = peak - cumulative
                    if dd > max_drawdown:
                        max_drawdown = dd
        
        # 4. Upsert today's record
        await db_execute("""
            INSERT INTO strategy_performance 
                (strategy, sport, period_start, period_end, total_trades, wins, losses, 
                 win_rate, total_pnl, avg_edge, avg_pnl_per_trade, max_drawdown, sharpe_ratio, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (strategy, sport, period_start) DO UPDATE SET
                total_trades = EXCLUDED.total_trades,
                wins = EXCLUDED.wins,
                losses = EXCLUDED.losses,
                win_rate = EXCLUDED.win_rate,
                total_pnl = EXCLUDED.total_pnl,
                avg_edge = EXCLUDED.avg_edge,
                avg_pnl_per_trade = EXCLUDED.avg_pnl_per_trade,
                max_drawdown = EXCLUDED.max_drawdown,
                sharpe_ratio = EXCLUDED.sharpe_ratio,
                updated_at = NOW()
        """, (
            strategy, sport, today, today,
            total, wins, losses,
            round(win_rate, 4), round(total_pnl_rolling, 2),
            round(avg_edge, 4), round(avg_pnl, 2),
            round(max_drawdown, 2), sharpe
        ))
        
        # 5. Auto-disable check: <48% win rate over 30+ trades
        if total >= 30 and win_rate < 0.48:
            await db_execute("""
                UPDATE strategy_performance SET is_active = false, updated_at = NOW()
                WHERE strategy = %s
            """, (strategy,))
            logger.warning(
                f"\U0001f6ab Strategy '{strategy}' AUTO-DISABLED: "
                f"win rate {win_rate*100:.1f}% over {total} trades (threshold: 48%)"
            )
            return {'disabled': True, 'win_rate': win_rate, 'total_trades': total}
        
        logger.info(
            f"\U0001f4ca Strategy '{strategy}' stats updated: "
            f"{wins}W/{losses}L ({win_rate*100:.1f}%), "
            f"P&L: ${total_pnl_rolling:+.2f}, Sharpe: {sharpe}"
        )
        return {'disabled': False, 'win_rate': win_rate, 'total_trades': total}
        
    except Exception as e:
        logger.error(f"Failed to update strategy stats for '{strategy}': {e}")
        return {'error': str(e)}


async def fetch_completed_scores(odds_api_key: str) -> List[Dict]:
    """Fetch completed match scores from The Odds API."""
    results = []
    sports = [
        'cricket_ipl',
        'basketball_nba',
        'icehockey_nhl',
        'soccer_epl',
    ]
    
    async with httpx.AsyncClient(timeout=15) as client:
        for sport in sports:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
                resp = await client.get(url, params={
                    'apiKey': odds_api_key,
                    'daysFrom': 3,
                })
                if resp.status_code == 200:
                    data = resp.json()
                    for event in data:
                        if event.get('completed'):
                            results.append({
                                'sport_key': sport,
                                'home_team': event.get('home_team', ''),
                                'away_team': event.get('away_team', ''),
                                'scores': event.get('scores', []),
                                'commence_time': event.get('commence_time', ''),
                                'completed': True,
                            })
                elif resp.status_code == 422:
                    # No events in timeframe
                    pass
                else:
                    logger.warning(f"Odds API {sport}: HTTP {resp.status_code}")
            except Exception as e:
                logger.error(f"Failed to fetch {sport} scores: {e}")
    
    return results


async def fetch_espn_cricket_scores() -> List[Dict]:
    """Fetch IPL scores from ESPN Cricket API."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://site.api.espn.com/apis/site/v2/sports/cricket/8048/scoreboard",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code == 200:
                data = resp.json()
                for event in data.get('events', []):
                    status = event.get('status', {}).get('type', {})
                    if status.get('completed', False):
                        teams = {}
                        for comp in event.get('competitions', []):
                            for team in comp.get('competitors', []):
                                name = team.get('team', {}).get('displayName', '')
                                teams[name] = {
                                    'score': team.get('score', ''),
                                    'winner': team.get('winner', False),
                                }
                        results.append({
                            'name': event.get('name', ''),
                            'teams': teams,
                            'completed': True,
                            'source': 'espn',
                        })
    except Exception as e:
        logger.error(f"ESPN cricket error: {e}")
    return results


def determine_winner(scores: List[Dict]) -> Optional[str]:
    """Determine winner from Odds API scores format."""
    if not scores or len(scores) < 2:
        return None
    
    # For cricket: higher score wins
    # For other sports: higher score wins
    try:
        team_scores = []
        for s in scores:
            name = s.get('name', '')
            score_str = s.get('score', '0')
            # Cricket scores can be like "185/5" — take the runs (before /)
            if '/' in str(score_str):
                score_val = int(str(score_str).split('/')[0])
            else:
                score_val = int(float(score_str))
            team_scores.append((name, score_val))
        
        if len(team_scores) >= 2:
            team_scores.sort(key=lambda x: x[1], reverse=True)
            if team_scores[0][1] > team_scores[1][1]:
                return team_scores[0][0]
    except Exception as e:
        logger.error(f"Error determining winner: {e}")
    
    return None


def match_trade_to_result(trade: Dict, completed_events: List[Dict]) -> Optional[Tuple[str, str]]:
    """
    Match an open trade to a completed event result.
    Returns (winner_team_name, 'won'|'lost') or None if no match found.
    
    STRICT matching: both teams in the event must appear in the market_title.
    This prevents cross-sport false matches (e.g. NHL team matching IPL trade).
    """
    market_title = (trade.get('market_title') or '').lower()
    metadata = trade.get('metadata') or {}
    team_backed = (metadata.get('team') or '').lower()
    match_time_str = metadata.get('match_time', '')
    
    # Skip future trades (match_time > now)
    if match_time_str:
        try:
            from datetime import timezone as tz
            mt_str = match_time_str.replace('+05:30', '+0530')
            mt = datetime.fromisoformat(mt_str)
            if mt.tzinfo is None:
                mt = mt.replace(tzinfo=tz.utc)
            now = datetime.now(tz.utc)
            if mt > now:
                return None  # Match hasn't started yet
        except:
            pass
    
    for event in completed_events:
        home = (event.get('home_team') or '').lower()
        away = (event.get('away_team') or '').lower()
        
        if not home or not away:
            continue
        
        # STRICT: Both teams must match the market title
        # Use significant words (>3 chars) to match
        home_words = [w for w in home.split() if len(w) > 3]
        away_words = [w for w in away.split() if len(w) > 3]
        
        home_match = any(w in market_title for w in home_words) if home_words else False
        away_match = any(w in market_title for w in away_words) if away_words else False
        
        # Both teams must be present in title for a match
        if not (home_match and away_match):
            continue
        
        # Also verify sport alignment if possible
        # IPL trades have 'IPL:' prefix; don't match to NBA/NHL events
        sport_key = event.get('sport_key', '')
        if 'ipl:' in market_title and 'cricket' not in sport_key:
            continue
        if 'nba' in market_title and 'basketball' not in sport_key:
            continue
        if 'nhl' in market_title and 'hockey' not in sport_key:
            continue
        
        # Found a match — determine winner
        scores = event.get('scores', [])
        winner = determine_winner(scores)
        
        if not winner:
            # Try ESPN data
            teams = event.get('teams', {})
            for tname, tdata in teams.items():
                if tdata.get('winner'):
                    winner = tname
                    break
        
        if not winner:
            continue
        
        winner_lower = winner.lower()
        
        # Did our backed team win?
        if team_backed:
            backed_words = [w for w in team_backed.split() if len(w) > 3]
            if any(w in winner_lower for w in backed_words):
                return (winner, 'won')
            else:
                return (winner, 'lost')
        
        # Fallback: check side from market_title
        # "IPL: RR vs MI - Mumbai Indians" means we backed Mumbai Indians
        if ' - ' in trade.get('market_title', ''):
            backed = trade['market_title'].split(' - ')[-1].lower()
            backed_words = [w for w in backed.split() if len(w) > 3]
            if any(w in winner_lower for w in backed_words):
                return (winner, 'won')
            else:
                return (winner, 'lost')
    
    return None


async def settle_trades(db_fetch_all, db_execute, db_fetch_one, odds_api_key: str) -> Dict:
    """
    Main settlement loop.
    1. Get all open trades
    2. Fetch completed match results
    3. Settle matching trades
    4. Return summary
    """
    settled = []
    errors = []
    
    # 1. Get open trades with past match times
    open_trades = await db_fetch_all("""
        SELECT id, market_id, market_title, side, entry_price, shares, size_usd,
               edge_at_entry, status, entry_at, metadata
        FROM trades
        WHERE status IN ('open', 'paper_open', 'live_open')
        ORDER BY entry_at ASC
    """)
    
    if not open_trades:
        return {"settled": 0, "message": "No open trades to settle"}
    
    logger.info(f"📋 Found {len(open_trades)} open trades to check")
    
    # 2. Fetch completed scores from all sources
    completed_events = []
    
    if odds_api_key:
        odds_results = await fetch_completed_scores(odds_api_key)
        completed_events.extend(odds_results)
        logger.info(f"📊 Odds API: {len(odds_results)} completed events")
    
    espn_results = await fetch_espn_cricket_scores()
    completed_events.extend(espn_results)
    logger.info(f"🏏 ESPN: {len(espn_results)} completed events")
    
    if not completed_events:
        # Check if any trades have match_time in the past (> 6 hours ago)
        # These need manual resolution
        stale_trades = []
        now = datetime.now(timezone.utc)
        for trade in open_trades:
            meta = trade.get('metadata') or {}
            match_time_str = meta.get('match_time', '')
            if match_time_str:
                try:
                    mt = datetime.fromisoformat(match_time_str.replace('+05:30', '+0530').replace('+0530', '+05:30'))
                    if mt.tzinfo is None:
                        mt = mt.replace(tzinfo=timezone.utc)
                    if now - mt > timedelta(hours=6):
                        stale_trades.append({
                            'id': trade['id'],
                            'market_title': trade['market_title'],
                            'match_time': match_time_str,
                            'hours_ago': round((now - mt).total_seconds() / 3600, 1)
                        })
                except:
                    pass
        
        if stale_trades:
            return {
                "settled": 0,
                "stale_trades": stale_trades,
                "message": f"No completed events found in APIs, but {len(stale_trades)} trades have past match times. Use /api/trades/settle-manual to resolve."
            }
        return {"settled": 0, "message": "No completed events found"}
    
    # 3. Match and settle
    for trade in open_trades:
        try:
            result = match_trade_to_result(trade, completed_events)
            if not result:
                continue
            
            winner, outcome = result
            entry_price = float(trade.get('entry_price', 0.5))
            size_usd = float(trade.get('size_usd', 0))
            shares = float(trade.get('shares', 0))
            
            # Calculate P&L
            if outcome == 'won':
                # Bought at entry_price, resolved at 1.00 (100¢)
                # P&L = shares * (1.0 - entry_price) or size * (1/entry - 1)
                if shares > 0:
                    pnl = shares * (1.0 - entry_price)
                else:
                    pnl = size_usd * ((1.0 / entry_price) - 1.0)
                exit_price = 1.0
                new_status = 'won'
            else:
                # Lost entire position
                pnl = -size_usd
                exit_price = 0.0
                new_status = 'lost'
            
            # Update trade
            await db_execute("""
                UPDATE trades SET
                    status = %s,
                    exit_price = %s,
                    pnl_usd = %s,
                    pnl_pct = %s,
                    resolved_at = %s,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
            """, (
                new_status,
                exit_price,
                round(pnl, 2),
                round((pnl / size_usd * 100) if size_usd > 0 else 0, 1),
                datetime.utcnow(),
                f'{{"winner": "{winner}", "settled_by": "auto"}}',
                trade['id']
            ))
            
            settled.append({
                'id': trade['id'],
                'market_title': trade['market_title'],
                'outcome': outcome,
                'pnl': round(pnl, 2),
                'winner': winner,
            })
            
            icon = '\u2705' if outcome == 'won' else '\u274c'
            logger.info(f"{icon} Settled trade #{trade['id']}: {trade['market_title']} -> {outcome} (${pnl:+.2f})")
            
            # Sprint 2: Update per-strategy performance tracking
            try:
                strategy = trade.get('metadata', {}).get('strategy') or trade.get('strategy', 'unknown') if isinstance(trade.get('metadata'), dict) else 'unknown'
                # Try to extract strategy from metadata JSONB
                meta = trade.get('metadata') or {}
                if isinstance(meta, str):
                    import json as _json
                    try:
                        meta = _json.loads(meta)
                    except:
                        meta = {}
                strategy = meta.get('strategy', '') or ''
                # Fallback: check if trade row has strategy column
                if not strategy:
                    strategy = trade.get('strategy', 'unknown') or 'unknown'
                
                sport_key = ''
                market_title = (trade.get('market_title') or '').lower()
                if 'ipl' in market_title or 'cricket' in market_title:
                    sport_key = 'cricket_ipl'
                elif 'nba' in market_title or 'basketball' in market_title:
                    sport_key = 'basketball_nba'
                elif 'nhl' in market_title or 'hockey' in market_title:
                    sport_key = 'icehockey_nhl'
                elif 'soccer' in market_title or 'epl' in market_title:
                    sport_key = 'soccer_epl'
                else:
                    sport_key = 'ALL'
                
                edge_val = float(trade.get('edge_at_entry', 0) or 0)
                await update_strategy_stats(db_fetch_all, db_execute, db_fetch_one, strategy, sport_key, pnl, edge_val)
            except Exception as strat_err:
                logger.error(f"Strategy stats update failed for trade #{trade['id']}: {strat_err}")
            
            # Sprint 3: Learning engine post-trade analysis
            try:
                from src.learning.improvement import LearningEngine
                from src.db_async import get_async_pool
                learning_engine = LearningEngine(get_async_pool())
                await learning_engine.post_trade_analysis(
                    trade_id=trade['id'],
                    strategy=strategy,
                    sport=sport_key,
                    predicted_edge=edge_val,
                    actual_outcome=outcome,
                    pnl=round(pnl, 2),
                )
            except Exception as learn_err:
                logger.error(f"Learning engine error for trade #{trade['id']}: {learn_err}")
            
        except Exception as e:
            errors.append({'id': trade['id'], 'error': str(e)})
            logger.error(f"Failed to settle trade #{trade['id']}: {e}")
    
    # Also settle paper_trades_live if they exist
    try:
        open_paper = await db_fetch_all("""
            SELECT id, match_name, team_backed, entry_price, position_size, shares, status, metadata
            FROM paper_trades_live
            WHERE status = 'open'
        """)
        
        for pt in (open_paper or []):
            # Try to match against completed events
            fake_trade = {
                'market_title': pt.get('match_name', ''),
                'metadata': {'team': pt.get('team_backed', '')},
            }
            result = match_trade_to_result(fake_trade, completed_events)
            if not result:
                continue
            
            winner, outcome = result
            entry_price = float(pt.get('entry_price', 0.5))
            size = float(pt.get('position_size', 0))
            shares = float(pt.get('shares', 0))
            
            if outcome == 'won':
                pnl = shares * (1.0 - entry_price) if shares > 0 else size * ((1.0 / entry_price) - 1.0)
                exit_price = 1.0
            else:
                pnl = -size
                exit_price = 0.0
            
            await db_execute("""
                UPDATE paper_trades_live SET
                    status = %s,
                    exit_price = %s,
                    pnl = %s,
                    pnl_usd = %s,
                    resolved_at = %s,
                    notes = %s
                WHERE id = %s
            """, (
                outcome,
                exit_price,
                round(pnl, 2),
                round(pnl, 2),
                datetime.utcnow(),
                f"Winner: {winner}. Auto-settled.",
                pt['id']
            ))
            
            settled.append({
                'id': f"paper-{pt['id']}",
                'market_title': pt.get('match_name', ''),
                'outcome': outcome,
                'pnl': round(pnl, 2),
                'winner': winner,
            })
            icon = '✅' if outcome == 'won' else '❌'
            logger.info(f"{icon} Settled paper trade #{pt['id']}: {pt.get('match_name','')} -> {outcome} (${pnl:+.2f})")
            
            # Sprint 2: Update strategy stats for paper trades too
            try:
                pt_strategy = pt.get('strategy', 'unknown') or 'unknown'
                pt_sport = 'ALL'
                mn = (pt.get('match_name') or '').lower()
                if 'ipl' in mn or 'cricket' in mn:
                    pt_sport = 'cricket_ipl'
                elif 'nba' in mn:
                    pt_sport = 'basketball_nba'
                elif 'nhl' in mn:
                    pt_sport = 'icehockey_nhl'
                await update_strategy_stats(db_fetch_all, db_execute, db_fetch_one, pt_strategy, pt_sport, pnl, 0)
            except Exception as strat_err2:
                logger.error(f"Strategy stats update failed for paper trade #{pt['id']}: {strat_err2}")
    
    except Exception as e:
        logger.warning(f"Paper trades settlement skipped: {e}")
    
    total_pnl = sum(s['pnl'] for s in settled)
    return {
        "settled": len(settled),
        "total_pnl": round(total_pnl, 2),
        "trades": settled,
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat()
    }


async def manual_settle(db_execute, trade_id: int, outcome: str, winner: str = "") -> Dict:
    """
    Manually settle a specific trade.
    outcome: 'won' or 'lost'
    """
    from src.db import fetch_one
    
    trade = await fetch_one("SELECT * FROM trades WHERE id = %s", (trade_id,))
    if not trade:
        return {"error": f"Trade {trade_id} not found"}
    
    if trade['status'] not in ('open', 'paper_open', 'live_open'):
        return {"error": f"Trade {trade_id} already settled (status: {trade['status']})"}
    
    entry_price = float(trade.get('entry_price', 0.5))
    size_usd = float(trade.get('size_usd', 0))
    shares = float(trade.get('shares', 0))
    
    if outcome == 'won':
        pnl = shares * (1.0 - entry_price) if shares > 0 else size_usd * ((1.0 / entry_price) - 1.0)
        exit_price = 1.0
    else:
        pnl = -size_usd
        exit_price = 0.0
    
    await db_execute("""
        UPDATE trades SET
            status = %s,
            exit_price = %s,
            pnl_usd = %s,
            pnl_pct = %s,
            resolved_at = %s,
            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
        WHERE id = %s
    """, (
        outcome,
        exit_price,
        round(pnl, 2),
        round((pnl / size_usd * 100) if size_usd > 0 else 0, 1),
        datetime.utcnow(),
        f'{{"winner": "{winner}", "settled_by": "manual"}}',
        trade_id
    ))
    
    return {
        "settled": True,
        "trade_id": trade_id,
        "outcome": outcome,
        "pnl": round(pnl, 2),
        "winner": winner,
    }
