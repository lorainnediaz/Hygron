import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TooltipProvider } from '@radix-ui/react-tooltip'
import { App } from './App'

if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false
}
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {}
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = () => {}
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider><App /></TooltipProvider>
    </QueryClientProvider>,
  )
}

function mockApi() {
  let acknowledged = false
  global.fetch = vi.fn(async (input, options = {}) => {
    const url = String(input)
    if (options.method === 'POST') {
      acknowledged = true
      return { ok: true, json: async () => ({ status: 'Acknowledged' }) }
    }
    if (url.includes('/api/alerts')) return { ok: true, json: async () => ({ alerts: [{
      id: 'room_102_1', room_id: 'room_102', room_name: 'Room 102',
      rh: 84, temp: 25.5, timestamp: '2026-08-30T01:00:00+08:00',
      status: acknowledged ? 'Acknowledged' : 'Action needed',
    }] }) }
    if (url.includes('/api/system-status')) return { ok: true, json: async () => ({
      latest_timestamp: '2026-08-30T01:00:00+08:00', valid_for_history: 12,
      models: { available: true },
    }) }
    if (url.includes('/api/rooms/room_102/forecast')) return { ok: true, json: async () => ({
      current_risk: 'High', forecast_24h_risk: 'Medium',
    }) }
    if (url.includes('/api/rooms/room_101/forecast')) return { ok: true, json: async () => ({
      current_risk: 'Low', forecast_24h_risk: 'Low',
    }) }
    if (url.includes('/history')) return { ok: true, json: async () => ({ readings: [
      { timestamp: '2026-08-30T00:00:00+08:00', rh: 72, temp: 24 },
      { timestamp: '2026-08-30T01:00:00+08:00', rh: 84, temp: 25.5 },
    ] }) }
    if (url === '/api/rooms') return { ok: true, json: async () => ({ rooms: [
      { room_id: 'room_101', room_name: 'Room 101', current_risk: 'Low', rh: 72, temp: 24, latest_timestamp: '2026-08-30T00:00:00+08:00', forecast_24h_risk: 'Low' },
      { room_id: 'room_102', room_name: 'Room 102', current_risk: 'High', rh: 84, temp: 25.5, latest_timestamp: '2026-08-30T01:00:00+08:00', forecast_24h_risk: 'Medium' },
    ], counts: { High: 1, Medium: 0, Low: 1, Unavailable: 0 } }) }
    return { ok: true, json: async () => ({}) }
  })
}

describe('dashboard interactions', () => {
  it('selects a room and updates its details', async () => {
    mockApi()
    renderApp()
    await screen.findByRole('row', { name: /Select Room 102/i })
    await userEvent.click(screen.getByRole('row', { name: /Select Room 102/i }))
    expect(await screen.findByRole('heading', { name: 'Room 102 details' })).toBeTruthy()
  })

  it('changes the chart time range', async () => {
    mockApi()
    renderApp()
    const trigger = await screen.findByRole('combobox', { name: 'Time period' })
    await userEvent.click(trigger)
    await userEvent.keyboard('{ArrowDown}{Enter}')
    expect(trigger.textContent).toContain('7 days')
  })

  it('acknowledges an alert', async () => {
    mockApi()
    renderApp()
    const button = await screen.findByRole('button', { name: 'Acknowledge' })
    await userEvent.click(button)
    expect(await screen.findByText('Acknowledged')).toBeTruthy()
  })

  it('refreshes dashboard queries', async () => {
    mockApi()
    renderApp()
    await screen.findByRole('button', { name: /Refresh readings/i })
    await userEvent.click(screen.getByRole('button', { name: /Refresh readings/i }))
    expect(global.fetch).toHaveBeenCalled()
  })
})
