import { useState, useEffect } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

function METAR() {
  const [stations, setStations] = useState([])
  const [selectedStation, setSelectedStation] = useState(null)
  const [stationHistory, setStationHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStations()
    const interval = setInterval(fetchStations, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  const fetchStations = async () => {
    try {
      const res = await axios.get('/api/metar/latest')
      setStations(res.data.data)
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch METAR data:', error)
      setLoading(false)
    }
  }

  const fetchStationHistory = async (icao) => {
    try {
      const res = await axios.get(`/api/metar/${icao}?hours=24`)
      setStationHistory(res.data.data)
      setSelectedStation(icao)
    } catch (error) {
      console.error('Failed to fetch station history:', error)
    }
  }

  const getTempTrend = (temp, prevTemp) => {
    if (!prevTemp) return '—'
    const diff = temp - prevTemp
    if (Math.abs(diff) < 0.5) return '➡️' // Stable
    return diff > 0 ? '🔺' : '🔻' // Warming or cooling
  }

  const getTimeSince = (dateStr) => {
    const minutes = Math.floor((Date.now() - new Date(dateStr).getTime()) / 60000)
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    return `${hours}h ago`
  }

  if (loading) {
    return <div className="loading">Loading...</div>
  }

  // Chart data for selected station
  const chartData = stationHistory.map(reading => ({
    time: new Date(reading.observation_time).toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit' 
    }),
    temp: reading.temperature_c
  })).reverse()

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">METAR Data</h1>
        <p className="page-subtitle">Live weather observations from stations</p>
      </div>

      {/* Station Grid */}
      {stations.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🌡️</div>
          <h3>No METAR data yet</h3>
          <p>Waiting for weather observations...</p>
        </div>
      ) : (
        <>
          <div className="card-grid">
            {stations.map((station) => {
              const prevTemp = stationHistory.find(s => s.station_icao === station.station_icao)?.temperature_c
              const trend = getTempTrend(station.temperature_c, prevTemp)
              
              return (
                <div 
                  key={station.station_icao}
                  className="card"
                  style={{ cursor: 'pointer', transition: 'all 0.2s' }}
                  onClick={() => fetchStationHistory(station.station_icao)}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'var(--accent-purple)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border)'
                  }}
                >
                  <div className="card-header">
                    <div className="card-title">{station.station_icao}</div>
                    <div style={{ fontSize: '24px' }}>{trend}</div>
                  </div>
                  <div className="card-value" style={{ 
                    color: station.temperature_c > 27 ? 'var(--error)' :
                           station.temperature_c < 0 ? 'var(--accent-purple)' :
                           'var(--success)'
                  }}>
                    {station.temperature_c?.toFixed(1)}°C
                  </div>
                  <div className="card-label">
                    Wind: {station.wind_speed_kt?.toFixed(0) || 0} kt
                    <br />
                    Updated: {getTimeSince(station.observation_time)}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Detailed View */}
          {selectedStation && stationHistory.length > 0 && (
            <div className="card" style={{ marginTop: '32px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div>
                  <h2 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '8px' }}>
                    {selectedStation} — 24 Hour Temperature
                  </h2>
                  <p style={{ color: 'var(--text-secondary)' }}>
                    {stationHistory.length} readings
                  </p>
                </div>
                <button 
                  className="btn btn-secondary"
                  onClick={() => setSelectedStation(null)}
                  style={{ padding: '8px 16px' }}
                >
                  Close
                </button>
              </div>

              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData}>
                  <XAxis 
                    dataKey="time" 
                    stroke="var(--text-tertiary)"
                    style={{ fontSize: '12px' }}
                  />
                  <YAxis 
                    stroke="var(--text-tertiary)"
                    style={{ fontSize: '12px' }}
                    domain={['auto', 'auto']}
                  />
                  <Tooltip 
                    contentStyle={{
                      background: 'var(--bg-tertiary)',
                      border: '1px solid var(--border)',
                      borderRadius: '8px',
                      color: 'var(--text-primary)'
                    }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="temp" 
                    stroke="var(--accent-purple)" 
                    strokeWidth={2}
                    dot={{ fill: 'var(--accent-purple)', r: 3 }}
                    name="Temperature (°C)"
                  />
                </LineChart>
              </ResponsiveContainer>

              {/* Raw METAR */}
              <div style={{ marginTop: '24px', padding: '16px', background: 'var(--bg-tertiary)', borderRadius: '8px' }}>
                <div style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '8px' }}>
                  Latest METAR:
                </div>
                <code style={{ color: 'var(--text-primary)', fontSize: '14px', fontFamily: 'monospace' }}>
                  {stationHistory[stationHistory.length - 1]?.raw_metar || 'N/A'}
                </code>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default METAR
