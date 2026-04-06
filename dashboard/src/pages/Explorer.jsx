import { useState, useEffect } from 'react'
import './Explorer.css'

export default function Explorer({ activeOnly = true }) {
  const [activeTab, setActiveTab] = useState('all') // 'all' or 'weather'
  const [markets, setMarkets] = useState([])
  const [weatherMarkets, setWeatherMarkets] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [nextCursor, setNextCursor] = useState('MA==')
  const [hasMore, setHasMore] = useState(true)
  const [selectedMarket, setSelectedMarket] = useState(null)
  const [marketDetail, setMarketDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const categories = [
    { label: 'All', value: '', icon: '📊' },
    { label: 'Weather', value: 'weather', icon: '🌡️' },
    { label: 'Sports', value: 'sports', icon: '⚽' },
    { label: 'Politics', value: 'politics', icon: '🏛️' },
    { label: 'Crypto', value: 'crypto', icon: '₿' },
    { label: 'Economics', value: 'economics', icon: '💼' },
    { label: 'Science', value: 'science', icon: '🔬' },
    { label: 'Entertainment', value: 'entertainment', icon: '🎬' },
  ]

  const fetchMarkets = async (reset = false) => {
    setLoading(true)
    try {
      const cursor = reset ? 'MA==' : nextCursor
      const params = new URLSearchParams({
        limit: '50',
        cursor: cursor,
        active_only: activeOnly ? 'true' : 'false',
      })
      if (search) params.append('search', search)
      if (category) params.append('category', category)

      const response = await fetch(`/api/explorer/markets?${params}`)
      const data = await response.json()

      if (reset) {
        setMarkets(data.data || [])
      } else {
        setMarkets(prev => [...prev, ...(data.data || [])])
      }
      
      setNextCursor(data.next_cursor || null)
      setHasMore(!!data.next_cursor && data.next_cursor !== cursor)
    } catch (error) {
      console.error('Failed to fetch markets:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchWeatherMarkets = async () => {
    try {
      const response = await fetch('/api/explorer/weather')
      const data = await response.json()
      setWeatherMarkets(data.data || [])
    } catch (error) {
      console.error('Failed to fetch weather markets:', error)
    }
  }

  const loadMarketDetail = async (conditionId) => {
    setDetailLoading(true)
    try {
      const response = await fetch(`/api/explorer/market/${conditionId}`)
      const data = await response.json()
      setMarketDetail(data)
    } catch (error) {
      console.error('Failed to load market detail:', error)
      setMarketDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'all') {
      fetchMarkets(true)
    } else {
      fetchWeatherMarkets()
    }
  }, [search, category, activeTab, activeOnly])

  useEffect(() => {
    if (selectedMarket) {
      const conditionId = selectedMarket.condition_id || selectedMarket.market_id || selectedMarket.id
      if (conditionId) {
        loadMarketDetail(conditionId)
      }
    }
  }, [selectedMarket])

  const handleSearchChange = (e) => {
    setSearch(e.target.value)
  }

  const handleCategoryChange = (value) => {
    setCategory(value)
  }

  const handleLoadMore = () => {
    fetchMarkets(false)
  }

  const formatPrice = (price) => {
    if (!price) return '50¢'
    const cents = Math.round(price * 100)
    return `${cents}¢`
  }

  const formatVolume = (volume) => {
    if (!volume) return '$0'
    if (volume >= 1000000) return `$${(volume / 1000000).toFixed(1)}M`
    if (volume >= 1000) return `$${(volume / 1000).toFixed(1)}K`
    return `$${volume.toFixed(0)}`
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Unknown'
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  const getCategoryBadge = (cat) => {
    const found = categories.find(c => c.value === cat)
    if (!found) return { icon: '📊', label: 'Other' }
    return found
  }

  const isResolved = (market) => {
    const yesPrice = market._yes_price || market.yes_price || 0
    const noPrice = market._no_price || market.no_price || 0
    return (yesPrice === 1 && noPrice === 0) || (yesPrice === 0 && noPrice === 1)
  }

  return (
    <div className="explorer-page">
      <div className="explorer-header">
        <h1>🔍 Market Explorer</h1>
        <p className="subtitle">Browse prediction markets with intelligent filtering</p>
      </div>

      {/* Tabs */}
      <div className="explorer-tabs">
        <button
          className={`tab-btn ${activeTab === 'all' ? 'active' : ''}`}
          onClick={() => setActiveTab('all')}
        >
          📊 All Markets
        </button>
        <button
          className={`tab-btn ${activeTab === 'weather' ? 'active' : ''}`}
          onClick={() => setActiveTab('weather')}
        >
          🌡️ Our Weather Markets
        </button>
      </div>

      {/* Search & Filters (only for All Markets tab) */}
      {activeTab === 'all' && (
        <>
          <div className="explorer-controls">
            <input
              type="text"
              placeholder="Search markets..."
              value={search}
              onChange={handleSearchChange}
              className="search-input"
            />
          </div>
          
          <div className="category-chips">
            {categories.map(cat => (
              <button
                key={cat.value}
                className={`category-chip ${category === cat.value ? 'active' : ''}`}
                onClick={() => handleCategoryChange(cat.value)}
              >
                {cat.icon} {cat.label}
              </button>
            ))}
          </div>
        </>
      )}

      {/* Market Grid - All Markets */}
      {activeTab === 'all' && (
        <div className="markets-grid">
          {markets.map((market, idx) => {
            const yesPrice = market._yes_price || 0.5
            const noPrice = market._no_price || 0.5
            const volume = market._volume || 0
            const endDate = market.end_date_iso || market.endDate
            const cat = market._category || 'other'
            const badge = getCategoryBadge(cat)
            const resolved = isResolved(market)
            
            return (
              <div 
                key={market.condition_id || market.id || idx} 
                className="market-card"
                onClick={() => setSelectedMarket(market)}
              >
                <div className="market-header">
                  <span className="category-badge">{badge.icon} {badge.label}</span>
                  {resolved ? (
                    <span className="status-badge resolved">Resolved</span>
                  ) : (
                    <span className="status-badge active">Active</span>
                  )}
                </div>
                
                <div className="market-question">{market.question || market.title}</div>
                
                <div className="market-prices">
                  <div className="price-row">
                    <span className="price-label">YES</span>
                    <div className="price-bar-container">
                      <div 
                        className="price-bar yes-bar" 
                        style={{width: `${yesPrice * 100}%`}}
                      />
                    </div>
                    <span className="price-value">{formatPrice(yesPrice)}</span>
                  </div>
                  <div className="price-row">
                    <span className="price-label">NO</span>
                    <div className="price-bar-container">
                      <div 
                        className="price-bar no-bar" 
                        style={{width: `${noPrice * 100}%`}}
                      />
                    </div>
                    <span className="price-value">{formatPrice(noPrice)}</span>
                  </div>
                </div>
                
                <div className="market-meta">
                  <span>📊 {formatVolume(volume)}</span>
                  <span>📅 {formatDate(endDate)}</span>
                </div>
                
                <button className="view-detail-btn">View Detail →</button>
              </div>
            )
          })}
        </div>
      )}

      {/* Weather Markets Tab */}
      {activeTab === 'weather' && (
        <div className="weather-markets-grid">
          {weatherMarkets.length === 0 ? (
            <div className="empty-state">
              <p>No weather markets tracked yet</p>
              <p style={{fontSize: '14px', color: 'var(--text-secondary)', marginTop: '8px'}}>
                Markets will appear here once the bot identifies and tracks weather prediction markets
              </p>
            </div>
          ) : (
            weatherMarkets.map((market, idx) => (
              <div key={market.market_id || idx} className="weather-market-card">
                <div className="weather-market-header">
                  <h3>{market.title}</h3>
                  <span className={`status-badge ${market.active ? 'active' : 'inactive'}`}>
                    {market.active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                
                <div className="weather-market-info">
                  <div className="info-row">
                    <span className="info-label">🏙️ City:</span>
                    <span className="info-value">{market.city}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">📡 Station:</span>
                    <span className="info-value">{market.station_icao}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">🎯 Threshold:</span>
                    <span className="info-value">
                      {market.threshold_type} {market.threshold_value}{market.threshold_unit}
                    </span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">📅 Resolution:</span>
                    <span className="info-value">{formatDate(market.resolution_date)}</span>
                  </div>
                </div>
                
                <div className="market-prices">
                  <div className="price-row">
                    <span className="price-label">YES</span>
                    <div className="price-bar-container">
                      <div 
                        className="price-bar yes-bar" 
                        style={{width: `${(market.yes_price || 0.5) * 100}%`}}
                      />
                    </div>
                    <span className="price-value">{formatPrice(market.yes_price)}</span>
                  </div>
                  <div className="price-row">
                    <span className="price-label">NO</span>
                    <div className="price-bar-container">
                      <div 
                        className="price-bar no-bar" 
                        style={{width: `${(market.no_price || 0.5) * 100}%`}}
                      />
                    </div>
                    <span className="price-value">{formatPrice(market.no_price)}</span>
                  </div>
                </div>
                
                <div className="market-meta">
                  <span>📊 {formatVolume(market.volume_usd)}</span>
                  <span>💧 {formatVolume(market.liquidity_usd)} liquidity</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Load More */}
      {activeTab === 'all' && hasMore && !loading && (
        <div className="load-more-container">
          <button className="load-more-btn" onClick={handleLoadMore}>
            Load More Markets
          </button>
        </div>
      )}

      {loading && (
        <div className="loading-indicator">
          <div className="spinner"></div>
          <p>Loading markets...</p>
        </div>
      )}

      {/* Market Detail Modal — Enhanced */}
      {selectedMarket && (() => {
        const m = selectedMarket
        const yesPrice = m._yes_price || m.tokens?.[0]?.price || 0.5
        const noPrice = m._no_price || m.tokens?.[1]?.price || 0.5
        const cat = m._category || m.tags?.[0] || 'Other'
        const isActive = m.active && !m.closed
        const desc = m.description || ''
        const vol = m._volume || m.volume || 0
        const liq = m.liquidity || 0
        const slug = m.market_slug || ''
        const img = m.image || m.icon || ''
        const endDate = m.end_date_iso || m.endDate || ''
        const tags = m.tags || []
        
        return (
        <div className="modal-overlay" onClick={() => setSelectedMarket(null)}>
          <div className="modal-content modal-enhanced" onClick={(e) => e.stopPropagation()}>
            {/* Header with image */}
            <div className="modal-header-enhanced">
              {img && <img src={img} alt="" style={{ width: 48, height: 48, borderRadius: 12, objectFit: 'cover', flexShrink: 0 }} onError={e => e.target.style.display='none'} />}
              <div style={{ flex: 1, minWidth: 0 }}>
                <h2 style={{ fontSize: '1.1rem', margin: 0, lineHeight: 1.3 }}>{m.question || m.title}</h2>
                <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                  <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: isActive ? 'rgba(16,185,129,0.15)' : 'rgba(107,114,128,0.2)', color: isActive ? '#10B981' : '#6b7280' }}>{isActive ? '🟢 Active' : '⚫ Resolved'}</span>
                  <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, background: 'rgba(124,58,237,0.15)', color: '#a78bfa' }}>{cat}</span>
                </div>
              </div>
              <button className="close-btn" onClick={() => setSelectedMarket(null)}>✕</button>
            </div>

            <div className="modal-body">
              {/* YES / NO Price Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 20 }}>
                <div style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 12, padding: 16, textAlign: 'center' }}>
                  <div style={{ fontSize: 12, color: '#10B981', fontWeight: 600, marginBottom: 4 }}>YES</div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: '#10B981' }}>{Math.round(yesPrice * 100)}¢</div>
                  <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>{(yesPrice * 100).toFixed(1)}% implied</div>
                </div>
                <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 12, padding: 16, textAlign: 'center' }}>
                  <div style={{ fontSize: 12, color: '#EF4444', fontWeight: 600, marginBottom: 4 }}>NO</div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: '#EF4444' }}>{Math.round(noPrice * 100)}¢</div>
                  <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>{(noPrice * 100).toFixed(1)}% implied</div>
                </div>
              </div>

              {/* Key Metrics Row */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 20 }}>
                <div style={{ background: 'var(--bg-tertiary, #111)', borderRadius: 10, padding: 12, textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>Volume</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>{formatVolume(vol)}</div>
                </div>
                <div style={{ background: 'var(--bg-tertiary, #111)', borderRadius: 10, padding: 12, textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>Liquidity</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>{formatVolume(liq)}</div>
                </div>
                <div style={{ background: 'var(--bg-tertiary, #111)', borderRadius: 10, padding: 12, textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>Resolves</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#fff' }}>{endDate ? new Date(endDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'TBD'}</div>
                </div>
              </div>

              {/* Description */}
              {desc && (
                <div style={{ marginBottom: 20 }}>
                  <h4 style={{ fontSize: 13, color: '#9ca3af', fontWeight: 600, marginBottom: 6 }}>Description</h4>
                  <p style={{ fontSize: 13, color: '#d1d5db', lineHeight: 1.5, margin: 0, maxHeight: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}>{desc.slice(0, 400)}{desc.length > 400 ? '...' : ''}</p>
                </div>
              )}

              {/* Tags */}
              {tags.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <h4 style={{ fontSize: 13, color: '#9ca3af', fontWeight: 600, marginBottom: 6 }}>Tags</h4>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {tags.filter(t => t !== 'All').slice(0, 8).map((tag, i) => (
                      <span key={i} style={{ padding: '3px 10px', borderRadius: 12, fontSize: 11, background: 'rgba(124,58,237,0.1)', color: '#a78bfa', border: '1px solid rgba(124,58,237,0.2)' }}>{tag}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Order Book (if loaded) */}
              {marketDetail?.order_book && (
                <div style={{ marginBottom: 20 }}>
                  <h4 style={{ fontSize: 13, color: '#9ca3af', fontWeight: 600, marginBottom: 8 }}>Order Book</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    <div>
                      <div style={{ fontSize: 11, color: '#10B981', fontWeight: 600, marginBottom: 4 }}>Bids ({marketDetail.order_book.bids?.length || 0})</div>
                      {(marketDetail.order_book.bids || []).slice(0, 5).map((bid, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 8px', background: 'rgba(16,185,129,0.05)', borderRadius: 6, marginBottom: 3, fontSize: 12 }}>
                          <span style={{ color: '#10B981' }}>{formatPrice(bid.price)}</span>
                          <span style={{ color: '#6b7280' }}>{bid.size || 0}</span>
                        </div>
                      ))}
                      {(!marketDetail.order_book.bids || marketDetail.order_book.bids.length === 0) && <div style={{ fontSize: 12, color: '#4b5563' }}>No bids</div>}
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: '#EF4444', fontWeight: 600, marginBottom: 4 }}>Asks ({marketDetail.order_book.asks?.length || 0})</div>
                      {(marketDetail.order_book.asks || []).slice(0, 5).map((ask, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 8px', background: 'rgba(239,68,68,0.05)', borderRadius: 6, marginBottom: 3, fontSize: 12 }}>
                          <span style={{ color: '#EF4444' }}>{formatPrice(ask.price)}</span>
                          <span style={{ color: '#6b7280' }}>{ask.size || 0}</span>
                        </div>
                      ))}
                      {(!marketDetail.order_book.asks || marketDetail.order_book.asks.length === 0) && <div style={{ fontSize: 12, color: '#4b5563' }}>No asks</div>}
                    </div>
                  </div>
                </div>
              )}

              {/* Market ID (collapsed) */}
              <div style={{ marginBottom: 16 }}>
                <h4 style={{ fontSize: 13, color: '#9ca3af', fontWeight: 600, marginBottom: 4 }}>Market ID</h4>
                <div style={{ fontSize: 11, color: '#4b5563', wordBreak: 'break-all', background: 'var(--bg-tertiary, #111)', padding: 8, borderRadius: 8, fontFamily: 'monospace' }}>{m.condition_id || m.id}</div>
              </div>

              {/* Action: Open on Polymarket */}
              {slug && (
                <a href={`https://polymarket.com/market/${slug}`} target="_blank" rel="noopener noreferrer"
                  style={{ display: 'block', textAlign: 'center', padding: '14px 20px', background: 'linear-gradient(135deg, #7c3aed, #6d28d9)', borderRadius: 12, color: '#fff', fontWeight: 700, fontSize: 14, textDecoration: 'none', marginTop: 8 }}>
                  Open on Polymarket →
                </a>
              )}
            </div>
          </div>
        </div>
        )
      })()}
    </div>
  )
}
