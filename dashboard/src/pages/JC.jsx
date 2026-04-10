import { useState, useEffect, useRef } from "react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
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
   B. TradingView Chart
   ═══════════════════════════════════════════════════════════════ */
function TVChart({ isMobile }) {
  const containerRef = useRef(null);
  const widgetRef = useRef(null);
  const [showJC, setShowJC] = useState(true);
  const [imgTs, setImgTs] = useState(Date.now());

  useEffect(() => {
    const iv = setInterval(() => setImgTs(Date.now()), 30000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    const containerId = "tv_chart_jc_interactive";
    const initWidget = () => {
      if (!window.TradingView || !containerRef.current || widgetRef.current) return;
      widgetRef.current = new window.TradingView.widget({
        container_id: containerId, autosize: true,
        symbol: "BINANCE:BTCUSDT.P", interval: "240",
        timezone: "Asia/Kolkata", theme: "dark", style: "1", locale: "en",
        toolbar_bg: C.card, enable_publishing: false,
        hide_top_toolbar: false, hide_legend: false,
        withdateranges: true, allow_symbol_change: true,
        details: true, hotlist: false, calendar: false,
        studies: ["Volume@tv-basicstudies", "VWAP@tv-basicstudies", "RSI@tv-basicstudies"],
        backgroundColor: C.bg, gridColor: "rgba(255,255,255,0.03)",
      });
    };
    if (window.TradingView) { initWidget(); return; }
    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/tv.js";
    script.async = true;
    script.onload = () => setTimeout(initWidget, 300);
    document.head.appendChild(script);
    return () => { widgetRef.current = null; };
  }, []);

  return (
    <div>
      <div style={{ display: "flex", gap: 6, padding: "8px 12px", background: C.bg }}>
        <button onClick={() => setShowJC(false)} style={{
          background: !showJC ? "rgba(255,255,255,0.08)" : "transparent",
          border: !showJC ? "1px solid rgba(255,255,255,0.12)" : "1px solid transparent",
          color: !showJC ? C.white : C.muted, borderRadius: 6, padding: "5px 12px",
          fontSize: 10, fontFamily: font, cursor: "pointer", letterSpacing: 1, minHeight: 32,
        }}>INTERACTIVE CHART</button>
        <button onClick={() => setShowJC(true)} style={{
          background: showJC ? "rgba(124,58,237,0.15)" : "transparent",
          border: showJC ? "1px solid rgba(124,58,237,0.3)" : "1px solid transparent",
          color: showJC ? C.accent : C.muted, borderRadius: 6, padding: "5px 12px",
          fontSize: 10, fontFamily: font, cursor: "pointer", letterSpacing: 1, minHeight: 32,
        }}>JAYSON LIVE (CDP)</button>
      </div>
      <Card style={{ padding: 0, overflow: "hidden", display: showJC ? "none" : "block" }}>
        <div id="tv_chart_jc_interactive" ref={containerRef}
          style={{ width: "100%", height: isMobile ? 380 : 550 }} />
      </Card>
      {showJC && (
        <Card style={{ padding: 0, overflow: "hidden", position: "relative" }}>
          <div style={{ position: "absolute", top: 8, left: 12, zIndex: 2, display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 9, color: C.accent, fontFamily: font, letterSpacing: 1, background: "rgba(0,0,0,0.8)", padding: "3px 8px", borderRadius: 4 }}>
              JAYSON CASPER LIVE CHART
            </span>
            <span style={{ fontSize: 8, color: C.muted, fontFamily: font, background: "rgba(0,0,0,0.7)", padding: "2px 6px", borderRadius: 3 }}>
              Auto-refresh 30s
            </span>
          </div>
          <img src={"/tv-live.png?" + imgTs} alt="Jayson Chart"
            onError={(e) => { e.target.style.display = "none"; }}
            style={{ width: "100%", height: isMobile ? 380 : 550, objectFit: "cover", display: "block" }} />
        </Card>
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

      {/* Active Position Card */}
      <Card>
        <SectionTitle>🎯 Active Position</SectionTitle>
        {position ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 12 }}>
            {[
              { label: "Side", value: position.side, color: position.side === "LONG" ? C.win : C.loss },
              { label: "Entry", value: position.entry_price ? `$${fmt(position.entry_price)}` : "—", color: C.white },
              { label: "Unrealized P&L", value: position.unrealized_pnl != null ? `${Number(position.unrealized_pnl) >= 0 ? "+" : ""}$${fmt(position.unrealized_pnl)}` : "—", color: Number(position.unrealized_pnl) >= 0 ? C.win : C.loss },
              { label: "State", value: position.state || "OPEN", color: C.accent },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ background: "#0f0f1a", borderRadius: 8, padding: "12px 14px", border: `1px solid ${C.border}` }}>
                <div style={{ fontSize: 9, fontFamily: font, color: C.muted, letterSpacing: 1, marginBottom: 6 }}>{label}</div>
                <div style={{ fontSize: 16, fontFamily: font, fontWeight: 700, color }}>{value}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "24px 0", color: C.muted, fontSize: 13, fontFamily: font }}>
            No open position
          </div>
        )}
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
   TAB: STRATEGY
   ═══════════════════════════════════════════════════════════════ */
function StrategyTab({ config, isMobile }) {
  const [settings, setSettings] = useState(null);
  const [editing, setEditing] = useState(null);
  const [editVal, setEditVal] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const load = () => fetchJSON('/api/ghost/jc-settings', null).then(d => d?.settings && setSettings(d.settings));
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
    const load = () => fetchJSON("/api/ghost/pnl", null).then(setPnlStats);
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
      <TVChart isMobile={isMobile} />

      {/* C. Signal Feed */}
      <SignalFeed messages={messages} />

      {/* ═══ TAB BAR ═══ */}
      <div style={{
        background: C.card, border: `1px solid ${C.border}`, borderRadius: 12,
        padding: "0 16px",
        display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap",
        minHeight: 52,
      }}>
        {["signals", "trades", "performance", "strategy"].map((t) => (
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
      {activeTab === "strategy" && (
        <StrategyTab config={config} isMobile={isMobile} />
      )}

      {/* Drill-down overlays */}
      <SignalDrillDown signal={selectedSignal} isOpen={!!selectedSignal} onClose={() => setSelectedSignal(null)} />
      <TradeAnalyzer trade={selectedTrade} isOpen={!!selectedTrade} onClose={() => setSelectedTrade(null)} />
    </div>
  );
}
