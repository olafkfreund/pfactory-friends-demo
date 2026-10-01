/**
 * MyFriends web UI — plan step 5.
 *
 * Three-tab single-page application:
 *   Profile    — display name, bio, "open to new friends" toggle (AC#2).
 *   Discover   — discovery results with Connect / Report actions (AC#3–AC#7).
 *   Messages   — pending and accepted connections; messaging, block, report
 *                (AC#6, AC#7, AC#8).
 *
 * All API calls go through ./api.ts; no raw fetch calls in this file.
 * Auth (Keycloak via oauth2-proxy) is wired at the deployment layer; the
 * /profiles/me endpoint returns a placeholder until step 2 adds real session
 * binding.
 */

import { useCallback, useEffect, useState } from 'react'
import {
  acceptConnection,
  blockUser,
  createProfile,
  getDiscovery,
  getMe,
  getMessages,
  sendConnectionRequest,
  sendMessage,
  submitReport,
  toggleAvailability,
} from './api.ts'
import type { Connection, DiscoveryResult, MeProfile, Message, ReportReason } from './types.ts'

// ---------------------------------------------------------------------------
// Local state types
// ---------------------------------------------------------------------------

type Tab = 'profile' | 'discovery' | 'messages'
type AvailabilityStatus = 'idle' | 'toggling' | 'error'
type SendStatus = 'idle' | 'sending' | 'sent' | 'error'
type AcceptStatus = 'idle' | 'accepting' | 'error'

// ---------------------------------------------------------------------------
// Create / edit profile form (AC#19: create a profile step)
// ---------------------------------------------------------------------------

type EditProfileFormProps = {
  profileId: string
  initialDisplayName?: string
  initialBio?: string
  onSaved: (updated: MeProfile) => void
}

function EditProfileForm({ profileId, initialDisplayName = '', initialBio = '', onSaved }: EditProfileFormProps) {
  const [displayName, setDisplayName] = useState(initialDisplayName)
  const [bio, setBio] = useState(initialBio)
  const [age, setAge] = useState(18)
  const [interestsRaw, setInterestsRaw] = useState('')
  const [status, setStatus] = useState<'idle' | 'saving' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  const handleSave = useCallback(async () => {
    setStatus('saving')
    try {
      const interests = interestsRaw
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
      const updated = await createProfile({
        id: profileId,
        display_name: displayName,
        bio,
        interests,
        activities: [],
        age,
        open_to_friends: false,
      })
      setStatus('idle')
      onSaved(updated)
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Unknown error')
      setStatus('error')
    }
  }, [profileId, displayName, bio, age, interestsRaw, onSaved])

  return (
    <form
      aria-label="Create profile"
      onSubmit={(e) => {
        e.preventDefault()
        void handleSave()
      }}
    >
      <div>
        <label htmlFor="edit-display-name">Display name</label>
        <input
          id="edit-display-name"
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          aria-label="Display name"
          required
        />
      </div>
      <div>
        <label htmlFor="edit-age">Age</label>
        <input
          id="edit-age"
          type="number"
          min={16}
          max={120}
          value={age}
          onChange={(e) => setAge(Number(e.target.value))}
          aria-label="Age"
          required
        />
      </div>
      <div>
        <label htmlFor="edit-bio">Bio</label>
        <textarea
          id="edit-bio"
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          aria-label="Bio"
        />
      </div>
      <div>
        <label htmlFor="edit-interests">Interests (comma-separated, up to 10)</label>
        <input
          id="edit-interests"
          type="text"
          value={interestsRaw}
          onChange={(e) => setInterestsRaw(e.target.value)}
          aria-label="Interests"
          placeholder="hiking, reading, cooking"
        />
      </div>
      {status === 'error' && (
        <p role="alert">Could not save profile: {errorMessage}</p>
      )}
      <button type="submit" disabled={status === 'saving'} aria-label="Save profile">
        {status === 'saving' ? 'Saving...' : 'Save profile'}
      </button>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Profile tab — display, availability toggle (AC#2), and edit form (AC#19)
// ---------------------------------------------------------------------------

type ProfileTabProps = {
  profile: MeProfile
  openToFriends: boolean
  availabilityStatus: AvailabilityStatus
  onToggle: (open: boolean) => void
  onProfileUpdated: (updated: MeProfile) => void
}

function ProfileTab({ profile, openToFriends, availabilityStatus, onToggle, onProfileUpdated }: ProfileTabProps) {
  const [showEdit, setShowEdit] = useState(false)

  return (
    <section aria-label="Profile">
      <h1>{profile.display_name}</h1>
      <p>{profile.bio}</p>
      <div>
        <label htmlFor="availability-toggle">Open to new friends</label>
        <input
          id="availability-toggle"
          type="checkbox"
          role="switch"
          checked={openToFriends}
          onChange={(e) => onToggle(e.target.checked)}
          disabled={availabilityStatus === 'toggling'}
          aria-label="Open to new friends"
        />
      </div>
      {availabilityStatus === 'toggling' && (
        <p role="status">Updating availability...</p>
      )}
      {availabilityStatus === 'error' && (
        <p role="alert">Failed to update availability.</p>
      )}
      <button
        onClick={() => setShowEdit((v) => !v)}
        aria-label={showEdit ? 'Cancel editing profile' : 'Edit profile'}
      >
        {showEdit ? 'Cancel' : 'Edit profile'}
      </button>
      {showEdit && (
        <EditProfileForm
          profileId={profile.id}
          initialDisplayName={profile.display_name}
          initialBio={profile.bio}
          onSaved={(updated) => {
            setShowEdit(false)
            onProfileUpdated(updated)
          }}
        />
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Report modal — AC#8 / P5
// ---------------------------------------------------------------------------

const REPORT_REASONS: ReportReason[] = [
  'spam',
  'harassment',
  'inappropriate_content',
  'fake_profile',
  'underage_user',
  'other',
]

type ReportModalProps = {
  myId: string
  targetId: string
  targetKind: 'user' | 'message'
  onClose: () => void
}

function ReportModal({ myId, targetId, targetKind, onClose }: ReportModalProps) {
  const [reason, setReason] = useState<ReportReason>('spam')
  const [additionalText, setAdditionalText] = useState('')
  const [status, setStatus] = useState<'idle' | 'submitting' | 'done' | 'error'>('idle')

  const handleSubmit = useCallback(async () => {
    setStatus('submitting')
    try {
      await submitReport(myId, targetId, targetKind, reason, additionalText)
      setStatus('done')
    } catch {
      setStatus('error')
    }
  }, [myId, targetId, targetKind, reason, additionalText])

  if (status === 'done') {
    return (
      <div role="dialog" aria-label="Report submitted">
        <p>Report submitted. Thank you.</p>
        <button onClick={onClose}>Close</button>
      </div>
    )
  }

  return (
    <div role="dialog" aria-label="Report">
      <h2>Report</h2>
      <label htmlFor="report-reason">Reason</label>
      <select
        id="report-reason"
        value={reason}
        onChange={(e) => setReason(e.target.value as ReportReason)}
      >
        {REPORT_REASONS.map((r) => (
          <option key={r} value={r}>
            {r.replace(/_/g, ' ')}
          </option>
        ))}
      </select>
      <label htmlFor="report-text">Additional detail (optional)</label>
      <textarea
        id="report-text"
        value={additionalText}
        onChange={(e) => setAdditionalText(e.target.value)}
      />
      {status === 'error' && <p role="alert">Failed to submit report.</p>}
      <button onClick={() => void handleSubmit()} disabled={status === 'submitting'}>
        {status === 'submitting' ? 'Submitting...' : 'Submit report'}
      </button>
      <button onClick={onClose}>Cancel</button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Discovery tab — AC#3, AC#4, AC#5, AC#7
// ---------------------------------------------------------------------------

type DiscoveryTabProps = {
  myId: string
  onConnectionSent: (connection: Connection) => void
}

function DiscoveryTab({ myId, onConnectionSent }: DiscoveryTabProps) {
  const [results, setResults] = useState<DiscoveryResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [connectStatus, setConnectStatus] = useState<Record<string, SendStatus>>({})
  const [reportTarget, setReportTarget] = useState<string | null>(null)

  useEffect(() => {
    getDiscovery(myId)
      .then(setResults)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [myId])

  const handleConnect = useCallback(
    async (profileId: string) => {
      setConnectStatus((prev) => ({ ...prev, [profileId]: 'sending' }))
      try {
        const conn = await sendConnectionRequest(myId, profileId)
        setConnectStatus((prev) => ({ ...prev, [profileId]: 'sent' }))
        onConnectionSent(conn)
      } catch {
        setConnectStatus((prev) => ({ ...prev, [profileId]: 'error' }))
      }
    },
    [myId, onConnectionSent],
  )

  if (loading) return <p role="status">Loading discovery...</p>
  if (error) return <p role="alert">Could not load discovery: {error}</p>

  if (results.length === 0) {
    return (
      <section aria-label="Discovery">
        <p>Nobody nearby is open to new friends right now. Check back later!</p>
      </section>
    )
  }

  return (
    <section aria-label="Discovery">
      <ul>
        {results.map(({ profile, score, shared_interests, shared_activities }) => {
          const status = connectStatus[profile.id]
          return (
            <li key={profile.id}>
              <h2>{profile.display_name}</h2>
              <p>{profile.bio}</p>
              <p>Match score: {(score * 100).toFixed(0)}%</p>
              {shared_interests.length > 0 && (
                <p>Shared interests: {shared_interests.join(', ')}</p>
              )}
              {shared_activities.length > 0 && (
                <p>Shared activities: {shared_activities.join(', ')}</p>
              )}
              <button
                onClick={() => void handleConnect(profile.id)}
                disabled={status === 'sending' || status === 'sent'}
                aria-label={`Send connection request to ${profile.display_name}`}
              >
                {status === 'sent'
                  ? 'Request sent'
                  : status === 'sending'
                    ? 'Sending...'
                    : 'Connect'}
              </button>
              {status === 'error' && (
                <span role="alert"> Could not send request.</span>
              )}
              <button
                onClick={() => setReportTarget(profile.id)}
                aria-label={`Report ${profile.display_name}`}
              >
                Report
              </button>
            </li>
          )
        })}
      </ul>
      {reportTarget !== null && (
        <ReportModal
          myId={myId}
          targetId={reportTarget}
          targetKind="user"
          onClose={() => setReportTarget(null)}
        />
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Conversation — messaging, block, report (AC#6, AC#7, AC#8)
// ---------------------------------------------------------------------------

type ConversationProps = {
  myId: string
  connection: Connection
  onBlock: () => void
}

function Conversation({ myId, connection, onBlock }: ConversationProps) {
  const otherId =
    connection.requester_id === myId ? connection.recipient_id : connection.requester_id

  const [messages, setMessages] = useState<Message[]>([])
  const [loadingMessages, setLoadingMessages] = useState(true)
  const [msgError, setMsgError] = useState<string | null>(null)
  const [newMessage, setNewMessage] = useState('')
  const [sendStatus, setSendStatus] = useState<'idle' | 'sending' | 'error'>('idle')
  const [showReport, setShowReport] = useState(false)
  const [reportMessageId, setReportMessageId] = useState<string | null>(null)

  useEffect(() => {
    getMessages(myId, otherId)
      .then(setMessages)
      .catch((err: Error) => setMsgError(err.message))
      .finally(() => setLoadingMessages(false))
  }, [myId, otherId])

  const handleSend = useCallback(async () => {
    const body = newMessage.trim()
    if (!body) return
    setSendStatus('sending')
    try {
      const msg = await sendMessage(myId, otherId, body)
      setMessages((prev) => [...prev, msg])
      setNewMessage('')
      setSendStatus('idle')
    } catch {
      setSendStatus('error')
    }
  }, [myId, otherId, newMessage])

  const handleBlock = useCallback(async () => {
    try {
      await blockUser(myId, otherId)
      onBlock()
    } catch {
      // block API error — swallowed; parent handles removal optimistically
    }
  }, [myId, otherId, onBlock])

  if (loadingMessages) return <p role="status">Loading messages...</p>
  if (msgError) return <p role="alert">Could not load messages: {msgError}</p>

  return (
    <div>
      <h3>Conversation with {otherId}</h3>
      <ul aria-label="Messages">
        {messages.length === 0 && <li>No messages yet.</li>}
        {messages.map((m) => (
          <li key={m.id}>
            <strong>{m.sender_id === myId ? 'You' : otherId}:</strong> {m.body}
            {m.sender_id !== myId && (
              <button
                onClick={() => setReportMessageId(m.id)}
                aria-label={`Report message ${m.id}`}
              >
                Report message
              </button>
            )}
          </li>
        ))}
      </ul>
      {reportMessageId !== null && (
        <ReportModal
          myId={myId}
          targetId={reportMessageId}
          targetKind="message"
          onClose={() => setReportMessageId(null)}
        />
      )}
      <div>
        <input
          type="text"
          value={newMessage}
          onChange={(e) => setNewMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void handleSend()
          }}
          placeholder="Type a message..."
          aria-label="Message input"
        />
        <button
          onClick={() => void handleSend()}
          disabled={sendStatus === 'sending'}
          aria-label="Send message"
        >
          {sendStatus === 'sending' ? 'Sending...' : 'Send'}
        </button>
        {sendStatus === 'error' && <span role="alert"> Failed to send message.</span>}
      </div>
      <button onClick={() => void handleBlock()} aria-label={`Block ${otherId}`}>
        Block
      </button>
      <button onClick={() => setShowReport(true)} aria-label={`Report ${otherId}`}>
        Report
      </button>
      {showReport && (
        <ReportModal
          myId={myId}
          targetId={otherId}
          targetKind="user"
          onClose={() => setShowReport(false)}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Messages tab — pending and accepted connections (AC#6, AC#7, AC#8)
// ---------------------------------------------------------------------------

type MessagesTabProps = {
  myId: string
  connections: Connection[]
  onConnectionAccepted: (conn: Connection) => void
  onConnectionRemoved: (connectionId: string) => void
}

function MessagesTab({
  myId,
  connections,
  onConnectionAccepted,
  onConnectionRemoved,
}: MessagesTabProps) {
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null)
  const [acceptId, setAcceptId] = useState('')
  const [acceptStatus, setAcceptStatus] = useState<AcceptStatus>('idle')

  const pendingConnections = connections.filter((c) => c.status === 'pending')
  const acceptedConnections = connections.filter((c) => c.status === 'accepted')

  const handleAccept = useCallback(async () => {
    const id = acceptId.trim()
    if (!id) return
    setAcceptStatus('accepting')
    try {
      const conn = await acceptConnection(id, myId)
      onConnectionAccepted(conn)
      setAcceptId('')
      setAcceptStatus('idle')
    } catch {
      setAcceptStatus('error')
    }
  }, [acceptId, myId, onConnectionAccepted])

  return (
    <section aria-label="Messages">
      {/* Accept an incoming request by its connection ID */}
      <div>
        <h2>Accept a request</h2>
        <input
          type="text"
          value={acceptId}
          onChange={(e) => setAcceptId(e.target.value)}
          placeholder="Connection ID"
          aria-label="Connection ID to accept"
        />
        <button
          onClick={() => void handleAccept()}
          disabled={acceptStatus === 'accepting'}
          aria-label="Accept connection request"
        >
          {acceptStatus === 'accepting' ? 'Accepting...' : 'Accept'}
        </button>
        {acceptStatus === 'error' && (
          <span role="alert"> Could not accept request.</span>
        )}
      </div>

      {/* Pending sent requests */}
      {pendingConnections.length > 0 && (
        <div>
          <h2>Pending requests</h2>
          <ul>
            {pendingConnections.map((c) => {
              const otherId = c.requester_id === myId ? c.recipient_id : c.requester_id
              return (
                <li key={c.id}>
                  Request to {otherId}
                  <span aria-label="status"> (pending)</span>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {/* Accepted connections */}
      {acceptedConnections.length > 0 && (
        <div>
          <h2>Connections</h2>
          <ul>
            {acceptedConnections.map((c) => {
              const otherId = c.requester_id === myId ? c.recipient_id : c.requester_id
              return (
                <li key={c.id}>
                  <button
                    onClick={() => setSelectedConnectionId(c.id)}
                    aria-label={`Open conversation with ${otherId}`}
                  >
                    {otherId}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {/* No connections at all */}
      {connections.length === 0 && (
        <p>No connections yet. Discover people and send a connection request!</p>
      )}

      {/* Active conversation */}
      {acceptedConnections.map((c) => {
        if (c.id !== selectedConnectionId) return null
        return (
          <Conversation
            key={c.id}
            myId={myId}
            connection={c}
            onBlock={() => {
              onConnectionRemoved(c.id)
              setSelectedConnectionId(null)
            }}
          />
        )
      })}
    </section>
  )
}

// ---------------------------------------------------------------------------
// App — root component
// ---------------------------------------------------------------------------

function App() {
  const [profile, setProfile] = useState<MeProfile | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('profile')
  const [openToFriends, setOpenToFriends] = useState(false)
  const [availabilityStatus, setAvailabilityStatus] = useState<AvailabilityStatus>('idle')
  const [connections, setConnections] = useState<Connection[]>([])

  useEffect(() => {
    getMe()
      .then(setProfile)
      .catch((err: Error) => setLoadError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const handleAvailabilityToggle = useCallback(
    async (open: boolean) => {
      if (!profile) return
      setAvailabilityStatus('toggling')
      try {
        await toggleAvailability(profile.id, open)
        setOpenToFriends(open)
        setAvailabilityStatus('idle')
      } catch {
        setAvailabilityStatus('error')
      }
    },
    [profile],
  )

  const handleConnectionSent = useCallback((conn: Connection) => {
    setConnections((prev) => [...prev, conn])
  }, [])

  const handleConnectionAccepted = useCallback((conn: Connection) => {
    setConnections((prev) => {
      const exists = prev.some((c) => c.id === conn.id)
      return exists ? prev.map((c) => (c.id === conn.id ? conn : c)) : [...prev, conn]
    })
  }, [])

  const handleConnectionRemoved = useCallback((connectionId: string) => {
    setConnections((prev) => prev.filter((c) => c.id !== connectionId))
  }, [])

  const handleProfileUpdated = useCallback((updated: MeProfile) => {
    setProfile(updated)
  }, [])

  if (loading) return <p role="status">Loading profile...</p>
  if (loadError) return <p role="alert">Could not load profile: {loadError}</p>
  if (!profile) return <p role="alert">No profile found.</p>

  return (
    <main>
      <nav aria-label="Main navigation">
        <button
          onClick={() => setTab('profile')}
          aria-current={tab === 'profile' ? 'page' : undefined}
        >
          Profile
        </button>
        <button
          onClick={() => setTab('discovery')}
          aria-current={tab === 'discovery' ? 'page' : undefined}
        >
          Discover
        </button>
        <button
          onClick={() => setTab('messages')}
          aria-current={tab === 'messages' ? 'page' : undefined}
        >
          Messages
        </button>
      </nav>
      {tab === 'profile' && (
        <ProfileTab
          profile={profile}
          openToFriends={openToFriends}
          availabilityStatus={availabilityStatus}
          onToggle={(open) => void handleAvailabilityToggle(open)}
          onProfileUpdated={handleProfileUpdated}
        />
      )}
      {tab === 'discovery' && (
        <DiscoveryTab myId={profile.id} onConnectionSent={handleConnectionSent} />
      )}
      {tab === 'messages' && (
        <MessagesTab
          myId={profile.id}
          connections={connections}
          onConnectionAccepted={handleConnectionAccepted}
          onConnectionRemoved={handleConnectionRemoved}
        />
      )}
    </main>
  )
}

export default App
