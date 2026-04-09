import { useState, useEffect, useRef, useCallback } from "react";

const SIGNALS = {
  RSI: { name: "RSI (14)", weight: 0.15, description: "Relative Strength Index" },
  MACD: { name: "MACD Cross", weight: 0.12, description: "MACD / Signal line crossover" },
  VWAP: { name: "VWAP Deviation", weight: 0.13, description: "Volume-weighted avg price deviation" },
  OBV: { name: "OBV Trend", weight: 0.10, description: "On-Balance Volume momentum" },
  BB: { name: "Bollinger Band", weight: 0.10, description: "Bollinger Band squeeze/breakout" },
  FUNDING: { name: "Funding Rate", weight: 0.08, description: "Perpetual swap funding rate" },
  OI: { name: "Open Interest Δ", weight: 0.08, description: "Open interest change rate" },
  CVD: { name: "CVD", weight: 0.09, description: "Cumulative Volume Delta" },
  ORDERBOOK: { name: "Book Imbalance", weight: 0.08, description: "Bid/ask depth imbalance" },
  CORRELATION: { name: "SPX Correlation", weight: 0.07, description: "S&P 500 lead/lag correlation" },
};

const generateMockSignal = (id, trend) => {
  const noise = (Math.random() - 0.5) * 0.6;
  const trendBias = trend === "up" ? 0.15 : trend === "down" ? -0.15 : 0;
  const raw = Math.max(-1, Math.min(1, trendBias + noise));
  const confidence = 0.4 + Math.random() * 0.55;
  return {
    id,
    ...SIGNALS[id],
    value: raw,
    confidence,
    direction: raw > 0.05 ? "UP" : raw < -0.05 ? "NEUTRAL" : "DOWN",
    score: raw * confidence * SIGNALS[id].weight,
    timestamp: Date.now(),
  };
};

const generateCandle = (prev, trend) => {
  const volatility = 30 + Math.random() * 80;
  const bias = trend === "up" ? volatility * 0.3 : trend === "down" ? -volatility * 0.3 : 0;
  const change = (Math.random() - 0.5) * volatility + bias;
  const open = prev?.close || 67500 + Math.random() * 500;
  const close = open + change;
  const high = Math.max(open, close) + Math.random() * volatility * 0.5;
  const low = Math.min(open, close) - Math.random() * volatility * 0.5;
  const volume = 50 + Math.random() * 200;
  return { open, close, high, low, volume, time: Date.now() };
};

const SignalBar = ({ signal }) => {
  const pct = ((signal.value + 1) / 2) * 100;
  const color =
    signal.value > 0.15 ? "#00ff87" : signal.value < -0.15 ? "#ff3366" : "#ffaa00";
  const confPct = signal.confidence * 100;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
      <div style={{ width: 130, fontSize: 11, color: "#8892a4", fontFamily: "'JetBrains Mono', monospace", letterSpacing: 0.3 }}>
        {signal.name}
      </div>
      <div style={{ flex: 1, height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 3, position: "relative", overflow: "hidden" }}>
        <div style={{
          position: "absolute", left: "50%", top: 0, height: "100%", borderRadius: 3,
          width: `${Math.abs(pct - 50)}%`,
          marginLeft: pct >= 50 ? 0 : `${pct - 50}%`,
          background: `linear-gradient(90deg, ${color}88, ${color})`,
          transition: "all 0.5s ease",
        }} />
        <div style={{ position: "absolute", left: "50%", top: -2, width: 1, height: 10, background: "rgba(255,255,255,0.15)" }} />
      </div>
      <div style={{ width: 45, textAlign: "right", fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color, fontWeight: 600 }}>
        {signal.value > 0 ? "+" : ""}{(signal.value * 100).toFixed(0)}%
      </div>
      <div style={{
        width: 50, height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden",
      }}>
        <div style={{ width: `${confPct}%`, height: "100%", background: `rgba(255,255,255,${0.15 + signal.confidence * 0.35})`, borderRadius: 2, transition: "width 0.5s" }} />
      </div>
    </div>
  );
};

const MiniChart = ({ candles, targetPrice, windowOpen }) => {
  if (candles.length < 2) return null;
  const w = 320, h = 120, pad = 2;
  const prices = candles.flatMap((c) => [c.high, c.low]);
  // Include target and window open in price range so lines are always visible
  if (targetPrice) prices.push(targetPrice);
  if (windowOpen) prices.push(windowOpen);
  const min = Math.min(...prices), max = Math.max(...prices);
  const range = max - min || 1;
  const barW = Math.max(2, (w - pad * 2) / candles.length - 1);

  // Y position helper
  const priceToY = (p) => pad + ((max - p) / range) * (h - pad * 2);

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      {/* Window open price line (dashed white) */}
      {windowOpen > 0 && (
        <g>
          <line x1={0} y1={priceToY(windowOpen)} x2={w} y2={priceToY(windowOpen)}
            stroke="#ffffff" strokeWidth={0.8} strokeDasharray="4,3" opacity={0.25} />
          <text x={w - 2} y={priceToY(windowOpen) - 3} fill="#ffffff" opacity={0.4}
            fontSize={7} fontFamily="JetBrains Mono" textAnchor="end">OPEN</text>
        </g>
      )}

      {/* Polymarket target line (bright, solid) */}
      {targetPrice > 0 && (
        <g>
          <line x1={0} y1={priceToY(targetPrice)} x2={w} y2={priceToY(targetPrice)}
            stroke="#6366f1" strokeWidth={1.2} opacity={0.8} />
          <rect x={w - 52} y={priceToY(targetPrice) - 8} width={50} height={14} rx={3}
            fill="#6366f1" opacity={0.9} />
          <text x={w - 27} y={priceToY(targetPrice) + 3} fill="#fff"
            fontSize={8} fontFamily="JetBrains Mono" textAnchor="middle" fontWeight="600">
            PM ${targetPrice.toFixed(0)}
          </text>
        </g>
      )}

      {/* Candlesticks */}
      {candles.map((c, i) => {
        const x = pad + i * ((w - pad * 2) / candles.length);
        const yH = priceToY(c.high);
        const yL = priceToY(c.low);
        const yO = priceToY(c.open);
        const yC = priceToY(c.close);
        const bull = c.close >= c.open;
        const col = bull ? "#00ff87" : "#ff3366";
        return (
          <g key={i}>
            <line x1={x + barW / 2} y1={yH} x2={x + barW / 2} y2={yL} stroke={col} strokeWidth={0.8} opacity={0.6} />
            <rect x={x} y={Math.min(yO, yC)} width={barW} height={Math.max(1, Math.abs(yC - yO))} fill={col} rx={0.5} opacity={0.85} />
          </g>
        );
      })}

      {/* Current price label on right edge */}
      {candles.length > 0 && (
        <g>
          <rect x={w - 58} y={priceToY(candles[candles.length-1].close) - 8} width={56} height={14} rx={3}
            fill={candles[candles.length-1].close >= (windowOpen || candles[0].open) ? "#00ff87" : "#ff3366"} opacity={0.9} />
          <text x={w - 30} y={priceToY(candles[candles.length-1].close) + 3} fill="#000"
            fontSize={8} fontFamily="JetBrains Mono" textAnchor="middle" fontWeight="700">
            ${candles[candles.length-1].close.toFixed(0)}
          </text>
        </g>
      )}
    </svg>
  );
};

export default function BTCPolymarketEngine() {
  const [signals, setSignals] = useState([]);
  const [candles, setCandles] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [polymarketOdds, setPolymarketOdds] = useState({ up: 0.50, down: 0.50 });
  const [trades, setTrades] = useState([]);
  const [running, setRunning] = useState(true);  // Auto-start
  const [btcPrice, setBtcPrice] = useState(null);
  const [chainlinkPrice, setChainlinkPrice] = useState(null);
  const [liveWindows, setLiveWindows] = useState([]);
  const [activeWindow, setActiveWindow] = useState(null);
  const [priceFlash, setPriceFlash] = useState(null);
  const prevPriceRef = useRef(null);
  const [countdown, setCountdown] = useState(300);
  const [config, setConfig] = useState({
    minConfidence: 0.65,
    minEdge: 0.05,
    kellyFraction: 0.25,
    maxBet: 500,
    bankroll: 10000,
    autoTrade: false,
  });
  const [stats, setStats] = useState({ wins: 0, losses: 0, pnl: 0, trades: 0 });
  const [tab, setTab] = useState("dashboard");
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const trendRef = useRef("neutral");
  const intervalRef = useRef(null);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const computePrediction = useCallback((sigs) => {
    const totalScore = sigs.reduce((s, sig) => s + sig.score, 0);
    const avgConf = sigs.reduce((s, sig) => s + sig.confidence, 0) / sigs.length;
    const agreeing = sigs.filter((s) => (totalScore > 0 ? s.value > 0 : s.value < 0)).length;
    const confluence = agreeing / sigs.length;
    const direction = totalScore > 0.02 ? "UP" : totalScore < -0.02 ? "DOWN" : "NEUTRAL";
    const rawProb = 0.5 + totalScore * 2.5;
    const prob = Math.max(0.05, Math.min(0.95, rawProb));
    const confidence = avgConf * confluence;
    return { direction, probability: prob, confidence, confluence, totalScore, agreeing, total: sigs.length };
  }, []);

  const computeEdge = useCallback((pred, odds) => {
    if (pred.direction === "NEUTRAL") return { edge: 0, side: null, marketPrice: 0 };
    const side = pred.direction === "UP" ? "up" : "down";
    const marketPrice = odds[side];
    const edge = pred.probability - marketPrice;
    return { edge, side, marketPrice };
  }, []);

  const kellyBet = useCallback((edge, prob, fraction, maxBet, bankroll) => {
    if (edge <= 0) return 0;
    const b = (1 / (1 - prob)) - 1;
    const kelly = (b * prob - (1 - prob)) / b;
    const bet = Math.max(0, Math.min(maxBet, bankroll * kelly * fraction));
    return Math.round(bet * 100) / 100;
  }, []);

  const tick = useCallback(() => {
    const trends = ["up", "down", "neutral"];
    if (Math.random() < 0.08) trendRef.current = trends[Math.floor(Math.random() * 3)];

    const newSignals = Object.keys(SIGNALS).map((id) => generateMockSignal(id, trendRef.current));
    setSignals(newSignals);

    setCandles((prev) => {
      const next = [...prev, generateCandle(prev[prev.length - 1], trendRef.current)];
      return next.slice(-60);
    });

    const pred = computePrediction(newSignals);
    setPrediction(pred);

    const upBias = 0.5 + (Math.random() - 0.5) * 0.15 + (trendRef.current === "up" ? 0.03 : trendRef.current === "down" ? -0.03 : 0);
    setPolymarketOdds({ up: Math.round(upBias * 100) / 100, down: Math.round((1 - upBias) * 100) / 100 });

    setCountdown((c) => (c <= 0 ? 300 : c - 1));

    if (config.autoTrade && pred.direction !== "NEUTRAL") {
      const { edge, side, marketPrice } = computeEdge(pred, { up: upBias, down: 1 - upBias });
      if (pred.confidence >= config.minConfidence && edge >= config.minEdge) {
        const bet = kellyBet(edge, pred.probability, config.kellyFraction, config.maxBet, config.bankroll);
        if (bet > 0) {
          const win = Math.random() < pred.probability * 0.85 + 0.08;
          const pnl = win ? bet * (1 / marketPrice - 1) : -bet;
          const trade = {
            id: Date.now(),
            time: new Date().toLocaleTimeString(),
            side: side.toUpperCase(),
            confidence: pred.confidence,
            edge,
            bet,
            marketPrice,
            result: win ? "WIN" : "LOSS",
            pnl: Math.round(pnl * 100) / 100,
          };
          setTrades((prev) => [trade, ...prev].slice(0, 50));
          setStats((prev) => ({
            wins: prev.wins + (win ? 1 : 0),
            losses: prev.losses + (win ? 0 : 1),
            pnl: Math.round((prev.pnl + pnl) * 100) / 100,
            trades: prev.trades + 1,
          }));
        }
      }
    }
  }, [config, computePrediction, computeEdge, kellyBet]);

  useEffect(() => {
    // Initialize candles
    let c = [];
    for (let i = 0; i < 30; i++) c.push(generateCandle(c[c.length - 1], "neutral"));
    setCandles(c);
    tick();

    // Fetch real BTC data from our API — fast 1s refresh
    const fetchLive = async () => {
      try {
        const res = await fetch('/api/btc/state');
        const data = await res.json();
        if (data.btc_price) {
          const newPrice = Number(data.btc_price);
          if (prevPriceRef.current && newPrice !== prevPriceRef.current) {
            setPriceFlash(newPrice > prevPriceRef.current ? 'up' : 'down');
            setTimeout(() => setPriceFlash(null), 500);
          }
          prevPriceRef.current = newPrice;
          setBtcPrice(newPrice);
        }
        if (data.chainlink_price) setChainlinkPrice(Number(data.chainlink_price));
        if (data.active_windows) {
          setLiveWindows(data.active_windows);
          // Find the nearest active window
          const activeW = data.active_windows
            .filter(w => w.seconds_remaining > 0)
            .sort((a, b) => a.seconds_remaining - b.seconds_remaining)[0];
          if (activeW) {
            setActiveWindow(activeW);
            setPolymarketOdds({ up: activeW.up_price || 0.5, down: activeW.down_price || 0.5 });
          }
        }
      } catch(e) { /* silent */ }
    };
    fetchLive();
    const liveInterval = setInterval(fetchLive, 1000);
    return () => clearInterval(liveInterval);
  }, []);

  useEffect(() => {
    if (running) {
      intervalRef.current = setInterval(tick, 2000);
    } else {
      clearInterval(intervalRef.current);
    }
    return () => clearInterval(intervalRef.current);
  }, [running, tick]);

  const winRate = stats.trades > 0 ? ((stats.wins / stats.trades) * 100).toFixed(1) : "—";
  const edgeInfo = prediction ? computeEdge(prediction, polymarketOdds) : { edge: 0, side: null };

  const font = "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace";
  const fontSans = "'Inter', 'SF Pro', -apple-system, sans-serif";

  return (
    <div style={{
      background: "#0a0c10", color: "#c8cdd8", minHeight: "100vh", fontFamily: fontSans,
      padding: "0", position: "relative", overflow: "hidden",
    }}>
      <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />

      {/* Subtle grid background */}
      <div style={{ position: "fixed", inset: 0, opacity: 0.03, backgroundImage: "linear-gradient(rgba(255,255,255,.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.1) 1px, transparent 1px)", backgroundSize: "40px 40px", pointerEvents: "none" }} />

      {/* Header */}
      <div style={{
        borderBottom: "1px solid rgba(255,255,255,0.06)", padding: isMobile ? "10px 12px" : "14px 24px",
        display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: isMobile ? 8 : 0,
        background: "rgba(10,12,16,0.9)", backdropFilter: "blur(20px)", position: "sticky", top: 0, zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: running ? "#00ff87" : "#ff3366",
            boxShadow: running ? "0 0 12px #00ff8766" : "0 0 12px #ff336666",
            animation: running ? "pulse 2s infinite" : "none",
          }} />
          <span style={{ fontFamily: font, fontWeight: 700, fontSize: 14, letterSpacing: 1.5, color: "#fff" }}>
            POLYMARKET EDGE ENGINE
          </span>
          <span style={{ fontSize: 10, color: "#4a5068", fontFamily: font }}>BTC/USD 5m</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {["dashboard", "analysis", "strategy", "trades"].map((t) => (
            <button key={t} onClick={() => setTab(t)} style={{
              background: tab === t ? "rgba(255,255,255,0.08)" : "transparent",
              border: tab === t ? "1px solid rgba(255,255,255,0.12)" : "1px solid transparent",
              color: tab === t ? "#fff" : "#4a5068", borderRadius: 6, padding: "5px 14px",
              fontSize: 11, fontFamily: font, cursor: "pointer", textTransform: "uppercase", letterSpacing: 1,
            }}>
              {t}
            </button>
          ))}
        </div>
        <button onClick={() => setRunning(!running)} style={{
          background: running ? "rgba(255,51,102,0.15)" : "rgba(0,255,135,0.15)",
          border: `1px solid ${running ? "#ff336644" : "#00ff8744"}`,
          color: running ? "#ff3366" : "#00ff87", borderRadius: 8, padding: "7px 20px",
          fontFamily: font, fontSize: 11, fontWeight: 600, cursor: "pointer", letterSpacing: 1,
        }}>
          {running ? "■ STOP" : "▶ START"} ENGINE
        </button>
      </div>

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        input[type=range] { -webkit-appearance: none; height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; outline: none; }
        input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 14px; height: 14px; background: #00ff87; border-radius: 50%; cursor: pointer; }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-track { background: transparent; } ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }
        @media (max-width: 768px) {
          .main-grid { grid-template-columns: 1fr !important; }
          .stats-grid { grid-template-columns: repeat(2, 1fr) !important; }
          .header-bar { flex-wrap: wrap; gap: 8px !important; padding: 10px 12px !important; }
          .header-bar > div:last-child { order: -1; width: 100%; }
          .trade-table { overflow-x: auto; }
          .trade-row { grid-template-columns: 65px 40px 55px 55px 50px 55px 50px 65px !important; font-size: 10px !important; }
        }
      `}</style>

      {/* Triple Price Ticker Bar */}
      <div style={{
        display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, 1fr)', gap: isMobile ? 6 : 12,
        padding: isMobile ? '8px 12px' : '12px 24px',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        background: 'rgba(0,0,0,0.3)',
      }}>
        {/* Binance */}
        <div style={{ background: 'rgba(247,147,26,0.06)', border: '1px solid rgba(247,147,26,0.12)', borderRadius: 10, padding: isMobile ? '10px 12px' : '14px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 9, color: '#F7931A', fontFamily: font, letterSpacing: 1.5, marginBottom: 4 }}>BINANCE BTC/USD</div>
            <div style={{
              fontSize: isMobile ? 20 : 26, fontFamily: font, fontWeight: 700, letterSpacing: -0.5,
              color: priceFlash === 'up' ? '#00ff87' : priceFlash === 'down' ? '#ff3366' : '#F7931A',
              transition: 'color 0.3s',
            }}>
              ${btcPrice ? btcPrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '---'}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 9, color: '#4a5068', fontFamily: font }}>24H</div>
            <div style={{ fontSize: 12, fontFamily: font, fontWeight: 600, color: '#00ff87' }}>LIVE</div>
          </div>
        </div>

        {/* Chainlink */}
        <div style={{ background: 'rgba(55,91,210,0.06)', border: '1px solid rgba(55,91,210,0.12)', borderRadius: 10, padding: isMobile ? '10px 12px' : '14px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 9, color: '#375BD2', fontFamily: font, letterSpacing: 1.5, marginBottom: 4 }}>CHAINLINK ORACLE</div>
            <div style={{ fontSize: isMobile ? 20 : 26, fontFamily: font, fontWeight: 700, color: '#7B93DB' }}>
              ${chainlinkPrice ? chainlinkPrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '---'}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 9, color: '#4a5068', fontFamily: font }}>LAG</div>
            <div style={{ fontSize: 12, fontFamily: font, fontWeight: 600, color: btcPrice && chainlinkPrice ? (Math.abs(btcPrice - chainlinkPrice) < 50 ? '#00ff87' : '#ffaa00') : '#4a5068' }}>
              {btcPrice && chainlinkPrice ? `${(btcPrice - chainlinkPrice).toFixed(0)}` : '---'}
            </div>
          </div>
        </div>

        {/* Polymarket */}
        <div style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.12)', borderRadius: 10, padding: isMobile ? '10px 12px' : '14px 18px' }}>
          <div style={{ fontSize: 9, color: '#6366f1', fontFamily: font, letterSpacing: 1.5, marginBottom: 4 }}>
            POLYMARKET {activeWindow ? `${activeWindow.window_length}M` : ''}
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
            <div>
              <span style={{ fontSize: 9, color: '#00ff87aa', fontFamily: font }}>UP </span>
              <span style={{ fontSize: isMobile ? 18 : 22, fontFamily: font, fontWeight: 700, color: '#00ff87' }}>
                {(polymarketOdds.up * 100).toFixed(0)}c
              </span>
            </div>
            <div>
              <span style={{ fontSize: 9, color: '#ff3366aa', fontFamily: font }}>DN </span>
              <span style={{ fontSize: isMobile ? 18 : 22, fontFamily: font, fontWeight: 700, color: '#ff3366' }}>
                {(polymarketOdds.down * 100).toFixed(0)}c
              </span>
            </div>
            {activeWindow && (
              <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                <div style={{ fontSize: 9, color: '#4a5068', fontFamily: font }}>CLOSES</div>
                <div style={{ fontSize: 14, fontFamily: font, fontWeight: 700, color: activeWindow.seconds_remaining < 30 ? '#ff3366' : activeWindow.seconds_remaining < 120 ? '#ffaa00' : '#00ff87' }}>
                  {Math.floor(activeWindow.seconds_remaining / 60)}:{(activeWindow.seconds_remaining % 60).toString().padStart(2, '0')}
                </div>
              </div>
            )}
          </div>
          {liveWindows.length > 0 && (
            <div style={{ fontSize: 9, color: '#4a5068', fontFamily: font, marginTop: 4 }}>
              {liveWindows.filter(w => w.seconds_remaining > 0).length} windows | Vol: ${liveWindows.reduce((s, w) => s + (w.volume_usd || 0), 0).toLocaleString(undefined, {maximumFractionDigits: 0})}
            </div>
          )}
        </div>
      </div>

      {tab === "dashboard" && (
        <div style={{ padding: isMobile ? "12px" : "20px 24px", display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr 1fr", gap: isMobile ? 10 : 16, className: "main-grid" }}>
          {/* Top stats row */}
          <div style={{ gridColumn: "1 / -1", display: "grid", gridTemplateColumns: isMobile ? "repeat(2, 1fr)" : "repeat(5, 1fr)", gap: isMobile ? 8 : 12 }}>
            {[
              { label: "WIN RATE", value: `${winRate}%`, color: parseFloat(winRate) > 55 ? "#00ff87" : "#ffaa00" },
              { label: "P&L", value: `$${stats.pnl.toLocaleString()}`, color: stats.pnl >= 0 ? "#00ff87" : "#ff3366" },
              { label: "TRADES", value: stats.trades, color: "#6366f1" },
              { label: "EDGE", value: `${(edgeInfo.edge * 100).toFixed(1)}%`, color: edgeInfo.edge > 0.05 ? "#00ff87" : "#4a5068" },
              { label: "NEXT CANDLE", value: `${Math.floor(countdown / 60)}:${(countdown % 60).toString().padStart(2, "0")}`, color: countdown < 30 ? "#ff3366" : "#4a5068" },
            ].map((s, i) => (
              <div key={i} style={{
                background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)",
                borderRadius: 10, padding: "14px 16px", textAlign: "center",
              }}>
                <div style={{ fontSize: 9, color: "#4a5068", fontFamily: font, letterSpacing: 1.5, marginBottom: 6 }}>{s.label}</div>
                <div style={{ fontSize: 20, fontFamily: font, fontWeight: 700, color: s.color }}>{s.value}</div>
              </div>
            ))}
          </div>

          {/* Signal Panel */}
          <div style={{
            background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)",
            borderRadius: 12, padding: isMobile ? 12 : 18, gridRow: isMobile ? "auto" : "span 2",
          }}>
            <div style={{ fontSize: 10, color: "#4a5068", fontFamily: font, letterSpacing: 1.5, marginBottom: 14 }}>
              SIGNAL CONFLUENCE — {signals.filter((s) => (prediction?.direction === "UP" ? s.value > 0 : s.value < 0)).length}/{signals.length} AGREEING
            </div>
            {signals.map((s) => <SignalBar key={s.id} signal={s} />)}
            <div style={{ marginTop: 14, padding: "10px 12px", background: "rgba(255,255,255,0.03)", borderRadius: 8 }}>
              <div style={{ fontSize: 9, color: "#4a5068", fontFamily: font, letterSpacing: 1.5, marginBottom: 6 }}>WEIGHTED COMPOSITE</div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ flex: 1, height: 8, background: "rgba(255,255,255,0.06)", borderRadius: 4, position: "relative", overflow: "hidden" }}>
                  <div style={{
                    position: "absolute", left: "50%", top: 0, height: "100%", borderRadius: 4,
                    width: `${Math.abs((prediction?.totalScore || 0) * 200)}%`,
                    marginLeft: (prediction?.totalScore || 0) >= 0 ? 0 : `${(prediction?.totalScore || 0) * 200}%`,
                    background: (prediction?.totalScore || 0) > 0 ? "linear-gradient(90deg, #00ff8766, #00ff87)" : "linear-gradient(270deg, #ff336666, #ff3366)",
                    transition: "all 0.5s",
                  }} />
                </div>
                <span style={{ fontFamily: font, fontSize: 13, fontWeight: 700, color: (prediction?.totalScore || 0) > 0 ? "#00ff87" : "#ff3366" }}>
                  {((prediction?.totalScore || 0) * 100).toFixed(1)}
                </span>
              </div>
            </div>
          </div>

          {/* Prediction + Market */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Prediction card */}
            <div style={{
              background: prediction?.direction === "UP" ? "rgba(0,255,135,0.04)" : prediction?.direction === "DOWN" ? "rgba(255,51,102,0.04)" : "rgba(255,255,255,0.02)",
              border: `1px solid ${prediction?.direction === "UP" ? "rgba(0,255,135,0.15)" : prediction?.direction === "DOWN" ? "rgba(255,51,102,0.15)" : "rgba(255,255,255,0.05)"}`,
              borderRadius: 12, padding: 20, textAlign: "center",
            }}>
              <div style={{ fontSize: 9, color: "#4a5068", fontFamily: font, letterSpacing: 1.5, marginBottom: 8 }}>MODEL PREDICTION</div>
              <div style={{
                fontSize: 36, fontFamily: font, fontWeight: 700, letterSpacing: 2,
                color: prediction?.direction === "UP" ? "#00ff87" : prediction?.direction === "DOWN" ? "#ff3366" : "#ffaa00",
              }}>
                {prediction?.direction || "—"}
              </div>
              <div style={{ fontSize: 12, color: "#6b7280", fontFamily: font, marginTop: 4 }}>
                P = {((prediction?.probability || 0.5) * 100).toFixed(1)}% · Conf {((prediction?.confidence || 0) * 100).toFixed(0)}%
              </div>
              <div style={{ marginTop: 12, display: "flex", justifyContent: "center", gap: 16 }}>
                <div>
                  <div style={{ fontSize: 9, color: "#4a5068", fontFamily: font }}>CONFLUENCE</div>
                  <div style={{ fontSize: 14, fontFamily: font, fontWeight: 600, color: "#fff" }}>
                    {prediction ? `${prediction.agreeing}/${prediction.total}` : "—"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 9, color: "#4a5068", fontFamily: font }}>EDGE</div>
                  <div style={{ fontSize: 14, fontFamily: font, fontWeight: 600, color: edgeInfo.edge > 0.05 ? "#00ff87" : "#4a5068" }}>
                    {(edgeInfo.edge * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>

            {/* Polymarket Odds */}
            <div style={{
              background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)",
              borderRadius: 12, padding: 18,
            }}>
              <div style={{ fontSize: 9, color: "#4a5068", fontFamily: font, letterSpacing: 1.5, marginBottom: 12 }}>POLYMARKET ODDS</div>
              <div style={{ display: "flex", gap: 10 }}>
                <div style={{ flex: 1, background: "rgba(0,255,135,0.06)", borderRadius: 8, padding: 12, textAlign: "center" }}>
                  <div style={{ fontSize: 9, color: "#00ff87aa", fontFamily: font }}>UP</div>
                  <div style={{ fontSize: 22, fontFamily: font, fontWeight: 700, color: "#00ff87" }}>{(polymarketOdds.up * 100).toFixed(0)}¢</div>
                </div>
                <div style={{ flex: 1, background: "rgba(255,51,102,0.06)", borderRadius: 8, padding: 12, textAlign: "center" }}>
                  <div style={{ fontSize: 9, color: "#ff3366aa", fontFamily: font }}>DOWN</div>
                  <div style={{ fontSize: 22, fontFamily: font, fontWeight: 700, color: "#ff3366" }}>{(polymarketOdds.down * 100).toFixed(0)}¢</div>
                </div>
              </div>
              {edgeInfo.edge > config.minEdge && prediction?.confidence >= config.minConfidence && (
                <div style={{
                  marginTop: 12, padding: "10px 14px", background: "rgba(0,255,135,0.08)",
                  border: "1px solid rgba(0,255,135,0.2)", borderRadius: 8, textAlign: "center",
                }}>
                  <div style={{ fontSize: 10, fontFamily: font, color: "#00ff87", fontWeight: 600, letterSpacing: 1 }}>
                    ⚡ TRADE SIGNAL: BUY {edgeInfo.side?.toUpperCase()} @ {((edgeInfo.marketPrice || 0) * 100).toFixed(0)}¢
                  </div>
                  <div style={{ fontSize: 10, fontFamily: font, color: "#6b7280", marginTop: 4 }}>
                    Kelly bet: ${kellyBet(edgeInfo.edge, prediction.probability, config.kellyFraction, config.maxBet, config.bankroll)}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Chart */}
          <div style={{
            background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)",
            borderRadius: 12, padding: isMobile ? 12 : 18, display: "flex", flexDirection: "column", gridRow: isMobile ? "auto" : "span 2",
          }}>
            <div style={{ fontSize: 9, color: "#4a5068", fontFamily: font, letterSpacing: 1.5, marginBottom: 10 }}>BTC/USD LIVE</div>
            <div style={{ fontSize: 22, fontFamily: font, fontWeight: 700, color: "#F7931A", marginBottom: 4 }}>
              ${btcPrice ? Number(btcPrice).toLocaleString() : (candles.length > 0 ? candles[candles.length - 1].close.toFixed(2) : "—")}
            </div>
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <MiniChart candles={candles}
                targetPrice={btcPrice || (candles.length > 0 ? candles[candles.length-1].close : 0)}
                windowOpen={activeWindow ? (candles.length > 20 ? candles[candles.length - 20].open : candles[0]?.open || 0) : (candles[0]?.open || 0)}
              />
            </div>

            {/* Recent trades mini */}
            <div style={{ marginTop: 14, maxHeight: 120, overflowY: "auto" }}>
              <div style={{ fontSize: 9, color: "#4a5068", fontFamily: font, letterSpacing: 1.5, marginBottom: 8 }}>RECENT EXECUTIONS</div>
              {trades.slice(0, 5).map((t) => (
                <div key={t.id} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 10, fontFamily: font, borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                  <span style={{ color: "#4a5068" }}>{t.time}</span>
                  <span style={{ color: t.side === "UP" ? "#00ff87" : "#ff3366" }}>{t.side}</span>
                  <span style={{ color: "#6b7280" }}>${t.bet}</span>
                  <span style={{ color: t.result === "WIN" ? "#00ff87" : "#ff3366", fontWeight: 600 }}>
                    {t.result === "WIN" ? "+" : ""}{t.pnl}
                  </span>
                </div>
              ))}
              {trades.length === 0 && <div style={{ fontSize: 10, color: "#2a2e3a", fontFamily: font }}>No trades yet. Enable auto-trade or start engine.</div>}
            </div>
          </div>
        </div>
      )}

      {tab === "strategy" && (
        <div style={{ padding: isMobile ? "12px" : "24px", maxWidth: 720, margin: "0 auto" }}>
          <div style={{ fontSize: 10, color: "#4a5068", fontFamily: font, letterSpacing: 1.5, marginBottom: 20 }}>STRATEGY CONFIGURATION</div>

          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 12, padding: 20, marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: "#fff", fontFamily: font, fontWeight: 600, marginBottom: 16 }}>RISK MANAGEMENT</div>
            {[
              { key: "minConfidence", label: "Min Confidence", min: 0.3, max: 0.95, step: 0.05, fmt: (v) => `${(v * 100).toFixed(0)}%` },
              { key: "minEdge", label: "Min Edge", min: 0.01, max: 0.2, step: 0.01, fmt: (v) => `${(v * 100).toFixed(0)}%` },
              { key: "kellyFraction", label: "Kelly Fraction", min: 0.05, max: 0.5, step: 0.05, fmt: (v) => `${(v * 100).toFixed(0)}%` },
              { key: "maxBet", label: "Max Bet Size", min: 50, max: 2000, step: 50, fmt: (v) => `$${v}` },
              { key: "bankroll", label: "Bankroll", min: 1000, max: 100000, step: 1000, fmt: (v) => `$${v.toLocaleString()}` },
            ].map((s) => (
              <div key={s.key} style={{ marginBottom: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 11, color: "#8892a4", fontFamily: font }}>{s.label}</span>
                  <span style={{ fontSize: 11, color: "#fff", fontFamily: font, fontWeight: 600 }}>{s.fmt(config[s.key])}</span>
                </div>
                <input type="range" min={s.min} max={s.max} step={s.step} value={config[s.key]}
                  onChange={(e) => setConfig((c) => ({ ...c, [s.key]: parseFloat(e.target.value) }))}
                  style={{ width: "100%" }}
                />
              </div>
            ))}
            <button onClick={() => setConfig((c) => ({ ...c, autoTrade: !c.autoTrade }))} style={{
              width: "100%", padding: "12px", borderRadius: 8, fontFamily: font, fontSize: 12, fontWeight: 600,
              cursor: "pointer", letterSpacing: 1, border: "none",
              background: config.autoTrade ? "rgba(0,255,135,0.15)" : "rgba(255,255,255,0.05)",
              color: config.autoTrade ? "#00ff87" : "#4a5068",
            }}>
              {config.autoTrade ? "✓ AUTO-TRADE ENABLED" : "ENABLE AUTO-TRADE"}
            </button>
          </div>

          <div style={{ background: "rgba(255,170,0,0.04)", border: "1px solid rgba(255,170,0,0.15)", borderRadius: 12, padding: 18 }}>
            <div style={{ fontSize: 11, color: "#ffaa00", fontFamily: font, fontWeight: 600, marginBottom: 8 }}>⚠ IMPORTANT DISCLAIMER</div>
            <div style={{ fontSize: 11, color: "#8892a4", lineHeight: 1.7 }}>
              This is a <strong style={{ color: "#ffaa00" }}>simulation/demo dashboard</strong>. No real trades are being placed. Near-100% accuracy on 5-minute crypto predictions is not achievable — markets are adversarial and efficient. Even the best quant firms target 52-55% accuracy on short timeframes with edge coming from volume & execution. This tool demonstrates the architecture for a multi-signal confluence system. To connect to real Polymarket via their CLOB API, you would need: API keys, wallet integration, proper order routing, and extensive backtesting.
            </div>
          </div>

          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 12, padding: 18, marginTop: 16 }}>
            <div style={{ fontSize: 11, color: "#fff", fontFamily: font, fontWeight: 600, marginBottom: 12 }}>SIGNAL WEIGHTS</div>
            {Object.entries(SIGNALS).map(([id, sig]) => (
              <div key={id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                <span style={{ fontSize: 11, color: "#8892a4", fontFamily: font }}>{sig.name}</span>
                <span style={{ fontSize: 11, color: "#6366f1", fontFamily: font }}>{(sig.weight * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "trades" && (
        <div style={{ padding: isMobile ? "12px" : "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
            <div style={{ fontSize: 10, color: "#4a5068", fontFamily: font, letterSpacing: 1.5 }}>TRADE LOG — {stats.trades} EXECUTIONS</div>
            <div style={{ display: "flex", gap: 16 }}>
              <span style={{ fontSize: 11, fontFamily: font, color: "#00ff87" }}>W: {stats.wins}</span>
              <span style={{ fontSize: 11, fontFamily: font, color: "#ff3366" }}>L: {stats.losses}</span>
              <span style={{ fontSize: 11, fontFamily: font, color: stats.pnl >= 0 ? "#00ff87" : "#ff3366", fontWeight: 700 }}>P&L: ${stats.pnl}</span>
            </div>
          </div>

          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 12, overflow: "hidden" }}>
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "60px 40px 50px 50px 45px 50px 45px 60px" : "80px 50px 70px 70px 60px 70px 60px 80px", padding: isMobile ? "8px 10px" : "10px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: isMobile ? 8 : 9, color: "#4a5068", fontFamily: font, letterSpacing: 1 }}>
              <span>TIME</span><span>SIDE</span><span>CONF</span><span>EDGE</span><span>BET</span><span>PRICE</span><span>RESULT</span><span>P&L</span>
            </div>
            <div style={{ maxHeight: 500, overflowY: "auto" }}>
              {trades.map((t) => (
                <div key={t.id} style={{
                  display: "grid", gridTemplateColumns: isMobile ? "60px 40px 50px 50px 45px 50px 45px 60px" : "80px 50px 70px 70px 60px 70px 60px 80px",
                  padding: isMobile ? "6px 10px" : "8px 16px", borderBottom: "1px solid rgba(255,255,255,0.03)",
                  fontSize: 11, fontFamily: font,
                  background: t.result === "WIN" ? "rgba(0,255,135,0.02)" : "rgba(255,51,102,0.02)",
                }}>
                  <span style={{ color: "#6b7280" }}>{t.time}</span>
                  <span style={{ color: t.side === "UP" ? "#00ff87" : "#ff3366", fontWeight: 600 }}>{t.side}</span>
                  <span style={{ color: "#8892a4" }}>{(t.confidence * 100).toFixed(0)}%</span>
                  <span style={{ color: "#6366f1" }}>{(t.edge * 100).toFixed(1)}%</span>
                  <span style={{ color: "#c8cdd8" }}>${t.bet}</span>
                  <span style={{ color: "#8892a4" }}>{(t.marketPrice * 100).toFixed(0)}¢</span>
                  <span style={{ color: t.result === "WIN" ? "#00ff87" : "#ff3366", fontWeight: 600 }}>{t.result}</span>
                  <span style={{ color: t.pnl >= 0 ? "#00ff87" : "#ff3366", fontWeight: 600 }}>{t.pnl >= 0 ? "+" : ""}{t.pnl}</span>
                </div>
              ))}
              {trades.length === 0 && (
                <div style={{ padding: 40, textAlign: "center", color: "#2a2e3a", fontFamily: font, fontSize: 12 }}>
                  No trades yet. Start the engine and enable auto-trade.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══ ANALYSIS TAB ═══ */}
      {tab === "analysis" && <AnalysisPanel font={font} fontSans={fontSans} isMobile={isMobile} />}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════ */
/* Analysis Panel Component                                        */
/* ═══════════════════════════════════════════════════════════════ */
function AnalysisPanel({ font, fontSans, isMobile }) {
  const [tf, setTf] = useState("1h");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const TF_MAP = { "1h": 1, "4h": 4, "8h": 8, "1d": 24, "3d": 72, "1w": 168 };

  useEffect(() => {
    setLoading(true);
    fetch(`/api/btc/analysis?hours=${TF_MAP[tf]}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [tf]);

  // Auto-refresh every 30s
  useEffect(() => {
    const iv = setInterval(() => {
      fetch(`/api/btc/analysis?hours=${TF_MAP[tf]}`)
        .then(r => r.json()).then(d => setData(d)).catch(() => {});
    }, 30000);
    return () => clearInterval(iv);
  }, [tf]);

  const card = { background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 12, padding: isMobile ? 12 : 18 };
  const headStyle = { fontSize: 10, color: "#4a5068", fontFamily: font, letterSpacing: 1.5, marginBottom: 12, textTransform: "uppercase" };

  // P&L line chart
  const PnlChart = ({ cumulative }) => {
    if (!cumulative || cumulative.length < 2) return <div style={{ color: '#4a5068', fontSize: 11, fontFamily: font }}>Not enough data</div>;
    const w = isMobile ? 320 : 500, h = 120, pad = 30;
    const vals = cumulative.map(c => c.running);
    const mn = Math.min(...vals, 0), mx = Math.max(...vals, 0);
    const range = mx - mn || 1;
    const toY = v => pad + ((mx - v) / range) * (h - pad * 2);
    const toX = (i) => pad + (i / (cumulative.length - 1)) * (w - pad * 2);
    const pts = cumulative.map((c, i) => `${toX(i)},${toY(c.running)}`).join(" ");
    const zeroY = toY(0);
    const lastVal = vals[vals.length - 1];
    const lastColor = lastVal >= 0 ? "#00ff87" : "#ff3366";
    return (
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
        <line x1={pad} y1={zeroY} x2={w-pad} y2={zeroY} stroke="rgba(255,255,255,0.1)" strokeDasharray="4,3" />
        <text x={pad-4} y={zeroY+3} fill="#4a5068" fontSize={8} fontFamily={font} textAnchor="end">$0</text>
        <text x={pad-4} y={pad+3} fill="#4a5068" fontSize={8} fontFamily={font} textAnchor="end">${mx >= 0 ? '+' : ''}${mx.toFixed(0)}</text>
        <text x={pad-4} y={h-pad+3} fill="#4a5068" fontSize={8} fontFamily={font} textAnchor="end">${mn.toFixed(0)}</text>
        {/* Fill under line */}
        <polygon points={`${toX(0)},${zeroY} ${pts} ${toX(cumulative.length-1)},${zeroY}`} fill={lastVal >= 0 ? "rgba(0,255,135,0.08)" : "rgba(255,51,102,0.08)"} />
        <polyline points={pts} fill="none" stroke={lastColor} strokeWidth={1.5} />
        {/* Dots for wins/losses */}
        {cumulative.map((c, i) => (
          <circle key={i} cx={toX(i)} cy={toY(c.running)} r={2} fill={c.correct ? "#00ff87" : "#ff3366"} opacity={0.7} />
        ))}
        {/* End label */}
        <rect x={w-pad-40} y={toY(lastVal)-8} width={38} height={16} rx={4} fill={lastColor} opacity={0.9} />
        <text x={w-pad-21} y={toY(lastVal)+4} fill="#000" fontSize={9} fontFamily={font} textAnchor="middle" fontWeight="700">
          {lastVal >= 0 ? '+' : ''}${lastVal.toFixed(0)}
        </text>
      </svg>
    );
  };

  // Bar chart for buckets/hourly
  const BarChart = ({ items, labelKey, valueKey, colorFn }) => {
    if (!items || items.length === 0) return null;
    const maxAbs = Math.max(...items.map(i => Math.abs(i[valueKey] || 0)), 1);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {items.map((item, i) => {
          const val = item[valueKey] || 0;
          const pct = Math.abs(val) / maxAbs * 100;
          const color = colorFn ? colorFn(item) : (val >= 0 ? '#00ff87' : '#ff3366');
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 55, fontSize: 10, fontFamily: font, color: '#8a8fa8', textAlign: 'right', flexShrink: 0 }}>{item[labelKey]}</div>
              <div style={{ flex: 1, height: 16, background: 'rgba(255,255,255,0.03)', borderRadius: 3, overflow: 'hidden', position: 'relative' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: color, opacity: 0.7, borderRadius: 3, transition: 'width 0.5s' }} />
                <span style={{ position: 'absolute', right: 6, top: 2, fontSize: 9, fontFamily: font, color: '#fff', fontWeight: 600 }}>
                  {val >= 0 ? '+' : ''}${val.toFixed(0)}
                </span>
              </div>
              <div style={{ width: 55, fontSize: 9, fontFamily: font, color: '#8a8fa8', flexShrink: 0 }}>
                {item.wins}/{item.trades} ({item.trades > 0 ? (item.wins/item.trades*100).toFixed(0) : 0}%)
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  if (loading && !data) return (
    <div style={{ padding: 40, textAlign: 'center', color: '#4a5068', fontFamily: font }}>
      Loading analysis...
    </div>
  );

  if (!data || data.error) return (
    <div style={{ padding: 40, textAlign: 'center', color: '#ff3366', fontFamily: font }}>
      Error loading analysis: {data?.error || 'No data'}
    </div>
  );

  // Totals from v2_compare
  const allTrades = data.v2_compare?.find(v => v.strategy === 'All Trades');
  const v2Trades = data.v2_compare?.find(v => v.strategy === 'V2 (<70c, 5M)');

  return (
    <div style={{ padding: isMobile ? '12px' : '20px 24px' }}>
      {/* Timeframe Toggle */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
        {Object.keys(TF_MAP).map(t => (
          <button key={t} onClick={() => setTf(t)} style={{
            background: tf === t ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.03)',
            border: tf === t ? '1px solid rgba(99,102,241,0.4)' : '1px solid rgba(255,255,255,0.06)',
            color: tf === t ? '#6366f1' : '#4a5068',
            borderRadius: 8, padding: '7px 16px', fontSize: 12, fontFamily: font,
            fontWeight: tf === t ? 700 : 400, cursor: 'pointer', letterSpacing: 0.5,
            transition: 'all 0.2s',
          }}>
            {t.toUpperCase()}
          </button>
        ))}
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)', gap: isMobile ? 8 : 12, marginBottom: 16 }}>
        <div style={{ ...card, borderLeft: `3px solid ${(allTrades?.net_pnl || 0) >= 0 ? '#00ff87' : '#ff3366'}` }}>
          <div style={headStyle}>NET P&L</div>
          <div style={{ fontSize: isMobile ? 20 : 28, fontFamily: font, fontWeight: 700, color: (allTrades?.net_pnl || 0) >= 0 ? '#00ff87' : '#ff3366' }}>
            {(allTrades?.net_pnl || 0) >= 0 ? '+' : ''}${(allTrades?.net_pnl || 0).toFixed(2)}
          </div>
          <div style={{ fontSize: 10, color: '#4a5068', fontFamily: font, marginTop: 4 }}>Fee-adjusted (2% PM fee)</div>
        </div>
        <div style={{ ...card, borderLeft: '3px solid #6366f1' }}>
          <div style={headStyle}>WIN RATE</div>
          <div style={{ fontSize: isMobile ? 20 : 28, fontFamily: font, fontWeight: 700, color: '#fff' }}>
            {allTrades?.trades > 0 ? (allTrades.wins/allTrades.trades*100).toFixed(1) : '—'}%
          </div>
          <div style={{ fontSize: 10, color: '#4a5068', fontFamily: font, marginTop: 4 }}>{allTrades?.wins || 0}W-{(allTrades?.trades || 0)-(allTrades?.wins || 0)}L</div>
        </div>
        <div style={{ ...card, borderLeft: '3px solid #F7931A' }}>
          <div style={headStyle}>BEST TRADE</div>
          <div style={{ fontSize: isMobile ? 20 : 28, fontFamily: font, fontWeight: 700, color: '#00ff87' }}>
            +${(allTrades?.best || 0).toFixed(2)}
          </div>
          <div style={{ fontSize: 10, color: '#4a5068', fontFamily: font, marginTop: 4 }}>Single trade max</div>
        </div>
        <div style={{ ...card, borderLeft: '3px solid #00ff87' }}>
          <div style={headStyle}>V2 STRATEGY</div>
          <div style={{ fontSize: isMobile ? 20 : 28, fontFamily: font, fontWeight: 700, color: v2Trades?.trades > 0 ? ((v2Trades?.net_pnl || 0) >= 0 ? '#00ff87' : '#ff3366') : '#4a5068' }}>
            {v2Trades?.trades > 0 ? `${(v2Trades?.net_pnl || 0) >= 0 ? '+' : ''}$${(v2Trades?.net_pnl || 0).toFixed(0)}` : 'N/A'}
          </div>
          <div style={{ fontSize: 10, color: '#4a5068', fontFamily: font, marginTop: 4 }}>
            {v2Trades?.trades > 0 ? `${v2Trades.wins}W-${v2Trades.trades-v2Trades.wins}L (<70c, 5M)` : 'Entry <70c, 5M only'}
          </div>
        </div>
      </div>

      {/* Cumulative P&L Chart */}
      <div style={{ ...card, marginBottom: 16 }}>
        <div style={headStyle}>CUMULATIVE P&L</div>
        <PnlChart cumulative={data.cumulative} />
        <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
          <span style={{ fontSize: 9, fontFamily: font, color: '#00ff87' }}>● Win</span>
          <span style={{ fontSize: 9, fontFamily: font, color: '#ff3366' }}>● Loss</span>
          <span style={{ fontSize: 9, fontFamily: font, color: '#4a5068' }}>Trades: {data.cumulative?.length || 0}</span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: isMobile ? 10 : 16 }}>
        {/* Entry Price Buckets */}
        <div style={card}>
          <div style={headStyle}>P&L BY ENTRY PRICE</div>
          <BarChart items={data.buckets} labelKey="bucket" valueKey="net_pnl" />
          <div style={{ marginTop: 10, padding: '8px 10px', background: 'rgba(0,255,135,0.05)', borderRadius: 6, border: '1px solid rgba(0,255,135,0.1)' }}>
            <div style={{ fontSize: 9, fontFamily: font, color: '#00ff87', letterSpacing: 1 }}>V2 ZONE: ENTRY &lt; 70c</div>
            <div style={{ fontSize: 10, fontFamily: font, color: '#8a8fa8', marginTop: 2 }}>Only take trades in top 3 buckets</div>
          </div>
        </div>

        {/* Hourly Heatmap */}
        <div style={card}>
          <div style={headStyle}>HOURLY P&L HEATMAP</div>
          <BarChart items={data.hourly?.map(h => ({ ...h, label: `${h.hour.toString().padStart(2,'0')}:00` }))} labelKey="label" valueKey="net_pnl" />
        </div>

        {/* Confidence Tiers */}
        <div style={card}>
          <div style={headStyle}>CONFIDENCE vs P&L</div>
          <BarChart items={data.confidence} labelKey="tier" valueKey="net_pnl"
            colorFn={(item) => {
              const entry = item.avg_entry || 0;
              return entry < 0.5 ? '#00ff87' : entry < 0.7 ? '#ffaa00' : '#ff3366';
            }}
          />
          <div style={{ marginTop: 10, padding: '8px 10px', background: 'rgba(255,51,102,0.05)', borderRadius: 6, border: '1px solid rgba(255,51,102,0.1)' }}>
            <div style={{ fontSize: 9, fontFamily: font, color: '#ff3366', letterSpacing: 1 }}>⚠️ CONFIDENCE TRAP</div>
            <div style={{ fontSize: 10, fontFamily: font, color: '#8a8fa8', marginTop: 2 }}>High confidence ≠ high profit. Avg entry matters more.</div>
          </div>
        </div>

        {/* Timeframe Comparison */}
        <div style={card}>
          <div style={headStyle}>5M vs 15M</div>
          {data.timeframes?.map((tf, i) => {
            const winPct = tf.trades > 0 ? (tf.wins/tf.trades*100).toFixed(0) : 0;
            const pnlColor = tf.net_pnl >= 0 ? '#00ff87' : '#ff3366';
            return (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <div>
                  <div style={{ fontSize: 14, fontFamily: font, fontWeight: 700, color: '#fff' }}>{tf.wl}</div>
                  <div style={{ fontSize: 10, fontFamily: font, color: '#4a5068' }}>{tf.wins}W-{tf.trades-tf.wins}L ({winPct}%)</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 18, fontFamily: font, fontWeight: 700, color: pnlColor }}>
                    {tf.net_pnl >= 0 ? '+' : ''}${tf.net_pnl.toFixed(0)}
                  </div>
                  <div style={{ fontSize: 10, fontFamily: font, color: '#4a5068' }}>Entry: {(tf.avg_entry*100).toFixed(0)}c</div>
                </div>
              </div>
            );
          })}

          {/* V1 vs V2 comparison */}
          {data.v2_compare && (
            <div style={{ marginTop: 12 }}>
              <div style={{ ...headStyle, marginBottom: 8 }}>STRATEGY COMPARISON</div>
              {data.v2_compare.map((v, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                  <div style={{ fontSize: 11, fontFamily: font, color: v.strategy.includes('V2') ? '#00ff87' : '#8a8fa8' }}>{v.strategy}</div>
                  <div style={{ fontSize: 11, fontFamily: font, fontWeight: 600, color: v.net_pnl >= 0 ? '#00ff87' : '#ff3366' }}>
                    {v.wins}W-{v.trades-v.wins}L | {v.net_pnl >= 0 ? '+' : ''}${v.net_pnl.toFixed(0)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
