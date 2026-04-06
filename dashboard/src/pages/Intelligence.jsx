import { useState, useEffect } from 'react'
import axios from 'axios'

function Intelligence() {
  const [data, setData] = useState(null)
  const [daily, setDaily] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedStation, setSelectedStation] = useState(null)
  const [stationForecast, setStationForecast] = useState(null)
  const [stationHistory, setStationHistory] = useState(null)

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 60000)
    return () => clearInterval(interval)
  }, [])

  const fetchAll = async () => {
    try {
      const [dashRes, dailyRes] = await Promise.all([
        axios.get('/api/intelligence/dashboard'),
        axios.get('/api/intelligence/daily').catch(() => ({ data: null }))
      ])
      setData(dashRes.data)
      setDaily(dailyRes.data)
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch intelligence data:', error)
      setLoading(false)
    }
  }

  const fetchStationDetail = async (icao) => {
    setSelectedStation(icao)
    try {
      const [fRes, hRes] = await Promise.all([
        axios.get(`/api/intelligence/forecast/${icao}`).catch(() => ({ data: null })),
        axios.get(`/api/intelligence/historical/${icao}`).catch(() => ({ data: null }))
      ])
      setStationForecast(fRes.data)
      setStationHistory(hRes.data)
    } catch (e) {
      console.error('Station detail fetch failed', e)
    }
  }

  if (loading) return <div className="loading">Loading intelligence data...</div>
  if (!data) return <div className="loading">No data available</div>

  const convergenceColor = (status) => {
    if (status === 'high') return '#10B981'
    if (status === 'medium') return '#F59E0B'
    return '#EF4444'
  }

  const trendArrow = (val) => {
    if (!val) return '—'
    if (val > 0.5) return '🔺'
    if (val < -0.5) return '🔻'
    return '➡️'
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">🧠 Intelligence Layer</h1>
        <p className="page-subtitle">Real-time data convergence across {data.station_count} stations</p>
      </div>

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 24 }}>
        <div className="card" style={{ textAlign: 'center', padding: 16 }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{data.station_count}</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>METAR Stations</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 16 }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{data.forecast_count}</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Forecasts Loaded</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 16 }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{data.trend_count}</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Trend Calculations</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 16 }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{data.signal_count}</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Signals Generated</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 16 }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{data.trade_count}</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Trades Executed</div>
        </div>
      </div>

      {/* Daily Analysis */}
      {daily && daily.total_trades !== undefined && (
        <div className="card" style={{ marginBottom: 24, padding: 20 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>📊 Performance Analysis (7 days)</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Win Rate</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: daily.win_rate >= 0.55 ? '#10B981' : '#EF4444' }}>
                {(daily.win_rate * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Total P&L</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: daily.total_pnl >= 0 ? '#10B981' : '#EF4444' }}>
                ${daily.total_pnl?.toFixed(2) || '0.00'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Trades</div>
              <div style={{ fontSize: 24, fontWeight: 700 }}>{daily.total_trades}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Wins / Losses</div>
              <div style={{ fontSize: 24, fontWeight: 700 }}>
                <span style={{ color: '#10B981' }}>{daily.wins}</span>
                {' / '}
                <span style={{ color: '#EF4444' }}>{daily.losses}</span>
              </div>
            </div>
          </div>
          {daily.needs_attention && (
            <div style={{ marginTop: 16, padding: 12, background: 'rgba(239,68,68,0.1)', borderRadius: 8, color: '#EF4444', fontSize: 14 }}>
              ⚠️ Win rate below 55% over {daily.total_trades} trades — strategy review recommended
            </div>
          )}
        </div>
      )}

      {/* Station Data Convergence Table */}
      <div className="card" style={{ marginBottom: 24, padding: 20 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>🌡️ Station Data Convergence</h3>
        <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 16 }}>
          Click any station to see detailed forecast + historical data
        </p>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)' }}>Station</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>METAR °C</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Trend/hr</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Proj High</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Forecast High</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Forecast Low</th>
                <th style={{ padding: '8px 12px', textAlign: 'center' }}>Convergence</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Wind</th>
              </tr>
            </thead>
            <tbody>
              {data.stations.map((s, i) => (
                <tr 
                  key={s.station_icao}
                  onClick={() => fetchStationDetail(s.station_icao)}
                  style={{ 
                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                    cursor: 'pointer',
                    background: selectedStation === s.station_icao ? 'rgba(139,92,246,0.1)' : i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)'
                  }}
                >
                  <td style={{ padding: '10px 12px', fontWeight: 600, fontFamily: 'monospace' }}>{s.station_icao}</td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, 
                    color: s.metar.temperature_c > 30 ? '#EF4444' : s.metar.temperature_c < 0 ? '#3B82F6' : '#10B981' }}>
                    {s.metar.temperature_c?.toFixed(1) || '—'}°
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                    {trendArrow(s.trend.per_hour)} {s.trend.per_hour?.toFixed(2) || '—'}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                    {s.trend.projected_high?.toFixed(1) || '—'}°
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', color: '#8B5CF6' }}>
                    {s.forecast.high_c?.toFixed(1) || '—'}°
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', color: '#3B82F6' }}>
                    {s.forecast.low_c?.toFixed(1) || '—'}°
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                    <span style={{ 
                      display: 'inline-block', padding: '2px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600,
                      background: `${convergenceColor(s.convergence.status)}22`,
                      color: convergenceColor(s.convergence.status)
                    }}>
                      {s.convergence.sources_agree}/{s.convergence.total_sources}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 12 }}>
                    {s.metar.wind_speed_kt ? `${s.metar.wind_speed_kt}kt ${s.metar.wind_dir || ''}°` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Station Detail Modal */}
      {selectedStation && (stationForecast || stationHistory) && (
        <div className="card" style={{ marginBottom: 24, padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 600 }}>📍 {selectedStation} — Detailed Intelligence</h3>
            <button onClick={() => { setSelectedStation(null); setStationForecast(null); setStationHistory(null) }}
              style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 8, padding: '4px 12px', color: 'var(--text-secondary)', cursor: 'pointer' }}>
              ✕ Close
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {/* Forecast */}
            {stationForecast && (
              <div style={{ background: 'var(--bg-tertiary)', borderRadius: 12, padding: 16 }}>
                <h4 style={{ fontSize: 14, color: '#8B5CF6', marginBottom: 12 }}>🔮 Open-Meteo Forecast</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Forecast High</div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: '#EF4444' }}>{stationForecast.forecast_high_c?.toFixed(1)}°C</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Forecast Low</div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: '#3B82F6' }}>{stationForecast.forecast_low_c?.toFixed(1)}°C</div>
                  </div>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>Hourly Temperature (next 12h)</div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {(stationForecast.hourly_temps || []).slice(0, 12).map((t, i) => (
                    <div key={i} style={{ 
                      width: 36, textAlign: 'center', padding: '4px 0', borderRadius: 6, fontSize: 11, fontWeight: 600,
                      background: t > 25 ? 'rgba(239,68,68,0.15)' : t < 5 ? 'rgba(59,130,246,0.15)' : 'rgba(16,185,129,0.15)',
                      color: t > 25 ? '#EF4444' : t < 5 ? '#3B82F6' : '#10B981'
                    }}>
                      {t?.toFixed(0)}°
                    </div>
                  ))}
                </div>
                {stationForecast.precipitation_probs && (
                  <>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 12, marginBottom: 8 }}>Precipitation Probability (next 12h)</div>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {stationForecast.precipitation_probs.slice(0, 12).map((p, i) => (
                        <div key={i} style={{ 
                          width: 36, textAlign: 'center', padding: '4px 0', borderRadius: 6, fontSize: 11,
                          background: p > 50 ? 'rgba(59,130,246,0.2)' : 'rgba(255,255,255,0.05)',
                          color: p > 50 ? '#3B82F6' : 'var(--text-tertiary)'
                        }}>
                          {p}%
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Historical */}
            {stationHistory && (
              <div style={{ background: 'var(--bg-tertiary)', borderRadius: 12, padding: 16 }}>
                <h4 style={{ fontSize: 14, color: '#F59E0B', marginBottom: 12 }}>📜 Historical Pattern (5yr)</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Avg High (this date)</div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: '#F59E0B' }}>{stationHistory.avg_high_c?.toFixed(1)}°C</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Avg Low</div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: '#6366F1' }}>{stationHistory.avg_low_c?.toFixed(1) || '—'}°C</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Hottest Record</div>
                    <div style={{ fontSize: 18, fontWeight: 600 }}>{stationHistory.max_high_c?.toFixed(1)}°C</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Data Points</div>
                    <div style={{ fontSize: 18, fontWeight: 600 }}>{stationHistory.data_points} years</div>
                  </div>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>Year-by-Year Highs</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {stationHistory.yearly_highs && Object.entries(stationHistory.yearly_highs).sort().map(([year, temp]) => (
                    <div key={year} style={{ 
                      padding: '6px 10px', borderRadius: 8, fontSize: 12,
                      background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)'
                    }}>
                      <span style={{ color: 'var(--text-tertiary)' }}>{year}: </span>
                      <span style={{ fontWeight: 600 }}>{temp?.toFixed(1)}°C</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 8-Gate System Status */}
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>🔒 8-Gate Intelligence System</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
          {[
            { num: 1, name: 'Data Convergence', desc: 'METAR + Open-Meteo + Historical (2/3 must agree)', icon: '📊' },
            { num: 2, name: 'Multi-Station', desc: 'Multiple airports validate same city (±1°C)', icon: '✈️' },
            { num: 3, name: 'Bucket Coherence', desc: 'Temperature ranges must sum to ~100%', icon: '🪣' },
            { num: 4, name: 'Binary Arbitrage', desc: 'YES + NO < $0.98 = guaranteed profit', icon: '💰' },
            { num: 5, name: 'Liquidity Check', desc: 'Spread < 8¢, enough depth to fill', icon: '💧' },
            { num: 6, name: 'Time Window', desc: 'Optimal trading hours (6-8 AM, post-METAR)', icon: '⏰' },
            { num: 7, name: 'Risk Manager', desc: 'Position limits, Kelly sizing, circuit breakers', icon: '🛡️' },
            { num: 8, name: 'Claude AI', desc: 'Final AI confirmation (catches edge cases)', icon: '🤖' },
          ].map(gate => (
            <div key={gate.num} style={{ 
              display: 'flex', alignItems: 'center', gap: 12, padding: 12, 
              background: 'var(--bg-tertiary)', borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)'
            }}>
              <div style={{ fontSize: 24, width: 40, textAlign: 'center' }}>{gate.icon}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>Gate {gate.num}: {gate.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>{gate.desc}</div>
              </div>
              <div style={{ 
                width: 10, height: 10, borderRadius: '50%', background: '#10B981',
                boxShadow: '0 0 6px rgba(16,185,129,0.5)'
              }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default Intelligence
