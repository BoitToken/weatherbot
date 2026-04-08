import { useState, useEffect } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceDot } from 'recharts'

function Trades() {
  const [activeTab, setActiveTab] = useState('scanner') // scanner | trades
  
  // Performance summary (used in Trades tab)
  const [performanceSummary, setPerformanceSummary] = useState({
    totalPnl: 0, roiPct: 0, winRate: 0, totalTrades: 0,
    activePositions: 0, bestTrade: 0, worstTrade: 0, wins: 0, losses: 0
  })
  
  // Trades tab data
  const [pnlData, setPnlData] = useState([])
  const [strategyComparison, setStrategyComparison] = useState([])
  const [recentTrades, setRecentTrades] = useState([])
  const [activePositions, setActivePositions] = useState([])
  const [signalsData, setSignalsData] = useState([])
  
  // Scanner tab data
  const [scannerOpportunities, setScannerOpportunities] = useState([])
  const [groupOverpricing, setGroupOverpricing] = useState([])
  
  // UI state
  const [loading, setLoading] = useState(true)
  const [timeRange, setTimeRange] = useState('7d') // 7d | 30d | all
  const [tradeFilter, setTradeFilter] = useState('all') // all | open | won | lost | by-strategy
  const [selectedStrategy, setSelectedStrategy] = useState(null)
  const [sportFilter, setSportFilter] = useState('all') // all | ipl | nba | nhl | soccer

  useEffect(() => {
    fetchAllData()
    const interval = setInterval(fetchAllData, 10000) // Refresh every 30s
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
        strategyRes,
        oddsComparisonRes,
        arbitrageRes,
        groupsRes,
        signalsRes
      ] = await Promise.all([
        axios.get('/api/trades?limit=100').catch(() => ({ data: { data: [] } })),
        axios.get('/api/trades/active').catch(() => ({ data: { data: [] } })),
        axios.get(`/api/analytics/win-rate?days=${days}`).catch(() => ({ data: { win_rate: 0, total_trades: 0, wins: 0, losses: 0 } })),
        axios.get(`/api/pnl/daily?days=${days}`).catch(() => ({ data: { data: [] } })),
        axios.get('/api/bankroll').catch(() => ({ data: { total: 0 } })),
        axios.get('/api/strategy/comparison').catch(() => ({ data: { strategies: [] } })),
        axios.get('/api/performance/odds-comparison').catch(() => ({ data: { data: [] } })),
        axios.get('/api/sports/arbitrage').catch(() => ({ data: { data: [] } })),
        axios.get('/api/sports/groups').catch(() => ({ data: { data: [] } })),
        axios.get('/api/performance/signals/latest').catch(() => ({ data: { data: [] } }))
      ])

      const trades = tradesRes.data.data || []
      const active = activeRes.data.data || []
      const winRateData = winRateRes.data
      const pnl = pnlRes.data.data || []
      const bankroll = bankrollRes.data
      
      // Normalize strategies (can be dict or array)
      const rawStrategies = strategyRes.data.strategies || []
      const strategies = Array.isArray(rawStrategies) 
        ? rawStrategies 
        : Object.entries(rawStrategies).map(([key, val]) => ({ id: key, name: key, ...val }))

      // Scanner data
      const oddsComparison = oddsComparisonRes.data.data || []
      const arbitrage = arbitrageRes.data.data || []
      const groups = groupsRes.data.data || []
      const signals = signalsRes.data.data || []

      setRecentTrades(trades)
      setActivePositions(active)
      setStrategyComparison(strategies)
      setSignalsData(signals)

      // Combine scanner opportunities
      const opportunities = [
        ...oddsComparison.map(o => ({ ...o, source: 'odds_comparison' })),
        ...arbitrage.map(a => ({ ...a, source: 'arbitrage' })),
        ...groups.filter(g => (g.sum_probability || 0) > 1.0).map(g => ({ ...g, source: 'group_overpricing' }))
      ]
      setScannerOpportunities(opportunities)
      setGroupOverpricing(groups.filter(g => (g.sum_probability || 0) > 1.0))

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
      console.error('Failed to fetch data:', error)
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

  const getFilteredOpportunities = () => {
    let filtered = scannerOpportunities

    if (sportFilter !== 'all') {
      filtered = filtered.filter(o => {
        const sport = (o.sport || o.market_title || '').toLowerCase()
        return sport.includes(sportFilter.toLowerCase())
      })
    }

    // Sort by edge (highest first)
    return filtered.sort((a, b) => {
      const edgeA = a.edge || a.edge_pct || a.sum_probability || 0
      const edgeB = b.edge || b.edge_pct || b.sum_probability || 0
      return edgeB - edgeA
    })
  }

  const getSportInfo = (trade) => {
    const title = (trade.market_title || trade.match_name || '').toLowerCase()
    const sport = (trade.sport || '').toLowerCase()
    if (title.includes('ipl') || sport.includes('ipl') || sport.includes('cricket')) return { emoji: '🏏', name: 'IPL', color: '#FF6B00' }
    if (title.includes('nba') || sport.includes('nba') || sport.includes('basketball')) return { emoji: '🏀', name: 'NBA', color: '#1D428A' }
    if (title.includes('nhl') || sport.includes('nhl') || sport.includes('hockey')) return { emoji: '🏒', name: 'NHL', color: '#A2AAAD' }
    if (title.includes('soccer') || sport.includes('soccer') || sport.includes('football')) return { emoji: '⚽', name: 'Soccer', color: '#00B140' }
    if (sport.includes('mlb') || sport.includes('baseball')) return { emoji: '⚾', name: 'MLB', color: '#002D72' }
    if (sport.includes('nfl')) return { emoji: '🏈', name: 'NFL', color: '#A2AAAD' }
    return { emoji: '🎯', name: 'Other', color: '#7c3aed' }
  }

  const getSportEmoji = (sport) => {
    return getSportInfo({ sport }).emoji
  }

  if (loading) {
    return (
      <div className="loading" style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        minHeight: '60vh',
        color: 'var(--text-secondary)'
      }}>
        Loading dashboard...
      </div>
    )
  }

  const filteredTrades = getFilteredTrades()
  const filteredOpportunities = getFilteredOpportunities()

  return (
    <div className="trades-page" style={{ paddingBottom: 40 }}>
      {/* Page Header */}
      <div className="page-header" style={{ marginBottom: 24 }}>
        <h1 className="page-title" style={{ fontSize: 28, fontWeight: 800, marginBottom: 8 }}>
          💰 Trading Dashboard
        </h1>
        <p className="page-subtitle" style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
          Market scanner, trade history, and strategy analytics
        </p>
      </div>

      {/* Tab Bar */}
      <div style={{ 
        display: 'flex', 
        gap: 0, 
        borderBottom: '2px solid var(--border)',
        marginBottom: 32,
        overflowX: 'auto',
        WebkitOverflowScrolling: 'touch'
      }}>
        <button
          onClick={() => setActiveTab('scanner')}
          style={{
            padding: '14px 24px',
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'scanner' ? '3px solid #7c3aed' : '3px solid transparent',
            color: activeTab === 'scanner' ? '#7c3aed' : 'var(--text-secondary)',
            fontWeight: 700,
            fontSize: 15,
            cursor: 'pointer',
            transition: 'all 0.2s',
            whiteSpace: 'nowrap',
            minHeight: 44
          }}
        >
          🔍 Scanner
        </button>
        <button
          onClick={() => setActiveTab('trades')}
          style={{
            padding: '14px 24px',
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'trades' ? '3px solid #7c3aed' : '3px solid transparent',
            color: activeTab === 'trades' ? '#7c3aed' : 'var(--text-secondary)',
            fontWeight: 700,
            fontSize: 15,
            cursor: 'pointer',
            transition: 'all 0.2s',
            whiteSpace: 'nowrap',
            minHeight: 44
          }}
        >
          💰 Trades
        </button>
      </div>

      {/* SCANNER TAB */}
      {activeTab === 'scanner' && (
        <div className="scanner-tab">
          {/* Sport Filter */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap' }}>
            {['all', 'IPL', 'NBA', 'NHL', 'Soccer', 'MLB'].map(sport => {
              const sportInfo = getSportInfo({ sport })
              return (
                <button
                  key={sport}
                  onClick={() => setSportFilter(sport)}
                  className={`btn ${sportFilter === sport ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ 
                    padding: '8px 16px', 
                    fontSize: 13,
                    minHeight: 44,
                    background: sportFilter === sport ? (sport === 'all' ? '#7c3aed' : sportInfo.color) : 'var(--bg-secondary)',
                    color: sportFilter === sport ? '#fff' : 'var(--text-primary)',
                    border: sportFilter === sport ? 'none' : '1px solid var(--border)'
                  }}
                >
                  {sport === 'all' ? 'All' : `${sportInfo.emoji} ${sport}`}
                </button>
              )
            })}
          </div>

          {/* Opportunities Grid */}
          {filteredOpportunities.length === 0 ? (
            <div className="empty-state" style={{ 
              textAlign: 'center', 
              padding: 60,
              background: 'var(--bg-secondary)',
              borderRadius: 16,
              border: '1px solid var(--border)'
            }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
              <p style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>No opportunities found</p>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                Scanner is actively monitoring markets. Arbitrage opportunities will appear here.
              </p>
            </div>
          ) : (
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
              gap: 16
            }}>
              {(Array.isArray(filteredOpportunities) ? filteredOpportunities : []).map((opp, idx) => {
                const edge = (opp.edge || opp.edge_pct || (opp.sum_probability ? (opp.sum_probability - 1) * 100 : 0)) * (opp.edge < 1 ? 100 : 1)
                const matchName = opp.market_title || opp.event || opp.match_name || opp.group_name || 'Unknown Market'
                const sportInfo = getSportInfo(opp)
                const polymarketPrice = opp.polymarket_price || opp.pm_price || null
                const sportsbookPrice = opp.sportsbook_price || opp.book_price || opp.sb_price || null
                const bookName = opp.book_name || opp.sportsbook || 'Multiple'
                const numBooks = opp.num_books || opp.agreeing_books || 1
                const signal = edge > 0 ? 'BUY' : 'SELL'

                return (
                  <div
                    key={idx}
                    style={{
                      background: '#1a1a2e',
                      border: '1px solid var(--border)',
                      borderRadius: 12,
                      padding: 16,
                      position: 'relative',
                      transition: 'transform 0.2s, box-shadow 0.2s',
                      cursor: 'pointer'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = 'translateY(-2px)'
                      e.currentTarget.style.boxShadow = '0 8px 16px rgba(124,58,237,0.2)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0)'
                      e.currentTarget.style.boxShadow = 'none'
                    }}
                  >
                    {/* Sport badge + match name */}
                    <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ 
                        padding: '4px 8px',
                        borderRadius: 6,
                        fontSize: 12,
                        fontWeight: 700,
                        background: `${sportInfo.color}20`,
                        color: sportInfo.color
                      }}>
                        {sportInfo.emoji} {sportInfo.name}
                      </span>
                      <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', flex: 1 }}>
                        {matchName.length > 40 ? matchName.substring(0, 40) + '...' : matchName}
                      </span>
                    </div>

                    {/* Edge badge */}
                    <div style={{ 
                      position: 'absolute',
                      top: 16,
                      right: 16,
                      background: edge > 10 ? '#10B981' : edge > 5 ? '#F59E0B' : '#EF4444',
                      color: '#fff',
                      padding: '6px 12px',
                      borderRadius: 8,
                      fontSize: 16,
                      fontWeight: 800
                    }}>
                      {edge.toFixed(1)}%
                    </div>

                    {/* Prices comparison */}
                    {polymarketPrice !== null && sportsbookPrice !== null && (
                      <div style={{ 
                        display: 'grid', 
                        gridTemplateColumns: '1fr 1fr',
                        gap: 12,
                        marginTop: 16,
                        marginBottom: 16
                      }}>
                        <div style={{ 
                          background: 'var(--bg-primary)',
                          padding: 12,
                          borderRadius: 8,
                          border: '1px solid var(--border)'
                        }}>
                          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                            Polymarket
                          </div>
                          <div style={{ fontSize: 18, fontWeight: 700, color: '#7c3aed' }}>
                            {(polymarketPrice * 100).toFixed(0)}¢
                          </div>
                        </div>
                        <div style={{ 
                          background: 'var(--bg-primary)',
                          padding: 12,
                          borderRadius: 8,
                          border: '1px solid var(--border)'
                        }}>
                          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                            Sportsbooks
                          </div>
                          <div style={{ fontSize: 18, fontWeight: 700, color: '#10B981' }}>
                            {(sportsbookPrice * 100).toFixed(0)}¢
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Footer: Signal + Book Name */}
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      paddingTop: 12,
                      borderTop: '1px solid var(--border)'
                    }}>
                      <span style={{
                        background: signal === 'BUY' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                        color: signal === 'BUY' ? '#10B981' : '#EF4444',
                        padding: '4px 12px',
                        borderRadius: 6,
                        fontSize: 12,
                        fontWeight: 700
                      }}>
                        {signal}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                        {bookName}
                      </span>
                    </div>

                    {/* Paper Trade button (future) */}
                    <button
                      style={{
                        width: '100%',
                        marginTop: 12,
                        padding: '10px',
                        background: 'transparent',
                        border: '1px solid #7c3aed',
                        borderRadius: 8,
                        color: '#7c3aed',
                        fontSize: 13,
                        fontWeight: 600,
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        minHeight: 44
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#7c3aed'
                        e.currentTarget.style.color = '#fff'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent'
                        e.currentTarget.style.color = '#7c3aed'
                      }}
                    >
                      Paper Trade
                    </button>
                  </div>
                )
              })}
            </div>
          )}

          {/* IPL Paper Trades from signals */}
          {Array.isArray(signalsData) && signalsData.length > 0 && (
            <div style={{ marginTop: 32 }}>
              <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>
                🏏 IPL Paper Trades
              </h3>
              <div style={{ display: 'grid', gap: 12 }}>
                {signalsData.map((signal, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: '#1a1a2e',
                      border: '1px solid var(--border)',
                      borderRadius: 12,
                      padding: 16,
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: 12
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>
                        {signal.market_title || signal.match_name}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                        Edge: {((signal.edge || 0) * 100).toFixed(1)}% • 
                        Side: <span style={{ color: signal.side === 'YES' ? '#10B981' : '#EF4444' }}>
                          {signal.side}
                        </span>
                      </div>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                      {new Date(signal.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TRADES TAB */}
      {activeTab === 'trades' && (
        <div className="trades-tab">
          {/* Summary Banner */}
          <div style={{
            background: '#1a1a2e',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 12,
            padding: 20,
            marginBottom: 24,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 16
          }}>
            <div>
              <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 4 }}>Total Deployed</div>
              <div style={{ fontSize: 24, fontWeight: 800 }}>${(Array.isArray(activePositions) ? activePositions : []).reduce((sum, t) => sum + (t.size_usd || 0), 0).toFixed(2)}</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 4 }}>Won</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#10B981' }}>{performanceSummary.wins}</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 4 }}>Open</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#F59E0B' }}>{performanceSummary.activePositions}</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 4 }}>P&L</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: performanceSummary.totalPnl >= 0 ? '#10B981' : '#EF4444' }}>
                {performanceSummary.totalPnl >= 0 ? '+' : ''}${performanceSummary.totalPnl.toFixed(2)}
              </div>
            </div>
          </div>

          {/* Performance Summary Cards */}
          <div style={{ 
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 16,
            marginBottom: 24
          }}>
            <div className="card" style={{ 
              background: '#1a1a2e',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: 16
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                Total P&L
              </div>
              <div style={{ 
                fontSize: 24, 
                fontWeight: 800,
                color: performanceSummary.totalPnl >= 0 ? '#10B981' : '#EF4444'
              }}>
                {performanceSummary.totalPnl >= 0 ? '+' : ''}${performanceSummary.totalPnl.toFixed(2)}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                {performanceSummary.roiPct >= 0 ? '+' : ''}{performanceSummary.roiPct.toFixed(2)}% ROI
              </div>
            </div>

            <div className="card" style={{ 
              background: '#1a1a2e',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: 16
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                Win Rate
              </div>
              <div style={{ fontSize: 24, fontWeight: 800 }}>
                {performanceSummary.winRate.toFixed(1)}%
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                {performanceSummary.wins}W / {performanceSummary.losses}L
              </div>
            </div>

            <div className="card" style={{ 
              background: '#1a1a2e',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: 16
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                Active Positions
              </div>
              <div style={{ fontSize: 24, fontWeight: 800 }}>
                {performanceSummary.activePositions}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                Open Trades
              </div>
            </div>

            <div className="card" style={{ 
              background: '#1a1a2e',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: 16
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                Total Trades
              </div>
              <div style={{ fontSize: 24, fontWeight: 800 }}>
                {performanceSummary.totalTrades}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                All Time
              </div>
            </div>
          </div>

          {/* Trade History */}
          <div style={{ 
            background: '#1a1a2e',
            border: '1px solid var(--border)',
            borderRadius: 12,
            padding: 24
          }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              marginBottom: 20,
              flexWrap: 'wrap',
              gap: 12
            }}>
              <h3 style={{ fontSize: 18, fontWeight: 700 }}>📋 Trade History</h3>
              
              {/* Filters */}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {['all', 'open', 'won', 'lost'].map(filter => (
                  <button
                    key={filter}
                    onClick={() => { setTradeFilter(filter); setSelectedStrategy(null) }}
                    style={{
                      padding: '6px 14px',
                      fontSize: 12,
                      textTransform: 'capitalize',
                      background: tradeFilter === filter && !selectedStrategy ? '#7c3aed' : 'var(--bg-primary)',
                      color: tradeFilter === filter && !selectedStrategy ? '#fff' : 'var(--text-primary)',
                      border: tradeFilter === filter && !selectedStrategy ? 'none' : '1px solid var(--border)',
                      borderRadius: 8,
                      cursor: 'pointer',
                      fontWeight: 600,
                      minHeight: 44
                    }}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>

            {filteredTrades.length === 0 ? (
              <div className="empty-state" style={{ 
                textAlign: 'center', 
                padding: 60
              }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>💤</div>
                <p style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>No trades yet</p>
                <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                  Bot is scanning markets. Trades will appear here once signals trigger.
                </p>
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 12 }}>
                {(Array.isArray(filteredTrades) ? filteredTrades : []).map(trade => {
                  const pnl = parseFloat(trade.pnl_usd || trade.unrealized_pnl_usd || 0)
                  const isWin = pnl > 0
                  const isOpen = trade.status === 'open'
                  const statusEmoji = isOpen ? '⏳' : isWin ? '✅' : '❌'
                  const statusLabel = isOpen ? 'Open' : isWin ? 'Won' : 'Lost'
                  const accentColor = isOpen ? '#F59E0B' : isWin ? '#10B981' : '#EF4444'
                  const sportInfo = getSportInfo(trade)
                  
                  return (
                    <div
                      key={trade.id}
                      style={{
                        background: 'var(--bg-primary)',
                        borderRadius: 12,
                        padding: 16,
                        borderLeft: `4px solid ${accentColor}`,
                        border: `1px solid var(--border)`,
                        borderLeftWidth: '4px',
                        position: 'relative'
                      }}
                    >
                      {/* Header: Status + Time */}
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between',
                        marginBottom: 12,
                        alignItems: 'center'
                      }}>
                        <span style={{
                          background: isOpen ? 'rgba(245,158,11,0.15)' : isWin ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                          color: accentColor,
                          padding: '4px 10px',
                          borderRadius: 6,
                          fontSize: 12,
                          fontWeight: 700
                        }}>
                          {statusEmoji} {statusLabel}
                        </span>
                        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                          {new Date(trade.created_at).toLocaleString([], {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </span>
                      </div>

                      {/* Market name + Sport badge */}
                      <div style={{ 
                        fontWeight: 600, 
                        marginBottom: 12,
                        fontSize: 15,
                        color: 'var(--text-primary)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        flexWrap: 'wrap'
                      }}>
                        <span style={{ flex: 1, minWidth: 0 }}>
                          {trade.market_title || trade.market_id || 'Unknown Market'}
                        </span>
                        <span style={{
                          padding: '4px 8px',
                          borderRadius: 6,
                          fontSize: 11,
                          fontWeight: 700,
                          background: `${sportInfo.color}20`,
                          color: sportInfo.color,
                          flexShrink: 0
                        }}>
                          {sportInfo.emoji} {sportInfo.name}
                        </span>
                      </div>

                      {/* Trade details grid */}
                      <div style={{ 
                        display: 'grid',
                        gridTemplateColumns: 'repeat(2, 1fr)',
                        gap: 12,
                        fontSize: 13,
                        marginBottom: 12
                      }}>
                        <div>
                          <span style={{ color: 'var(--text-tertiary)' }}>Side: </span>
                          <span style={{ 
                            fontWeight: 700,
                            color: trade.side === 'YES' ? '#10B981' : '#EF4444'
                          }}>
                            {trade.side || 'BUY'}
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
                        <div>
                          <span style={{ color: 'var(--text-tertiary)' }}>Size: </span>
                          <strong>${(trade.position_size || 100).toFixed(0)}</strong>
                        </div>
                        <div>
                          <span style={{ color: 'var(--text-tertiary)' }}>Strategy: </span>
                          <strong>{trade.strategy || 'Manual'}</strong>
                        </div>
                      </div>

                      {/* P&L footer */}
                      <div style={{
                        paddingTop: 12,
                        borderTop: '1px solid var(--border)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center'
                      }}>
                        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                          P&L:
                        </span>
                        <span style={{
                          fontSize: 20,
                          fontWeight: 800,
                          color: isOpen ? 'var(--text-secondary)' : accentColor
                        }}>
                          {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default Trades
