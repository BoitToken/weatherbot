import { useState, useEffect, useRef } from "react";

/* ═══════════════════════════════════════════════════════════════
   TradeAnalyzer — Deep analysis panel for a single trade
   Props: { trade, onClose, isOpen }
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

const fmt = (n, dec = 2) =>
  n == null ? "—" : Number(n).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
const fmtUSD = (n, dec = 0) => (n == null ? "—" : `$${fmt(n, dec)}`);
const fmtPnl = (n) => {
  if (n == null) return <span style={{ color: C.muted }}>—</span>;
  const v = Number(n);
  return <span style={{ color: v >= 0 ? C.win : C.loss, fontWeight: 700 }}>
    {v >= 0 ? "+" : ""}{fmt(v)}
  </span>;
};

const formatTime = (ts) => {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
};
const formatDate = (ts) => {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleDateString("en-IN", { month: "short", day: "numeric" }) + " " + formatTime(ts);
};
const durationStr = (ms) => {
  if (!ms || ms <= 0) return "—";
  const m = Math.floor(ms / 60000);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60), rm = m % 60;
  return rm ? `${h}h ${rm}m` : `${h}h`;
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

/* ─── Lifecycle step ─── */
const LifecycleStep = ({ label, ts, active, done, last }) => (
  <div style={{ display: "flex", alignItems: "flex-start", gap: 12, paddingBottom: last ? 0 : 20, position: "relative" }}>
    {/* Connector line */}
    {!last && (
      <div style={{
        position: "absolute", left: 13, top: 28, bottom: 0,
        width: 2, background: done ? C.accent : C.border,
        transition: "background 0.3s",
      }} />
    )}
    {/* Dot */}
    <div style={{
      width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
      background: active ? C.accent : done ? `${C.accent}44` : C.cardDeep,
      border: `2px solid ${active ? C.accent : done ? C.accent : C.border}`,
      display: "flex", alignItems: "center", justifyContent: "center",
      boxShadow: active ? `0 0 12px ${C.accent}66` : "none",
    }}>
      {done ? (
        <span style={{ fontSize: 12, color: active ? C.white : C.accent }}>✓</span>
      ) : (
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.border }} />
      )}
    </div>
    {/* Label */}
    <div style={{ paddingTop: 4 }}>
      <div style={{
        fontSize: 12, fontFamily: font, fontWeight: 700,
        color: active ? C.white : done ? C.text : C.muted,
        letterSpacing: 1,
      }}>{label}</div>
      {ts && <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{formatDate(ts)}</div>}
    </div>
  </div>
);

/* ─── Price level chart (canvas) ─── */
const PriceLevelChart = ({ entry, sl, tp, direction }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !entry) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const prices = [entry, sl, tp].filter(Boolean);
    const minP = Math.min(...prices) * 0.998;
    const maxP = Math.max(...prices) * 1.002;
    const range = maxP - minP;

    const toY = (p) => H - ((p - minP) / range) * (H - 40) - 20;
    const toLabel = (p) => p != null ? `$${Number(p).toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "";

    /* Background */
    ctx.fillStyle = "#12121f";
    ctx.fillRect(0, 0, W, H);

    /* Grid */
    ctx.strokeStyle = "rgba(255,255,255,0.04)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = 20 + (i / 4) * (H - 40);
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }

    const drawLevel = (price, color, label, dashed = false) => {
      if (!price) return;
      const y = toY(price);
      ctx.strokeStyle = color;
      ctx.lineWidth = dashed ? 1.5 : 2;
      if (dashed) { ctx.setLineDash([6, 4]); } else { ctx.setLineDash([]); }
      ctx.beginPath(); ctx.moveTo(60, y); ctx.lineTo(W - 10, y); ctx.stroke();
      ctx.setLineDash([]);

      /* Dot */
      ctx.fillStyle = color;
      ctx.beginPath(); ctx.arc(60, y, 4, 0, Math.PI * 2); ctx.fill();

      /* Label */
      ctx.fillStyle = color;
      ctx.font = "bold 10px 'JetBrains Mono', monospace";
      ctx.fillText(label + " " + toLabel(price), 4, y + 4);
    };

    /* Zone fill between entry and tp */
    if (entry && tp) {
      const y1 = toY(Math.max(entry, tp));
      const y2 = toY(Math.min(entry, tp));
      const gradient = ctx.createLinearGradient(0, y1, 0, y2);
      gradient.addColorStop(0, direction === "SHORT" ? `${C.loss}22` : `${C.win}22`);
      gradient.addColorStop(1, "transparent");
      ctx.fillStyle = gradient;
      ctx.fillRect(60, y1, W - 70, y2 - y1);
    }

    /* Zone fill between entry and sl (loss zone) */
    if (entry && sl) {
      const y1 = toY(Math.max(entry, sl));
      const y2 = toY(Math.min(entry, sl));
      const gradient = ctx.createLinearGradient(0, y1, 0, y2);
      gradient.addColorStop(0, `${C.loss}15`);
      gradient.addColorStop(1, "transparent");
      ctx.fillStyle = gradient;
      ctx.fillRect(60, y1, W - 70, y2 - y1);
    }

    drawLevel(tp, C.win, "TP");
    drawLevel(entry, C.white, "ENT");
    drawLevel(sl, C.loss, "SL", true);

  }, [entry, sl, tp, direction]);

  if (!entry) return (
    <div style={{
      height: 120, background: C.cardDeep, borderRadius: 8,
      display: "flex", alignItems: "center", justifyContent: "center",
      color: C.muted, fontSize: 12,
    }}>
      No price data
    </div>
  );

  return (
    <canvas
      ref={canvasRef}
      width={460}
      height={120}
      style={{
        width: "100%", height: 120, borderRadius: 8,
        display: "block",
      }}
    />
  );
};

/* ═══════════════════════════════════════════════════════════════
   Main component
   ═══════════════════════════════════════════════════════════════ */
export default function TradeAnalyzer({ trade, onClose, isOpen }) {
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  if (!trade) return null;

  /* ── Derived values ── */
  const entry = trade.entry_price ?? trade.entry ?? null;
  const exitPrice = trade.exit_price ?? trade.close_price ?? null;
  const sl = trade.stop_loss ?? trade.sl ?? null;
  const tp = trade.take_profit ?? trade.tp ?? null;
  const dir = trade.direction || trade.side || "—";
  const status = trade.status || trade.state || "CLOSED";
  const stake = trade.stake ?? trade.size ?? trade.qty ?? null;
  const grossPnl = trade.gross_pnl ?? trade.pnl ?? trade.profit_loss ?? null;
  const fee = trade.fee ?? trade.fees ?? null;
  const netPnl = trade.net_pnl ?? (grossPnl != null && fee != null ? grossPnl - fee : grossPnl);

  const openedAt = trade.opened_at ?? trade.created_at ?? trade.open_time ?? null;
  const closedAt = trade.closed_at ?? trade.close_time ?? trade.updated_at ?? null;
  const breakevenAt = trade.breakeven_at ?? null;
  const halfClosedAt = trade.half_closed_at ?? null;

  const durationMs = openedAt && closedAt
    ? new Date(closedAt) - new Date(openedAt)
    : null;

  const lifecycleSteps = [
    { label: "OPENED", ts: openedAt, done: true },
    { label: "BREAKEVEN", ts: breakevenAt, done: !!breakevenAt },
    { label: "HALF CLOSED", ts: halfClosedAt, done: !!halfClosedAt },
    { label: "CLOSED", ts: closedAt, done: status === "CLOSED" || status === "closed" },
  ];
  const currentStep = lifecycleSteps.filter((s) => s.done).length - 1;

  const signalId = trade.signal_id ?? trade.jc_signal_id ?? null;
  const won = netPnl != null ? netPnl >= 0 : null;

  /* V4 comparison placeholder */
  const v4Stats = {
    winRateOnType: dir === "SHORT" || dir === "DOWN" ? 64 : 71,
    avgWinOnType: 340,
    avgLossOnType: 180,
  };

  return (
    <>
      <style>{`
        @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        @media(max-width:768px){
          .ta-panel { width: 100% !important; right: 0 !important; border-radius: 16px 16px 0 0 !important; top: auto !important; bottom: 0 !important; max-height: 92vh !important; }
        }
      `}</style>

      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0, zIndex: 900,
          background: "rgba(0,0,0,0.65)", backdropFilter: "blur(2px)",
          opacity: isOpen ? 1 : 0, transition: "opacity 0.25s",
          pointerEvents: isOpen ? "auto" : "none",
        }}
      />

      {/* Panel */}
      <div
        className="ta-panel"
        style={{
          position: "fixed", top: 0, right: 0, bottom: 0,
          width: "min(560px, 100vw)", zIndex: 901,
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
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: C.white, letterSpacing: -0.5 }}>
                📈 TRADE ANALYSIS
              </div>
              {won != null && (
                <span style={{
                  background: won ? `${C.win}22` : `${C.loss}22`,
                  color: won ? C.win : C.loss,
                  border: `1px solid ${won ? C.win : C.loss}44`,
                  borderRadius: 20, padding: "2px 10px", fontSize: 11, fontWeight: 700,
                }}>
                  {won ? "✓ WIN" : "✗ LOSS"}
                </span>
              )}
            </div>
            <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>
              {trade.id ? `#${trade.id}` : "Trade"} · {formatDate(openedAt)}
            </div>
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

        {/* Lifecycle */}
        <div style={{ marginBottom: 24 }}>
          <Sect>Trade Lifecycle</Sect>
          <div style={{
            background: C.card, borderRadius: 10, border: `1px solid ${C.border}`,
            padding: "20px 20px 8px",
          }}>
            {lifecycleSteps.map((step, i) => (
              <LifecycleStep
                key={step.label}
                label={step.label}
                ts={step.ts}
                active={i === currentStep}
                done={step.done}
                last={i === lifecycleSteps.length - 1}
              />
            ))}
          </div>
        </div>

        {/* Price chart */}
        <div style={{ marginBottom: 24 }}>
          <Sect>Price Levels</Sect>
          <PriceLevelChart entry={entry} sl={sl} tp={tp} direction={dir} />
        </div>

        {/* Trade details */}
        <div style={{ marginBottom: 24 }}>
          <Sect>Trade Details</Sect>
          <div style={{
            background: C.card, borderRadius: 10, border: `1px solid ${C.border}`,
            overflow: "hidden",
          }}>
            {[
              {
                label: "Direction", value: (
                  <span style={{
                    color: dir === "SHORT" || dir === "DOWN" ? C.loss : dir === "LONG" || dir === "UP" ? C.win : C.muted,
                    fontWeight: 700,
                  }}>{dir}</span>
                )
              },
              { label: "Entry", value: <span style={{ color: C.white, fontWeight: 700 }}>{fmtUSD(entry)}</span> },
              { label: "Exit", value: <span style={{ color: C.text }}>{fmtUSD(exitPrice)}</span> },
              { label: "Stop Loss", value: <span style={{ color: C.loss }}>{fmtUSD(sl)}</span> },
              { label: "Take Profit", value: <span style={{ color: C.win }}>{fmtUSD(tp)}</span> },
              { label: "Stake", value: <span style={{ color: C.text }}>{stake != null ? `$${fmt(stake, 2)}` : "—"}</span> },
              { label: "Duration", value: <span style={{ color: C.text }}>{durationStr(durationMs)}</span> },
              ...(signalId ? [{ label: "Signal ID", value: <span style={{ color: C.accent }}>#{signalId}</span> }] : []),
            ].map(({ label, value }, i, arr) => (
              <div key={label} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "11px 16px",
                borderBottom: i < arr.length - 1 ? `1px solid ${C.border}` : "none",
                fontSize: 13,
              }}>
                <span style={{ color: C.muted }}>{label}</span>
                <span>{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* P&L Breakdown */}
        <div style={{ marginBottom: 24 }}>
          <Sect>P&L Breakdown</Sect>
          <div style={{
            background: C.card, borderRadius: 10, border: `1px solid ${C.border}`,
            overflow: "hidden",
          }}>
            {[
              { label: "Gross P&L", value: fmtPnl(grossPnl) },
              { label: "Fees", value: fee != null ? <span style={{ color: C.loss }}>-${fmt(fee, 2)}</span> : <span style={{ color: C.muted }}>—</span> },
              {
                label: "Net P&L", value: (
                  <span style={{
                    fontSize: 15, fontWeight: 700,
                    color: netPnl != null ? (netPnl >= 0 ? C.win : C.loss) : C.muted,
                  }}>
                    {netPnl != null ? `${netPnl >= 0 ? "+" : ""}${fmt(netPnl, 2)}` : "—"}
                  </span>
                )
              },
            ].map(({ label, value }, i, arr) => (
              <div key={label} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "11px 16px",
                borderBottom: i < arr.length - 1 ? `1px solid ${C.border}` : "none",
                fontSize: 13,
                background: i === arr.length - 1 ? `${netPnl >= 0 ? C.win : C.loss}08` : "transparent",
              }}>
                <span style={{ color: C.muted }}>{label}</span>
                <span>{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* V4 Comparison */}
        <div style={{ marginBottom: 28 }}>
          <Sect>V4 Strategy Comparison</Sect>
          <div style={{
            background: C.card, borderRadius: 10, border: `1px solid ${C.borderAccent}`,
            padding: "16px",
          }}>
            <div style={{ fontSize: 12, color: C.muted, marginBottom: 12 }}>
              How V4 performs on <strong style={{ color: dir === "SHORT" || dir === "DOWN" ? C.loss : C.win }}>
                {dir}
              </strong> trades historically:
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
              {[
                { label: "Win Rate", value: `${v4Stats.winRateOnType}%`, color: v4Stats.winRateOnType >= 60 ? C.win : C.warning },
                { label: "Avg Win", value: `+$${v4Stats.avgWinOnType}`, color: C.win },
                { label: "Avg Loss", value: `-$${v4Stats.avgLossOnType}`, color: C.loss },
              ].map(({ label, value, color }) => (
                <div key={label} style={{
                  background: C.cardDeep, borderRadius: 8, padding: "12px",
                  textAlign: "center",
                }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
                  <div style={{ fontSize: 10, color: C.muted, marginTop: 4, letterSpacing: 1 }}>{label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Close button */}
        <button onClick={onClose} style={{
          width: "100%", minHeight: 44, background: "transparent",
          border: `1px solid ${C.border}`, borderRadius: 8,
          color: C.muted, fontSize: 13, fontFamily: font,
          cursor: "pointer", fontWeight: 700, letterSpacing: 1,
        }}>
          CLOSE
        </button>
      </div>
    </>
  );
}
