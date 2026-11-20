import { vi } from 'vitest'

export const UNAVAILABLE_REASON =
  'The 60-day history has missing or duplicate readings, so the model cannot run.'

const rooms = [
  { room_id: 'room_102', room_name: 'Room 102', current_risk: 'High', rh: 84, temp: 25.5, latest_timestamp: '2026-08-30T01:00:00+08:00', forecast_24h_risk: 'Medium' },
  { room_id: 'room_101', room_name: 'Room 101', current_risk: 'Low', rh: 72, temp: 24, latest_timestamp: '2026-08-30T00:00:00+08:00', forecast_24h_risk: 'Low' },
  {
    room_id: 'room_103', room_name: 'Room 103', current_risk: 'Unavailable', rh: 81, temp: 25, latest_timestamp: '2026-08-30T01:00:00+08:00',
    forecast_24h_risk: 'Unavailable', unavailable_code: 'history_gaps', unavailable_reason: UNAVAILABLE_REASON,
  },
]

const json = (body) => ({ ok: true, json: async () => body })

/** Install a fetch mock that mimics the FastAPI routes used by the dashboard. */
export function mockApi() {
  let acknowledged = false
  global.fetch = vi.fn(async (input, options = {}) => {
    const url = String(input)
    if (options.method === 'POST') {
      acknowledged = true
      return json({ status: 'Acknowledged' })
    }
    if (url.includes('/api/alerts')) return json({ alerts: [{
      id: 'room_102_1', room_id: 'room_102', room_name: 'Room 102',
      rh: 84, temp: 25.5, timestamp: '2026-08-30T01:00:00+08:00',
      status: acknowledged ? 'Acknowledged' : 'Action needed',
    }] })
    if (url.includes('/api/system-status')) return json({
      latest_timestamp: '2026-08-30T01:00:00+08:00', valid_for_history: 12,
      models: { available: true }, alert_acknowledgment_retention_days: 90,
    })
    const forecastMatch = url.match(/\/api\/rooms\/(room_\d+)\/forecast/)
    if (forecastMatch) {
      const room = rooms.find((item) => item.room_id === forecastMatch[1])
      return json({
        current_risk: room.current_risk,
        forecast_24h_risk: room.forecast_24h_risk,
        unavailable_reason: room.unavailable_reason,
        confidence: 'Unavailable',
        confidence_reason: "The model's scores haven't been checked against labeled data, so no percentage is shown.",
      })
    }
    if (url.includes('/history')) return json({ readings: [
      { timestamp: '2026-08-30T00:00:00+08:00', rh: 72, temp: 24 },
      { timestamp: '2026-08-30T01:00:00+08:00', rh: 84, temp: 25.5 },
    ] })
    if (url === '/api/rooms') return json({ rooms, counts: { High: 1, Medium: 0, Low: 1, Unavailable: 1 } })
    return json({})
  })
}

/** jsdom lacks pointer-capture and scrollIntoView, which Radix Select calls. */
export function installDomShims() {
  if (!Element.prototype.hasPointerCapture) Element.prototype.hasPointerCapture = () => false
  if (!Element.prototype.setPointerCapture) Element.prototype.setPointerCapture = () => {}
  if (!Element.prototype.releasePointerCapture) Element.prototype.releasePointerCapture = () => {}
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  // Radix Tooltip measures its trigger when it opens on keyboard focus.
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
}
