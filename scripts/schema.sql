--
-- PostgreSQL database dump
--

\restrict 4tlW7O9rPRmOAfbcKtW47Km2F2zBXVnSmHy5FvhtoajQ3dZI18NBQjg0o537REd

-- Dumped from database version 15.17 (Homebrew)
-- Dumped by pg_dump version 15.17 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'SQL_ASCII';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: backtest_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.backtest_results (
    id integer NOT NULL,
    strategy character varying(100),
    sport character varying(50),
    match_name text,
    team_backed character varying(200),
    entry_price numeric,
    fair_value numeric,
    edge_pct numeric,
    position_size numeric,
    outcome character varying(20),
    pnl numeric,
    books_used text,
    match_date timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: backtest_results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.backtest_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: backtest_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.backtest_results_id_seq OWNED BY public.backtest_results.id;


--
-- Name: bankroll; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bankroll (
    id integer NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now(),
    total_usd numeric(12,2),
    available_usd numeric(12,2),
    in_positions_usd numeric(12,2),
    daily_pnl numeric(10,2)
);


--
-- Name: bankroll_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bankroll_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bankroll_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bankroll_id_seq OWNED BY public.bankroll.id;


--
-- Name: bot_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_settings (
    key text NOT NULL,
    value jsonb NOT NULL,
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: btc_bankroll; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.btc_bankroll (
    id integer NOT NULL,
    balance numeric(12,2) NOT NULL,
    available numeric(12,2) NOT NULL,
    in_positions numeric(12,2) DEFAULT 0,
    total_won numeric(12,2) DEFAULT 0,
    total_lost numeric(12,2) DEFAULT 0,
    total_trades integer DEFAULT 0,
    peak_balance numeric(12,2),
    max_drawdown_pct numeric(6,2) DEFAULT 0,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: btc_bankroll_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.btc_bankroll_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: btc_bankroll_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.btc_bankroll_id_seq OWNED BY public.btc_bankroll.id;


--
-- Name: btc_calibration; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.btc_calibration (
    id integer NOT NULL,
    date date NOT NULL,
    window_length integer NOT NULL,
    factor_weights jsonb NOT NULL,
    accuracy_overall numeric(6,4),
    accuracy_high_conviction numeric(6,4),
    accuracy_by_bucket jsonb,
    windows_analyzed integer,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: btc_calibration_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.btc_calibration_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: btc_calibration_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.btc_calibration_id_seq OWNED BY public.btc_calibration.id;


--
-- Name: btc_intelligence_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.btc_intelligence_log (
    id integer NOT NULL,
    date date NOT NULL,
    strategy_version text NOT NULL,
    trades_taken integer DEFAULT 0,
    trades_won integer DEFAULT 0,
    net_pnl numeric(12,2) DEFAULT 0,
    gross_profit numeric(12,2) DEFAULT 0,
    gross_loss numeric(12,2) DEFAULT 0,
    best_trade numeric(12,2) DEFAULT 0,
    avg_entry numeric(6,4) DEFAULT 0,
    avg_rr numeric(6,2) DEFAULT 0,
    best_hour integer,
    worst_hour integer,
    best_hour_pnl numeric(12,2),
    worst_hour_pnl numeric(12,2),
    volatility_data jsonb,
    verdict text,
    action_taken text,
    next_strategy text,
    learnings text,
    full_analysis jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: btc_intelligence_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.btc_intelligence_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: btc_intelligence_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.btc_intelligence_log_id_seq OWNED BY public.btc_intelligence_log.id;


--
-- Name: btc_signals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.btc_signals (
    id integer NOT NULL,
    window_id text,
    signal_ts timestamp with time zone DEFAULT now(),
    seconds_remaining integer,
    f_price_delta numeric(8,6),
    f_momentum numeric(8,6),
    f_volume_imbalance numeric(8,6),
    f_oracle_lead numeric(8,6),
    f_book_imbalance numeric(8,6),
    f_volatility numeric(8,6),
    f_time_decay numeric(8,6),
    prob_up numeric(6,4) NOT NULL,
    prediction text NOT NULL,
    confidence numeric(6,4),
    skip_reason text,
    weights_used jsonb,
    was_correct boolean,
    created_at timestamp with time zone DEFAULT now(),
    stake_used numeric(10,2)
);


--
-- Name: btc_windows; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.btc_windows (
    id integer NOT NULL,
    window_id text NOT NULL,
    window_length integer NOT NULL,
    open_time timestamp with time zone NOT NULL,
    close_time timestamp with time zone NOT NULL,
    btc_open numeric(12,2),
    btc_close numeric(12,2),
    up_price numeric(6,4),
    down_price numeric(6,4),
    resolution text,
    volume_usd numeric(18,2),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: btc_pnl; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.btc_pnl AS
 WITH best AS (
         SELECT DISTINCT ON (s.window_id) s.window_id,
            s.prediction,
            w.resolution,
            w.window_length,
            w.close_time,
            (s.prediction = w.resolution) AS correct,
                CASE
                    WHEN (s.prediction = 'UP'::text) THEN w.up_price
                    ELSE w.down_price
                END AS entry_price,
            s.confidence AS sig_confidence,
            s.f_price_delta AS sig_price_delta,
            s.stake_used
           FROM (public.btc_signals s
             JOIN public.btc_windows w ON ((s.window_id = w.window_id)))
          WHERE ((s.prediction <> 'SKIP'::text) AND (w.resolution IS NOT NULL))
          ORDER BY s.window_id, s.confidence DESC
        ), computed_stake AS (
         SELECT best.window_id,
            best.prediction,
            best.resolution,
            best.window_length,
            best.close_time,
            best.correct,
            best.entry_price,
            best.sig_confidence,
            best.sig_price_delta,
            best.stake_used,
            COALESCE(best.stake_used,
                CASE
                    WHEN ((best.sig_confidence >= 0.70) AND (abs(best.sig_price_delta) > 0.35) AND (best.entry_price < 0.30) AND (best.prediction = 'DOWN'::text)) THEN 600.0
                    WHEN ((best.sig_confidence >= 0.70) AND (abs(best.sig_price_delta) > 0.35) AND (best.entry_price < 0.30) AND (best.prediction = 'UP'::text)) THEN 100.0
                    WHEN ((best.prediction = 'DOWN'::text) AND (best.entry_price < 0.20)) THEN 150.0
                    WHEN ((best.prediction = 'DOWN'::text) AND (best.entry_price < 0.30)) THEN 100.0
                    WHEN ((best.prediction = 'DOWN'::text) AND (best.entry_price < 0.40)) THEN 75.0
                    WHEN ((best.prediction = 'DOWN'::text) AND (best.entry_price < 0.50)) THEN 50.0
                    WHEN ((best.prediction = 'UP'::text) AND (best.entry_price < 0.20)) THEN 25.0
                    WHEN ((best.prediction = 'UP'::text) AND (best.entry_price < 0.30)) THEN 25.0
                    WHEN ((best.prediction = 'UP'::text) AND (best.entry_price < 0.40)) THEN 35.0
                    WHEN ((best.prediction = 'UP'::text) AND (best.entry_price < 0.50)) THEN 25.0
                    ELSE 25.0
                END) AS stake
           FROM best
        )
 SELECT computed_stake.window_id,
    computed_stake.prediction,
    computed_stake.resolution,
    computed_stake.window_length,
    computed_stake.close_time,
    computed_stake.correct,
    computed_stake.entry_price,
    computed_stake.stake,
        CASE
            WHEN computed_stake.correct THEN (((computed_stake.stake / computed_stake.entry_price) - computed_stake.stake) * 0.98)
            ELSE ('-1.0'::numeric * computed_stake.stake)
        END AS trade_pnl
   FROM computed_stake
  WHERE ((computed_stake.entry_price > 0.005) AND (computed_stake.entry_price < 0.995));


--
-- Name: btc_signals_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.btc_signals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: btc_signals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.btc_signals_id_seq OWNED BY public.btc_signals.id;


--
-- Name: btc_strategy_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.btc_strategy_versions (
    id integer NOT NULL,
    version text NOT NULL,
    status text DEFAULT 'active'::text,
    max_entry numeric(6,4) NOT NULL,
    min_rr numeric(6,2) NOT NULL,
    min_factors integer NOT NULL,
    window_lengths integer[] NOT NULL,
    stakes jsonb NOT NULL,
    extra_rules jsonb,
    activated_at timestamp with time zone DEFAULT now(),
    deactivated_at timestamp with time zone,
    created_by text DEFAULT 'intelligence_loop'::text,
    notes text,
    parent_version text,
    performance_snapshot jsonb,
    revert_reason text
);


--
-- Name: btc_strategy_versions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.btc_strategy_versions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: btc_strategy_versions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.btc_strategy_versions_id_seq OWNED BY public.btc_strategy_versions.id;


--
-- Name: btc_volatility_hours; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.btc_volatility_hours (
    id integer NOT NULL,
    date date NOT NULL,
    hour_ist integer NOT NULL,
    window_length integer DEFAULT 5 NOT NULL,
    trades_taken integer DEFAULT 0,
    trades_won integer DEFAULT 0,
    trades_lost integer DEFAULT 0,
    net_pnl numeric(12,2) DEFAULT 0,
    avg_entry numeric(6,4) DEFAULT 0,
    btc_price_range_pct numeric(8,4) DEFAULT 0,
    best_trade numeric(12,2) DEFAULT 0,
    session_tag text DEFAULT 'v2'::text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: btc_volatility_hours_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.btc_volatility_hours_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: btc_volatility_hours_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.btc_volatility_hours_id_seq OWNED BY public.btc_volatility_hours.id;


--
-- Name: btc_windows_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.btc_windows_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: btc_windows_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.btc_windows_id_seq OWNED BY public.btc_windows.id;


--
-- Name: invite_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invite_codes (
    id integer NOT NULL,
    code character varying(20) NOT NULL,
    created_by bigint,
    used_by bigint,
    used_at timestamp with time zone,
    is_used boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: invite_codes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invite_codes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invite_codes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invite_codes_id_seq OWNED BY public.invite_codes.id;


--
-- Name: jc_bankroll; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jc_bankroll (
    id integer NOT NULL,
    balance numeric(12,2) DEFAULT 10000 NOT NULL,
    available numeric(12,2) DEFAULT 10000 NOT NULL,
    in_positions numeric(12,2) DEFAULT 0,
    total_won numeric(12,2) DEFAULT 0,
    total_lost numeric(12,2) DEFAULT 0,
    total_trades integer DEFAULT 0,
    peak_balance numeric(12,2) DEFAULT 10000,
    max_drawdown_pct numeric(6,2) DEFAULT 0,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: jc_bankroll_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.jc_bankroll_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: jc_bankroll_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.jc_bankroll_id_seq OWNED BY public.jc_bankroll.id;


--
-- Name: jc_levels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jc_levels (
    id integer NOT NULL,
    price numeric(12,2) NOT NULL,
    label text NOT NULL,
    level_type text NOT NULL,
    color text,
    active boolean DEFAULT true,
    source text DEFAULT 'chart_cdp'::text,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: jc_levels_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.jc_levels_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: jc_levels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.jc_levels_id_seq OWNED BY public.jc_levels.id;


--
-- Name: jc_manual_actions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jc_manual_actions (
    id integer NOT NULL,
    trade_id integer,
    action text NOT NULL,
    amount numeric,
    mode text,
    executed_at timestamp without time zone DEFAULT now(),
    result jsonb
);


--
-- Name: jc_manual_actions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.jc_manual_actions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: jc_manual_actions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.jc_manual_actions_id_seq OWNED BY public.jc_manual_actions.id;


--
-- Name: jc_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jc_settings (
    key text NOT NULL,
    value text NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: jc_trades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jc_trades (
    id integer NOT NULL,
    signal_source text DEFAULT 'jayson_discord'::text,
    direction text NOT NULL,
    entry_price numeric(12,2) NOT NULL,
    stop_loss numeric(12,2),
    take_profit_1 numeric(12,2),
    take_profit_2 numeric(12,2),
    risk_reward numeric(6,2),
    stake_usd numeric(10,2) DEFAULT 100,
    leverage integer DEFAULT 30,
    status text DEFAULT 'pending'::text,
    entry_reason text,
    close_reason text,
    entry_fill_price numeric(12,2),
    exit_fill_price numeric(12,2),
    realized_pnl numeric(12,2),
    unrealized_pnl numeric(12,2),
    btc_price_at_signal numeric(12,2),
    half_closed_at numeric(12,2),
    breakeven_set_at timestamp with time zone,
    opened_at timestamp with time zone DEFAULT now(),
    closed_at timestamp with time zone,
    signal_message text,
    metadata jsonb,
    original_stop_loss numeric(12,2),
    original_tp1 numeric(12,2),
    original_tp2 numeric(12,2),
    manual_override boolean DEFAULT false,
    risk_amount numeric(12,2)
);


--
-- Name: jc_trades_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.jc_trades_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: jc_trades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.jc_trades_id_seq OWNED BY public.jc_trades.id;


--
-- Name: leader_copy_positions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leader_copy_positions (
    id integer NOT NULL,
    leader_trade_id integer,
    condition_id text NOT NULL,
    market_title text,
    our_entry_price real,
    our_size real,
    outcome_index integer,
    status text DEFAULT 'open'::text,
    pnl real DEFAULT 0,
    opened_at timestamp without time zone DEFAULT now(),
    closed_at timestamp without time zone
);


--
-- Name: leader_copy_positions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.leader_copy_positions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: leader_copy_positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.leader_copy_positions_id_seq OWNED BY public.leader_copy_positions.id;


--
-- Name: leader_performance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leader_performance (
    id integer NOT NULL,
    wallet text NOT NULL,
    date date NOT NULL,
    trades_count integer DEFAULT 0,
    volume real DEFAULT 0,
    pnl real DEFAULT 0,
    win_count integer DEFAULT 0,
    loss_count integer DEFAULT 0,
    avg_entry_price real DEFAULT 0
);


--
-- Name: leader_performance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.leader_performance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: leader_performance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.leader_performance_id_seq OWNED BY public.leader_performance.id;


--
-- Name: leader_trades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leader_trades (
    id integer NOT NULL,
    wallet text NOT NULL,
    condition_id text NOT NULL,
    market_slug text,
    market_title text,
    trade_type text,
    sport text,
    side text,
    outcome_index integer,
    leader_price real,
    leader_size real,
    leader_total_position real DEFAULT 0,
    our_size real DEFAULT 0,
    our_price real DEFAULT 0,
    status text DEFAULT 'detected'::text,
    result text,
    pnl real DEFAULT 0,
    detected_at timestamp without time zone DEFAULT now(),
    settled_at timestamp without time zone,
    polymarket_url text
);


--
-- Name: leader_trades_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.leader_trades_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: leader_trades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.leader_trades_id_seq OWNED BY public.leader_trades.id;


--
-- Name: leader_wallets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leader_wallets (
    id integer NOT NULL,
    wallet text NOT NULL,
    name text DEFAULT 'Unknown'::text NOT NULL,
    active boolean DEFAULT true,
    scale_factor real DEFAULT 0.00025,
    max_position real DEFAULT 50.0,
    min_edge real DEFAULT 0.0,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: leader_wallets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.leader_wallets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: leader_wallets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.leader_wallets_id_seq OWNED BY public.leader_wallets.id;


--
-- Name: learning_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.learning_reports (
    id integer NOT NULL,
    report_type character varying(50),
    report_data jsonb,
    recommendations jsonb,
    status character varying(20) DEFAULT 'pending'::character varying,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: learning_reports_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.learning_reports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: learning_reports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.learning_reports_id_seq OWNED BY public.learning_reports.id;


--
-- Name: live_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.live_events (
    id integer NOT NULL,
    sport character varying(50),
    event_id character varying(255),
    home_team character varying(200),
    away_team character varying(200),
    home_score integer DEFAULT 0,
    away_score integer DEFAULT 0,
    status character varying(50),
    minute character varying(20),
    period character varying(20),
    key_events jsonb,
    linked_market_ids text[],
    last_updated timestamp with time zone DEFAULT now()
);


--
-- Name: live_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.live_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: live_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.live_events_id_seq OWNED BY public.live_events.id;


--
-- Name: live_trades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.live_trades (
    id integer NOT NULL,
    window_id text,
    prediction text,
    token_id text,
    side text,
    entry_price numeric,
    stake_usd numeric,
    tx_hash text,
    status text DEFAULT 'pending'::text,
    exit_price numeric,
    pnl_usd numeric,
    wallet_balance_before numeric,
    wallet_balance_after numeric,
    created_at timestamp with time zone DEFAULT now(),
    resolved_at timestamp with time zone
);


--
-- Name: live_trades_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.live_trades_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: live_trades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.live_trades_id_seq OWNED BY public.live_trades.id;


--
-- Name: metar_readings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metar_readings (
    id integer NOT NULL,
    station_icao character varying(4) NOT NULL,
    observation_time timestamp without time zone NOT NULL,
    raw_metar text NOT NULL,
    temperature_c double precision,
    dewpoint_c double precision,
    wind_speed_kt double precision,
    wind_dir integer,
    visibility_m double precision,
    pressure_hpa double precision,
    cloud_cover character varying(50),
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: metar_readings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metar_readings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metar_readings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metar_readings_id_seq OWNED BY public.metar_readings.id;


--
-- Name: noaa_forecasts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.noaa_forecasts (
    id integer NOT NULL,
    city character varying(100) NOT NULL,
    station_icao character varying(10),
    forecast_date date NOT NULL,
    high_c numeric,
    low_c numeric,
    high_f numeric,
    low_f numeric,
    confidence numeric,
    source character varying(50) DEFAULT 'noaa_gfs'::character varying,
    raw_data jsonb,
    fetched_at timestamp with time zone DEFAULT now()
);


--
-- Name: noaa_forecasts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.noaa_forecasts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: noaa_forecasts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.noaa_forecasts_id_seq OWNED BY public.noaa_forecasts.id;


--
-- Name: paper_trades_live; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.paper_trades_live (
    id integer NOT NULL,
    match_name text NOT NULL,
    sport character varying(50) DEFAULT 'IPL'::character varying,
    team_backed character varying(200),
    entry_price numeric,
    fair_value numeric,
    edge_pct numeric,
    position_size numeric,
    shares numeric,
    strategy character varying(100),
    books_consensus text,
    book_count integer,
    status character varying(20) DEFAULT 'open'::character varying,
    exit_price numeric,
    pnl numeric,
    match_time timestamp with time zone,
    entry_at timestamp with time zone DEFAULT now(),
    resolved_at timestamp with time zone,
    notes text
);


--
-- Name: paper_trades_live_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.paper_trades_live_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: paper_trades_live_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.paper_trades_live_id_seq OWNED BY public.paper_trades_live.id;


--
-- Name: penny_positions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.penny_positions (
    id integer NOT NULL,
    market_id text NOT NULL,
    condition_id text,
    question text NOT NULL,
    category text,
    outcome text,
    buy_price numeric(6,4) NOT NULL,
    quantity numeric(10,2) DEFAULT 1,
    size_usd numeric(10,2),
    potential_payout numeric(10,2),
    catalyst_score numeric(4,2),
    catalyst_reason text,
    days_to_resolution integer,
    volume_usd numeric(18,2),
    status text DEFAULT 'open'::text,
    resolution text,
    pnl_usd numeric(10,2),
    opened_at timestamp with time zone DEFAULT now(),
    resolved_at timestamp with time zone,
    metadata jsonb
);


--
-- Name: penny_positions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.penny_positions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: penny_positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.penny_positions_id_seq OWNED BY public.penny_positions.id;


--
-- Name: positions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.positions (
    id integer NOT NULL,
    market_id character varying(255) NOT NULL,
    market_title text,
    city character varying(100),
    strategy character varying(50) NOT NULL,
    side character varying(10) DEFAULT 'YES'::character varying,
    entry_price numeric NOT NULL,
    current_price numeric,
    size_usd numeric NOT NULL,
    shares numeric,
    status character varying(20) DEFAULT 'open'::character varying,
    entered_at timestamp with time zone DEFAULT now(),
    exited_at timestamp with time zone,
    exit_price numeric,
    pnl_usd numeric,
    notes text
);


--
-- Name: positions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.positions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.positions_id_seq OWNED BY public.positions.id;


--
-- Name: signals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signals (
    id integer NOT NULL,
    market_id text,
    station_icao text,
    city text,
    side text NOT NULL,
    our_probability numeric(6,4),
    market_price numeric(6,4),
    edge numeric(6,4),
    confidence text,
    claude_reasoning text,
    metar_data jsonb,
    was_traded boolean DEFAULT false,
    skip_reason text,
    created_at timestamp without time zone DEFAULT now(),
    bot text,
    market_title text,
    source text,
    recommended_size_usd numeric(10,2),
    expires_at timestamp without time zone,
    metadata jsonb,
    flagged boolean DEFAULT true,
    strategy character varying(50) DEFAULT 'intelligence_layer'::character varying,
    entry_price numeric,
    exit_threshold numeric DEFAULT 0.45
);


--
-- Name: signals_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.signals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: signals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.signals_id_seq OWNED BY public.signals.id;


--
-- Name: sports_markets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sports_markets (
    id integer NOT NULL,
    market_id character varying(255),
    question text,
    sport character varying(50),
    league character varying(100),
    event_type character varying(50),
    team_a character varying(200),
    team_b character varying(200),
    yes_price numeric,
    no_price numeric,
    volume_usd numeric,
    liquidity_usd numeric,
    resolution_date timestamp with time zone,
    group_id character varying(255),
    metadata jsonb,
    last_updated timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true
);


--
-- Name: sports_markets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sports_markets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sports_markets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sports_markets_id_seq OWNED BY public.sports_markets.id;


--
-- Name: sports_signals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sports_signals (
    id integer NOT NULL,
    edge_type character varying(50),
    sport character varying(50),
    market_id character varying(255),
    market_title text,
    group_id character varying(255),
    polymarket_price numeric,
    fair_value numeric,
    edge_pct numeric,
    confidence character varying(20),
    signal character varying(20),
    reasoning text,
    data_sources jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: sports_signals_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sports_signals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sports_signals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sports_signals_id_seq OWNED BY public.sports_signals.id;


--
-- Name: sportsbook_odds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sportsbook_odds (
    id integer NOT NULL,
    sport character varying(50),
    event_name text,
    bookmaker character varying(100),
    market_type character varying(50),
    outcome character varying(200),
    odds_decimal numeric,
    implied_probability numeric,
    polymarket_id character varying(255),
    fetched_at timestamp with time zone DEFAULT now()
);


--
-- Name: sportsbook_odds_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sportsbook_odds_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sportsbook_odds_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sportsbook_odds_id_seq OWNED BY public.sportsbook_odds.id;


--
-- Name: station_accuracy; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.station_accuracy (
    station_icao text NOT NULL,
    city text,
    total_signals integer DEFAULT 0,
    correct_signals integer DEFAULT 0,
    accuracy numeric(6,4),
    avg_temp_error_c numeric(5,2),
    best_lead_time_hours integer,
    last_updated timestamp without time zone DEFAULT now()
);


--
-- Name: strategy_performance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.strategy_performance (
    id integer NOT NULL,
    strategy character varying(50) NOT NULL,
    sport character varying(50) DEFAULT 'ALL'::character varying NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    total_trades integer DEFAULT 0,
    wins integer DEFAULT 0,
    losses integer DEFAULT 0,
    win_rate double precision,
    total_pnl double precision DEFAULT 0,
    avg_edge double precision DEFAULT 0,
    avg_pnl_per_trade double precision DEFAULT 0,
    max_drawdown double precision DEFAULT 0,
    sharpe_ratio double precision,
    is_active boolean DEFAULT true,
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: strategy_performance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.strategy_performance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: strategy_performance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.strategy_performance_id_seq OWNED BY public.strategy_performance.id;


--
-- Name: taf_forecasts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.taf_forecasts (
    id integer NOT NULL,
    station_icao character varying(4) NOT NULL,
    issue_time timestamp without time zone NOT NULL,
    valid_from timestamp without time zone NOT NULL,
    valid_to timestamp without time zone NOT NULL,
    raw_taf text NOT NULL,
    forecast_high double precision,
    forecast_low double precision,
    significant_weather text,
    wind_changes text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: taf_forecasts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.taf_forecasts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: taf_forecasts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.taf_forecasts_id_seq OWNED BY public.taf_forecasts.id;


--
-- Name: telegram_subscribers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_subscribers (
    id integer NOT NULL,
    chat_id bigint NOT NULL,
    username character varying(100),
    first_name character varying(100),
    tier character varying(20) DEFAULT 'free'::character varying,
    subscribed_at timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true,
    sports_filter text[],
    min_edge numeric DEFAULT 5.0,
    alert_frequency character varying(20) DEFAULT 'instant'::character varying,
    last_alert_at timestamp with time zone,
    total_alerts_sent integer DEFAULT 0,
    approved boolean DEFAULT false
);


--
-- Name: telegram_subscribers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.telegram_subscribers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: telegram_subscribers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.telegram_subscribers_id_seq OWNED BY public.telegram_subscribers.id;


--
-- Name: temperature_trends; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.temperature_trends (
    id integer NOT NULL,
    station_icao character varying(4) NOT NULL,
    calculated_at timestamp without time zone DEFAULT now(),
    trend_per_hour double precision,
    projected_high double precision,
    projected_low double precision,
    confidence double precision,
    num_readings integer
);


--
-- Name: temperature_trends_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.temperature_trends_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: temperature_trends_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.temperature_trends_id_seq OWNED BY public.temperature_trends.id;


--
-- Name: trade_learnings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trade_learnings (
    id integer NOT NULL,
    trade_id integer,
    strategy character varying(50),
    sport character varying(50),
    predicted_edge double precision,
    actual_outcome character varying(20),
    pnl_usd double precision,
    edge_bucket character varying(20),
    signal_was_correct boolean,
    analysis_notes text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: trade_learnings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trade_learnings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trade_learnings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trade_learnings_id_seq OWNED BY public.trade_learnings.id;


--
-- Name: trades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trades (
    id integer NOT NULL,
    signal_id integer,
    market_id text,
    market_title text,
    side text NOT NULL,
    entry_price numeric(6,4),
    shares numeric(12,4),
    size_usd numeric(10,2),
    edge_at_entry numeric(10,4),
    tx_hash text,
    status text DEFAULT 'open'::text,
    exit_price numeric(6,4),
    exit_tx_hash text,
    pnl_usd numeric(10,2),
    pnl_pct numeric(8,4),
    resolved_at timestamp without time zone,
    entry_at timestamp without time zone DEFAULT now(),
    metadata jsonb,
    strategy character varying(50) DEFAULT 'intelligence_layer'::character varying
);


--
-- Name: trades_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trades_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trades_id_seq OWNED BY public.trades.id;


--
-- Name: weather_markets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weather_markets (
    id integer NOT NULL,
    market_id text NOT NULL,
    title text NOT NULL,
    city text,
    station_icao text,
    threshold_type text,
    threshold_value numeric(6,1),
    threshold_unit text,
    resolution_date date,
    yes_price numeric(6,4),
    no_price numeric(6,4),
    volume_usd numeric(12,2),
    liquidity_usd numeric(12,2),
    last_updated timestamp without time zone DEFAULT now(),
    active boolean DEFAULT true,
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    volume numeric(12,2),
    liquidity numeric(12,2)
);


--
-- Name: weather_markets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.weather_markets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: weather_markets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.weather_markets_id_seq OWNED BY public.weather_markets.id;


--
-- Name: backtest_results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtest_results ALTER COLUMN id SET DEFAULT nextval('public.backtest_results_id_seq'::regclass);


--
-- Name: bankroll id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bankroll ALTER COLUMN id SET DEFAULT nextval('public.bankroll_id_seq'::regclass);


--
-- Name: btc_bankroll id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_bankroll ALTER COLUMN id SET DEFAULT nextval('public.btc_bankroll_id_seq'::regclass);


--
-- Name: btc_calibration id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_calibration ALTER COLUMN id SET DEFAULT nextval('public.btc_calibration_id_seq'::regclass);


--
-- Name: btc_intelligence_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_intelligence_log ALTER COLUMN id SET DEFAULT nextval('public.btc_intelligence_log_id_seq'::regclass);


--
-- Name: btc_signals id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_signals ALTER COLUMN id SET DEFAULT nextval('public.btc_signals_id_seq'::regclass);


--
-- Name: btc_strategy_versions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_strategy_versions ALTER COLUMN id SET DEFAULT nextval('public.btc_strategy_versions_id_seq'::regclass);


--
-- Name: btc_volatility_hours id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_volatility_hours ALTER COLUMN id SET DEFAULT nextval('public.btc_volatility_hours_id_seq'::regclass);


--
-- Name: btc_windows id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_windows ALTER COLUMN id SET DEFAULT nextval('public.btc_windows_id_seq'::regclass);


--
-- Name: invite_codes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invite_codes ALTER COLUMN id SET DEFAULT nextval('public.invite_codes_id_seq'::regclass);


--
-- Name: jc_bankroll id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jc_bankroll ALTER COLUMN id SET DEFAULT nextval('public.jc_bankroll_id_seq'::regclass);


--
-- Name: jc_levels id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jc_levels ALTER COLUMN id SET DEFAULT nextval('public.jc_levels_id_seq'::regclass);


--
-- Name: jc_manual_actions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jc_manual_actions ALTER COLUMN id SET DEFAULT nextval('public.jc_manual_actions_id_seq'::regclass);


--
-- Name: jc_trades id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jc_trades ALTER COLUMN id SET DEFAULT nextval('public.jc_trades_id_seq'::regclass);


--
-- Name: leader_copy_positions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_copy_positions ALTER COLUMN id SET DEFAULT nextval('public.leader_copy_positions_id_seq'::regclass);


--
-- Name: leader_performance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_performance ALTER COLUMN id SET DEFAULT nextval('public.leader_performance_id_seq'::regclass);


--
-- Name: leader_trades id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_trades ALTER COLUMN id SET DEFAULT nextval('public.leader_trades_id_seq'::regclass);


--
-- Name: leader_wallets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_wallets ALTER COLUMN id SET DEFAULT nextval('public.leader_wallets_id_seq'::regclass);


--
-- Name: learning_reports id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.learning_reports ALTER COLUMN id SET DEFAULT nextval('public.learning_reports_id_seq'::regclass);


--
-- Name: live_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.live_events ALTER COLUMN id SET DEFAULT nextval('public.live_events_id_seq'::regclass);


--
-- Name: live_trades id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.live_trades ALTER COLUMN id SET DEFAULT nextval('public.live_trades_id_seq'::regclass);


--
-- Name: metar_readings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metar_readings ALTER COLUMN id SET DEFAULT nextval('public.metar_readings_id_seq'::regclass);


--
-- Name: noaa_forecasts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.noaa_forecasts ALTER COLUMN id SET DEFAULT nextval('public.noaa_forecasts_id_seq'::regclass);


--
-- Name: paper_trades_live id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_trades_live ALTER COLUMN id SET DEFAULT nextval('public.paper_trades_live_id_seq'::regclass);


--
-- Name: penny_positions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.penny_positions ALTER COLUMN id SET DEFAULT nextval('public.penny_positions_id_seq'::regclass);


--
-- Name: positions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions ALTER COLUMN id SET DEFAULT nextval('public.positions_id_seq'::regclass);


--
-- Name: signals id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signals ALTER COLUMN id SET DEFAULT nextval('public.signals_id_seq'::regclass);


--
-- Name: sports_markets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sports_markets ALTER COLUMN id SET DEFAULT nextval('public.sports_markets_id_seq'::regclass);


--
-- Name: sports_signals id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sports_signals ALTER COLUMN id SET DEFAULT nextval('public.sports_signals_id_seq'::regclass);


--
-- Name: sportsbook_odds id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sportsbook_odds ALTER COLUMN id SET DEFAULT nextval('public.sportsbook_odds_id_seq'::regclass);


--
-- Name: strategy_performance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_performance ALTER COLUMN id SET DEFAULT nextval('public.strategy_performance_id_seq'::regclass);


--
-- Name: taf_forecasts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.taf_forecasts ALTER COLUMN id SET DEFAULT nextval('public.taf_forecasts_id_seq'::regclass);


--
-- Name: telegram_subscribers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_subscribers ALTER COLUMN id SET DEFAULT nextval('public.telegram_subscribers_id_seq'::regclass);


--
-- Name: temperature_trends id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.temperature_trends ALTER COLUMN id SET DEFAULT nextval('public.temperature_trends_id_seq'::regclass);


--
-- Name: trade_learnings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade_learnings ALTER COLUMN id SET DEFAULT nextval('public.trade_learnings_id_seq'::regclass);


--
-- Name: trades id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trades ALTER COLUMN id SET DEFAULT nextval('public.trades_id_seq'::regclass);


--
-- Name: weather_markets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_markets ALTER COLUMN id SET DEFAULT nextval('public.weather_markets_id_seq'::regclass);


--
-- Name: backtest_results backtest_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtest_results
    ADD CONSTRAINT backtest_results_pkey PRIMARY KEY (id);


--
-- Name: bankroll bankroll_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bankroll
    ADD CONSTRAINT bankroll_pkey PRIMARY KEY (id);


--
-- Name: bot_settings bot_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_settings
    ADD CONSTRAINT bot_settings_pkey PRIMARY KEY (key);


--
-- Name: btc_bankroll btc_bankroll_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_bankroll
    ADD CONSTRAINT btc_bankroll_pkey PRIMARY KEY (id);


--
-- Name: btc_calibration btc_calibration_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_calibration
    ADD CONSTRAINT btc_calibration_pkey PRIMARY KEY (id);


--
-- Name: btc_intelligence_log btc_intelligence_log_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_intelligence_log
    ADD CONSTRAINT btc_intelligence_log_date_key UNIQUE (date);


--
-- Name: btc_intelligence_log btc_intelligence_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_intelligence_log
    ADD CONSTRAINT btc_intelligence_log_pkey PRIMARY KEY (id);


--
-- Name: btc_signals btc_signals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_signals
    ADD CONSTRAINT btc_signals_pkey PRIMARY KEY (id);


--
-- Name: btc_strategy_versions btc_strategy_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_strategy_versions
    ADD CONSTRAINT btc_strategy_versions_pkey PRIMARY KEY (id);


--
-- Name: btc_volatility_hours btc_volatility_hours_date_hour_ist_window_length_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_volatility_hours
    ADD CONSTRAINT btc_volatility_hours_date_hour_ist_window_length_key UNIQUE (date, hour_ist, window_length);


--
-- Name: btc_volatility_hours btc_volatility_hours_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_volatility_hours
    ADD CONSTRAINT btc_volatility_hours_pkey PRIMARY KEY (id);


--
-- Name: btc_windows btc_windows_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_windows
    ADD CONSTRAINT btc_windows_pkey PRIMARY KEY (id);


--
-- Name: btc_windows btc_windows_window_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_windows
    ADD CONSTRAINT btc_windows_window_id_key UNIQUE (window_id);


--
-- Name: invite_codes invite_codes_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invite_codes
    ADD CONSTRAINT invite_codes_code_key UNIQUE (code);


--
-- Name: invite_codes invite_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invite_codes
    ADD CONSTRAINT invite_codes_pkey PRIMARY KEY (id);


--
-- Name: jc_bankroll jc_bankroll_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jc_bankroll
    ADD CONSTRAINT jc_bankroll_pkey PRIMARY KEY (id);


--
-- Name: jc_levels jc_levels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jc_levels
    ADD CONSTRAINT jc_levels_pkey PRIMARY KEY (id);


--
-- Name: jc_manual_actions jc_manual_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jc_manual_actions
    ADD CONSTRAINT jc_manual_actions_pkey PRIMARY KEY (id);


--
-- Name: jc_settings jc_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jc_settings
    ADD CONSTRAINT jc_settings_pkey PRIMARY KEY (key);


--
-- Name: jc_trades jc_trades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jc_trades
    ADD CONSTRAINT jc_trades_pkey PRIMARY KEY (id);


--
-- Name: leader_copy_positions leader_copy_positions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_copy_positions
    ADD CONSTRAINT leader_copy_positions_pkey PRIMARY KEY (id);


--
-- Name: leader_performance leader_performance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_performance
    ADD CONSTRAINT leader_performance_pkey PRIMARY KEY (id);


--
-- Name: leader_performance leader_performance_wallet_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_performance
    ADD CONSTRAINT leader_performance_wallet_date_key UNIQUE (wallet, date);


--
-- Name: leader_trades leader_trades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_trades
    ADD CONSTRAINT leader_trades_pkey PRIMARY KEY (id);


--
-- Name: leader_trades leader_trades_wallet_condition_id_detected_at_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_trades
    ADD CONSTRAINT leader_trades_wallet_condition_id_detected_at_key UNIQUE (wallet, condition_id, detected_at);


--
-- Name: leader_wallets leader_wallets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_wallets
    ADD CONSTRAINT leader_wallets_pkey PRIMARY KEY (id);


--
-- Name: leader_wallets leader_wallets_wallet_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_wallets
    ADD CONSTRAINT leader_wallets_wallet_key UNIQUE (wallet);


--
-- Name: learning_reports learning_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.learning_reports
    ADD CONSTRAINT learning_reports_pkey PRIMARY KEY (id);


--
-- Name: live_events live_events_event_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.live_events
    ADD CONSTRAINT live_events_event_id_key UNIQUE (event_id);


--
-- Name: live_events live_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.live_events
    ADD CONSTRAINT live_events_pkey PRIMARY KEY (id);


--
-- Name: live_trades live_trades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.live_trades
    ADD CONSTRAINT live_trades_pkey PRIMARY KEY (id);


--
-- Name: metar_readings metar_readings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metar_readings
    ADD CONSTRAINT metar_readings_pkey PRIMARY KEY (id);


--
-- Name: metar_readings metar_readings_station_icao_observation_time_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metar_readings
    ADD CONSTRAINT metar_readings_station_icao_observation_time_key UNIQUE (station_icao, observation_time);


--
-- Name: noaa_forecasts noaa_forecasts_city_forecast_date_source_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.noaa_forecasts
    ADD CONSTRAINT noaa_forecasts_city_forecast_date_source_key UNIQUE (city, forecast_date, source);


--
-- Name: noaa_forecasts noaa_forecasts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.noaa_forecasts
    ADD CONSTRAINT noaa_forecasts_pkey PRIMARY KEY (id);


--
-- Name: paper_trades_live paper_trades_live_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_trades_live
    ADD CONSTRAINT paper_trades_live_pkey PRIMARY KEY (id);


--
-- Name: penny_positions penny_positions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.penny_positions
    ADD CONSTRAINT penny_positions_pkey PRIMARY KEY (id);


--
-- Name: positions positions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_pkey PRIMARY KEY (id);


--
-- Name: signals signals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_pkey PRIMARY KEY (id);


--
-- Name: sports_markets sports_markets_market_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sports_markets
    ADD CONSTRAINT sports_markets_market_id_key UNIQUE (market_id);


--
-- Name: sports_markets sports_markets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sports_markets
    ADD CONSTRAINT sports_markets_pkey PRIMARY KEY (id);


--
-- Name: sports_signals sports_signals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sports_signals
    ADD CONSTRAINT sports_signals_pkey PRIMARY KEY (id);


--
-- Name: sportsbook_odds sportsbook_odds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sportsbook_odds
    ADD CONSTRAINT sportsbook_odds_pkey PRIMARY KEY (id);


--
-- Name: station_accuracy station_accuracy_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.station_accuracy
    ADD CONSTRAINT station_accuracy_pkey PRIMARY KEY (station_icao);


--
-- Name: strategy_performance strategy_performance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_performance
    ADD CONSTRAINT strategy_performance_pkey PRIMARY KEY (id);


--
-- Name: taf_forecasts taf_forecasts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.taf_forecasts
    ADD CONSTRAINT taf_forecasts_pkey PRIMARY KEY (id);


--
-- Name: taf_forecasts taf_forecasts_station_icao_issue_time_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.taf_forecasts
    ADD CONSTRAINT taf_forecasts_station_icao_issue_time_key UNIQUE (station_icao, issue_time);


--
-- Name: telegram_subscribers telegram_subscribers_chat_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_subscribers
    ADD CONSTRAINT telegram_subscribers_chat_id_key UNIQUE (chat_id);


--
-- Name: telegram_subscribers telegram_subscribers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_subscribers
    ADD CONSTRAINT telegram_subscribers_pkey PRIMARY KEY (id);


--
-- Name: temperature_trends temperature_trends_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.temperature_trends
    ADD CONSTRAINT temperature_trends_pkey PRIMARY KEY (id);


--
-- Name: temperature_trends temperature_trends_station_icao_calculated_at_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.temperature_trends
    ADD CONSTRAINT temperature_trends_station_icao_calculated_at_key UNIQUE (station_icao, calculated_at);


--
-- Name: trade_learnings trade_learnings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade_learnings
    ADD CONSTRAINT trade_learnings_pkey PRIMARY KEY (id);


--
-- Name: trades trades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_pkey PRIMARY KEY (id);


--
-- Name: weather_markets weather_markets_market_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_markets
    ADD CONSTRAINT weather_markets_market_id_key UNIQUE (market_id);


--
-- Name: weather_markets weather_markets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_markets
    ADD CONSTRAINT weather_markets_pkey PRIMARY KEY (id);


--
-- Name: idx_btc_signals_window; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_btc_signals_window ON public.btc_signals USING btree (window_id);


--
-- Name: idx_btc_windows_close; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_btc_windows_close ON public.btc_windows USING btree (close_time);


--
-- Name: idx_leader_copy_positions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_leader_copy_positions_status ON public.leader_copy_positions USING btree (status, opened_at DESC);


--
-- Name: idx_leader_performance_wallet; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_leader_performance_wallet ON public.leader_performance USING btree (wallet, date DESC);


--
-- Name: idx_leader_trades_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_leader_trades_status ON public.leader_trades USING btree (status, detected_at DESC);


--
-- Name: idx_leader_trades_wallet; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_leader_trades_wallet ON public.leader_trades USING btree (wallet, detected_at DESC);


--
-- Name: idx_learning_reports_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_learning_reports_type ON public.learning_reports USING btree (report_type, created_at DESC);


--
-- Name: idx_live_events_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_live_events_status ON public.live_events USING btree (status, sport);


--
-- Name: idx_metar_station_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metar_station_time ON public.metar_readings USING btree (station_icao, observation_time DESC);


--
-- Name: idx_penny_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_penny_status ON public.penny_positions USING btree (status);


--
-- Name: idx_sports_markets_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sports_markets_group_id ON public.sports_markets USING btree (group_id) WHERE (is_active = true);


--
-- Name: idx_sports_signals_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sports_signals_created ON public.sports_signals USING btree (created_at DESC);


--
-- Name: idx_strat_perf_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_strat_perf_unique ON public.strategy_performance USING btree (strategy, sport, period_start);


--
-- Name: idx_taf_station_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_taf_station_time ON public.taf_forecasts USING btree (station_icao, issue_time DESC);


--
-- Name: idx_telegram_subscribers_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_telegram_subscribers_active ON public.telegram_subscribers USING btree (is_active);


--
-- Name: idx_telegram_subscribers_chat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_telegram_subscribers_chat_id ON public.telegram_subscribers USING btree (chat_id);


--
-- Name: idx_trade_learnings_bucket; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trade_learnings_bucket ON public.trade_learnings USING btree (edge_bucket);


--
-- Name: idx_trade_learnings_sport; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trade_learnings_sport ON public.trade_learnings USING btree (sport, created_at DESC);


--
-- Name: idx_trade_learnings_strategy; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trade_learnings_strategy ON public.trade_learnings USING btree (strategy, created_at DESC);


--
-- Name: idx_trends_station_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trends_station_time ON public.temperature_trends USING btree (station_icao, calculated_at DESC);


--
-- Name: btc_signals btc_signals_window_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.btc_signals
    ADD CONSTRAINT btc_signals_window_id_fkey FOREIGN KEY (window_id) REFERENCES public.btc_windows(window_id);


--
-- Name: leader_copy_positions leader_copy_positions_leader_trade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leader_copy_positions
    ADD CONSTRAINT leader_copy_positions_leader_trade_id_fkey FOREIGN KEY (leader_trade_id) REFERENCES public.leader_trades(id);


--
-- Name: trades trades_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id);


--
-- PostgreSQL database dump complete
--

\unrestrict 4tlW7O9rPRmOAfbcKtW47Km2F2zBXVnSmHy5FvhtoajQ3dZI18NBQjg0o537REd

