"""Alerts module for WeatherBot."""
from src.alerts.telegram_bot import send_alert, send_daily_summary

__all__ = ['send_alert', 'send_daily_summary']
