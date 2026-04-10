import { useState, useEffect, useCallback } from "react";

/* ═══════════════════════════════════════════════════════════════
   SignalDrillDown — Deep analysis modal for a single JC signal
   Props: { signal, onClose, isOpen }
   ═══════════════════════════════════════════════════════════════ */

const C = {
  bg: "#0a0a0f",
  card: "#1a1a2e",
  cardDeep: "#12121f",
  border: "rgba(255,255,255,0.06)",
  borderAccent: "rgba(124,58,237,0.3)",
  win: "#00ff87",
  loss: "#ff3366",
  accent: "#7c3aed",
  warning: "#f59e0b",
  muted: "#4a5068",
  text: "#c8cdd8",
  white: "#fff",
};
const font = "'JetBrains Mono', 'Fira Code', monospace";

const fmt = (n, dec = 0) =>
  n == null ? "—" : Number(n).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });

const fmtUSD = (n) => (n == null ? "—" : `$${fmt(n, 0)}`);

const formatDate = (ts) => {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleDateString("en-IN", { month: "short", day: "numeric" }) +
    ", " + d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false }) + " IST";
};

/* ─── Shimmer ─── */
const Shimmer = ({ w = "100%", h = 16, br = 6, style = {} }) => (
  <div style={{
    width: w, height: h, borderRadius: br,
    background: `linear-gradient(90deg, ${C.card} 25%, rgba(255,255,255,0.04) 50%, ${C.card} 75%)`,
    backgroundSize: "200% 100%",
    animation: "shimmer 1.4s infinite",
    ...style,
  }} />
);

/* ─── Conviction badge ─── */
const ConvictionBadge = ({ pct }) => {
  if (pct == null) return null;
  const color = pct >= 80 ? C.win : pct >= 60 ? C.warning : C.muted;
  return (
    <span style={{
      background: `${color}22`, color, border: `1px solid ${color}44`,
      borderRadius: 20, padding: "2px 10px", fontSize: 12, fontFamily: font, fontWeight: 700,
    }}>
      {pct}%
    </span>
  );
};

/* ─── Section header ─── */
const Sect = ({ children }) => (
  <div style={{
    fontSize: 10, fontFamily: font, color: C.muted,
    letterSpacing: 2, textTransform: "uppercase",
    borderBottom: `1px solid ${C.border}`, paddingBottom: 8, marginBottom: 16,
  }}>
    {children}
  </div>
);

/* ─── Similar signal row ─── */
const SimilarRow = ({ date, dir, price, outcome, pnl }) => {
  const won = outcome === "WON";
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "8px 0", borderBottom: `1px solid ${C.border}`,
      fontFamily: font, fontSize: 13,
    }}>
      <span style={{ color: C.muted, minWidth: 50 }}>{date}</span>
      <span style={{
        background: dir === "SHORT" ? `${C.loss}22` : `${C.win}22`,
        color: dir === "SHORT" ? C.loss : C.win,
        border: `1px solid ${dir === "SHORT" ? C.loss : C.win}44`,
        borderRadius: 4, padding: "1px 8px", fontSize: 11,
      }}>{dir}</span>
      <span style={{ color: C.text }}>{fmtUSD(price)}</span>
      <span style={{ color: won ? C.win : C.loss, fontWeight: 700 }}>
        {won ? "✓ WON" : "✗ LOST"}
      </span>
      <span style={{ color: won ? C.win : C.loss, fontWeight: 700 }}>
        {pnl >= 0 ? "+" : ""}{fmtUSD(pnl)}
      </span>
    </div>
  );
};

/* ─── Button ─── */
const Btn = ({ children, onClick, color = C.accent, outline = false, style = {} }) => (
  <button onClick={onClick} style={{
    minHeight: 44, padding: "10px 20px",
    background: outline ? "transparent" : color,
    color: outline ? color : C.white,
    border: `1px solid ${color}`,
    borderRadius: 8, cursor: "pointer",
    fontFamily: font, fontSize: 13, fontWeight: 700,
    letterSpacing: 0.5,
    transition: "all 0.15s",
    flex: 1,
    ...style,
  }}>
    {children}
  </button>
);

/* ═══════════════════════════════════════════════════════════════
   Main component
   ═══════════════════════════════════════════════════════════════ */
export default function SignalDrillDown({ signal, onClose, isOpen }) {
  const [priceCtx, setPriceCtx] = useState(null);
  const [loadingPrice, setLoadingPrice] = useState(false);
  const [copied, setCopied] = useState(false);

  /* Fetch market context when panel opens */
  useEffect(() => {
    if (!isOpen || !signal) return;
    setLoadingPrice(true);
    fetch("/api/ghost/price")
      .then((r) => r.json())
      .then((d) => setPriceCtx(d))
      .catch(() => setPriceCtx(null))
      .finally(() => setLoadingPrice(false));
  }, [isOpen, signal]);

  /* Trap ESC key */
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  /* Prevent body scroll when open */
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  if (!signal) return null;

  /* Derived values */
  const dir = signal.direction || signal.signal_direction || "—";
  const conviction = signal.conviction_pct ?? signal.conviction ?? null;
  const entry = signal.entry_price ?? signal.parsed_entry ?? null;
  const sl = signal.stop_loss ?? signal.parsed_sl ?? null;
  const tp = signal.take_profit ?? signal.parsed_tp ?? null;
  const rrRaw = entry && sl && tp
    ? Math.abs((tp - entry) / (sl - entry))
    : null;
  const rr = rrRaw ? `${rrRaw.toFixed(1)}:1` : "—";
  const classification = signal.classification || signal.signal_type || "ENTRY SIGNAL";
  const channel = signal.channel_name || signal.source_channel || "#ᴊᴀʏꜱᴏɴ-btc-ta";
  const author = signal.author || signal.username || "jayson_casper";
  const rawText = signal.raw_content || signal.text || signal.message || "(no message)";
  const timestamp = signal.timestamp || signal.created_at || signal.ts;

  /* Placeholder similar signals */
  const similarSignals = [
    { date: "Apr 8", dir: dir || "SHORT", price: entry ? entry - 1000 : 71100, outcome: "WON", pnl: 450 },
    { date: "Apr 7", dir: dir || "SHORT", price: entry ? entry - 1300 : 70800, outcome: "LOST", pnl: -150 },
    { date: "Apr 6", dir: dir || "SHORT", price: entry ? entry - 2600 : 69500, outcome: "WON", pnl: 200 },
  ];
  const winRate = Math.round((similarSignals.filter((s) => s.outcome === "WON").length / similarSignals.length) * 100);

  /* Price context */
  const btcPrice = priceCtx?.price ?? priceCtx?.last ?? priceCtx?.usd ?? null;
  const change24h = priceCtx?.change_24h ?? priceCtx?.change_pct ?? null;
  const volume24h = priceCtx?.volume_24h ?? priceCtx?.volume ?? null;

  const handleCopyTrade = () => {
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    /* Emit custom event so JC.jsx can intercept */
    window.dispatchEvent(new CustomEvent("jc:copy-trade", { detail: { signal } }));
  };

  /* ── Overlay + panel ── */
  return (
    <>
      {/* Shimmer keyframes */}
      <style>{`
        @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        @keyframes slideInRight { from{transform:translateX(100%);opacity:0} to{transform:translateX(0);opacity:1} }
        @keyframes fadeIn { from{opacity:0} to{opacity:1} }
        @media(max-width:768px){
          .sdd-panel { width: 100% !important; right: 0 !important; border-radius: 16px 16px 0 0 !important; top: auto !important; bottom: 0 !important; max-height: 92vh !important; }
        }
      `}</style>

      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0, zIndex: 900,
          background: "rgba(0,0,0,0.65)",
          backdropFilter: "blur(2px)",
          opacity: isOpen ? 1 : 0,
          transition: "opacity 0.25s",
          pointerEvents: isOpen ? "auto" : "none",
        }}
      />

      {/* Side panel */}
      <div
        className="sdd-panel"
        style={{
          position: "fixed", top: 0, right: 0, bottom: 0,
          width: "min(520px, 100vw)",
          zIndex: 901,
          background: C.bg,
          borderLeft: `1px solid ${C.borderAccent}`,
          overflowY: "auto",
          transform: isOpen ? "translateX(0)" : "translateX(100%)",
          transition: "transform 0.3s cubic-bezier(0.4,0,0.2,1)",
          padding: "24px 24px 40px",
          fontFamily: font,
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 24 }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.white, letterSpacing: -0.5 }}>
              ⚡ SIGNAL DEEP DIVE
            </div>
            <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>{formatDate(timestamp)}</div>
          </div>
          <button
            onClick={onClose}
            style={{
              minWidth: 44, minHeight: 44, background: "transparent",
              border: `1px solid ${C.border}`, borderRadius: 8,
              color: C.muted, fontSize: 18, cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >
            ✕
          </button>
        </div>

        {/* Source meta */}
        <div style={{
          background: C.card, borderRadius: 10, padding: "14px 16px",
          border: `1px solid ${C.border}`, marginBottom: 20,
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10,
        }}>
          <div>
            <div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 4 }}>Source</div>
            <div style={{ fontSize: 13, color: C.warning }}>{channel}</div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 4 }}>Author</div>
            <div style={{ fontSize: 13, color: C.accent }}>👤 {author}</div>
          </div>
        </div>

        {/* Jayson's message */}
        <div style={{ marginBottom: 24 }}>
          <Sect>Jayson's Message</Sect>
          <div style={{
            background: C.cardDeep, border: `1px solid ${C.border}`,
            borderRadius: 10, padding: "16px",
            fontSize: 13, color: C.text, lineHeight: 1.7,
            whiteSpace: "pre-wrap", wordBreak: "break-word",
            maxHeight: 180, overflowY: "auto",
          }}>
            {rawText}
          </div>
        </div>

        {/* AI Analysis */}
        <div style={{ marginBottom: 24 }}>
          <Sect>AI Analysis</Sect>
          <div style={{
            background: C.card, borderRadius: 10, border: `1px solid ${C.border}`,
            overflow: "hidden",
          }}>
            {[
              { label: "Classification", value: <span style={{ color: C.warning, fontWeight: 700 }}>{classification}</span> },
              {
                label: "Direction", value: (
                  <span style={{
                    color: dir === "SHORT" || dir === "DOWN" ? C.loss : dir === "LONG" || dir === "UP" ? C.win : C.muted,
                    fontWeight: 700,
                  }}>{dir}</span>
                )
              },
              { label: "Conviction", value: <ConvictionBadge pct={conviction} /> },
              { label: "Entry", value: <span style={{ color: C.white, fontWeight: 700 }}>{fmtUSD(entry)}</span> },
              { label: "Stop Loss", value: <span style={{ color: C.loss }}>{fmtUSD(sl)}</span> },
              { label: "Take Profit", value: <span style={{ color: C.win }}>{fmtUSD(tp)}</span> },
              { label: "R:R Ratio", value: <span style={{ color: C.accent, fontWeight: 700 }}>{rr}</span> },
            ].map(({ label, value }, i) => (
              <div key={label} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "11px 16px",
                borderBottom: i < 6 ? `1px solid ${C.border}` : "none",
                fontSize: 13,
              }}>
                <span style={{ color: C.muted }}>{label}</span>
                <span>{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Market Context */}
        <div style={{ marginBottom: 24 }}>
          <Sect>Market Context</Sect>
          {loadingPrice ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Shimmer h={14} w="60%" />
              <Shimmer h={14} w="40%" />
              <Shimmer h={14} w="50%" />
            </div>
          ) : (
            <div style={{
              background: C.card, borderRadius: 10, border: `1px solid ${C.border}`,
              overflow: "hidden",
            }}>
              {[
                {
                  label: "BTC Price", value: btcPrice
                    ? <span style={{ color: C.white, fontWeight: 700 }}>${fmt(btcPrice, 0)}</span>
                    : <span style={{ color: C.muted }}>—</span>
                },
                {
                  label: "24H Change", value: change24h != null
                    ? <span style={{ color: change24h >= 0 ? C.win : C.loss, fontWeight: 700 }}>
                      {change24h >= 0 ? "+" : ""}{change24h?.toFixed(2)}%
                    </span>
                    : <span style={{ color: C.muted }}>—</span>
                },
                {
                  label: "24H Volume", value: volume24h
                    ? <span style={{ color: C.text }}>${(volume24h / 1e9).toFixed(1)}B</span>
                    : <span style={{ color: C.muted }}>—</span>
                },
              ].map(({ label, value }, i) => (
                <div key={label} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "11px 16px",
                  borderBottom: i < 2 ? `1px solid ${C.border}` : "none",
                  fontSize: 13,
                }}>
                  <span style={{ color: C.muted }}>{label}</span>
                  <span>{value}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Similar Past Signals */}
        <div style={{ marginBottom: 28 }}>
          <Sect>Similar Past Signals (7 days)</Sect>
          <div style={{
            background: C.card, borderRadius: 10, border: `1px solid ${C.border}`,
            padding: "4px 16px 0",
          }}>
            {similarSignals.map((s, i) => (
              <SimilarRow key={i} {...s} />
            ))}
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "12px 0", fontSize: 13,
            }}>
              <span style={{ color: C.muted }}>Win rate on similar</span>
              <span style={{
                color: winRate >= 60 ? C.win : C.loss,
                fontWeight: 700, fontSize: 15,
              }}>{winRate}%</span>
            </div>
          </div>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 8, textAlign: "center" }}>
            * Placeholder data — more history needed for accurate similarity matching
          </div>
        </div>

        {/* Action buttons */}
        <div style={{ display: "flex", gap: 10 }}>
          <Btn onClick={handleCopyTrade} color={C.win} style={{ color: C.bg }}>
            {copied ? "✓ QUEUED" : "⚡ COPY TRADE"}
          </Btn>
          <Btn onClick={onClose} color={C.muted} outline>
            SKIP
          </Btn>
          <Btn
            onClick={() => window.dispatchEvent(new CustomEvent("jc:analyze-more", { detail: { signal } }))}
            color={C.accent} outline
          >
            ANALYZE MORE
          </Btn>
        </div>
      </div>
    </>
  );
}
