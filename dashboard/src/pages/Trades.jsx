import { useState, useEffect } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceDot, Cell } from 'recharts'

function Trades() {
  const [performanceSummary, setPerformanceSummary] = useState({
    totalPnl: 0, roiPct: 0, winRate: 0, totalTrades: 0,
    activePositions: 0, bestTrade: 0, worstTrade: 0, wins: 0, losses: 0
  })
  const [pnlData, setPnlData] = useState([])
  const [strategyComparison, setStrategyComparison] = useState([])
  const [recentTrades, setRecentTrades] = useState([])
  const [activePositions, setActivePositions] = useState([])
  const [loading, setLoading] = useState(true)
  const [timeRange, setTimeRange] = useState('7d') // 7d | 30d | all
  const [tradeFilter, setTradeFilter] = useState('all') // all | open | won | lost | by-strategy
  const [selectedStrategy, setSelectedStrategy] = useState(null)

  useEffect(() => {
    fetchAllData()
    const interval = setInterval(fetchAllData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [timeRange])

  const fetchAllData = async () => {
    try {
      const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 365

      const [
        tradesRes,
        activeRes,
        winRateRes,
        pnlRes,
        bankrollRes,
        strategyRes
      ] = await Promise.all([
        axios.get('/api/trades?limit=100').catch(() => ({ data: { data: [] } })),
        axios.get('/api/trades/active').catch(() => ({ data: { data: [] } })),
        axios.get(`/api/analytics/win-rate?days=${days}`).catch(() => ({ data: { win_rate: 0, total_trades: 0, wins: 0, losses: 0 } })),
        axios.get(`/api/pnl/daily?days=${days}`).catch(() => ({ data: { data: [] } })),
        axios.get('/api/bankroll').catch(() => ({ data: { total: 0 } })),
        axios.get('/api/strategy/comparison').catch(() => ({ data: { strategies: [] } }))
      ])

      const trades = tradesRes.data.data || []
      const active = activeRes.data.data || []
      const winRateData = winRateRes.data
      const pnl = pnlRes.data.data || []
      const bankroll = bankrollRes.data
      // strategies can be dict or array — normalize to array
      const rawStrategies = strategyRes.data.strategies || []
      const strategies = Array.isArray(rawStrategies) 
        ? rawStrategies 
        : Object.entries(rawStrategies).map(([key, val]) => ({ id: key, ...val }))

      setRecentTrades(trades)
      setActivePositions(active)
      setStrategyComparison(strategies)

      // Calculate cumulative P&L
      const cumulativePnl = []
      let cumulative = 0
      ;(Array.isArray(pnl) ? pnl : []).reverse().forEach(day => {
        cumulative += day.total_pnl || 0
        cumulativePnl.push({
          date: new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
          pnl: cumulative,
          rawDate: day.date
        })
      })
      setPnlData(cumulativePnl)

      // Calculate summary metrics
      const totalPnl = trades.reduce((sum, t) => sum + (parseFloat(t.pnl_usd || 0)), 0)
      const closedTrades = trades.filter(t => t.status === 'closed' || t.status === 'won' || t.status === 'lost')
      const bestTrade = closedTrades.length > 0 
        ? Math.max(...closedTrades.map(t => parseFloat(t.pnl_usd || 0)))
        : 0
      const worstTrade = closedTrades.length > 0
        ? Math.min(...closedTrades.map(t => parseFloat(t.pnl_usd || 0)))
        : 0

      const roiPct = bankroll.total > 0 ? (totalPnl / bankroll.total) * 100 : 0

      setPerformanceSummary({
        totalPnl,
        roiPct,
        winRate: winRateData.win_rate_pct || winRateData.win_rate || 0,
        totalTrades: trades.length,
        activePositions: active.length,
        bestTrade,
        worstTrade,
        wins: winRateData.wins || 0,
        losses: winRateData.losses || 0
      })

      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch performance data:', error)
      setLoading(false)
    }
  }

  const toggleStrategy = async (strategyName, currentStatus) => {
    try {
      await axios.post(`/api/strategy/${strategyName}/toggle`, {
        enabled: !currentStatus
      })
      fetchAllData()
    } catch (error) {
      console.error('Failed to toggle strategy:', error)
    }
  }

  const getFilteredTrades = () => {
    let filtered = recentTrades

    if (tradeFilter === 'open') {
      filtered = activePositions
    } else if (tradeFilter === 'won') {
      filtered = recentTrades.filter(t => t.status === 'closed' && parseFloat(t.pnl_usd || 0) > 0)
    } else if (tradeFilter === 'lost') {
      filtered = recentTrades.filter(t => t.status === 'closed' && parseFloat(t.pnl_usd || 0) < 0)
    } else if (selectedStrategy) {
      filtered = recentTrades.filter(t => t.strategy === selectedStrategy)
    }

    return filtered.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  }

  if (loading) {
    return <div className="loading">Loading performance dashboard...</div>
  }

  const filteredTrades = getFilteredTrades()

  return (
    <div className="trades-page">
      <div className="page-header">
        <h1 className="page-title">💰 Performance Dashboard</h1>
        <p className="page-subtitle">Track paper trades, analyze strategy performance, and optimize settings</p>
      </div>

      {/* Section 1: Performance Summary Cards */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        <div className="card">
          <div className="card-title">Total P&L</div>
          <div className={`card-value ${performanceSummary.totalPnl >= 0 ? 'positive' : 'negative'}`}>
            {performanceSummary.totalPnl >= 0 ? '+' : ''}${performanceSummary.totalPnl.toFixed(2)}
          </div>
          <div className="card-label">
            {performanceSummary.roiPct >= 0 ? '+' : ''}{performanceSummary.roiPct.toFixed(2)}% ROI
          </div>
        </div>

        <div className="card">
          <div className="card-title">Win Rate</div>
          <div className="card-value">
            {performanceSummary.winRate.toFixed(1)}%
          </div>
          <div className="card-label">
            {performanceSummary.wins}W / {performanceSummary.losses}L
          </div>
          {/* Circular progress indicator */}
          <div style={{ marginTop: 12 }}>
            <svg width="80" height="80" style={{ transform: 'rotate(-90deg)' }}>
              <circle cx="40" cy="40" r="32" fill="none" stroke="var(--bg-tertiary)" strokeWidth="6" />
              <circle 
                cx="40" cy="40" r="32" fill="none" 
                stroke={performanceSummary.winRate >= 50 ? '#10B981' : '#F59E0B'}
                strokeWidth="6"
                strokeDasharray={`${(performanceSummary.winRate / 100) * 201} 201`}
                strokeLinecap="round"
              />
            </svg>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Active Positions</div>
          <div className="card-value">{performanceSummary.activePositions}</div>
          <div className="card-label">
            {activePositions.reduce((sum, p) => sum + parseFloat(p.unrealized_pnl_usd || 0), 0) >= 0 ? '📈' : '📉'} Open Trades
          </div>
        </div>

        <div className="card">
          <div className="card-title">Total Trades</div>
          <div className="card-value">{performanceSummary.totalTrades}</div>
          <div className="card-label">All Time</div>
        </div>

        <div className="card">
          <div className="card-title">Best Trade</div>
          <div className="card-value positive">
            +${performanceSummary.bestTrade.toFixed(2)}
          </div>
          <div className="card-label">Single Win</div>
        </div>

        <div className="card">
          <div className="card-title">Worst Trade</div>
          <div className="card-value negative">
            ${performanceSummary.worstTrade.toFixed(2)}
          </div>
          <div className="card-label">Single Loss</div>
        </div>
      </div>

      {/* Section 2: P&L Chart */}
      <div className="card" style={{ marginTop: 24, padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 18, fontWeight: 700 }}>📈 Cumulative P&L</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            {['7d', '30d', 'all'].map(range => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`btn ${timeRange === range ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '6px 12px', fontSize: 12 }}
              >
                {range.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {pnlData.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📊</div>
            <p>No P&L data yet</p>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 8 }}>
              Bot is scanning markets. Paper trades will appear here once signals trigger.
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={pnlData}>
              <XAxis 
                dataKey="date" 
                stroke="var(--text-tertiary)"
                style={{ fontSize: 12 }}
              />
              <YAxis 
                stroke="var(--text-tertiary)"
                style={{ fontSize: 12 }}
                tickFormatter={(value) => `$${value}`}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--text-primary)'
                }}
                formatter={(value) => [`$${value.toFixed(2)}`, 'P&L']}
              />
              <Line 
                type="monotone" 
                dataKey="pnl" 
                stroke="#7c3aed" 
                strokeWidth={3}
                dot={false}
              />
              {/* Trade markers - green for wins, red for losses */}
              {recentTrades
                .filter(t => t.status === 'closed')
                .map((trade, idx) => {
                  const tradeDate = new Date(trade.closed_at || trade.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                  const dataPoint = pnlData.find(d => d.date === tradeDate)
                  if (!dataPoint) return null
                  
                  return (
                    <ReferenceDot
                      key={idx}
                      x={dataPoint.date}
                      y={dataPoint.pnl}
                      r={5}
                      fill={parseFloat(trade.pnl_usd || 0) > 0 ? '#10B981' : '#EF4444'}
                      stroke="none"
                    />
                  )
                })}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Section 3: Strategy Comparison Table */}
      <div className="card" style={{ marginTop: 24, padding: 24 }}>
        <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>⚙️ Strategy Comparison</h3>
        
        {strategyComparison.length === 0 ? (
          <div className="empty-state">
            <p>No strategy data available</p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Strategy Name</th>
                  <th style={{ textAlign: 'right' }}>Trades</th>
                  <th style={{ textAlign: 'right' }}>Win Rate</th>
                  <th style={{ textAlign: 'right' }}>Avg Edge</th>
                  <th style={{ textAlign: 'right' }}>Total P&L</th>
                  <th style={{ textAlign: 'right' }}>Sharpe</th>
                  <th style={{ textAlign: 'center' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {(Array.isArray(strategyComparison) ? strategyComparison : []).map(strategy => (
                  <tr key={strategy.name}>
                    <td style={{ fontWeight: 600 }}>{strategy.name}</td>
                    <td style={{ textAlign: 'right' }}>{strategy.total_trades || 0}</td>
                    <td style={{ textAlign: 'right' }}>
                      <span style={{ 
                        color: (strategy.win_rate || 0) >= 0.5 ? '#10B981' : '#F59E0B',
                        fontWeight: 600 
                      }}>
                        {((strategy.win_rate || 0) * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {strategy.avg_edge ? `${(strategy.avg_edge * 100).toFixed(1)}%` : '—'}
                    </td>
                    <td style={{ 
                      textAlign: 'right',
                      color: (strategy.total_pnl || 0) >= 0 ? '#10B981' : '#EF4444',
                      fontWeight: 700
                    }}>
                      {(strategy.total_pnl || 0) >= 0 ? '+' : ''}${(strategy.total_pnl || 0).toFixed(2)}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {strategy.sharpe ? strategy.sharpe.toFixed(2) : '—'}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        onClick={() => toggleStrategy(strategy.name, strategy.enabled)}
                        className={`badge ${strategy.enabled ? 'high' : 'low'}`}
                        style={{ cursor: 'pointer', border: 'none' }}
                      >
                        {strategy.enabled ? '✓ Active' : '✕ Disabled'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Section 4: Recent Trades Feed */}
      <div className="card" style={{ marginTop: 24, padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
          <h3 style={{ fontSize: 18, fontWeight: 700 }}>📋 Recent Trades</h3>
          
          {/* Filter Chips */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {['all', 'open', 'won', 'lost'].map(filter => (
              <button
                key={filter}
                onClick={() => { setTradeFilter(filter); setSelectedStrategy(null) }}
                className={`btn ${tradeFilter === filter && !selectedStrategy ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '6px 12px', fontSize: 12, textTransform: 'capitalize' }}
              >
                {filter}
              </button>
            ))}
            {(Array.isArray(strategyComparison) ? strategyComparison : []).map(s => (
              <button
                key={s.name}
                onClick={() => { setTradeFilter('all'); setSelectedStrategy(s.name) }}
                className={`btn ${selectedStrategy === s.name ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '6px 12px', fontSize: 11 }}
              >
                {s.name}
              </button>
            ))}
          </div>
        </div>

        {filteredTrades.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">💤</div>
            <p>No trades yet</p>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 8 }}>
              Bot is scanning markets. Paper trades will appear here once signals trigger.
            </p>
          </div>
        ) : (
          <>
            {/* Desktop: Table */}
            <div className="table-container" style={{ display: 'none' }}>
              <table className="trades-table-desktop">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Market</th>
                    <th style={{ textAlign: 'center' }}>Direction</th>
                    <th style={{ textAlign: 'right' }}>Entry</th>
                    <th style={{ textAlign: 'right' }}>Current/Exit</th>
                    <th style={{ textAlign: 'right' }}>Edge</th>
                    <th style={{ textAlign: 'right' }}>P&L</th>
                    <th>Strategy</th>
                  </tr>
                </thead>
                <tbody>
                  {(Array.isArray(filteredTrades) ? filteredTrades : []).map(trade => {
                    const pnl = parseFloat(trade.pnl_usd || trade.unrealized_pnl_usd || 0)
                    const isWin = pnl > 0
                    const isOpen = trade.status === 'open'
                    
                    return (
                      <tr 
                        key={trade.id}
                        style={{
                          background: isOpen ? 'transparent' : isWin ? 'rgba(16,185,129,0.05)' : 'rgba(239,68,68,0.05)'
                        }}
                      >
                        <td style={{ fontSize: 12 }}>
                          {new Date(trade.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {trade.market_title || trade.market_id}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <span className={`badge ${trade.side === 'YES' ? 'high' : 'medium'}`}>
                            {trade.side}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>
                          {(parseFloat(trade.entry_price || 0) * 100).toFixed(0)}¢
                        </td>
                        <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>
                          {(parseFloat(trade.exit_price || trade.current_price || 0) * 100).toFixed(0)}¢
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          {trade.edge ? `${(trade.edge * 100).toFixed(1)}%` : '—'}
                        </td>
                        <td style={{ 
                          textAlign: 'right', 
                          fontWeight: 700,
                          color: isOpen ? 'var(--text-secondary)' : isWin ? '#10B981' : '#EF4444'
                        }}>
                          {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                        </td>
                        <td>
                          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                            {trade.strategy || 'Manual'}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile: Cards */}
            <div className="trades-cards-mobile">
              {(Array.isArray(filteredTrades) ? filteredTrades : []).map(trade => {
                const pnl = parseFloat(trade.pnl_usd || trade.unrealized_pnl_usd || 0)
                const isWin = pnl > 0
                const isOpen = trade.status === 'open'
                
                return (
                  <div
                    key={trade.id}
                    className="trade-card"
                    style={{
                      padding: 16,
                      borderRadius: 12,
                      border: '1px solid var(--border)',
                      background: isOpen ? 'var(--bg-secondary)' : isWin ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                      marginBottom: 12
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                        {new Date(trade.created_at).toLocaleString([], { 
                          month: 'short', 
                          day: 'numeric',
                          hour: '2-digit', 
                          minute: '2-digit' 
                        })}
                      </span>
                      <span className={`badge ${isOpen ? 'open' : isWin ? 'won' : 'lost'}`}>
                        {isOpen ? 'Open' : isWin ? 'Won' : 'Lost'}
                      </span>
                    </div>
                    
                    <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>
                      {trade.market_title || trade.market_id}
                    </div>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12 }}>
                      <div>
                        <span style={{ color: 'var(--text-tertiary)' }}>Direction: </span>
                        <span className={`badge ${trade.side === 'YES' ? 'high' : 'medium'}`} style={{ fontSize: 11 }}>
                          {trade.side}
                        </span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-tertiary)' }}>Entry: </span>
                        <strong>{(parseFloat(trade.entry_price || 0) * 100).toFixed(0)}¢</strong>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-tertiary)' }}>Current: </span>
                        <strong>{(parseFloat(trade.exit_price || trade.current_price || 0) * 100).toFixed(0)}¢</strong>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-tertiary)' }}>Edge: </span>
                        <strong>{trade.edge ? `${(trade.edge * 100).toFixed(1)}%` : '—'}</strong>
                      </div>
                    </div>
                    
                    <div style={{ 
                      marginTop: 12, 
                      paddingTop: 12, 
                      borderTop: '1px solid var(--border)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                        {trade.strategy || 'Manual'}
                      </span>
                      <span style={{ 
                        fontSize: 18, 
                        fontWeight: 800,
                        color: isOpen ? 'var(--text-secondary)' : isWin ? '#10B981' : '#EF4444'
                      }}>
                        {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default Trades
