# BTC Up/Down Market Discovery

## Market Structure (from Polymarket screenshot + API testing)

**5-Minute Markets:**
- Slug pattern: `btc-updown-5m-{unix_timestamp}`
- Timestamp = window START time (rounded to 300-second boundary)
- Example: `btc-updown-5m-1775691300` = April 8, 7:35PM-7:40PM ET
- UP token pays $1 if BTC price (Chainlink) at window close >= window open
- DOWN token pays $1 otherwise
- Resolution: Chainlink BTC/USD data stream (https://data.chain.link/streams/btc-usd)
- Typical volume: $1.5K-$80K per window
- Windows run 24/7

**15-Minute Markets:**
- Slug pattern: `btc-updown-15m-{unix_timestamp}`
- Same mechanics, 15-minute windows
- Timestamp = window START, rounded to 900-second boundary

**Also Active:**
- ETH Up or Down (5 Min / 15 Min)
- SOL Up or Down (5 Min / 15 Min)  
- XRP Up or Down (5 Min / 15 Min)
- DOGE Up or Down (5 Min / 15 Min)

**API Discovery:**
```python
import time
now = int(time.time())
current_5m = (now // 300) * 300
next_5m = current_5m + 300
slug = f"btc-updown-5m-{next_5m}"
# GET https://gamma-api.polymarket.com/events?slug={slug}
```

**Key Fields:**
- conditionId: for CLOB order placement
- clobTokenIds: [UP_token_id, DOWN_token_id]
- outcomePrices: ["UP_price", "DOWN_price"] (e.g., ["0.62", "0.40"])

**Last Verified:** 2026-04-09 05:06 IST
