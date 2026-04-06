-- WeatherBot Database Schema
-- Run this to create all required tables

-- Signals table
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    signal_id UUID UNIQUE NOT NULL,
    city VARCHAR(100) NOT NULL,
    icao VARCHAR(4) NOT NULL,
    market_id VARCHAR(255),
    market_title TEXT,
    side VARCHAR(10) NOT NULL,  -- 'YES' or 'NO'
    market_price FLOAT NOT NULL,  -- 0-1
    metar_temp FLOAT,
    metar_trend FLOAT,
    threshold_type VARCHAR(50),  -- 'above_80', 'below_32', etc.
    edge_pct FLOAT NOT NULL,
    confidence VARCHAR(10),  -- 'HIGH', 'MEDIUM', 'LOW'
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'traded', 'skipped', 'expired'
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status, confidence);
CREATE INDEX IF NOT EXISTS idx_signals_city ON signals(city, created_at DESC);

-- Trades table
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY,
    signal_id INTEGER,
    city VARCHAR(100) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- 'YES' or 'NO'
    entry_price FLOAT NOT NULL,  -- cents (0-100)
    exit_price FLOAT,  -- cents (0-100)
    size_usd FLOAT NOT NULL,
    edge_pct FLOAT NOT NULL,
    status VARCHAR(20) NOT NULL,  -- 'paper_open', 'paper_won', 'paper_lost', 'live_open', etc.
    pnl FLOAT,  -- Realized P&L
    created_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_closed ON trades(closed_at DESC) WHERE closed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trades_city ON trades(city, created_at DESC);

-- Markets table
CREATE TABLE IF NOT EXISTS markets (
    id SERIAL PRIMARY KEY,
    market_id VARCHAR(255) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    city VARCHAR(100),
    icao VARCHAR(4),
    threshold_type VARCHAR(50),
    resolution_date TIMESTAMP,
    yes_price FLOAT,
    no_price FLOAT,
    volume FLOAT,
    liquidity FLOAT,
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'resolved', 'closed'
    outcome VARCHAR(10),  -- 'YES', 'NO', 'INVALID'
    last_scanned TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_markets_status ON markets(status, last_scanned DESC);
CREATE INDEX IF NOT EXISTS idx_markets_city ON markets(city, status);

-- Bot settings table
CREATE TABLE IF NOT EXISTS bot_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default bankroll if not exists
INSERT INTO bot_settings (key, value)
VALUES ('bankroll', '1000.0')
ON CONFLICT (key) DO NOTHING;

-- METAR readings (already in db.py, but included for completeness)
CREATE TABLE IF NOT EXISTS metar_readings (
    id SERIAL PRIMARY KEY,
    station_icao VARCHAR(4) NOT NULL,
    observation_time TIMESTAMP NOT NULL,
    raw_metar TEXT NOT NULL,
    temperature_c FLOAT,
    dewpoint_c FLOAT,
    wind_speed_kt FLOAT,
    wind_dir INTEGER,
    visibility_m FLOAT,
    pressure_hpa FLOAT,
    cloud_cover VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(station_icao, observation_time)
);

CREATE INDEX IF NOT EXISTS idx_metar_station_time 
ON metar_readings(station_icao, observation_time DESC);

-- Temperature trends
CREATE TABLE IF NOT EXISTS temperature_trends (
    id SERIAL PRIMARY KEY,
    station_icao VARCHAR(4) NOT NULL,
    calculated_at TIMESTAMP DEFAULT NOW(),
    trend_per_hour FLOAT,
    projected_high FLOAT,
    projected_low FLOAT,
    confidence FLOAT,
    num_readings INTEGER,
    UNIQUE(station_icao, calculated_at)
);

CREATE INDEX IF NOT EXISTS idx_trends_station_time 
ON temperature_trends(station_icao, calculated_at DESC);
