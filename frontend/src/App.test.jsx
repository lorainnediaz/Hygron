import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TooltipProvider } from '@radix-ui/react-tooltip'
import { App } from './App'

afterEach(() => cleanup())

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
}

function renderApp(queryClient = createQueryClient()) {
  return render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <App />
      </TooltipProvider>
    </QueryClientProvider>,
  )
}

describe('sidebar', () => {
  it('removes the sidebar and restores it with the floating control', async () => {
    const queryClient = createQueryClient()
    global.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({ rooms: [], counts: {}, alerts: [], valid_for_history: 0, models: { available: true } }),
    }))

    renderApp(queryClient)

    await userEvent.click(await screen.findByRole('button', { name: 'Expand sidebar' }))
    const collapse = await screen.findByRole('button', { name: 'Collapse sidebar' })
    await userEvent.click(collapse)
    await new Promise((resolve) => window.setTimeout(resolve, 340))
    expect(screen.queryByLabelText('Main navigation')).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: 'Expand sidebar' }))
    expect(await screen.findByLabelText('Main navigation')).not.toBeNull()
  })
})
