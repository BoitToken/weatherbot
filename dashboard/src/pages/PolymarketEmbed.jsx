import { useState, useEffect } from 'react'
import axios from 'axios'

const SECTIONS = [
  { id: 'home', label: '🏠 Home', url: 'https://polymarket.com' },
  { id: 'sports', label: '🏆 Sports', url: 'https://polymarket.com/sports' },
  { id: 'crypto', label: '₿ Crypto', url: 'https://polymarket.com/crypto' },
  { id: 'politics', label: '🏛️ Politics', url: 'https://polymarket.com/politics' },
  { id: 'culture', label: '🎬 Culture', url: 'https://polymarket.com/culture' },
  { id: 'leaderboard', label: '🏆 Leaderboard', url: 'https://polymarket.com/leaderboard' },
]

function ProxyView({ activeSection }) {
  const [markets, setMarkets] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchMarkets()
  }, [activeSection])

  const fetchMarkets = async () => {
    try {
      setLoading(true)
      let url = '/api/explorer/markets?limit=50&active_only=true'
      
      // Map sections to categories
      const categoryMap = {
        'sports': 'sports',
        'crypto': 'crypto', 
        'politics': 'politics',
        'culture': 'entertainment'
      }
      
      const category = categoryMap[activeSection]
      if (category) {
        url += `&category=${category}`
      }
      
      const res = await axios.get(url)
      setMarkets(res.data.data || [])
    } catch (error) {
      console.error('Failed to fetch markets:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatPrice = (priceStr) => {
    try {
      const prices = JSON.parse(priceStr)
      const yesPrice = parseFloat(prices[0]) * 100
      return `${yesPrice.toFixed(0)}%`
    } catch {
      return '—'
    }
  }

  const formatVolume = (vol) => {
    const num = parseFloat(vol) || 0
    if (num >= 1e9) return `$${(num / 1e9).toFixed(1)}B`
    if (num >= 1e6) return `$${(num / 1e6).toFixed(1)}M`
    if (num >= 1e3) return `$${(num / 1e3).toFixed(1)}K`
    return `$${num.toFixed(0)}`
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '48px', color: '#94a3b8' }}>
        <div style={{ fontSize: '32px', marginBottom: '16px' }}>⏳</div>
        <div>Loading markets...</div>
      </div>
    )
  }

  return (
    <div style={{ padding: '16px 0' }}>
      <div style={{
        background: 'rgba(251, 191, 36, 0.1)',
        border: '1px solid rgba(251, 191, 36, 0.2)',
        borderRadius: '12px',
        padding: '16px',
        marginBottom: '24px',
        color: '#fbbf24'
      }}>
        ⚠️ <strong>Iframe Blocked:</strong> Polymarket blocks iframe embedding. Showing proxy view from our API instead. 
        Click <a href="https://polymarket.com" target="_blank" rel="noopener noreferrer" style={{ color: '#fbbf24', textDecoration: 'underline' }}>here</a> to open in new tab.
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
        gap: '16px'
      }}>
        {(Array.isArray(markets) ? markets : []).map((market, idx) => {
          const question = market.question || ''
          const yesPrice = formatPrice(market.outcomePrices || '["0.5","0.5"]')
          const volume = formatVolume(market.volume)
          
          return (
            <div key={idx} style={{
              background: '#1a1a2e',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: '12px',
              padding: '16px',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(124, 58, 237, 0.4)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'}
            onClick={() => window.open(`https://polymarket.com/event/${market.id || market.slug}`, '_blank')}
            >
              <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', lineHeight: 1.4 }}>
                {question.length > 80 ? question.substring(0, 80) + '...' : question}
              </div>
              
              <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>YES</div>
                  <div style={{
                    padding: '8px',
                    background: 'rgba(16, 185, 129, 0.1)',
                    borderRadius: '8px',
                    textAlign: 'center',
                    fontSize: '16px',
                    fontWeight: 700,
                    color: '#10B981'
                  }}>
                    {yesPrice}
                  </div>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>NO</div>
                  <div style={{
                    padding: '8px',
                    background: 'rgba(239, 68, 68, 0.1)',
                    borderRadius: '8px',
                    textAlign: 'center',
                    fontSize: '16px',
                    fontWeight: 700,
                    color: '#EF4444'
                  }}>
                    {(100 - parseFloat(yesPrice)).toFixed(0)}%
                  </div>
                </div>
              </div>

              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '12px',
                color: '#94a3b8'
              }}>
                <span>Volume: {volume}</span>
                <span style={{ color: '#7c3aed' }}>View →</span>
              </div>
            </div>
          )
        })}
      </div>

      {markets.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px', color: '#94a3b8' }}>
          <div style={{ fontSize: '32px', marginBottom: '16px' }}>📭</div>
          <div>No markets found</div>
        </div>
      )}
    </div>
  )
}

export default function PolymarketEmbed() {
  const [activeSection, setActiveSection] = useState('home')
  const [customUrl, setCustomUrl] = useState('')
  const [iframeError, setIframeError] = useState(false)
  const [showProxy, setShowProxy] = useState(false)
  
  const currentUrl = customUrl || SECTIONS.find(s => s.id === activeSection)?.url || 'https://polymarket.com'
  
  // Auto-detect iframe block after 3 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      setShowProxy(true)
    }, 3000)
    return () => clearTimeout(timer)
  }, [])
  
  if (showProxy || iframeError) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div className="page-header" style={{ marginBottom: 0, paddingBottom: 8 }}>
          <h1 className="page-title">🔮 Polymarket</h1>
          <p className="page-subtitle">Browse prediction markets — all categories, all drill-downs</p>
        </div>
        
        {/* Section tabs */}
        <div style={{ 
          display: 'flex', gap: 8, padding: '8px 0', marginBottom: 8, 
          overflowX: 'auto', flexShrink: 0 
        }}>
          {SECTIONS.map(section => (
            <button
              key={section.id}
              onClick={() => { setActiveSection(section.id); setCustomUrl(''); }}
              style={{
                padding: '8px 16px',
                borderRadius: 20,
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: 13,
                whiteSpace: 'nowrap',
                background: activeSection === section.id ? '#7c3aed' : 'var(--bg-tertiary, #1a1a2e)',
                color: activeSection === section.id ? '#fff' : '#94a3b8',
                transition: 'all 0.2s',
              }}
            >
              {section.label}
            </button>
          ))}
        </div>

        <ProxyView activeSection={activeSection} />

        <div style={{ 
          textAlign: 'center', 
          padding: '12px 0 4px', 
          color: '#666', 
          fontSize: 12,
          flexShrink: 0,
        }}>
          Powered by Claude + OpenClaw + Actual Intelligence
        </div>
      </div>
    )
  }
  
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="page-header" style={{ marginBottom: 0, paddingBottom: 8 }}>
        <h1 className="page-title">🔮 Polymarket</h1>
        <p className="page-subtitle">Browse prediction markets — all categories, all drill-downs</p>
      </div>
      
      {/* Section tabs */}
      <div style={{ 
        display: 'flex', gap: 8, padding: '8px 0', marginBottom: 8, 
        overflowX: 'auto', flexShrink: 0 
      }}>
        {SECTIONS.map(section => (
          <button
            key={section.id}
            onClick={() => { setActiveSection(section.id); setCustomUrl(''); }}
            style={{
              padding: '8px 16px',
              borderRadius: 20,
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: 13,
              whiteSpace: 'nowrap',
              background: activeSection === section.id ? '#7c3aed' : 'var(--bg-tertiary, #1a1a2e)',
              color: activeSection === section.id ? '#fff' : '#94a3b8',
              transition: 'all 0.2s',
            }}
          >
            {section.label}
          </button>
        ))}
      </div>
      
      {/* URL bar */}
      <div style={{ 
        display: 'flex', gap: 8, marginBottom: 8, flexShrink: 0 
      }}>
        <input
          type="text"
          value={customUrl || currentUrl}
          onChange={(e) => setCustomUrl(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { /* URL already reactive */ } }}
          placeholder="Enter Polymarket URL..."
          style={{
            flex: 1,
            padding: '10px 14px',
            background: 'var(--bg-tertiary, #1a1a2e)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 8,
            color: '#fff',
            fontSize: 13,
            outline: 'none',
          }}
        />
        <button
          onClick={() => setCustomUrl('')}
          style={{
            padding: '10px 16px',
            background: '#7c3aed',
            border: 'none',
            borderRadius: 8,
            color: '#fff',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          Reset
        </button>
        <button
          onClick={() => setShowProxy(!showProxy)}
          style={{
            padding: '10px 16px',
            background: showProxy ? '#10B981' : '#1a1a2e',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 8,
            color: '#fff',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          {showProxy ? 'Try Iframe' : 'Proxy View'}
        </button>
      </div>
      
      {/* Iframe - takes remaining space */}
      <div style={{ 
        flex: 1, 
        borderRadius: 12, 
        overflow: 'hidden',
        border: '1px solid rgba(255,255,255,0.06)',
        minHeight: 'calc(100vh - 220px)',
      }}>
        <iframe
          src={currentUrl}
          title="Polymarket"
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
            minHeight: 'calc(100vh - 220px)',
          }}
          sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-top-navigation"
          referrerPolicy="no-referrer"
          onError={() => setIframeError(true)}
        />
      </div>
      
      <div style={{ 
        textAlign: 'center', 
        padding: '12px 0 4px', 
        color: '#666', 
        fontSize: 12,
        flexShrink: 0,
      }}>
        Powered by Claude + OpenClaw + Actual Intelligence
      </div>
    </div>
  )
}
