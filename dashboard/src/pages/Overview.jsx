import { useState, useEffect } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

function getSportInfo(trade) {
  const title = (trade.market_title || trade.match_name || '').toLowerCase()
  const strategy = (trade.strategy || '').toLowerCase()
  if (title.includes('ipl') || strategy.includes('ipl')) return { emoji: '🏏', name: 'IPL', color: '#FF6B00' }
  if (title.includes('nba') || strategy.includes('nba')) return { emoji: '🏀', name: 'NBA', color: '#1D428A' }
  if (title.includes('nhl') || strategy.includes('nhl')) return { emoji: '🏒', name: 'NHL', color: '#A2AAAD' }
  if (title.includes('premier league') || title.includes('epl') || title.includes('soccer')) return { emoji: '⚽', name: 'Soccer', color: '#00B140' }
  if (title.includes('mlb') || strategy.includes('mlb')) return { emoji: '⚾', name: 'MLB', color: '#002D72' }
  return { emoji: '📊', name: 'Other', color: '#7c3aed' }
}

function Overview() {
  const [botStatus, setBotStatus] = useState(null)
  const [bankroll, setBankroll] = useState(null)
  const [todayPnl, setTodayPnl] = useState(0)
  const [activeTrades, setActiveTrades] = useState([])
  const [allTrades, setAllTrades] = useState([])
  const [paperTrades, setPaperTrades] = useState([])
  const [sportsBreakdown, setSportsBreakdown] = useState([])
  const [dailyPnl, setDailyPnl] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      const [statusRes, bankrollRes, activeRes, allRes, paperRes, sportsRes, pnlRes] = await Promise.all([
        axios.get('/api/bot/status'),
        axios.get('/api/bankroll'),
        axios.get('/api/trades/active'),
        axios.get('/api/trades'),
        axios.get('/api/paper-trades').catch(() => ({ data: { data: [] } })),
        axios.get('/api/performance/sports-breakdown').catch(() => ({ data: { sports: [] } })),
        axios.get('/api/pnl/daily?days=7')
      ])

      setBotStatus(statusRes.data)
      setBankroll(bankrollRes.data)
      setActiveTrades(activeRes.data.data || [])
      setAllTrades(allRes.data.data || [])
      setPaperTrades(paperRes.data.data || [])
      setSportsBreakdown(sportsRes.data.sports || [])
      
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

      {/* Active Trades */}
      {activeTrades.length > 0 && (
        <div style={{ marginTop: '24px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '16px' }}>📈 Active Trades</h2>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Market</th>
                  <th>Sport</th>
                  <th>Side</th>
                  <th>Entry</th>
                  <th>Size</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(Array.isArray(activeTrades) ? activeTrades : []).map((trade) => {
                  const sport = getSportInfo(trade)
                  const marketTitle = (trade.market_title || 'Unknown Market').length > 40 
                    ? trade.market_title.substring(0, 40) + '...' 
                    : trade.market_title || 'Unknown Market'
                  return (
                    <tr key={trade.id}>
                      <td style={{ fontWeight: 600 }}>{marketTitle}</td>
                      <td>
                        <span style={{ 
                          padding: '4px 8px', 
                          borderRadius: '6px', 
                          fontSize: '12px', 
                          fontWeight: 600,
                          background: `${sport.color}15`,
                          color: sport.color
                        }}>
                          {sport.emoji} {sport.name}
                        </span>
                      </td>
                      <td>
                        <span style={{
                          padding: '4px 10px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: 700,
                          background: trade.side === 'YES' || trade.side === 'BUY' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                          color: trade.side === 'YES' || trade.side === 'BUY' ? '#10B981' : '#EF4444'
                        }}>
                          {trade.side}
                        </span>
                      </td>
                      <td>{((trade.entry_price || 0) * 100).toFixed(0)}¢</td>
                      <td>${(trade.size_usd || 0).toFixed(2)}</td>
                      <td>
                        <span style={{
                          padding: '4px 10px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: 700,
                          background: 'rgba(245,158,11,0.15)',
                          color: '#F59E0B'
                        }}>
                          ⏳ Open
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Resolved Trades */}
      {(() => {
        const resolved = (Array.isArray(allTrades) ? allTrades : []).filter(t => t.status === 'won')
        return resolved.length > 0 && (
          <div style={{ marginTop: '32px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '16px' }}>✅ Resolved Trades</h2>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Market</th>
                    <th>Sport</th>
                    <th>Side</th>
                    <th>Entry</th>
                    <th>Size</th>
                    <th>P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {resolved.map((trade) => {
                    const sport = getSportInfo(trade)
                    const marketTitle = (trade.market_title || 'Unknown Market').length > 40 
                      ? trade.market_title.substring(0, 40) + '...' 
                      : trade.market_title || 'Unknown Market'
                    return (
                      <tr key={trade.id}>
                        <td style={{ fontWeight: 600 }}>{marketTitle}</td>
                        <td>
                          <span style={{ 
                            padding: '4px 8px', 
                            borderRadius: '6px', 
                            fontSize: '12px', 
                            fontWeight: 600,
                            background: `${sport.color}15`,
                            color: sport.color
                          }}>
                            {sport.emoji} {sport.name}
                          </span>
                        </td>
                        <td>
                          <span style={{
                            padding: '4px 10px',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 700,
                            background: trade.side === 'YES' || trade.side === 'BUY' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                            color: trade.side === 'YES' || trade.side === 'BUY' ? '#10B981' : '#EF4444'
                          }}>
                            {trade.side}
                          </span>
                        </td>
                        <td>{((trade.entry_price || 0) * 100).toFixed(0)}¢</td>
                        <td>${(trade.size_usd || 0).toFixed(2)}</td>
                        <td style={{ color: '#10B981', fontWeight: 700 }}>
                          +${(trade.pnl_usd || 0).toFixed(2)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )
      })()}

      {/* Paper Trades */}
      {paperTrades.length > 0 && (
        <div style={{ marginTop: '32px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '16px' }}>📝 Paper Trades</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
            {(Array.isArray(paperTrades) ? paperTrades : []).map((trade, idx) => {
              const sport = getSportInfo(trade)
              return (
                <div key={idx} style={{
                  background: '#1a1a2e',
                  border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: '12px',
                  padding: '16px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                    <span style={{ fontSize: '20px' }}>{sport.emoji}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '14px', fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {trade.match_name || 'Unknown Match'}
                      </div>
                      <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
                        {trade.team_backed || ''}
                      </div>
                    </div>
                  </div>
                  <div style={{ fontSize: '13px', color: '#d1d5db', marginBottom: '8px' }}>
                    Entry: <strong>{((trade.entry_price || 0) * 100).toFixed(0)}¢</strong> | 
                    Fair: <strong>{((trade.fair_value || 0) * 100).toFixed(1)}¢</strong> | 
                    Edge: <strong style={{ color: '#10B981' }}>{((trade.edge_pct || 0) * 100).toFixed(1)}%</strong>
                  </div>
                  <div style={{ fontSize: '13px', color: '#d1d5db', marginBottom: '12px' }}>
                    Size: <strong>${(trade.position_size || 0).toFixed(2)}</strong>
                  </div>
                  <div style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontWeight: 700,
                    textAlign: 'center',
                    background: trade.status === 'open' ? 'rgba(245,158,11,0.15)' : 'rgba(16,185,129,0.15)',
                    color: trade.status === 'open' ? '#F59E0B' : '#10B981'
                  }}>
                    {trade.status === 'open' ? '⏳ Open' : '✅ Closed'}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Market Overview by Sport */}
      {sportsBreakdown.length > 0 && (
        <div style={{ marginTop: '32px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '16px' }}>🌍 Market Overview</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '16px' }}>
            {(Array.isArray(sportsBreakdown) ? sportsBreakdown : []).map((sport, idx) => {
              const sportInfo = getSportInfo({ market_title: sport.sport })
              return (
                <div key={idx} style={{
                  background: '#1a1a2e',
                  border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: '12px',
                  padding: '20px'
                }}>
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>{sportInfo.emoji}</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, marginBottom: '4px', color: sportInfo.color }}>
                    {sport.sport.toUpperCase()}
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: 800, marginBottom: '4px' }}>
                    {sport.markets || 0} markets
                  </div>
                  <div style={{ fontSize: '13px', color: '#94a3b8' }}>
                    {(sport.signals || 0).toLocaleString()} signals
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default Overview
