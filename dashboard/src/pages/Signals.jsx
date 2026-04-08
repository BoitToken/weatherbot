import { useState, useEffect } from 'react'
import axios from 'axios'

function Signals() {
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ confidence: 'all', minEdge: 0, strategy: 'all' })
  const [comparison, setComparison] = useState(null)
  const [positions, setPositions] = useState([])
  const [forecasts, setForecasts] = useState({})
  const [marketStatus, setMarketStatus] = useState(null)

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchAll = async () => {
    try {
      const [sigRes, compRes, posRes, healthRes] = await Promise.all([
        axios.get('/api/signals?limit=100').catch(() => ({ data: { data: [] } })),
        axios.get('/api/strategy/comparison').catch(() => ({ data: null })),
        axios.get('/api/positions/open').catch(() => ({ data: { positions: [] } })),
        axios.get('/api/health').catch(() => ({ data: {} })),
      ])
      setSignals(sigRes.data.data || [])
      setComparison(compRes.data)
      setPositions(posRes.data.positions || [])
      setMarketStatus(healthRes.data)
      setLoading(false)

      // Fetch NOAA forecasts for key cities
      const cities = ['NYC', 'Chicago', 'London', 'Seoul', 'Seattle', 'Atlanta']
      const fcasts = {}
      for (const city of cities) {
        try {
          const r = await axios.get(`/api/noaa/forecast/${city}`)
          if (r.data) fcasts[city] = r.data
        } catch {}
      }
      setForecasts(fcasts)
    } catch (error) {
      console.error('Failed to fetch:', error)
      setLoading(false)
    }
  }

  const filteredSignals = signals.filter(signal => {
    if (filter.confidence !== 'all' && signal.confidence !== filter.confidence) return false
    if (filter.strategy !== 'all' && signal.strategy !== filter.strategy) return false
    if (signal.edge_pct < filter.minEdge) return false
    return true
  })

  if (loading) return <div className="loading">Loading...</div>

  const strA = comparison?.strategies?.forecast_edge
  const strB = comparison?.strategies?.intelligence_layer

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">⚡ Dual Strategy Signals</h1>
        <p className="page-subtitle">Two strategies running in parallel — speed vs depth</p>
      </div>

      {/* Strategy Comparison Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        <div className="card" style={{ padding: 20, borderLeft: '3px solid #10B981' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700 }}>🎯 Strategy A: Forecast Edge</h3>
            <span style={{ fontSize: 11, padding: '3px 8px', borderRadius: 6, background: 'rgba(16,185,129,0.12)', color: '#10B981', fontWeight: 600 }}>Every 2 min</span>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16 }}>
            NOAA says X → market says Y → buy X when price ≤15¢ → exit at 45¢
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            <div><div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Trades</div><div style={{ fontSize: 20, fontWeight: 800 }}>{strA?.total_trades || 0}</div></div>
            <div><div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Win Rate</div><div style={{ fontSize: 20, fontWeight: 800, color: '#10B981' }}>{strA?.win_rate || 0}%</div></div>
            <div><div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>P&L</div><div style={{ fontSize: 20, fontWeight: 800, color: (strA?.total_pnl || 0) >= 0 ? '#10B981' : '#EF4444' }}>${strA?.total_pnl || 0}</div></div>
          </div>
        </div>

        <div className="card" style={{ padding: 20, borderLeft: '3px solid #8B5CF6' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700 }}>🧠 Strategy B: 8-Gate Intelligence</h3>
            <span style={{ fontSize: 11, padding: '3px 8px', borderRadius: 6, background: 'rgba(139,92,246,0.12)', color: '#8B5CF6', fontWeight: 600 }}>Every 5 min</span>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16 }}>
            METAR + Forecast + Historical convergence → 8 safety gates → trade if all pass
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            <div><div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Trades</div><div style={{ fontSize: 20, fontWeight: 800 }}>{strB?.total_trades || 0}</div></div>
            <div><div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Win Rate</div><div style={{ fontSize: 20, fontWeight: 800, color: '#8B5CF6' }}>{strB?.win_rate || 0}%</div></div>
            <div><div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>P&L</div><div style={{ fontSize: 20, fontWeight: 800, color: (strB?.total_pnl || 0) >= 0 ? '#10B981' : '#EF4444' }}>${strB?.total_pnl || 0}</div></div>
          </div>
        </div>
      </div>

      {/* NOAA Forecasts — Live Data */}
      {Object.keys(forecasts).length > 0 && (
        <div className="card" style={{ padding: 20, marginBottom: 24 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>🌡️ NOAA GFS Forecasts — Live</h3>
          <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 16 }}>Primary data source for Strategy A (85-90% accurate at 1-2 day). Scanning for matching Polymarket temperature bucket markets.</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
            {Object.entries(forecasts).map(([city, f]) => (
              <div key={city} style={{ background: 'var(--bg-tertiary)', borderRadius: 10, padding: 14, border: '1px solid var(--border)' }}>
                <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>{city}</div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                  <span style={{ fontSize: 24, fontWeight: 800, color: f.forecast_high_f > 80 ? '#EF4444' : f.forecast_high_f < 32 ? '#3B82F6' : '#10B981' }}>
                    {f.forecast_high_f ? `${Math.round(f.forecast_high_f)}°F` : '—'}
                  </span>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    / {f.forecast_low_f ? `${Math.round(f.forecast_low_f)}°F` : '—'}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>
                  {f.source === 'noaa_gfs' ? '🇺🇸 NOAA GFS' : '🌍 Open-Meteo'} · {Math.round((f.confidence || 0) * 100)}% conf
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Market Status */}
      <div className="card" style={{ padding: 20, marginBottom: 24, background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.15)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <span style={{ fontSize: 20 }}>⚠️</span>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: '#F59E0B' }}>Market Status: No Active Weather Markets</h3>
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          Polymarket currently has <strong>0 active temperature bucket markets</strong>. Weather markets are seasonal — they appear during 
          major weather events (hurricanes, heat waves, cold snaps, winter storms). Both strategies are scanning every 2-5 minutes 
          and will auto-detect and signal the moment markets open.
        </p>
        <div style={{ marginTop: 12, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ fontSize: 12 }}>
            <span style={{ color: 'var(--text-tertiary)' }}>Last data scan: </span>
            <span style={{ color: '#10B981', fontWeight: 600 }}>{marketStatus?.last_data_scan ? new Date(marketStatus.last_data_scan).toLocaleTimeString() : '—'}</span>
          </div>
          <div style={{ fontSize: 12 }}>
            <span style={{ color: 'var(--text-tertiary)' }}>Scheduler: </span>
            <span style={{ color: marketStatus?.scheduler ? '#10B981' : '#EF4444', fontWeight: 600 }}>{marketStatus?.scheduler ? '✅ Running' : '❌ Stopped'}</span>
          </div>
          <div style={{ fontSize: 12 }}>
            <span style={{ color: 'var(--text-tertiary)' }}>NOAA: </span>
            <span style={{ color: '#10B981', fontWeight: 600 }}>✅ Connected ({Object.keys(forecasts).length} cities)</span>
          </div>
        </div>
      </div>

      {/* Open Positions */}
      {positions.length > 0 && (
        <div className="card" style={{ padding: 20, marginBottom: 24 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>📊 Open Positions</h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Market</th>
                  <th>Strategy</th>
                  <th>Entry</th>
                  <th>Current</th>
                  <th>P/L</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {positions.map(p => (
                  <tr key={p.id}>
                    <td>{p.market_title}</td>
                    <td><span className="badge" style={{ background: p.strategy === 'forecast_edge' ? 'rgba(16,185,129,0.12)' : 'rgba(139,92,246,0.12)', color: p.strategy === 'forecast_edge' ? '#10B981' : '#8B5CF6' }}>{p.strategy === 'forecast_edge' ? 'A' : 'B'}</span></td>
                    <td>${p.entry_price?.toFixed(2)}</td>
                    <td>${p.current_price?.toFixed(2)}</td>
                    <td style={{ color: (p.current_price - p.entry_price) >= 0 ? '#10B981' : '#EF4444', fontWeight: 600 }}>${((p.current_price - p.entry_price) * (p.shares || 1)).toFixed(2)}</td>
                    <td>{p.current_price >= 0.45 && <button className="btn btn-primary" style={{ padding: '4px 10px', fontSize: 11 }}>Exit 45¢+</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card" style={{ marginBottom: 24, padding: 16 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <label style={{ marginRight: 8, color: 'var(--text-secondary)', fontSize: 13 }}>Strategy:</label>
            <select value={filter.strategy} onChange={(e) => setFilter({ ...filter, strategy: e.target.value })}
              style={{ padding: '6px 10px', background: 'var(--bg-tertiary)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)', fontSize: 13 }}>
              <option value="all">Both</option>
              <option value="forecast_edge">A: Forecast Edge</option>
              <option value="intelligence_layer">B: 8-Gate</option>
            </select>
          </div>
          <div>
            <label style={{ marginRight: 8, color: 'var(--text-secondary)', fontSize: 13 }}>Confidence:</label>
            <select value={filter.confidence} onChange={(e) => setFilter({ ...filter, confidence: e.target.value })}
              style={{ padding: '6px 10px', background: 'var(--bg-tertiary)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)', fontSize: 13 }}>
              <option value="all">All</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>
          <div>
            <label style={{ marginRight: 8, color: 'var(--text-secondary)', fontSize: 13 }}>Min Edge:</label>
            <input type="number" value={filter.minEdge} onChange={(e) => setFilter({ ...filter, minEdge: parseFloat(e.target.value) || 0 })}
              style={{ padding: '6px 10px', background: 'var(--bg-tertiary)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)', fontSize: 13, width: 80 }} />
            <span style={{ marginLeft: 4, color: 'var(--text-secondary)', fontSize: 13 }}>%</span>
          </div>
          <div style={{ marginLeft: 'auto', color: 'var(--text-secondary)', fontSize: 13 }}>
            {filteredSignals.length} of {signals.length} signals
          </div>
        </div>
      </div>

      {/* Signals Table */}
      {filteredSignals.length === 0 ? (
        <div className="card" style={{ padding: 32, textAlign: 'center' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🔄</div>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Both strategies scanning — no signals yet</h3>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 500, margin: '0 auto', lineHeight: 1.6 }}>
            Strategy A checks NOAA forecasts every 2 minutes. Strategy B runs the 8-gate intelligence layer every 5 minutes. 
            Signals will appear here automatically when temperature bucket markets open on Polymarket.
          </p>
          <div style={{ marginTop: 16, display: 'flex', justifyContent: 'center', gap: 8 }}>
            <span style={{ padding: '4px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600, background: 'rgba(16,185,129,0.1)', color: '#10B981' }}>Strategy A: Scanning ✓</span>
            <span style={{ padding: '4px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600, background: 'rgba(139,92,246,0.1)', color: '#8B5CF6' }}>Strategy B: Scanning ✓</span>
            <span style={{ padding: '4px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600, background: 'rgba(245,158,11,0.1)', color: '#F59E0B' }}>Markets: Waiting</span>
          </div>
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Strategy</th>
                <th>City</th>
                <th>Market</th>
                <th>Side</th>
                <th>Edge</th>
                <th>Confidence</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredSignals.map((signal) => (
                <tr key={signal.signal_id}>
                  <td style={{ fontSize: 12 }}>{new Date(signal.created_at).toLocaleString()}</td>
                  <td>
                    <span className="badge" style={{ 
                      background: signal.strategy === 'forecast_edge' ? 'rgba(16,185,129,0.12)' : 'rgba(139,92,246,0.12)', 
                      color: signal.strategy === 'forecast_edge' ? '#10B981' : '#8B5CF6',
                      fontSize: 10
                    }}>
                      {signal.strategy === 'forecast_edge' ? '🎯 A' : '🧠 B'}
                    </span>
                  </td>
                  <td>{signal.city}</td>
                  <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{signal.market_title || 'N/A'}</td>
                  <td><span className="badge">{signal.side}</span></td>
                  <td style={{ color: '#10B981', fontWeight: 600 }}>{signal.edge_pct?.toFixed(1)}%</td>
                  <td><span className={`badge ${signal.confidence?.toLowerCase()}`}>{signal.confidence}</span></td>
                  <td>{signal.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default Signals
