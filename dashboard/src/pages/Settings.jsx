import { useState, useEffect } from 'react'
import axios from 'axios'
import './Settings.css'

function Settings() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [walletBalance, setWalletBalance] = useState(null)
  const [settings, setSettings] = useState({
    // Position Sizing & Risk
    max_position_size: 50,
    max_portfolio_exposure: 15,
    kelly_fraction: 0.25,
    max_trades_per_city_per_day: 3,
    daily_loss_limit: 10,
    consecutive_loss_reducer_threshold: 3,
    consecutive_loss_reducer_pct: 25,
    min_hours_to_resolution: 2,
    
    // Signal Thresholds
    min_edge_auto_trade: 25,
    min_edge_alert: 15,
    min_confidence_sources: 2,
    max_spread_cents: 8,
    min_liquidity_multiple: 2,
    
    // Intelligence Gates
    gates_enabled: {
      data_convergence: true,
      multi_station: true,
      bucket_coherence: true,
      binary_arbitrage: true,
      liquidity_check: true,
      time_window: true,
      risk_manager: true,
      claude_confirmation: true,
    },
    
    // Notifications
    telegram_alerts: false,
    telegram_chat_id: '',
    alert_on_trade: true,
    alert_on_signal: true,
    alert_on_daily_summary: true,
    alert_on_weekly_review: true,
    alert_on_low_balance: true,
    alert_on_circuit_breaker: true,
    
    // Data Sources
    refresh_interval_min: 15,
    
    // Improvement Loop
    strategy_auto_proposals: true,
    weekly_review_day: 'Sunday',
    weekly_review_time: '09:00',
    auto_adjust_accuracy: true,
    proposal_approval_mode: 'require', // 'require' or 'auto'
  })
  
  const [mode, setMode] = useState('paper')
  const [showModeConfirm, setShowModeConfirm] = useState(false)
  const [pendingMode, setPendingMode] = useState(null)

  useEffect(() => {
    fetchSettings()
    fetchWalletBalance()
  }, [])

  const fetchSettings = async () => {
    try {
      const res = await axios.get('/api/settings')
      if (res.data.settings) {
        setSettings(prev => ({ ...prev, ...res.data.settings }))
      }
      setMode(res.data.mode || 'paper')
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch settings:', error)
      setLoading(false)
    }
  }

  const fetchWalletBalance = async () => {
    try {
      const res = await axios.get('/api/wallet/balance')
      setWalletBalance(res.data)
    } catch (error) {
      console.error('Failed to fetch wallet balance:', error)
    }
  }

  const handleSaveSettings = async () => {
    setSaving(true)
    try {
      await axios.post('/api/settings', settings)
      alert('✅ Settings saved successfully!')
    } catch (error) {
      console.error('Failed to save settings:', error)
      alert('❌ Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const handleModeChange = (newMode) => {
    if (newMode === 'live') {
      setPendingMode(newMode)
      setShowModeConfirm(true)
    } else {
      setMode(newMode)
    }
  }

  const confirmModeChange = () => {
    setMode(pendingMode)
    setShowModeConfirm(false)
    setPendingMode(null)
  }

  const handleEmergencyStop = async () => {
    if (confirm('🛑 EMERGENCY STOP: This will halt ALL trading immediately. Continue?')) {
      try {
        await axios.post('/api/bot/stop')
        alert('✅ Bot stopped successfully')
      } catch (error) {
        console.error('Emergency stop failed:', error)
        alert('❌ Failed to stop bot')
      }
    }
  }

  const handleBotControl = async (action) => {
    try {
      await axios.post(`/api/bot/${action}`)
      alert(`✅ Bot ${action}ed successfully`)
    } catch (error) {
      console.error(`Bot ${action} failed:`, error)
      alert(`❌ Failed to ${action} bot`)
    }
  }

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  const updateGate = (gate, value) => {
    setSettings(prev => ({
      ...prev,
      gates_enabled: { ...prev.gates_enabled, [gate]: value }
    }))
  }

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>Loading settings...</p>
      </div>
    )
  }

  const maskWallet = (addr) => {
    if (!addr) return 'Not configured'
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>⚙️ Settings</h1>
        <p className="subtitle">Configure trading parameters, risk controls, and intelligence gates</p>
      </div>

      {/* Section 1: Wallet & Account */}
      <div className="settings-section">
        <h2>💳 Wallet & Account</h2>
        <div className="settings-grid">
          <div className="setting-item">
            <label>Wallet Address</label>
            <div className="value-display">
              {maskWallet(walletBalance?.wallet)}
            </div>
          </div>
          
          <div className="setting-item">
            <label>USDC Balance</label>
            <div className="value-display balance">
              ${walletBalance?.usdc?.toFixed(2) || '0.00'}
            </div>
          </div>
          
          <div className="setting-item">
            <label>MATIC Balance</label>
            <div className="value-display balance">
              {walletBalance?.matic?.toFixed(4) || '0.0000'} MATIC
            </div>
          </div>
          
          <div className="setting-item">
            <label>Network</label>
            <div className="value-display">
              Polygon Mainnet
            </div>
          </div>
          
          <div className="setting-item full-width">
            <label>Connection Status</label>
            <div className="connection-status">
              {walletBalance && !walletBalance.error ? (
                <span className="status-badge connected">✅ Connected</span>
              ) : (
                <span className="status-badge disconnected">❌ Not Connected</span>
              )}
            </div>
          </div>
        </div>
        
        <button className="btn-secondary" onClick={fetchWalletBalance} style={{marginTop: '16px'}}>
          🔄 Refresh Balance
        </button>
      </div>

      {/* Section 2: Trading Mode */}
      <div className="settings-section mode-section">
        <h2>🎮 Trading Mode</h2>
        
        <div className="mode-toggle">
          <button 
            className={`mode-btn ${mode === 'paper' ? 'active paper' : ''}`}
            onClick={() => handleModeChange('paper')}
          >
            <span className="mode-icon">📄</span>
            <span className="mode-label">Paper Trading</span>
          </button>
          
          <button 
            className={`mode-btn ${mode === 'live' ? 'active live' : ''}`}
            onClick={() => handleModeChange('live')}
          >
            <span className="mode-icon">🔴</span>
            <span className="mode-label">Live Trading</span>
          </button>
        </div>
        
        <div className={`mode-info ${mode === 'live' ? 'warning' : ''}`}>
          {mode === 'paper' ? (
            <>
              ✅ <strong>Paper Mode:</strong> All trades are simulated. No real money at risk.
            </>
          ) : (
            <>
              ⚠️ <strong>Live Mode:</strong> Real USDC will be used. Ensure wallet is funded and you understand the risks.
            </>
          )}
        </div>
        
        <button className="emergency-stop-btn" onClick={handleEmergencyStop}>
          🛑 EMERGENCY STOP
        </button>
      </div>

      {/* Section 3: Position Sizing & Risk */}
      <div className="settings-section">
        <h2>💰 Position Sizing & Risk</h2>
        
        <div className="setting-control">
          <label>Max Position Size ($)</label>
          <input 
            type="range" 
            min="1" 
            max="500" 
            value={settings.max_position_size}
            onChange={(e) => updateSetting('max_position_size', parseInt(e.target.value))}
          />
          <span className="value">${settings.max_position_size}</span>
        </div>
        
        <div className="setting-control">
          <label>Max Portfolio Exposure (%)</label>
          <input 
            type="range" 
            min="1" 
            max="50" 
            value={settings.max_portfolio_exposure}
            onChange={(e) => updateSetting('max_portfolio_exposure', parseInt(e.target.value))}
          />
          <span className="value">{settings.max_portfolio_exposure}%</span>
        </div>
        
        <div className="setting-control">
          <label>
            Kelly Fraction
            <span className="help-text">Recommended: 0.25 (Quarter Kelly)</span>
          </label>
          <input 
            type="range" 
            min="0.05" 
            max="1.0" 
            step="0.05"
            value={settings.kelly_fraction}
            onChange={(e) => updateSetting('kelly_fraction', parseFloat(e.target.value))}
          />
          <span className="value">{settings.kelly_fraction.toFixed(2)}</span>
        </div>
        
        <div className="setting-control">
          <label>Max Trades Per City Per Day</label>
          <select 
            value={settings.max_trades_per_city_per_day}
            onChange={(e) => updateSetting('max_trades_per_city_per_day', parseInt(e.target.value))}
          >
            {[1,2,3,4,5,6,7,8,9,10].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        
        <div className="setting-control">
          <label>Daily Loss Limit (%)</label>
          <input 
            type="range" 
            min="1" 
            max="30" 
            value={settings.daily_loss_limit}
            onChange={(e) => updateSetting('daily_loss_limit', parseInt(e.target.value))}
          />
          <span className="value">{settings.daily_loss_limit}%</span>
        </div>
        
        <div className="setting-control">
          <label>Min Hours to Resolution</label>
          <input 
            type="range" 
            min="0" 
            max="24" 
            value={settings.min_hours_to_resolution}
            onChange={(e) => updateSetting('min_hours_to_resolution', parseInt(e.target.value))}
          />
          <span className="value">{settings.min_hours_to_resolution}h</span>
        </div>
      </div>

      {/* Section 4: Signal Thresholds */}
      <div className="settings-section">
        <h2>📊 Signal Thresholds</h2>
        
        <div className="setting-control">
          <label>Min Edge for Auto-Trade (%)</label>
          <input 
            type="range" 
            min="5" 
            max="50" 
            value={settings.min_edge_auto_trade}
            onChange={(e) => updateSetting('min_edge_auto_trade', parseInt(e.target.value))}
          />
          <span className="value">{settings.min_edge_auto_trade}%</span>
        </div>
        
        <div className="setting-control">
          <label>Min Edge for Alert (%)</label>
          <input 
            type="range" 
            min="1" 
            max="25" 
            value={settings.min_edge_alert}
            onChange={(e) => updateSetting('min_edge_alert', parseInt(e.target.value))}
          />
          <span className="value">{settings.min_edge_alert}%</span>
        </div>
        
        <div className="setting-control">
          <label>Min Confidence Sources Required</label>
          <select 
            value={settings.min_confidence_sources}
            onChange={(e) => updateSetting('min_confidence_sources', parseInt(e.target.value))}
          >
            {[1,2,3].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        
        <div className="setting-control">
          <label>Max Spread (¢)</label>
          <input 
            type="range" 
            min="1" 
            max="20" 
            value={settings.max_spread_cents}
            onChange={(e) => updateSetting('max_spread_cents', parseInt(e.target.value))}
          />
          <span className="value">{settings.max_spread_cents}¢</span>
        </div>
        
        <div className="setting-control">
          <label>Min Liquidity Multiple</label>
          <input 
            type="range" 
            min="1" 
            max="5" 
            value={settings.min_liquidity_multiple}
            onChange={(e) => updateSetting('min_liquidity_multiple', parseInt(e.target.value))}
          />
          <span className="value">{settings.min_liquidity_multiple}x</span>
        </div>
      </div>

      {/* Section 5: Intelligence Gates */}
      <div className="settings-section">
        <h2>🧠 Intelligence Gates</h2>
        <p className="section-description">Each gate validates different aspects of signal quality</p>
        
        <div className="gates-grid">
          <div className="gate-item">
            <div className="gate-header">
              <label>
                <input 
                  type="checkbox" 
                  checked={settings.gates_enabled.data_convergence}
                  onChange={(e) => updateGate('data_convergence', e.target.checked)}
                />
                Gate 1: Data Convergence
              </label>
            </div>
            <p className="gate-description">Validates METAR + Open-Meteo + Historical data agreement</p>
          </div>
          
          <div className="gate-item">
            <div className="gate-header">
              <label>
                <input 
                  type="checkbox" 
                  checked={settings.gates_enabled.multi_station}
                  onChange={(e) => updateGate('multi_station', e.target.checked)}
                />
                Gate 2: Multi-Station Validation
              </label>
            </div>
            <p className="gate-description">Cross-checks with nearby weather stations</p>
          </div>
          
          <div className="gate-item">
            <div className="gate-header">
              <label>
                <input 
                  type="checkbox" 
                  checked={settings.gates_enabled.bucket_coherence}
                  onChange={(e) => updateGate('bucket_coherence', e.target.checked)}
                />
                Gate 3: Bucket Coherence
              </label>
            </div>
            <p className="gate-description">Ensures temperature threshold brackets are logically consistent</p>
          </div>
          
          <div className="gate-item">
            <div className="gate-header">
              <label>
                <input 
                  type="checkbox" 
                  checked={settings.gates_enabled.binary_arbitrage}
                  onChange={(e) => updateGate('binary_arbitrage', e.target.checked)}
                />
                Gate 4: Binary Arbitrage Scanner
              </label>
            </div>
            <p className="gate-description">Detects YES+NO price inefficiencies</p>
          </div>
          
          <div className="gate-item">
            <div className="gate-header">
              <label>
                <input 
                  type="checkbox" 
                  checked={settings.gates_enabled.liquidity_check}
                  onChange={(e) => updateGate('liquidity_check', e.target.checked)}
                />
                Gate 5: Liquidity & Execution
              </label>
            </div>
            <p className="gate-description">Verifies sufficient market depth for position size</p>
          </div>
          
          <div className="gate-item">
            <div className="gate-header">
              <label>
                <input 
                  type="checkbox" 
                  checked={settings.gates_enabled.time_window}
                  onChange={(e) => updateGate('time_window', e.target.checked)}
                />
                Gate 6: Time Window Optimization
              </label>
            </div>
            <p className="gate-description">Avoids markets too close or too far from resolution</p>
          </div>
          
          <div className="gate-item">
            <div className="gate-header">
              <label>
                <input 
                  type="checkbox" 
                  checked={settings.gates_enabled.risk_manager}
                  onChange={(e) => updateGate('risk_manager', e.target.checked)}
                />
                Gate 7: Risk Manager
              </label>
            </div>
            <p className="gate-description">Enforces position sizing, exposure, and loss limits</p>
          </div>
          
          <div className="gate-item">
            <div className="gate-header">
              <label>
                <input 
                  type="checkbox" 
                  checked={settings.gates_enabled.claude_confirmation}
                  onChange={(e) => updateGate('claude_confirmation', e.target.checked)}
                />
                Gate 8: Claude AI Confirmation
              </label>
            </div>
            <p className="gate-description">AI validates reasoning and surface-level sanity checks</p>
          </div>
        </div>
      </div>

      {/* Section 6: Notifications */}
      <div className="settings-section">
        <h2>🔔 Notifications</h2>
        
        <div className="setting-control">
          <label>
            <input 
              type="checkbox" 
              checked={settings.telegram_alerts}
              onChange={(e) => updateSetting('telegram_alerts', e.target.checked)}
            />
            Enable Telegram Alerts
          </label>
        </div>
        
        {settings.telegram_alerts && (
          <div className="setting-control">
            <label>Telegram Chat ID</label>
            <input 
              type="text" 
              value={settings.telegram_chat_id}
              onChange={(e) => updateSetting('telegram_chat_id', e.target.value)}
              placeholder="Enter your Telegram chat ID"
            />
          </div>
        )}
        
        <div className="alert-toggles">
          <label>
            <input 
              type="checkbox" 
              checked={settings.alert_on_trade}
              onChange={(e) => updateSetting('alert_on_trade', e.target.checked)}
            />
            Trade Executed
          </label>
          
          <label>
            <input 
              type="checkbox" 
              checked={settings.alert_on_signal}
              onChange={(e) => updateSetting('alert_on_signal', e.target.checked)}
            />
            Signal Detected
          </label>
          
          <label>
            <input 
              type="checkbox" 
              checked={settings.alert_on_daily_summary}
              onChange={(e) => updateSetting('alert_on_daily_summary', e.target.checked)}
            />
            Daily Summary
          </label>
          
          <label>
            <input 
              type="checkbox" 
              checked={settings.alert_on_weekly_review}
              onChange={(e) => updateSetting('alert_on_weekly_review', e.target.checked)}
            />
            Weekly Review
          </label>
          
          <label>
            <input 
              type="checkbox" 
              checked={settings.alert_on_low_balance}
              onChange={(e) => updateSetting('alert_on_low_balance', e.target.checked)}
            />
            Low Balance Warning
          </label>
          
          <label>
            <input 
              type="checkbox" 
              checked={settings.alert_on_circuit_breaker}
              onChange={(e) => updateSetting('alert_on_circuit_breaker', e.target.checked)}
            />
            Circuit Breaker Triggered
          </label>
        </div>
      </div>

      {/* Section 7: Data Sources */}
      <div className="settings-section">
        <h2>📡 Data Sources</h2>
        
        <div className="data-sources-grid">
          <div className="data-source-card">
            <h4>METAR Stations</h4>
            <div className="source-status">
              <span className="status-indicator active">●</span> Active
            </div>
            <p>Real-time aviation weather data</p>
          </div>
          
          <div className="data-source-card">
            <h4>Open-Meteo</h4>
            <div className="source-status">
              <span className="status-indicator active">●</span> Active
            </div>
            <p>High-resolution forecasts</p>
          </div>
          
          <div className="data-source-card">
            <h4>Historical Data</h4>
            <div className="source-status">
              <span className="status-indicator active">●</span> Active
            </div>
            <p>Multi-year temperature trends</p>
          </div>
          
          <div className="data-source-card">
            <h4>Polymarket Scanner</h4>
            <div className="source-status">
              <span className="status-indicator active">●</span> Active
            </div>
            <p>Live market data</p>
          </div>
        </div>
        
        <div className="setting-control">
          <label>Data Refresh Interval</label>
          <select 
            value={settings.refresh_interval_min}
            onChange={(e) => updateSetting('refresh_interval_min', parseInt(e.target.value))}
          >
            <option value="5">5 minutes</option>
            <option value="15">15 minutes</option>
            <option value="30">30 minutes</option>
            <option value="60">1 hour</option>
          </select>
        </div>
      </div>

      {/* Section 8: Improvement Loop */}
      <div className="settings-section">
        <h2>🔄 Improvement Loop</h2>
        
        <div className="setting-control">
          <label>
            <input 
              type="checkbox" 
              checked={settings.strategy_auto_proposals}
              onChange={(e) => updateSetting('strategy_auto_proposals', e.target.checked)}
            />
            Enable Strategy Auto-Proposals
          </label>
        </div>
        
        <div className="setting-control">
          <label>Weekly Review Day</label>
          <select 
            value={settings.weekly_review_day}
            onChange={(e) => updateSetting('weekly_review_day', e.target.value)}
          >
            {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map(day => (
              <option key={day} value={day}>{day}</option>
            ))}
          </select>
        </div>
        
        <div className="setting-control">
          <label>Weekly Review Time</label>
          <input 
            type="time" 
            value={settings.weekly_review_time}
            onChange={(e) => updateSetting('weekly_review_time', e.target.value)}
          />
        </div>
        
        <div className="setting-control">
          <label>
            <input 
              type="checkbox" 
              checked={settings.auto_adjust_accuracy}
              onChange={(e) => updateSetting('auto_adjust_accuracy', e.target.checked)}
            />
            Auto-Adjust Station Accuracy Weights
          </label>
        </div>
        
        <div className="setting-control">
          <label>Proposal Approval Mode</label>
          <select 
            value={settings.proposal_approval_mode}
            onChange={(e) => updateSetting('proposal_approval_mode', e.target.value)}
          >
            <option value="require">Require CEO Approval</option>
            <option value="auto">Auto-Apply if Safe</option>
          </select>
        </div>
      </div>

      {/* Save Button */}
      <div className="settings-actions">
        <button 
          className="btn-primary save-btn"
          onClick={handleSaveSettings}
          disabled={saving}
        >
          {saving ? '💾 Saving...' : '💾 Save All Settings'}
        </button>
      </div>

      {/* Mode Confirmation Modal */}
      {showModeConfirm && (
        <div className="modal-overlay" onClick={() => setShowModeConfirm(false)}>
          <div className="modal-content confirm-modal" onClick={(e) => e.stopPropagation()}>
            <h2>⚠️ Enable Live Trading?</h2>
            <p>
              You are about to enable <strong>LIVE TRADING MODE</strong>.
            </p>
            <p>
              Real USDC will be used to execute trades on Polymarket. 
              Ensure your wallet is funded and you understand the risks.
            </p>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setShowModeConfirm(false)}>
                Cancel
              </button>
              <button className="btn-danger" onClick={confirmModeChange}>
                Yes, Enable Live Trading
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Settings
