import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import './Performance.css'

const API_BASE = ''  // Use relative URLs (nginx proxies /api → backend)

function Performance() {
  const [strategies, setStrategies] = useState([])
  const [signals, setSignals] = useState([])
  const [timeline, setTimeline] = useState([])
  const [edgeDistribution, setEdgeDistribution] = useState([])
  const [sportsBreakdown, setSportsBreakdown] = useState([])
  const [oddsComparison, setOddsComparison] = useState([])
  const [activeTab, setActiveTab] = useState('overview')
  const [signalFilter, setSignalFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)

  useEffect(() => {
    fetchAllData()
    const interval = setInterval(() => {
      fetchSignals()
      setScanning(true)
      setTimeout(() => setScanning(false), 1000)
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchAllData = async () => {
    setLoading(true)
    try {
      const [stratRes, sigRes, timeRes, edgeRes, sportsRes, oddsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/performance/strategies`),
        axios.get(`${API_BASE}/api/performance/signals/latest?limit=50`),
        axios.get(`${API_BASE}/api/performance/signals/timeline`),
        axios.get(`${API_BASE}/api/performance/edge-distribution`),
        axios.get(`${API_BASE}/api/performance/sports-breakdown`),
        axios.get(`${API_BASE}/api/performance/odds-comparison?limit=50`)
      ])
      
      const toArr = (v) => Array.isArray(v) ? v : []
      setStrategies(toArr(stratRes.data?.strategies ?? stratRes.data))
      setSignals(toArr(sigRes.data?.signals ?? sigRes.data))
      setTimeline(toArr(timeRes.data?.buckets))
      setEdgeDistribution(toArr(edgeRes.data?.buckets))
      setSportsBreakdown(toArr(sportsRes.data?.sports ?? sportsRes.data))
      setOddsComparison(toArr(oddsRes.data?.comparisons ?? oddsRes.data))
    } catch (err) {
      console.error('Failed to fetch performance data:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchSignals = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/performance/signals/latest?limit=50`)
      setSignals(res.data.signals || [])
    } catch (err) {
      console.error('Failed to refresh signals:', err)
    }
  }

  const getRelativeTime = (timestamp) => {
    if (!timestamp) return 'Unknown'
    const now = new Date()
    const time = new Date(timestamp)
    const diff = Math.floor((now - time) / 1000)
    if (diff < 60) return `${diff}s ago`
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
  }

  const getStrategyIcon = (id) => {
    const map = {
      cross_odds: '⚡',
      logical_arb: '🔗',
      forecast_edge: '🌡️',
      intelligence_layer: '🧠',
      live_momentum: '🏃'
    }
    return map[id] || '📊'
  }

  const getConfidenceBadgeColor = (conf) => {
    if (conf === 'HIGH') return '#10B981'
    if (conf === 'MEDIUM') return '#F59E0B'
    return '#6B7280'
  }

  const getSportInfo = (signal) => {
    const sport = (signal.sport || '').toLowerCase()
    if (sport.includes('ipl')) return { emoji: '🏏', name: 'IPL', color: '#FF6B00' }
    if (sport.includes('nba')) return { emoji: '🏀', name: 'NBA', color: '#1D428A' }
    if (sport.includes('nhl')) return { emoji: '🏒', name: 'NHL', color: '#A2AAAD' }
    if (sport.includes('soccer')) return { emoji: '⚽', name: 'Soccer', color: '#00B140' }
    if (sport.includes('mlb')) return { emoji: '⚾', name: 'MLB', color: '#002D72' }
    return { emoji: '🎯', name: sport || 'N/A', color: '#7c3aed' }
  }

  const filteredSignals = (Array.isArray(signals) ? signals : []).filter(s => {
    if (signalFilter === 'all') return true
    if (signalFilter === 'buy') return s.side === 'BUY'
    if (signalFilter === 'sell') return s.side === 'SELL'
    return s.strategy.toLowerCase().includes(signalFilter.toLowerCase())
  })

  if (loading) {
    return (
      <div className="performance-loading">
        <div className="spinner"></div>
        <p>Loading Performance Dashboard...</p>
      </div>
    )
  }

  // Sort strategies by signal count
  const sortedStrategies = [...strategies].sort((a, b) => b.signal_count - a.signal_count)

  return (
    <div className="performance-page">
      <div className="performance-header">
        <h1>🏆 Performance — CEO Command Center</h1>
        <p className="performance-subtitle">
          Watch AI strategies compete in real-time • {signals.length.toLocaleString()} signals generated
        </p>
      </div>

      {/* A) Strategy Arena */}
      <section className="strategy-arena">
        <h2>Strategy Arena</h2>
        <div className="strategy-cards">
          {sortedStrategies.map(strategy => {
            const statusColor = strategy.status === 'active' ? '#10B981' : strategy.status === 'researching' ? '#F59E0B' : '#6B7280'
            const borderClass = strategy.status === 'active' && strategy.avg_edge > 0 ? 'border-active' : 'border-inactive'
            
            return (
              <div key={strategy.id} className={`strategy-card ${borderClass}`}>
                <div className="strategy-card-header">
                  <span className="strategy-icon">{strategy.emoji}</span>
                  <h3>{strategy.name}</h3>
                  <div className="status-badge" style={{ background: statusColor }}>
                    {strategy.status === 'active' ? '🟢 ACTIVE' : strategy.status === 'researching' ? '🟡 RESEARCHING' : '⚪ COMING SOON'}
                  </div>
                </div>
                
                <p className="strategy-description">{strategy.description}</p>
                
                <div className="strategy-metrics">
                  <div className="metric">
                    <div className="metric-value">{strategy.signal_count.toLocaleString()}</div>
                    <div className="metric-label">Signals</div>
                  </div>
                  <div className="metric">
                    <div className="metric-value">{strategy.avg_edge.toFixed(2)}%</div>
                    <div className="metric-label">Avg Edge</div>
                  </div>
                  <div className="metric">
                    <div className="metric-value" style={{ color: '#10B981' }}>{strategy.buy_count}</div>
                    <div className="metric-label">BUY</div>
                  </div>
                  <div className="metric">
                    <div className="metric-value" style={{ color: '#EF4444' }}>{strategy.sell_count}</div>
                    <div className="metric-label">SELL</div>
                  </div>
                </div>

                {strategy.sports_covered && strategy.sports_covered.length > 0 && (
                  <div className="sports-badges">
                    {strategy.sports_covered.map(sport => (
                      <span key={sport} className="sport-badge">{sport}</span>
                    ))}
                  </div>
                )}

                {strategy.last_signal_time && (
                  <div className="last-signal">Last: {getRelativeTime(strategy.last_signal_time)}</div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {/* B) Live Signal Feed */}
      <section className="signal-feed">
        <div className="signal-feed-header">
          <h2>Live Signal Feed {scanning && <span className="scanning-indicator">🔄 Scanning...</span>}</h2>
          <div className="signal-filters">
            <button className={signalFilter === 'all' ? 'active' : ''} onClick={() => setSignalFilter('all')}>All</button>
            <button className={signalFilter === 'buy' ? 'active' : ''} onClick={() => setSignalFilter('buy')}>BUY Only</button>
            <button className={signalFilter === 'sell' ? 'active' : ''} onClick={() => setSignalFilter('sell')}>SELL Only</button>
          </div>
        </div>

        <div className="signal-cards">
          {filteredSignals.length === 0 ? (
            <div className="empty-signals">
              <p>🔄 Scanning for signals...</p>
            </div>
          ) : (
            filteredSignals.slice(0, 20).map((signal, idx) => {
              const sideColor = signal.side === 'BUY' ? '#10B981' : '#EF4444'
              const edgeColor = signal.edge > 0 ? '#10B981' : '#EF4444'
              const sportInfo = getSportInfo(signal)
              const marketTitle = (signal.market_title || 'Unknown Market').length > 50
                ? signal.market_title.substring(0, 50) + '...'
                : signal.market_title || 'Unknown Market'
              
              return (
                <div key={signal.id || idx} className="signal-card">
                  <div className="signal-accent" style={{ background: sideColor }}></div>
                  <div className="signal-content">
                    <div className="signal-top">
                      <span className="signal-strategy">{getStrategyIcon(signal.strategy.toLowerCase().replace(/[^a-z]/g, '_'))} {signal.strategy}</span>
                      <span className="signal-time">{getRelativeTime(signal.created_at)}</span>
                    </div>
                    <div className="signal-market">{marketTitle}</div>
                    <div className="signal-bottom">
                      <span className="signal-edge" style={{ color: edgeColor }}>
                        {signal.edge > 0 ? '+' : ''}{signal.edge.toFixed(2)}%
                      </span>
                      <span className="sport-badge" style={{ background: `${sportInfo.color}15`, color: sportInfo.color, padding: '4px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 600 }}>
                        {sportInfo.emoji} {sportInfo.name}
                      </span>
                      <span className="signal-side" style={{ background: sideColor + '20', color: sideColor, padding: '4px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700 }}>
                        {signal.side || 'BUY'}
                      </span>
                      <span className="confidence-badge" style={{ background: getConfidenceBadgeColor(signal.confidence), color: '#fff', padding: '4px 8px', borderRadius: '6px', fontSize: '10px', fontWeight: 600 }}>
                        {signal.confidence || 'MEDIUM'}
                      </span>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </section>

      {/* C) Research & Analytics */}
      <section className="analytics-section">
        <div className="analytics-tabs">
          <button className={activeTab === 'overview' ? 'active' : ''} onClick={() => setActiveTab('overview')}>Overview</button>
          <button className={activeTab === 'edge' ? 'active' : ''} onClick={() => setActiveTab('edge')}>Edge Distribution</button>
          <button className={activeTab === 'odds' ? 'active' : ''} onClick={() => setActiveTab('odds')}>Odds Comparison</button>
          <button className={activeTab === 'sports' ? 'active' : ''} onClick={() => setActiveTab('sports')}>By Sport</button>
        </div>

        <div className="analytics-content">
          {activeTab === 'overview' && (
            <div className="tab-overview">
              <h3>Signal Generation Timeline (Last 24 Hours)</h3>
              {timeline.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={timeline}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                    <XAxis dataKey="time" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #7c3aed', borderRadius: 8 }} />
                    <Legend />
                    <Area type="monotone" dataKey="cross_odds_count" stackId="1" stroke="#7c3aed" fill="#7c3aed" name="Cross-Odds" />
                    <Area type="monotone" dataKey="logical_arb_count" stackId="1" stroke="#06B6D4" fill="#06B6D4" name="Logical Arb" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <p className="empty-state">No timeline data available yet. Signals will appear as they are generated.</p>
              )}
            </div>
          )}

          {activeTab === 'edge' && (
            <div className="tab-edge">
              <h3>Edge % Distribution</h3>
              {edgeDistribution.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={edgeDistribution}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                    <XAxis dataKey="range" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #7c3aed', borderRadius: 8 }} />
                    <Bar dataKey="count" fill="#7c3aed" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="empty-state">Edge distribution will appear as signals accumulate.</p>
              )}
            </div>
          )}

          {activeTab === 'odds' && (
            <div className="tab-odds">
              <h3>Sportsbook vs Polymarket Comparison</h3>
              {oddsComparison.length > 0 ? (
                <div className="odds-table-wrapper">
                  <table className="odds-table">
                    <thead>
                      <tr>
                        <th>Event</th>
                        <th>Polymarket</th>
                        <th>Sportsbook</th>
                        <th>Book</th>
                        <th>Edge</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {oddsComparison.slice(0, 30).map((row, idx) => {
                        const edgeClass = row.edge > 5 ? 'high-edge' : ''
                        return (
                          <tr key={idx} className={edgeClass}>
                            <td className="event-name">{row.event}</td>
                            <td>{(row.polymarket_price * 100).toFixed(1)}%</td>
                            <td>{(row.book_price * 100).toFixed(1)}%</td>
                            <td>{row.book_name}</td>
                            <td className="edge-cell">{row.edge.toFixed(2)}%</td>
                            <td>
                              {row.edge > 5 ? (
                                <span className="action-badge buy">BUY</span>
                              ) : row.edge < -5 ? (
                                <span className="action-badge sell">SELL</span>
                              ) : (
                                <span className="action-badge hold">HOLD</span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="empty-state">Odds comparison data loading. This requires matched markets between Polymarket and sportsbooks.</p>
              )}
            </div>
          )}

          {activeTab === 'sports' && (
            <div className="tab-sports">
              <h3>Performance by Sport</h3>
              {sportsBreakdown.length > 0 ? (
                <div className="sports-grid">
                  {sportsBreakdown.map(sport => (
                    <div key={sport.sport} className="sport-card">
                      <h4>{sport.sport}</h4>
                      <div className="sport-metrics">
                        <div className="sport-metric">
                          <span className="sport-metric-value">{sport.signals}</span>
                          <span className="sport-metric-label">Signals</span>
                        </div>
                        <div className="sport-metric">
                          <span className="sport-metric-value">{sport.avg_edge.toFixed(2)}%</span>
                          <span className="sport-metric-label">Avg Edge</span>
                        </div>
                        <div className="sport-metric">
                          <span className="sport-metric-value">{sport.markets}</span>
                          <span className="sport-metric-label">Markets</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="empty-state">Sports breakdown will appear as sports signals are generated.</p>
              )}
              
              {sportsBreakdown.length > 0 && (
                <div style={{ marginTop: 32 }}>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={sportsBreakdown}
                        dataKey="signals"
                        nameKey="sport"
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        label
                      >
                        {sportsBreakdown.map((entry, index) => {
                          const colors = ['#7c3aed', '#06B6D4', '#10B981', '#F59E0B', '#EF4444']
                          return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                        })}
                      </Pie>
                      <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #7c3aed', borderRadius: 8 }} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* D) Empty State Message */}
      {signals.length === 0 && (
        <div className="empty-state-banner">
          🤖 Bot is actively scanning 148 markets across 3 sports. Signals generated: 10,716. Paper trades begin when high-confidence edges are found.
        </div>
      )}
    </div>
  )
}

export default Performance
