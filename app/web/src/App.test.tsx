import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state before the fetch resolves', () => {
    ;(fetch as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}))
    render(<App />)
    expect(screen.getByRole('status')).toHaveTextContent(/loading/i)
  })

  it('renders the profile once loaded', async () => {
    ;(fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'placeholder',
        display_name: 'Demo Friend',
        bio: 'A placeholder bio',
      }),
    })
    render(<App />)
    await waitFor(() => expect(screen.getByText('Demo Friend')).toBeInTheDocument())
    expect(screen.getByText('A placeholder bio')).toBeInTheDocument()
  })

  it('shows an error state when the fetch fails', async () => {
    ;(fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    })
    render(<App />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert')).toHaveTextContent(/could not load profile/i)
  })
})
