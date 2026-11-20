import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TooltipProvider } from '@radix-ui/react-tooltip'
import axe from 'axe-core'
import { App } from './App'
import { riskMeanings } from './risk'
import { installDomShims, mockApi, UNAVAILABLE_REASON } from './test/mockApi'

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

async function axeViolations(container) {
  // jsdom has no layout engine, so color contrast is checked separately in contrast.test.js.
  const result = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } })
  return result.violations.map((violation) => `${violation.id}: ${violation.nodes.map((node) => node.target.join(' ')).join(', ')}`)
}

describe('accessibility semantics', () => {
  it('has no axe violations on the loaded dashboard', async () => {
    mockApi()
    const { container } = renderApp()
    await screen.findByRole('heading', { name: 'Room 101 details' })
    await screen.findByText(/Relative to the latest simulated reading/)
    expect(await axeViolations(container)).toEqual([])
  })

  it('has no axe violations with an Unavailable room selected', async () => {
    mockApi()
    const { container } = renderApp()
    await userEvent.click(await screen.findByRole('button', { name: /^Room 103:/ }))
    await screen.findByRole('heading', { name: 'Room 103 details' })
    expect(await axeViolations(container)).toEqual([])
  })

  it('exposes room rows as pressed-state buttons whose names include the visible room label', async () => {
    mockApi()
    renderApp()
    const row = await screen.findByRole('button', { name: /^Room 102:/ })
    expect(row.getAttribute('aria-pressed')).toBe('false')
    expect(row.getAttribute('aria-label')).toContain('High risk')
    expect(row.getAttribute('aria-label')).toContain('action Inspect')
  })
})

describe('risk explanations', () => {
  it('explains every risk level next to its count', async () => {
    mockApi()
    renderApp()
    const list = await screen.findByRole('list')
    for (const meaning of Object.values(riskMeanings)) {
      expect(within(list).getByText(meaning)).toBeTruthy()
    }
    expect(screen.getByText(/do not confirm that mold is present/)).toBeTruthy()
  })

  it('shows why a room is Unavailable and does not present it as Low', async () => {
    mockApi()
    renderApp()
    const row = await screen.findByRole('button', { name: /^Room 103:/ })
    expect(row.getAttribute('aria-label')).toContain(`reason: ${UNAVAILABLE_REASON}`)
    expect(within(row).getByText('Review data')).toBeTruthy()
    await userEvent.click(row)
    expect(await screen.findByText(`Reason: ${UNAVAILABLE_REASON}`)).toBeTruthy()
    expect(await screen.findByText(`Outlook unavailable: ${UNAVAILABLE_REASON}`)).toBeTruthy()
  })

  it('explains why forecast confidence is unavailable', async () => {
    mockApi()
    renderApp()
    expect(await screen.findByText('How sure is this outlook?')).toBeTruthy()
    expect(screen.getByText(/checked against labeled data/)).toBeTruthy()
  })
})
