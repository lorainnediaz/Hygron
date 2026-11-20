import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import * as SelectPrimitive from '@radix-ui/react-select'
import { Check, ChevronDown } from 'lucide-react'
import {
  AlertTriangle,
  ArrowRight,
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
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  ReferenceDot,
} from 'recharts'
import './App.css'
import { riskMeanings } from './risk'
import { CountUp, HumidityBar, RiskBar } from './visuals'

const API = '/api'
const RISK_ORDER = ['High', 'Medium', 'Low', 'Unavailable']

const riskStyles = {
  High: { icon: AlertTriangle, color: 'var(--coral)', label: 'High' },
  Medium: { icon: Gauge, color: 'var(--amber)', label: 'Medium' },
  Low: { icon: CheckCircle2, color: 'var(--green)', label: 'Low' },
  Unavailable: { icon: CircleMinus, color: 'var(--unavailable)', label: 'Unavailable' },
}

const staffActions = { High: 'Inspect', Medium: 'Monitor', Low: 'Continue', Unavailable: 'Review data' }

const CONFIDENCE_FALLBACK = "The model's scores haven't been checked against labeled data, so no percentage is shown."

function formatReading(value, unit) {
  return value != null ? `${Number(value).toFixed(1)}${unit}` : 'Unavailable'
}

function roomRowLabel(room) {
  const parts = [
    `${room.room_name}: ${room.current_risk} risk`,
    `humidity ${formatReading(room.rh, '%')}`,
    `temperature ${formatReading(room.temp, ' °C')}`,
    `action ${staffActions[room.current_risk] || staffActions.Unavailable}`,
  ]
  if (room.current_risk === 'Unavailable' && room.unavailable_reason) {
    parts.push(`reason: ${room.unavailable_reason}`)
  }
  return parts.join(', ')
}

async function fetchJson(path, options) {
  const response = await fetch(`${API}${path}`, options)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${response.status}`)
  }
  return response.json()
}

function RiskBadge({ risk, size = 15 }) {
  const style = riskStyles[risk] || riskStyles.Unavailable
  const Icon = style.icon
  return (
    <span className={`risk-badge risk-badge-${(riskStyles[risk] ? risk : 'Unavailable').toLowerCase()}`} style={{ '--risk': style.color }}>
      <Icon size={size} aria-hidden="true" />
      {style.label}
    </span>
  )
}

function MetricCard({ label, value, caption, tone, children }) {
  return (
    <article className="metric-card">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${tone || ''}`}>{value}</div>
      {children}
      {caption && <div className="metric-caption">{caption}</div>}
    </article>
  )
}

/** Hours-based tick labels: time of day for one day, date for longer ranges. */
function formatTick(value, hours) {
  const date = new Date(value)
  return hours <= 24
    ? date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

export function App() {
  const [page, setPage] = useState('Dashboard')
  const [selectedRoom, setSelectedRoom] = useState('room_101')
  const [hours, setHours] = useState(24)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true)
  const [sidebarClosing, setSidebarClosing] = useState(false)
  const queryClient = useQueryClient()
  const reduceMotion = useReducedMotion()

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
    const minimum = Math.min(...values)
    return {
      latest: values.at(-1),
      minimum,
      maximum: Math.max(...values),
      atThreshold: Math.round((values.filter((value) => value >= 80).length / values.length) * 100),
      // Start the humidity axis at 40% unless readings go lower, so changes are visible.
      floor: Math.max(0, Math.min(40, Math.floor((minimum - 5) / 10) * 10)),
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

  function showRoomDetails(roomId) {
    setSelectedRoom(roomId)
    // Move focus to the updated details so keyboard and screen-reader users land on the change.
    window.requestAnimationFrame(() => document.getElementById('room-details-title')?.focus())
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

      <main className="main" id="main-content" tabIndex={-1}>
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
              <div className="loading-card" role="status">Loading room monitoring data…</div>
            ) : (
              <>
                {priority && (
                  <section
                    className={`priority-panel reveal priority-${priority.current_risk.toLowerCase()}`}
                    style={{ '--i': 0, '--risk': (riskStyles[priority.current_risk] || riskStyles.Unavailable).color }}
                    aria-label="Recommended room"
                  >
                    <div className="priority-tile" aria-hidden="true">
                      <span>Room</span>
                      <strong>{priority.room_name.replace(/^Room\s*/i, '')}</strong>
                    </div>
                    <div className="priority-copy">
                      <p className="priority-eyebrow">
                        {priority.current_risk === 'High' && <span className="pulse-dot" aria-hidden="true" />}
                        {priority.current_risk === 'High' ? 'Immediate attention required' : 'Room to check'}
                      </p>
                      <h2>{priority.room_name}</h2>
                      <div className="priority-status">
                        {priority.current_risk === 'High'
                          ? 'High estimated risk. Inspect now.'
                          : `${priority.current_risk} estimated risk`}
                      </div>
                      <span className="priority-reading">
                        {priority.rh != null ? `${Number(priority.rh).toFixed(1)}% RH` : 'Humidity unavailable'}
                        {priority.temp != null ? `, ${Number(priority.temp).toFixed(1)} °C` : ''}
                      </span>
                      {priority.current_risk === 'Unavailable' && priority.unavailable_reason && (
                        <span className="unavailable-reason">Reason: {priority.unavailable_reason}</span>
                      )}
                    </div>
                    <button type="button" onClick={() => showRoomDetails(priority.room_id)}>
                      {priority.current_risk === 'High' ? 'Inspect room' : 'View room'}
                      <ArrowRight size={16} aria-hidden="true" />
                    </button>
                  </section>
                )}

                <section className="reveal" style={{ '--i': 1 }} aria-labelledby="risk-glance-title">
                  <h2 className="section-title" id="risk-glance-title">Risk at a glance</h2>
                  <p className="risk-scale-note">
                    Levels are model estimates from each room&apos;s simulated humidity and temperature over the last 60 days,
                    using VTT-derived mold-growth categories. They do not confirm that mold is present.
                  </p>
                  <RiskBar counts={counts} order={RISK_ORDER} />
                  <ul className="risk-rail">
                    {RISK_ORDER.map((risk) => {
                      const RiskIcon = riskStyles[risk].icon
                      return (
                        <li
                          className={`risk-rail-item ${risk.toLowerCase()}`}
                          key={risk}
                          style={{ '--risk': riskStyles[risk].color }}
                        >
                          <div className="risk-rail-head">
                            <strong><CountUp value={counts[risk] || 0} /></strong>
                            <RiskIcon className="risk-rail-icon" size={18} aria-hidden="true" />
                          </div>
                          <span className="risk-rail-label">{risk}</span>
                          <p className="risk-meaning">{riskMeanings[risk]}</p>
                        </li>
                      )
                    })}
                  </ul>
                </section>

                <section className="reveal" style={{ '--i': 2 }} aria-labelledby="rooms-title">
                  <h2 className="section-title" id="rooms-title">Rooms needing attention</h2>
                  <div className="room-table" role="group" aria-labelledby="rooms-title">
                    <div className="room-row room-header" aria-hidden="true">
                      <span>Room</span><span>Estimated risk</span><span>Humidity</span><span>Temperature</span><span>Staff action</span>
                    </div>
                    {roomList.map((room) => (
                      <button
                        type="button"
                        className={selectedRoom === room.room_id ? 'room-row selected' : 'room-row'}
                        style={{ '--risk': (riskStyles[room.current_risk] || riskStyles.Unavailable).color }}
                        key={room.room_id}
                        aria-pressed={selectedRoom === room.room_id}
                        aria-label={roomRowLabel(room)}
                        onClick={() => setSelectedRoom(room.room_id)}
                      >
                        <strong className="room-cell room-name" data-label="Room">{room.room_name}</strong>
                        <span className="room-cell room-risk" data-label="Estimated risk"><RiskBadge risk={room.current_risk} /></span>
                        <span className="room-cell" data-label="Humidity">{formatReading(room.rh, '%')}</span>
                        <span className="room-cell" data-label="Temperature">{formatReading(room.temp, ' °C')}</span>
                        <span className="room-cell" data-label="Staff action">{staffActions[room.current_risk] || staffActions.Unavailable}</span>
                      </button>
                    ))}
                  </div>
                </section>

                {selected && (
                  <section className="reveal" style={{ '--i': 3 }} aria-labelledby="room-details-title">
                    <h2 className="section-title" id="room-details-title" tabIndex={-1}>{selected.room_name} details</h2>
                    <motion.div
                      key={selected.room_id}
                      className="detail-grid"
                      initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
                    >
                      <MetricCard
                        label="ESTIMATED CURRENT RISK"
                        value={selected.current_risk}
                        tone={selected.current_risk.toLowerCase()}
                        caption={selected.current_risk !== 'Unavailable' ? riskMeanings[selected.current_risk] : undefined}
                      />
                      <MetricCard
                        label="RELATIVE HUMIDITY"
                        value={selected.rh != null ? `${Number(selected.rh).toFixed(1)}%` : 'Unavailable'}
                        tone={selected.rh >= 80 ? 'high' : ''}
                      >
                        <HumidityBar rh={selected.rh} />
                      </MetricCard>
                      <MetricCard
                        label="TEMPERATURE"
                        value={selected.temp != null ? `${Number(selected.temp).toFixed(1)} °C` : 'Unavailable'}
                      />
                      <MetricCard
                        label="24-HOUR OUTLOOK"
                        value={forecast?.forecast_24h_risk || selected.forecast_24h_risk || 'Unavailable'}
                        tone={(forecast?.forecast_24h_risk || selected.forecast_24h_risk || 'unavailable').toLowerCase()}
                      >
                        <div className="outlook-pills">
                          <RiskBadge risk={selected.current_risk} size={13} />
                          <ArrowRight size={14} aria-hidden="true" />
                          <span className="sr-only">to</span>
                          <RiskBadge risk={forecast?.forecast_24h_risk || selected.forecast_24h_risk || 'Unavailable'} size={13} />
                        </div>
                      </MetricCard>
                    </motion.div>
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
                          : selected.current_risk === 'Unavailable'
                            ? `Reason: ${selected.unavailable_reason || 'The backend did not report a reason.'}`
                            : 'Risk estimates do not confirm that physical mold is present.'}
                      </span>
                    </div>
                  </section>
                )}

                <section className="reveal" style={{ '--i': 4 }}>
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
                        <ComposedChart data={history} margin={{ top: 8, right: 4, bottom: 0, left: -8 }}>
                          <defs>
                            <linearGradient id="rhFill" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#4f7f78" stopOpacity={0.28} />
                              <stop offset="100%" stopColor="#4f7f78" stopOpacity={0.02} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid stroke="rgba(38,52,49,.08)" vertical={false} />
                          <XAxis
                            dataKey="timestamp"
                            tickFormatter={(value) => formatTick(value, hours)}
                            stroke="#5b6763"
                            tick={{ fontSize: 12 }}
                            tickLine={false}
                            axisLine={false}
                            minTickGap={56}
                            interval="preserveStartEnd"
                          />
                          <YAxis
                            domain={[chartStats?.floor ?? 0, 100]}
                            stroke="#5b6763"
                            tick={{ fontSize: 12 }}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(value) => `${value}%`}
                            width={46}
                          />
                          <YAxis
                            yAxisId="temperature"
                            orientation="right"
                            domain={[(dataMin) => Math.floor(dataMin - 6), (dataMax) => Math.ceil(dataMax + 6)]}
                            stroke="#5a5f8f"
                            tick={{ fontSize: 12 }}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(value) => `${Math.round(value)}°`}
                            width={36}
                          />
                          <Tooltip
                            labelFormatter={(value) => new Date(value).toLocaleString()}
                            formatter={(value, name) => [
                              Number(value).toFixed(1),
                              name === 'rh' ? 'Relative humidity (%)' : name === 'temp' ? 'Temperature (°C)' : name,
                            ]}
                          />
                          <ReferenceArea y1={80} y2={100} fill="#a8423a" fillOpacity={0.06} stroke="none" ifOverflow="hidden" />
                          <ReferenceLine
                            y={80}
                            stroke="#b77929"
                            strokeDasharray="5 5"
                            label={{ value: '80% RH', position: 'insideTopRight', fill: '#8a5a12', fontSize: 11 }}
                          />
                          <Area
                            type="monotone"
                            dataKey="rh"
                            stroke="#4f7f78"
                            strokeWidth={2.5}
                            fill="url(#rhFill)"
                            baseValue={chartStats?.floor ?? 0}
                            dot={false}
                            activeDot={{ r: 4 }}
                          />
                          <Line
                            type="monotone"
                            dataKey="temp"
                            yAxisId="temperature"
                            stroke="#5a5f8f"
                            strokeWidth={1.75}
                            strokeDasharray="6 4"
                            dot={false}
                          />
                          <ReferenceDot
                            x={history.at(-1)?.timestamp}
                            y={history.at(-1)?.rh}
                            r={5}
                            fill="#a8423a"
                            stroke="#fff"
                            strokeWidth={2}
                          />
                        </ComposedChart>
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
                  <section className="outlook-section reveal" style={{ '--i': 5 }} aria-labelledby="outlook-title">
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
                      {(forecast?.forecast_24h_risk || 'Unavailable') === 'Unavailable' && forecast?.unavailable_reason && (
                        <p className="unavailable-reason">Outlook unavailable: {forecast.unavailable_reason}</p>
                      )}
                      <div className="confidence-note">
                        <Info className="confidence-note-icon" size={16} aria-hidden="true" />
                        <p>
                          <strong>How sure is this outlook?</strong>{' '}
                          We can&apos;t say yet. {forecast?.confidence_reason || CONFIDENCE_FALLBACK}{' '}
                          Check the room yourself before acting on it.
                        </p>
                      </div>
                      <details className="outlook-limitations">
                        <summary>Forecast limitations</summary>
                        <p>
                          This is one predicted category for 24 hours from the latest reading, not an hourly curve.
                          The model was trained on simulated VTT-derived labels and may not match real-world mold conditions.
                          In testing it often missed rooms whose risk was about to change.
                        </p>
                      </details>
                    </div>
                  </section>
                )}

                <section className="reveal" style={{ '--i': 6 }}>
                  <h2 className="section-title">Alerts</h2>
                  <div className="alert-list-summary">
                    <p>
                      <strong>{alerts.filter((alert) => alert.status !== 'Acknowledged').length} active</strong>
                      <span> out of {alerts.length} current alert{alerts.length === 1 ? '' : 's'} in this session</span>
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
                            {', '}temperature: {alert.temp != null ? `${Number(alert.temp).toFixed(1)} °C` : 'Unavailable'}
                          </p>
                          <p className="alert-time">{alert.timestamp}</p>
                        </div>
                      </div>
                      <button
                        type="button"
                        aria-label={alert.status === 'Acknowledged'
                          ? `Reviewed: alert for ${alert.room_name} already acknowledged`
                          : `Acknowledge alert for ${alert.room_name}`}
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
