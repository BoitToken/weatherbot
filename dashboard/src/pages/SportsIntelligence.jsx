import { useState, useEffect } from 'react'
import axios from 'axios'

function SportsIntelligence() {
  const [markets, setMarkets] = useState(null)
  const [groups, setGroups] = useState(null)
  const [arbitrage, setArbitrage] = useState(null)
  const [live, setLive] = useState(null)
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(true)
  const [sportFilter, setSportFilter] = useState('all')
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchAll = async () => {
    try {
      const [mRes, gRes, aRes, lRes, sRes] = await Promise.all([
        axios.get('/api/sports/markets?limit=200').catch(() => ({ data: { total: 0, by_sport: {}, markets: [] } })),
        axios.get('/api/sports/groups').catch(() => ({ data: { groups: [] } })),
        axios.get('/api/sports/arbitrage').catch(() => ({ data: { opportunities: [] } })),
        axios.get('/api/sports/live').catch(() => ({ data: { events: [] } })),
        axios.get('/api/sports/signals').catch(() => ({ data: { signals: [] } })),
      ])
      setMarkets(mRes.data)
      setGroups(gRes.data)
      setArbitrage(aRes.data)
      setLive(lRes.data)
      setSignals(sRes.data.signals || [])
      setLoading(false)
    } catch { setLoading(false) }
  }

  if (loading) return <div className="loading">Loading sports intelligence...</div>

  const sportCounts = markets?.by_sport || {}
  const allSports = Object.keys(sportCounts).sort((a, b) => sportCounts[b].count - sportCounts[a].count)
  const arbCount = arbitrage?.total || 0
  const liveCount = live?.live || 0
  const overpricedGroups = (groups?.groups || []).filter(g => g.overpriced)

  const filteredMarkets = (markets?.markets || []).filter(m => sportFilter === 'all' || m.sport === sportFilter)

  const sportEmoji = { nhl: '🏒', nba: '🏀', soccer: '⚽', mlb: '⚾', nfl: '🏈', tennis: '🎾', cricket: '🏏', f1: '🏎️', combat: '🥊', other: '🎯' }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">🏆 Sports Intelligence</h1>
        <p className="page-subtitle">{markets?.total || 0} active markets · {arbCount} arbitrage opportunities · {liveCount} live games</p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap', overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        {['overview', 'arbitrage', 'live', 'signals'].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            style={{ padding: '8px 16px', borderRadius: 8, border: activeTab === tab ? '1px solid #F59E0B' : '1px solid var(--border)',
              background: activeTab === tab ? 'rgba(245,158,11,0.12)' : 'var(--bg-tertiary)',
              color: activeTab === tab ? '#F59E0B' : 'var(--text-secondary)', fontWeight: 600, fontSize: 13, cursor: 'pointer', textTransform: 'capitalize' }}>
            {tab === 'arbitrage' ? `🔒 Arbitrage (${arbCount})` : tab === 'live' ? `⚡ Live (${liveCount})` : tab === 'signals' ? `📊 Signals (${signals.length})` : '📋 Overview'}
          </button>
        ))}
      </div>

      {/* Sport Filter Chips */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <button onClick={() => setSportFilter('all')}
          style={{ padding: '5px 12px', borderRadius: 12, border: sportFilter === 'all' ? '1px solid #8B5CF6' : '1px solid var(--border)',
            background: sportFilter === 'all' ? 'rgba(139,92,246,0.12)' : 'transparent',
            color: sportFilter === 'all' ? '#8B5CF6' : 'var(--text-secondary)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
          All ({markets?.total || 0})
        </button>
        {allSports.map(s => (
          <button key={s} onClick={() => setSportFilter(s)}
            style={{ padding: '5px 12px', borderRadius: 12, border: sportFilter === s ? '1px solid #8B5CF6' : '1px solid var(--border)',
              background: sportFilter === s ? 'rgba(139,92,246,0.12)' : 'transparent',
              color: sportFilter === s ? '#8B5CF6' : 'var(--text-secondary)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
            {sportEmoji[s] || '🎯'} {s.toUpperCase()} ({sportCounts[s]?.count || 0})
          </button>
        ))}
      </div>

      {/* OVERVIEW TAB */}
      {activeTab === 'overview' && (
        <>
          {/* Sport Summary Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 24 }}>
            {allSports.map(s => (
              <div key={s} className="card" style={{ padding: 16, cursor: 'pointer' }} onClick={() => setSportFilter(s)}>
                <div style={{ fontSize: 24, marginBottom: 6 }}>{sportEmoji[s] || '🎯'}</div>
                <div style={{ fontSize: 14, fontWeight: 700 }}>{s.toUpperCase()}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{sportCounts[s]?.count} markets</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>${(sportCounts[s]?.total_volume / 1e6).toFixed(1)}M volume</div>
              </div>
            ))}
          </div>

          {/* Market Groups with Sum Analysis */}
          {(groups?.groups || []).length > 0 && (
            <div className="card" style={{ padding: 20, marginBottom: 24 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>📊 Market Groups — Sum Analysis</h3>
              <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 16 }}>
                Groups where YES prices sum &gt;105% = overpriced (arbitrage opportunity). Red = arb exists.
              </p>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      <th style={{ padding: '8px', textAlign: 'left', color: 'var(--text-secondary)' }}>Group</th>
                      <th style={{ padding: '8px', textAlign: 'center' }}>Sport</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>Markets</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>Sum %</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>Edge</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>Volume</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(groups?.groups || []).filter(g => sportFilter === 'all' || g.sport === sportFilter).slice(0, 30).map(g => (
                      <tr key={g.group_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)',
                        background: g.overpriced ? 'rgba(239,68,68,0.06)' : 'transparent' }}>
                        <td style={{ padding: '8px', fontWeight: 600, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{g.group_id}</td>
                        <td style={{ padding: '8px', textAlign: 'center' }}>{sportEmoji[g.sport] || '🎯'}</td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>{g.market_count}</td>
                        <td style={{ padding: '8px', textAlign: 'right', fontWeight: 700,
                          color: g.sum_pct > 105 ? '#EF4444' : g.sum_pct > 100 ? '#F59E0B' : '#10B981' }}>
                          {g.sum_pct}%
                        </td>
                        <td style={{ padding: '8px', textAlign: 'right', color: g.arb_edge > 0 ? '#EF4444' : 'var(--text-secondary)', fontWeight: g.arb_edge > 0 ? 700 : 400 }}>
                          {g.arb_edge > 0 ? `${g.arb_edge}%` : '—'}
                        </td>
                        <td style={{ padding: '8px', textAlign: 'right', color: 'var(--text-secondary)' }}>${(g.total_volume / 1e6).toFixed(1)}M</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Top Markets */}
          <div className="card" style={{ padding: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>🏆 Top Markets by Volume</h3>
            <div style={{ display: 'grid', gap: 8 }}>
              {filteredMarkets.slice(0, 20).map(m => (
                <div key={m.market_id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
                  background: 'var(--bg-tertiary)', borderRadius: 8, border: '1px solid var(--border)' }}>
                  <span style={{ fontSize: 18 }}>{sportEmoji[m.sport] || '🎯'}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.question}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{m.sport?.toUpperCase()} · {m.event_type} · ${(parseFloat(m.volume_usd || 0) / 1e6).toFixed(1)}M vol</div>
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <div style={{ fontSize: 18, fontWeight: 800, color: '#10B981' }}>{(parseFloat(m.yes_price || 0) * 100).toFixed(0)}¢</div>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>YES</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* ARBITRAGE TAB */}
      {activeTab === 'arbitrage' && (
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>🔒 Logical Arbitrage Opportunities</h3>
          {(arbitrage?.opportunities || []).length === 0 ? (
            <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-secondary)' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🔍</div>
              <p>Scanning for arbitrage... Correlation engine checks group sums, subset violations, and binary mispricing every 3 minutes.</p>
              {overpricedGroups.length > 0 && (
                <p style={{ marginTop: 12, color: '#F59E0B' }}>⚠️ {overpricedGroups.length} overpriced groups detected — check Overview → Sum Analysis</p>
              )}
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 12 }}>
              {(arbitrage.opportunities).map((opp, i) => (
                <div key={i} style={{ padding: 16, background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: 10 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6 }}>{opp.type || 'Arbitrage'}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>{opp.reasoning || opp.description}</div>
                  <div style={{ display: 'flex', gap: 16 }}>
                    <span style={{ fontSize: 12 }}>Edge: <strong style={{ color: '#EF4444' }}>{opp.edge_pct?.toFixed(1)}%</strong></span>
                    <span style={{ fontSize: 12 }}>Market: {opp.market_title || opp.group_id}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* LIVE TAB */}
      {activeTab === 'live' && (
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>⚡ Live & Upcoming Games</h3>
          {(live?.events || []).length === 0 ? (
            <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-secondary)' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>📺</div>
              <p>No live games right now. ESPN feeds update automatically when games start.</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {(live.events).map(e => (
                <div key={e.event_id || e.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 14,
                  background: e.status === 'live' ? 'rgba(239,68,68,0.06)' : 'var(--bg-tertiary)', borderRadius: 10,
                  border: e.status === 'live' ? '1px solid rgba(239,68,68,0.2)' : '1px solid var(--border)' }}>
                  <span style={{ fontSize: 20 }}>{sportEmoji[e.sport] || '🎯'}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{e.home_team} vs {e.away_team}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{e.sport?.toUpperCase()} · {e.period || ''} {e.minute ? `${e.minute}'` : ''}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 20, fontWeight: 800 }}>{e.home_score} - {e.away_score}</div>
                    <div style={{ fontSize: 10, padding: '2px 8px', borderRadius: 8, fontWeight: 600,
                      background: e.status === 'live' ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.12)',
                      color: e.status === 'live' ? '#EF4444' : '#F59E0B' }}>
                      {e.status?.toUpperCase()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SIGNALS TAB */}
      {activeTab === 'signals' && (
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>📊 Sports Trading Signals</h3>
          {signals.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-secondary)' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🔄</div>
              <p>Scanning markets for edges... Signals will appear when the correlation engine or cross-odds engine detect mispricing.</p>
            </div>
          ) : (
            <div className="table-container">
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={{ padding: 8, textAlign: 'left' }}>Time</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>Type</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>Sport</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>Market</th>
                    <th style={{ padding: 8, textAlign: 'right' }}>Price</th>
                    <th style={{ padding: 8, textAlign: 'right' }}>Fair Value</th>
                    <th style={{ padding: 8, textAlign: 'right' }}>Edge</th>
                    <th style={{ padding: 8, textAlign: 'center' }}>Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {signals.map(s => (
                    <tr key={s.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: 8 }}>{new Date(s.created_at).toLocaleTimeString()}</td>
                      <td style={{ padding: 8 }}><span style={{ padding: '2px 6px', borderRadius: 4, fontSize: 10, background: 'rgba(139,92,246,0.12)', color: '#8B5CF6' }}>{s.edge_type}</span></td>
                      <td style={{ padding: 8 }}>{sportEmoji[s.sport] || ''} {s.sport}</td>
                      <td style={{ padding: 8, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.market_title}</td>
                      <td style={{ padding: 8, textAlign: 'right' }}>{(parseFloat(s.polymarket_price || 0) * 100).toFixed(0)}¢</td>
                      <td style={{ padding: 8, textAlign: 'right', color: '#8B5CF6' }}>{(parseFloat(s.fair_value || 0) * 100).toFixed(0)}¢</td>
                      <td style={{ padding: 8, textAlign: 'right', color: '#10B981', fontWeight: 700 }}>{parseFloat(s.edge_pct || 0).toFixed(1)}%</td>
                      <td style={{ padding: 8, textAlign: 'center' }}>
                        <span style={{ padding: '3px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700,
                          background: s.signal === 'BUY' ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.12)',
                          color: s.signal === 'BUY' ? '#10B981' : '#F59E0B' }}>{s.signal}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default SportsIntelligence
