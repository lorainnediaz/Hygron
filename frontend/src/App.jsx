import { useMemo, useState } from 'react'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { motion, useReducedMotion } from 'motion/react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import * as SelectPrimitive from '@radix-ui/react-select'
import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleMinus,
  Cpu,
  Gauge,
  Info,
  LayoutDashboard,
  RefreshCw,
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
import { CountUp, HumidityBar } from './visuals'
import { RoomTimeline } from './timeline'
import { TIMELINE_HOURS } from './timelineData'

const API = '/api'
const RISK_ORDER = ['High', 'Medium', 'Low', 'Unavailable']
const PAGES = [
  ['Dashboard', LayoutDashboard],
  ['Methodology', Info],
  ['IoT Workbench', Cpu],
]

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

function Panel({ index, className = '', title, titleId, actions, children, ...rest }) {
  return (
    <section className={`panel reveal ${className}`} style={{ '--i': index }} aria-labelledby={titleId} {...rest}>
      <div className="panel-head">
        <h2 className="panel-title" id={titleId}>{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  )
}

/** Hours-based tick labels: time of day for one day, date for longer ranges. */
function formatTick(value, hours) {
  const date = new Date(value)
  return hours <= 24
    ? date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function formatStamp(value) {
  if (!value) return 'Unavailable'
  return new Date(value).toLocaleString([], { month: 'long', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function App() {
  const [page, setPage] = useState('Dashboard')
  const [selectedRoom, setSelectedRoom] = useState('room_101')
  const [hours, setHours] = useState(24)
  const queryClient = useQueryClient()
  const reduceMotion = useReducedMotion()

  const roomsQuery = useQuery({ queryKey: ['rooms'], queryFn: () => fetchJson('/rooms') })
  const alertsQuery = useQuery({ queryKey: ['alerts'], queryFn: () => fetchJson('/alerts') })
  const systemQuery = useQuery({ queryKey: ['system-status'], queryFn: () => fetchJson('/system-status') })
  const historyQuery = useQuery({
    queryKey: ['history', selectedRoom, hours],
    queryFn: () => fetchJson(`/rooms/${selectedRoom}/history?hours=${hours}`),
  })
  const forecastQuery = useQuery({
    queryKey: ['forecast', selectedRoom],
    queryFn: () => fetchJson(`/rooms/${selectedRoom}/forecast`),
  })

  const roomList = useMemo(() => roomsQuery.data?.rooms || [], [roomsQuery.data])
  const timelineQueries = useQueries({
    queries: roomList.map((room) => ({
      queryKey: ['history', room.room_id, TIMELINE_HOURS],
      queryFn: () => fetchJson(`/rooms/${room.room_id}/history?hours=${TIMELINE_HOURS}`),
    })),
  })
  const historyByRoom = {}
  roomList.forEach((room, index) => {
    historyByRoom[room.room_id] = timelineQueries[index]?.data?.readings || []
  })

  const counts = roomsQuery.data?.counts || {}
  const alerts = alertsQuery.data?.alerts || []
  const systemStatus = systemQuery.data
  const history = historyQuery.data?.readings || []
  const forecast = forecastQuery.data
  const chartStats = useMemo(() => {
    const readings = historyQuery.data?.readings || []
    const values = readings.map((reading) => Number(reading.rh)).filter(Number.isFinite)
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
  const outlookRisk = forecast?.forecast_24h_risk || selected?.forecast_24h_risk || 'Unavailable'
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
      queryClient.invalidateQueries({ queryKey: ['history'] }),
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

  const activeAlerts = alerts.filter((alert) => alert.status !== 'Acknowledged').length

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to dashboard content</a>

      <div className="frame">
        <header className="topbar">
          <div className="brand" aria-label="Hygron, environmental monitoring">
            <span className="brand-mark" aria-hidden="true" />
            <span className="brand-name">Hygron</span>
          </div>
          <nav className="tabs" aria-label="Main navigation">
            {PAGES.map(([name, Icon]) => (
              <button
                key={name}
                type="button"
                className={page === name ? 'tab active' : 'tab'}
                onClick={() => setPage(name)}
                aria-current={page === name ? 'page' : undefined}
              >
                <Icon size={15} aria-hidden="true" />
                {name}
              </button>
            ))}
          </nav>
          <div className="topbar-actions">
            <span className="prototype-chip">Prototype, simulated data</span>
            <TooltipPrimitive.Root>
              <TooltipPrimitive.Trigger asChild>
                <button
                  type="button"
                  className="refresh-button"
                  onClick={refreshDashboard}
                  disabled={roomsQuery.isFetching}
                >
                  <RefreshCw className="refresh-icon" size={16} aria-hidden="true" />
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
          </div>
        </header>

        <main className="main" id="main-content" tabIndex={-1}>
          {page !== 'Dashboard' ? (
            <section className="panel placeholder-page">
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
                  <p>Virtual BME680, virtual ESP32, Raspberry Pi gateway, simulated Internet, SQLite, FastAPI, then this React dashboard.</p>
                  <h2>Model limitation</h2>
                  <p>Hygron estimates simulated VTT-derived mold-growth risk. It does not detect or confirm physical mold.</p>
                </>
              )}
            </section>
          ) : (
            <>
              <div className="page-header">
                <h1>Room overview</h1>
                {systemStatus?.latest_timestamp && (
                  <span className="date-chip">
                    <CalendarClock size={15} aria-hidden="true" />
                    Latest reading {formatStamp(systemStatus.latest_timestamp)}
                  </span>
                )}
              </div>

              {error && (
                <div className="error-banner" role="alert">
                  <AlertTriangle size={18} aria-hidden="true" />
                  {error}
                </div>
              )}

              {loading ? (
                <div className="loading-card" role="status">Loading room monitoring data…</div>
              ) : (
                <div className="dashboard-grid">
                  <Panel
                    index={0}
                    className="span-12"
                    title="Room humidity, last 24 hours"
                    titleId="rooms-title"
                    actions={(
                      <div className="timeline-legend" aria-hidden="true">
                        <span><i className="legend-block" /> At or above 80% RH</span>
                        <span><i className="legend-nodata" /> No readings</span>
                      </div>
                    )}
                  >
                    <p className="panel-note">
                      Select a room to see its details. Blocks mark hours when the room&apos;s average humidity was at or above 80%.
                    </p>
                    <div role="group" aria-labelledby="rooms-title">
                      <RoomTimeline
                        rooms={roomList}
                        historyByRoom={historyByRoom}
                        selectedRoom={selectedRoom}
                        onSelect={setSelectedRoom}
                        riskStyles={riskStyles}
                        staffActions={staffActions}
                        rowLabel={roomRowLabel}
                      />
                    </div>
                  </Panel>

                  <Panel
                    index={1}
                    className="span-4"
                    title="Needs attention"
                    titleId="alerts-title"
                    actions={<span className="count-chip">{activeAlerts} active</span>}
                  >
                    {priority && (
                      <div
                        className={`priority-panel priority-${priority.current_risk.toLowerCase()}`}
                        style={{ '--risk': (riskStyles[priority.current_risk] || riskStyles.Unavailable).color }}
                        role="region"
                        aria-label="Recommended room"
                      >
                        <div className="priority-top">
                          <div className="priority-tile" aria-hidden="true">
                            <span>Room</span>
                            <strong>{priority.room_name.replace(/^Room\s*/i, '')}</strong>
                          </div>
                          <div className="priority-copy">
                            <p className="priority-eyebrow">
                              {priority.current_risk === 'High' && (
                                <AlertTriangle className="priority-warning-icon" size={15} strokeWidth={2.4} aria-hidden="true" />
                              )}
                              {priority.current_risk === 'High' ? 'Immediate attention required' : 'Room to check'}
                            </p>
                            <h3 className="sr-only">{priority.room_name}</h3>
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
                        </div>
                        <button type="button" onClick={() => showRoomDetails(priority.room_id)}>
                          {priority.current_risk === 'High' ? 'Inspect room' : 'View room'}
                          <ArrowRight size={15} aria-hidden="true" />
                        </button>
                      </div>
                    )}

                    <div className="alert-list-summary">
                      <p>
                        <strong>{activeAlerts} active</strong>
                        <span> out of {alerts.length} current alert{alerts.length === 1 ? '' : 's'} in this session</span>
                      </p>
                      <span>Acknowledgment records review; it does not confirm resolution.</span>
                    </div>
                    {alerts.length ? alerts.slice(0, 5).map((alert) => (
                      <article className={`alert-card ${alert.status === 'Acknowledged' ? 'acknowledged' : ''}`} key={alert.id}>
                        <div className="alert-main">
                          <span className="alert-status-icon" aria-hidden="true">
                            {alert.status === 'Acknowledged' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
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
                  </Panel>

                  {selected && (
                    <section className="panel reveal span-4" style={{ '--i': 2 }} aria-labelledby="room-details-title">
                      <div className="panel-head">
                        <h2 className="panel-title" id="room-details-title" tabIndex={-1}>{selected.room_name} details</h2>
                        <RiskBadge risk={selected.current_risk} size={13} />
                      </div>
                      <motion.div
                        key={selected.room_id}
                        className="detail-grid"
                        initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
                      >
                        <MetricCard
                          label="Estimated current risk"
                          value={selected.current_risk}
                          tone={selected.current_risk.toLowerCase()}
                          caption={selected.current_risk !== 'Unavailable' ? riskMeanings[selected.current_risk] : undefined}
                        />
                        <MetricCard
                          label="Relative humidity"
                          value={selected.rh != null ? `${Number(selected.rh).toFixed(1)}%` : 'Unavailable'}
                          tone={selected.rh >= 80 ? 'high' : ''}
                        >
                          <HumidityBar rh={selected.rh} />
                        </MetricCard>
                        <MetricCard
                          label="Temperature"
                          value={selected.temp != null ? `${Number(selected.temp).toFixed(1)} °C` : 'Unavailable'}
                        />
                        <MetricCard label="24-hour outlook" value={outlookRisk} tone={outlookRisk.toLowerCase()}>
                          <div className="outlook-pills">
                            <RiskBadge risk={selected.current_risk} size={12} />
                            <ArrowRight size={13} aria-hidden="true" />
                            <span className="sr-only">to</span>
                            <RiskBadge risk={outlookRisk} size={12} />
                          </div>
                        </MetricCard>
                      </motion.div>
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
                      <p className="disclaimer">
                        Latest simulated reading: {selected.latest_timestamp || 'Unavailable'}.
                        Risk estimates describe simulated VTT-derived conditions, not confirmed mold.
                      </p>
                    </section>
                  )}

                  {selected && (
                    <Panel
                      index={3}
                      className="span-4 outlook-section"
                      title="24-hour estimated outlook"
                      titleId="outlook-title"
                      actions={(
                        <span className={`outlook-direction direction-${forecastDirection.toLowerCase()}`}>
                          Direction: {forecastDirection}
                        </span>
                      )}
                    >
                      <div className="outlook-progress" aria-label={`${selected.current_risk} to ${forecast?.forecast_24h_risk || 'Unavailable'} in 24 hours`}>
                        <div>
                          <span>Current estimate</span>
                          <strong className={`outlook-risk risk-${selected.current_risk.toLowerCase()}`}>{selected.current_risk}</strong>
                        </div>
                        <ArrowRight className="outlook-arrow" size={20} aria-hidden="true" />
                        <div>
                          <span>In 24 hours</span>
                          <strong className={`outlook-risk risk-${(forecast?.forecast_24h_risk || 'Unavailable').toLowerCase()}`}>
                            {forecast?.forecast_24h_risk || 'Unavailable'}
                          </strong>
                        </div>
                      </div>
                      <p className="panel-note">
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
                    </Panel>
                  )}

                  <Panel index={4} className="span-4" title="Risk at a glance" titleId="risk-glance-title">
                    <p className="panel-note">
                      Levels are model estimates from each room&apos;s simulated humidity and temperature over the last 60 days,
                      using VTT-derived mold-growth categories. They do not confirm that mold is present.
                    </p>
                    <ul className="risk-rail">
                      {RISK_ORDER.map((risk) => {
                        const RiskIcon = riskStyles[risk].icon
                        return (
                          <li className={`risk-rail-item ${risk.toLowerCase()}`} key={risk} style={{ '--risk': riskStyles[risk].color }}>
                            <span className="risk-rail-icon" aria-hidden="true"><RiskIcon size={16} /></span>
                            <div>
                              <div className="risk-rail-head">
                                <strong><CountUp value={counts[risk] || 0} /></strong>
                                <span className="risk-rail-label">{risk}</span>
                              </div>
                              <p className="risk-meaning">{riskMeanings[risk]}</p>
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                  </Panel>

                  <section className="panel reveal span-8" style={{ '--i': 5 }} aria-labelledby="history-title">
                    <div className="panel-head">
                      <h2 className="panel-title" id="history-title">
                        {selected ? `${selected.room_name} humidity history` : 'Humidity history'}
                      </h2>
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
                        <div className="chart-visual" role="img" aria-label={`Humidity and temperature chart for ${selected?.room_name || 'the selected room'}`}>
                          <ResponsiveContainer width="100%" height={250}>
                            <ComposedChart data={history} margin={{ top: 8, right: 4, bottom: 0, left: -8 }}>
                              <defs>
                                <linearGradient id="rhFill" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="0%" stopColor="#4f8a7b" stopOpacity={0.28} />
                                  <stop offset="100%" stopColor="#4f8a7b" stopOpacity={0.02} />
                                </linearGradient>
                              </defs>
                              <CartesianGrid stroke="rgba(38,52,49,.08)" vertical={false} />
                              <XAxis
                                dataKey="timestamp"
                                tickFormatter={(value) => formatTick(value, hours)}
                                stroke="#56625e"
                                tick={{ fontSize: 12 }}
                                tickLine={false}
                                axisLine={false}
                                minTickGap={56}
                                interval="preserveStartEnd"
                              />
                              <YAxis
                                domain={[chartStats?.floor ?? 0, 100]}
                                stroke="#56625e"
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
                                stroke="#4f8a7b"
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
                              <ReferenceDot x={history.at(-1)?.timestamp} y={history.at(-1)?.rh} r={5} fill="#a8423a" stroke="#fff" strokeWidth={2} />
                            </ComposedChart>
                          </ResponsiveContainer>
                        </div>
                        {chartStats && (
                          <details className="chart-text-alternative">
                            <summary>Chart text alternative</summary>
                            <p>
                              For {selected?.room_name || 'the selected room'}, {history.length} displayed simulated readings are shown.
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
                  </section>
                </div>
              )}

              {systemStatus && (
                <footer className="system-footer">
                  <span>Asia/Manila</span>
                  <span>{systemStatus.valid_for_history} valid summaries</span>
                  <span>{systemStatus.models.available ? 'Models available' : 'Models unavailable'}</span>
                </footer>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  )
}

export default App
