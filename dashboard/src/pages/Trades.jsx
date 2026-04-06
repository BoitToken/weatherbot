import { useState, useEffect } from 'react'
import axios from 'axios'

function Trades() {
  const [trades, setTrades] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ status: 'all' })

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      const [tradesRes, analyticsRes] = await Promise.all([
        axios.get('/api/trades?limit=100'),
        axios.get('/api/analytics/win-rate?days=30')
      ])
      
      setTrades(tradesRes.data.data)
      setAnalytics(analyticsRes.data)
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch trades:', error)
      setLoading(false)
    }
  }

  const filteredTrades = trades.filter(trade => {
    if (filter.status === 'all') return true
    if (filter.status === 'open') return trade.status.includes('open')
    if (filter.status === 'won') return trade.status.includes('won')
    if (filter.status === 'lost') return trade.status.includes('lost')
    return true
  })

  if (loading) {
    return <div className="loading">Loading...</div>
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Trades</h1>
        <p className="page-subtitle">Complete trade history and performance</p>
      </div>

      {/* Summary Stats */}
      {analytics && (
        <div className="card-grid">
          <div className="card">
            <div className="card-title">Total Trades</div>
            <div className="card-value">{analytics.total_trades || 0}</div>
            <div className="card-label">All time</div>
          </div>

          <div className="card">
            <div className="card-title">Win Rate</div>
            <div className="card-value positive">
              {analytics.win_rate_pct?.toFixed(1) || '0.0'}%
            </div>
            <div className="card-label">
              {analytics.wins || 0}W / {(analytics.total_trades || 0) - (analytics.wins || 0)}L
            </div>
          </div>

          <div className="card">
            <div className="card-title">Total P&L</div>
            <div className={`card-value ${(analytics.total_pnl || 0) >= 0 ? 'positive' : 'negative'}`}>
              {(analytics.total_pnl || 0) >= 0 ? '+' : ''}${(analytics.total_pnl || 0).toFixed(2)}
            </div>
            <div className="card-label">Last 30 days</div>
          </div>

          <div className="card">
            <div className="card-title">Avg Edge</div>
            <div className="card-value" style={{ color: 'var(--accent-purple)' }}>
              {analytics.avg_edge?.toFixed(1) || '0.0'}%
            </div>
            <div className="card-label">Per trade</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card" style={{ marginTop: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <div>
            <label style={{ marginRight: '8px', color: 'var(--text-secondary)', fontSize: '14px' }}>
              Status:
            </label>
            <select 
              value={filter.status}
              onChange={(e) => setFilter({ ...filter, status: e.target.value })}
              style={{
                padding: '8px 12px',
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border)',
                borderRadius: '6px',
                color: 'var(--text-primary)',
                fontSize: '14px'
              }}
            >
              <option value="all">All</option>
              <option value="open">Open</option>
              <option value="won">Won</option>
              <option value="lost">Lost</option>
            </select>
          </div>

          <div style={{ marginLeft: 'auto', color: 'var(--text-secondary)', fontSize: '14px' }}>
            Showing {filteredTrades.length} of {trades.length} trades
          </div>
        </div>
      </div>

      {/* Trades Table */}
      {filteredTrades.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">💰</div>
          <h3>No trades yet</h3>
          <p>Trade history will appear here once the bot starts executing...</p>
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>City</th>
                <th>Side</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>Size</th>
                <th>Edge</th>
                <th>Status</th>
                <th>P&L</th>
              </tr>
            </thead>
            <tbody>
              {filteredTrades.map((trade) => (
                <tr key={trade.id}>
                  <td>{new Date(trade.created_at).toLocaleDateString()}</td>
                  <td>{trade.city}</td>
                  <td><span className="badge">{trade.side}</span></td>
                  <td>{trade.entry_price?.toFixed(1)}¢</td>
                  <td>{trade.exit_price?.toFixed(1) || '—'}¢</td>
                  <td>${trade.size_usd?.toFixed(2)}</td>
                  <td>{trade.edge_pct?.toFixed(1)}%</td>
                  <td>
                    <span className={`badge ${
                      trade.status.includes('won') ? 'won' :
                      trade.status.includes('lost') ? 'lost' : 'open'
                    }`}>
                      {trade.status}
                    </span>
                  </td>
                  <td style={{
                    color: trade.pnl > 0 ? 'var(--success)' : 
                           trade.pnl < 0 ? 'var(--error)' : 
                           'var(--text-secondary)',
                    fontWeight: 600
                  }}>
                    {trade.pnl !== null && trade.pnl !== undefined ? 
                      `${trade.pnl >= 0 ? '+' : ''}$${trade.pnl.toFixed(2)}` : 
                      '—'
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default Trades
