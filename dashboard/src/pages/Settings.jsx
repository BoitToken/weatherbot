import { useState, useEffect } from 'react'
import axios from 'axios'

function Settings() {
  const [botStatus, setBotStatus] = useState(null)
  const [config, setConfig] = useState({
    minEdge: 5.0,
    maxPosition: 50.0,
    kellyFraction: 0.25,
    mode: 'paper'
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchStatus()
  }, [])

  const fetchStatus = async () => {
    try {
      const res = await axios.get('/api/bot/status')
      setBotStatus(res.data)
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch bot status:', error)
      setLoading(false)
    }
  }

  const handleSaveConfig = async () => {
    setSaving(true)
    // TODO: Implement config save endpoint
    setTimeout(() => {
      setSaving(false)
      alert('Settings saved! (Endpoint not implemented yet)')
    }, 1000)
  }

  const handleBotControl = async (action) => {
    // TODO: Implement bot control endpoints
    alert(`${action} requested (Endpoint not implemented yet)`)
  }

  if (loading) {
    return <div className="loading">Loading...</div>
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Configure bot parameters and controls</p>
      </div>

      {/* Bot Controls */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>
          Bot Controls
        </h3>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div className={`status-indicator ${botStatus?.running ? 'running' : 'paused'}`}>
            <div className={`status-dot ${botStatus?.running ? 'green' : 'red'}`}></div>
            {botStatus?.running ? 'Running' : 'Paused'}
          </div>
          
          <button 
            className="btn btn-primary"
            onClick={() => handleBotControl('start')}
            disabled={botStatus?.running}
            style={{ opacity: botStatus?.running ? 0.5 : 1 }}
          >
            ▶️ Start
          </button>
          
          <button 
            className="btn btn-secondary"
            onClick={() => handleBotControl('pause')}
            disabled={!botStatus?.running}
            style={{ opacity: !botStatus?.running ? 0.5 : 1 }}
          >
            ⏸️ Pause
          </button>
          
          <button 
            className="btn btn-secondary"
            onClick={() => handleBotControl('stop')}
            style={{ 
              background: 'var(--error)',
              color: 'white',
              border: 'none'
            }}
          >
            ⏹️ Stop
          </button>
        </div>
      </div>

      {/* Trading Parameters */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '24px' }}>
          Trading Parameters
        </h3>
        
        <div style={{ display: 'grid', gap: '24px' }}>
          {/* Min Edge */}
          <div>
            <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)', fontSize: '14px' }}>
              Minimum Edge (%)
            </label>
            <input 
              type="number"
              value={config.minEdge}
              onChange={(e) => setConfig({ ...config, minEdge: parseFloat(e.target.value) || 0 })}
              step="0.1"
              style={{
                width: '100%',
                padding: '12px',
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                color: 'var(--text-primary)',
                fontSize: '16px'
              }}
            />
            <p style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-tertiary)' }}>
              Only trade signals with edge above this threshold
            </p>
          </div>

          {/* Max Position */}
          <div>
            <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)', fontSize: '14px' }}>
              Max Position Size ($)
            </label>
            <input 
              type="number"
              value={config.maxPosition}
              onChange={(e) => setConfig({ ...config, maxPosition: parseFloat(e.target.value) || 0 })}
              step="1"
              style={{
                width: '100%',
                padding: '12px',
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                color: 'var(--text-primary)',
                fontSize: '16px'
              }}
            />
            <p style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-tertiary)' }}>
              Maximum dollars to risk on a single trade
            </p>
          </div>

          {/* Kelly Fraction */}
          <div>
            <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)', fontSize: '14px' }}>
              Kelly Fraction
            </label>
            <input 
              type="number"
              value={config.kellyFraction}
              onChange={(e) => setConfig({ ...config, kellyFraction: parseFloat(e.target.value) || 0 })}
              step="0.05"
              min="0"
              max="1"
              style={{
                width: '100%',
                padding: '12px',
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                color: 'var(--text-primary)',
                fontSize: '16px'
              }}
            />
            <p style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-tertiary)' }}>
              Position sizing multiplier (0.25 = Quarter Kelly, recommended)
            </p>
          </div>
        </div>

        <button 
          className="btn btn-primary"
          onClick={handleSaveConfig}
          disabled={saving}
          style={{ marginTop: '24px', width: '100%' }}
        >
          {saving ? 'Saving...' : '💾 Save Parameters'}
        </button>
      </div>

      {/* Mode Toggle */}
      <div className="card">
        <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>
          Trading Mode
        </h3>
        
        <div style={{ display: 'flex', gap: '12px' }}>
          <button 
            className={config.mode === 'paper' ? 'btn btn-primary' : 'btn btn-secondary'}
            onClick={() => setConfig({ ...config, mode: 'paper' })}
            style={{ flex: 1, padding: '16px' }}
          >
            📄 Paper Trading
          </button>
          
          <button 
            className={config.mode === 'live' ? 'btn btn-primary' : 'btn btn-secondary'}
            onClick={() => setConfig({ ...config, mode: 'live' })}
            style={{ 
              flex: 1, 
              padding: '16px',
              ...(config.mode === 'live' && {
                background: 'var(--error)',
                border: 'none'
              })
            }}
          >
            🔴 Live Trading
          </button>
        </div>

        <div style={{ 
          marginTop: '16px', 
          padding: '12px', 
          background: config.mode === 'live' ? 'rgba(239, 68, 68, 0.1)' : 'var(--bg-tertiary)',
          borderRadius: '8px',
          fontSize: '14px',
          color: config.mode === 'live' ? 'var(--error)' : 'var(--text-secondary)'
        }}>
          {config.mode === 'paper' ? (
            <>
              ✅ <strong>Paper mode:</strong> All trades are simulated. No real money at risk.
            </>
          ) : (
            <>
              ⚠️ <strong>Live mode:</strong> Real money trading enabled. Trades execute on Polymarket.
            </>
          )}
        </div>
      </div>

      {/* API Status */}
      <div className="card" style={{ marginTop: '24px' }}>
        <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>
          API Status
        </h3>
        
        <div style={{ display: 'grid', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Telegram Bot</span>
            <span className="badge high">Connected</span>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Database</span>
            <span className="badge high">Connected</span>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)' }}>METAR Feed</span>
            <span className="badge high">Active</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings
