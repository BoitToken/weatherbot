import { useState, useEffect, useRef, useCallback } from "react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { createChart, ColorType, LineStyle } from "lightweight-charts";
import SignalDrillDown from "../components/SignalDrillDown";
import TradeAnalyzer from "../components/TradeAnalyzer";
import StrategyPanel from "../components/StrategyPanel";

/* ═══════════════════════════════════════════════════════════════
   Design tokens — matches BTC15M.jsx exactly
   ═══════════════════════════════════════════════════════════════ */
const C = {
  bg: "#0a0a0f",
  card: "#1a1a2e",
  border: "rgba(255,255,255,0.06)",
  win: "#00ff87",
  loss: "#ff3366",
  accent: "#7c3aed",
  warning: "#f59e0b",
  muted: "#4a5068",
  text: "#c8cdd8",
  white: "#fff",
};
const font = "'JetBrains Mono', 'Fira Code', monospace";

/* ═══════════════════════════════════════════════════════════════
   Hardcoded JC Key Levels (will be dynamic via CDP later)
   ═══════════════════════════════════════════════════════════════ */
const LEVEL_LEVERAGE_MAP = {
  'SPV?': 50, 'SPV of SPV': 50,
  'nwPOC': 45, 'ndPOC': 45, 'KEY / SPs Filled': 45,
  'nfPOC': 40, '0.918 Fib': 40, '0.786 Fib': 40,
  'D Level': 35, 'W (Weekly)': 35,
};

const JC_LEVELS = [
  { price: 75905, label: "SPV?", type: "resistance", color: "#ff3366", note: "Stop sweep zone" },
  { price: 74967, label: "D Level", type: "resistance", color: "#ff3366" },
  { price: 73974, label: "nwPOC", type: "resistance", color: "#f59e0b", note: "naked weekly POC" },
  { price: 72829, label: "SPV of SPV", type: "resistance", color: "#ff3366", note: "NY Open P&D" },
  { price: 71215, label: "SPV?", type: "support", color: "#7c3aed", note: "potential sweep → reversal" },
  { price: 70623, label: "KEY / SPs Filled", type: "support", color: "#00ff87" },
  { price: 69578, label: "0.918 Fib", type: "support", color: "#00ff87" },
  { price: 68517, label: "0.786 Fib", type: "support", color: "#00ff87", note: "Golden Pocket" },
  { price: 68424, label: "ndPOC", type: "support", color: "#f59e0b" },
  { price: 67361, label: "nfPOC", type: "support", color: "#f59e0b", note: "monthly" },
  { price: 65931, label: "W (Weekly)", type: "support", color: "#00ff87" },
];

/* ═══════════════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════════════ */
const fmt = (n, dec = 2) =>
  n == null ? "—" : Number(n).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });

const fmtPnl = (n) => {
  if (n == null) return <span style={{ color: C.muted }}>—</span>;
  const v = Number(n);
  return <span style={{ color: v >= 0 ? C.win : C.loss, fontWeight: 700 }}>{v >= 0 ? "+" : ""}{fmt(v)}</span>;
};

const timeAgo = (ts) => {
  if (!ts) return "";
  const d = new Date(ts);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString();
};

const channelColor = (ch = "") => {
  if (ch.includes("btc")) return C.warning;
  if (ch.includes("eth")) return "#60a5fa";
  if (ch.includes("chart")) return C.accent;
  return C.muted;
};

/* ═══════════════════════════════════════════════════════════════
   Section wrapper
   ═══════════════════════════════════════════════════════════════ */
const Card = ({ children, style }) => (
  <div style={{
    background: C.card,
    border: `1px solid ${C.border}`,
    borderRadius: 12,
    padding: "20px 24px",
    ...style,
  }}>
    {children}
  </div>
);

const SectionTitle = ({ children, style }) => (
  <div style={{ fontSize: 11, fontFamily: font, color: C.muted, letterSpacing: 2, textTransform: "uppercase", marginBottom: 16, ...style }}>
    {children}
  </div>
);

/* ═══════════════════════════════════════════════════════════════
   A. Header bar
   ═══════════════════════════════════════════════════════════════ */
function HeaderBar({ btcPrice, watcherStatus, mode }) {
  const online = watcherStatus?.running;
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      flexWrap: "wrap", gap: 12,
      background: C.card, border: `1px solid ${C.border}`, borderRadius: 12,
      padding: "16px 24px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <span style={{ fontSize: 18, fontFamily: font, fontWeight: 700, color: C.white, letterSpacing: 1 }}>
          👻 JAYSON CASPER — COPY TRADE DESK
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontFamily: font, color: C.text }}>
          <span style={{
            width: 8, height: 8, borderRadius: "50%",
            background: online ? C.win : C.loss,
            boxShadow: online ? `0 0 6px ${C.win}` : "none",
            display: "inline-block",
          }} />
          WATCHER {online ? "LIVE" : "OFF"}
        </div>
        <span style={{
          padding: "4px 10px", borderRadius: 6, fontSize: 11, fontFamily: font, fontWeight: 700,
          background: mode === "live" ? `${C.loss}22` : `${C.accent}22`,
          color: mode === "live" ? C.loss : C.accent,
          border: `1px solid ${mode === "live" ? C.loss : C.accent}44`,
          textTransform: "uppercase",
        }}>
          {mode || "PAPER"}
        </span>
        <span style={{ fontSize: 16, fontFamily: font, fontWeight: 700, color: C.warning, letterSpacing: 1 }}>
          {btcPrice ? `$${fmt(btcPrice, 0)}` : "BTC —"}
        </span>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   B. Interactive Chart — Lightweight Charts + Binance candles
   ═══════════════════════════════════════════════════════════════ */
/* ═══════════════════════════════════════════════════════════════
   Live P&L Panel — professional trading desk style
   ═══════════════════════════════════════════════════════════════ */
function LivePnLPanel({ trade, btcPrice, isMobile }) {
  const [elapsed, setElapsed] = useState('');

  useEffect(() => {
    if (!trade?.opened) return;
    const tick = () => {
      const openTime = new Date(trade.opened).getTime();
      const diff = Math.max(0, Math.floor((Date.now() - openTime) / 1000));
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = diff % 60;
      setElapsed(h > 0 ? `${h}h ${m}m ${s}s` : `${m}m ${s}s`);
    };
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, [trade?.opened]);

  if (!trade) return null;

  const isShort = (trade.direction || '').toUpperCase() === 'SHORT';
  const entry = trade.fill_price || trade.entry;
  const sl = trade.sl;
  const tp1 = trade.tp1;
  const tp2 = trade.tp2;
  const stake = trade.stake || 300;
  const leverage = trade.leverage || 50;
  const price = btcPrice || entry;

  // P&L calculation
  const priceMove = isShort ? (entry - price) : (price - entry);
  const notional = stake * leverage;
  const grossPnl = (priceMove / entry) * notional;
  const fees = notional * 0.00055 * 2; // Bybit taker fee both ways
  const netPnl = grossPnl - fees;
  const pnlPct = (netPnl / stake) * 100;
  const isProfit = netPnl >= 0;

  // Distance to TP1/SL
  const distToTp1 = tp1 ? Math.abs(price - tp1) : null;
  const totalDistTp1 = tp1 ? Math.abs(entry - tp1) : null;
  const tp1Pct = totalDistTp1 ? ((1 - distToTp1 / totalDistTp1) * 100) : null;

  const distToSl = sl ? Math.abs(price - sl) : null;
  const totalDistSl = sl ? Math.abs(entry - sl) : null;
  const slBufferPct = totalDistSl ? ((distToSl / totalDistSl) * 100) : null;

  // Potential P&L at SL/TP
  const slMove = isShort ? (entry - sl) : (sl - entry);
  const slPnl = sl ? (slMove / entry) * notional - fees : null;
  const tp1Move = isShort ? (entry - tp1) : (tp1 - entry);
  const tp1Pnl = tp1 ? (tp1Move / entry) * notional - fees : null;
  const tp2Move = tp2 ? (isShort ? (entry - tp2) : (tp2 - entry)) : null;
  const tp2Pnl = tp2 ? (tp2Move / entry) * notional - fees : null;

  const pnlColor = isProfit ? '#10b981' : '#ef4444';
  const dirEmoji = isShort ? '🔴' : '🟢';
  const dirLabel = isShort ? 'SHORT' : 'LONG';

  return (
    <div style={{
      background: '#0a0a0a',
      border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 10,
      padding: isMobile ? '12px' : '16px 20px',
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', gap: 8,
        paddingBottom: 12, marginBottom: 12,
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 14 }}>{dirEmoji}</span>
          <span style={{
            fontSize: isMobile ? 11 : 13, fontWeight: 700, color: '#fff', letterSpacing: 0.5,
          }}>
            {trade.is_live ? '' : `#${trade.id} `}{dirLabel} from ${fmt(entry)}
          </span>
          {trade.is_live ? (
            <span style={{
              fontSize: 9, fontWeight: 800, color: '#22c55e', letterSpacing: 1,
              background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.3)',
              padding: '2px 8px', borderRadius: 4, textTransform: 'uppercase',
              animation: 'pulse 2s infinite',
            }}>⚡ LIVE BYBIT</span>
          ) : (
            <span style={{
              fontSize: 9, fontWeight: 700, color: '#f59e0b', letterSpacing: 1,
              background: 'rgba(245,158,11,0.1)', padding: '2px 8px', borderRadius: 4,
            }}>📝 PAPER</span>
          )}
        </div>
        <span style={{
          fontSize: 10, color: '#6b7280',
          background: 'rgba(255,255,255,0.05)',
          padding: '3px 8px', borderRadius: 4,
        }}>
          ⏱ {elapsed}
        </span>
      </div>

      {/* Main stats grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, 1fr)',
        gap: isMobile ? 8 : 12,
      }}>
        {/* Current Price */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 6 }}>
          <span style={{ fontSize: 11, color: '#6b7280' }}>Current Price</span>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#F59E0B' }}>${fmt(price)}</span>
        </div>

        {/* Unrealized P&L */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: `${pnlColor}08`, borderRadius: 6, border: `1px solid ${pnlColor}22` }}>
          <span style={{ fontSize: 11, color: '#6b7280' }}>Unrealized P&L</span>
          <span style={{ fontSize: 14, fontWeight: 700, color: pnlColor }}>
            {isProfit ? '+' : ''}${fmt(netPnl)} ({isProfit ? '+' : ''}{pnlPct.toFixed(2)}%)
          </span>
        </div>

        {/* Distance to TP1 */}
        {tp1 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'rgba(16,185,129,0.05)', borderRadius: 6 }}>
            <span style={{ fontSize: 11, color: '#6b7280' }}>Distance to TP1</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#10b981' }}>
              ${fmt(distToTp1)} ({tp1Pct != null ? `${Math.max(0, tp1Pct).toFixed(0)}% to target` : '—'})
            </span>
          </div>
        )}

        {/* Distance to SL */}
        {sl && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'rgba(239,68,68,0.05)', borderRadius: 6 }}>
            <span style={{ fontSize: 11, color: '#6b7280' }}>Distance to SL</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#ef4444' }}>
              ${fmt(distToSl)} ({slBufferPct != null ? `${slBufferPct.toFixed(0)}% buffer` : '—'})
            </span>
          </div>
        )}
      </div>

      {/* Potential P&L row */}
      <div style={{
        display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap',
      }}>
        {slPnl != null && (
          <div style={{ flex: 1, minWidth: 100, padding: '6px 10px', background: 'rgba(239,68,68,0.08)', borderRadius: 6, textAlign: 'center' }}>
            <div style={{ fontSize: 9, color: '#6b7280', letterSpacing: 1, marginBottom: 2 }}>IF SL HIT</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#ef4444' }}>${fmt(slPnl)}</div>
          </div>
        )}
        {tp1Pnl != null && (
          <div style={{ flex: 1, minWidth: 100, padding: '6px 10px', background: 'rgba(16,185,129,0.08)', borderRadius: 6, textAlign: 'center' }}>
            <div style={{ fontSize: 9, color: '#6b7280', letterSpacing: 1, marginBottom: 2 }}>IF TP1 HIT</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#10b981' }}>+${fmt(tp1Pnl)}</div>
          </div>
        )}
        {tp2Pnl != null && (
          <div style={{ flex: 1, minWidth: 100, padding: '6px 10px', background: 'rgba(16,185,129,0.08)', borderRadius: 6, textAlign: 'center' }}>
            <div style={{ fontSize: 9, color: '#6b7280', letterSpacing: 1, marginBottom: 2 }}>IF TP2 HIT</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#10b981' }}>+${fmt(tp2Pnl)}</div>
          </div>
        )}
      </div>

      {/* Trade details footer */}
      <div style={{
        display: 'flex', gap: 16, marginTop: 12, paddingTop: 10,
        borderTop: '1px solid rgba(255,255,255,0.06)',
        flexWrap: 'wrap',
      }}>
        {[
          { label: 'Stake', value: `$${fmt(stake, 0)}` },
          { label: 'Leverage', value: `${leverage}x` },
          { label: 'Notional', value: `$${fmt(notional, 0)}` },
          { label: 'R:R', value: trade.rr ? `${Number(trade.rr).toFixed(1)}:1` : '—' },
          ...(trade.is_live ? [
            { label: 'Size', value: `${trade.size_btc} BTC` },
            { label: 'Liq Price', value: trade.liq_price ? `$${fmt(trade.liq_price, 0)}` : '—' },
          ] : []),
        ].map(({ label, value }) => (
          <div key={label} style={{ fontSize: 10 }}>
            <span style={{ color: '#4a5068' }}>{label}: </span>
            <span style={{ color: '#9ca3af', fontWeight: 600 }}>{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TVChart({ isMobile, btcPrice, activeTrade }) {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const tradePriceLines = useRef([]);
  const btcPriceLine = useRef(null);
  const [chartTab, setChartTab] = useState("interactive"); // "interactive" | "jayson"
  const [chartData, setChartData] = useState([]);
  const [hoveredLevel, setHoveredLevel] = useState(null);
  const [selectedLevel, setSelectedLevel] = useState(null);
  const [imgTs, setImgTs] = useState(Date.now());
  const [lastUpdate, setLastUpdate] = useState(null);
  const [timeframe, setTimeframe] = useState("5m");

  // Fetch candle data from Binance
  const fetchCandles = useCallback(async () => {
    try {
      const res = await fetch(
        `https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=${timeframe}&limit=300`
      );
      const klines = await res.json();
      if (!Array.isArray(klines)) return;
      const candles = klines.map((k) => ({
        time: Math.floor(k[0] / 1000),
        open: parseFloat(k[1]),
        high: parseFloat(k[2]),
        low: parseFloat(k[3]),
        close: parseFloat(k[4]),
        volume: parseFloat(k[5]),
      }));
      setChartData(candles);
      setLastUpdate(new Date());
    } catch (e) {
      console.error("Failed to fetch candles:", e);
    }
  }, [timeframe]);

  // Initial fetch + auto-refresh every 30s
  useEffect(() => {
    fetchCandles();
    const iv = setInterval(fetchCandles, 30000);
    return () => clearInterval(iv);
  }, [fetchCandles]);

  // Jayson tab image refresh
  useEffect(() => {
    const iv = setInterval(() => setImgTs(Date.now()), 30000);
    return () => clearInterval(iv);
  }, []);

  // Create/update lightweight chart
  useEffect(() => {
    if (chartTab !== "interactive" || !chartContainerRef.current || !chartData.length) return;

    // Clean up previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
    }

    const chartHeight = isMobile ? 400 : 560;
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: chartHeight,
      layout: {
        background: { type: ColorType.Solid, color: '#0a0a0f' },
        textColor: '#8a8f9e',
        fontFamily: font,
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.03)' },
        horzLines: { color: 'rgba(255,255,255,0.03)' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: 'rgba(124,58,237,0.4)', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#7c3aed' },
        horzLine: { color: 'rgba(124,58,237,0.4)', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#7c3aed' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: 'rgba(255,255,255,0.06)',
        rightOffset: 12,
        barSpacing: 8,
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.06)',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      handleScroll: { vertTouchDrag: false },
    });

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00ff87',
      downColor: '#ff3366',
      borderUpColor: '#00ff87',
      borderDownColor: '#ff3366',
      wickUpColor: 'rgba(0,255,135,0.5)',
      wickDownColor: 'rgba(255,51,102,0.5)',
    });
    candleSeries.setData(chartData);

    // Volume series (overlay)
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });
    volumeSeries.setData(
      chartData.map((d) => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(0,255,135,0.15)' : 'rgba(255,51,102,0.15)',
      }))
    );

    // Draw JC levels as price lines
    JC_LEVELS.forEach((level) => {
      const isResistance = level.type === 'resistance';
      candleSeries.createPriceLine({
        price: level.price,
        color: level.color + 'cc',
        lineWidth: isResistance ? 2 : 1,
        lineStyle: level.label.includes('POC') ? LineStyle.Dotted : LineStyle.Solid,
        axisLabelVisible: true,
        title: `${level.label} $${level.price.toLocaleString()}`,
      });
    });

    // Fit content
    chart.timeScale().fitContent();

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
    };
  }, [chartData, chartTab, isMobile]);

  // Separate useEffect for BTC price line — updates in-place without chart rebuild
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;

    // Remove old BTC price line
    if (btcPriceLine.current) {
      try { series.removePriceLine(btcPriceLine.current); } catch (e) {}
      btcPriceLine.current = null;
    }

    if (btcPrice) {
      btcPriceLine.current = series.createPriceLine({
        price: btcPrice,
        color: '#f59e0b',
        lineWidth: 1,
        lineStyle: LineStyle.SparseDotted,
        axisLabelVisible: true,
        title: `BTC $${btcPrice.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
      });
    }
  }, [btcPrice]);

  // Separate useEffect for active trade lines — updates instantly on override/revert
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;

    // Remove old trade price lines
    tradePriceLines.current.forEach(line => {
      try { series.removePriceLine(line); } catch (e) {}
    });
    tradePriceLines.current = [];

    if (activeTrade && activeTrade.status === 'active') {
      const t = activeTrade;
      const entry = t.fill_price || t.entry;
      const isShort = (t.direction || '').toUpperCase() === 'SHORT';
      const notional = (t.stake || 300) * (t.leverage || 50);
      const feesCost = notional * 0.00055 * 2;

      if (entry) {
        tradePriceLines.current.push(series.createPriceLine({
          price: entry,
          color: '#60a5fa',
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `ENTRY $${entry.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
        }));
      }
      if (t.sl) {
        const slMove = isShort ? (entry - t.sl) : (t.sl - entry);
        const slPnl = (slMove / entry) * notional - feesCost;
        const slManual = t.manual_override ? ' (MANUAL)' : '';
        tradePriceLines.current.push(series.createPriceLine({
          price: t.sl,
          color: t.manual_override ? '#F59E0B' : '#ef4444',
          lineWidth: 3,
          lineStyle: LineStyle.Solid,
          axisLabelVisible: true,
          title: `SL $${t.sl.toLocaleString(undefined, { minimumFractionDigits: 2 })} (${slPnl >= 0 ? '+' : ''}$${slPnl.toFixed(0)})${slManual}`,
        }));
      }
      if (t.tp1) {
        const tp1Move = isShort ? (entry - t.tp1) : (t.tp1 - entry);
        const tp1Pnl = (tp1Move / entry) * notional - feesCost;
        const tp1Manual = t.manual_override ? ' (MANUAL)' : '';
        tradePriceLines.current.push(series.createPriceLine({
          price: t.tp1,
          color: t.manual_override ? '#F59E0B' : '#10b981',
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `TP1 $${t.tp1.toLocaleString(undefined, { minimumFractionDigits: 2 })} (+$${tp1Pnl.toFixed(0)})${tp1Manual}`,
        }));
      }
      if (t.tp2) {
        const tp2Move = isShort ? (entry - t.tp2) : (t.tp2 - entry);
        const tp2Pnl = (tp2Move / entry) * notional - feesCost;
        const tp2Manual = t.manual_override ? ' (MANUAL)' : '';
        tradePriceLines.current.push(series.createPriceLine({
          price: t.tp2,
          color: t.manual_override ? '#F59E0B' : '#10b981',
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `TP2 $${t.tp2.toLocaleString(undefined, { minimumFractionDigits: 2 })} (+$${tp2Pnl.toFixed(0)})${tp2Manual}`,
        }));
      }
    }
  }, [activeTrade]);

  // Level tooltip on hover/click
  const LevelTooltip = ({ level, onClose }) => {
    if (!level) return null;
    const dist = btcPrice ? ((level.price - btcPrice) / btcPrice * 100).toFixed(2) : null;
    const isAbove = dist > 0;
    return (
      <div style={{
        position: 'absolute', top: 60, right: 16, zIndex: 10,
        background: '#1a1a2e', border: `1px solid ${level.color}44`,
        borderRadius: 10, padding: '16px 20px', minWidth: 240,
        boxShadow: `0 8px 32px rgba(0,0,0,0.5)`,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <span style={{ fontSize: 13, fontFamily: font, fontWeight: 700, color: level.color }}>{level.label}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: C.muted, cursor: 'pointer', fontSize: 16 }}>&times;</button>
        </div>
        <div style={{ fontSize: 20, fontFamily: font, fontWeight: 700, color: C.white, marginBottom: 8 }}>
          ${level.price.toLocaleString()}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, fontFamily: font }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: C.muted }}>Type</span>
            <span style={{ color: level.type === 'resistance' ? C.loss : C.win, fontWeight: 600, textTransform: 'uppercase' }}>{level.type}</span>
          </div>
          {dist && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: C.muted }}>Distance</span>
              <span style={{ color: isAbove ? C.loss : C.win, fontWeight: 600 }}>{isAbove ? '+' : ''}{dist}%</span>
            </div>
          )}
          {level.note && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: C.muted }}>Note</span>
              <span style={{ color: C.text }}>{level.note}</span>
            </div>
          )}
          <div style={{ marginTop: 8, padding: '8px 10px', background: '#0a0a0f', borderRadius: 6, borderLeft: `3px solid ${level.color}` }}>
            <div style={{ fontSize: 10, color: C.muted, marginBottom: 4, letterSpacing: 1 }}>TRADE IDEA</div>
            <div style={{ fontSize: 11, color: C.text, lineHeight: 1.5 }}>
              {level.type === 'support'
                ? `LONG @ $${level.price.toLocaleString()} — SL below $${(level.price * 0.995).toLocaleString(undefined, { maximumFractionDigits: 0 })}, TP at next resistance`
                : `SHORT @ $${level.price.toLocaleString()} — SL above $${(level.price * 1.005).toLocaleString(undefined, { maximumFractionDigits: 0 })}, TP at next support`
              }
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div>
      {/* Tab buttons + timeframe selector */}
      <div style={{ display: 'flex', gap: 6, padding: '8px 12px', background: C.bg, alignItems: 'center', flexWrap: 'wrap' }}>
        <button onClick={() => setChartTab('interactive')} style={{
          background: chartTab === 'interactive' ? 'rgba(255,255,255,0.08)' : 'transparent',
          border: chartTab === 'interactive' ? '1px solid rgba(255,255,255,0.12)' : '1px solid transparent',
          color: chartTab === 'interactive' ? C.white : C.muted, borderRadius: 6, padding: '5px 12px',
          fontSize: 10, fontFamily: font, cursor: 'pointer', letterSpacing: 1, minHeight: 32,
        }}>⚡ INTERACTIVE CHART</button>
        <button onClick={() => setChartTab('jayson')} style={{
          background: chartTab === 'jayson' ? 'rgba(124,58,237,0.15)' : 'transparent',
          border: chartTab === 'jayson' ? '1px solid rgba(124,58,237,0.3)' : '1px solid transparent',
          color: chartTab === 'jayson' ? C.accent : C.muted, borderRadius: 6, padding: '5px 12px',
          fontSize: 10, fontFamily: font, cursor: 'pointer', letterSpacing: 1, minHeight: 32,
        }}>👻 JAYSON LIVE (CDP)</button>

        {chartTab === 'interactive' && (
          <>
            <span style={{ flex: 1 }} />
            {['1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => (
              <button key={tf} onClick={() => setTimeframe(tf)} style={{
                background: timeframe === tf ? `${C.accent}22` : 'transparent',
                border: timeframe === tf ? `1px solid ${C.accent}44` : '1px solid transparent',
                color: timeframe === tf ? C.accent : C.muted, borderRadius: 4, padding: '3px 8px',
                fontSize: 10, fontFamily: font, cursor: 'pointer', letterSpacing: 0.5,
              }}>{tf.toUpperCase()}</button>
            ))}
          </>
        )}
      </div>

      {/* Interactive Chart (lightweight-charts) */}
      {chartTab === 'interactive' && (
        <Card style={{ padding: 0, overflow: 'hidden', position: 'relative' }}>
          {/* Chart header overlay */}
          <div style={{ position: 'absolute', top: 8, left: 12, zIndex: 5, display: 'flex', gap: 8, alignItems: 'center', pointerEvents: 'none' }}>
            <span style={{ fontSize: 9, color: C.win, fontFamily: font, letterSpacing: 1, background: 'rgba(0,0,0,0.85)', padding: '3px 8px', borderRadius: 4 }}>
              ⚡ BTC/USDT • {timeframe.toUpperCase()} • BINANCE
            </span>
            {lastUpdate && (
              <span style={{ fontSize: 8, color: C.muted, fontFamily: font, background: 'rgba(0,0,0,0.7)', padding: '2px 6px', borderRadius: 3 }}>
                Updated {lastUpdate.toLocaleTimeString()}
              </span>
            )}
            <span style={{ fontSize: 8, color: C.accent, fontFamily: font, background: 'rgba(0,0,0,0.7)', padding: '2px 6px', borderRadius: 3 }}>
              {JC_LEVELS.length} JC LEVELS
            </span>
          </div>

          {/* Chart container */}
          <div ref={chartContainerRef} style={{ width: '100%', height: isMobile ? 400 : 560, background: '#0a0a0f' }} />

          {/* Level selector panel */}
          <div style={{
            display: 'flex', gap: 4, padding: '8px 12px', background: '#0d0d18',
            borderTop: `1px solid ${C.border}`, overflowX: 'auto', flexWrap: 'nowrap',
          }}>
            {JC_LEVELS.map((level) => {
              const isSelected = selectedLevel?.price === level.price;
              const dist = btcPrice ? ((level.price - btcPrice) / btcPrice * 100) : 0;
              const isNear = Math.abs(dist) < 0.5;
              return (
                <button
                  key={level.price}
                  onClick={() => setSelectedLevel(isSelected ? null : level)}
                  onMouseEnter={() => setHoveredLevel(level)}
                  onMouseLeave={() => setHoveredLevel(null)}
                  style={{
                    background: isSelected ? `${level.color}22` : isNear ? `${C.warning}11` : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${isSelected ? level.color + '66' : isNear ? C.warning + '44' : 'rgba(255,255,255,0.06)'}`,
                    borderRadius: 6, padding: '4px 8px', cursor: 'pointer',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1,
                    flexShrink: 0, minWidth: 72, transition: 'all 0.15s ease',
                  }}
                >
                  <span style={{ fontSize: 10, fontFamily: font, fontWeight: 700, color: level.color }}>
                    ${(level.price / 1000).toFixed(1)}k
                  </span>
                  <span style={{ fontSize: 8, fontFamily: font, color: C.muted, whiteSpace: 'nowrap' }}>
                    {level.label}
                  </span>
                  {isNear && (
                    <span style={{ fontSize: 7, fontFamily: font, color: C.warning, fontWeight: 700 }}>NEAR</span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Level tooltip */}
          <LevelTooltip level={selectedLevel || hoveredLevel} onClose={() => { setSelectedLevel(null); setHoveredLevel(null); }} />
        </Card>
      )}

      {/* Jayson CDP tab (static image fallback) */}
      {chartTab === 'jayson' && (
        <Card style={{ padding: 0, overflow: 'hidden', position: 'relative' }}>
          <div style={{ position: 'absolute', top: 8, left: 12, zIndex: 2, display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 9, color: C.accent, fontFamily: font, letterSpacing: 1, background: 'rgba(0,0,0,0.8)', padding: '3px 8px', borderRadius: 4 }}>
              JAYSON CASPER LIVE CHART
            </span>
            <span style={{ fontSize: 8, color: C.muted, fontFamily: font, background: 'rgba(0,0,0,0.7)', padding: '2px 6px', borderRadius: 3 }}>
              Auto-refresh 30s
            </span>
          </div>
          <img src={'/tv-live.png?' + imgTs} alt="Jayson Chart"
            onError={(e) => { e.target.style.display = 'none'; }}
            style={{ width: '100%', height: isMobile ? 380 : 550, objectFit: 'cover', display: 'block' }} />
        </Card>
      )}

      {/* Live P&L Panel — below chart when trade is active */}
      {activeTrade && activeTrade.status === 'active' && (
        <LivePnLPanel trade={activeTrade} btcPrice={btcPrice} isMobile={isMobile} />
      )}
    </div>
  );
}

/* ─── Signal Feed helpers ───────────────────────────────────── */
function cleanContent(text) {
  if (!text) return '';
  let cleaned = text.replace(/<@[&!]?\d+>/g, '').trim();
  cleaned = cleaned.replace(/<#\d+>/g, '').trim();
  // Strip bare URLs from display text (shown as buttons instead)
  cleaned = cleaned.replace(/https?:\/\/(?:www\.)?tradingview\.com\/\S+/g, '').trim();
  return cleaned;
}

function classifyMessage(text) {
  const t = (text || '').toLowerCase();
  const hasTV = /tradingview\.com/.test(t);
  if (hasTV || t.includes('full chart') || t.includes('my chart'))
    return { type: 'chart', emoji: '📊', label: 'FULL CHART', color: '#7c3aed' };
  if (t.includes('tp') || t.includes('take profit') || t.includes('hit a tp'))
    return { type: 'tp', emoji: '✅', label: 'TP HIT', color: '#00ff87' };
  if (t.includes('stopped') || t.includes('stop loss') || t.includes('not the low'))
    return { type: 'loss', emoji: '❌', label: 'STOPPED', color: '#ff3366' };
  if (t.includes('long') || t.includes('short') || t.includes('scalp'))
    return { type: 'signal', emoji: '⚡', label: 'TRADE SIGNAL', color: '#f59e0b' };
  return { type: 'message', emoji: '💬', label: null, color: '#4a5068' };
}

function extractTVLink(text) {
  const match = (text || '').match(/https?:\/\/(?:www\.)?tradingview\.com\/\S+/);
  return match ? match[0] : null;
}

function formatTimestamp(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const diffMin = (now - d) / 60000;
  if (diffMin < 60) return `${Math.round(diffMin)}m ago`;
  if (diffMin < 1440) return `${Math.round(diffMin / 60)}h ago`;
  return (
    d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ', ' +
    d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
  );
}

/* C. Signal Feed — single message card
   ═══════════════════════════════════════════════════════════════ */
function cleanMsg(text) {
  if (!text) return '';
  let c = text.replace(/<@[&!]?\d+>/g, '').replace(/<#\d+>/g, '').trim();
  c = c.replace(/https?:\/\/\S+/g, '').trim();
  return c;
}

function classifyMsg(text) {
  const t = (text || '').toLowerCase();
  if (t.includes('full chart') || t.includes('my chart')) return { tag: 'CHART', emoji: String.fromCodePoint(0x1F4CA), color: C.accent };
  if ((t.includes("i've") || t.includes("ive")) && (t.includes('long') || t.includes('short')) || t.includes('scalped') || t.includes('i shorted'))
    return { tag: 'ENTRY', emoji: String.fromCodePoint(0x26A1), color: C.warning };
  if (t.includes('hit a tp') || t.includes('tp hit') || t.includes('nice move') || t.includes('take profit'))
    return { tag: 'TP HIT', emoji: String.fromCodePoint(0x2705), color: C.win };
  if (t.includes('stopped') || t.includes('not the low') || t.includes('invalidated'))
    return { tag: 'STOPPED', emoji: String.fromCodePoint(0x274C), color: C.loss };
  if (t.includes('mcb') || t.includes('poc') || t.includes('vah') || t.includes('val') || t.includes('fib') || t.includes('cdw'))
    return { tag: 'TA', emoji: String.fromCodePoint(0x1F9E0), color: '#60a5fa' };
  return { tag: '', emoji: String.fromCodePoint(0x1F4AC), color: C.muted };
}

function fmtTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const diffMin = (now - d) / 60000;
  if (diffMin < 60) return Math.round(diffMin) + 'm ago';
  if (diffMin < 1440) return Math.round(diffMin / 60) + 'h ago';
  if (diffMin < 10080) return Math.round(diffMin / 1440) + 'd ago';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function getTVLink(text) {
  const m = (text || '').match(/https?:\/\/(?:www\.)?tradingview\.com\/\S+/);
  return m ? m[0] : null;
}

function SignalFeed({ messages }) {
  const sorted = [...(messages || [])].sort((a, b) => {
    return new Date(b.created_at || b.timestamp || 0) - new Date(a.created_at || a.timestamp || 0);
  });
  const recent = sorted.filter(m => {
    const t = (m.content || m.message || '').toLowerCase();
    return t.includes('long') || t.includes('short') || t.includes('tp') || t.includes('chart') || t.includes('mcb') || t.includes('poc') || t.includes('cdw') || t.includes('fib') || t.includes('scalp');
  }).slice(0, 3);
  const items = recent.length > 0 ? recent : sorted.slice(0, 3);

  return (
    <Card>
      <SectionTitle>{String.fromCodePoint(0x1F4E1)} Jayson Casper</SectionTitle>
      {items.length === 0 ? (
        <div style={{ textAlign: "center", padding: 20, color: C.muted, fontSize: 12, fontFamily: font }}>
          {String.fromCodePoint(0x1F47B)} Listening for signals...
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {items.map((m, i) => {
            const raw = m.content || m.message || '';
            const text = cleanMsg(raw);
            if (!text && !m.has_attachments) return null;
            const cls = classifyMsg(raw);
            const tv = getTVLink(raw);
            const ch = (m.channel_type || m.channel || 'btc-ta').replace('_', '-');
            return (
              <div key={m.id || i} style={{
                borderLeft: `3px solid ${cls.color}`,
                background: '#0d0d18',
                padding: '8px 10px',
                borderRadius: '0 6px 6px 0',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 2 }}>
                  <span style={{ fontSize: 12 }}>{cls.emoji}</span>
                  {cls.tag && <span style={{ fontSize: 9, fontFamily: font, color: cls.color, fontWeight: 700 }}>{cls.tag}</span>}
                  <span style={{ flex: 1 }} />
                  <span style={{ fontSize: 9, fontFamily: font, color: C.muted }}>#{ch}</span>
                  <span style={{ fontSize: 9, fontFamily: font, color: C.muted }}>{fmtTime(m.created_at || m.timestamp)}</span>
                </div>
                <div style={{ fontSize: 12, color: C.text, lineHeight: 1.4, fontFamily: "'Inter', sans-serif", wordBreak: 'break-word' }}>
                  {text.slice(0, 120)}{text.length > 120 ? '...' : ''}
                </div>
                {tv && (
                  <a href={tv} target="_blank" rel="noopener noreferrer"
                    style={{ fontSize: 10, color: C.accent, fontFamily: font, textDecoration: 'none', marginTop: 3, display: 'inline-block' }}
                    onClick={e => e.stopPropagation()}>
                    {String.fromCodePoint(0x1F4CA)} View Chart {String.fromCodePoint(0x2192)}
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

/* ═══════════════════════════════════════════════════════════════
   TAB: SIGNALS
   ═══════════════════════════════════════════════════════════════ */
function SignalsTab({ btcPrice, position, messages, signals }) {
  // Determine current price zone
  const price = btcPrice || 0;

  const resistanceLevels = JC_LEVELS.filter(l => l.type === "resistance").sort((a, b) => b.price - a.price);
  const supportLevels = JC_LEVELS.filter(l => l.type === "support").sort((a, b) => b.price - a.price);

  // Recent messages feed (last 5)
  const all = [...(signals || []), ...(messages || [])];
  const seen = new Set();
  const feedItems = all.filter(m => {
    const k = m.id || m.message_id || (m.content || m.message || "") + (m.created_at || m.timestamp || "");
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  }).sort((a, b) => new Date(b.created_at || b.timestamp || 0) - new Date(a.created_at || a.timestamp || 0)).slice(0, 5);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Key Levels Card */}
      <Card>
        <SectionTitle>🗺 Jayson's Key Levels</SectionTitle>

        {/* Resistance */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 10, fontFamily: font, color: C.loss, letterSpacing: 1.5, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            🔴 RESISTANCE
          </div>
          {resistanceLevels.map((lvl) => (
            <div key={lvl.price} style={{
              display: "flex", alignItems: "center", gap: 12,
              padding: "7px 12px", borderRadius: 8, marginBottom: 4,
              background: "rgba(255,51,102,0.05)", border: `1px solid rgba(255,51,102,0.1)`,
            }}>
              <div style={{ width: 3, height: 20, borderRadius: 2, background: lvl.color, flexShrink: 0 }} />
              <span style={{ fontSize: 14, fontFamily: font, fontWeight: 700, color: C.white, minWidth: 80 }}>
                ${lvl.price.toLocaleString()}
              </span>
              <span style={{ fontSize: 12, fontFamily: font, color: lvl.color, fontWeight: 600 }}>{lvl.label}</span>
              {lvl.note && <span style={{ fontSize: 10, fontFamily: font, color: C.muted }}>— {lvl.note}</span>}
              {price > 0 && Math.abs(price - lvl.price) / price < 0.005 && (
                <span style={{ marginLeft: "auto", fontSize: 9, fontFamily: font, color: C.warning, background: `${C.warning}22`, padding: "2px 6px", borderRadius: 4 }}>NEAR</span>
              )}
            </div>
          ))}
        </div>

        {/* Current Price */}
        <div style={{
          padding: "10px 16px", borderRadius: 8, marginBottom: 12,
          background: `${C.warning}11`, border: `1px solid ${C.warning}44`,
          display: "flex", alignItems: "center", gap: 12,
        }}>
          <span style={{ fontSize: 11, fontFamily: font, color: C.warning }}>⚡ CURRENT</span>
          <span style={{ fontSize: 18, fontFamily: font, fontWeight: 700, color: C.warning }}>
            {btcPrice ? `$${fmt(btcPrice, 0)}` : "Loading..."}
          </span>
        </div>

        {/* Support */}
        <div>
          <div style={{ fontSize: 10, fontFamily: font, color: C.win, letterSpacing: 1.5, marginBottom: 8 }}>
            🟢 SUPPORT
          </div>
          {supportLevels.map((lvl) => (
            <div key={lvl.price} style={{
              display: "flex", alignItems: "center", gap: 12,
              padding: "7px 12px", borderRadius: 8, marginBottom: 4,
              background: "rgba(0,255,135,0.03)", border: `1px solid rgba(0,255,135,0.08)`,
            }}>
              <div style={{ width: 3, height: 20, borderRadius: 2, background: lvl.color, flexShrink: 0 }} />
              <span style={{ fontSize: 14, fontFamily: font, fontWeight: 700, color: C.white, minWidth: 80 }}>
                ${lvl.price.toLocaleString()}
              </span>
              <span style={{ fontSize: 12, fontFamily: font, color: lvl.color, fontWeight: 600 }}>{lvl.label}</span>
              {lvl.note && <span style={{ fontSize: 10, fontFamily: font, color: C.muted }}>— {lvl.note}</span>}
              {price > 0 && Math.abs(price - lvl.price) / price < 0.005 && (
                <span style={{ marginLeft: "auto", fontSize: 9, fontFamily: font, color: C.warning, background: `${C.warning}22`, padding: "2px 6px", borderRadius: 4 }}>NEAR</span>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Trade Setup Card */}
      <Card>
        <SectionTitle>📐 Trade Setup</SectionTitle>
        {(() => {
          const p = btcPrice || 0;
          const nearSupport = supportLevels.find(l => l.price < p) || supportLevels[0];
          const nearResist = resistanceLevels.find(l => l.price > p) || resistanceLevels[0];
          const distSupport = nearSupport ? ((p - nearSupport.price) / p * 100).toFixed(2) : null;
          const distResist = nearResist ? ((nearResist.price - p) / p * 100).toFixed(2) : null;
          const bias = distSupport && distResist ? (Number(distSupport) < Number(distResist) ? "NEAR SUPPORT — LONG BIAS" : "NEAR RESISTANCE — SHORT BIAS") : "NEUTRAL";
          const biasColor = bias.includes("LONG") ? C.win : bias.includes("SHORT") ? C.loss : C.warning;
          const setup = nearSupport ? `LONG at ${nearSupport.label} ($${fmt(nearSupport.price, 0)})` : "—";
          const sl = nearSupport ? `$${fmt(nearSupport.price * 0.995, 0)}` : "—";
          const tp1 = nearResist ? `$${fmt(nearResist.price, 0)} (${nearResist.label})` : "—";
          const tp2 = resistanceLevels.length > 1 ? `$${fmt(resistanceLevels[1]?.price || 0, 0)}` : "—";
          return (
            <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "8px 20px", fontSize: 13, fontFamily: font }}>
              {[
                { label: "Bias", value: bias, color: biasColor },
                { label: "Nearest Support", value: nearSupport ? `${nearSupport.label} — $${fmt(nearSupport.price, 0)} (${distSupport}% away)` : "—", color: C.win },
                { label: "Nearest Resistance", value: nearResist ? `${nearResist.label} — $${fmt(nearResist.price, 0)} (${distResist}% away)` : "—", color: C.loss },
                { label: "Long Setup", value: setup, color: C.text },
                { label: "SL", value: sl, color: C.loss },
                { label: "TP1", value: tp1, color: C.win },
              ].map(({ label, value, color }) => (
                              <div key={label} style={{ display: "contents" }}>
                  <span style={{ color: C.muted, fontSize: 11, letterSpacing: 1, textTransform: "uppercase", paddingTop: 2 }}>{label}</span>
                  <span style={{ color, fontWeight: 600 }}>{value}</span>
                              </div>
              ))}
            </div>
          );
        })()}
      </Card>

      {/* Discord Signal Feed (last 5) */}
      <SignalFeed messages={feedItems} />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   TAB: TRADES
   ═══════════════════════════════════════════════════════════════ */
function TradesTab({ trades, pnlStats, isMobile }) {
  const [expandedId, setExpandedId] = useState(null);
  const rows = (trades || []).slice(0, 20);

  const balance = pnlStats?.balance ?? pnlStats?.total_balance ?? 10000;
  const totalPnl = pnlStats?.total_pnl ?? null;
  const winRate = pnlStats?.win_rate != null ? (pnlStats.win_rate * 100).toFixed(1) : null;
  const totalTrades = pnlStats?.total_trades ?? rows.length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Bankroll */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "repeat(2, 1fr)" : "repeat(4, 1fr)", gap: 12 }}>
        {[
          { label: "Balance", value: balance != null ? `$${fmt(balance, 0)}` : "—", color: C.white, big: true },
          { label: "Total P&L", value: totalPnl != null ? `${Number(totalPnl) >= 0 ? "+" : ""}$${fmt(totalPnl)}` : "—", color: Number(totalPnl) >= 0 ? C.win : C.loss, big: true },
          { label: "Win Rate", value: winRate != null ? `${winRate}%` : "—", color: Number(winRate) >= 50 ? C.win : C.loss },
          { label: "Total Trades", value: totalTrades ?? "—", color: C.accent },
        ].map(({ label, value, color, big }) => (
          <div key={label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: "16px", textAlign: "center" }}>
            <div style={{ fontSize: 9, fontFamily: font, color: C.muted, letterSpacing: 1, marginBottom: 8, textTransform: "uppercase" }}>{label}</div>
            <div style={{ fontSize: big ? 22 : 18, fontFamily: font, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Trade History */}
      <Card>
        <SectionTitle>📋 Trade History (Last 20)</SectionTitle>
        {rows.length === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: C.muted, fontSize: 13, fontFamily: font }}>
            No trades yet
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {rows.map((t, i) => {
              const id = t.id || i;
              const isExpanded = expandedId === id;
              const pnl = Number(t.pnl ?? t.realized_pnl ?? 0);
              const isLong = (t.side || "").toUpperCase() === "LONG";
              const dur = t.duration_sec != null ? `${Math.floor(t.duration_sec / 60)}m ${t.duration_sec % 60}s` : "—";
              const reason = t.close_reason || "—";

              return (
                <div key={id}
                  onClick={() => setExpandedId(isExpanded ? null : id)}
                  style={{
                    background: "#0f0f1a",
                    border: `1px solid ${isExpanded ? C.accent + "55" : C.border}`,
                    borderRadius: 10, padding: "14px 16px", cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                    <span style={{
                      padding: "3px 10px", borderRadius: 5, fontSize: 11, fontWeight: 700,
                      background: isLong ? `${C.win}22` : `${C.loss}22`,
                      color: isLong ? C.win : C.loss,
                      border: `1px solid ${isLong ? C.win : C.loss}44`,
                    }}>{(t.side || "?").toUpperCase()}</span>

                    <span style={{ fontSize: 13, fontFamily: font, color: C.text }}>
                      ${fmt(t.entry_price)} → {t.exit_price ? `$${fmt(t.exit_price)}` : "OPEN"}
                    </span>

                    <span style={{
                      fontSize: 16, fontFamily: font, fontWeight: 700,
                      color: pnl >= 0 ? C.win : C.loss, marginLeft: "auto",
                    }}>
                      {pnl >= 0 ? "+" : ""}${fmt(pnl)}
                    </span>
                  </div>

                  <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 11, fontFamily: font, color: C.muted }}>⏱ {dur}</span>
                    <span style={{
                      fontSize: 10, fontFamily: font, padding: "2px 8px", borderRadius: 4,
                      background: reason === "TP" ? `${C.win}22` : reason === "SL" ? `${C.loss}22` : `${C.muted}22`,
                      color: reason === "TP" ? C.win : reason === "SL" ? C.loss : C.muted,
                      border: `1px solid ${reason === "TP" ? C.win : reason === "SL" ? C.loss : C.muted}44`,
                    }}>{reason}</span>
                  </div>

                  {isExpanded && t.signal_text && (
                    <div style={{
                      marginTop: 12, padding: "10px 12px", background: "#070710", borderRadius: 8,
                      fontSize: 12, color: C.text, fontFamily: "'Inter', sans-serif", lineHeight: 1.6,
                      borderLeft: `3px solid ${C.accent}`,
                    }}>
                      <div style={{ fontSize: 9, fontFamily: font, color: C.accent, marginBottom: 6, letterSpacing: 1 }}>SIGNAL THAT TRIGGERED</div>
                      {t.signal_text}
                    </div>
                  )}
                  {isExpanded && !t.signal_text && (
                    <div style={{ marginTop: 10, fontSize: 11, color: C.muted, fontFamily: font }}>No signal data attached to this trade.</div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   TAB: PERFORMANCE
   ═══════════════════════════════════════════════════════════════ */
function PerformanceTab({ pnlStats, dailyPnl, trades, isMobile }) {
  const totalPnl = Number(pnlStats?.total_pnl ?? 0);
  const winRate = pnlStats?.win_rate != null ? (pnlStats.win_rate * 100) : 0;
  const totalTrades = pnlStats?.total_trades ?? (trades || []).length;
  const avgWin = pnlStats?.avg_win ?? null;
  const avgLoss = pnlStats?.avg_loss ?? null;
  const profitFactor = pnlStats?.profit_factor ?? null;

  // Build daily P&L chart data
  const dailyData = (dailyPnl || []).map(d => ({
    date: d.date ? d.date.slice(5) : "—",
    pnl: Number(d.pnl ?? d.total_pnl ?? 0),
  }));

  // Build cumulative P&L
  let cum = 0;
  const cumulativeData = (dailyPnl || []).map(d => {
    cum += Number(d.pnl ?? d.total_pnl ?? 0);
    return { date: d.date ? d.date.slice(5) : "—", cumPnl: cum };
  });

  // Build hourly heatmap from trades
  const hourlyMap = {};
  for (let h = 0; h < 24; h++) hourlyMap[h] = { count: 0, wins: 0, pnl: 0 };
  (trades || []).forEach(t => {
    const h = t.created_at || t.timestamp ? new Date(t.created_at || t.timestamp).getUTCHours() : null;
    if (h == null) return;
    hourlyMap[h].count++;
    if (Number(t.pnl ?? t.realized_pnl ?? 0) > 0) hourlyMap[h].wins++;
    hourlyMap[h].pnl += Number(t.pnl ?? t.realized_pnl ?? 0);
  });
  const hourlyData = Object.entries(hourlyMap).map(([h, v]) => ({
    hour: `${String(h).padStart(2, "0")}h`,
    winRate: v.count > 0 ? (v.wins / v.count) * 100 : 0,
    count: v.count,
    pnl: v.pnl,
  }));

  const statCards = [
    { label: "Total P&L", value: `${totalPnl >= 0 ? "+" : ""}$${fmt(totalPnl)}`, color: totalPnl >= 0 ? C.win : C.loss },
    { label: "Win Rate", value: `${winRate.toFixed(1)}%`, color: winRate >= 50 ? C.win : C.loss },
    { label: "Total Trades", value: totalTrades, color: C.accent },
    { label: "Avg Win", value: avgWin != null ? `+$${fmt(avgWin)}` : "—", color: C.win },
    { label: "Avg Loss", value: avgLoss != null ? `-$${fmt(Math.abs(avgLoss))}` : "—", color: C.loss },
    { label: "Profit Factor", value: profitFactor != null ? fmt(profitFactor, 2) : "—", color: Number(profitFactor) >= 1 ? C.win : C.loss },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Stats Row */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "repeat(2, 1fr)" : "repeat(3, 1fr)", gap: 12 }}>
        {statCards.map(({ label, value, color }) => (
          <div key={label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: "16px", textAlign: "center" }}>
            <div style={{ fontSize: 9, fontFamily: font, color: C.muted, letterSpacing: 1, marginBottom: 8, textTransform: "uppercase" }}>{label}</div>
            <div style={{ fontSize: 20, fontFamily: font, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Daily P&L Bar Chart */}
      <Card>
        <SectionTitle>📊 Daily P&L</SectionTitle>
        {dailyData.length === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: C.muted, fontSize: 13, fontFamily: font }}>No daily data yet</div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={dailyData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 10, fontFamily: font }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: C.muted, fontSize: 10, fontFamily: font }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, fontFamily: font, fontSize: 12 }}
                labelStyle={{ color: C.muted }}
                formatter={(v) => [`${v >= 0 ? "+" : ""}$${fmt(v)}`, "P&L"]}
              />
              <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                {dailyData.map((entry, i) => (
                  <Cell key={i} fill={entry.pnl >= 0 ? C.win : C.loss} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Cumulative P&L Line */}
      <Card>
        <SectionTitle>📈 Cumulative P&L</SectionTitle>
        {cumulativeData.length === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: C.muted, fontSize: 13, fontFamily: font }}>No data yet</div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={cumulativeData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 10, fontFamily: font }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: C.muted, fontSize: 10, fontFamily: font }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, fontFamily: font, fontSize: 12 }}
                labelStyle={{ color: C.muted }}
                formatter={(v) => [`${v >= 0 ? "+" : ""}$${fmt(v)}`, "Cumulative P&L"]}
              />
              <Line type="monotone" dataKey="cumPnl" stroke={C.win} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Hourly Heatmap */}
      <Card>
        <SectionTitle>⏰ Hourly Signal Heatmap (UTC)</SectionTitle>
        {trades && trades.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <div style={{ display: "flex", gap: 4, minWidth: "max-content" }}>
              {hourlyData.map((h) => {
                const intensity = Math.min(h.winRate / 100, 1);
                const bg = h.count === 0
                  ? "rgba(255,255,255,0.03)"
                  : `rgba(0,255,135,${0.05 + intensity * 0.5})`;
                return (
                  <div key={h.hour} style={{ textAlign: "center", minWidth: 36 }}>
                    <div style={{
                      height: 48, borderRadius: 6, background: bg,
                      border: `1px solid rgba(255,255,255,0.06)`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 10, fontFamily: font,
                      color: h.count > 0 ? C.win : C.muted,
                      fontWeight: 700,
                    }}>
                      {h.count > 0 ? `${h.winRate.toFixed(0)}%` : "—"}
                    </div>
                    <div style={{ fontSize: 9, fontFamily: font, color: C.muted, marginTop: 4 }}>{h.hour}</div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "24px 0", color: C.muted, fontSize: 13, fontFamily: font }}>
            Need trade history to build heatmap
          </div>
        )}
      </Card>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   TAB: WWJD — What Would Jayson Do? Strategy Guide
   ═══════════════════════════════════════════════════════════════ */
function WWJDTab({ position, isMobile }) {
  const [expanded, setExpanded] = useState(null);

  const toggle = (key) => setExpanded(expanded === key ? null : key);

  const Section = ({ id, icon, title, children }) => (
    <Card style={{ cursor: 'pointer' }} onClick={() => toggle(id)}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{ fontSize: 13, fontFamily: font, fontWeight: 700, color: C.white, flex: 1 }}>{title}</span>
        <span style={{ fontSize: 12, color: C.muted, transform: expanded === id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
          {String.fromCodePoint(0x25BC)}
        </span>
      </div>
      {expanded === id && (
        <div style={{ marginTop: 16, fontSize: 12, fontFamily: "'Inter', sans-serif", color: C.text, lineHeight: 1.7 }} onClick={e => e.stopPropagation()}>
          {children}
        </div>
      )}
    </Card>
  );

  const CheckItem = ({ ok, text }) => (
    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '4px 0' }}>
      <span style={{ color: ok ? C.win : C.loss, fontWeight: 700, fontSize: 14, lineHeight: 1 }}>{ok ? '\u2713' : '\u2717'}</span>
      <span>{text}</span>
    </div>
  );

  const FlowNode = ({ label, color, children }) => (
    <div style={{ borderLeft: `3px solid ${color}`, padding: '8px 12px', marginBottom: 8, background: `${color}11`, borderRadius: '0 8px 8px 0' }}>
      <div style={{ fontWeight: 700, color, fontSize: 12, fontFamily: font, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 11, color: C.text }}>{children}</div>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Entry Checklist */}
      <Section id="entry" icon={String.fromCodePoint(0x2705)} title="Entry Checklist (Pre-Trade)">
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontFamily: font, color: C.warning, letterSpacing: 1, marginBottom: 8 }}>BEFORE EVERY TRADE</div>
          <CheckItem ok={true} text="At exact JC level (within 0.2% proximity)?" />
          <CheckItem ok={true} text="3+ confluence factors agree?" />
          <CheckItem ok={true} text="R:R \u2265 1:1 (prefer 3:1)?" />
          <CheckItem ok={true} text="Max 2 open positions?" />
          <CheckItem ok={true} text="Not counter to JC's bias?" />
          <CheckItem ok={true} text="Session active (NY/London)?" />
        </div>
        <div style={{ padding: '10px 14px', background: '#0d0d18', borderRadius: 8, border: `1px solid ${C.border}` }}>
          <div style={{ fontSize: 10, fontFamily: font, color: C.muted, letterSpacing: 1, marginBottom: 8 }}>CONVICTION SCORING</div>
          <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, 1fr)', gap: 8 }}>
            {[
              { label: 'HIGH', emoji: String.fromCodePoint(0x1F7E2), desc: '4+ factors, 5% risk, 50x', color: C.win },
              { label: 'MEDIUM', emoji: String.fromCodePoint(0x1F7E1), desc: '3 factors, 3% risk, 40x', color: C.warning },
              { label: 'SKIP', emoji: String.fromCodePoint(0x1F534), desc: '<3 factors, NO TRADE', color: C.loss },
            ].map(c => (
              <div key={c.label} style={{ padding: '8px 10px', background: `${c.color}11`, border: `1px solid ${c.color}33`, borderRadius: 6, textAlign: 'center' }}>
                <div style={{ fontSize: 14 }}>{c.emoji}</div>
                <div style={{ fontWeight: 700, color: c.color, fontSize: 12, fontFamily: font }}>{c.label}</div>
                <div style={{ fontSize: 10, color: C.muted }}>{c.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* Trade Management */}
      <Section id="manage" icon={String.fromCodePoint(0x1F3AF)} title="Trade Management (Active Position)">
        {[
          { trigger: '+1.0%', action: 'Move SL to breakeven', color: C.warning },
          { trigger: 'TP1 (opposing level)', action: 'Close 50%, SL to breakeven', color: C.win },
          { trigger: 'TP2 or +1.5%', action: 'Close remaining 50%', color: C.win },
          { trigger: 'Trending >1.5%', action: 'Trail SL 0.5% behind price, ride to next level', color: '#60a5fa' },
          { trigger: 'SL Hit', action: 'Full close — no hoping, no holding', color: C.loss },
          { trigger: 'Never', action: 'Widen SL — only tighten, never move away', color: C.loss },
        ].map(r => (
          <div key={r.trigger} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '8px 12px', background: '#0f0f1a', borderRadius: 8, border: `1px solid ${C.border}`, marginBottom: 6 }}>
            <span style={{ fontSize: 12, fontFamily: font, fontWeight: 700, color: r.color, minWidth: 120, flexShrink: 0 }}>{r.trigger}</span>
            <span style={{ fontSize: 12, fontFamily: font, color: C.text }}>{r.action}</span>
          </div>
        ))}
      </Section>

      {/* Stop-Out Response */}
      <Section id="stopout" icon={String.fromCodePoint(0x274C)} title="Stop-Out Response (What JC Does)">
        <div style={{ fontSize: 11, fontFamily: font, color: C.warning, letterSpacing: 1, marginBottom: 12 }}>DECISION FLOWCHART</div>
        <FlowNode label="STOPPED OUT" color={C.loss}>
          Log level + reason. Fake-out or invalidation?
        </FlowNode>
        <FlowNode label="Level holds on retest?" color={C.win}>
          YES {String.fromCodePoint(0x2192)} Wait 5-15 min, re-enter SAME direction at 2% size (reduced)
        </FlowNode>
        <FlowNode label="Level invalidated (clean break)?" color={C.warning}>
          Move to NEXT major level in hierarchy. Wait for price to reach it.
        </FlowNode>
        <FlowNode label="Momentum flipped (BOS opposite)?" color={C.accent}>
          Consider OPPOSITE bias at next key level. Wait for JC signal.
        </FlowNode>
        <div style={{ padding: '10px 14px', background: `${C.loss}11`, borderRadius: 8, marginTop: 12 }}>
          <div style={{ fontWeight: 700, color: C.loss, marginBottom: 6 }}>{String.fromCodePoint(0x274C)} NEVER DO</div>
          <div>{String.fromCodePoint(0x2022)} Revenge trade immediately</div>
          <div>{String.fromCodePoint(0x2022)} Double down without confirmation</div>
          <div>{String.fromCodePoint(0x2022)} Hope and hold losers</div>
          <div>{String.fromCodePoint(0x2022)} Enter between levels</div>
          <div>{String.fromCodePoint(0x2022)} Increase size after a loss</div>
        </div>
      </Section>

      {/* Level Hierarchy */}
      <Section id="levels" icon={String.fromCodePoint(0x1F5FA)} title="Level Hierarchy (JC's Key Levels)">
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 10, fontFamily: font, color: C.loss, letterSpacing: 1, marginBottom: 8 }}>{String.fromCodePoint(0x1F534)} RESISTANCE</div>
          {JC_LEVELS.filter(l => l.type === 'resistance').sort((a,b) => b.price - a.price).map(l => (
            <div key={l.price} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 10px', background: 'rgba(255,51,102,0.05)', borderRadius: 6, marginBottom: 4, border: '1px solid rgba(255,51,102,0.1)' }}>
              <span style={{ fontSize: 13, fontFamily: font, fontWeight: 700, color: C.white, minWidth: 80 }}>${l.price.toLocaleString()}</span>
              <span style={{ fontSize: 11, fontFamily: font, color: l.color, fontWeight: 600 }}>{l.label}</span>
              {l.note && <span style={{ fontSize: 10, color: C.muted }}>{String.fromCodePoint(0x2014)} {l.note}</span>}
              <span style={{ marginLeft: 'auto', fontSize: 10, fontFamily: font, color: C.muted }}>{LEVEL_LEVERAGE_MAP[l.label] || 30}x</span>
            </div>
          ))}
        </div>
        <div>
          <div style={{ fontSize: 10, fontFamily: font, color: C.win, letterSpacing: 1, marginBottom: 8 }}>{String.fromCodePoint(0x1F7E2)} SUPPORT</div>
          {JC_LEVELS.filter(l => l.type === 'support').sort((a,b) => b.price - a.price).map(l => (
            <div key={l.price} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 10px', background: 'rgba(0,255,135,0.03)', borderRadius: 6, marginBottom: 4, border: '1px solid rgba(0,255,135,0.08)' }}>
              <span style={{ fontSize: 13, fontFamily: font, fontWeight: 700, color: C.white, minWidth: 80 }}>${l.price.toLocaleString()}</span>
              <span style={{ fontSize: 11, fontFamily: font, color: l.color, fontWeight: 600 }}>{l.label}</span>
              {l.note && <span style={{ fontSize: 10, color: C.muted }}>{String.fromCodePoint(0x2014)} {l.note}</span>}
              <span style={{ marginLeft: 'auto', fontSize: 10, fontFamily: font, color: C.muted }}>{LEVEL_LEVERAGE_MAP[l.label] || 30}x</span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, padding: '10px 14px', background: '#0d0d18', borderRadius: 8 }}>
          <div style={{ fontSize: 10, fontFamily: font, color: C.accent, letterSpacing: 1, marginBottom: 6 }}>LEVEL TYPES</div>
          <div style={{ fontSize: 11, lineHeight: 1.8 }}>
            <b style={{ color: C.white }}>SPV</b> {String.fromCodePoint(0x2014)} Single Print Value: one-time volume nodes, tends to sweep and reverse<br/>
            <b style={{ color: C.white }}>nPOC</b> {String.fromCodePoint(0x2014)} Naked Point of Control: untested magnet level (w/d/m)<br/>
            <b style={{ color: C.white }}>Fib</b> {String.fromCodePoint(0x2014)} Fibonacci retracement (0.786 = Golden Pocket, highest conviction)<br/>
            <b style={{ color: C.white }}>NY Open P&D</b> {String.fromCodePoint(0x2014)} Levels set during NY open volatility<br/>
            <b style={{ color: C.white }}>KEY</b> {String.fromCodePoint(0x2014)} Multiple confluence points marked by Jayson
          </div>
        </div>
      </Section>

      {/* Bankroll Management */}
      <Section id="bankroll" icon={String.fromCodePoint(0x1F4B0)} title="Bankroll Management">
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, 1fr)', gap: 8 }}>
          {[
            { label: 'Standard Trade', value: '3% of bankroll', note: 'MEDIUM conviction', color: C.warning },
            { label: 'High Conviction', value: '5% of bankroll', note: '4+ factors, SPV/CDW', color: C.win },
            { label: 'After Stop-Out', value: '2% of bankroll', note: 'Reduced until next win', color: C.loss },
            { label: 'Max Concurrent', value: '2 positions', note: 'Any direction', color: C.accent },
            { label: 'Max Exposure', value: '10% total', note: 'All positions combined', color: C.accent },
            { label: 'Max Drawdown', value: '15% pause', note: 'Auto-pause trading', color: C.loss },
          ].map(r => (
            <div key={r.label} style={{ padding: '10px 12px', background: '#0f0f1a', borderRadius: 8, border: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 10, fontFamily: font, color: C.muted, letterSpacing: 1 }}>{r.label}</div>
              <div style={{ fontSize: 14, fontFamily: font, fontWeight: 700, color: r.color }}>{r.value}</div>
              <div style={{ fontSize: 10, color: C.muted }}>{r.note}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* Active Trade WWJD Status */}
      {position && (
        <Card>
          <SectionTitle>{String.fromCodePoint(0x1F3AF)} Active Trade — WWJD Status</SectionTitle>
          <div style={{ padding: '12px 16px', background: `${C.accent}11`, borderRadius: 8, border: `1px solid ${C.accent}33` }}>
            <div style={{ fontSize: 13, fontFamily: font, fontWeight: 700, color: C.white, marginBottom: 8 }}>
              {position.side} @ ${fmt(position.entry_price)}
            </div>
            <div style={{ fontSize: 11, color: C.text, lineHeight: 1.8 }}>
              {String.fromCodePoint(0x2022)} Status: {position.state || 'OPEN'}<br/>
              {String.fromCodePoint(0x2022)} If TP1 hit: Close 50%, move SL to breakeven<br/>
              {String.fromCodePoint(0x2022)} If stopped: Analyze level, wait for JC signal<br/>
              {String.fromCodePoint(0x2022)} If trending: Trail SL, let it sizzle
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   TAB: STRATEGY
   ═══════════════════════════════════════════════════════════════ */
function StrategyTab({ config, isMobile }) {
  const [settings, setSettings] = useState(null);
  const [editing, setEditing] = useState(null);
  const [editVal, setEditVal] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const load = () => fetch('/api/ghost/jc-settings').then(r => r.json()).then(d => d?.settings && setSettings(d.settings)).catch(() => {});
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  const s = settings || {};
  const mode = s.mode || config?.mode || 'paper';

  const saveSetting = async (key, value) => {
    setSaving(true);
    try {
      await fetch('/api/ghost/jc-settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value }),
      });
      setSettings(prev => ({ ...prev, [key]: value }));
    } catch (e) { console.error(e); }
    setSaving(false);
    setEditing(null);
  };

  const editableCard = (key, icon, label, displayFn, suffix) => {
    const isEdit = editing === key;
    const rawVal = s[key] || '0';
    return (
      <div key={key} style={{ background: '#0f0f1a', borderRadius: 10, padding: '14px 16px', border: `1px solid ${isEdit ? C.accent : C.border}`, cursor: 'pointer', transition: 'border-color 0.2s' }}
        onClick={() => { if (!isEdit) { setEditing(key); setEditVal(rawVal); } }}>
        <div style={{ fontSize: 10, fontFamily: font, color: C.muted, marginBottom: 6, letterSpacing: 1 }}>{icon} {label.toUpperCase()}</div>
        {isEdit ? (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input value={editVal} onChange={e => setEditVal(e.target.value)} autoFocus
              style={{ background: '#1a1a2e', border: `1px solid ${C.accent}`, borderRadius: 6, padding: '6px 10px', color: C.white, fontSize: 15, fontFamily: font, fontWeight: 700, width: '100%', outline: 'none' }}
              onKeyDown={e => { if (e.key === 'Enter') saveSetting(key, editVal); if (e.key === 'Escape') setEditing(null); }} />
            <button onClick={(e) => { e.stopPropagation(); saveSetting(key, editVal); }}
              style={{ background: C.accent, color: '#fff', border: 'none', borderRadius: 6, padding: '6px 12px', fontSize: 11, fontFamily: font, cursor: 'pointer', fontWeight: 700, flexShrink: 0 }}>
              {saving ? '...' : 'Save'}
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 15, fontFamily: font, fontWeight: 700, color: C.white }}>{displayFn ? displayFn(rawVal) : rawVal}{suffix || ''}</span>
            <span style={{ fontSize: 10, color: C.muted, marginLeft: 'auto' }}>tap to edit</span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Mode Toggle */}
      <Card>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
          <SectionTitle style={{ marginBottom: 0 }}>Settings</SectionTitle>
          <button onClick={() => saveSetting('mode', mode === 'paper' ? 'live' : 'paper')}
            style={{
              padding: '5px 14px', borderRadius: 6, fontSize: 12, fontFamily: font, fontWeight: 700, cursor: 'pointer',
              background: mode === 'live' ? `${C.loss}22` : `${C.accent}22`,
              color: mode === 'live' ? C.loss : C.accent,
              border: `1px solid ${mode === 'live' ? C.loss : C.accent}55`,
              textTransform: 'uppercase', letterSpacing: 1,
            }}>
            {mode === 'live' ? 'LIVE' : 'PAPER'}
          </button>
        </div>

        {/* Editable Settings Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, 1fr)', gap: 12 }}>
          {editableCard('stake_pct', String.fromCodePoint(0x1F4B0), 'Risk / Trade', v => `${(Number(v) * 100).toFixed(0)}% of balance`)}
          {editableCard('max_leverage', String.fromCodePoint(0x2696), 'Max Leverage', v => `${v}x`)}
          {editableCard('min_leverage', String.fromCodePoint(0x1F4C9), 'Min Leverage', v => `${v}x`)}
          {editableCard('max_concurrent', String.fromCodePoint(0x1F4CA), 'Max Concurrent', v => `${v} positions`)}
          {editableCard('proximity_pct', String.fromCodePoint(0x1F3AF), 'Level Proximity', v => `${(Number(v) * 100).toFixed(1)}%`)}
          {editableCard('half_close_pct', String.fromCodePoint(0x2702), 'Partial Close At', v => `+${v}%`)}
          {editableCard('full_close_pct', String.fromCodePoint(0x2705), 'Full Close At', v => `+${v}%`)}
          {editableCard('breakeven_pct', String.fromCodePoint(0x1F6E1), 'Breakeven SL At', v => `+${v}%`)}
        </div>
      </Card>

      {/* Position Management — dynamic from settings */}
      <Card>
        <SectionTitle>Position Management</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[
            { trigger: `+${s.half_close_pct || '1.0'}%`, action: 'Half close + move SL to breakeven', color: C.warning },
            { trigger: `+${s.full_close_pct || '1.5'}%`, action: 'Full close remaining position', color: C.win },
            { trigger: 'Opposing JC level', action: 'Partial exit at next resistance/support', color: C.accent },
            { trigger: 'Trending >1.5%', action: 'Hold remainder, ride to next level', color: '#60a5fa' },
            { trigger: 'SL hit', action: 'Full close at stop loss', color: C.loss },
          ].map(({ trigger, action, color }) => (
            <div key={trigger} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '8px 12px', background: '#0f0f1a', borderRadius: 8, border: `1px solid ${C.border}` }}>
              <span style={{ fontSize: 12, fontFamily: font, fontWeight: 700, color, minWidth: 90, flexShrink: 0 }}>{trigger}</span>
              <span style={{ fontSize: 12, fontFamily: font, color: C.text }}>{action}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Level-Based Strategy Info */}
      <Card>
        <SectionTitle>V1 Strategy</SectionTitle>
        <div style={{ fontSize: 12, fontFamily: "'Inter', sans-serif", color: C.text, lineHeight: 1.7 }}>
          <div style={{ marginBottom: 8 }}><b style={{ color: C.white }}>Entry:</b> LONG at support levels, SHORT at resistance. Price must be within {((Number(s.proximity_pct || 0.002)) * 100).toFixed(1)}% of a JC level.</div>
          <div style={{ marginBottom: 8 }}><b style={{ color: C.white }}>Leverage:</b> {s.min_leverage || 30}x{String.fromCodePoint(0x2013)}{s.max_leverage || 50}x auto-scaled by level type (SPV 50x, POC 45x, Fib 40x, D/W 35x).</div>
          <div style={{ marginBottom: 8 }}><b style={{ color: C.white }}>Sizing:</b> {((Number(s.stake_pct || 0.03)) * 100).toFixed(0)}% of bankroll per trade.</div>
          <div><b style={{ color: C.white }}>Exits:</b> Level-based partial closes + trending hold. Not fixed %. Mirrors Jayson's "let it sizzle" approach.</div>
        </div>
      </Card>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MANUAL CONTROLS — Trading Desk Control Panel
   ═══════════════════════════════════════════════════════════════ */
function ManualControls({ activeTrade, btcPrice, onRefresh }) {
  const [isOpen, setIsOpen] = useState(true);
  const [mode, setMode] = useState('paper');
  const [isPaused, setIsPaused] = useState(false);
  const [marginAmount, setMarginAmount] = useState('');
  const [loading, setLoading] = useState(null); // 'pause' | 'kill' | 'margin' | 'override' | null
  const [killConfirm, setKillConfirm] = useState(false);
  const [toast, setToast] = useState(null); // { message, type: 'success' | 'error' }
  const [bybitStatus, setBybitStatus] = useState(null);
  const [customSL, setCustomSL] = useState('');
  const [customTP1, setCustomTP1] = useState('');
  const [customTP2, setCustomTP2] = useState('');
  const [isOverridden, setIsOverridden] = useState(false);

  // Track manual override state from active trade
  useEffect(() => {
    if (activeTrade) {
      setIsOverridden(activeTrade.manual_override || false);
    } else {
      setIsOverridden(false);
      setCustomSL('');
      setCustomTP1('');
      setCustomTP2('');
    }
  }, [activeTrade?.id, activeTrade?.manual_override]);

  // Load settings on mount
  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch('/api/ghost/jc-settings');
        const d = await r.json();
        if (d?.settings) {
          setMode(d.settings.mode || 'paper');
          setIsPaused(d.settings.paused === 'true');
        }
      } catch {}
    };
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  // Check Bybit status when in live mode
  useEffect(() => {
    if (mode !== 'live') { setBybitStatus(null); return; }
    const load = async () => {
      try {
        const r = await fetch('/api/ghost/jc-bybit-status');
        setBybitStatus(await r.json());
      } catch { setBybitStatus({ api_connected: false }); }
    };
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [mode]);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  // Toggle mode
  const toggleMode = async (newMode) => {
    if (newMode === 'live') {
      if (!window.confirm('⚠️ Switch to LIVE mode?\n\nReal funds will be used on Bybit.\nMake sure API keys are valid.')) return;
    }
    try {
      await fetch('/api/ghost/jc-settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode }),
      });
      setMode(newMode);
      showToast(`Switched to ${newMode.toUpperCase()} mode`);
    } catch (e) {
      showToast(`Failed: ${e.message}`, 'error');
    }
  };

  // Pause/unpause
  const handlePause = async () => {
    setLoading('pause');
    try {
      const r = await fetch('/api/ghost/jc-pause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'toggle' }),
      });
      const d = await r.json();
      if (d.ok) {
        setIsPaused(d.paused);
        showToast(d.message);
      } else {
        showToast(d.error || 'Failed', 'error');
      }
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error');
    }
    setLoading(null);
  };

  // Kill trade
  const handleKill = async () => {
    setLoading('kill');
    try {
      const r = await fetch('/api/ghost/jc-kill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trade_id: activeTrade?.id || null }),
      });
      const d = await r.json();
      if (d.ok) {
        showToast(`Position closed @ $${Number(d.exit_price).toLocaleString()}. P&L: ${d.pnl >= 0 ? '+' : ''}$${d.pnl}`);
        setKillConfirm(false);
        onRefresh?.();
      } else {
        showToast(d.error || 'Kill failed', 'error');
      }
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error');
    }
    setLoading(null);
  };

  // Add margin
  const handleAddMargin = async () => {
    const amt = parseFloat(marginAmount);
    if (!amt || amt <= 0) { showToast('Enter a valid USD amount', 'error'); return; }
    if (mode !== 'live') { showToast('Add margin only works in LIVE mode', 'error'); return; }
    if (!window.confirm(`Add $${amt} margin to position?`)) return;

    setLoading('margin');
    try {
      const r = await fetch('/api/ghost/jc-add-margin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trade_id: activeTrade?.id || null, amount: amt }),
      });
      const d = await r.json();
      if (d.ok) {
        showToast(`Added $${amt}. New position: $${d.new_size}`);
        setMarginAmount('');
        onRefresh?.();
      } else {
        showToast(d.error || 'Failed', 'error');
      }
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error');
    }
    setLoading(null);
  };

  // Apply manual TP/SL override
  const handleApplyOverride = async () => {
    const sl = customSL ? parseFloat(customSL) : null;
    const tp1 = customTP1 ? parseFloat(customTP1) : null;
    const tp2 = customTP2 ? parseFloat(customTP2) : null;

    if (!sl && !tp1 && !tp2) {
      showToast('Enter at least one level to override', 'error');
      return;
    }

    // Direction validation
    const dir = (activeTrade.direction || activeTrade.side || '').toUpperCase();
    const entry = Number(activeTrade.fill_price || activeTrade.entry || activeTrade.entry_price);
    if (dir === 'SHORT') {
      if (sl && sl <= entry) { showToast('SL must be above entry for SHORT', 'error'); return; }
      if (tp1 && tp1 >= entry) { showToast('TP1 must be below entry for SHORT', 'error'); return; }
      if (tp2 && tp2 >= entry) { showToast('TP2 must be below entry for SHORT', 'error'); return; }
    } else if (dir === 'LONG') {
      if (sl && sl >= entry) { showToast('SL must be below entry for LONG', 'error'); return; }
      if (tp1 && tp1 <= entry) { showToast('TP1 must be above entry for LONG', 'error'); return; }
      if (tp2 && tp2 <= entry) { showToast('TP2 must be above entry for LONG', 'error'); return; }
    }

    setLoading('override');
    try {
      const r = await fetch('/api/ghost/jc-override-levels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          trade_id: activeTrade.id,
          stop_loss: sl,
          tp1: tp1,
          tp2: tp2,
        }),
      });
      const d = await r.json();
      if (d.ok) {
        setIsOverridden(true);
        showToast('Levels updated! Manual override active.');
        onRefresh?.();
      } else {
        showToast(d.error || 'Failed to update levels', 'error');
      }
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error');
    }
    setLoading(null);
  };

  // Revert to JC's original levels
  const handleRevertStrategy = async () => {
    if (!window.confirm("Revert to JC's original TP/SL levels?")) return;

    setLoading('override');
    try {
      const r = await fetch('/api/ghost/jc-revert-levels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trade_id: activeTrade.id }),
      });
      const d = await r.json();
      if (d.ok) {
        setIsOverridden(false);
        setCustomSL('');
        setCustomTP1('');
        setCustomTP2('');
        showToast('Reverted to JC levels');
        onRefresh?.();
      } else {
        showToast(d.error || 'Failed to revert', 'error');
      }
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error');
    }
    setLoading(null);
  };

  // Compute live P&L for kill confirm modal
  const livePnl = activeTrade && btcPrice && activeTrade.entry_price
    ? (() => {
        const entry = Number(activeTrade.entry_price || activeTrade.entry || activeTrade.fill_price);
        const stake = Number(activeTrade.stake_usd || activeTrade.stake || 300);
        const lev = Number(activeTrade.leverage || 30);
        const dir = (activeTrade.direction || activeTrade.side || '').toUpperCase();
        const move = dir === 'SHORT' ? entry - btcPrice : btcPrice - entry;
        const notional = stake * lev;
        return ((move / entry) * notional).toFixed(2);
      })()
    : null;

  const isLive = mode === 'live';

  return (
    <div style={{
      background: C.card,
      border: `1px solid ${isLive ? '#ef444466' : C.border}`,
      borderRadius: 12,
      overflow: 'hidden',
      transition: 'border-color 0.3s ease',
    }}>
      {/* Toast notification */}
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 20, zIndex: 9999,
          padding: '12px 20px', borderRadius: 10,
          background: toast.type === 'error' ? '#ef4444' : '#10b981',
          color: '#fff', fontSize: 13, fontFamily: font, fontWeight: 600,
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          animation: 'slideIn 0.3s ease',
        }}>
          {toast.type === 'error' ? '❌' : '✅'} {toast.message}
        </div>
      )}

      {/* Kill confirmation modal */}
      {killConfirm && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.8)', zIndex: 9998,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 20,
        }} onClick={() => setKillConfirm(false)}>
          <div style={{
            background: '#1a1a2e', border: '1px solid #ef444466', borderRadius: 16,
            padding: '28px 32px', maxWidth: 420, width: '100%',
            boxShadow: '0 16px 64px rgba(0,0,0,0.6)',
          }} onClick={e => e.stopPropagation()}>
            <div style={{ fontSize: 18, fontFamily: font, fontWeight: 700, color: '#ef4444', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
              ⚠️ Close Position Now?
            </div>
            {activeTrade && (
              <div style={{ marginBottom: 16, padding: '12px 16px', background: '#0a0a0f', borderRadius: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontSize: 12, color: C.muted, fontFamily: font }}>Direction</span>
                  <span style={{
                    fontSize: 12, fontFamily: font, fontWeight: 700,
                    color: (activeTrade.direction || '').toUpperCase() === 'LONG' ? C.win : C.loss,
                  }}>{(activeTrade.direction || activeTrade.side || '?').toUpperCase()}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontSize: 12, color: C.muted, fontFamily: font }}>Entry</span>
                  <span style={{ fontSize: 12, fontFamily: font, color: C.white }}>${fmt(activeTrade.entry_price || activeTrade.entry)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontSize: 12, color: C.muted, fontFamily: font }}>Current</span>
                  <span style={{ fontSize: 12, fontFamily: font, color: C.warning }}>${fmt(btcPrice)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, color: C.muted, fontFamily: font }}>Est. P&L</span>
                  <span style={{
                    fontSize: 14, fontFamily: font, fontWeight: 700,
                    color: livePnl && Number(livePnl) >= 0 ? C.win : C.loss,
                  }}>{livePnl ? `${Number(livePnl) >= 0 ? '+' : ''}$${livePnl}` : '—'}</span>
                </div>
              </div>
            )}
            <div style={{ fontSize: 12, color: C.text, lineHeight: 1.6, marginBottom: 20 }}>
              This will immediately close your position at market price{isLive ? ' on Bybit' : ' (paper)'}.
              This action cannot be undone.
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <button onClick={() => setKillConfirm(false)} style={{
                flex: 1, padding: '10px 16px', borderRadius: 8, fontSize: 13, fontFamily: font,
                fontWeight: 700, cursor: 'pointer', background: '#ffffff11', color: C.text,
                border: `1px solid ${C.border}`,
              }}>CANCEL</button>
              <button onClick={handleKill} disabled={loading === 'kill'} style={{
                flex: 1, padding: '10px 16px', borderRadius: 8, fontSize: 13, fontFamily: font,
                fontWeight: 700, cursor: loading === 'kill' ? 'wait' : 'pointer',
                background: '#ef444433', color: '#ef4444', border: '1px solid #ef444466',
              }}>{loading === 'kill' ? 'CLOSING...' : '⏹ CONFIRM KILL'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Header / toggle */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 20px', cursor: 'pointer',
          borderBottom: isOpen ? `1px solid ${C.border}` : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 14 }}>⚙️</span>
          <span style={{ fontSize: 12, fontFamily: font, fontWeight: 700, color: C.white, letterSpacing: 1.5, textTransform: 'uppercase' }}>
            Manual Controls
          </span>
          {isPaused && (
            <span style={{
              fontSize: 9, fontFamily: font, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
              background: '#F59E0B22', color: '#F59E0B', border: '1px solid #F59E0B44',
            }}>PAUSED</span>
          )}
          {isLive && (
            <span style={{
              fontSize: 9, fontFamily: font, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
              background: '#ef444422', color: '#ef4444', border: '1px solid #ef444444',
              animation: 'pulse 2s infinite',
            }}>🔴 LIVE</span>
          )}
        </div>
        <span style={{
          fontSize: 12, color: C.muted,
          transform: isOpen ? 'rotate(180deg)' : 'none',
          transition: 'transform 0.2s',
        }}>▼</span>
      </div>

      {isOpen && (
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Mode Toggle */}
          <div>
            <div style={{ fontSize: 10, fontFamily: font, color: C.muted, letterSpacing: 1.5, marginBottom: 8 }}>TRADING MODE</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {['paper', 'live'].map(m => (
                <button key={m} onClick={() => toggleMode(m)} style={{
                  flex: 1, padding: '10px 16px', borderRadius: 8, fontSize: 12, fontFamily: font,
                  fontWeight: 700, cursor: 'pointer', textTransform: 'uppercase', letterSpacing: 1,
                  transition: 'all 0.2s ease',
                  background: mode === m
                    ? (m === 'live' ? '#ef444422' : `${C.accent}22`)
                    : '#ffffff06',
                  color: mode === m
                    ? (m === 'live' ? '#ef4444' : C.accent)
                    : C.muted,
                  border: `1px solid ${mode === m
                    ? (m === 'live' ? '#ef444466' : `${C.accent}55`)
                    : C.border}`,
                }}>
                  {m === 'live' ? '🔴 ' : '📝 '}{m}
                </button>
              ))}
            </div>
          </div>

          {/* Bybit API status (live mode only) */}
          {isLive && bybitStatus && (
            <div style={{
              padding: '10px 14px', borderRadius: 8,
              background: bybitStatus.api_connected ? '#10b98111' : '#ef444411',
              border: `1px solid ${bybitStatus.api_connected ? '#10b98133' : '#ef444433'}`,
              display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%',
                background: bybitStatus.api_connected ? '#10b981' : '#ef4444',
                boxShadow: bybitStatus.api_connected ? '0 0 6px #10b981' : 'none',
              }} />
              <span style={{ fontSize: 11, fontFamily: font, color: bybitStatus.api_connected ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                Bybit API {bybitStatus.api_connected ? 'Connected' : 'Disconnected'}
              </span>
              {bybitStatus.balance?.ok && (
                <span style={{ fontSize: 11, fontFamily: font, color: C.text, marginLeft: 'auto' }}>
                  Balance: ${Number(bybitStatus.balance.available).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              )}
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {/* PAUSE */}
            <button onClick={handlePause} disabled={loading === 'pause'} style={{
              flex: '1 1 120px', padding: '12px 16px', borderRadius: 10, fontSize: 12, fontFamily: font,
              fontWeight: 700, cursor: loading === 'pause' ? 'wait' : 'pointer',
              background: isPaused ? '#F59E0B22' : '#ffffff08',
              color: isPaused ? '#F59E0B' : C.text,
              border: `1px solid ${isPaused ? '#F59E0B55' : C.border}`,
              transition: 'all 0.2s ease',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
              {isPaused ? '▶️' : '⏸'} {loading === 'pause' ? '...' : (isPaused ? 'RESUME' : 'PAUSE')}
            </button>

            {/* KILL */}
            <button
              onClick={() => activeTrade ? setKillConfirm(true) : showToast('No open trade to kill', 'error')}
              disabled={loading === 'kill'}
              style={{
                flex: '1 1 120px', padding: '12px 16px', borderRadius: 10, fontSize: 12, fontFamily: font,
                fontWeight: 700, cursor: !activeTrade ? 'not-allowed' : 'pointer',
                background: '#ef444422', color: '#ef4444',
                border: '1px solid #ef444455',
                opacity: activeTrade ? 1 : 0.4,
                transition: 'all 0.2s ease',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}
            >
              ⏹ KILL POSITION
            </button>
          </div>

          {/* Add Margin */}
          <div>
            <div style={{ fontSize: 10, fontFamily: font, color: C.muted, letterSpacing: 1.5, marginBottom: 8 }}>ADD MARGIN (LIVE ONLY)</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'stretch' }}>
              <div style={{ flex: 1, position: 'relative' }}>
                <span style={{
                  position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
                  fontSize: 13, fontFamily: font, color: C.muted,
                }}>$</span>
                <input
                  type="number"
                  value={marginAmount}
                  onChange={e => setMarginAmount(e.target.value)}
                  placeholder="Amount USD"
                  disabled={mode !== 'live' || !activeTrade}
                  style={{
                    width: '100%', padding: '10px 12px 10px 28px', borderRadius: 8,
                    background: '#0a0a0f', border: `1px solid ${C.border}`,
                    color: C.white, fontSize: 13, fontFamily: font,
                    outline: 'none', boxSizing: 'border-box',
                    opacity: mode !== 'live' || !activeTrade ? 0.4 : 1,
                  }}
                  onFocus={e => e.target.style.borderColor = '#10b981'}
                  onBlur={e => e.target.style.borderColor = C.border}
                  onKeyDown={e => e.key === 'Enter' && handleAddMargin()}
                />
              </div>
              <button
                onClick={handleAddMargin}
                disabled={mode !== 'live' || !activeTrade || loading === 'margin'}
                style={{
                  padding: '10px 20px', borderRadius: 8, fontSize: 12, fontFamily: font,
                  fontWeight: 700, cursor: mode !== 'live' || !activeTrade ? 'not-allowed' : 'pointer',
                  background: '#10b98122', color: '#10b981',
                  border: '1px solid #10b98155',
                  opacity: mode !== 'live' || !activeTrade ? 0.4 : 1,
                  whiteSpace: 'nowrap',
                  display: 'flex', alignItems: 'center', gap: 6,
                }}
              >
                {loading === 'margin' ? '...' : '+ ADD MARGIN'}
              </button>
            </div>
          </div>

          {/* Manual TP/SL Override */}
          {activeTrade && (
            <div style={{
              marginTop: 4, padding: 16,
              background: '#0a0a0f',
              border: `1px solid ${isOverridden ? '#F59E0B33' : C.border}`,
              borderRadius: 10,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ fontSize: 10, fontFamily: font, color: C.muted, letterSpacing: 1.5, textTransform: 'uppercase' }}>
                  MANUAL TP/SL OVERRIDE
                </div>
                {isOverridden && (
                  <span style={{
                    fontSize: 9, fontFamily: font, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                    background: '#F59E0B22', color: '#F59E0B', border: '1px solid #F59E0B44',
                  }}>⚠️ OVERRIDE ACTIVE</span>
                )}
              </div>

              {/* SL input */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 11, fontFamily: font, color: '#ef4444', fontWeight: 600, minWidth: 80 }}>Stop Loss</span>
                  <div style={{ flex: 1, position: 'relative' }}>
                    <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 12, fontFamily: font, color: C.muted }}>$</span>
                    <input
                      type="number"
                      step="0.01"
                      placeholder={activeTrade.sl || 'N/A'}
                      value={customSL}
                      onChange={e => setCustomSL(e.target.value)}
                      style={{
                        width: '100%', padding: '8px 10px 8px 24px', borderRadius: 6,
                        background: '#1a1a2e', border: `1px solid ${C.border}`,
                        color: C.white, fontSize: 12, fontFamily: font,
                        outline: 'none', boxSizing: 'border-box',
                      }}
                      onFocus={e => e.target.style.borderColor = '#F59E0B'}
                      onBlur={e => e.target.style.borderColor = C.border}
                    />
                  </div>
                  <span style={{ fontSize: 10, fontFamily: font, color: '#666', minWidth: 100, textAlign: 'right' }}>
                    Orig: ${fmt(activeTrade.original_sl || activeTrade.sl)}
                  </span>
                </div>
              </div>

              {/* TP1 input */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 11, fontFamily: font, color: '#10b981', fontWeight: 600, minWidth: 80 }}>Take Profit 1</span>
                  <div style={{ flex: 1, position: 'relative' }}>
                    <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 12, fontFamily: font, color: C.muted }}>$</span>
                    <input
                      type="number"
                      step="0.01"
                      placeholder={activeTrade.tp1 || 'N/A'}
                      value={customTP1}
                      onChange={e => setCustomTP1(e.target.value)}
                      style={{
                        width: '100%', padding: '8px 10px 8px 24px', borderRadius: 6,
                        background: '#1a1a2e', border: `1px solid ${C.border}`,
                        color: C.white, fontSize: 12, fontFamily: font,
                        outline: 'none', boxSizing: 'border-box',
                      }}
                      onFocus={e => e.target.style.borderColor = '#F59E0B'}
                      onBlur={e => e.target.style.borderColor = C.border}
                    />
                  </div>
                  <span style={{ fontSize: 10, fontFamily: font, color: '#666', minWidth: 100, textAlign: 'right' }}>
                    Orig: ${fmt(activeTrade.original_tp1 || activeTrade.tp1)}
                  </span>
                </div>
              </div>

              {/* TP2 input */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 11, fontFamily: font, color: '#10b981', fontWeight: 600, minWidth: 80 }}>Take Profit 2</span>
                  <div style={{ flex: 1, position: 'relative' }}>
                    <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 12, fontFamily: font, color: C.muted }}>$</span>
                    <input
                      type="number"
                      step="0.01"
                      placeholder={activeTrade.tp2 || 'N/A'}
                      value={customTP2}
                      onChange={e => setCustomTP2(e.target.value)}
                      style={{
                        width: '100%', padding: '8px 10px 8px 24px', borderRadius: 6,
                        background: '#1a1a2e', border: `1px solid ${C.border}`,
                        color: C.white, fontSize: 12, fontFamily: font,
                        outline: 'none', boxSizing: 'border-box',
                      }}
                      onFocus={e => e.target.style.borderColor = '#F59E0B'}
                      onBlur={e => e.target.style.borderColor = C.border}
                    />
                  </div>
                  <span style={{ fontSize: 10, fontFamily: font, color: '#666', minWidth: 100, textAlign: 'right' }}>
                    Orig: ${fmt(activeTrade.original_tp2 || activeTrade.tp2)}
                  </span>
                </div>
              </div>

              {/* Buttons */}
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  onClick={handleApplyOverride}
                  disabled={loading === 'override'}
                  style={{
                    flex: 1, padding: '10px 16px', borderRadius: 8, fontSize: 12, fontFamily: font,
                    fontWeight: 700, cursor: loading === 'override' ? 'wait' : 'pointer',
                    background: '#F59E0B22', color: '#F59E0B',
                    border: '1px solid #F59E0B55',
                    transition: 'all 0.2s ease',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  }}
                >
                  {loading === 'override' ? '...' : '⚡ APPLY OVERRIDE'}
                </button>
                <button
                  onClick={handleRevertStrategy}
                  disabled={!isOverridden || loading === 'override'}
                  style={{
                    flex: 1, padding: '10px 16px', borderRadius: 8, fontSize: 12, fontFamily: font,
                    fontWeight: 700,
                    cursor: !isOverridden || loading === 'override' ? 'not-allowed' : 'pointer',
                    background: isOverridden ? '#8B5CF622' : '#ffffff06',
                    color: isOverridden ? '#8B5CF6' : C.muted,
                    border: `1px solid ${isOverridden ? '#8B5CF655' : C.border}`,
                    opacity: isOverridden ? 1 : 0.4,
                    transition: 'all 0.2s ease',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  }}
                >
                  🔄 REVERT STRATEGY
                </button>
              </div>
            </div>
          )}

          {/* Warning */}
          {isLive && (
            <div style={{
              padding: '10px 14px', borderRadius: 8,
              background: '#ef444411', border: '1px solid #ef444422',
              display: 'flex', alignItems: 'flex-start', gap: 8,
            }}>
              <span style={{ fontSize: 14, flexShrink: 0, lineHeight: 1 }}>⚠️</span>
              <span style={{ fontSize: 11, fontFamily: font, color: '#ef4444', lineHeight: 1.5 }}>
                LIVE mode is active. All actions will execute real trades on Bybit with real funds. Use with caution.
              </span>
            </div>
          )}
        </div>
      )}

      {/* Pulse animation for LIVE indicator */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Root page
   ═══════════════════════════════════════════════════════════════ */
export default function JC() {
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [activeTab, setActiveTab] = useState("signals");
  const [btcPrice, setBtcPrice] = useState(null);
  const [watcherStatus, setWatcherStatus] = useState(null);
  const [signals, setSignals] = useState([]);
  const [messages, setMessages] = useState([]);
  const [position, setPosition] = useState(null);
  const [pnlStats, setPnlStats] = useState(null);
  const [trades, setTrades] = useState([]);
  const [dailyPnl, setDailyPnl] = useState([]);
  const [config, setConfig] = useState(null);
  const [activeTrade, setActiveTrade] = useState(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const fetchJSON = async (url, fallback) => {
    try {
      const r = await fetch(url);
      if (!r.ok) return fallback;
      return await r.json();
    } catch {
      return fallback;
    }
  };

  // BTC price — 1s live
  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT");
        const d = await r.json();
        if (d?.price) setBtcPrice(Number(d.price));
      } catch {
        const g = await fetchJSON("/api/ghost/price", null);
        if (g?.price) setBtcPrice(g.price);
      }
    };
    load();
    const t = setInterval(load, 1000);
    return () => clearInterval(t);
  }, []);

  // Watcher status — 10s
  useEffect(() => {
    const load = () => fetchJSON("/api/ghost/watcher-status", null).then(setWatcherStatus);
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  // Signals — 5s
  useEffect(() => {
    const load = () => fetchJSON("/api/ghost/signals", []).then(d => setSignals(Array.isArray(d) ? d : d?.signals || []));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  // Messages — 10s
  useEffect(() => {
    const load = () => fetchJSON("/api/ghost/messages", []).then(d => setMessages(Array.isArray(d) ? d : d?.messages || []));
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  // Positions — 5s
  useEffect(() => {
    const load = () => fetchJSON("/api/ghost/positions", null).then(d => {
      const pos = Array.isArray(d) ? d[0] : d?.position || d;
      setPosition(pos && pos.side ? pos : null);
    });
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  // PnL stats — 10s
  useEffect(() => {
    const load = async () => {
      const [pnl, jcStatus] = await Promise.all([
        fetchJSON("/api/ghost/pnl", null),
        fetchJSON("/api/jc/status", null),
      ]);
      const merged = { ...pnl };
      if (jcStatus?.bankroll) {
        merged.balance = jcStatus.bankroll.balance;
        merged.available = jcStatus.bankroll.available;
        merged.in_positions = jcStatus.bankroll.in_positions;
        merged.total_won = jcStatus.bankroll.total_won;
        merged.total_lost = jcStatus.bankroll.total_lost;
        merged.total_trades = jcStatus.bankroll.total_trades || merged.trades;
      }
      setPnlStats(merged);
    };
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  // Trades — 10s
  useEffect(() => {
    const load = () => fetchJSON("/api/ghost/trades", []).then(d => setTrades(Array.isArray(d) ? d : d?.trades || []));
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  // Daily P&L — 30s
  useEffect(() => {
    const load = () => fetchJSON("/api/ghost/daily-pnl", []).then(d => setDailyPnl(Array.isArray(d) ? d : d?.data || []));
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  // Config — 30s
  useEffect(() => {
    const load = () => fetchJSON("/api/ghost/config", null).then(setConfig);
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  // Active JC trade — 3s (Bybit REAL position takes priority over paper DB trades)
  useEffect(() => {
    const load = async () => {
      // 1. Check real Bybit position first
      const bybit = await fetchJSON("/api/jc/bybit/position", null);
      const realPos = bybit?.positions?.find(p => p.size > 0);
      if (realPos) {
        // Map Bybit position to activeTrade format
        setActiveTrade({
          id: 'bybit-live',
          direction: realPos.side === 'Buy' ? 'LONG' : 'SHORT',
          entry: realPos.entry_price,
          entry_price: realPos.entry_price,
          fill_price: realPos.entry_price,
          sl: Number(realPos.stop_loss) || null,
          tp1: Number(realPos.take_profit) || null,
          tp2: null,
          stake: realPos.size * realPos.entry_price / Number(realPos.leverage || 10),
          stake_usd: realPos.size * realPos.entry_price / Number(realPos.leverage || 10),
          leverage: Number(realPos.leverage) || 10,
          notional: realPos.size * realPos.entry_price,
          rr: realPos.take_profit && realPos.stop_loss ? Math.abs(Number(realPos.take_profit) - realPos.entry_price) / Math.abs(realPos.entry_price - Number(realPos.stop_loss)) : null,
          status: 'active',
          reason: 'Bybit Live Position',
          unrealized_pnl: realPos.unrealized_pnl,
          liq_price: realPos.liq_price,
          is_live: true,
          symbol: realPos.symbol,
          size_btc: realPos.size,
        });
        return;
      }
      // 2. Fallback to paper trades from DB
      const d = await fetchJSON("/api/ghost/jc-trades", { trades: [] });
      const trades = d?.trades || [];
      const open = trades.find(t => t.status === 'active' || t.status === 'open');
      setActiveTrade(open || null);
    };
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  const mode = watcherStatus?.mode || config?.mode || "paper";

  return (
    <div style={{
      background: C.bg, minHeight: "100vh", padding: isMobile ? "12px 12px 80px" : "24px 24px 40px",
      fontFamily: font, color: C.text,
      display: "flex", flexDirection: "column", gap: 16,
    }}>
      {/* A. Header */}
      <HeaderBar btcPrice={btcPrice} watcherStatus={watcherStatus} mode={mode} />

      {/* B. Chart */}
      <TVChart isMobile={isMobile} btcPrice={btcPrice} activeTrade={activeTrade} />

      {/* C. Signal Feed */}
      <SignalFeed messages={messages} />

      {/* D. Manual Controls */}
      <ManualControls
        activeTrade={activeTrade}
        btcPrice={btcPrice}
        onRefresh={() => {
          fetchJSON("/api/ghost/jc-trades", { trades: [] }).then(d => {
            const tds = d?.trades || [];
            const open = tds.find(t => t.status === 'active' || t.status === 'open');
            setActiveTrade(open || null);
          });
        }}
      />

      {/* ═══ TAB BAR ═══ */}
      <div style={{
        background: C.card, border: `1px solid ${C.border}`, borderRadius: 12,
        padding: "0 16px",
        display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap",
        minHeight: 52,
      }}>
        {["signals", "trades", "performance", "wwjd", "strategy"].map((t) => (
          <button key={t} onClick={() => setActiveTab(t)} style={{
            background: activeTab === t ? "rgba(255,255,255,0.08)" : "transparent",
            border: activeTab === t ? "1px solid rgba(255,255,255,0.12)" : "1px solid transparent",
            color: activeTab === t ? C.white : C.muted,
            borderRadius: 6,
            padding: isMobile ? "6px 10px" : "5px 14px",
            fontSize: isMobile ? 10 : 11,
            fontFamily: font,
            cursor: "pointer",
            textTransform: "uppercase",
            letterSpacing: 1,
            minHeight: 36,
          }}>{t}</button>
        ))}
      </div>

      {/* ═══ TAB CONTENT ═══ */}
      {activeTab === "signals" && (
        <SignalsTab btcPrice={btcPrice} position={position} messages={messages} signals={signals} />
      )}
      {activeTab === "trades" && (
        <TradesTab trades={trades} pnlStats={pnlStats} isMobile={isMobile} />
      )}
      {activeTab === "performance" && (
        <PerformanceTab pnlStats={pnlStats} dailyPnl={dailyPnl} trades={trades} isMobile={isMobile} />
      )}
      {activeTab === "wwjd" && (
        <WWJDTab position={position} isMobile={isMobile} />
      )}
      {activeTab === "strategy" && (
        <StrategyTab config={config} isMobile={isMobile} />
      )}

      {/* Drill-down overlays */}
      <SignalDrillDown signal={selectedSignal} isOpen={!!selectedSignal} onClose={() => setSelectedSignal(null)} />
      <TradeAnalyzer trade={selectedTrade} isOpen={!!selectedTrade} onClose={() => setSelectedTrade(null)} />
    </div>
  );
}
