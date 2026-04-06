-- Telegram Subscriber Table
-- Stores users who subscribe via /start and their preferences

CREATE TABLE IF NOT EXISTS telegram_subscribers (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(100),
    first_name VARCHAR(100),
    tier VARCHAR(20) DEFAULT 'free',  -- free/pro/vip
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,
    sports_filter TEXT[],  -- ['IPL', 'NBA', 'NHL'] or NULL for all
    min_edge NUMERIC DEFAULT 5.0,  -- minimum edge % to receive alerts
    alert_frequency VARCHAR(20) DEFAULT 'instant',  -- instant/hourly/daily
    last_alert_at TIMESTAMPTZ,
    total_alerts_sent INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_telegram_subscribers_chat_id ON telegram_subscribers(chat_id);
CREATE INDEX IF NOT EXISTS idx_telegram_subscribers_active ON telegram_subscribers(is_active);
