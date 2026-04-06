import { useState, useEffect } from 'react'
import './Explorer.css'

export default function Explorer() {
  const [markets, setMarkets] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [nextCursor, setNextCursor] = useState('MA==')
  const [hasMore, setHasMore] = useState(true)
  const [selectedMarket, setSelectedMarket] = useState(null)
  const [marketDetail, setMarketDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const categories = [
    { label: 'All', value: '' },
    { label: '🌡️ Weather', value: 'weather' },
    { label: '⚽ Sports', value: 'sports' },
    { label: '₿ Crypto', value: 'crypto' },
    { label: '🏛️ Politics', value: 'politics' },
    { label: '💼 Economics', value: 'economics' },
  ]

  const fetchMarkets = async (reset = false) => {
    setLoading(true)
    try {
      const cursor = reset ? 'MA==' : nextCursor
      const params = new URLSearchParams({
        limit: '50',
        cursor: cursor,
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
    fetchMarkets(true)
  }, [search, category])

  useEffect(() => {
    if (selectedMarket) {
      const conditionId = selectedMarket.condition_id || selectedMarket.id
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
    return `${(price * 100).toFixed(0)}¢`
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
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  return (
    <div className="explorer-page">
      <div className="explorer-header">
        <h1>🔍 Polymarket Explorer</h1>
        <p className="subtitle">Browse all prediction markets (proxy bypasses ISP blocks)</p>
      </div>

      {/* Search & Filters */}
      <div className="explorer-controls">
        <input
          type="text"
          placeholder="Search markets..."
          value={search}
          onChange={handleSearchChange}
          className="search-input"
        />
        
        <div className="category-chips">
          {categories.map(cat => (
            <button
              key={cat.value}
              className={`category-chip ${category === cat.value ? 'active' : ''}`}
              onClick={() => handleCategoryChange(cat.value)}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Market Grid */}
      <div className="markets-grid">
        {markets.map((market, idx) => {
          const tokens = market.tokens || []
          const yesPrice = tokens[0]?.price || 0.5
          const noPrice = tokens[1]?.price || 0.5
          const volume = market.volume || 0
          const endDate = market.end_date_iso || market.endDate
          
          return (
            <div 
              key={market.condition_id || market.id || idx} 
              className="market-card"
              onClick={() => setSelectedMarket(market)}
            >
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

      {/* Load More */}
      {hasMore && !loading && (
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

      {/* Market Detail Modal */}
      {selectedMarket && (
        <div className="modal-overlay" onClick={() => setSelectedMarket(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{selectedMarket.question || selectedMarket.title}</h2>
              <button className="close-btn" onClick={() => setSelectedMarket(null)}>✕</button>
            </div>
            
            {detailLoading ? (
              <div className="modal-loading">
                <div className="spinner"></div>
                <p>Loading details...</p>
              </div>
            ) : marketDetail ? (
              <div className="modal-body">
                <div className="detail-section">
                  <h3>Market Info</h3>
                  <div className="detail-grid">
                    <div className="detail-item">
                      <span className="detail-label">Market ID:</span>
                      <span className="detail-value">{selectedMarket.condition_id || selectedMarket.id}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Volume:</span>
                      <span className="detail-value">{formatVolume(selectedMarket.volume)}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Liquidity:</span>
                      <span className="detail-value">{formatVolume(selectedMarket.liquidity)}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Resolution:</span>
                      <span className="detail-value">{formatDate(selectedMarket.end_date_iso || selectedMarket.endDate)}</span>
                    </div>
                  </div>
                </div>

                {marketDetail.order_book && (
                  <div className="detail-section">
                    <h3>Order Book</h3>
                    <div className="order-book">
                      <div className="book-column">
                        <h4>Bids ({marketDetail.order_book.bids?.length || 0})</h4>
                        {marketDetail.order_book.bids?.slice(0, 5).map((bid, idx) => (
                          <div key={idx} className="order-row bid">
                            <span>{formatPrice(bid.price)}</span>
                            <span>{bid.size || 0}</span>
                          </div>
                        ))}
                      </div>
                      <div className="book-column">
                        <h4>Asks ({marketDetail.order_book.asks?.length || 0})</h4>
                        {marketDetail.order_book.asks?.slice(0, 5).map((ask, idx) => (
                          <div key={idx} className="order-row ask">
                            <span>{formatPrice(ask.price)}</span>
                            <span>{ask.size || 0}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="modal-error">
                <p>Failed to load market details</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
