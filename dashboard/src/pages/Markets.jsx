import React, { useState, useEffect, Component } from 'react'
import { useLocation } from 'react-router-dom'
import axios from 'axios'
import './Explorer.css'
import './Intelligence.css'
import Explorer from './Explorer'
import Intelligence from './Intelligence'
import SportsIntelligence from './SportsIntelligence'
import METAR from './METAR'

// Error boundary to catch rendering crashes
class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { hasError: false, error: null }; }
  static getDerivedStateFromError(error) { return { hasError: true, error }; }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 32, textAlign: 'center', color: '#94a3b8' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
          <h3 style={{ color: '#fff', marginBottom: 8 }}>Something went wrong</h3>
          <p style={{ fontSize: 14, marginBottom: 16 }}>{this.state.error?.message || 'Component failed to load'}</p>
          <button onClick={() => this.setState({ hasError: false, error: null })} 
            style={{ padding: '10px 20px', background: '#7c3aed', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer' }}>
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}


const INDUSTRIES = [
  { id: 'all', label: 'All', icon: '📊', component: 'explorer' },
  { id: 'weather', label: 'Weather', icon: '🌡️', component: 'intelligence' },
  { id: 'sports', label: 'Sports', icon: '🏆', component: 'sports' },
  { id: 'crypto', label: 'Crypto', icon: '₿', component: 'explorer-filtered' },
  { id: 'politics', label: 'Politics', icon: '🏛️', component: 'explorer-filtered' },
  { id: 'entertainment', label: 'Entertainment', icon: '🎬', component: 'explorer-filtered' },
  { id: 'custom', label: 'Custom', icon: '⚙️', component: 'explorer-filtered' }
]

function Markets() {
  const location = useLocation()
  const [activeIndustry, setActiveIndustry] = useState('all')
  const [showActive, setShowActive] = useState(true)  // Active vs Resolved toggle
  const [markets, setMarkets] = useState([])
  const [loading, setLoading] = useState(false)

  // Parse route to pre-select industry (e.g., /markets/weather → weather tab)
  useEffect(() => {
    const path = location.pathname
    if (path.includes('/weather')) setActiveIndustry('weather')
    else if (path.includes('/sports')) setActiveIndustry('sports')
    else if (path.includes('/crypto')) setActiveIndustry('crypto')
    else if (path.includes('/politics')) setActiveIndustry('politics')
    else if (path.includes('/entertainment')) setActiveIndustry('entertainment')
    else setActiveIndustry('all')
  }, [location])

  const currentIndustry = INDUSTRIES.find(i => i.id === activeIndustry) || INDUSTRIES[0]

  const renderContent = () => {
    return (
      <ErrorBoundary key={currentIndustry.id}>
        
          {currentIndustry.component === 'explorer' && <Explorer activeOnly={showActive} />}
          {currentIndustry.component === 'intelligence' && (
            <>
              <Intelligence />
              <div style={{ marginTop: 24 }}><METAR /></div>
            </>
          )}
          {currentIndustry.component === 'sports' && <SportsIntelligence />}
          {currentIndustry.component === 'explorer-filtered' && <FilteredExplorer category={currentIndustry.id} activeOnly={showActive} />}
        
      </ErrorBoundary>
    );
  }

  return (
    <div className="markets-page">
      {/* Industry Tab Bar */}
      <div className="industry-tabs-container">
        <div className="industry-tabs">
          {INDUSTRIES.map(industry => (
            <button
              key={industry.id}
              className={`industry-tab ${activeIndustry === industry.id ? 'active' : ''}`}
              onClick={() => setActiveIndustry(industry.id)}
            >
              <span className="industry-icon">{industry.icon}</span>
              <span className="industry-label">{industry.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Active / Resolved Toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <button
          onClick={() => setShowActive(true)}
          style={{
            padding: '8px 16px', borderRadius: 20, border: 'none', cursor: 'pointer',
            fontWeight: 600, fontSize: 13, transition: 'all 0.2s',
            background: showActive ? '#10B981' : 'var(--bg-tertiary, #1a1a2e)',
            color: showActive ? '#fff' : '#94a3b8',
          }}
        >
          🟢 Active
        </button>
        <button
          onClick={() => setShowActive(false)}
          style={{
            padding: '8px 16px', borderRadius: 20, border: 'none', cursor: 'pointer',
            fontWeight: 600, fontSize: 13, transition: 'all 0.2s',
            background: !showActive ? '#6b7280' : 'var(--bg-tertiary, #1a1a2e)',
            color: !showActive ? '#fff' : '#94a3b8',
          }}
        >
          ⚫ Resolved
        </button>
      </div>

      {/* Content Area */}
      <div className="industry-content">
        {renderContent()}
      </div>
    </div>
  )
}

// Filtered Explorer for non-weather industries
function FilteredExplorer({ category, activeOnly = true }) {
  const [markets, setMarkets] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [nextCursor, setNextCursor] = useState('MA==')
  const [hasMore, setHasMore] = useState(true)

  useEffect(() => {
    fetchMarkets(true)
  }, [category])

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
      if (category && category !== 'all' && category !== 'custom') {
        params.append('category', category)
      }

      const response = await axios.get(`/api/explorer/markets?${params}`)
      const data = response.data

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

  const categoryEmoji = {
    crypto: '₿',
    politics: '🏛️',
    entertainment: '🎬',
    custom: '⚙️'
  }

  if (loading && markets.length === 0) {
    return <div className="loading">Loading {category} markets...</div>
  }

  return (
    <div>
      <div className="page-header" style={{ marginTop: 0 }}>
        <h1 className="page-title">{categoryEmoji[category] || '📊'} {category.charAt(0).toUpperCase() + category.slice(1)} Markets</h1>
        <p className="page-subtitle">{markets.length} active markets</p>
      </div>

      {/* Search */}
      <div style={{ marginBottom: 20 }}>
        <input
          type="text"
          placeholder={`Search ${category} markets...`}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && fetchMarkets(true)}
          className="search-input"
          style={{
            width: '100%',
            padding: '12px 16px',
            borderRadius: 10,
            border: '1px solid var(--border)',
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            fontSize: 14
          }}
        />
      </div>

      {/* Markets Grid */}
      <div className="markets-grid">
        {markets.map((market, idx) => {
          const yesPrice = market._yes_price || 0.5
          const noPrice = market._no_price || 0.5
          const volume = market._volume || 0
          
          return (
            <div key={market.condition_id || market.id || idx} className="market-card">
              <div className="market-header">
                <span className="category-badge">{categoryEmoji[category] || '📊'} {category}</span>
                <span className="status-badge active">Active</span>
              </div>
              
              <div className="market-question">{market.question || market.title}</div>
              
              <div className="market-prices">
                <div className="price-row">
                  <span className="price-label">YES</span>
                  <div className="price-bar-container">
                    <div className="price-bar yes-bar" style={{width: `${yesPrice * 100}%`}} />
                  </div>
                  <span className="price-value">{formatPrice(yesPrice)}</span>
                </div>
                <div className="price-row">
                  <span className="price-label">NO</span>
                  <div className="price-bar-container">
                    <div className="price-bar no-bar" style={{width: `${noPrice * 100}%`}} />
                  </div>
                  <span className="price-value">{formatPrice(noPrice)}</span>
                </div>
              </div>
              
              <div className="market-meta">
                <span>📊 {formatVolume(volume)}</span>
              </div>
              
              <button className="view-detail-btn">View Detail →</button>
            </div>
          )
        })}
      </div>

      {markets.length === 0 && !loading && (
        <div className="empty-state">
          <div className="empty-state-icon">{categoryEmoji[category] || '📊'}</div>
          <p>No {category} markets found</p>
          <p style={{fontSize: '14px', color: 'var(--text-secondary)', marginTop: '8px'}}>
            Try adjusting your search or check back later
          </p>
        </div>
      )}

      {hasMore && !loading && (
        <div className="load-more-container" style={{ textAlign: 'center', marginTop: 24 }}>
          <button 
            className="btn btn-primary"
            onClick={() => fetchMarkets(false)}
            style={{ padding: '12px 32px' }}
          >
            Load More
          </button>
        </div>
      )}

      {loading && markets.length > 0 && (
        <div className="loading-indicator">
          <div className="spinner"></div>
        </div>
      )}
    </div>
  )
}

export default Markets
