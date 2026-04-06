import { useState, useEffect } from 'react'
import axios from 'axios'

function Signals() {
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ confidence: 'all', minEdge: 0 })

  useEffect(() => {
    fetchSignals()
    const interval = setInterval(fetchSignals, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchSignals = async () => {
    try {
      const res = await axios.get('/api/signals?limit=100')
      setSignals(res.data.data)
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch signals:', error)
      setLoading(false)
    }
  }

  const filteredSignals = signals.filter(signal => {
    if (filter.confidence !== 'all' && signal.confidence !== filter.confidence) {
      return false
    }
    if (signal.edge_pct < filter.minEdge) {
      return false
    }
    return true
  })

  if (loading) {
    return <div className="loading">Loading...</div>
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Signals</h1>
        <p className="page-subtitle">Weather edge opportunities detected by the bot</p>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <div>
            <label style={{ marginRight: '8px', color: 'var(--text-secondary)', fontSize: '14px' }}>
              Confidence:
            </label>
            <select 
              value={filter.confidence}
              onChange={(e) => setFilter({ ...filter, confidence: e.target.value })}
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
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>

          <div>
            <label style={{ marginRight: '8px', color: 'var(--text-secondary)', fontSize: '14px' }}>
              Min Edge:
            </label>
            <input 
              type="number"
              value={filter.minEdge}
              onChange={(e) => setFilter({ ...filter, minEdge: parseFloat(e.target.value) || 0 })}
              style={{
                padding: '8px 12px',
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border)',
                borderRadius: '6px',
                color: 'var(--text-primary)',
                fontSize: '14px',
                width: '100px'
              }}
              placeholder="0"
            />
            <span style={{ marginLeft: '4px', color: 'var(--text-secondary)' }}>%</span>
          </div>

          <div style={{ marginLeft: 'auto', color: 'var(--text-secondary)', fontSize: '14px' }}>
            Showing {filteredSignals.length} of {signals.length} signals
          </div>
        </div>
      </div>

      {/* Signals Table */}
      {filteredSignals.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📡</div>
          <h3>No signals yet</h3>
          <p>Waiting for the bot to detect weather edge opportunities...</p>
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>City</th>
                <th>Market</th>
                <th>Side</th>
                <th>Edge</th>
                <th>Confidence</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredSignals.map((signal) => (
                <tr key={signal.signal_id}>
                  <td>{new Date(signal.created_at).toLocaleString()}</td>
                  <td>{signal.city}</td>
                  <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {signal.market_title || 'N/A'}
                  </td>
                  <td><span className="badge">{signal.side}</span></td>
                  <td style={{ color: 'var(--success)', fontWeight: 600 }}>
                    {signal.edge_pct?.toFixed(1)}%
                  </td>
                  <td>
                    <span className={`badge ${signal.confidence?.toLowerCase()}`}>
                      {signal.confidence}
                    </span>
                  </td>
                  <td>{signal.status}</td>
                  <td>
                    {signal.status === 'pending' && (
                      <button className="btn btn-primary" style={{ padding: '6px 12px', fontSize: '12px' }}>
                        Approve
                      </button>
                    )}
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

export default Signals
