/**
 * AC#19 — The web client can perform the whole flow against the API:
 * create a profile, toggle availability, see discovery results with their
 * scores, send a request, accept one, exchange a message, block a person,
 * and report a person.
 *
 * Target: app/web/src/App.tsx::App
 *
 * This drives the real React app (app/web/src/App.tsx) in a browser against
 * the real API (app/api/app/main.py) — no component is mocked. Every
 * endpoint in app/api/app/main.py requires an authenticated caller
 * (app/api/app/auth.py::require_auth reads the `X-User-ID` header that the
 * deployment-layer oauth2-proxy injects after validating a Keycloak token).
 * There is no login UI to drive — in line with "use programmatic auth, never
 * log in via the UI" — so this test sets that header once on the browser
 * context (the same place the proxy would inject it) and every request the
 * page makes, browser fetch() calls and this file's own setup calls alike,
 * carries it from then on.
 *
 * GET /profiles/me always returns a hard-coded profile with id "placeholder"
 * (app/api/app/main.py::profile_me — real per-session identity is a later
 * step). The signed-in user in this app is therefore always "placeholder".
 * To exercise discovery, a connection request, an accept, and a message
 * exchange, a second party has to exist on the backend. Age assurance and a
 * counterpart profile have no UI surface yet, so both are seeded directly
 * through the API with the same authenticated context — the rest of the
 * flow (create profile, toggle availability, browse discovery, connect,
 * accept, message, block, report) is driven entirely through the rendered
 * page using role/label locators, per the framework's selector priority.
 *
 * Single test file, single scenario: the whole point of AC#19 is that one
 * continuous journey works end to end, so the steps are grouped with
 * test.step() rather than split into independent tests that would each need
 * to re-derive the same backend state.
 */

import { expect, test } from '@playwright/test'

// Unique per run so re-running this spec against a live (in-memory, never
// reset) backend never collides with a prior run's counterpart profiles or
// connections — it is test-data isolation, not something any assertion
// branches on.
const runId = Date.now()
const aliceId = `e2e-alice-${runId}`
const aliceName = `Alice E2E ${runId}`
const bobId = `e2e-bob-${runId}`

test('web client completes the full flow: profile, availability, discovery, connect, accept, message, block, report', async ({
  page,
}) => {
  // Simulates the oauth2-proxy header injection (C18) for every request this
  // browser context makes, including the page's own fetch() calls.
  await page.context().setExtraHTTPHeaders({ 'X-User-ID': 'e2e-tester' })

  await test.step('seed a discoverable counterpart profile (Alice) via the API', async () => {
    const created = await page.request.post('/profiles', {
      data: {
        id: aliceId,
        display_name: aliceName,
        bio: 'Looking for hiking buddies.',
        interests: ['hiking', 'reading', 'skiing'],
        activities: [],
        age: 25,
        open_to_friends: true,
      },
    })
    expect(created.ok()).toBeTruthy()

    // AC#5: only profiles with PASSED age assurance are eligible for
    // discovery. There is no UI for this yet, so it is set directly.
    const assured = await page.request.post(`/profiles/${aliceId}/age-assurance`, {
      data: { status: 'passed' },
    })
    expect(assured.ok()).toBeTruthy()
  })

  await test.step('load the app', async () => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Demo Friend' })).toBeVisible()
  })

  await test.step('create a profile (AC#19 step 1)', async () => {
    await page.getByRole('button', { name: 'Edit profile' }).click()
    await expect(page.getByRole('form', { name: 'Create profile' })).toBeVisible()

    await page.getByRole('textbox', { name: 'Display name' }).fill('E2E Full Flow Tester')
    await page.getByRole('spinbutton', { name: 'Age' }).fill('20')
    await page.getByRole('textbox', { name: 'Bio' }).fill('Testing the whole flow end to end.')
    // Overlaps fully with Alice's interests so the match score is deterministic (100%).
    await page.getByRole('textbox', { name: 'Interests' }).fill('hiking, reading')

    await page.getByRole('button', { name: 'Save profile' }).click()

    await expect(page.getByRole('heading', { name: 'E2E Full Flow Tester' })).toBeVisible()
    await expect(page.getByRole('form', { name: 'Create profile' })).not.toBeVisible()
  })

  await test.step('mark my own age assurance as passed (required to use discovery)', async () => {
    // No UI surface for this step yet (app/api/app/main.py::record_age_assurance);
    // the profile must exist first, which the previous step just created.
    const assured = await page.request.post('/profiles/placeholder/age-assurance', {
      data: { status: 'passed' },
    })
    expect(assured.ok()).toBeTruthy()
  })

  await test.step('toggle availability on (AC#19 step 2)', async () => {
    const toggle = page.getByRole('switch', { name: 'Open to new friends' })
    await expect(toggle).not.toBeChecked()
    await toggle.click()
    await expect(toggle).toBeChecked()
  })

  await test.step('see discovery results with their scores (AC#19 step 3)', async () => {
    await page.getByRole('button', { name: 'Discover' }).click()
    await expect(page.getByRole('region', { name: 'Discovery' })).toBeVisible()

    await expect(page.getByRole('heading', { name: aliceName, level: 2 })).toBeVisible()
    // Alice's interests fully contain mine, so the interest-only match score
    // (my_activities is [] via the create-profile form) is exactly 100%.
    await expect(page.getByText('Match score: 100%')).toBeVisible()
    await expect(page.getByText('Shared interests: hiking, reading')).toBeVisible()
  })

  await test.step('send a connection request to Alice (AC#19 step 4)', async () => {
    const connectButton = page.getByRole('button', {
      name: `Send connection request to ${aliceName}`,
    })
    await connectButton.click()
    await expect(connectButton).toHaveText('Request sent')
    await expect(connectButton).toBeDisabled()
  })

  await test.step('the sent request shows as pending in Messages', async () => {
    await page.getByRole('button', { name: 'Messages' }).click()
    await expect(page.getByRole('region', { name: 'Messages' })).toBeVisible()
    await expect(page.getByText(`Request to ${aliceId}`)).toBeVisible()
  })

  let bobConnectionId = ''
  await test.step('seed an incoming connection request from Bob via the API', async () => {
    // Accepting requires the request to have myId ("placeholder") as the
    // recipient — the UI can only *send* requests as "placeholder", so the
    // other side of an acceptable request has to originate elsewhere.
    const res = await page.request.post('/connections', {
      params: { requester_id: bobId, recipient_id: 'placeholder' },
    })
    expect(res.ok()).toBeTruthy()
    const body = (await res.json()) as { id: string }
    bobConnectionId = body.id
    expect(bobConnectionId).toBeTruthy()
  })

  await test.step('accept the incoming request from Bob (AC#19 step 5)', async () => {
    await page.getByRole('textbox', { name: 'Connection ID to accept' }).fill(bobConnectionId)
    await page.getByRole('button', { name: 'Accept connection request' }).click()
    await expect(page.getByRole('button', { name: `Open conversation with ${bobId}` })).toBeVisible()
  })

  await test.step("seed an inbound message from Bob (the other half of the exchange)", async () => {
    const res = await page.request.post('/messages', {
      data: { sender_id: bobId, recipient_id: 'placeholder', body: 'Hi from Bob!' },
    })
    expect(res.ok()).toBeTruthy()
  })

  await test.step('exchange a message with Bob (AC#19 step 6)', async () => {
    await page.getByRole('button', { name: `Open conversation with ${bobId}` }).click()
    await expect(page.getByRole('heading', { name: `Conversation with ${bobId}` })).toBeVisible()

    // Bob's half of the exchange, seeded above, renders in the thread.
    await expect(page.getByText('Hi from Bob!')).toBeVisible()

    // My half of the exchange, sent through the UI.
    await page.getByRole('textbox', { name: 'Message input' }).fill('Hello Bob, nice to meet you!')
    await page.getByRole('button', { name: 'Send message' }).click()
    await expect(page.getByText('Hello Bob, nice to meet you!')).toBeVisible()
  })

  await test.step('block Bob (AC#19 step 7)', async () => {
    await page.getByRole('button', { name: `Block ${bobId}` }).click()
    await expect(
      page.getByRole('button', { name: `Open conversation with ${bobId}` }),
    ).not.toBeVisible()
    await expect(
      page.getByRole('heading', { name: `Conversation with ${bobId}` }),
    ).not.toBeVisible()
  })

  await test.step('report Alice (AC#19 step 8)', async () => {
    await page.getByRole('button', { name: 'Discover' }).click()
    await page.getByRole('button', { name: `Report ${aliceName}` }).click()

    const dialog = page.getByRole('dialog', { name: 'Report' })
    await expect(dialog).toBeVisible()

    await dialog.getByLabel('Reason').selectOption('harassment')
    await dialog.getByLabel('Additional detail (optional)').fill('Reported during e2e verification run.')
    await dialog.getByRole('button', { name: 'Submit report' }).click()

    await expect(page.getByRole('dialog', { name: 'Report submitted' })).toBeVisible()
    await expect(page.getByText('Report submitted. Thank you.')).toBeVisible()
  })
})
