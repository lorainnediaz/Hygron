import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  CircleMinus,
  Gauge,
  RefreshCw,
  Thermometer,
  Droplets,
  LayoutDashboard,
  Info,
  Cpu,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  ReferenceDot,
} from 'recharts'
import './App.css'

const API = '/api'

const riskStyles = {
  High: { icon: AlertTriangle, color: '#ff453a', label: 'High — Inspect first' },
  Medium: { icon: Gauge, color: '#ff9f0a', label: 'Medium — Monitor' },
  Low: { icon: CheckCircle2, color: '#30d158', label: 'Low — Normal monitoring' },
  Unavailable: { icon: CircleMinus, color: '#98989f', label: 'Unavailable — Check data' },
}

async function fetchJson(path, options) {
  const response = await fetch(`${API}${path}`, options)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${response.status}`)
  }
  return response.json()
}

function RiskBadge({ risk }) {
  const style = riskStyles[risk] || riskStyles.Unavailable
  const Icon = style.icon
  return (
    <span className="risk-badge" style={{ '--risk': style.color }}>
      <Icon size={16} aria-hidden="true" />
      {style.label}
    </span>
  )
}

function MetricCard({ label, value, caption, tone }) {
  return (
    <article className="metric-card">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${tone || ''}`}>{value}</div>
      {caption && <div className="metric-caption">{caption}</div>}
    </article>
  )
}

function App() {
  const [page, setPage] = useState('Dashboard')
  const [roomList, setRoomList] = useState([])
  const [counts, setCounts] = useState({})
  const [selectedRoom, setSelectedRoom] = useState('room_101')
  const [history, setHistory] = useState([])
  const [hours, setHours] = useState(24)
  const [alerts, setAlerts] = useState([])
  const [systemStatus, setSystemStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  async function loadDashboard() {
    setLoading(true)
    setError('')
    try {
      const [roomsBody, alertsBody, statusBody] = await Promise.all([
        fetchJson('/rooms'),
        fetchJson('/alerts'),
        fetchJson('/system-status'),
      ])
      setRoomList(roomsBody.rooms)
      setCounts(roomsBody.counts)
      setAlerts(alertsBody.alerts)
      setSystemStatus(statusBody)
      if (roomsBody.rooms.length && !roomsBody.rooms.some((room) => room.room_id === selectedRoom)) {
        setSelectedRoom(roomsBody.rooms[0].room_id)
      }
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [refreshKey])

  useEffect(() => {
    let active = true
    fetchJson(`/rooms/${selectedRoom}/history?hours=${hours}`)
      .then((body) => {
        if (active) setHistory(body.readings)
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
    return () => {
      active = false
    }
  }, [selectedRoom, hours, refreshKey])

  const selected = useMemo(
    () => roomList.find((room) => room.room_id === selectedRoom),
    [roomList, selectedRoom],
  )
  const priority = roomList[0]

  async function acknowledgeAlert(alertId) {
    await fetchJson(`/alerts/${encodeURIComponent(alertId)}/acknowledge`, { method: 'POST' })
      .then(async () => setAlerts((current) => current.map((alert) =>
        alert.id === alertId ? { ...alert, status: 'Acknowledged' } : alert,
      )))
      .catch((requestError) => setError(requestError.message))
  }

  return (
    <div className={sidebarCollapsed ? 'app-shell sidebar-collapsed' : 'app-shell'}>
      {sidebarCollapsed && (
        <button
          type="button"
          className="floating-sidebar-toggle"
          onClick={() => setSidebarCollapsed(false)}
          aria-label="Expand sidebar"
          title="Expand sidebar"
        >
          <PanelLeftOpen size={18} aria-hidden="true" />
        </button>
      )}
      <aside className="sidebar" aria-label="Main navigation">
        <button
          type="button"
          className="sidebar-toggle"
          onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed
            ? <PanelLeftOpen size={18} aria-hidden="true" />
            : <PanelLeftClose size={18} aria-hidden="true" />}
        </button>
        <div className="brand">
          <div className="brand-mark">H</div>
          <div>
            <strong>HYGRON</strong>
            <span>Environmental monitoring</span>
          </div>
        </div>
        <nav>
          {[
            ['Dashboard', LayoutDashboard],
            ['Methodology', Info],
            ['IoT Workbench', Cpu],
          ].map(([name, Icon]) => (
            <button
              key={name}
              type="button"
              className={page === name ? 'nav-item active' : 'nav-item'}
              onClick={() => setPage(name)}
              aria-current={page === name ? 'page' : undefined}
            >
              <Icon size={18} aria-hidden="true" />
              {name}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span>Prototype</span>
          <small>Simulated data</small>
        </div>
      </aside>

      <main className="main">
        {page !== 'Dashboard' ? (
          <section className="content-card placeholder-page">
            <h1>{page}</h1>
            {page === 'IoT Workbench' ? (
              <>
                <p>
                  The virtual sensor, ESP32, edge gateway, simulated Internet, and SQLite pipeline remain in the separate Streamlit IoT Workbench.
                </p>
                <a className="method-link" href="http://127.0.0.1:8501/workbench" target="_blank" rel="noreferrer">
                  Open IoT Workbench
                </a>
              </>
            ) : (
              <>
                <h2>Software-in-the-Loop architecture</h2>
                <p>Virtual BME680 → virtual ESP32 → Raspberry Pi gateway → simulated Internet → SQLite → FastAPI → React dashboard.</p>
                <h2>Model limitation</h2>
                <p>Hygron estimates simulated VTT-derived mold-growth risk. It does not detect or confirm physical mold.</p>
              </>
            )}
          </section>
        ) : (
          <>
            <header className="page-header">
              <div>
                <p className="eyebrow">Hotel monitoring</p>
                <h1>Room overview</h1>
              </div>
              <button
                type="button"
                className="refresh-button"
                onClick={() => setRefreshKey((value) => value + 1)}
              >
                <RefreshCw size={17} aria-hidden="true" />
                Refresh readings
              </button>
            </header>

            {error && (
              <div className="error-banner" role="alert">
                <AlertTriangle size={18} aria-hidden="true" />
                {error}
              </div>
            )}

            {loading ? (
              <div className="loading-card">Loading room monitoring data…</div>
            ) : (
              <>
                {priority && (
                  <section className="priority-panel" aria-label="Recommended room">
                    <div className="priority-copy">
                      <p>Room to check</p>
                      <h2>{priority.room_name}</h2>
                      <div className="priority-status">
                        <span className={`status-dot ${priority.current_risk.toLowerCase()}`} />
                        {priority.current_risk} estimated risk
                      </div>
                      <span className="priority-reading">
                        {priority.rh != null ? `${Number(priority.rh).toFixed(1)}% RH` : 'Humidity unavailable'}
                        {priority.temp != null ? ` · ${Number(priority.temp).toFixed(1)} °C` : ''}
                      </span>
                    </div>
                    <button type="button" onClick={() => setSelectedRoom(priority.room_id)}>
                      View room
                    </button>
                  </section>
                )}

                <section>
                  <h2 className="section-title">Risk at a glance</h2>
                  <div className="risk-rail">
                    {['High', 'Medium', 'Low', 'Unavailable'].map((risk) => (
                      <div className="risk-rail-item" key={risk}>
                        <span className={`status-dot ${risk.toLowerCase()}`} />
                        <div>
                          <strong>{counts[risk] || 0}</strong>
                          <span>{risk}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                <section>
                  <h2 className="section-title">Rooms needing attention</h2>
                  <div className="room-table" role="table" aria-label="Room risk summary">
                    <div className="room-row room-header" role="row">
                      <span>Room</span><span>Estimated risk</span><span>Humidity</span><span>Temperature</span><span>Staff action</span>
                    </div>
                    {roomList.map((room) => (
                      <button
                        type="button"
                        role="row"
                        className={selectedRoom === room.room_id ? 'room-row selected' : 'room-row'}
                        key={room.room_id}
                        onClick={() => setSelectedRoom(room.room_id)}
                      >
                        <strong>{room.room_name}</strong>
                        <RiskBadge risk={room.current_risk} />
                        <span>{room.rh != null ? `${Number(room.rh).toFixed(1)}%` : 'Unavailable'}</span>
                        <span>{room.temp != null ? `${Number(room.temp).toFixed(1)} °C` : 'Unavailable'}</span>
                        <span>{room.current_risk === 'High' ? 'Inspect' : room.current_risk === 'Medium' ? 'Monitor' : room.current_risk === 'Low' ? 'Continue' : 'Review data'}</span>
                      </button>
                    ))}
                  </div>
                </section>

                {selected && (
                  <section>
                    <h2 className="section-title">{selected.room_name} details</h2>
                    <div className="detail-grid">
                      <MetricCard label="ESTIMATED CURRENT RISK" value={selected.current_risk} tone={selected.current_risk.toLowerCase()} />
                      <MetricCard
                        label="RELATIVE HUMIDITY"
                        value={selected.rh != null ? `${Number(selected.rh).toFixed(1)}%` : 'Unavailable'}
                        tone={selected.rh >= 80 ? 'high' : ''}
                      />
                      <MetricCard
                        label="TEMPERATURE"
                        value={selected.temp != null ? `${Number(selected.temp).toFixed(1)} °C` : 'Unavailable'}
                      />
                      <MetricCard label="24-HOUR OUTLOOK" value={selected.forecast_24h_risk} />
                    </div>
                    <p className="disclaimer">
                      Latest simulated reading: {selected.latest_timestamp || 'Unavailable'}.
                      Risk estimates describe simulated VTT-derived conditions, not confirmed mold.
                    </p>
                  </section>
                )}

                <section>
                  <div className="section-heading">
                    <h2 className="section-title">Humidity history</h2>
                    <select value={hours} onChange={(event) => setHours(Number(event.target.value))} aria-label="Time period">
                      <option value={24}>24 hours</option>
                      <option value={168}>7 days</option>
                      <option value={720}>30 days</option>
                      <option value={1440}>60 days</option>
                    </select>
                  </div>
                  <div className="chart-card">
                    {history.length ? (
                      <ResponsiveContainer width="100%" height={280}>
                        <LineChart data={history}>
                          <CartesianGrid stroke="rgba(128,128,128,.18)" vertical={false} />
                          <XAxis
                            dataKey="timestamp"
                            tickFormatter={(value) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            stroke="#98989f"
                            tick={{ fontSize: 12 }}
                          />
                          <YAxis domain={[0, 100]} stroke="#98989f" tick={{ fontSize: 12 }} />
                          <YAxis
                            yAxisId="temperature"
                            orientation="right"
                            domain={[10, 45]}
                            stroke="#30d158"
                            tick={{ fontSize: 12 }}
                            width={42}
                          />
                          <Tooltip
                            labelFormatter={(value) => new Date(value).toLocaleString()}
                            formatter={(value, name) => [Number(value).toFixed(1), name === 'rh' ? 'Relative humidity (%)' : name]}
                          />
                          <ReferenceLine y={80} stroke="#ff9f0a" strokeDasharray="5 5" label="80% RH" />
                          <ReferenceDot
                            x={history.at(-1)?.timestamp}
                            y={history.at(-1)?.rh}
                            r={5}
                            fill="#ff453a"
                            stroke="#fff"
                          />
                          <Line type="monotone" dataKey="rh" stroke="#0a84ff" strokeWidth={2.5} dot={false} />
                          <Line
                            type="monotone"
                            dataKey="temp"
                            yAxisId="temperature"
                            stroke="#30d158"
                            strokeWidth={2}
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="empty-state">No valid cloud readings for this room.</div>
                    )}
                  </div>
                </section>

                <section>
                  <h2 className="section-title">Alerts</h2>
                  {alerts.length ? alerts.map((alert) => (
                    <article className="alert-card" key={alert.id}>
                      <div>
                        <strong>{alert.room_name} needs attention</strong>
                        <p>{alert.rh != null ? `Humidity: ${Number(alert.rh).toFixed(1)}%` : 'Humidity unavailable'} · {alert.timestamp}</p>
                        <p>Inspect for moisture, condensation, or ventilation issues.</p>
                      </div>
                      <button
                        type="button"
                        disabled={alert.status === 'Acknowledged'}
                        onClick={() => acknowledgeAlert(alert.id)}
                      >
                        {alert.status === 'Acknowledged' ? 'Acknowledged' : 'Acknowledge'}
                      </button>
                    </article>
                  )) : (
                    <div className="empty-state">No active High-risk alerts.</div>
                  )}
                </section>

                {systemStatus && (
                  <footer className="system-footer">
                    <span>Asia/Manila</span>
                    <span>{systemStatus.valid_for_history} valid summaries</span>
                    <span>{systemStatus.models.available ? 'Models available' : 'Models unavailable'}</span>
                  </footer>
                )}
              </>
            )}
          </>
        )}
      </main>
    </div>
  )
}

export default App
