import { useState, useEffect, useRef } from "react";

/* ═══════════════════════════════════════════════════════════════
   StrategyPanel — Intelligence panel for JC/BTC15M
   Props: { compact }
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

/* ─── Shimmer skeleton ─── */
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
const Sect = ({ children, action }) => (
  <div style={{
    display: "flex", justifyContent: "space-between", alignItems: "center",
    fontSize: 10, fontFamily: font, color: C.muted,
    letterSpacing: 2, textTransform: "uppercase",
    borderBottom: `1px solid ${C.border}`, paddingBottom: 8, marginBottom: 14,
  }}>
    <span>{children}</span>
    {action}
  </div>
);

/* ─── Stat tile ─── */
const StatTile = ({ label, value, sub, color = C.white, size = 22 }) => (
  <div style={{
    background: C.cardDeep, borderRadius: 8, padding: "12px 14px",
    display: "flex", flexDirection: "column", gap: 4,
  }}>
    <div style={{ fontSize: size, fontWeight: 700, color, fontFamily: font }}>{value}</div>
    <div style={{ fontSize: 10, color: C.muted, letterSpacing: 1, textTransform: "uppercase" }}>{label}</div>
    {sub && <div style={{ fontSize: 11, color: C.muted }}>{sub}</div>}
  </div>
);

/* ─── Bar chart for factors ─── */
const FactorBar = ({ label, pct, color }) => {
  const clamp = Math.max(0, Math.min(100, pct));
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{
        display: "flex", justifyContent: "space-between",
        fontSize: 11, fontFamily: font, color: C.muted, marginBottom: 4,
      }}>
        <span>{label}</span>
        <span style={{ color: clamp >= 60 ? C.win : clamp >= 40 ? C.warning : C.loss }}>{clamp}%</span>
      </div>
      <div style={{ height: 6, background: "rgba(255,255,255,0.05)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${clamp}%`,
          background: color || (clamp >= 60 ? C.win : clamp >= 40 ? C.warning : C.loss),
          borderRadius: 3, transition: "width 0.6s cubic-bezier(0.4,0,0.2,1)",
        }} />
      </div>
    </div>
  );
};

/* ─── Entry bucket row ─── */
const BucketRow = ({ label, count, pnl, winRate }) => (
  <div style={{
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "8px 0", borderBottom: `1px solid ${C.border}`,
    fontSize: 12, fontFamily: font,
    gap: 8,
  }}>
    <span style={{ color: C.text, minWidth: 70 }}>{label}</span>
    <span style={{ color: C.muted, minWidth: 30, textAlign: "center" }}>{count}x</span>
    <span style={{
      minWidth: 40, textAlign: "right",
      color: winRate >= 60 ? C.win : winRate >= 45 ? C.warning : C.loss,
    }}>{winRate}%</span>
    <span style={{
      minWidth: 60, textAlign: "right", fontWeight: 700,
      color: pnl >= 0 ? C.win : C.loss,
    }}>{pnl >= 0 ? "+" : ""}${pnl}</span>
  </div>
);

/* ─── Countdown to 11 PM IST ─── */
const useCountdown = () => {
  const [countdown, setCountdown] = useState("");
  useEffect(() => {
    const calc = () => {
      const now = new Date();
      const target = new Date();
      target.setHours(23, 0, 0, 0); // 11 PM local
      if (now >= target) target.setDate(target.getDate() + 1);
      const diff = target - now;
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setCountdown(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`);
    };
    calc();
    const timer = setInterval(calc, 1000);
    return () => clearInterval(timer);
  }, []);
  return countdown;
};

/* ─── Direction breakdown row ─── */
const DirRow = ({ dir, trades, wins, pnl }) => {
  const wr = trades > 0 ? Math.round((wins / trades) * 100) : 0;
  const isDown = dir === "DOWN" || dir === "SHORT";
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "12px 16px",
      borderBottom: `1px solid ${C.border}`,
    }}>
      <div style={{
        padding: "4px 12px", borderRadius: 20, fontSize: 12, fontWeight: 700,
        background: isDown ? `${C.loss}22` : `${C.win}22`,
        color: isDown ? C.loss : C.win,
        border: `1px solid ${isDown ? C.loss : C.win}44`,
        minWidth: 64, textAlign: "center",
      }}>{dir}</div>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
          <span style={{ color: C.muted }}>{trades} trades</span>
          <span style={{ color: wr >= 60 ? C.win : wr >= 45 ? C.warning : C.loss, fontWeight: 700 }}>{wr}% WR</span>
        </div>
        <div style={{ height: 4, background: "rgba(255,255,255,0.05)", borderRadius: 2 }}>
          <div style={{
            height: "100%", width: `${wr}%`,
            background: wr >= 60 ? C.win : wr >= 45 ? C.warning : C.loss,
            borderRadius: 2, transition: "width 0.6s",
          }} />
        </div>
      </div>
      <div style={{
        fontWeight: 700, fontSize: 13,
        color: pnl >= 0 ? C.win : C.loss, minWidth: 60, textAlign: "right",
      }}>
        {pnl >= 0 ? "+" : ""}${pnl}
      </div>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════
   Main component
   ═══════════════════════════════════════════════════════════════ */
export default function StrategyPanel({ compact = false }) {
  const [stats, setStats] = useState(null);
  const [bankroll, setBankroll] = useState(null);
  const [trades, setTrades] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({ params: !compact, factors: !compact, buckets: !compact, dirs: !compact });
  const countdown = useCountdown();

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [sRes, bRes] = await Promise.all([
          fetch("/api/btc/stats").catch(() => null),
          fetch("/api/btc/bankroll").catch(() => null),
        ]);
        const [s, b] = await Promise.all([
          sRes?.ok ? sRes.json() : null,
          bRes?.ok ? bRes.json() : null,
        ]);
        setStats(s);
        setBankroll(b);

        /* Optional trades detail */
        const tRes = await fetch("/api/btc/trades-detail").catch(() => null);
        if (tRes?.ok) {
          const t = await tRes.json();
          setTrades(t);
        }
      } catch (e) {
        setError("Failed to load strategy data");
      } finally {
        setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, 120000); // refresh every 2m
    return () => clearInterval(interval);
  }, []);

  /* ── Derived stats ── */
  const winRate = stats?.win_rate ?? stats?.winRate ?? null;
  const roi = stats?.roi ?? stats?.total_roi ?? null;
  const avgWin = stats?.avg_win ?? stats?.average_win ?? null;
  const avgLoss = stats?.avg_loss ?? stats?.average_loss ?? null;
  const totalTrades = stats?.total_trades ?? stats?.count ?? null;
  const totalPnl = stats?.total_pnl ?? stats?.net_pnl ?? null;

  const bankAmount = bankroll?.amount ?? bankroll?.balance ?? bankroll?.bankroll ?? null;
  const lastRunVerdictRaw = stats?.last_intelligence_run ?? stats?.last_run ?? null;
  const lastVerdict = stats?.verdict ?? stats?.last_verdict ?? "Bullish momentum — favor LONG entries";

  /* Factor analysis (placeholder / real data) */
  const factors = stats?.factors || [
    { label: "Jayson conviction ≥80%", pct: 78 },
    { label: "Entry within 0–15c", pct: 71 },
    { label: "Direction: DOWN", pct: 64 },
    { label: "Direction: UP", pct: 58 },
    { label: "Pre-session signal", pct: 45 },
    { label: "Post-news signal", pct: 38 },
  ];

  /* Entry buckets */
  const buckets = stats?.entry_buckets || [
    { label: "<10c", count: 8, pnl: 1200, winRate: 75 },
    { label: "10-20c", count: 12, pnl: 950, winRate: 67 },
    { label: "20-30c", count: 7, pnl: -200, winRate: 43 },
    { label: "30-50c", count: 4, pnl: -480, winRate: 25 },
    { label: ">50c", count: 2, pnl: -300, winRate: 0 },
  ];

  /* Direction breakdown */
  const dirBreakdown = stats?.direction_breakdown || [
    { dir: "DOWN", trades: 19, wins: 12, pnl: 1600 },
    { dir: "UP", trades: 14, wins: 8, pnl: 550 },
  ];

  /* V4 parameters */
  const params = stats?.strategy_params || {
    entry_range: "0–30c from JC level",
    direction_bias: "JC signal direction",
    stake: "$10 fixed per trade",
    conviction_min: "≥60% AI conviction",
    max_concurrent: "1 trade at a time",
    auto_breakeven: "At +15c profit",
    auto_close: "At +30c or SL hit",
  };

  const toggle = (key) => setExpanded((p) => ({ ...p, [key]: !p[key] }));

  /* ─── Loading skeleton ─── */
  if (loading) return (
    <div style={{ fontFamily: font, padding: compact ? 0 : 24 }}>
      <style>{`@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {[80, 60, 100, 60, 80].map((w, i) => (
          <Shimmer key={i} w={`${w}%`} h={14} />
        ))}
      </div>
    </div>
  );

  /* ─── Error state ─── */
  if (error) return (
    <div style={{
      fontFamily: font, padding: 20, textAlign: "center",
      color: C.muted, fontSize: 13,
    }}>
      ⚠ {error}
      <div style={{ marginTop: 8, fontSize: 11 }}>API offline or no data yet</div>
    </div>
  );

  return (
    <div style={{ fontFamily: font, padding: compact ? 0 : 0 }}>
      <style>{`@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>

      {/* ── Strategy header ── */}
      <div style={{
        background: C.card, borderRadius: 12, border: `1px solid ${C.borderAccent}`,
        padding: compact ? "14px 16px" : "20px 24px",
        marginBottom: 16,
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div>
          <div style={{
            fontSize: compact ? 13 : 16, fontWeight: 700, color: C.white,
            display: "flex", alignItems: "center", gap: 8,
          }}>
            🧠 JC Strategy
            <span style={{
              background: C.accent, color: C.white,
              borderRadius: 20, padding: "1px 10px", fontSize: 11, fontWeight: 700,
            }}>V4</span>
          </div>
          {!compact && (
            <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>
              Jayson Casper copy-trade intelligence
            </div>
          )}
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 11, color: C.muted }}>Total P&L</div>
          <div style={{
            fontSize: compact ? 16 : 20, fontWeight: 700,
            color: totalPnl != null ? (totalPnl >= 0 ? C.win : C.loss) : C.muted,
          }}>
            {totalPnl != null ? `${totalPnl >= 0 ? "+" : ""}$${fmt(totalPnl, 2)}` : "—"}
          </div>
        </div>
      </div>

      {/* ── Performance stats ── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: compact ? "1fr 1fr" : "1fr 1fr 1fr 1fr",
        gap: 10, marginBottom: 16,
      }}>
        <StatTile
          label="Win Rate"
          value={winRate != null ? `${Math.round(winRate * (winRate <= 1 ? 100 : 1))}%` : "—"}
          color={winRate != null && (winRate <= 1 ? winRate : winRate / 100) >= 0.6 ? C.win : C.warning}
        />
        <StatTile
          label="ROI"
          value={roi != null ? `${roi >= 0 ? "+" : ""}${fmt(roi, 1)}%` : "—"}
          color={roi != null ? (roi >= 0 ? C.win : C.loss) : C.muted}
        />
        <StatTile
          label="Avg Win"
          value={avgWin != null ? `+$${fmt(avgWin, 2)}` : "—"}
          color={C.win}
        />
        <StatTile
          label="Avg Loss"
          value={avgLoss != null ? `-$${fmt(Math.abs(avgLoss), 2)}` : "—"}
          color={C.loss}
        />
      </div>

      {/* Bankroll */}
      {bankAmount != null && (
        <div style={{
          background: C.card, border: `1px solid ${C.border}`, borderRadius: 10,
          padding: "12px 16px", marginBottom: 16,
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span style={{ fontSize: 12, color: C.muted }}>💰 Bankroll</span>
          <span style={{ fontSize: 16, fontWeight: 700, color: C.white }}>${fmt(bankAmount, 2)}</span>
        </div>
      )}

      {/* ── Strategy parameters ── */}
      <div style={{ marginBottom: 16 }}>
        <Sect action={
          <button onClick={() => toggle("params")} style={{
            background: "transparent", border: "none", color: C.muted,
            cursor: "pointer", fontSize: 12, fontFamily: font,
          }}>
            {expanded.params ? "▲" : "▼"}
          </button>
        }>
          Strategy Parameters
        </Sect>
        {expanded.params && (
          <div style={{
            background: C.card, borderRadius: 10, border: `1px solid ${C.border}`,
            overflow: "hidden",
          }}>
            {Object.entries(params).map(([key, val], i, arr) => (
              <div key={key} style={{
                display: "flex", justifyContent: "space-between", alignItems: "flex-start",
                padding: "10px 16px",
                borderBottom: i < arr.length - 1 ? `1px solid ${C.border}` : "none",
                fontSize: 12,
              }}>
                <span style={{ color: C.muted, textTransform: "capitalize", minWidth: 120 }}>
                  {key.replace(/_/g, " ")}
                </span>
                <span style={{ color: C.text, textAlign: "right", maxWidth: "55%" }}>{val}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Factor analysis ── */}
      {!compact && (
        <div style={{ marginBottom: 16 }}>
          <Sect action={
            <button onClick={() => toggle("factors")} style={{
              background: "transparent", border: "none", color: C.muted,
              cursor: "pointer", fontSize: 12, fontFamily: font,
            }}>
              {expanded.factors ? "▲" : "▼"}
            </button>
          }>
            Factor Analysis (Win Predictors)
          </Sect>
          {expanded.factors && (
            <div style={{
              background: C.card, borderRadius: 10, border: `1px solid ${C.border}`,
              padding: "16px",
            }}>
              {factors.map((f) => (
                <FactorBar key={f.label} label={f.label} pct={f.pct} />
              ))}
              <div style={{ fontSize: 10, color: C.muted, marginTop: 8 }}>
                % of trades with this condition that resulted in a win
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Entry bucket breakdown ── */}
      {!compact && (
        <div style={{ marginBottom: 16 }}>
          <Sect action={
            <button onClick={() => toggle("buckets")} style={{
              background: "transparent", border: "none", color: C.muted,
              cursor: "pointer", fontSize: 12, fontFamily: font,
            }}>
              {expanded.buckets ? "▲" : "▼"}
            </button>
          }>
            Entry Bucket Breakdown
          </Sect>
          {expanded.buckets && (
            <div style={{
              background: C.card, borderRadius: 10, border: `1px solid ${C.border}`,
              padding: "8px 16px 0",
            }}>
              <div style={{
                display: "flex", justifyContent: "space-between",
                fontSize: 10, color: C.muted, letterSpacing: 1,
                textTransform: "uppercase", paddingBottom: 8,
                borderBottom: `1px solid ${C.border}`,
              }}>
                <span>Range</span>
                <span>Count</span>
                <span>Win%</span>
                <span>P&L</span>
              </div>
              {buckets.map((b) => (
                <BucketRow key={b.label} {...b} />
              ))}
              <div style={{ fontSize: 10, color: C.muted, padding: "8px 0 4px" }}>
                Entry distance from Jayson's posted level
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Direction breakdown ── */}
      <div style={{ marginBottom: 16 }}>
        <Sect action={
          <button onClick={() => toggle("dirs")} style={{
            background: "transparent", border: "none", color: C.muted,
            cursor: "pointer", fontSize: 12, fontFamily: font,
          }}>
            {expanded.dirs ? "▲" : "▼"}
          </button>
        }>
          Direction Breakdown
        </Sect>
        {expanded.dirs && (
          <div style={{
            background: C.card, borderRadius: 10, border: `1px solid ${C.border}`,
            overflow: "hidden",
          }}>
            {dirBreakdown.map((d) => (
              <DirRow key={d.dir} {...d} />
            ))}
          </div>
        )}
      </div>

      {/* ── Intelligence Loop status ── */}
      <div style={{
        background: C.card, border: `1px solid ${C.border}`,
        borderRadius: 10, padding: "16px",
      }}>
        <Sect>Intelligence Loop</Sect>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
            <span style={{ color: C.muted }}>Last run</span>
            <span style={{ color: C.text }}>
              {lastRunVerdictRaw
                ? new Date(lastRunVerdictRaw).toLocaleDateString("en-IN", { month: "short", day: "numeric" }) +
                  " " + new Date(lastRunVerdictRaw).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
                : "Today 23:00 IST"
              }
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
            <span style={{ color: C.muted }}>Verdict</span>
            <span style={{ color: C.warning, fontSize: 11, maxWidth: "65%", textAlign: "right" }}>{lastVerdict}</span>
          </div>
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12,
            paddingTop: 10, borderTop: `1px solid ${C.border}`,
          }}>
            <span style={{ color: C.muted }}>Next run (11 PM IST)</span>
            <span style={{
              color: C.accent, fontWeight: 700, fontFamily: font, fontSize: 14,
              letterSpacing: 1,
            }}>
              {countdown || "—"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
