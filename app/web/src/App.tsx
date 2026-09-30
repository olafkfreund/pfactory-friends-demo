import { useEffect, useState } from 'react'

type Profile = {
  id: string
  display_name: string
  bio: string
}

// ponytail: API base is same-origin in the deployed setup (nginx proxies
// /profiles and /healthz to the api service); '' keeps local dev simple too
// when run behind a dev-server proxy. Revisit if that stops being true.
const API_BASE = ''

function App() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_BASE}/profiles/me`)
      .then((res) => {
        if (!res.ok) throw new Error(`request failed: ${res.status}`)
        return res.json() as Promise<Profile>
      })
      .then((data) => setProfile(data))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p role="status">Loading profile...</p>
  if (error) return <p role="alert">Could not load profile: {error}</p>
  if (!profile) return <p role="alert">No profile found.</p>

  return (
    <main>
      <h1>{profile.display_name}</h1>
      <p>{profile.bio}</p>
    </main>
  )
}

export default App
