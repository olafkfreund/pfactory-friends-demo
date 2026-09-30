/**
 * Component tests for the MyFriends web UI (plan step 5).
 *
 * Each test describes one user-visible behaviour; fetch is mocked globally
 * per test so the components never hit a real network.
 *
 * Tests are ordered to match the flows in the spec:
 *   1. Initial load (profile tab)
 *   2. Availability toggle
 *   3. Discovery tab
 *   4. Connect button
 *   5. Messages tab (empty state, accept, pending)
 *   6. Send message
 *   7. Block
 *   8. Report
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ME = { id: 'placeholder', display_name: 'Demo Friend', bio: 'A placeholder bio' }

/** Build a mock fetch response. */
function ok(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body })
}
function fail(status = 500) {
  return Promise.resolve({ ok: false, status, json: async () => ({}) })
}

type FetchMock = ReturnType<typeof vi.fn>

// ---------------------------------------------------------------------------
// Initial load — profile tab
// ---------------------------------------------------------------------------

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state before the fetch resolves', () => {
    ;(fetch as FetchMock).mockReturnValue(new Promise(() => {}))
    render(<App />)
    expect(screen.getByRole('status')).toHaveTextContent(/loading/i)
  })

  it('renders the profile once loaded', async () => {
    ;(fetch as FetchMock).mockResolvedValue({
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
    ;(fetch as FetchMock).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    })
    render(<App />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert')).toHaveTextContent(/could not load profile/i)
  })

  // -------------------------------------------------------------------------
  // Profile tab — availability toggle (AC#2)
  // -------------------------------------------------------------------------

  it('renders the availability toggle unchecked by default', async () => {
    ;(fetch as FetchMock).mockResolvedValueOnce(ok(ME))
    render(<App />)
    await waitFor(() => screen.getByLabelText('Open to new friends'))
    const toggle = screen.getByLabelText('Open to new friends')
    expect(toggle).not.toBeChecked()
  })

  it('sends PATCH when availability toggle is clicked', async () => {
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME)) // getMe
      .mockResolvedValueOnce(ok({})) // toggleAvailability
    render(<App />)
    await waitFor(() => screen.getByLabelText('Open to new friends'))
    fireEvent.click(screen.getByLabelText('Open to new friends'))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/profiles/placeholder/availability'),
        expect.objectContaining({ method: 'PATCH' }),
      ),
    )
  })

  it('checks the toggle after a successful availability update', async () => {
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME)) // getMe
      .mockResolvedValueOnce(ok({})) // toggleAvailability
    render(<App />)
    await waitFor(() => screen.getByLabelText('Open to new friends'))
    const toggle = screen.getByLabelText('Open to new friends')
    fireEvent.click(toggle)
    await waitFor(() => expect(toggle).toBeChecked())
  })

  it('shows an error message when the availability toggle fails', async () => {
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME)) // getMe
      .mockResolvedValueOnce(fail(500)) // toggleAvailability
    render(<App />)
    await waitFor(() => screen.getByLabelText('Open to new friends'))
    fireEvent.click(screen.getByLabelText('Open to new friends'))
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert')).toHaveTextContent(/failed to update availability/i)
  })

  // -------------------------------------------------------------------------
  // Create / edit profile form (AC#19: create a profile step)
  // -------------------------------------------------------------------------

  it('renders an "Edit profile" button on the profile tab', async () => {
    ;(fetch as FetchMock).mockResolvedValueOnce(ok(ME))
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /edit profile/i }))
    expect(screen.getByRole('button', { name: /edit profile/i })).toBeInTheDocument()
  })

  it('shows the create-profile form when "Edit profile" is clicked', async () => {
    ;(fetch as FetchMock).mockResolvedValueOnce(ok(ME))
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /edit profile/i }))
    fireEvent.click(screen.getByRole('button', { name: /edit profile/i }))
    expect(screen.getByRole('form', { name: /create profile/i })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /display name/i })).toBeInTheDocument()
    expect(screen.getByRole('spinbutton', { name: /age/i })).toBeInTheDocument()
  })

  it('sends POST /profiles when the profile form is saved', async () => {
    const savedProfile = { id: 'placeholder', display_name: 'Alice', bio: 'Hello!' }
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME))          // getMe
      .mockResolvedValueOnce(ok(savedProfile)) // createProfile
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /edit profile/i }))
    fireEvent.click(screen.getByRole('button', { name: /edit profile/i }))

    const nameInput = screen.getByRole('textbox', { name: /display name/i })
    fireEvent.change(nameInput, { target: { value: 'Alice' } })

    fireEvent.click(screen.getByRole('button', { name: /save profile/i }))

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/profiles',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('Alice'),
        }),
      ),
    )
  })

  it('updates the displayed name after a successful profile save', async () => {
    const savedProfile = { id: 'placeholder', display_name: 'Alice', bio: 'New bio' }
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME))          // getMe
      .mockResolvedValueOnce(ok(savedProfile)) // createProfile
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /edit profile/i }))
    fireEvent.click(screen.getByRole('button', { name: /edit profile/i }))

    const nameInput = screen.getByRole('textbox', { name: /display name/i })
    fireEvent.change(nameInput, { target: { value: 'Alice' } })
    fireEvent.click(screen.getByRole('button', { name: /save profile/i }))

    await waitFor(() => expect(screen.getByText('Alice')).toBeInTheDocument())
    // Form should be hidden after save
    expect(screen.queryByRole('form', { name: /create profile/i })).not.toBeInTheDocument()
  })

  it('shows an error when the profile save fails', async () => {
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME))    // getMe
      .mockResolvedValueOnce(fail(422)) // createProfile fails
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /edit profile/i }))
    fireEvent.click(screen.getByRole('button', { name: /edit profile/i }))
    fireEvent.click(screen.getByRole('button', { name: /save profile/i }))
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert')).toHaveTextContent(/could not save profile/i)
  })

  // -------------------------------------------------------------------------
  // Discover tab navigation
  // -------------------------------------------------------------------------

  it('navigates to the discovery tab when Discover is clicked', async () => {
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME)) // getMe
      .mockResolvedValueOnce(ok([])) // getDiscovery — empty list
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /discover/i }))
    fireEvent.click(screen.getByRole('button', { name: /discover/i }))
    await waitFor(() => screen.getByRole('region', { name: 'Discovery' }))
    expect(screen.getByRole('region', { name: 'Discovery' })).toBeInTheDocument()
  })

  it('shows a loading indicator while discovery results are fetched', async () => {
    // Keep the discovery fetch pending indefinitely so we can see the loading state.
    let resolveDiscovery!: (v: unknown) => void
    const pending = new Promise((res) => { resolveDiscovery = res })

    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME)) // getMe
      .mockReturnValueOnce(pending) // getDiscovery — never resolves
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /discover/i }))
    fireEvent.click(screen.getByRole('button', { name: /discover/i }))
    await waitFor(() => screen.getByRole('status'))
    expect(screen.getByRole('status')).toHaveTextContent(/loading discovery/i)

    // Clean up: resolve so the component unmounts without open timers.
    resolveDiscovery({ ok: true, json: async () => [] })
  })

  it('shows the empty-state message when no one is nearby', async () => {
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME)) // getMe
      .mockResolvedValueOnce(ok([])) // getDiscovery — empty
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /discover/i }))
    fireEvent.click(screen.getByRole('button', { name: /discover/i }))
    await waitFor(() => screen.getByText(/nobody nearby/i))
  })

  it('lists discovery results by display name', async () => {
    const results = [
      {
        profile: {
          id: 'alice',
          display_name: 'Alice',
          bio: 'Hi',
          age: 25,
          interests: ['hiking'],
          activities: [],
          open_to_friends: true,
        },
        score: 1.0,
        shared_interests: ['hiking'],
        shared_activities: [],
      },
    ]
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME)) // getMe
      .mockResolvedValueOnce(ok(results)) // getDiscovery
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /discover/i }))
    fireEvent.click(screen.getByRole('button', { name: /discover/i }))
    await waitFor(() => screen.getByText('Alice'))
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText(/hiking/i)).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Connect button — AC#5
  // -------------------------------------------------------------------------

  it('sends a POST /connections request when Connect is clicked', async () => {
    const results = [
      {
        profile: {
          id: 'alice',
          display_name: 'Alice',
          bio: 'Hi',
          age: 25,
          interests: [],
          activities: [],
          open_to_friends: true,
        },
        score: 0.5,
        shared_interests: [],
        shared_activities: [],
      },
    ]
    const conn = { id: 'conn-1', requester_id: 'placeholder', recipient_id: 'alice', status: 'pending' }
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME)) // getMe
      .mockResolvedValueOnce(ok(results)) // getDiscovery
      .mockResolvedValueOnce(ok(conn)) // sendConnectionRequest
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /discover/i }))
    fireEvent.click(screen.getByRole('button', { name: /discover/i }))
    await waitFor(() => screen.getByRole('button', { name: /send connection request to alice/i }))
    fireEvent.click(screen.getByRole('button', { name: /send connection request to alice/i }))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/connections'),
        expect.objectContaining({ method: 'POST' }),
      ),
    )
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /send connection request to alice/i }),
      ).toBeDisabled(),
    )
  })

  // -------------------------------------------------------------------------
  // Messages tab
  // -------------------------------------------------------------------------

  it('navigates to the messages tab when Messages is clicked', async () => {
    ;(fetch as FetchMock).mockResolvedValueOnce(ok(ME))
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /messages/i }))
    fireEvent.click(screen.getByRole('button', { name: /messages/i }))
    expect(screen.getByRole('region', { name: 'Messages' })).toBeInTheDocument()
  })

  it('shows the empty-connections message when there are no connections', async () => {
    ;(fetch as FetchMock).mockResolvedValueOnce(ok(ME))
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /messages/i }))
    fireEvent.click(screen.getByRole('button', { name: /messages/i }))
    expect(screen.getByText(/no connections yet/i)).toBeInTheDocument()
  })

  it('calls POST /connections/{id}/accept when a request is accepted', async () => {
    const acceptedConn = {
      id: 'conn-abc',
      requester_id: 'alice',
      recipient_id: 'placeholder',
      status: 'accepted',
    }
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME)) // getMe
      .mockResolvedValueOnce(ok(acceptedConn)) // acceptConnection
    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /messages/i }))
    fireEvent.click(screen.getByRole('button', { name: /messages/i }))

    const input = screen.getByRole('textbox', { name: /connection id to accept/i })
    fireEvent.change(input, { target: { value: 'conn-abc' } })
    fireEvent.click(screen.getByRole('button', { name: /accept connection request/i }))

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/connections/conn-abc/accept'),
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })

  // -------------------------------------------------------------------------
  // Messaging (AC#6)
  // -------------------------------------------------------------------------

  it('shows a message conversation when an accepted connection is clicked', async () => {
    // Mocks queued in call order: getMe → acceptConnection → getMessages
    const acceptedConn = {
      id: 'conn-1',
      requester_id: 'placeholder',
      recipient_id: 'bob',
      status: 'accepted',
    }
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME))           // 1. getMe on mount
      .mockResolvedValueOnce(ok(acceptedConn)) // 2. acceptConnection when Accept is clicked
      .mockResolvedValueOnce(ok([]))           // 3. getMessages when conversation opens

    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /messages/i }))
    fireEvent.click(screen.getByRole('button', { name: /messages/i }))

    const input = screen.getByRole('textbox', { name: /connection id to accept/i })
    fireEvent.change(input, { target: { value: 'conn-1' } })
    fireEvent.click(screen.getByRole('button', { name: /accept connection request/i }))

    await waitFor(() => screen.getByRole('button', { name: /open conversation with bob/i }))
    fireEvent.click(screen.getByRole('button', { name: /open conversation with bob/i }))

    await waitFor(() => screen.getByRole('textbox', { name: /message input/i }))
    expect(screen.getByRole('textbox', { name: /message input/i })).toBeInTheDocument()
  })

  it('sends POST /messages when the Send button is clicked', async () => {
    // Mocks queued in call order: getMe → acceptConnection → getMessages → sendMessage
    const acceptedConn = {
      id: 'conn-1',
      requester_id: 'placeholder',
      recipient_id: 'bob',
      status: 'accepted',
    }
    const outMsg = {
      id: 'msg-0',
      sender_id: 'placeholder',
      recipient_id: 'bob',
      body: 'Hello!',
    }
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME))           // 1. getMe on mount
      .mockResolvedValueOnce(ok(acceptedConn)) // 2. acceptConnection
      .mockResolvedValueOnce(ok([]))           // 3. getMessages
      .mockResolvedValueOnce(ok(outMsg))       // 4. sendMessage

    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /messages/i }))
    fireEvent.click(screen.getByRole('button', { name: /messages/i }))

    const acceptInput = screen.getByRole('textbox', { name: /connection id to accept/i })
    fireEvent.change(acceptInput, { target: { value: 'conn-1' } })
    fireEvent.click(screen.getByRole('button', { name: /accept connection request/i }))

    await waitFor(() => screen.getByRole('button', { name: /open conversation with bob/i }))
    fireEvent.click(screen.getByRole('button', { name: /open conversation with bob/i }))

    await waitFor(() => screen.getByRole('textbox', { name: /message input/i }))
    const msgInput = screen.getByRole('textbox', { name: /message input/i })
    fireEvent.change(msgInput, { target: { value: 'Hello!' } })
    fireEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/messages',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('Hello!'),
        }),
      ),
    )
  })

  // -------------------------------------------------------------------------
  // Block — AC#7 / P5
  // -------------------------------------------------------------------------

  it('sends POST /blocks when Block is clicked', async () => {
    // Mocks queued in call order: getMe → acceptConnection → getMessages → blockUser
    const acceptedConn = {
      id: 'conn-1',
      requester_id: 'placeholder',
      recipient_id: 'carol',
      status: 'accepted',
    }
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME))           // 1. getMe on mount
      .mockResolvedValueOnce(ok(acceptedConn)) // 2. acceptConnection
      .mockResolvedValueOnce(ok([]))           // 3. getMessages when conversation opens
      .mockResolvedValueOnce({ ok: true, status: 204, json: async () => null }) // 4. blockUser

    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /messages/i }))
    fireEvent.click(screen.getByRole('button', { name: /messages/i }))

    const acceptInput = screen.getByRole('textbox', { name: /connection id to accept/i })
    fireEvent.change(acceptInput, { target: { value: 'conn-1' } })
    fireEvent.click(screen.getByRole('button', { name: /accept connection request/i }))

    await waitFor(() => screen.getByRole('button', { name: /open conversation with carol/i }))
    fireEvent.click(screen.getByRole('button', { name: /open conversation with carol/i }))

    await waitFor(() => screen.getByRole('button', { name: /block carol/i }))
    fireEvent.click(screen.getByRole('button', { name: /block carol/i }))

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/blocks',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('carol'),
        }),
      ),
    )
  })

  // -------------------------------------------------------------------------
  // Report — AC#8 / P5
  // -------------------------------------------------------------------------

  it('opens the report dialog and sends POST /reports on submit', async () => {
    const results = [
      {
        profile: {
          id: 'dave',
          display_name: 'Dave',
          bio: 'Hey',
          age: 30,
          interests: [],
          activities: [],
          open_to_friends: true,
        },
        score: 0.0,
        shared_interests: [],
        shared_activities: [],
      },
    ]
    ;(fetch as FetchMock)
      .mockResolvedValueOnce(ok(ME)) // getMe
      .mockResolvedValueOnce(ok(results)) // getDiscovery
      .mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({}) }) // submitReport

    render(<App />)
    await waitFor(() => screen.getByRole('button', { name: /discover/i }))
    fireEvent.click(screen.getByRole('button', { name: /discover/i }))

    await waitFor(() => screen.getByRole('button', { name: /report dave/i }))
    fireEvent.click(screen.getByRole('button', { name: /report dave/i }))

    expect(screen.getByRole('dialog', { name: /report/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /submit report/i }))

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/reports',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('dave'),
        }),
      ),
    )
    await waitFor(() => screen.getByRole('dialog', { name: /report submitted/i }))
  })
})
