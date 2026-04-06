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

  useEffect(() => {
    fetchSignals()
    const interval = setInterval(fetchSignals, 30000) // Auto-refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const fetchSignals = async () => {
    try {
      const res = await axios.get('/api/intelligence/live-signals')
      setSignals(res.data.signals || [])
      setSummary({
        total_markets: res.data.total_markets || 0,
        actionable: res.data.actionable || 0,
        arbitrage: res.data.arbitrage || 0
      })
      setLastUpdate(new Date())
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch live signals:', error)
      setLoading(false)
    }
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

export default Intelligence
