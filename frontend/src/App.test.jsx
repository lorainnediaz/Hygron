import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TooltipProvider } from '@radix-ui/react-tooltip'
import { App } from './App'
import { hourlyBuckets, humidBlocks } from './timelineData'
import { installDomShims, mockApi } from './test/mockApi'

installDomShims()

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

describe('top navigation', () => {
  it('switches pages and marks the current page', async () => {
    mockApi()
    renderApp()
    const nav = await screen.findByRole('navigation', { name: 'Main navigation' })
    const dashboard = within(nav).getByRole('button', { name: 'Dashboard' })
    expect(dashboard.getAttribute('aria-current')).toBe('page')

    await userEvent.click(within(nav).getByRole('button', { name: 'Methodology' }))
    expect(await screen.findByRole('heading', { name: 'Methodology' })).toBeTruthy()
    expect(within(nav).getByRole('button', { name: 'Methodology' }).getAttribute('aria-current')).toBe('page')
    expect(dashboard.getAttribute('aria-current')).toBeNull()

    await userEvent.click(dashboard)
    expect(await screen.findByRole('heading', { name: 'Room overview' })).toBeTruthy()
  })

  it('links to the IoT simulator from the end of Methodology instead of a separate tab', async () => {
    mockApi()
    renderApp()
    const nav = await screen.findByRole('navigation', { name: 'Main navigation' })
    expect(within(nav).queryByRole('button', { name: /IoT Workbench/ })).toBeNull()

    await userEvent.click(within(nav).getByRole('button', { name: 'Methodology' }))
    const link = await screen.findByRole('link', { name: /Open IoT simulator/ })
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toContain('noreferrer')
  })
})

describe('room timeline helpers', () => {
  const HOUR = 60 * 60 * 1000
  const end = Date.parse('2026-08-30T03:00:00+08:00')
  const at = (hoursBeforeEnd, rh) => ({ timestamp: new Date(end - hoursBeforeEnd * HOUR + 60_000).toISOString(), rh })

  it('puts readings in hourly buckets and leaves empty hours as no data', () => {
    const buckets = hourlyBuckets([at(1, 70), at(1, 90), at(3, 60)], end, 4)
    expect(buckets[3]).toEqual({ mean: 80, peak: 90 })
    expect(buckets[2]).toBeNull()
    expect(buckets[1]).toEqual({ mean: 60, peak: 60 })
    expect(buckets[0]).toBeNull()
  })

  it('merges consecutive humid hours into one block with the peak value', () => {
    const blocks = humidBlocks([{ mean: 70, peak: 72 }, { mean: 82, peak: 85 }, { mean: 88, peak: 93 }, null, { mean: 81, peak: 81 }])
    expect(blocks).toEqual([{ start: 1, end: 2, peak: 93 }, { start: 4, end: 4, peak: 81 }])
  })
})
