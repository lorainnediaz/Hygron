import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TooltipProvider } from '@radix-ui/react-tooltip'
import { App } from './App'
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

describe('dashboard interactions', () => {
  it('selects a room and updates its details', async () => {
    mockApi()
    renderApp()
    await userEvent.click(await screen.findByRole('button', { name: /^Room 102:/ }))
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
    const button = await screen.findByRole('button', { name: 'Acknowledge alert for Room 102' })
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
