import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import './App.css'

// Pages
import Overview from './pages/Overview'
import Signals from './pages/Signals'
import Trades from './pages/Trades'
import METAR from './pages/METAR'
import Settings from './pages/Settings'
import Explorer from './pages/Explorer'

function Sidebar() {
  const location = useLocation()
  
  const navItems = [
    { path: '/', label: 'Overview', icon: '📊' },
    { path: '/signals', label: 'Signals', icon: '⚡' },
    { path: '/trades', label: 'Trades', icon: '💰' },
    { path: '/metar', label: 'METAR', icon: '🌡️' },
    { path: '/explorer', label: 'Explorer', icon: '🔍' },
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
              <span>{item.icon}</span>
              <span>{item.label}</span>
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
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/signals" element={<Signals />} />
            <Route path="/trades" element={<Trades />} />
            <Route path="/metar" element={<METAR />} />
            <Route path="/explorer" element={<Explorer />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
          
          <div className="footer">
            Powered by Claude + OpenClaw + Actual Intelligence
          </div>
        </div>
      </div>
    </Router>
  )
}

export default App
