import { useState, useEffect } from 'react'
import axios from 'axios'

const CATEGORIES = [
  { id: 'all', label: '🔮 All', tag: null },
  { id: 'sports', label: '🏆 Sports', tag: 'sports' },
  { id: 'crypto', label: '₿ Crypto', tag: 'crypto' },
  { id: 'politics', label: '🏛️ Politics', tag: 'politics' },
  { id: 'culture', label: '🎬 Culture', tag: 'culture' },
  { id: 'economics', label: '📈 Economics', tag: 'economics' },
  { id: 'tech', label: '💻 Tech', tag: 'tech' },
  { id: 'weather', label: '🌤️ Weather', tag: 'weather' },
]

// Polymarket color scheme
const COLORS = {
  bg: '#15191d',
  card: '#1c2127',
  cardHover: '#232a31',
  yesGreen: '#00c853',
  noRed: '#ff3d00',
  accent: '#4c82fb',
  textPrimary: '#ffffff',
  textSecondary: '#858d92',
  border: 'rgba(255,255,255,0.08)',
}

function formatVolume(v) {
  if (v >= 1e9) return `$${(v/1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v/1e6).toFixed(1)}M`
  if (v >= 1e3) return `$${(v/1e3).toFixed(1)}K`
  return `$${v.toFixed(0)}`
}

function ProbabilityBar({ yesPrice }) {
  return (
    <div style={{ 
      height: 6, 
      borderRadius: 3, 
      background: COLORS.border,
      position: 'relative', 
      overflow: 'hidden',
      marginTop: 4,
    }}>
      <div style={{
        position: 'absolute', 
        left: 0, 
        top: 0, 
        bottom: 0,
        width: `${yesPrice * 100}%`,
        background: `linear-gradient(90deg, ${COLORS.yesGreen}, #00e676)`,
        borderRadius: 3,
        transition: 'width 0.3s ease',
      }} />
    </div>
  )
}

function MarketCard({ market, onClick }) {
  const yesPrice = market.yes_price || 0.5
  const noPrice = market.no_price || 0.5
  const volume = market.volume || 0

  return (
    <div 
      onClick={onClick}
      style={{
        background: COLORS.card,
        border: `1px solid ${COLORS.border}`,
        borderRadius: 12,
        padding: 16,
        cursor: 'pointer',
        transition: 'all 0.2s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = COLORS.cardHover}
      onMouseLeave={e => e.currentTarget.style.background = COLORS.card}
    >
      {market.image && (
        <img 
          src={market.image} 
          alt="" 
          style={{ 
            width: '100%', 
            height: 140, 
            objectFit: 'cover', 
            borderRadius: 8, 
            marginBottom: 12 
          }} 
        />
      )}
      
      <div style={{ 
        fontSize: 14, 
        fontWeight: 600, 
        marginBottom: 12, 
        lineHeight: 1.4,
        color: COLORS.textPrimary,
      }}>
        {market.question}
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button style={{
          flex: 1, 
          padding: '10px 12px', 
          borderRadius: 8,
          background: 'rgba(0, 200, 83, 0.1)',
          border: `1px solid rgba(0, 200, 83, 0.2)`,
          color: COLORS.yesGreen, 
          fontWeight: 700, 
          fontSize: 15,
          cursor: 'pointer',
        }}>
          Yes {Math.round(yesPrice * 100)}¢
        </button>
        <button style={{
          flex: 1, 
          padding: '10px 12px', 
          borderRadius: 8,
          background: 'rgba(255, 61, 0, 0.1)',
          border: `1px solid rgba(255, 61, 0, 0.2)`,
          color: COLORS.noRed, 
          fontWeight: 700, 
          fontSize: 15,
          cursor: 'pointer',
        }}>
          No {Math.round(noPrice * 100)}¢
        </button>
      </div>

      <ProbabilityBar yesPrice={yesPrice} />

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: 12,
        color: COLORS.textSecondary,
        marginTop: 12,
      }}>
        <span>Vol: {formatVolume(volume)}</span>
        {market.endDate && (
          <span>Ends: {new Date(market.endDate).toLocaleDateString()}</span>
        )}
      </div>
    </div>
  )
}

function EventCard({ event, onClick }) {
  const topMarkets = (event.markets || []).slice(0, 2)
  
  return (
    <div 
      onClick={onClick}
      style={{
        background: COLORS.card,
        border: `1px solid ${COLORS.border}`,
        borderRadius: 12,
        padding: 16,
        cursor: 'pointer',
        transition: 'all 0.2s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = COLORS.cardHover}
      onMouseLeave={e => e.currentTarget.style.background = COLORS.card}
    >
      {event.image && (
        <img 
          src={event.image} 
          alt="" 
          style={{ 
            width: '100%', 
            height: 160, 
            objectFit: 'cover', 
            borderRadius: 8, 
            marginBottom: 12 
          }} 
        />
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        {event.icon && (
          <img src={event.icon} alt="" style={{ width: 32, height: 32, borderRadius: '50%' }} />
        )}
        <div style={{ flex: 1 }}>
          <div style={{ 
            fontSize: 16, 
            fontWeight: 700, 
            marginBottom: 4,
            color: COLORS.textPrimary,
          }}>
            {event.title}
          </div>
          <div style={{ fontSize: 12, color: COLORS.textSecondary }}>
            {formatVolume(event.volume)} Vol · {event.market_count} markets
          </div>
        </div>
      </div>

      {topMarkets.length > 0 && (
        <div style={{ display: 'grid', gap: 8, marginTop: 12 }}>
          {topMarkets.map((market, idx) => (
            <div 
              key={idx}
              style={{
                padding: 12,
                background: COLORS.bg,
                borderRadius: 8,
              }}
            >
              <div style={{ fontSize: 13, marginBottom: 8, color: COLORS.textPrimary }}>
                {market.question}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ 
                  flex: 1, 
                  padding: '6px 10px', 
                  background: 'rgba(0, 200, 83, 0.1)',
                  border: `1px solid rgba(0, 200, 83, 0.2)`,
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 600,
                  color: COLORS.yesGreen,
                  textAlign: 'center',
                }}>
                  {Math.round((market.yes_price || 0.5) * 100)}¢
                </div>
                <div style={{ 
                  flex: 1, 
                  padding: '6px 10px', 
                  background: 'rgba(255, 61, 0, 0.1)',
                  border: `1px solid rgba(255, 61, 0, 0.2)`,
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 600,
                  color: COLORS.noRed,
                  textAlign: 'center',
                }}>
                  {Math.round((market.no_price || 0.5) * 100)}¢
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function EventDetailView({ event, onBack }) {
  return (
    <div style={{ padding: '0 8px' }}>
      <button 
        onClick={onBack}
        style={{
          background: COLORS.card,
          border: `1px solid ${COLORS.border}`,
          borderRadius: 8,
          padding: '8px 16px',
          color: COLORS.accent,
          cursor: 'pointer',
          fontSize: 14,
          fontWeight: 600,
          marginBottom: 20,
        }}
      >
        ← Back
      </button>

      {event.image && (
        <img 
          src={event.image} 
          alt="" 
          style={{ 
            width: '100%', 
            maxHeight: 300, 
            objectFit: 'cover', 
            borderRadius: 12, 
            marginBottom: 20 
          }} 
        />
      )}

      <h2 style={{ 
        fontSize: 24, 
        fontWeight: 700, 
        marginBottom: 12,
        color: COLORS.textPrimary,
      }}>
        {event.title}
      </h2>

      {event.description && (
        <p style={{ 
          fontSize: 14, 
          lineHeight: 1.6, 
          color: COLORS.textSecondary,
          marginBottom: 12,
        }}>
          {event.description}
        </p>
      )}

      <div style={{ 
        fontSize: 13, 
        color: COLORS.textSecondary,
        marginBottom: 24,
      }}>
        {formatVolume(event.volume)} total volume · {event.market_count} markets
      </div>

      <h3 style={{ 
        fontSize: 18, 
        fontWeight: 600, 
        marginBottom: 16,
        color: COLORS.textPrimary,
      }}>
        Markets in this event:
      </h3>

      <div style={{ display: 'grid', gap: 16 }}>
        {(event.markets || []).map((market, idx) => (
          <div 
            key={idx}
            style={{
              background: COLORS.card,
              border: `1px solid ${COLORS.border}`,
              borderRadius: 12,
              padding: 16,
            }}
          >
            <div style={{ 
              fontSize: 15, 
              fontWeight: 600, 
              marginBottom: 12,
              color: COLORS.textPrimary,
            }}>
              {market.question}
            </div>

            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: COLORS.textSecondary, marginBottom: 4 }}>
                  YES
                </div>
                <div style={{
                  padding: '10px 12px',
                  background: 'rgba(0, 200, 83, 0.1)',
                  border: `1px solid rgba(0, 200, 83, 0.2)`,
                  borderRadius: 8,
                  fontSize: 16,
                  fontWeight: 700,
                  color: COLORS.yesGreen,
                  textAlign: 'center',
                }}>
                  {Math.round((market.yes_price || 0.5) * 100)}¢
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: COLORS.textSecondary, marginBottom: 4 }}>
                  NO
                </div>
                <div style={{
                  padding: '10px 12px',
                  background: 'rgba(255, 61, 0, 0.1)',
                  border: `1px solid rgba(255, 61, 0, 0.2)`,
                  borderRadius: 8,
                  fontSize: 16,
                  fontWeight: 700,
                  color: COLORS.noRed,
                  textAlign: 'center',
                }}>
                  {Math.round((market.no_price || 0.5) * 100)}¢
                </div>
              </div>
            </div>

            <ProbabilityBar yesPrice={market.yes_price || 0.5} />

            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: 12,
              color: COLORS.textSecondary,
              marginTop: 12,
            }}>
              <span>Volume: {formatVolume(market.volume || 0)}</span>
              {market.endDate && (
                <span>Ends: {new Date(market.endDate).toLocaleDateString()}</span>
              )}
            </div>

            <a 
              href={`https://polymarket.com/event/${market.slug || market.id}`}
              target="_blank" 
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              style={{ 
                display: 'inline-block',
                marginTop: 12,
                color: COLORS.accent, 
                fontSize: 13, 
                textDecoration: 'none',
                fontWeight: 600,
              }}
            >
              View on Polymarket ↗
            </a>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function PolymarketEmbed() {
  const [category, setCategory] = useState('all')
  const [events, setEvents] = useState([])
  const [markets, setMarkets] = useState([])
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState('events')
  const [searchQuery, setSearchQuery] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Auto-refresh every 30s
    return () => clearInterval(interval)
  }, [category, viewMode])

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const tag = CATEGORIES.find(c => c.id === category)?.tag
      const params = new URLSearchParams({
        limit: viewMode === 'events' ? '20' : '50',
        active: 'true',
        closed: 'false',
        order: 'volume',
        ascending: 'false',
      })
      if (tag) params.append('tag', tag)

      const endpoint = viewMode === 'events' ? '/api/polymarket/events' : '/api/polymarket/markets'
      const res = await axios.get(`${endpoint}?${params.toString()}`)
      
      if (res.data.error) {
        setError(res.data.error)
        return
      }

      if (viewMode === 'events') {
        setEvents(res.data.events || [])
      } else {
        setMarkets(res.data.markets || [])
      }
    } catch (err) {
      console.error('Fetch error:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const filteredEvents = events.filter(e => 
    !searchQuery || 
    e.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (e.description || '').toLowerCase().includes(searchQuery.toLowerCase())
  )

  const filteredMarkets = markets.filter(m => 
    !searchQuery || 
    m.question.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (selectedEvent) {
    return (
      <div style={{ height: '100%', overflow: 'auto', padding: '16px 0' }}>
        <EventDetailView 
          event={selectedEvent} 
          onBack={() => setSelectedEvent(null)} 
        />
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '0 8px', marginBottom: 16 }}>
        <h1 style={{ 
          fontSize: 28, 
          fontWeight: 700, 
          marginBottom: 8,
          color: COLORS.textPrimary,
        }}>
          🔮 Polymarket
        </h1>
        <p style={{ 
          fontSize: 14, 
          color: COLORS.textSecondary,
          marginBottom: 16,
        }}>
          Live prediction markets powered by Gamma API
        </p>

        {/* Category tabs */}
        <div style={{ 
          display: 'flex', 
          gap: 8, 
          marginBottom: 16, 
          overflowX: 'auto',
          paddingBottom: 8,
        }}>
          {CATEGORIES.map(cat => (
            <button
              key={cat.id}
              onClick={() => { setCategory(cat.id); setSelectedEvent(null); }}
              style={{
                padding: '8px 16px',
                borderRadius: 20,
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: 13,
                whiteSpace: 'nowrap',
                background: category === cat.id ? COLORS.accent : COLORS.card,
                color: category === cat.id ? '#fff' : COLORS.textSecondary,
                transition: 'all 0.2s',
              }}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* View mode toggle & search */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search markets..."
            style={{
              flex: 1,
              padding: '10px 14px',
              background: COLORS.card,
              border: `1px solid ${COLORS.border}`,
              borderRadius: 8,
              color: COLORS.textPrimary,
              fontSize: 14,
              outline: 'none',
            }}
          />
          <button
            onClick={() => setViewMode(viewMode === 'events' ? 'markets' : 'events')}
            style={{
              padding: '10px 16px',
              background: COLORS.card,
              border: `1px solid ${COLORS.border}`,
              borderRadius: 8,
              color: COLORS.textPrimary,
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
              whiteSpace: 'nowrap',
            }}
          >
            {viewMode === 'events' ? '📊 Markets' : '🔥 Events'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          background: 'rgba(255, 61, 0, 0.1)',
          border: `1px solid rgba(255, 61, 0, 0.2)`,
          borderRadius: 8,
          padding: 12,
          margin: '0 8px 16px',
          color: COLORS.noRed,
          fontSize: 13,
        }}>
          ⚠️ Error: {error}
        </div>
      )}

      {/* Content area */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 8px' }}>
        {loading ? (
          <div style={{ 
            textAlign: 'center', 
            padding: 48, 
            color: COLORS.textSecondary 
          }}>
            <div style={{ fontSize: 32, marginBottom: 16 }}>⏳</div>
            <div>Loading {viewMode}...</div>
          </div>
        ) : viewMode === 'events' ? (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: 16,
            paddingBottom: 16,
          }}>
            {filteredEvents.map(event => (
              <EventCard 
                key={event.id} 
                event={event} 
                onClick={() => setSelectedEvent(event)}
              />
            ))}
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: 16,
            paddingBottom: 16,
          }}>
            {filteredMarkets.map(market => (
              <MarketCard 
                key={market.id} 
                market={market}
                onClick={() => window.open(`https://polymarket.com/event/${market.slug || market.id}`, '_blank')}
              />
            ))}
          </div>
        )}

        {!loading && (viewMode === 'events' ? filteredEvents : filteredMarkets).length === 0 && (
          <div style={{ 
            textAlign: 'center', 
            padding: 48, 
            color: COLORS.textSecondary 
          }}>
            <div style={{ fontSize: 32, marginBottom: 16 }}>📭</div>
            <div>No {viewMode} found</div>
          </div>
        )}
      </div>

      <div style={{ 
        textAlign: 'center', 
        padding: '12px 0', 
        color: COLORS.textSecondary, 
        fontSize: 12,
      }}>
        Powered by Polymarket Gamma API · Auto-refresh 30s
      </div>
    </div>
  )
}
