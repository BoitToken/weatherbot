import { useState, useEffect, useRef } from "react";
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

const SectionTitle = ({ children }) => (
  <div style={{ fontSize: 11, fontFamily: font, color: C.muted, letterSpacing: 2, textTransform: "uppercase", marginBottom: 16 }}>
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
        {/* Watcher dot */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontFamily: font, color: C.text }}>
          <span style={{
            width: 8, height: 8, borderRadius: "50%",
            background: online ? C.win : C.loss,
            boxShadow: online ? `0 0 6px ${C.win}` : "none",
            display: "inline-block",
          }} />
          WATCHER {online ? "LIVE" : "OFF"}
        </div>
        {/* Mode badge */}
        <span style={{
          padding: "4px 10px", borderRadius: 6, fontSize: 11, fontFamily: font, fontWeight: 700,
          background: mode === "live" ? `${C.loss}22` : `${C.accent}22`,
          color: mode === "live" ? C.loss : C.accent,
          border: `1px solid ${mode === "live" ? C.loss : C.accent}44`,
          textTransform: "uppercase",
        }}>
          {mode || "PAPER"}
        </span>
        {/* BTC price */}
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
  const [imgTs, setImgTs] = useState(Date.now());
  const [imgError, setImgError] = useState(false);

  // Refresh screenshot every 30s
  useEffect(() => {
    const iv = setInterval(() => setImgTs(Date.now()), 30000);
    return () => clearInterval(iv);
  }, []);

  return (
    <Card style={{ padding: 0, overflow: "hidden", position: "relative" }}>
      <div style={{ position: "absolute", top: 8, left: 12, zIndex: 2, display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 9, color: C.accent, fontFamily: font, letterSpacing: 1, background: "rgba(0,0,0,0.7)", padding: "3px 8px", borderRadius: 4 }}>
          JAYSON CASPER LIVE CHART
        </span>
        <span style={{ fontSize: 8, color: C.muted, fontFamily: font, background: "rgba(0,0,0,0.7)", padding: "2px 6px", borderRadius: 3 }}>
          Auto-refresh 30s
        </span>
      </div>
      {!imgError ? (
        <img
          src={"/tv-live.png?" + imgTs}
          alt="Jayson Casper TradingView Chart"
          onError={() => setImgError(true)}
          style={{ width: "100%", height: isMobile ? 350 : 500, objectFit: "cover", display: "block" }}
        />
      ) : (
        <div style={{ width: "100%", height: isMobile ? 350 : 500, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 8 }}>
          <span style={{ fontSize: 32 }}>📊</span>
          <span style={{ color: C.muted, fontFamily: font, fontSize: 11 }}>TradingView not connected</span>
          <span style={{ color: C.muted, fontFamily: font, fontSize: 9 }}>Open TradingView Desktop + SSH tunnel</span>
        </div>
      )}
    </Card>
  );
}

/* ═══════════════════════════════════════════════════════════════
   C. Signal Feed — single message card
   ═══════════════════════════════════════════════════════════════ */
function MessageCard({ msg }) {
  const [expanded, setExpanded] = useState(false);
  const sig = msg.signal;
  const dirColor = sig?.direction === "LONG" ? C.win : sig?.direction === "SHORT" ? C.loss : C.warning;

  return (
    <div
      onClick={() => setExpanded(e => !e)}
      style={{
        background: "#0f0f1a",
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: "12px 16px",
        cursor: "pointer",
        transition: "border-color 0.2s",
        borderColor: expanded ? C.accent + "66" : C.border,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 6 }}>
        {/* Channel badge */}
        <span style={{
          fontSize: 10, fontFamily: font, padding: "2px 7px", borderRadius: 4,
          background: `${channelColor(msg.channel)}22`, color: channelColor(msg.channel),
          border: `1px solid ${channelColor(msg.channel)}44`, flexShrink: 0, marginTop: 1,
        }}>
          #{msg.channel || "discord"}
        </span>

        {/* Signal badge */}
        {sig && (
          <span style={{
            fontSize: 10, fontFamily: font, padding: "2px 8px", borderRadius: 4,
            background: `${dirColor}22`, color: dirColor,
            border: `1px solid ${dirColor}44`, flexShrink: 0, marginTop: 1, fontWeight: 700,
          }}>
            ⚡ {sig.direction} {sig.conviction ? `· ${sig.conviction}` : ""}
          </span>
        )}

        {/* Attachment badge */}
        {msg.has_attachments && (
          <span style={{ fontSize: 11, marginTop: 1 }}>📷</span>
        )}

        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 10, fontFamily: font, color: C.muted, flexShrink: 0 }}>
          {timeAgo(msg.created_at || msg.timestamp)}
        </span>
      </div>

      <div style={{ fontSize: 13, color: C.text, lineHeight: 1.55, fontFamily: "'Inter', sans-serif", wordBreak: "break-word" }}>
        {expanded ? (msg.content || msg.message || "—") : (msg.content || msg.message || "—").slice(0, 180) + ((msg.content || msg.message || "").length > 180 ? "…" : "")}
      </div>

      {expanded && msg.raw && (
        <pre style={{
          marginTop: 10, padding: 10, background: "#070710", borderRadius: 6,
          fontSize: 11, color: C.muted, fontFamily: font, overflowX: "auto", whiteSpace: "pre-wrap",
        }}>
          {typeof msg.raw === "string" ? msg.raw : JSON.stringify(msg.raw, null, 2)}
        </pre>
      )}

      {/* Strategy Panel Button */}
      <div style={{ padding: "0 24px 16px", display: "flex", justifyContent: "center" }}>
        <button onClick={() => setShowStrategy(s => !s)} style={{
          background: showStrategy ? C.accent + "33" : "rgba(255,255,255,0.05)",
          border: "1px solid " + (showStrategy ? C.accent : C.border),
          color: showStrategy ? C.accent : C.muted,
          borderRadius: 8, padding: "10px 24px", fontFamily: font,
          fontSize: 12, cursor: "pointer", letterSpacing: 1,
        }}>
          {showStrategy ? "▼ HIDE STRATEGY" : "▶ SHOW V4 STRATEGY INTELLIGENCE"}
        </button>
      </div>
      {showStrategy && <div style={{ padding: "0 24px 24px" }}><StrategyPanel compact={false} /></div>}

      {/* Drill-down panels */}
      <SignalDrillDown signal={selectedSignal} isOpen={!!selectedSignal} onClose={() => setSelectedSignal(null)} />
      <TradeAnalyzer trade={selectedTrade} isOpen={!!selectedTrade} onClose={() => setSelectedTrade(null)} />

    </div>
  );
}

function SignalFeed({ signals, messages }) {
  // Merge signals + messages, dedupe by id, sort newest first
  const all = [...(signals || []), ...(messages || [])];
  const seen = new Set();
  const deduped = all.filter(m => {
    const k = m.id || m.message_id || (m.content || m.message || "") + (m.created_at || m.timestamp || "");
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  deduped.sort((a, b) => {
    const ta = new Date(a.created_at || a.timestamp || 0).getTime();
    const tb = new Date(b.created_at || b.timestamp || 0).getTime();
    return tb - ta;
  });
  const items = deduped.slice(0, 20);

  return (
    <Card>
      <SectionTitle>📡 Signal Feed — Jayson Casper Discord</SectionTitle>
      {items.length === 0 ? (
        <div style={{ textAlign: "center", padding: "32px 0", color: C.muted, fontSize: 13, fontFamily: font }}>
          👻 Listening to Jayson's Discord... no messages yet
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {items.map((m, i) => <div key={m.id || m.message_id || i} onClick={() => setSelectedSignal(m)} style={{cursor:"pointer"}}><MessageCard msg={m} /></div>)}
        </div>
      )}
    </Card>
  );
}

/* ═══════════════════════════════════════════════════════════════
   D. Copy Trade Controls
   ═══════════════════════════════════════════════════════════════ */
function CopyTradeControls({ position, pnlStats }) {
  return (
    <Card>
      <SectionTitle>⚡ Copy Trade Controls</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>

        {/* Strategy */}
        <div style={{ background: "#0f0f1a", borderRadius: 10, padding: "14px 16px", border: `1px solid ${C.border}` }}>
          <div style={{ fontSize: 10, fontFamily: font, color: C.muted, marginBottom: 10, letterSpacing: 1 }}>STRATEGY</div>
          <div style={{ fontSize: 12, fontFamily: font, color: C.text, lineHeight: 1.8 }}>
            <div>Entry Range: <span style={{ color: C.warning }}>Market / Limit</span></div>
            <div>Bias: <span style={{ color: C.win }}>Follow JC Signal</span></div>
            <div>Conviction: <span style={{ color: C.accent }}>HIGH → 2x size</span></div>
          </div>
        </div>

        {/* Active position */}
        <div style={{ background: "#0f0f1a", borderRadius: 10, padding: "14px 16px", border: `1px solid ${position ? C.accent + "55" : C.border}` }}>
          <div style={{ fontSize: 10, fontFamily: font, color: C.muted, marginBottom: 10, letterSpacing: 1 }}>ACTIVE POSITION</div>
          {position ? (
            <div style={{ fontSize: 12, fontFamily: font, color: C.text, lineHeight: 1.8 }}>
              <div>Side: <span style={{ color: position.side === "LONG" ? C.win : C.loss, fontWeight: 700 }}>{position.side}</span></div>
              <div>Entry: <span style={{ color: C.white }}>${fmt(position.entry_price)}</span></div>
              <div>P&L: {fmtPnl(position.unrealized_pnl)}</div>
              <div>State: <span style={{ color: C.accent }}>{position.state || "OPEN"}</span></div>
            </div>
          ) : (
            <div style={{ color: C.muted, fontSize: 12, fontFamily: font }}>No open position</div>
          )}
        </div>

        {/* Quick stats */}
        <div style={{ background: "#0f0f1a", borderRadius: 10, padding: "14px 16px", border: `1px solid ${C.border}` }}>
          <div style={{ fontSize: 10, fontFamily: font, color: C.muted, marginBottom: 10, letterSpacing: 1 }}>PERFORMANCE</div>
          <div style={{ fontSize: 12, fontFamily: font, color: C.text, lineHeight: 1.8 }}>
            <div>Total P&L: {fmtPnl(pnlStats?.total_pnl)}</div>
            <div>Win Rate: <span style={{ color: C.win }}>{pnlStats?.win_rate != null ? `${fmt(pnlStats.win_rate * 100, 1)}%` : "—"}</span></div>
            <div>Trades: <span style={{ color: C.white }}>{pnlStats?.total_trades ?? "—"}</span></div>
          </div>
        </div>

      </div>
    </Card>
  );
}

/* ═══════════════════════════════════════════════════════════════
   E. Trade History
   ═══════════════════════════════════════════════════════════════ */
function TradeHistory({ trades }) {
  const rows = (trades || []).slice(0, 10);

  return (
    <Card>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <SectionTitle style={{ margin: 0 }}>📋 Trade History</SectionTitle>
        <span style={{ fontSize: 11, fontFamily: font, color: C.accent, cursor: "pointer" }}>
          View all →
        </span>
      </div>

      {rows.length === 0 ? (
        <div style={{ color: C.muted, fontSize: 12, fontFamily: font, textAlign: "center", padding: "20px 0" }}>
          No trades yet
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: font }}>
            <thead>
              <tr style={{ color: C.muted, fontSize: 10, letterSpacing: 1, textTransform: "uppercase" }}>
                {["Side", "Entry", "Exit", "P&L", "Reason", "Duration"].map(h => (
                  <th key={h} style={{ padding: "6px 10px", textAlign: "left", borderBottom: `1px solid ${C.border}`, whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((t, i) => { const handleTradeClick = () => setSelectedTrade(t);
                const pnl = Number(t.pnl ?? t.realized_pnl ?? 0);
                const isLong = (t.side || "").toUpperCase() === "LONG";
                const dur = t.duration_sec != null ? `${Math.floor(t.duration_sec / 60)}m` : "—";
                return (
                  <tr key={t.id || i} style={{ borderBottom: `1px solid ${C.border}`, color: C.text }}>
                    <td style={{ padding: "8px 10px" }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 700,
                        background: isLong ? `${C.win}22` : `${C.loss}22`,
                        color: isLong ? C.win : C.loss,
                        border: `1px solid ${isLong ? C.win : C.loss}44`,
                      }}>{(t.side || "?").toUpperCase()}</span>
                    </td>
                    <td style={{ padding: "8px 10px" }}>${fmt(t.entry_price)}</td>
                    <td style={{ padding: "8px 10px" }}>{t.exit_price ? `$${fmt(t.exit_price)}` : "—"}</td>
                    <td style={{ padding: "8px 10px" }}>{fmtPnl(pnl)}</td>
                    <td style={{ padding: "8px 10px", color: C.muted }}>{t.close_reason || "—"}</td>
                    <td style={{ padding: "8px 10px", color: C.muted }}>{dur}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Root page
   ═══════════════════════════════════════════════════════════════ */
export default function JC() {
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [showStrategy, setShowStrategy] = useState(false);
  const [btcPrice, setBtcPrice] = useState(null);
  const [watcherStatus, setWatcherStatus] = useState(null);
  const [signals, setSignals] = useState([]);
  const [messages, setMessages] = useState([]);
  const [position, setPosition] = useState(null);
  const [pnlStats, setPnlStats] = useState(null);
  const [trades, setTrades] = useState([]);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  // Mobile detection
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // Fetch helpers
  const fetchJSON = async (url, fallback) => {
    try {
      const r = await fetch(url);
      if (!r.ok) return fallback;
      return await r.json();
    } catch {
      return fallback;
    }
  };

  // BTC price — 3s
  useEffect(() => {
    const load = async () => {
      const d = await fetchJSON("/api/btc/state", null);
      if (d?.price) setBtcPrice(d.price);
      else {
        const g = await fetchJSON("/api/ghost/price", null);
        if (g?.price) setBtcPrice(g.price);
      }
    };
    load();
    const t = setInterval(load, 3000);
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

  // Determine mode from watcher status
  const mode = watcherStatus?.mode || "paper";

  return (
    <div style={{
      background: C.bg, minHeight: "100vh", padding: isMobile ? "12px" : "24px",
      fontFamily: font, color: C.text,
      display: "flex", flexDirection: "column", gap: 16,
    }}>
      {/* A. Header */}
      <HeaderBar btcPrice={btcPrice} watcherStatus={watcherStatus} mode={mode} />

      {/* B. Chart */}
      <TVChart isMobile={isMobile} />

      {/* C. Signal Feed */}
      <SignalFeed signals={signals} messages={messages} />

      {/* D. Copy Trade Controls */}
      <CopyTradeControls position={position} pnlStats={pnlStats} />

      {/* E. Trade History */}
      <TradeHistory trades={trades} />
    </div>
  );
}
