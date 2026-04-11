# SCHEMA.md — Live Database Schema
**Auto-generated:** 2026-04-11 19:16 IST
**Database:** polyedge

⚠️ **AGENTS: READ THIS BEFORE WRITING ANY SQL QUERY.**
Do NOT guess table/column names. Use ONLY what's listed here.

## backtest_results (0 rows)
```
                                        Table "public.backtest_results"
    Column     |           Type           | Collation | Nullable |                   Default                    
 id            | integer                  |           | not null | nextval('backtest_results_id_seq'::regclass)
 strategy      | character varying(100)   |           |          | 
 sport         | character varying(50)    |           |          | 
 match_name    | text                     |           |          | 
 team_backed   | character varying(200)   |           |          | 
 entry_price   | numeric                  |           |          | 
 fair_value    | numeric                  |           |          | 
 edge_pct      | numeric                  |           |          | 
 position_size | numeric                  |           |          | 
 outcome       | character varying(20)    |           |          | 
 pnl           | numeric                  |           |          | 
 books_used    | text                     |           |          | 
 match_date    | timestamp with time zone |           |          | 
 created_at    | timestamp with time zone |           |          | now()
    "backtest_results_pkey" PRIMARY KEY, btree (id)
```

## bankroll (1 rows)
```
                                           Table "public.bankroll"
      Column      |            Type             | Collation | Nullable |               Default                
 id               | integer                     |           | not null | nextval('bankroll_id_seq'::regclass)
 timestamp        | timestamp without time zone |           |          | now()
 total_usd        | numeric(12,2)               |           |          | 
 available_usd    | numeric(12,2)               |           |          | 
 in_positions_usd | numeric(12,2)               |           |          | 
 daily_pnl        | numeric(10,2)               |           |          | 
    "bankroll_pkey" PRIMARY KEY, btree (id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 1,
    "timestamp": "2026-04-07T02:59:44.895009",
    "total_usd": 0.0,
    "available_usd": 0.0,
    "in_positions_usd": 0.0,
    "daily_pnl": 0.0
}
```
</details>

## bot_settings (7 rows)
```
                        Table "public.bot_settings"
   Column   |            Type             | Collation | Nullable | Default 
 key        | text                        |           | not null | 
 value      | jsonb                       |           | not null | 
 updated_at | timestamp without time zone |           |          | now()
    "bot_settings_pkey" PRIMARY KEY, btree (key)
```
<details><summary>Sample row</summary>

```json
{
    "key": "recommended_min_edge",
    "value": 7,
    "updated_at": "2026-04-08T20:30:11.013836"
}
```
</details>

## btc_bankroll (1 rows)
```
                                          Table "public.btc_bankroll"
      Column      |           Type           | Collation | Nullable |                 Default                  
 id               | integer                  |           | not null | nextval('btc_bankroll_id_seq'::regclass)
 balance          | numeric(12,2)            |           | not null | 
 available        | numeric(12,2)            |           | not null | 
 in_positions     | numeric(12,2)            |           |          | 0
 total_won        | numeric(12,2)            |           |          | 0
 total_lost       | numeric(12,2)            |           |          | 0
 total_trades     | integer                  |           |          | 0
 peak_balance     | numeric(12,2)            |           |          | 
 max_drawdown_pct | numeric(6,2)             |           |          | 0
 updated_at       | timestamp with time zone |           |          | now()
    "btc_bankroll_pkey" PRIMARY KEY, btree (id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 1,
    "balance": 0.0,
    "available": 0.0,
    "in_positions": 0.0,
    "total_won": 0.0,
    "total_lost": 0.0,
    "total_trades": 0,
    "peak_balance": 0.0,
    "max_drawdown_pct": 0.0,
    "updated_at": "2026-04-11T19:15:33.483111+05:30"
}
```
</details>

## btc_calibration (0 rows)
```
                                              Table "public.btc_calibration"
          Column          |           Type           | Collation | Nullable |                   Default                   
 id                       | integer                  |           | not null | nextval('btc_calibration_id_seq'::regclass)
 date                     | date                     |           | not null | 
 window_length            | integer                  |           | not null | 
 factor_weights           | jsonb                    |           | not null | 
 accuracy_overall         | numeric(6,4)             |           |          | 
 accuracy_high_conviction | numeric(6,4)             |           |          | 
 accuracy_by_bucket       | jsonb                    |           |          | 
 windows_analyzed         | integer                  |           |          | 
 created_at               | timestamp with time zone |           |          | now()
    "btc_calibration_pkey" PRIMARY KEY, btree (id)
```

## btc_intelligence_log (0 rows)
```
                                          Table "public.btc_intelligence_log"
      Column      |           Type           | Collation | Nullable |                     Default                      
 id               | integer                  |           | not null | nextval('btc_intelligence_log_id_seq'::regclass)
 date             | date                     |           | not null | 
 strategy_version | text                     |           | not null | 
 trades_taken     | integer                  |           |          | 0
 trades_won       | integer                  |           |          | 0
 net_pnl          | numeric(12,2)            |           |          | 0
 gross_profit     | numeric(12,2)            |           |          | 0
 gross_loss       | numeric(12,2)            |           |          | 0
 best_trade       | numeric(12,2)            |           |          | 0
 avg_entry        | numeric(6,4)             |           |          | 0
 avg_rr           | numeric(6,2)             |           |          | 0
 best_hour        | integer                  |           |          | 
 worst_hour       | integer                  |           |          | 
 best_hour_pnl    | numeric(12,2)            |           |          | 
 worst_hour_pnl   | numeric(12,2)            |           |          | 
 volatility_data  | jsonb                    |           |          | 
 verdict          | text                     |           |          | 
 action_taken     | text                     |           |          | 
 next_strategy    | text                     |           |          | 
 learnings        | text                     |           |          | 
 full_analysis    | jsonb                    |           |          | 
 created_at       | timestamp with time zone |           |          | now()
    "btc_intelligence_log_pkey" PRIMARY KEY, btree (id)
    "btc_intelligence_log_date_key" UNIQUE CONSTRAINT, btree (date)
```

## btc_pnl (285 rows)
```
                           View "public.btc_pnl"
    Column     |           Type           | Collation | Nullable | Default 
 window_id     | text                     |           |          | 
 prediction    | text                     |           |          | 
 resolution    | text                     |           |          | 
 window_length | integer                  |           |          | 
 close_time    | timestamp with time zone |           |          | 
 correct       | boolean                  |           |          | 
 entry_price   | numeric(6,4)             |           |          | 
 stake         | numeric                  |           |          | 
 trade_pnl     | numeric                  |           |          | 
```
<details><summary>Sample row</summary>

```json
{
    "window_id": "btc-updown-15m-1775748600",
    "prediction": "UP",
    "resolution": "UP",
    "window_length": 15,
    "close_time": "2026-04-09T21:15:00+05:30",
    "correct": true,
    "entry_price": 0.985,
    "stake": 25.0,
    "trade_pnl": 0.3730964467005077
}
```
</details>

## btc_signals (29592 rows)
```
                                           Table "public.btc_signals"
       Column       |           Type           | Collation | Nullable |                 Default                 
 id                 | integer                  |           | not null | nextval('btc_signals_id_seq'::regclass)
 window_id          | text                     |           |          | 
 signal_ts          | timestamp with time zone |           |          | now()
 seconds_remaining  | integer                  |           |          | 
 f_price_delta      | numeric(8,6)             |           |          | 
 f_momentum         | numeric(8,6)             |           |          | 
 f_volume_imbalance | numeric(8,6)             |           |          | 
 f_oracle_lead      | numeric(8,6)             |           |          | 
 f_book_imbalance   | numeric(8,6)             |           |          | 
 f_volatility       | numeric(8,6)             |           |          | 
 f_time_decay       | numeric(8,6)             |           |          | 
 prob_up            | numeric(6,4)             |           | not null | 
 prediction         | text                     |           | not null | 
 confidence         | numeric(6,4)             |           |          | 
 skip_reason        | text                     |           |          | 
 weights_used       | jsonb                    |           |          | 
 was_correct        | boolean                  |           |          | 
 created_at         | timestamp with time zone |           |          | now()
 stake_used         | numeric(10,2)            |           |          | 
    "btc_signals_pkey" PRIMARY KEY, btree (id)
    "idx_btc_signals_window" btree (window_id)
    "btc_signals_window_id_fkey" FOREIGN KEY (window_id) REFERENCES btc_windows(window_id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 2,
    "window_id": "btc-updown-5m-1775691300",
    "signal_ts": "2026-04-09T05:09:23.494991+05:30",
    "seconds_remaining": 37,
    "f_price_delta": 0.397157,
    "f_momentum": -0.017181,
    "f_volume_imbalance": -0.900766,
    "f_oracle_lead": 0.150045,
    "f_book_imbalance": -0.36,
    "f_volatility": 1.0,
    "f_time_decay": 0.876667,
    "prob_up": 0.4731,
    "prediction": "SKIP",
    "confidence": 0.3753,
    "skip_reason": "Low conviction (prob_up between 0.45-0.55)",
    "weights_used": {
        "momentum": 0.22,
        "time_decay": 0.02,
        "volatility": 0.05,
        "oracle_lead": 0.08,
        "price_delta": 0.38,
        "book_imbalance": 0.1,
        "volume_imbalance": 0.15
    },
    "was_correct": null,
    "created_at": "2026-04-09T05:09:23.494991+05:30",
    "stake_used": null
}
```
</details>

## btc_strategy_versions (5 rows)
```
                                            Table "public.btc_strategy_versions"
        Column        |           Type           | Collation | Nullable |                      Default                      
 id                   | integer                  |           | not null | nextval('btc_strategy_versions_id_seq'::regclass)
 version              | text                     |           | not null | 
 status               | text                     |           |          | 'active'::text
 max_entry            | numeric(6,4)             |           | not null | 
 min_rr               | numeric(6,2)             |           | not null | 
 min_factors          | integer                  |           | not null | 
 window_lengths       | integer[]                |           | not null | 
 stakes               | jsonb                    |           | not null | 
 extra_rules          | jsonb                    |           |          | 
 activated_at         | timestamp with time zone |           |          | now()
 deactivated_at       | timestamp with time zone |           |          | 
 created_by           | text                     |           |          | 'intelligence_loop'::text
 notes                | text                     |           |          | 
 parent_version       | text                     |           |          | 
 performance_snapshot | jsonb                    |           |          | 
 revert_reason        | text                     |           |          | 
    "btc_strategy_versions_pkey" PRIMARY KEY, btree (id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 2,
    "version": "V1",
    "status": "superseded",
    "max_entry": 1.0,
    "min_rr": 0.0,
    "min_factors": 0,
    "window_lengths": [
        5,
        15
    ],
    "stakes": {
        "all": 25
    },
    "extra_rules": null,
    "activated_at": "2026-04-09T05:00:00+05:30",
    "deactivated_at": "2026-04-09T12:36:00+05:30",
    "created_by": "intelligence_loop",
    "notes": "No filters. 118 trades, -$202.",
    "parent_version": null,
    "performance_snapshot": null,
    "revert_reason": null
}
```
</details>

## btc_volatility_hours (0 rows)
```
                                           Table "public.btc_volatility_hours"
       Column        |           Type           | Collation | Nullable |                     Default                      
 id                  | integer                  |           | not null | nextval('btc_volatility_hours_id_seq'::regclass)
 date                | date                     |           | not null | 
 hour_ist            | integer                  |           | not null | 
 window_length       | integer                  |           | not null | 5
 trades_taken        | integer                  |           |          | 0
 trades_won          | integer                  |           |          | 0
 trades_lost         | integer                  |           |          | 0
 net_pnl             | numeric(12,2)            |           |          | 0
 avg_entry           | numeric(6,4)             |           |          | 0
 btc_price_range_pct | numeric(8,4)             |           |          | 0
 best_trade          | numeric(12,2)            |           |          | 0
 session_tag         | text                     |           |          | 'v2'::text
 created_at          | timestamp with time zone |           |          | now()
    "btc_volatility_hours_pkey" PRIMARY KEY, btree (id)
    "btc_volatility_hours_date_hour_ist_window_length_key" UNIQUE CONSTRAINT, btree (date, hour_ist, window_length)
```

## btc_windows (968 rows)
```
                                        Table "public.btc_windows"
    Column     |           Type           | Collation | Nullable |                 Default                 
 id            | integer                  |           | not null | nextval('btc_windows_id_seq'::regclass)
 window_id     | text                     |           | not null | 
 window_length | integer                  |           | not null | 
 open_time     | timestamp with time zone |           | not null | 
 close_time    | timestamp with time zone |           | not null | 
 btc_open      | numeric(12,2)            |           |          | 
 btc_close     | numeric(12,2)            |           |          | 
 up_price      | numeric(6,4)             |           |          | 
 down_price    | numeric(6,4)             |           |          | 
 resolution    | text                     |           |          | 
 volume_usd    | numeric(18,2)            |           |          | 
 created_at    | timestamp with time zone |           |          | now()
 token_id_up   | text                     |           |          | 
 token_id_down | text                     |           |          | 
    "btc_windows_pkey" PRIMARY KEY, btree (id)
    "btc_windows_window_id_key" UNIQUE CONSTRAINT, btree (window_id)
    "idx_btc_windows_close" btree (close_time)
    TABLE "btc_signals" CONSTRAINT "btc_signals_window_id_fkey" FOREIGN KEY (window_id) REFERENCES btc_windows(window_id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 182,
    "window_id": "btc-updown-15m-1775693700",
    "window_length": 15,
    "open_time": "2026-04-09T05:45:00+05:30",
    "close_time": "2026-04-09T06:00:00+05:30",
    "btc_open": 71069.93,
    "btc_close": 70800.34,
    "up_price": 0.0,
    "down_price": 1.0,
    "resolution": "DOWN",
    "volume_usd": 53473.23,
    "created_at": "2026-04-09T05:30:08.523299+05:30",
    "token_id_up": null,
    "token_id_down": null
}
```
</details>

## invite_codes (0 rows)
```
                                       Table "public.invite_codes"
   Column   |           Type           | Collation | Nullable |                 Default                  
 id         | integer                  |           | not null | nextval('invite_codes_id_seq'::regclass)
 code       | character varying(20)    |           | not null | 
 created_by | bigint                   |           |          | 
 used_by    | bigint                   |           |          | 
 used_at    | timestamp with time zone |           |          | 
 is_used    | boolean                  |           |          | false
 created_at | timestamp with time zone |           |          | now()
    "invite_codes_pkey" PRIMARY KEY, btree (id)
    "invite_codes_code_key" UNIQUE CONSTRAINT, btree (code)
```

## jc_bankroll (1 rows)
```
                                          Table "public.jc_bankroll"
      Column      |           Type           | Collation | Nullable |                 Default                 
 id               | integer                  |           | not null | nextval('jc_bankroll_id_seq'::regclass)
 balance          | numeric(12,2)            |           | not null | 10000
 available        | numeric(12,2)            |           | not null | 10000
 in_positions     | numeric(12,2)            |           |          | 0
 total_won        | numeric(12,2)            |           |          | 0
 total_lost       | numeric(12,2)            |           |          | 0
 total_trades     | integer                  |           |          | 0
 peak_balance     | numeric(12,2)            |           |          | 10000
 max_drawdown_pct | numeric(6,2)             |           |          | 0
 updated_at       | timestamp with time zone |           |          | now()
    "jc_bankroll_pkey" PRIMARY KEY, btree (id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 1,
    "balance": 10000.0,
    "available": 9827.87,
    "in_positions": 172.13,
    "total_won": 0.0,
    "total_lost": 0.0,
    "total_trades": 0,
    "peak_balance": 10000.0,
    "max_drawdown_pct": 0.0,
    "updated_at": "2026-04-11T19:16:11.587479+05:30"
}
```
</details>

## jc_levels (11 rows)
```
                                       Table "public.jc_levels"
   Column   |           Type           | Collation | Nullable |                Default                
 id         | integer                  |           | not null | nextval('jc_levels_id_seq'::regclass)
 price      | numeric(12,2)            |           | not null | 
 label      | text                     |           | not null | 
 level_type | text                     |           | not null | 
 color      | text                     |           |          | 
 active     | boolean                  |           |          | true
 source     | text                     |           |          | 'chart_cdp'::text
 updated_at | timestamp with time zone |           |          | now()
    "jc_levels_pkey" PRIMARY KEY, btree (id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 1,
    "price": 75905.0,
    "label": "SPV? (stop sweep zone)",
    "level_type": "resistance",
    "color": "#ff3366",
    "active": true,
    "source": "chart_cdp",
    "updated_at": "2026-04-10T06:18:24.789443+05:30"
}
```
</details>

## jc_manual_actions (0 rows)
```
                                         Table "public.jc_manual_actions"
   Column    |            Type             | Collation | Nullable |                    Default                    
 id          | integer                     |           | not null | nextval('jc_manual_actions_id_seq'::regclass)
 trade_id    | integer                     |           |          | 
 action      | text                        |           | not null | 
 amount      | numeric                     |           |          | 
 mode        | text                        |           |          | 
 executed_at | timestamp without time zone |           |          | now()
 result      | jsonb                       |           |          | 
    "jc_manual_actions_pkey" PRIMARY KEY, btree (id)
```

## jc_settings (14 rows)
```
                       Table "public.jc_settings"
   Column   |           Type           | Collation | Nullable | Default 
 key        | text                     |           | not null | 
 value      | text                     |           | not null | 
 updated_at | timestamp with time zone |           |          | now()
    "jc_settings_pkey" PRIMARY KEY, btree (key)
```
<details><summary>Sample row</summary>

```json
{
    "key": "stake_pct",
    "value": "0.03",
    "updated_at": "2026-04-10T06:26:03.730063+05:30"
}
```
</details>

## jc_trades (2 rows)
```
                                           Table "public.jc_trades"
       Column        |           Type           | Collation | Nullable |                Default                
 id                  | integer                  |           | not null | nextval('jc_trades_id_seq'::regclass)
 signal_source       | text                     |           |          | 'jayson_discord'::text
 direction           | text                     |           | not null | 
 entry_price         | numeric(12,2)            |           | not null | 
 stop_loss           | numeric(12,2)            |           |          | 
 take_profit_1       | numeric(12,2)            |           |          | 
 take_profit_2       | numeric(12,2)            |           |          | 
 risk_reward         | numeric(6,2)             |           |          | 
 stake_usd           | numeric(10,2)            |           |          | 100
 leverage            | integer                  |           |          | 30
 status              | text                     |           |          | 'pending'::text
 entry_reason        | text                     |           |          | 
 close_reason        | text                     |           |          | 
 entry_fill_price    | numeric(12,2)            |           |          | 
 exit_fill_price     | numeric(12,2)            |           |          | 
 realized_pnl        | numeric(12,2)            |           |          | 
 unrealized_pnl      | numeric(12,2)            |           |          | 
 btc_price_at_signal | numeric(12,2)            |           |          | 
 half_closed_at      | numeric(12,2)            |           |          | 
 breakeven_set_at    | timestamp with time zone |           |          | 
 opened_at           | timestamp with time zone |           |          | now()
 closed_at           | timestamp with time zone |           |          | 
 signal_message      | text                     |           |          | 
 metadata            | jsonb                    |           |          | 
 original_stop_loss  | numeric(12,2)            |           |          | 
 original_tp1        | numeric(12,2)            |           |          | 
 original_tp2        | numeric(12,2)            |           |          | 
 manual_override     | boolean                  |           |          | false
 risk_amount         | numeric(12,2)            |           |          | 
 bybit_order_id      | text                     |           |          | 
 is_live             | boolean                  |           |          | false
 daily_loss_at_entry | numeric(10,2)            |           |          | 
    "jc_trades_pkey" PRIMARY KEY, btree (id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 3,
    "signal_source": "jayson_discord",
    "direction": "LONG",
    "entry_price": 72923.77,
    "stop_loss": 71465.29,
    "take_profit_1": 75111.48,
    "take_profit_2": 76569.96,
    "risk_reward": 1.5,
    "stake_usd": 300.0,
    "leverage": 10,
    "status": "closed",
    "entry_reason": "TEST nwPOC @ $72924",
    "close_reason": "TEST_CLEANUP",
    "entry_fill_price": 72923.77,
    "exit_fill_price": null,
    "realized_pnl": null,
    "unrealized_pnl": null,
    "btc_price_at_signal": 72923.77,
    "half_closed_at": null,
    "breakeven_set_at": null,
    "opened_at": "2026-04-11T05:15:30.424591+05:30",
    "closed_at": "2026-04-11T05:17:19.688338+05:30",
    "signal_message": null,
    "metadata": null,
    "original_stop_loss": null,
    "original_tp1": null,
    "original_tp2": null,
    "manual_override": false,
    "risk_amount": 63.3,
```
</details>

## late_window_stats (0 rows)
```
                                         Table "public.late_window_stats"
     Column      |           Type           | Collation | Nullable |                    Default                    
 id              | integer                  |           | not null | nextval('late_window_stats_id_seq'::regclass)
 stat_date       | date                     |           |          | CURRENT_DATE
 trades_total    | integer                  |           |          | 0
 trades_won      | integer                  |           |          | 0
 trades_lost     | integer                  |           |          | 0
 total_pnl       | numeric(10,2)            |           |          | 0
 avg_entry_price | numeric(8,4)             |           |          | 
 updated_at      | timestamp with time zone |           |          | now()
    "late_window_stats_pkey" PRIMARY KEY, btree (id)
    "late_window_stats_stat_date_key" UNIQUE CONSTRAINT, btree (stat_date)
```

## late_window_trades (0 rows)
```
                                          Table "public.late_window_trades"
      Column       |           Type           | Collation | Nullable |                    Default                     
 id                | integer                  |           | not null | nextval('late_window_trades_id_seq'::regclass)
 window_epoch      | bigint                   |           |          | 
 window_length     | integer                  |           |          | 5
 direction         | text                     |           |          | 
 entry_price       | numeric(8,4)             |           |          | 
 exit_price        | numeric(8,4)             |           |          | 
 stake_usd         | numeric(10,2)            |           |          | 
 pnl_usd           | numeric(10,2)            |           |          | 
 btc_open_price    | numeric(12,2)            |           |          | 
 btc_close_price   | numeric(12,2)            |           |          | 
 btc_current_price | numeric(12,2)            |           |          | 
 seconds_remaining | integer                  |           |          | 
 oracle_price      | numeric(12,2)            |           |          | 
 binance_price     | numeric(12,2)            |           |          | 
 outcome           | text                     |           |          | 'pending'::text
 traded_at         | timestamp with time zone |           |          | now()
 resolved_at       | timestamp with time zone |           |          | 
    "late_window_trades_pkey" PRIMARY KEY, btree (id)
```

## leader_copy_positions (0 rows)
```
                                           Table "public.leader_copy_positions"
     Column      |            Type             | Collation | Nullable |                      Default                      
 id              | integer                     |           | not null | nextval('leader_copy_positions_id_seq'::regclass)
 leader_trade_id | integer                     |           |          | 
 condition_id    | text                        |           | not null | 
 market_title    | text                        |           |          | 
 our_entry_price | real                        |           |          | 
 our_size        | real                        |           |          | 
 outcome_index   | integer                     |           |          | 
 status          | text                        |           |          | 'open'::text
 pnl             | real                        |           |          | 0
 opened_at       | timestamp without time zone |           |          | now()
 closed_at       | timestamp without time zone |           |          | 
    "leader_copy_positions_pkey" PRIMARY KEY, btree (id)
    "idx_leader_copy_positions_status" btree (status, opened_at DESC)
    "leader_copy_positions_leader_trade_id_fkey" FOREIGN KEY (leader_trade_id) REFERENCES leader_trades(id)
```

## leader_performance (1 rows)
```
                                 Table "public.leader_performance"
     Column      |  Type   | Collation | Nullable |                    Default                     
 id              | integer |           | not null | nextval('leader_performance_id_seq'::regclass)
 wallet          | text    |           | not null | 
 date            | date    |           | not null | 
 trades_count    | integer |           |          | 0
 volume          | real    |           |          | 0
 pnl             | real    |           |          | 0
 win_count       | integer |           |          | 0
 loss_count      | integer |           |          | 0
 avg_entry_price | real    |           |          | 0
    "leader_performance_pkey" PRIMARY KEY, btree (id)
    "idx_leader_performance_wallet" btree (wallet, date DESC)
    "leader_performance_wallet_date_key" UNIQUE CONSTRAINT, btree (wallet, date)
```
<details><summary>Sample row</summary>

```json
{
    "id": 1,
    "wallet": "0x492442eab586f242b53bda933fd5de859c8a3782",
    "date": "2026-04-11",
    "trades_count": 17,
    "volume": 157708.64,
    "pnl": 0,
    "win_count": 0,
    "loss_count": 0,
    "avg_entry_price": 0.45
}
```
</details>

## leader_trades (17 rows)
```
                                              Table "public.leader_trades"
        Column         |            Type             | Collation | Nullable |                  Default                  
 id                    | integer                     |           | not null | nextval('leader_trades_id_seq'::regclass)
 wallet                | text                        |           | not null | 
 condition_id          | text                        |           | not null | 
 market_slug           | text                        |           |          | 
 market_title          | text                        |           |          | 
 trade_type            | text                        |           |          | 
 sport                 | text                        |           |          | 
 side                  | text                        |           |          | 
 outcome_index         | integer                     |           |          | 
 leader_price          | real                        |           |          | 
 leader_size           | real                        |           |          | 
 leader_total_position | real                        |           |          | 0
 our_size              | real                        |           |          | 0
 our_price             | real                        |           |          | 0
 status                | text                        |           |          | 'detected'::text
 result                | text                        |           |          | 
 pnl                   | real                        |           |          | 0
 detected_at           | timestamp without time zone |           |          | now()
 settled_at            | timestamp without time zone |           |          | 
 polymarket_url        | text                        |           |          | 
    "leader_trades_pkey" PRIMARY KEY, btree (id)
    "idx_leader_trades_status" btree (status, detected_at DESC)
    "idx_leader_trades_wallet" btree (wallet, detected_at DESC)
    "leader_trades_wallet_condition_id_detected_at_key" UNIQUE CONSTRAINT, btree (wallet, condition_id, detected_at)
    TABLE "leader_copy_positions" CONSTRAINT "leader_copy_positions_leader_trade_id_fkey" FOREIGN KEY (leader_trade_id) REFERENCES leader_trades(id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 1,
    "wallet": "0x492442eab586f242b53bda933fd5de859c8a3782",
    "condition_id": "0x404dfb4aa322139bfb1ea55cf1020e309f96722325d95bd172d2e0f013a2add8",
    "market_slug": "nba-orl-chi-2026-04-10-spread-away-14pt5",
    "market_title": "Spread: Magic (-14.5)",
    "trade_type": "SPREAD",
    "sport": "NBA",
    "side": "BUY",
    "outcome_index": 1,
    "leader_price": 0.45,
    "leader_size": 2291.481,
    "leader_total_position": 2291.481,
    "our_size": 1,
    "our_price": 0.45,
    "status": "detected",
    "result": null,
    "pnl": 0,
    "detected_at": "2026-04-11T05:25:41.811524",
    "settled_at": null,
    "polymarket_url": "https://polymarket.com/event/nba-orl-chi-2026-04-10-spread-away-14pt5"
}
```
</details>

## leader_wallets (0 rows)
```
                                         Table "public.leader_wallets"
    Column    |            Type             | Collation | Nullable |                  Default                   
 id           | integer                     |           | not null | nextval('leader_wallets_id_seq'::regclass)
 wallet       | text                        |           | not null | 
 name         | text                        |           | not null | 'Unknown'::text
 active       | boolean                     |           |          | true
 scale_factor | real                        |           |          | 0.00025
 max_position | real                        |           |          | 50.0
 min_edge     | real                        |           |          | 0.0
 created_at   | timestamp without time zone |           |          | now()
    "leader_wallets_pkey" PRIMARY KEY, btree (id)
    "leader_wallets_wallet_key" UNIQUE CONSTRAINT, btree (wallet)
```

## learning_reports (0 rows)
```
                                           Table "public.learning_reports"
     Column      |            Type             | Collation | Nullable |                   Default                    
 id              | integer                     |           | not null | nextval('learning_reports_id_seq'::regclass)
 report_type     | character varying(50)       |           |          | 
 report_data     | jsonb                       |           |          | 
 recommendations | jsonb                       |           |          | 
 status          | character varying(20)       |           |          | 'pending'::character varying
 created_at      | timestamp without time zone |           |          | now()
    "learning_reports_pkey" PRIMARY KEY, btree (id)
    "idx_learning_reports_type" btree (report_type, created_at DESC)
```

## live_events (52 rows)
```
                                          Table "public.live_events"
      Column       |           Type           | Collation | Nullable |                 Default                 
 id                | integer                  |           | not null | nextval('live_events_id_seq'::regclass)
 sport             | character varying(50)    |           |          | 
 event_id          | character varying(255)   |           |          | 
 home_team         | character varying(200)   |           |          | 
 away_team         | character varying(200)   |           |          | 
 home_score        | integer                  |           |          | 0
 away_score        | integer                  |           |          | 0
 status            | character varying(50)    |           |          | 
 minute            | character varying(20)    |           |          | 
 period            | character varying(20)    |           |          | 
 key_events        | jsonb                    |           |          | 
 linked_market_ids | text[]                   |           |          | 
 last_updated      | timestamp with time zone |           |          | now()
    "live_events_pkey" PRIMARY KEY, btree (id)
    "idx_live_events_status" btree (status, sport)
    "live_events_event_id_key" UNIQUE CONSTRAINT, btree (event_id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 140922,
    "sport": "MLB",
    "event_id": "401814883",
    "home_team": "Baltimore Orioles",
    "away_team": "San Francisco Giants",
    "home_score": 3,
    "away_score": 6,
    "status": "post",
    "minute": "0:00",
    "period": "9",
    "key_events": null,
    "linked_market_ids": [],
    "last_updated": "2026-04-11T19:15:48.230639+05:30"
}
```
</details>

## live_trades (2 rows)
```
                                            Table "public.live_trades"
        Column         |           Type           | Collation | Nullable |                 Default                 
 id                    | integer                  |           | not null | nextval('live_trades_id_seq'::regclass)
 window_id             | text                     |           |          | 
 prediction            | text                     |           |          | 
 token_id              | text                     |           |          | 
 side                  | text                     |           |          | 
 entry_price           | numeric                  |           |          | 
 stake_usd             | numeric                  |           |          | 
 tx_hash               | text                     |           |          | 
 status                | text                     |           |          | 'pending'::text
 exit_price            | numeric                  |           |          | 
 pnl_usd               | numeric                  |           |          | 
 wallet_balance_before | numeric                  |           |          | 
 wallet_balance_after  | numeric                  |           |          | 
 created_at            | timestamp with time zone |           |          | now()
 resolved_at           | timestamp with time zone |           |          | 
    "live_trades_pkey" PRIMARY KEY, btree (id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 1,
    "window_id": "btc-updown-5m-1775854500",
    "prediction": "DOWN",
    "token_id": "72797279821996995864732017843551069865515207350805743953675390578338354563465",
    "side": "BUY",
    "entry_price": 0.065,
    "stake_usd": 25,
    "tx_hash": "FAILED: PolyApiException[status_code=400, error_message={'error': 'not enough balance / allowance: the balan",
    "status": "failed",
    "exit_price": null,
    "pnl_usd": null,
    "wallet_balance_before": 998.273135,
    "wallet_balance_after": null,
    "created_at": "2026-04-11T02:30:09.268561+05:30",
    "resolved_at": null
}
```
</details>

## maker_daily_pnl (0 rows)
```
                         Table "public.maker_daily_pnl"
    Column     |           Type           | Collation | Nullable |   Default    
 date          | date                     |           | not null | CURRENT_DATE
 gross_pnl     | numeric(10,2)            |           |          | 0
 trades_filled | integer                  |           |          | 0
 updated_at    | timestamp with time zone |           |          | now()
    "maker_daily_pnl_pkey" PRIMARY KEY, btree (date)
```

## maker_orders (1612 rows)
```
                                       Table "public.maker_orders"
   Column    |           Type           | Collation | Nullable |                 Default                  
 id          | integer                  |           | not null | nextval('maker_orders_id_seq'::regclass)
 window_id   | text                     |           | not null | 
 order_id    | text                     |           | not null | 
 side        | text                     |           | not null | 
 token_id    | text                     |           | not null | 
 price       | numeric(6,4)             |           |          | 
 size        | numeric(10,2)            |           |          | 
 status      | text                     |           |          | 'open'::text
 filled_size | numeric(10,2)            |           |          | 0
 pnl_usd     | numeric(10,2)            |           |          | 
 created_at  | timestamp with time zone |           |          | now()
 updated_at  | timestamp with time zone |           |          | now()
    "maker_orders_pkey" PRIMARY KEY, btree (id)
    "idx_maker_orders_status" btree (status)
    "idx_maker_orders_window" btree (window_id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 555,
    "window_id": "btc-updown-5m-1775866500",
    "order_id": "0xbe0f1cc3e9d6b3249ecd0c6aa7ee894c6bf8920707c805abc25e90cfc89b9012",
    "side": "BUY_UP",
    "token_id": "110067921834261600242796166514542910181319709879252918482190525591750693754398",
    "price": 0.0643,
    "size": 20.0,
    "status": "cancelled",
    "filled_size": 0.0,
    "pnl_usd": null,
    "created_at": "2026-04-11T05:44:00.241362+05:30",
    "updated_at": "2026-04-11T05:44:05.075957+05:30"
}
```
</details>

## metar_readings (45511 rows)
```
                                           Table "public.metar_readings"
      Column      |            Type             | Collation | Nullable |                  Default                   
 id               | integer                     |           | not null | nextval('metar_readings_id_seq'::regclass)
 station_icao     | character varying(4)        |           | not null | 
 observation_time | timestamp without time zone |           | not null | 
 raw_metar        | text                        |           | not null | 
 temperature_c    | double precision            |           |          | 
 dewpoint_c       | double precision            |           |          | 
 wind_speed_kt    | double precision            |           |          | 
 wind_dir         | integer                     |           |          | 
 visibility_m     | double precision            |           |          | 
 pressure_hpa     | double precision            |           |          | 
 cloud_cover      | character varying(50)       |           |          | 
 created_at       | timestamp without time zone |           |          | now()
    "metar_readings_pkey" PRIMARY KEY, btree (id)
    "idx_metar_station_time" btree (station_icao, observation_time DESC)
    "metar_readings_station_icao_observation_time_key" UNIQUE CONSTRAINT, btree (station_icao, observation_time)
```
<details><summary>Sample row</summary>

```json
{
    "id": 2,
    "station_icao": "CYYZ",
    "observation_time": "2026-04-06T10:59:01.496823",
    "raw_metar": "METAR CYYZ 061000Z 27009KT 15SM OVC042 01/M04 A3005 RMK SC8 SLP184",
    "temperature_c": 1,
    "dewpoint_c": -4,
    "wind_speed_kt": 9,
    "wind_dir": 270,
    "visibility_m": 24140.1,
    "pressure_hpa": 34463.29103,
    "cloud_cover": "OVERCAST",
    "created_at": "2026-04-06T16:29:01.502972"
}
```
</details>

## noaa_forecasts (20 rows)
```
                                        Table "public.noaa_forecasts"
    Column     |           Type           | Collation | Nullable |                  Default                   
 id            | integer                  |           | not null | nextval('noaa_forecasts_id_seq'::regclass)
 city          | character varying(100)   |           | not null | 
 station_icao  | character varying(10)    |           |          | 
 forecast_date | date                     |           | not null | 
 high_c        | numeric                  |           |          | 
 low_c         | numeric                  |           |          | 
 high_f        | numeric                  |           |          | 
 low_f         | numeric                  |           |          | 
 confidence    | numeric                  |           |          | 
 source        | character varying(50)    |           |          | 'noaa_gfs'::character varying
 raw_data      | jsonb                    |           |          | 
 fetched_at    | timestamp with time zone |           |          | now()
    "noaa_forecasts_pkey" PRIMARY KEY, btree (id)
    "noaa_forecasts_city_forecast_date_source_key" UNIQUE CONSTRAINT, btree (city, forecast_date, source)
```
<details><summary>Sample row</summary>

```json
{
    "id": 1,
    "city": "NYC",
    "station_icao": null,
    "forecast_date": "2026-04-06",
    "high_c": 13.9,
    "low_c": null,
    "high_f": 57,
    "low_f": null,
    "confidence": 0.85,
    "source": "noaa_today",
    "raw_data": {
        "city": "NYC",
        "wind_speed": "14 mph",
        "period_name": "Today",
        "temperature_c": 13.9,
        "temperature_f": 57,
        "short_forecast": "Mostly Sunny",
        "wind_direction": "W",
        "detailed_forecast": "Mostly sunny. High near 57, with temperatures falling to around 55 in the afternoon. West wind around 14 mph, with gusts as high as 25 mph."
    },
    "fetched_at": "2026-04-06T20:47:52.088679+05:30"
}
```
</details>

## paper_trades_live (4 rows)
```
                                         Table "public.paper_trades_live"
     Column      |           Type           | Collation | Nullable |                    Default                    
 id              | integer                  |           | not null | nextval('paper_trades_live_id_seq'::regclass)
 match_name      | text                     |           | not null | 
 sport           | character varying(50)    |           |          | 'IPL'::character varying
 team_backed     | character varying(200)   |           |          | 
 entry_price     | numeric                  |           |          | 
 fair_value      | numeric                  |           |          | 
 edge_pct        | numeric                  |           |          | 
 position_size   | numeric                  |           |          | 
 shares          | numeric                  |           |          | 
 strategy        | character varying(100)   |           |          | 
 books_consensus | text                     |           |          | 
 book_count      | integer                  |           |          | 
 status          | character varying(20)    |           |          | 'open'::character varying
 exit_price      | numeric                  |           |          | 
 pnl             | numeric                  |           |          | 
 match_time      | timestamp with time zone |           |          | 
 entry_at        | timestamp with time zone |           |          | now()
 resolved_at     | timestamp with time zone |           |          | 
 notes           | text                     |           |          | 
    "paper_trades_live_pkey" PRIMARY KEY, btree (id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 3,
    "match_name": "Rajasthan Royals vs Mumbai Indians",
    "sport": "IPL",
    "team_backed": "Mumbai Indians",
    "entry_price": 0.5,
    "fair_value": 0.576,
    "edge_pct": 7.6,
    "position_size": 25.0,
    "shares": 50.0,
    "strategy": "cross_odds_ipl",
    "books_consensus": null,
    "book_count": 22,
    "status": "open",
    "exit_price": null,
    "pnl": null,
    "match_time": "2026-04-07T19:30:00+05:30",
    "entry_at": "2026-04-07T03:55:34.062651+05:30",
    "resolved_at": null,
    "notes": "EV=$+3.80"
}
```
</details>

## penny_positions (26 rows)
```
                                           Table "public.penny_positions"
       Column       |           Type           | Collation | Nullable |                   Default                   
 id                 | integer                  |           | not null | nextval('penny_positions_id_seq'::regclass)
 market_id          | text                     |           | not null | 
 condition_id       | text                     |           |          | 
 question           | text                     |           | not null | 
 category           | text                     |           |          | 
 outcome            | text                     |           |          | 
 buy_price          | numeric(6,4)             |           | not null | 
 quantity           | numeric(10,2)            |           |          | 1
 size_usd           | numeric(10,2)            |           |          | 
 potential_payout   | numeric(10,2)            |           |          | 
 catalyst_score     | numeric(4,2)             |           |          | 
 catalyst_reason    | text                     |           |          | 
 days_to_resolution | integer                  |           |          | 
 volume_usd         | numeric(18,2)            |           |          | 
 status             | text                     |           |          | 'open'::text
 resolution         | text                     |           |          | 
 pnl_usd            | numeric(10,2)            |           |          | 
 opened_at          | timestamp with time zone |           |          | now()
 resolved_at        | timestamp with time zone |           |          | 
 metadata           | jsonb                    |           |          | 
    "penny_positions_pkey" PRIMARY KEY, btree (id)
    "idx_penny_status" btree (status)
```
<details><summary>Sample row</summary>

```json
{
    "id": 12,
    "market_id": "1695986",
    "condition_id": "0x79a3155deb0060fe904f446def4d0c7b0e32dbb0b6ec1d29900d2ae14a171e50",
    "question": "Will Trump talk to Emmanuel Macron in April?",
    "category": "politics",
    "outcome": "No",
    "buy_price": 0.0195,
    "quantity": 128.21,
    "size_usd": 2.5,
    "potential_payout": 128.21,
    "catalyst_score": 5.0,
    "catalyst_reason": "20d left (sweet spot) | politics catalyst | 2c good asymmetry",
    "days_to_resolution": 20,
    "volume_usd": 9948.1,
    "status": "lost",
    "resolution": "resolved_loss",
    "pnl_usd": -2.5,
    "opened_at": "2026-04-09T16:34:52.084763+05:30",
    "resolved_at": "2026-04-09T19:34:54.623201+05:30",
    "metadata": {
        "end_date": "2026-04-30T00:00:00Z",
        "scanned_at": "2026-04-09T11:04:52.084884+00:00",
        "description": "This market will resolve to \"Yes\" if the listed individual talks with Donald Trump between April 1 and April 30, 2026, 11:59 PM ET. Otherwise, it will resolve to \"No\".\n\nA talk is defined as any interaction between the listed individual and Donald Trump, occurring either in person or through verbal communication by phone or video call.\n\nThe resolution source will be a consensus of credible reporting."
    }
}
```
</details>

## positions (0 rows)
```
                                        Table "public.positions"
    Column     |           Type           | Collation | Nullable |                Default                
 id            | integer                  |           | not null | nextval('positions_id_seq'::regclass)
 market_id     | character varying(255)   |           | not null | 
 market_title  | text                     |           |          | 
 city          | character varying(100)   |           |          | 
 strategy      | character varying(50)    |           | not null | 
 side          | character varying(10)    |           |          | 'YES'::character varying
 entry_price   | numeric                  |           | not null | 
 current_price | numeric                  |           |          | 
 size_usd      | numeric                  |           | not null | 
 shares        | numeric                  |           |          | 
 status        | character varying(20)    |           |          | 'open'::character varying
 entered_at    | timestamp with time zone |           |          | now()
 exited_at     | timestamp with time zone |           |          | 
 exit_price    | numeric                  |           |          | 
 pnl_usd       | numeric                  |           |          | 
 notes         | text                     |           |          | 
    "positions_pkey" PRIMARY KEY, btree (id)
```

## signals (0 rows)
```
                                               Table "public.signals"
        Column        |            Type             | Collation | Nullable |                 Default                 
 id                   | integer                     |           | not null | nextval('signals_id_seq'::regclass)
 market_id            | text                        |           |          | 
 station_icao         | text                        |           |          | 
 city                 | text                        |           |          | 
 side                 | text                        |           | not null | 
 our_probability      | numeric(6,4)                |           |          | 
 market_price         | numeric(6,4)                |           |          | 
 edge                 | numeric(6,4)                |           |          | 
 confidence           | text                        |           |          | 
 claude_reasoning     | text                        |           |          | 
 metar_data           | jsonb                       |           |          | 
 was_traded           | boolean                     |           |          | false
 skip_reason          | text                        |           |          | 
 created_at           | timestamp without time zone |           |          | now()
 bot                  | text                        |           |          | 
 market_title         | text                        |           |          | 
 source               | text                        |           |          | 
 recommended_size_usd | numeric(10,2)               |           |          | 
 expires_at           | timestamp without time zone |           |          | 
 metadata             | jsonb                       |           |          | 
 flagged              | boolean                     |           |          | true
 strategy             | character varying(50)       |           |          | 'intelligence_layer'::character varying
 entry_price          | numeric                     |           |          | 
 exit_threshold       | numeric                     |           |          | 0.45
    "signals_pkey" PRIMARY KEY, btree (id)
    TABLE "trades" CONSTRAINT "trades_signal_id_fkey" FOREIGN KEY (signal_id) REFERENCES signals(id)
```

## sports_markets (156 rows)
```
                                         Table "public.sports_markets"
     Column      |           Type           | Collation | Nullable |                  Default                   
 id              | integer                  |           | not null | nextval('sports_markets_id_seq'::regclass)
 market_id       | character varying(255)   |           |          | 
 question        | text                     |           |          | 
 sport           | character varying(50)    |           |          | 
 league          | character varying(100)   |           |          | 
 event_type      | character varying(50)    |           |          | 
 team_a          | character varying(200)   |           |          | 
 team_b          | character varying(200)   |           |          | 
 yes_price       | numeric                  |           |          | 
 no_price        | numeric                  |           |          | 
 volume_usd      | numeric                  |           |          | 
 liquidity_usd   | numeric                  |           |          | 
 resolution_date | timestamp with time zone |           |          | 
 group_id        | character varying(255)   |           |          | 
 metadata        | jsonb                    |           |          | 
 last_updated    | timestamp with time zone |           |          | now()
 is_active       | boolean                  |           |          | true
    "sports_markets_pkey" PRIMARY KEY, btree (id)
    "idx_sports_markets_group_id" btree (group_id) WHERE is_active = true
    "sports_markets_market_id_key" UNIQUE CONSTRAINT, btree (market_id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 2,
    "market_id": "553826",
    "question": "Will the Edmonton Oilers win the 2026 NHL Stanley Cup?",
    "sport": "NHL",
    "league": "NHL",
    "event_type": "championship",
    "team_a": "Stanley Cup",
    "team_b": null,
    "yes_price": 0.5,
    "no_price": 0.5,
    "volume_usd": 477239.79836500157,
    "liquidity_usd": 53168.7119,
    "resolution_date": null,
    "group_id": "nhl_stanley_cup_2026",
    "metadata": null,
    "last_updated": "2026-04-11T19:15:47.344469+05:30",
    "is_active": true
}
```
</details>

## sports_signals (342986 rows)
```
                                          Table "public.sports_signals"
      Column      |           Type           | Collation | Nullable |                  Default                   
 id               | integer                  |           | not null | nextval('sports_signals_id_seq'::regclass)
 edge_type        | character varying(50)    |           |          | 
 sport            | character varying(50)    |           |          | 
 market_id        | character varying(255)   |           |          | 
 market_title     | text                     |           |          | 
 group_id         | character varying(255)   |           |          | 
 polymarket_price | numeric                  |           |          | 
 fair_value       | numeric                  |           |          | 
 edge_pct         | numeric                  |           |          | 
 confidence       | character varying(20)    |           |          | 
 signal           | character varying(20)    |           |          | 
 reasoning        | text                     |           |          | 
 data_sources     | jsonb                    |           |          | 
 created_at       | timestamp with time zone |           |          | now()
    "sports_signals_pkey" PRIMARY KEY, btree (id)
    "idx_sports_signals_created" btree (created_at DESC)
```
<details><summary>Sample row</summary>

```json
{
    "id": 196936,
    "edge_type": "logical_arb",
    "sport": "NHL",
    "market_id": "553843",
    "market_title": "Will the Philadelphia Flyers win the 2026 NHL Stanley Cup?",
    "group_id": "nhl_stanley_cup_2026",
    "polymarket_price": 0.5,
    "fair_value": 0.037037037037037035,
    "edge_pct": 1250.0,
    "confidence": "HIGH",
    "signal": "SELL",
    "reasoning": "Group sum is 1350.00% (>100%). This market is 46.30% above fair share.",
    "data_sources": null,
    "created_at": "2026-04-10T01:56:10.932072+05:30"
}
```
</details>

## sportsbook_odds (747 rows)
```
                                           Table "public.sportsbook_odds"
       Column        |           Type           | Collation | Nullable |                   Default                   
 id                  | integer                  |           | not null | nextval('sportsbook_odds_id_seq'::regclass)
 sport               | character varying(50)    |           |          | 
 event_name          | text                     |           |          | 
 bookmaker           | character varying(100)   |           |          | 
 market_type         | character varying(50)    |           |          | 
 outcome             | character varying(200)   |           |          | 
 odds_decimal        | numeric                  |           |          | 
 implied_probability | numeric                  |           |          | 
 polymarket_id       | character varying(255)   |           |          | 
 fetched_at          | timestamp with time zone |           |          | now()
    "sportsbook_odds_pkey" PRIMARY KEY, btree (id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 97,
    "sport": "NBA",
    "event_name": "Boston Celtics vs Charlotte Hornets",
    "bookmaker": "fanduel",
    "market_type": "h2h",
    "outcome": "Boston Celtics",
    "odds_decimal": 1.4081632653061225,
    "implied_probability": 0.6805555555555556,
    "polymarket_id": null,
    "fetched_at": "2026-04-06T22:14:04.791387+05:30"
}
```
</details>

## station_accuracy (0 rows)
```
                           Table "public.station_accuracy"
        Column        |            Type             | Collation | Nullable | Default 
 station_icao         | text                        |           | not null | 
 city                 | text                        |           |          | 
 total_signals        | integer                     |           |          | 0
 correct_signals      | integer                     |           |          | 0
 accuracy             | numeric(6,4)                |           |          | 
 avg_temp_error_c     | numeric(5,2)                |           |          | 
 best_lead_time_hours | integer                     |           |          | 
 last_updated         | timestamp without time zone |           |          | now()
    "station_accuracy_pkey" PRIMARY KEY, btree (station_icao)
```

## strategy_performance (0 rows)
```
                                            Table "public.strategy_performance"
      Column       |            Type             | Collation | Nullable |                     Default                      
 id                | integer                     |           | not null | nextval('strategy_performance_id_seq'::regclass)
 strategy          | character varying(50)       |           | not null | 
 sport             | character varying(50)       |           | not null | 'ALL'::character varying
 period_start      | date                        |           | not null | 
 period_end        | date                        |           | not null | 
 total_trades      | integer                     |           |          | 0
 wins              | integer                     |           |          | 0
 losses            | integer                     |           |          | 0
 win_rate          | double precision            |           |          | 
 total_pnl         | double precision            |           |          | 0
 avg_edge          | double precision            |           |          | 0
 avg_pnl_per_trade | double precision            |           |          | 0
 max_drawdown      | double precision            |           |          | 0
 sharpe_ratio      | double precision            |           |          | 
 is_active         | boolean                     |           |          | true
 updated_at        | timestamp without time zone |           |          | now()
    "strategy_performance_pkey" PRIMARY KEY, btree (id)
    "idx_strat_perf_unique" UNIQUE, btree (strategy, sport, period_start)
```

## taf_forecasts (0 rows)
```
                                             Table "public.taf_forecasts"
       Column        |            Type             | Collation | Nullable |                  Default                  
 id                  | integer                     |           | not null | nextval('taf_forecasts_id_seq'::regclass)
 station_icao        | character varying(4)        |           | not null | 
 issue_time          | timestamp without time zone |           | not null | 
 valid_from          | timestamp without time zone |           | not null | 
 valid_to            | timestamp without time zone |           | not null | 
 raw_taf             | text                        |           | not null | 
 forecast_high       | double precision            |           |          | 
 forecast_low        | double precision            |           |          | 
 significant_weather | text                        |           |          | 
 wind_changes        | text                        |           |          | 
 created_at          | timestamp without time zone |           |          | now()
    "taf_forecasts_pkey" PRIMARY KEY, btree (id)
    "idx_taf_station_time" btree (station_icao, issue_time DESC)
    "taf_forecasts_station_icao_issue_time_key" UNIQUE CONSTRAINT, btree (station_icao, issue_time)
```

## telegram_subscribers (4 rows)
```
                                          Table "public.telegram_subscribers"
      Column       |           Type           | Collation | Nullable |                     Default                      
 id                | integer                  |           | not null | nextval('telegram_subscribers_id_seq'::regclass)
 chat_id           | bigint                   |           | not null | 
 username          | character varying(100)   |           |          | 
 first_name        | character varying(100)   |           |          | 
 tier              | character varying(20)    |           |          | 'free'::character varying
 subscribed_at     | timestamp with time zone |           |          | now()
 is_active         | boolean                  |           |          | true
 sports_filter     | text[]                   |           |          | 
 min_edge          | numeric                  |           |          | 5.0
 alert_frequency   | character varying(20)    |           |          | 'instant'::character varying
 last_alert_at     | timestamp with time zone |           |          | 
 total_alerts_sent | integer                  |           |          | 0
 approved          | boolean                  |           |          | false
    "telegram_subscribers_pkey" PRIMARY KEY, btree (id)
    "idx_telegram_subscribers_active" btree (is_active)
    "idx_telegram_subscribers_chat_id" btree (chat_id)
    "telegram_subscribers_chat_id_key" UNIQUE CONSTRAINT, btree (chat_id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 1,
    "chat_id": 1656605843,
    "username": "ahswaat",
    "first_name": "A",
    "tier": "free",
    "subscribed_at": "2026-04-07T13:35:29.775803+05:30",
    "is_active": true,
    "sports_filter": null,
    "min_edge": 5.0,
    "alert_frequency": "instant",
    "last_alert_at": "2026-04-07T13:41:57.725004+05:30",
    "total_alerts_sent": 1,
    "approved": true
}
```
</details>

## temperature_trends (87037 rows)
```
                                          Table "public.temperature_trends"
     Column     |            Type             | Collation | Nullable |                    Default                     
 id             | integer                     |           | not null | nextval('temperature_trends_id_seq'::regclass)
 station_icao   | character varying(4)        |           | not null | 
 calculated_at  | timestamp without time zone |           |          | now()
 trend_per_hour | double precision            |           |          | 
 projected_high | double precision            |           |          | 
 projected_low  | double precision            |           |          | 
 confidence     | double precision            |           |          | 
 num_readings   | integer                     |           |          | 
    "temperature_trends_pkey" PRIMARY KEY, btree (id)
    "idx_trends_station_time" btree (station_icao, calculated_at DESC)
    "temperature_trends_station_icao_calculated_at_key" UNIQUE CONSTRAINT, btree (station_icao, calculated_at)
```
<details><summary>Sample row</summary>

```json
{
    "id": 1,
    "station_icao": "CYYZ",
    "calculated_at": "2026-04-06T16:30:40.094106",
    "trend_per_hour": 7.52168660934662e-15,
    "projected_high": 6.00000000000018,
    "projected_low": -4,
    "confidence": 0,
    "num_readings": 4
}
```
</details>

## trade_learnings (0 rows)
```
                                            Table "public.trade_learnings"
       Column       |            Type             | Collation | Nullable |                   Default                   
 id                 | integer                     |           | not null | nextval('trade_learnings_id_seq'::regclass)
 trade_id           | integer                     |           |          | 
 strategy           | character varying(50)       |           |          | 
 sport              | character varying(50)       |           |          | 
 predicted_edge     | double precision            |           |          | 
 actual_outcome     | character varying(20)       |           |          | 
 pnl_usd            | double precision            |           |          | 
 edge_bucket        | character varying(20)       |           |          | 
 signal_was_correct | boolean                     |           |          | 
 analysis_notes     | text                        |           |          | 
 created_at         | timestamp without time zone |           |          | now()
    "trade_learnings_pkey" PRIMARY KEY, btree (id)
    "idx_trade_learnings_bucket" btree (edge_bucket)
    "idx_trade_learnings_sport" btree (sport, created_at DESC)
    "idx_trade_learnings_strategy" btree (strategy, created_at DESC)
```

## trades (0 rows)
```
                                            Table "public.trades"
    Column     |            Type             | Collation | Nullable |                 Default                 
 id            | integer                     |           | not null | nextval('trades_id_seq'::regclass)
 signal_id     | integer                     |           |          | 
 market_id     | text                        |           |          | 
 market_title  | text                        |           |          | 
 side          | text                        |           | not null | 
 entry_price   | numeric(6,4)                |           |          | 
 shares        | numeric(12,4)               |           |          | 
 size_usd      | numeric(10,2)               |           |          | 
 edge_at_entry | numeric(10,4)               |           |          | 
 tx_hash       | text                        |           |          | 
 status        | text                        |           |          | 'open'::text
 exit_price    | numeric(6,4)                |           |          | 
 exit_tx_hash  | text                        |           |          | 
 pnl_usd       | numeric(10,2)               |           |          | 
 pnl_pct       | numeric(8,4)                |           |          | 
 resolved_at   | timestamp without time zone |           |          | 
 entry_at      | timestamp without time zone |           |          | now()
 metadata      | jsonb                       |           |          | 
 strategy      | character varying(50)       |           |          | 'intelligence_layer'::character varying
    "trades_pkey" PRIMARY KEY, btree (id)
    "trades_signal_id_fkey" FOREIGN KEY (signal_id) REFERENCES signals(id)
```

## weather_markets (30 rows)
```
                                           Table "public.weather_markets"
     Column      |            Type             | Collation | Nullable |                   Default                   
 id              | integer                     |           | not null | nextval('weather_markets_id_seq'::regclass)
 market_id       | text                        |           | not null | 
 title           | text                        |           | not null | 
 city            | text                        |           |          | 
 station_icao    | text                        |           |          | 
 threshold_type  | text                        |           |          | 
 threshold_value | numeric(6,1)                |           |          | 
 threshold_unit  | text                        |           |          | 
 resolution_date | date                        |           |          | 
 yes_price       | numeric(6,4)                |           |          | 
 no_price        | numeric(6,4)                |           |          | 
 volume_usd      | numeric(12,2)               |           |          | 
 liquidity_usd   | numeric(12,2)               |           |          | 
 last_updated    | timestamp without time zone |           |          | now()
 active          | boolean                     |           |          | true
 metadata        | jsonb                       |           |          | 
 created_at      | timestamp without time zone |           |          | now()
 updated_at      | timestamp without time zone |           |          | now()
 volume          | numeric(12,2)               |           |          | 
 liquidity       | numeric(12,2)               |           |          | 
    "weather_markets_pkey" PRIMARY KEY, btree (id)
    "weather_markets_market_id_key" UNIQUE CONSTRAINT, btree (market_id)
```
<details><summary>Sample row</summary>

```json
{
    "id": 1,
    "market_id": "0x97ff49f9ad7222f4dede0476269cdadfadb4004eb4644a908bc44bc11ddf4f81",
    "title": "Will it snow in New York's Central Park on New Year's Eve (Dec 31)?",
    "city": null,
    "station_icao": null,
    "threshold_type": null,
    "threshold_value": null,
    "threshold_unit": null,
    "resolution_date": null,
    "yes_price": null,
    "no_price": null,
    "volume_usd": null,
    "liquidity_usd": null,
    "last_updated": "2026-04-06T20:49:46.808233",
    "active": false,
    "metadata": {
        "slug": "will-it-snow-in-new-yorks-central-park-on-new-years-eve-dec-31",
        "closed": true,
        "end_date": "2022-01-01T00:00:00Z",
        "question": "Will it snow in New York's Central Park on New Year's Eve (Dec 31)?"
    },
    "created_at": "2026-04-06T20:49:46.808233",
    "updated_at": "2026-04-06T20:49:46.808233",
    "volume": null,
    "liquidity": null
}
```
</details>

---
**Re-generate:** `bash scripts/dump-schema.sh`
