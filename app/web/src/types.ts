// Shared domain types for the MyFriends web UI.
// Kept in a separate module so api.ts and App.tsx can both import them
// without creating a circular dependency.

/** Partial profile returned by GET /profiles/me (no store lookup required). */
export type MeProfile = {
  id: string
  display_name: string
  bio: string
}

/** Full profile returned by GET /profiles/{id} and discovery results. */
export type Profile = {
  id: string
  display_name: string
  bio: string
  age: number
  interests: string[]
  activities: string[]
  open_to_friends: boolean
}

/** A single entry from GET /discovery/{searcher_id}. */
export type DiscoveryResult = {
  profile: Profile
  score: number
  shared_interests: string[]
  shared_activities: string[]
}

/** A connection between two users (AC#6). */
export type Connection = {
  id: string
  requester_id: string
  recipient_id: string
  status: 'pending' | 'accepted'
}

/** A message between two connected users (AC#6). */
export type Message = {
  id: string
  sender_id: string
  recipient_id: string
  body: string
}

/** Input shape for POST /profiles (create or upsert a profile). */
export type ProfileCreate = {
  id: string
  display_name: string
  bio: string
  interests: string[]
  activities: string[]
  age: number
  open_to_friends: boolean
}

/** Fixed set of reasons a person can choose when filing a report (AC#8). */
export type ReportReason =
  | 'spam'
  | 'harassment'
  | 'inappropriate_content'
  | 'fake_profile'
  | 'underage_user'
  | 'other'
