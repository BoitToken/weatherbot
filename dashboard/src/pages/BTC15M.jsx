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

const MiniChart = ({ candles }) => {
  if (candles.length < 2) return null;
  const w = 320, h = 100, pad = 2;
  const prices = candles.flatMap((c) => [c.high, c.low]);
  const min = Math.min(...prices), max = Math.max(...prices);
  const range = max - min || 1;
  const barW = Math.max(2, (w - pad * 2) / candles.length - 1);

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      {candles.map((c, i) => {
        const x = pad + i * ((w - pad * 2) / candles.length);
        const yH = pad + ((max - c.high) / range) * (h - pad * 2);
        const yL = pad + ((max - c.low) / range) * (h - pad * 2);
        const yO = pad + ((max - c.open) / range) * (h - pad * 2);
        const yC = pad + ((max - c.close) / range) * (h - pad * 2);
        const bull = c.close >= c.open;
        const col = bull ? "#00ff87" : "#ff3366";
        return (
          <g key={i}>
            <line x1={x + barW / 2} y1={yH} x2={x + barW / 2} y2={yL} stroke={col} strokeWidth={0.8} opacity={0.6} />
            <rect x={x} y={Math.min(yO, yC)} width={barW} height={Math.max(1, Math.abs(yC - yO))} fill={col} rx={0.5} opacity={0.85} />
          </g>
        );
      })}
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
  const [liveWindows, setLiveWindows] = useState([]);
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

    // Fetch real BTC data from our API
    const fetchLive = async () => {
      try {
        const res = await fetch('/api/btc/state');
        const data = await res.json();
        if (data.btc_price) setBtcPrice(data.btc_price);
        if (data.active_windows) setLiveWindows(data.active_windows);
        // Update polymarket odds from live windows
        const activeW = (data.active_windows || []).find(w => w.seconds_remaining > 0);
        if (activeW) {
          setPolymarketOdds({ up: activeW.up_price || 0.5, down: activeW.down_price || 0.5 });
        }
      } catch(e) { /* silent */ }
    };
    fetchLive();
    const liveInterval = setInterval(fetchLive, 3000);
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
          {["dashboard", "strategy", "trades"].map((t) => (
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
              <MiniChart candles={candles} />
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
    </div>
  );
}
