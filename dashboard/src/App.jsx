import React, { Component } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import './App.css'

// Pages
import Overview from './pages/Overview'
import Markets from './pages/Markets'
import Performance from './pages/Performance'
import Trades from './pages/Trades'
import Settings from './pages/Settings'
import PolymarketEmbed from './pages/PolymarketEmbed'

// Global error boundary
class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { hasError: false, error: null }; }
  static getDerivedStateFromError(error) { return { hasError: true, error }; }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 48, textAlign: 'center', color: '#94a3b8', minHeight: '60vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ fontSize: 56, marginBottom: 16 }}>⚠️</div>
          <h2 style={{ color: '#fff', marginBottom: 8 }}>Page crashed</h2>
          <p style={{ fontSize: 14, marginBottom: 20, maxWidth: 400 }}>{this.state.error?.message || 'Something went wrong rendering this page'}</p>
          <button onClick={() => { this.setState({ hasError: false }); window.location.reload(); }}
            style={{ padding: '12px 24px', background: '#7c3aed', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer', fontWeight: 600 }}>
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function Sidebar() {
  const location = useLocation()
  
  const navItems = [
    { path: '/', label: 'Home', icon: '🏠' },
    { path: '/markets', label: 'Markets', icon: '📊' },
    { path: '/performance', label: 'Performance', icon: '🏆' },
    { path: '/trades', label: 'Trades', icon: '💰' },
    { path: '/polymarket', label: 'Polymarket', icon: '🔮' },
    { path: '/settings', label: 'Settings', icon: '⚙️' },
  ]
  
  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        WeatherBot
      </div>
      <ul className="sidebar-nav">
        {navItems.map(item => (
          <li key={item.path}>
            <Link 
              to={item.path}
              className={location.pathname === item.path ? 'active' : ''}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

function App() {
  return (
    <Router>
      <div className="app">
        <Sidebar />
        <div className="main-content">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/markets" element={<Markets />} />
              <Route path="/markets/:industry" element={<Markets />} />
              <Route path="/performance" element={<Performance />} />
              <Route path="/trades" element={<Trades />} />
              <Route path="/polymarket" element={<PolymarketEmbed />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </ErrorBoundary>
          
          <div className="footer">
            Powered by Claude + OpenClaw + Actual Intelligence
          </div>
        </div>
      </div>
    </Router>
  )
}

export default App
