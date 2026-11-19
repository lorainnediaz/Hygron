import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { AnimatePresence, motion } from 'motion/react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import * as SelectPrimitive from '@radix-ui/react-select'
import { Check, ChevronDown } from 'lucide-react'
import {
  AlertTriangle,
  CheckCircle2,
  CircleMinus,
  Gauge,
  RefreshCw,
  LayoutDashboard,
  Info,
  Cpu,
  ChevronsLeft,
  ChevronsRight,
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
  High: { icon: AlertTriangle, color: '#b84d45', label: 'High — Inspect first' },
  Medium: { icon: Gauge, color: '#b77929', label: 'Medium — Monitor' },
  Low: { icon: CheckCircle2, color: '#3e8067', label: 'Low — Normal monitoring' },
  Unavailable: { icon: CircleMinus, color: '#91a098', label: 'Unavailable — Check data' },
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

export function App() {
  const [page, setPage] = useState('Dashboard')
  const [selectedRoom, setSelectedRoom] = useState('room_101')
  const [hours, setHours] = useState(24)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true)
  const [sidebarClosing, setSidebarClosing] = useState(false)
  const queryClient = useQueryClient()

  const roomsQuery = useQuery({
    queryKey: ['rooms'],
    queryFn: () => fetchJson('/rooms'),
  })
  const alertsQuery = useQuery({
    queryKey: ['alerts'],
    queryFn: () => fetchJson('/alerts'),
  })
  const systemQuery = useQuery({
    queryKey: ['system-status'],
    queryFn: () => fetchJson('/system-status'),
  })
  const historyQuery = useQuery({
    queryKey: ['history', selectedRoom, hours],
    queryFn: () => fetchJson(`/rooms/${selectedRoom}/history?hours=${hours}`),
  })
  const forecastQuery = useQuery({
    queryKey: ['forecast', selectedRoom],
    queryFn: () => fetchJson(`/rooms/${selectedRoom}/forecast`),
  })

  const roomList = useMemo(() => roomsQuery.data?.rooms || [], [roomsQuery.data])
  const counts = roomsQuery.data?.counts || {}
  const alerts = alertsQuery.data?.alerts || []
  const systemStatus = systemQuery.data
  const history = historyQuery.data?.readings || []
  const forecast = forecastQuery.data
  const chartStats = useMemo(() => {
    const history = historyQuery.data?.readings || []
    if (!history.length) return null
    const values = history.map((reading) => Number(reading.rh)).filter(Number.isFinite)
    if (!values.length) return null
    return {
      latest: values.at(-1),
      minimum: Math.min(...values),
      maximum: Math.max(...values),
      atThreshold: Math.round((values.filter((value) => value >= 80).length / values.length) * 100),
    }
  }, [historyQuery.data])
  const loading = roomsQuery.isLoading || alertsQuery.isLoading || systemQuery.isLoading
  const error = roomsQuery.error?.message || alertsQuery.error?.message || systemQuery.error?.message || historyQuery.error?.message || ''

  const selected = useMemo(
    () => roomList.find((room) => room.room_id === selectedRoom),
    [roomList, selectedRoom],
  )
  const priority = roomList[0]
  const forecastDirection = useMemo(() => {
    if (!forecast?.current_risk || !forecast?.forecast_24h_risk) return 'Unknown'
    const rank = { Low: 0, Medium: 1, High: 2 }
    if (!(forecast.current_risk in rank) || !(forecast.forecast_24h_risk in rank)) return 'Unknown'
    if (rank[forecast.forecast_24h_risk] > rank[forecast.current_risk]) return 'Higher'
    if (rank[forecast.forecast_24h_risk] < rank[forecast.current_risk]) return 'Lower'
    return 'Unchanged'
  }, [forecast])

  const acknowledgeMutation = useMutation({
    mutationFn: (alertId) =>
      fetchJson(`/alerts/${encodeURIComponent(alertId)}/acknowledge`, { method: 'POST' }),
    onSuccess: () => {
      toast.success('Alert acknowledged', {
        description: 'Acknowledgment records review. It does not confirm that risk is resolved.',
      })
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
    },
    onError: (requestError) => {
      toast.error('Could not acknowledge alert', { description: requestError.message })
    },
  })

  function refreshDashboard() {
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['rooms'] }),
      queryClient.invalidateQueries({ queryKey: ['alerts'] }),
      queryClient.invalidateQueries({ queryKey: ['system-status'] }),
      queryClient.invalidateQueries({ queryKey: ['history', selectedRoom, hours] }),
      queryClient.invalidateQueries({ queryKey: ['forecast', selectedRoom] }),
    ]).then(() => {
      toast.success('Readings refreshed', {
        description: 'The latest shared SQLite summaries are being displayed.',
      })
    })
  }

  function openSidebar() {
    setSidebarClosing(false)
    setSidebarCollapsed(false)
  }

  function closeSidebar() {
    if (sidebarClosing) return
    setSidebarClosing(true)
  }

  return (
    <div className={sidebarCollapsed ? 'app-shell sidebar-collapsed' : 'app-shell'}>
      <a className="skip-link" href="#main-content">Skip to dashboard content</a>
      {sidebarCollapsed && (
        <button
          type="button"
          className="floating-sidebar-toggle"
          onClick={openSidebar}
          aria-label="Expand sidebar"
          title="Expand sidebar"
        >
          <ChevronsRight size={17} aria-hidden="true" />
        </button>
      )}
      <AnimatePresence initial={false}>
        {(!sidebarCollapsed || sidebarClosing) && (
          <motion.aside
            key="sidebar"
            className="sidebar"
            aria-label="Main navigation"
            initial={sidebarClosing ? false : { x: -248, opacity: 0 }}
            animate={{ x: sidebarClosing ? -248 : 0, opacity: sidebarClosing ? 0 : 1 }}
            exit={{ x: -248, opacity: 0 }}
            transition={{ duration: 0.32, ease: [0.2, 0.8, 0.2, 1] }}
            onAnimationComplete={() => {
              if (sidebarClosing) {
                setSidebarCollapsed(true)
                setSidebarClosing(false)
              }
            }}
          >
        <button
          type="button"
          className="sidebar-toggle"
          onClick={closeSidebar}
          aria-label="Collapse sidebar"
          title="Collapse sidebar"
        >
          <ChevronsLeft size={17} aria-hidden="true" />
        </button>
        <div className="brand">
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
          </motion.aside>
        )}
      </AnimatePresence>

      <main className="main" id="main-content">
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
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.32, ease: [0.2, 0.8, 0.2, 1] }}
              >
                <h2>Software-in-the-Loop architecture</h2>
                <p>Virtual BME680 → virtual ESP32 → Raspberry Pi gateway → simulated Internet → SQLite → FastAPI → React dashboard.</p>
                <h2>Model limitation</h2>
                <p>Hygron estimates simulated VTT-derived mold-growth risk. It does not detect or confirm physical mold.</p>
              </motion.div>
            )}
          </section>
        ) : (
          <>
            <header className="page-header">
              <div>
                <h1>Room overview</h1>
                {systemStatus?.latest_timestamp && (
                  <p className="system-caption">Latest reading {systemStatus.latest_timestamp}</p>
                )}
              </div>
              <TooltipPrimitive.Root>
                <TooltipPrimitive.Trigger asChild>
                  <button
                    type="button"
                    className="refresh-button"
                    onClick={refreshDashboard}
                    disabled={roomsQuery.isFetching}
                  >
                    <RefreshCw className="refresh-icon" size={17} aria-hidden="true" />
                    {roomsQuery.isFetching ? 'Refreshing…' : 'Refresh readings'}
                  </button>
                </TooltipPrimitive.Trigger>
                <TooltipPrimitive.Portal>
                  <TooltipPrimitive.Content className="tooltip-content" sideOffset={8}>
                    Re-read the latest shared SQLite summaries
                    <TooltipPrimitive.Arrow className="tooltip-arrow" />
                  </TooltipPrimitive.Content>
                </TooltipPrimitive.Portal>
              </TooltipPrimitive.Root>
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
                  <section
                    className={`priority-panel priority-${priority.current_risk.toLowerCase()}`}
                    aria-label="Recommended room"
                  >
                    {priority.current_risk === 'High' && (
                      <AlertTriangle className="priority-warning-icon" size={26} aria-hidden="true" />
                    )}
                    <div className="priority-copy">
                      <p>{priority.current_risk === 'High' ? 'Immediate attention required' : 'Room to check'}</p>
                      <h2>{priority.room_name}</h2>
                      <div className="priority-status">
                        <span className={`status-dot ${priority.current_risk.toLowerCase()}`} />
                        {priority.current_risk === 'High'
                          ? 'High estimated risk — inspect now'
                          : `${priority.current_risk} estimated risk`}
                      </div>
                      <span className="priority-reading">
                        {priority.rh != null ? `${Number(priority.rh).toFixed(1)}% RH` : 'Humidity unavailable'}
                        {priority.temp != null ? ` · ${Number(priority.temp).toFixed(1)} °C` : ''}
                      </span>
                    </div>
                    <button type="button" onClick={() => setSelectedRoom(priority.room_id)}>
                      {priority.current_risk === 'High' ? 'Inspect room' : 'View room'}
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
                        aria-pressed={selectedRoom === room.room_id}
                        aria-label={`Select ${room.room_name}, ${room.current_risk} risk`}
                        onClick={() => setSelectedRoom(room.room_id)}
                      >
                        <strong className="room-cell room-name" data-label="Room">{room.room_name}</strong>
                        <span className="room-cell room-risk" data-label="Estimated risk"><RiskBadge risk={room.current_risk} /></span>
                        <span className="room-cell" data-label="Humidity">{room.rh != null ? `${Number(room.rh).toFixed(1)}%` : 'Unavailable'}</span>
                        <span className="room-cell" data-label="Temperature">{room.temp != null ? `${Number(room.temp).toFixed(1)} °C` : 'Unavailable'}</span>
                        <span className="room-cell" data-label="Staff action">{room.current_risk === 'High' ? 'Inspect' : room.current_risk === 'Medium' ? 'Monitor' : room.current_risk === 'Low' ? 'Continue' : 'Review data'}</span>
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
                      <MetricCard
                        label="24-HOUR OUTLOOK"
                        value={forecast?.forecast_24h_risk || selected.forecast_24h_risk || 'Unavailable'}
                        tone={(forecast?.forecast_24h_risk || selected.forecast_24h_risk || 'unavailable').toLowerCase()}
                      />
                    </div>
                    <p className="disclaimer">
                      Latest simulated reading: {selected.latest_timestamp || 'Unavailable'}.
                      Risk estimates describe simulated VTT-derived conditions, not confirmed mold.
                    </p>
                    <div className={`room-guidance guidance-${selected.current_risk.toLowerCase()}`}>
                      <strong>
                        {selected.current_risk === 'High'
                          ? 'Inspect for moisture or ventilation issues.'
                          : selected.current_risk === 'Medium'
                            ? 'Monitor the trend and plan a follow-up check.'
                            : selected.current_risk === 'Low'
                              ? 'Continue normal monitoring.'
                              : 'Review data availability before making a risk decision.'}
                      </strong>
                      <span>
                        {selected.current_risk === 'High'
                          ? 'Check the room, inspect damp surfaces, and review the humidity trend.'
                          : 'Risk estimates do not confirm that physical mold is present.'}
                      </span>
                    </div>
                  </section>
                )}

                <section>
                  <div className="section-heading">
                    <h2 className="section-title">Humidity history</h2>
                    <SelectPrimitive.Root value={String(hours)} onValueChange={(value) => setHours(Number(value))}>
                      <SelectPrimitive.Trigger className="period-select-trigger" aria-label="Time period">
                        <SelectPrimitive.Value />
                        <SelectPrimitive.Icon>
                          <ChevronDown size={15} aria-hidden="true" />
                        </SelectPrimitive.Icon>
                      </SelectPrimitive.Trigger>
                      <SelectPrimitive.Portal>
                        <SelectPrimitive.Content className="period-select-content" position="popper" sideOffset={6}>
                          <SelectPrimitive.Viewport>
                            {[
                              ['24', '24 hours'],
                              ['168', '7 days'],
                              ['720', '30 days'],
                              ['1440', '60 days'],
                            ].map(([value, label]) => (
                              <SelectPrimitive.Item className="period-select-item" value={value} key={value}>
                                <SelectPrimitive.ItemText>{label}</SelectPrimitive.ItemText>
                                <SelectPrimitive.ItemIndicator className="period-select-indicator">
                                  <Check size={15} aria-hidden="true" />
                                </SelectPrimitive.ItemIndicator>
                              </SelectPrimitive.Item>
                            ))}
                          </SelectPrimitive.Viewport>
                        </SelectPrimitive.Content>
                      </SelectPrimitive.Portal>
                    </SelectPrimitive.Root>
                  </div>
                  <div className="chart-card">
                    {history.length ? (
                      <>
                        {chartStats && (
                          <div className="chart-summary" aria-label="Humidity chart summary">
                            <div><span>Latest RH</span><strong>{chartStats.latest.toFixed(1)}%</strong></div>
                            <div><span>Humidity range</span><strong>{chartStats.minimum.toFixed(1)}–{chartStats.maximum.toFixed(1)}%</strong></div>
                            <div><span>At or above 80%</span><strong>{chartStats.atThreshold}%</strong></div>
                          </div>
                        )}
                        <div className="chart-legend" aria-label="Chart legend">
                          <span><i className="legend-rh" aria-hidden="true" /> Relative humidity</span>
                          <span><i className="legend-temp" aria-hidden="true" /> Temperature</span>
                          <span><i className="legend-threshold" aria-hidden="true" /> 80% RH reference</span>
                        </div>
                        <div className="chart-visual" role="img" aria-label={`Humidity and temperature chart for ${selected.room_name}`}>
                        <ResponsiveContainer width="100%" height={280}>
                        <LineChart data={history}>
                          <CartesianGrid stroke="rgba(128,128,128,.18)" vertical={false} />
                          <XAxis
                            dataKey="timestamp"
                            tickFormatter={(value) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            stroke="#74807c"
                            tick={{ fontSize: 12 }}
                          />
                          <YAxis domain={[0, 100]} stroke="#74807c" tick={{ fontSize: 12 }} />
                          <YAxis
                            yAxisId="temperature"
                            orientation="right"
                            domain={[10, 45]}
                            stroke="#3e8067"
                            tick={{ fontSize: 12 }}
                            width={42}
                          />
                          <Tooltip
                            labelFormatter={(value) => new Date(value).toLocaleString()}
                            formatter={(value, name) => [Number(value).toFixed(1), name === 'rh' ? 'Relative humidity (%)' : name]}
                          />
                          <ReferenceLine y={80} stroke="#b77929" strokeDasharray="5 5" label="80% RH" />
                          <ReferenceDot
                            x={history.at(-1)?.timestamp}
                            y={history.at(-1)?.rh}
                            r={5}
                            fill="#b84d45"
                            stroke="#fff"
                          />
                          <Line type="monotone" dataKey="rh" stroke="#4f7f78" strokeWidth={2.5} dot={false} />
                          <Line
                            type="monotone"
                            dataKey="temp"
                            yAxisId="temperature"
                            stroke="#3e8067"
                            strokeWidth={2}
                            dot={false}
                          />
                        </LineChart>
                        </ResponsiveContainer>
                        </div>
                        {chartStats && (
                          <details className="chart-text-alternative">
                            <summary>Chart text alternative</summary>
                            <p>
                              For {selected.room_name}, {history.length} displayed simulated readings are shown.
                              {' '}Relative humidity ranges from {chartStats.minimum.toFixed(1)}% to {chartStats.maximum.toFixed(1)}%;
                              {' '}the latest reading is {chartStats.latest.toFixed(1)}%, and {chartStats.atThreshold}% of displayed readings
                              are at or above 80% RH.
                            </p>
                          </details>
                        )}
                      </>
                    ) : (
                      <div className="empty-state">No valid cloud readings for this room.</div>
                    )}
                  </div>
                </section>

                {selected && (
                  <section className="outlook-section" aria-labelledby="outlook-title">
                    <div className="section-heading">
                      <h2 className="section-title" id="outlook-title">24-hour estimated outlook</h2>
                      <span className={`outlook-direction direction-${forecastDirection.toLowerCase()}`}>
                        Direction: {forecastDirection}
                      </span>
                    </div>
                    <div className="outlook-card">
                      <div className="outlook-progress" aria-label={`${selected.current_risk} to ${forecast?.forecast_24h_risk || 'Unavailable'} in 24 hours`}>
                        <div>
                          <span>Current estimate</span>
                          <strong className={`outlook-risk risk-${selected.current_risk.toLowerCase()}`}>{selected.current_risk}</strong>
                        </div>
                        <span className="outlook-arrow" aria-hidden="true">→</span>
                        <div>
                          <span>In 24 hours</span>
                          <strong className={`outlook-risk risk-${(forecast?.forecast_24h_risk || 'Unavailable').toLowerCase()}`}>
                            {forecast?.forecast_24h_risk || 'Unavailable'}
                          </strong>
                        </div>
                      </div>
                      <p>
                        Relative to the latest simulated reading
                        {selected.latest_timestamp ? ` (${selected.latest_timestamp})` : ''}.
                        This is supplementary decision support, not a guaranteed warning.
                      </p>
                      <p className="forecast-confidence">Forecast confidence: <strong>Unavailable</strong></p>
                      <details className="outlook-limitations">
                        <summary>Forecast limitations</summary>
                        <p>
                          This is one predicted category at +24 hours, not an hourly curve.
                          The model is trained on simulated VTT-derived labels and may not predict real-world mold conditions.
                          No calibrated confidence estimate is available; staff should confirm conditions before acting.
                        </p>
                      </details>
                    </div>
                  </section>
                )}

                <section>
                  <h2 className="section-title">Alerts</h2>
                  <div className="alert-list-summary">
                    <p>
                      <strong>{alerts.filter((alert) => alert.status !== 'Acknowledged').length} active</strong>
                      <span> · {alerts.length} current alert{alerts.length === 1 ? '' : 's'} in this session</span>
                    </p>
                    <span>Acknowledgment records review; it does not confirm resolution.</span>
                  </div>
                  {alerts.length ? alerts.slice(0, 5).map((alert) => (
                    <article className={`alert-card ${alert.status === 'Acknowledged' ? 'acknowledged' : ''}`} key={alert.id}>
                      <div className="alert-main">
                        <span className="alert-status-icon" aria-hidden="true">
                          {alert.status === 'Acknowledged'
                            ? <CheckCircle2 size={18} />
                            : <AlertTriangle size={18} />}
                        </span>
                        <div>
                          <div className="alert-heading">
                            <strong>{alert.room_name} needs attention</strong>
                            <span className={`alert-state ${alert.status === 'Acknowledged' ? 'is-acknowledged' : 'needs-action'}`}>
                              {alert.status === 'Acknowledged' ? 'Acknowledged' : 'Action needed'}
                            </span>
                          </div>
                          <p>
                            Humidity: {alert.rh != null ? `${Number(alert.rh).toFixed(1)}%` : 'Unavailable'}
                            {' · '}Temperature: {alert.temp != null ? `${Number(alert.temp).toFixed(1)} °C` : 'Unavailable'}
                          </p>
                          <p className="alert-time">{alert.timestamp}</p>
                        </div>
                      </div>
                      <button
                        type="button"
                        disabled={alert.status === 'Acknowledged' || acknowledgeMutation.isPending}
                        onClick={() => acknowledgeMutation.mutate(alert.id)}
                      >
                        {alert.status === 'Acknowledged' ? 'Reviewed' : 'Acknowledge'}
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
