import { useState } from 'react'

const SECTIONS = [
  { id: 'home', label: '🏠 Home', url: 'https://polymarket.com' },
  { id: 'sports', label: '🏆 Sports', url: 'https://polymarket.com/sports' },
  { id: 'crypto', label: '₿ Crypto', url: 'https://polymarket.com/crypto' },
  { id: 'politics', label: '🏛️ Politics', url: 'https://polymarket.com/politics' },
  { id: 'culture', label: '🎬 Culture', url: 'https://polymarket.com/culture' },
  { id: 'leaderboard', label: '🏆 Leaderboard', url: 'https://polymarket.com/leaderboard' },
]

export default function PolymarketEmbed() {
  const [activeSection, setActiveSection] = useState('home')
  const [customUrl, setCustomUrl] = useState('')
  
  const currentUrl = customUrl || SECTIONS.find(s => s.id === activeSection)?.url || 'https://polymarket.com'
  
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', backgroundColor: '#0a0a0f' }}>
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
          key={currentUrl}
          src={currentUrl}
          title="Polymarket"
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
            minHeight: 'calc(100vh - 220px)',
          }}
          sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-top-navigation allow-popups-to-escape-sandbox"
          referrerPolicy="no-referrer"
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
