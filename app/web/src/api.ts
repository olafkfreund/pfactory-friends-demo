// API client for the MyFriends backend.
//
// ponytail: API base is same-origin in the deployed setup (nginx proxies
// /profiles, /discovery, /connections, /messages, /blocks, /reports to the
// api service); the empty string keeps local dev simple when run behind a
// dev-server proxy configured to forward those paths.

import type { Connection, DiscoveryResult, MeProfile, Message, ProfileCreate, ReportReason } from './types.ts'

/**
 * Create or update a profile (upsert via POST /profiles).
 * AC#19: the web client can perform the create-profile step of the whole flow.
 */
export async function createProfile(data: ProfileCreate): Promise<MeProfile> {
  const res = await fetch('/profiles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `request failed: ${res.status}`)
  }
  return res.json() as Promise<MeProfile>
}

/** Load the currently authenticated user's basic profile (GET /profiles/me). */
export async function getMe(): Promise<MeProfile> {
  const res = await fetch('/profiles/me')
  if (!res.ok) throw new Error(`request failed: ${res.status}`)
  return res.json() as Promise<MeProfile>
}

/**
 * Toggle the current user's "open to new friends" status (AC#2).
 * PATCH /profiles/{profileId}/availability?open_to_friends={open}
 */
export async function toggleAvailability(profileId: string, open: boolean): Promise<void> {
  const res = await fetch(`/profiles/${profileId}/availability?open_to_friends=${open}`, {
    method: 'PATCH',
  })
  if (!res.ok) throw new Error(`request failed: ${res.status}`)
}

/**
 * Fetch discovery results for the given searcher (AC#3, AC#4).
 * GET /discovery/{searcherId}?radius_km=25
 */
export async function getDiscovery(searcherId: string): Promise<DiscoveryResult[]> {
  const res = await fetch(`/discovery/${searcherId}?radius_km=25`)
  if (!res.ok) throw new Error(`request failed: ${res.status}`)
  return res.json() as Promise<DiscoveryResult[]>
}

/**
 * Send a connection request from requester to recipient (AC#5).
 * POST /connections?requester_id={requesterId}&recipient_id={recipientId}
 */
export async function sendConnectionRequest(
  requesterId: string,
  recipientId: string,
): Promise<Connection> {
  const res = await fetch(
    `/connections?requester_id=${requesterId}&recipient_id=${recipientId}`,
    { method: 'POST' },
  )
  if (!res.ok) throw new Error(`request failed: ${res.status}`)
  return res.json() as Promise<Connection>
}

/**
 * Accept a pending connection request on behalf of acceptorId (AC#6).
 * POST /connections/{connectionId}/accept?acceptor_id={acceptorId}
 */
export async function acceptConnection(
  connectionId: string,
  acceptorId: string,
): Promise<Connection> {
  const res = await fetch(`/connections/${connectionId}/accept?acceptor_id=${acceptorId}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`request failed: ${res.status}`)
  return res.json() as Promise<Connection>
}

/**
 * Load all messages exchanged between two users (AC#6).
 * GET /messages/{user1Id}/{user2Id}
 */
export async function getMessages(user1Id: string, user2Id: string): Promise<Message[]> {
  const res = await fetch(`/messages/${user1Id}/${user2Id}`)
  if (!res.ok) throw new Error(`request failed: ${res.status}`)
  return res.json() as Promise<Message[]>
}

/**
 * Send a message from sender to recipient (AC#6, AC#7).
 * POST /messages {sender_id, recipient_id, body}
 */
export async function sendMessage(
  senderId: string,
  recipientId: string,
  body: string,
): Promise<Message> {
  const res = await fetch('/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sender_id: senderId, recipient_id: recipientId, body }),
  })
  if (!res.ok) throw new Error(`request failed: ${res.status}`)
  return res.json() as Promise<Message>
}

/**
 * Block a user (AC#7 / P5).
 * POST /blocks {blocker_id, blocked_id}
 */
export async function blockUser(blockerId: string, blockedId: string): Promise<void> {
  const res = await fetch('/blocks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ blocker_id: blockerId, blocked_id: blockedId }),
  })
  if (!res.ok) throw new Error(`request failed: ${res.status}`)
}

/**
 * Submit a report (AC#8 / P5).
 * POST /reports {reporter_id, target_id, target_kind, reason, additional_text}
 */
export async function submitReport(
  reporterId: string,
  targetId: string,
  targetKind: 'user' | 'message',
  reason: ReportReason,
  additionalText: string,
): Promise<void> {
  const res = await fetch('/reports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reporter_id: reporterId,
      target_id: targetId,
      target_kind: targetKind,
      reason,
      additional_text: additionalText,
    }),
  })
  if (!res.ok) throw new Error(`request failed: ${res.status}`)
}
