import { useState, useEffect } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

function Overview() {
  const [botStatus, setBotStatus] = useState(null)
  const [bankroll, setBankroll] = useState(null)
  const [todayPnl, setTodayPnl] = useState(0)
  const [activeTrades, setActiveTrades] = useState([])
  const [dailyPnl, setDailyPnl] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      const [statusRes, bankrollRes, tradesRes, pnlRes] = await Promise.all([
        axios.get('/api/bot/status'),
        axios.get('/api/bankroll'),
        axios.get('/api/trades/active'),
        axios.get('/api/pnl/daily?days=7')
      ])

      setBotStatus(statusRes.data)
      setBankroll(bankrollRes.data)
      setActiveTrades(tradesRes.data.data)
      
      const pnlData = pnlRes.data.data
      setDailyPnl(pnlData)
      
      // Calculate today's P&L (first item)
      if (pnlData.length > 0) {
        setTodayPnl(pnlData[0].total_pnl || 0)
      }
      
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch data:', error)
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="loading">Loading...</div>
  }

  const pnlChartData = (Array.isArray(dailyPnl) ? dailyPnl : []).map(d => ({
    date: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    pnl: d.total_pnl
  })).reverse()

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Overview</h1>
        <p className="page-subtitle">Real-time bot status and performance</p>
      </div>

      {/* Status Card */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <div className="card-title">Bot Status</div>
          <div className={`status-indicator ${botStatus?.running ? 'running' : 'paused'}`}>
            <div className={`status-dot ${botStatus?.running ? 'green' : 'red'}`}></div>
            {botStatus?.running ? 'Running' : 'Paused'}
          </div>
        </div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
          Mode: {botStatus?.mode || 'unknown'}
          {botStatus?.last_data_scan && (
            <> • Last scan: {new Date(botStatus.last_data_scan).toLocaleTimeString()}</>
          )}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="card-grid">
        <div className="card">
          <div className="card-title">Total Bankroll</div>
          <div className="card-value">
            ${bankroll?.total?.toFixed(2) || '0.00'}
          </div>
          <div className="card-label">
            Available: ${bankroll?.available?.toFixed(2) || '0.00'}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Today's P&L</div>
          <div className={`card-value ${todayPnl >= 0 ? 'positive' : 'negative'}`}>
            {todayPnl >= 0 ? '+' : ''}${todayPnl.toFixed(2)}
          </div>
          <div className="card-label">
            {todayPnl >= 0 ? '📈 Profitable' : '📉 Loss'}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Active Positions</div>
          <div className="card-value">{activeTrades.length}</div>
          <div className="card-label">
            ${activeTrades.reduce((sum, t) => sum + (t.size_usd || 0), 0).toFixed(2)} deployed
          </div>
        </div>

        <div className="card">
          <div className="card-title">7-Day P&L</div>
          <div className={`card-value ${dailyPnl.reduce((sum, d) => sum + (d.total_pnl || 0), 0) >= 0 ? 'positive' : 'negative'}`}>
            {dailyPnl.reduce((sum, d) => sum + (d.total_pnl || 0), 0) >= 0 ? '+' : ''}
            ${dailyPnl.reduce((sum, d) => sum + (d.total_pnl || 0), 0).toFixed(2)}
          </div>
          <div className="card-label">
            {dailyPnl.reduce((sum, d) => sum + (d.trades || 0), 0)} trades
          </div>
        </div>
      </div>

      {/* P&L Chart */}
      {pnlChartData.length > 0 && (
        <div className="card">
          <div className="card-title" style={{ marginBottom: '16px' }}>7-Day P&L Trend</div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={pnlChartData}>
              <XAxis 
                dataKey="date" 
                stroke="var(--text-tertiary)"
                style={{ fontSize: '12px' }}
              />
              <YAxis 
                stroke="var(--text-tertiary)"
                style={{ fontSize: '12px' }}
              />
              <Tooltip 
                contentStyle={{
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border)',
                  borderRadius: '8px',
                  color: 'var(--text-primary)'
                }}
              />
              <Line 
                type="monotone" 
                dataKey="pnl" 
                stroke="var(--accent-purple)" 
                strokeWidth={2}
                dot={{ fill: 'var(--accent-purple)', r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Active Positions */}
      {activeTrades.length > 0 && (
        <div className="table-container" style={{ marginTop: '24px' }}>
          <table>
            <thead>
              <tr>
                <th>City</th>
                <th>Side</th>
                <th>Entry</th>
                <th>Size</th>
                <th>Edge</th>
                <th>Opened</th>
              </tr>
            </thead>
            <tbody>
              {(Array.isArray(activeTrades) ? activeTrades : []).map((trade) => (
                <tr key={trade.id}>
                  <td>{trade.city}</td>
                  <td><span className="badge">{trade.side}</span></td>
                  <td>{trade.entry_price?.toFixed(1)}¢</td>
                  <td>${trade.size_usd?.toFixed(2)}</td>
                  <td>{trade.edge_pct?.toFixed(1)}%</td>
                  <td>{new Date(trade.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default Overview
