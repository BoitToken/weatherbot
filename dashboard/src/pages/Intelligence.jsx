import { useState, useEffect } from 'react'
import axios from 'axios'
import './Intelligence.css'

function Intelligence() {
  const [signals, setSignals] = useState([])
  const [summary, setSummary] = useState({ total_markets: 0, actionable: 0, arbitrage: 0 })
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [sortBy, setSortBy] = useState('edge')
  const [showSkip, setShowSkip] = useState(false)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [executing, setExecuting] = useState(null)
  const [dashData, setDashData] = useState(null)
  const [selectedStation, setSelectedStation] = useState(null)
  const [stationForecast, setStationForecast] = useState(null)
  const [stationHistory, setStationHistory] = useState(null)
  const [strategyComparison, setStrategyComparison] = useState(null)
  const [openPositions, setOpenPositions] = useState([])

  useEffect(() => {
    fetchSignals()
    const interval = setInterval(fetchSignals, 30000) // Auto-refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const fetchSignals = async () => {
    try {
      const [sigRes, dashRes, compRes, posRes] = await Promise.all([
        axios.get('/api/intelligence/live-signals'),
        axios.get('/api/intelligence/dashboard').catch(() => ({ data: null })),
        axios.get('/api/strategy/comparison').catch(() => ({ data: null })),
        axios.get('/api/positions/open').catch(() => ({ data: { data: [] } }))
      ])
      setSignals(sigRes.data.signals || [])
      setSummary({
        total_markets: sigRes.data.total_markets || 0,
        actionable: sigRes.data.actionable || 0,
        arbitrage: sigRes.data.arbitrage || 0
      })
      if (dashRes.data) setDashData(dashRes.data)
      if (compRes.data) setStrategyComparison(compRes.data.strategies)
      setOpenPositions(posRes.data.data || [])
      setLastUpdate(new Date())
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch live signals:', error)
      setLoading(false)
    }
  }

  const fetchStationDetail = async (icao) => {
    setSelectedStation(icao)
    try {
      const [fRes, hRes] = await Promise.all([
        axios.get(`/api/intelligence/forecast/${icao}`).catch(() => ({ data: null })),
        axios.get(`/api/intelligence/historical/${icao}`).catch(() => ({ data: null }))
      ])
      setStationForecast(fRes.data)
      setStationHistory(hRes.data)
    } catch (e) { console.error('Station detail fetch failed', e) }
  }

  const executeTrade = async (signal) => {
    setExecuting(signal.market_id)
    try {
      await axios.post('/api/trades/execute', {
        market_id: signal.market_id,
        side: signal.recommended_side,
        size_usd: 25
      })
      alert(`✅ Trade executed: ${signal.recommended_side} on ${signal.title}`)
      fetchSignals()
    } catch (error) {
      alert(`❌ Trade failed: ${error.response?.data?.detail || error.message}`)
    } finally {
      setExecuting(null)
    }
  }

  // Filter signals
  let filteredSignals = signals
  if (filter === 'strong-buy') {
    filteredSignals = signals.filter(s => s.signal === 'STRONG_BUY')
  } else if (filter === 'buy') {
    filteredSignals = signals.filter(s => s.signal === 'BUY')
  } else if (filter === 'watch') {
    filteredSignals = signals.filter(s => s.signal === 'WATCH')
  } else if (filter === 'arbitrage') {
    filteredSignals = signals.filter(s => s.is_arbitrage)
  }

  if (!showSkip) {
    filteredSignals = filteredSignals.filter(s => s.signal !== 'SKIP')
  }

  // Sort signals
  if (sortBy === 'edge') {
    filteredSignals = [...filteredSignals].sort((a, b) => Math.abs(b.edge) - Math.abs(a.edge))
  } else if (sortBy === 'volume') {
    filteredSignals = [...filteredSignals].sort((a, b) => b.volume - a.volume)
  } else if (sortBy === 'temperature') {
    filteredSignals = [...filteredSignals].sort((a, b) => b.current_temp - a.current_temp)
  } else if (sortBy === 'probability') {
    filteredSignals = [...filteredSignals].sort((a, b) => b.our_probability - a.our_probability)
  }

  if (loading) return <div className="loading">Loading live signals...</div>

  return (
    <div className="intelligence-page">
      <div className="page-header">
        <h1 className="page-title">🟢 Live Trading Signal Board</h1>
        <p className="page-subtitle">
          Real-time probability analysis • Auto-refreshes every 30s
          {lastUpdate && ` • Last update: ${lastUpdate.toLocaleTimeString()}`}
        </p>
      </div>

      {/* Summary Bar */}
      <div className="summary-bar">
        <div className="summary-item">
          <div className="summary-value">{summary.total_markets}</div>
          <div className="summary-label">Total Markets</div>
        </div>
        <div className="summary-item highlight">
          <div className="summary-value">{summary.actionable}</div>
          <div className="summary-label">Actionable Signals</div>
        </div>
        <div className="summary-item">
          <div className="summary-value">{summary.arbitrage}</div>
          <div className="summary-label">Arbitrage Ops</div>
        </div>
        <div className="summary-item">
          <div className="summary-value">{filteredSignals.length}</div>
          <div className="summary-label">Showing</div>
        </div>
      </div>

      {/* Filter & Sort Bar */}
      <div className="controls-bar">
        <div className="filter-chips">
          <button 
            className={`chip ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All
          </button>
          <button 
            className={`chip ${filter === 'strong-buy' ? 'active' : ''}`}
            onClick={() => setFilter('strong-buy')}
          >
            Strong Buy
          </button>
          <button 
            className={`chip ${filter === 'buy' ? 'active' : ''}`}
            onClick={() => setFilter('buy')}
          >
            Buy
          </button>
          <button 
            className={`chip ${filter === 'watch' ? 'active' : ''}`}
            onClick={() => setFilter('watch')}
          >
            Watch
          </button>
          <button 
            className={`chip ${filter === 'arbitrage' ? 'active' : ''}`}
            onClick={() => setFilter('arbitrage')}
          >
            Arbitrage
          </button>
          <label className="chip toggle">
            <input 
              type="checkbox" 
              checked={showSkip} 
              onChange={(e) => setShowSkip(e.target.checked)}
            />
            Show Skip
          </label>
        </div>
        
        <div className="sort-select">
          <label>Sort by:</label>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="edge">Edge</option>
            <option value="volume">Volume</option>
            <option value="temperature">Temperature</option>
            <option value="probability">Probability</option>
          </select>
        </div>
      </div>

      {/* Signal Cards Grid */}
      <div className="signals-grid">
        {filteredSignals.map(signal => (
          <SignalCard 
            key={signal.market_id} 
            signal={signal} 
            onExecute={executeTrade}
            executing={executing === signal.market_id}
          />
        ))}
      </div>

      {filteredSignals.length === 0 && (
        <div className="empty-state">
          <p>No signals match the current filter.</p>
        </div>
      )}

      {/* Station Intelligence Data */}
      <StationDataSection
        dashData={dashData}
        selectedStation={selectedStation}
        stationForecast={stationForecast}
        stationHistory={stationHistory}
        onSelectStation={fetchStationDetail}
        onCloseDetail={() => { setSelectedStation(null); setStationForecast(null); setStationHistory(null) }}
      />
    </div>
  )
}

function SignalCard({ signal, onExecute, executing }) {
  const getCardClass = () => {
    if (signal.is_arbitrage) return 'signal-card arbitrage'
    if (signal.signal === 'STRONG_BUY') return 'signal-card strong-buy'
    if (signal.signal === 'BUY') return 'signal-card buy'
    if (signal.signal === 'WATCH') return 'signal-card watch'
    return 'signal-card skip'
  }

  const getSignalBadge = () => {
    if (signal.is_arbitrage) return { emoji: '💰', text: 'ARBITRAGE — FREE MONEY', color: '#FFD700' }
    if (signal.signal === 'STRONG_BUY') return { emoji: '🟢', text: 'STRONG BUY', color: '#10B981' }
    if (signal.signal === 'BUY') return { emoji: '🟡', text: 'BUY', color: '#F59E0B' }
    if (signal.signal === 'WATCH') return { emoji: '⚪', text: 'WATCH', color: '#6B7280' }
    return { emoji: '⏭️', text: 'SKIP', color: '#9CA3AF' }
  }

  const badge = getSignalBadge()

  return (
    <div className={getCardClass()}>
      <div className="signal-header">
        <div className="signal-badge" style={{ color: badge.color }}>
          <span className="signal-emoji">{badge.emoji}</span>
          <span className="signal-text">{badge.text}</span>
        </div>
        {signal.auto_trade && (
          <div className="auto-trade-badge">Auto-Trade: ON</div>
        )}
      </div>

      <div className="signal-title">{signal.title}</div>
      <div className="signal-station">{signal.station_icao} • {signal.city}</div>

      {signal.is_arbitrage ? (
        <div className="arbitrage-content">
          <div className="arb-equation">
            YES: {(signal.yes_price * 100).toFixed(0)}¢ + NO: {(signal.no_price * 100).toFixed(0)}¢ = {(signal.arb_total * 100).toFixed(0)}¢
          </div>
          <div className="arb-profit">
            Profit: {((1 - signal.arb_total) * 100).toFixed(1)}¢ per $1
          </div>
        </div>
      ) : (
        <>
          <div className="signal-data">
            <div className="data-row">
              <span>METAR:</span>
              <strong>{signal.current_temp.toFixed(1)}°C</strong>
            </div>
            <div className="data-row">
              <span>Trend:</span>
              <strong>{signal.trend_per_hour > 0 ? '+' : ''}{signal.trend_per_hour.toFixed(1)}°C/hr</strong>
            </div>
            {signal.forecast_high && (
              <div className="data-row">
                <span>Forecast:</span>
                <strong>{signal.forecast_high.toFixed(1)}°C</strong>
              </div>
            )}
            {signal.projected_high && (
              <div className="data-row">
                <span>Projected:</span>
                <strong>{signal.projected_high.toFixed(1)}°C</strong>
              </div>
            )}
          </div>

          <div className="signal-analysis">
            <div className="analysis-grid">
              <div className="analysis-item">
                <div className="analysis-label">Our Prob</div>
                <div className="analysis-value">{(signal.our_probability * 100).toFixed(0)}%</div>
              </div>
              <div className="analysis-item">
                <div className="analysis-label">Market</div>
                <div className="analysis-value">{(signal.yes_price * 100).toFixed(0)}¢</div>
              </div>
              <div className="analysis-item">
                <div className="analysis-label">Edge</div>
                <div className="analysis-value edge-positive">{signal.edge > 0 ? '+' : ''}{(signal.edge * 100).toFixed(0)}%</div>
              </div>
              <div className="analysis-item">
                <div className="analysis-label">Expected</div>
                <div className="analysis-value">+{signal.expected_return_pct.toFixed(0)}%</div>
              </div>
              <div className="analysis-item">
                <div className="analysis-label">Side</div>
                <div className="analysis-value">{signal.recommended_side}</div>
              </div>
              <div className="analysis-item">
                <div className="analysis-label">Volume</div>
                <div className="analysis-value">${(signal.volume / 1000).toFixed(1)}K</div>
              </div>
            </div>
          </div>

          <div className="signal-sources">
            <span className="sources-label">Sources:</span>
            <span className={signal.sources.metar ? 'source-active' : 'source-inactive'}>
              {signal.sources.metar ? '✅' : '⬜'}METAR
            </span>
            <span className={signal.sources.forecast ? 'source-active' : 'source-inactive'}>
              {signal.sources.forecast ? '✅' : '⬜'}Forecast
            </span>
            <span className={signal.sources.trend ? 'source-active' : 'source-inactive'}>
              {signal.sources.trend ? '✅' : '⬜'}Trend
            </span>
            <span className={signal.sources.historical ? 'source-active' : 'source-inactive'}>
              {signal.sources.historical ? '✅' : '⬜'}Historical
            </span>
          </div>
        </>
      )}

      <div className="signal-actions">
        <button 
          className="btn btn-primary"
          onClick={() => onExecute(signal)}
          disabled={executing}
        >
          {executing ? 'Executing...' : signal.is_arbitrage ? 'Buy Both Sides' : 'Execute Trade'}
        </button>
        <button className="btn btn-secondary">Details</button>
        {!signal.is_arbitrage && signal.signal !== 'SKIP' && (
          <button className="btn btn-tertiary">Skip</button>
        )}
      </div>
    </div>
  )
}

function StationDataSection({ dashData, selectedStation, stationForecast, stationHistory, onSelectStation, onCloseDetail }) {
  if (!dashData) return null

  const convergenceColor = (status) => {
    if (status === 'high') return '#10B981'
    if (status === 'medium') return '#F59E0B'
    return '#EF4444'
  }
  const trendArrow = (val) => {
    if (!val) return '—'
    if (val > 0.5) return '🔺'
    if (val < -0.5) return '🔻'
    return '➡️'
  }

  return (
    <>
      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, margin: '24px 0 16px' }}>
        <div className="card" style={{ textAlign: 'center', padding: 12 }}>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{dashData.station_count}</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>METAR Stations</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 12 }}>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{dashData.forecast_count}</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Forecasts</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 12 }}>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{dashData.trend_count}</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Trends</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 12 }}>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{dashData.signal_count}</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Signals</div>
        </div>
      </div>

      {/* Station Convergence Table */}
      <div className="card" style={{ padding: 16, marginBottom: 20 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>🌡️ Station Data Convergence</h3>
        <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 12 }}>Click any station for detailed forecast + historical data</p>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-secondary)' }}>Station</th>
                <th style={{ padding: '6px 10px', textAlign: 'right' }}>METAR °C</th>
                <th style={{ padding: '6px 10px', textAlign: 'right' }}>Trend/hr</th>
                <th style={{ padding: '6px 10px', textAlign: 'right' }}>Proj High</th>
                <th style={{ padding: '6px 10px', textAlign: 'right' }}>Forecast High</th>
                <th style={{ padding: '6px 10px', textAlign: 'right' }}>Forecast Low</th>
                <th style={{ padding: '6px 10px', textAlign: 'center' }}>Conv</th>
              </tr>
            </thead>
            <tbody>
              {dashData.stations.map((s, i) => (
                <tr key={s.station_icao}
                  onClick={() => onSelectStation(s.station_icao)}
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer',
                    background: selectedStation === s.station_icao ? 'rgba(139,92,246,0.1)' : i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 600, fontFamily: 'monospace' }}>{s.station_icao}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 700,
                    color: s.metar.temperature_c > 30 ? '#EF4444' : s.metar.temperature_c < 0 ? '#3B82F6' : '#10B981' }}>
                    {s.metar.temperature_c?.toFixed(1) || '—'}°
                  </td>
                  <td style={{ padding: '8px 10px', textAlign: 'right' }}>
                    {trendArrow(s.trend.per_hour)} {s.trend.per_hour?.toFixed(2) || '—'}
                  </td>
                  <td style={{ padding: '8px 10px', textAlign: 'right' }}>{s.trend.projected_high?.toFixed(1) || '—'}°</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', color: '#8B5CF6' }}>{s.forecast.high_c?.toFixed(1) || '—'}°</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', color: '#3B82F6' }}>{s.forecast.low_c?.toFixed(1) || '—'}°</td>
                  <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                    <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600,
                      background: `${convergenceColor(s.convergence.status)}22`, color: convergenceColor(s.convergence.status) }}>
                      {s.convergence.sources_agree}/{s.convergence.total_sources}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Station Detail */}
      {selectedStation && (stationForecast || stationHistory) && (
        <div className="card" style={{ padding: 16, marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600 }}>📍 {selectedStation} — Detail</h3>
            <button onClick={onCloseDetail}
              style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '3px 10px', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 12 }}>✕</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {stationForecast && (
              <div style={{ background: 'var(--bg-tertiary)', borderRadius: 10, padding: 14 }}>
                <h4 style={{ fontSize: 13, color: '#8B5CF6', marginBottom: 10 }}>🔮 Open-Meteo Forecast</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
                  <div><div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>High</div><div style={{ fontSize: 20, fontWeight: 700, color: '#EF4444' }}>{stationForecast.forecast_high_c?.toFixed(1)}°C</div></div>
                  <div><div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Low</div><div style={{ fontSize: 20, fontWeight: 700, color: '#3B82F6' }}>{stationForecast.forecast_low_c?.toFixed(1)}°C</div></div>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 6 }}>Hourly (next 12h)</div>
                <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                  {(stationForecast.hourly_temps || []).slice(0, 12).map((t, i) => (
                    <div key={i} style={{ width: 32, textAlign: 'center', padding: '3px 0', borderRadius: 5, fontSize: 10, fontWeight: 600,
                      background: t > 25 ? 'rgba(239,68,68,0.12)' : t < 5 ? 'rgba(59,130,246,0.12)' : 'rgba(16,185,129,0.12)',
                      color: t > 25 ? '#EF4444' : t < 5 ? '#3B82F6' : '#10B981' }}>
                      {t?.toFixed(0)}°
                    </div>
                  ))}
                </div>
              </div>
            )}
            {stationHistory && (
              <div style={{ background: 'var(--bg-tertiary)', borderRadius: 10, padding: 14 }}>
                <h4 style={{ fontSize: 13, color: '#F59E0B', marginBottom: 10 }}>📜 Historical (5yr)</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
                  <div><div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Avg High</div><div style={{ fontSize: 20, fontWeight: 700, color: '#F59E0B' }}>{stationHistory.avg_high_c?.toFixed(1)}°C</div></div>
                  <div><div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Record</div><div style={{ fontSize: 20, fontWeight: 700 }}>{stationHistory.max_high_c?.toFixed(1)}°C</div></div>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 6 }}>Year-by-Year</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {stationHistory.yearly_highs && Object.entries(stationHistory.yearly_highs).sort().map(([y, t]) => (
                    <div key={y} style={{ padding: '4px 8px', borderRadius: 6, fontSize: 11, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.06)' }}>
                      <span style={{ color: 'var(--text-tertiary)' }}>{y}: </span><span style={{ fontWeight: 600 }}>{t?.toFixed(1)}°</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 8-Gate System */}
      <div className="card" style={{ padding: 16 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>🔒 8-Gate Intelligence System</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 10 }}>
          {[
            { n: 1, name: 'Data Convergence', desc: 'METAR + Forecast + Historical (2/3 agree)', icon: '📊' },
            { n: 2, name: 'Multi-Station', desc: 'Multiple airports validate (±1°C)', icon: '✈️' },
            { n: 3, name: 'Bucket Coherence', desc: 'Temp ranges sum to ~100%', icon: '🪣' },
            { n: 4, name: 'Binary Arbitrage', desc: 'YES+NO < $0.98 = free money', icon: '💰' },
            { n: 5, name: 'Liquidity Check', desc: 'Spread < 8¢, enough depth', icon: '💧' },
            { n: 6, name: 'Time Window', desc: 'Optimal trading hours', icon: '⏰' },
            { n: 7, name: 'Risk Manager', desc: 'Kelly sizing, circuit breakers', icon: '🛡️' },
            { n: 8, name: 'Claude AI', desc: 'Final AI confirmation', icon: '🤖' },
          ].map(g => (
            <div key={g.n} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 10, background: 'var(--bg-tertiary)', borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)' }}>
              <div style={{ fontSize: 20, width: 32, textAlign: 'center' }}>{g.icon}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, fontWeight: 600 }}>Gate {g.n}: {g.name}</div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 1 }}>{g.desc}</div>
              </div>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981', boxShadow: '0 0 4px rgba(16,185,129,0.5)' }} />
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

export default Intelligence
