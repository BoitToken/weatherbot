"""
Configuration module for WeatherBot.
Loads settings from .env file and provides defaults.
"""
import os
from dotenv import load_dotenv

# Load .env file from project root — override=True so .env wins over parent process env
# (OpenClaw injects its own TELEGRAM_BOT_TOKEN which is the wrong bot)
load_dotenv(override=True)

# Database
DB_URL = os.getenv("DB_URL", "postgresql://node@localhost:5432/polyedge")

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")  # Admin chat ID for manual broadcasts
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))  # Alias

# Mode
MODE = os.getenv("MODE", "live")  # "live" or "backtest"

# Risk Parameters
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.02"))  # 2% default
MAX_DRAWDOWN = float(os.getenv("MAX_DRAWDOWN", "0.10"))  # 10% default
KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.5"))  # Half-Kelly default
POSITION_SIZE_LIMIT = float(os.getenv("POSITION_SIZE_LIMIT", "0.25"))  # 25% max per position

# Scan Intervals (seconds)
METAR_SCAN_INTERVAL = int(os.getenv("METAR_SCAN_INTERVAL", "1800"))  # 30 minutes
TAF_SCAN_INTERVAL = int(os.getenv("TAF_SCAN_INTERVAL", "3600"))  # 1 hour
TREND_CALCULATION_INTERVAL = int(os.getenv("TREND_CALCULATION_INTERVAL", "1800"))  # 30 minutes

# METAR/TAF Settings
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))  # seconds

# Trend Analysis
MIN_READINGS_FOR_TREND = int(os.getenv("MIN_READINGS_FOR_TREND", "3"))
TREND_LOOKBACK_HOURS = int(os.getenv("TREND_LOOKBACK_HOURS", "6"))
MIN_CONFIDENCE_THRESHOLD = float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.5"))  # R² threshold

# Debug
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Export all config as dict for debugging
def get_config_dict():
    """Return all configuration as a dictionary."""
    return {
        "DB_URL": DB_URL,
        "MODE": MODE,
        "RISK_PER_TRADE": RISK_PER_TRADE,
        "MAX_DRAWDOWN": MAX_DRAWDOWN,
        "KELLY_FRACTION": KELLY_FRACTION,
        "POSITION_SIZE_LIMIT": POSITION_SIZE_LIMIT,
        "METAR_SCAN_INTERVAL": METAR_SCAN_INTERVAL,
        "TAF_SCAN_INTERVAL": TAF_SCAN_INTERVAL,
        "TREND_CALCULATION_INTERVAL": TREND_CALCULATION_INTERVAL,
        "MAX_CONCURRENT_REQUESTS": MAX_CONCURRENT_REQUESTS,
        "REQUEST_TIMEOUT": REQUEST_TIMEOUT,
        "MIN_READINGS_FOR_TREND": MIN_READINGS_FOR_TREND,
        "TREND_LOOKBACK_HOURS": TREND_LOOKBACK_HOURS,
        "MIN_CONFIDENCE_THRESHOLD": MIN_CONFIDENCE_THRESHOLD,
        "DEBUG": DEBUG,
    }
