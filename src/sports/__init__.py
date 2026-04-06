"""
Sports Intelligence Module for PolyEdge
Tracks sports markets on Polymarket and generates arbitrage/edge signals.
"""
from .polymarket_sports_scanner import PolymarketSportsScanner
from .espn_live import ESPNLiveScores
from .correlation_engine import CorrelationEngine
from .cross_odds_engine import CrossOddsEngine
from .sports_signal_loop import SportsSignalLoop

__all__ = [
    'PolymarketSportsScanner',
    'ESPNLiveScores',
    'CorrelationEngine',
    'CrossOddsEngine',
    'SportsSignalLoop',
]
