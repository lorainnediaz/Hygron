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

/** Press Tab until the focused element matches, proving it is reachable in tab order. */
async function tabTo(user, matches, maxTabs = 60) {
  for (let i = 0; i < maxTabs; i += 1) {
    await user.tab()
    if (document.activeElement && matches(document.activeElement)) return document.activeElement
  }
  throw new Error('Element was not reachable with the Tab key')
}

const named = (pattern) => (element) => pattern.test(element.getAttribute('aria-label') || element.textContent || '')

describe('keyboard-only primary tasks', () => {
  it('offers the skip link as the first tab stop', async () => {
    mockApi()
    renderApp()
    await screen.findByRole('button', { name: /^Room 102:/ })
    const user = userEvent.setup()
    await user.tab()
    expect(document.activeElement.textContent).toBe('Skip to dashboard content')
  })

  it('opens the sidebar and navigates to Methodology', async () => {
    mockApi()
    renderApp()
    await screen.findByRole('button', { name: /^Room 102:/ })
    const user = userEvent.setup()
    await tabTo(user, named(/^Expand sidebar$/))
    await user.keyboard('{Enter}')
    await tabTo(user, named(/^Methodology$/))
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('heading', { name: 'Methodology' })).toBeTruthy()
  })

  it('inspects the priority room and moves focus to its details', async () => {
    mockApi()
    renderApp()
    await screen.findByRole('button', { name: /^Room 102:/ })
    const user = userEvent.setup()
    await tabTo(user, named(/^Inspect room$/))
    await user.keyboard('{Enter}')
    const heading = await screen.findByRole('heading', { name: 'Room 102 details' })
    await vi.waitFor(() => expect(document.activeElement).toBe(heading))
  })

  it('selects a room from the list with the keyboard', async () => {
    mockApi()
    renderApp()
    await screen.findByRole('button', { name: /^Room 103:/ })
    const user = userEvent.setup()
    const row = await tabTo(user, named(/^Room 103:/))
    await user.keyboard(' ')
    expect(row.getAttribute('aria-pressed')).toBe('true')
    expect(await screen.findByRole('heading', { name: 'Room 103 details' })).toBeTruthy()
  })

  it('changes the history period with the keyboard', async () => {
    mockApi()
    renderApp()
    const trigger = await screen.findByRole('combobox', { name: 'Time period' })
    const user = userEvent.setup()
    await tabTo(user, (element) => element === trigger)
    await user.keyboard('{Enter}')
    await user.keyboard('{ArrowDown}{Enter}')
    expect(trigger.textContent).toContain('7 days')
  })

  it('reaches the chart text alternative and forecast limitations', async () => {
    mockApi()
    renderApp()
    await screen.findByText('Chart text alternative')
    const user = userEvent.setup()
    await tabTo(user, (element) => element.tagName === 'SUMMARY' && element.textContent === 'Chart text alternative')
    await tabTo(user, (element) => element.tagName === 'SUMMARY' && element.textContent === 'Forecast limitations')
  })

  it('acknowledges an alert with the keyboard', async () => {
    mockApi()
    renderApp()
    await screen.findByRole('button', { name: 'Acknowledge alert for Room 102' })
    const user = userEvent.setup()
    await tabTo(user, named(/^Acknowledge alert for Room 102$/))
    await user.keyboard('{Enter}')
    expect(await screen.findByText('Acknowledged')).toBeTruthy()
  })

  it('refreshes readings with the keyboard', async () => {
    mockApi()
    renderApp()
    await screen.findByRole('button', { name: /Refresh readings/ })
    const user = userEvent.setup()
    const callsBefore = global.fetch.mock.calls.length
    await tabTo(user, named(/Refresh readings/))
    await user.keyboard('{Enter}')
    await vi.waitFor(() => expect(global.fetch.mock.calls.length).toBeGreaterThan(callsBefore))
  })
})
