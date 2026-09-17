/**
 * The client's half of the organization endpoints (features/ORG_ONBOARDING.md).
 *
 * Built on `lib/api.ts` rather than beside it: that module owns the base URL,
 * the token, and the rule that a non-2xx throws - which is load-bearing
 * everywhere and would be wrong to re-decide here.
 *
 * TWO STANCES, and which one an endpoint takes is a statement about who it is
 * for. A read that any hiker may make (an org's own page, its registry, the
 * upcoming workdays) goes through `readOrg`, which sends a token when there
 * happens to be one and works without. Everything else goes through
 * `writeOrg`, which refuses before spending a request when signed out -
 * because the answer is knowable without a round trip on a metered
 * connection, and because a console screen has nothing useful to show a
 * signed-out caller anyway.
 *
 * NOTHING HERE DECIDES A PERMISSION. `GET /clubs/{slug}/access` is the one
 * place the client learns what somebody may do, and it is the server's answer
 * rather than the client's inference - see `backend/app/core/org_access.py`,
 * whose whole argument is that a flag in a browser is a display detail and
 * never a gate.
 */

import { accessToken, apiFetch } from '../lib/api'
import { NotSignedInError } from '../lib/api'

/** A read any hiker may make. The token rides along when there is one. */
async function readOrg<T>(path: string, signal?: AbortSignal): Promise<T> {
  const token = await accessToken()
  const response = await apiFetch(path, {
    signal,
    headers: token === null ? {} : { Authorization: `Bearer ${token}` },
  })
  return (await response.json()) as T
}

/** A call that needs an account, refused here rather than by a round trip. */
async function writeOrg<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await accessToken()
  if (token === null) throw new NotSignedInError()

  const response = await apiFetch(path, {
    ...init,
    headers: {
      ...init.headers,
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  })
  // 204 on the way out of an organization. `response.json()` on an empty body
  // throws, and "you left" is not a failure.
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export interface OrgAdmin {
  id: string
  person_id: string
  title: string | null
  is_codeowner: boolean
  invited_at: string
  approved_at: string | null
  declined_at: string | null
  decline_reason: string | null
}

export interface Org {
  id: string
  slug: string | null
  name: string
  region: string | null
  domain: string | null
  website: string | null
  verified_by: 'dns' | 'email' | null
  state: 'unclaimed' | 'claimed' | 'frozen' | 'deleted'
  membership_url: string | null
  donation_url: string | null
  created_at: string
  admins: OrgAdmin[]
  /** The server's answer on whether the assist panels may send. Never inferred here. */
  assist_opted_in: boolean
}

/** What the server says this person may do here. Never inferred locally. */
export interface OrgAccess {
  org_slug: string
  is_admin: boolean
  is_codeowner: boolean
  is_supervisor: boolean
  is_volunteer: boolean
  can_manage_volunteers: boolean
  can_read_roster: boolean
  can_touch_registry: boolean
}

export interface OrgSection {
  id: string
  trail_id: string
  name: string
  start_anchor: string | null
  end_anchor: string | null
  start_mile: number | null
  end_mile: number | null
  miles: number | null
  region: string | null
  geometry: string | null
}

export interface OrgTrail {
  id: string
  park_id: string
  name: string | null
  blaze_value_raw: string | null
  blaze_mapped: string | null
  miles: number | null
  sections: OrgSection[]
}

export interface OrgPark {
  id: string
  club_id: string
  name: string
  kind: 'park' | 'system' | 'forest'
  created_at: string
  trails: OrgTrail[]
}

export interface RegistryDiffRow {
  kind: 'added' | 'changed' | 'removed'
  tier: 'park' | 'trail' | 'section'
  name: string
  detail: string | null
}

export interface RegistryDiff {
  club_id: string
  rows: RegistryDiffRow[]
  touches_published_geometry: boolean
}

export interface CoverageGap {
  section_id: string
  section_name: string
  trail_name: string | null
  region: string | null
  miles: number | null
  geometry: string | null
}

export interface Coverage {
  club_id: string
  region: string | null
  sections_total: number
  gaps: CoverageGap[]
}

export type RoleCategory = 'trail_maintenance' | 'stewards' | 'environmental'

export interface OrgRole {
  id: string
  club_id: string
  name: string
  category: RoleCategory
  reports_to_role_id: string | null
  section_id: string | null
  required: boolean
  required_by: string | null
  retired_at: string | null
}

export interface RosterEntry {
  person_id: string | null
  email: string | null
  display_name: string | null
  full_name: string | null
  roles: string[]
  sections: string[]
  pending_invite: boolean
}

export interface RosterSyncResult {
  run_id: string
  added: number
  updated: number
  deactivated: number
  deactivations_held: number
  held_person_ids: string[]
  held_reason: string | null
}

export type SignupState =
  'interested' | 'confirmed' | 'waitlisted' | 'declined' | 'cancelled_by_volunteer'

export interface Workday {
  id: string
  club_id: string
  title: string
  description: string | null
  starts_on: string
  ends_on: string
  meet_point: string | null
  mile: number | null
  lat: number | null
  lon: number | null
  status: 'upcoming' | 'completed' | 'cancelled'
  cap: number | null
  source: 'ourhike' | 'mirrored'
  signup_mode: 'contact' | 'in_app'
  signup_contact: string | null
  signup_url: string | null
  interested_count: number
  confirmed_count: number
}

export interface WorkdaySignup {
  id: string
  work_project_id: string
  person_id: string
  state: SignupState
  note: string | null
  reply_message: string | null
  replied_at: string | null
  attended: number | null
  created_at: string
}

export interface Commitment {
  id: string
  person_id: string
  starts_on: string
  ends_on: string
  tasks: string[]
  club_id: string | null
  note: string | null
  created_at: string
  ended_early_at: string | null
}

export interface ConsoleKey {
  id: string
  club_id: string
  public_key: string
  label: string | null
  can_write: boolean
  created_at: string
  revoked_at: string | null
  last_used_at: string | null
  allowed_origins: string[]
  /** Present exactly once, on the response that created it. */
  secret?: string
}

/**
 * Whether an organization has turned the assist panels on, and who did.
 *
 * `opted_in_at` and `opted_in_by` are null until somebody has; `opted_out_at`
 * carries the last time somebody turned it back off, so a record of both
 * directions survives rather than only the current state.
 */
export interface AssistConsent {
  opted_in: boolean
  opted_in_at: string | null
  opted_in_by: string | null
  opted_out_at: string | null
}

const org = (slug: string) => `/clubs/${encodeURIComponent(slug)}`

export const orgApi = {
  list: (signal?: AbortSignal) => readOrg<Org[]>('/clubs', signal),
  read: (slug: string, signal?: AbortSignal) => readOrg<Org>(org(slug), signal),
  access: (slug: string, signal?: AbortSignal) =>
    readOrg<OrgAccess>(`${org(slug)}/access`, signal),

  registry: (slug: string, signal?: AbortSignal) =>
    readOrg<OrgPark[]>(`${org(slug)}/registry`, signal),
  diff: (slug: string, signal?: AbortSignal) =>
    readOrg<RegistryDiff>(`${org(slug)}/registry/diff`, signal),
  coverage: (slug: string, region?: string, signal?: AbortSignal) =>
    readOrg<Coverage>(
      `${org(slug)}/coverage${region ? `?region=${encodeURIComponent(region)}` : ''}`,
      signal,
    ),

  roles: (slug: string, signal?: AbortSignal) =>
    readOrg<OrgRole[]>(`${org(slug)}/roles`, signal),
  roster: (slug: string, signal?: AbortSignal) =>
    readOrg<RosterEntry[]>(`${org(slug)}/roster`, signal),

  workdays: (slug: string, days = 60, signal?: AbortSignal) =>
    readOrg<Workday[]>(`/workdays?org=${encodeURIComponent(slug)}&days=${days}`, signal),
  signups: (workdayId: string, signal?: AbortSignal) =>
    readOrg<WorkdaySignup[]>(
      `/workdays/${encodeURIComponent(workdayId)}/signups`,
      signal,
    ),
  mySignups: (signal?: AbortSignal) =>
    readOrg<WorkdaySignup[]>('/workdays/signups/mine', signal),
  myCommitments: (signal?: AbortSignal) =>
    readOrg<Commitment[]>('/ridge-runner/mine', signal),

  approveSeat: (slug: string, adminId: string) =>
    writeOrg<Org>(`${org(slug)}/admins/${encodeURIComponent(adminId)}/approve`, {
      method: 'POST',
    }),
  declineSeat: (slug: string, adminId: string, reason?: string) =>
    writeOrg<Org>(`${org(slug)}/admins/${encodeURIComponent(adminId)}/decline`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  inviteAdmin: (slug: string, email: string, title?: string) =>
    writeOrg<Org>(`${org(slug)}/admins`, {
      method: 'POST',
      body: JSON.stringify({ email, title: title ?? null }),
    }),
  signOff: (slug: string) =>
    writeOrg<{
      status: string
      approvals_required: number
      codeowners_available: number
      detail: string
    }>(`${org(slug)}/registry/signoff`, { method: 'POST' }),
  registerSource: (slug: string, url: string, kind: string) =>
    writeOrg<{ status: string; detail: string }>(`${org(slug)}/gis-source`, {
      method: 'POST',
      body: JSON.stringify({ url, kind }),
    }),
  syncRoster: (slug: string, source: string, entries: unknown[]) =>
    writeOrg<RosterSyncResult>(`${org(slug)}/roster/sync`, {
      method: 'POST',
      body: JSON.stringify({ source, entries }),
    }),
  inviteVolunteer: (slug: string, email: string, roleId?: string, fullName?: string) =>
    writeOrg(`${org(slug)}/invites`, {
      method: 'POST',
      body: JSON.stringify({
        email,
        role_id: roleId ?? null,
        full_name: fullName ?? null,
      }),
    }),
  replyToSignup: (
    workdayId: string,
    signupId: string,
    state: SignupState,
    message?: string,
  ) =>
    writeOrg<WorkdaySignup>(
      `/workdays/${encodeURIComponent(workdayId)}/signups/${encodeURIComponent(signupId)}/reply`,
      { method: 'POST', body: JSON.stringify({ state, message: message ?? null }) },
    ),
  consoleKeys: (slug: string, signal?: AbortSignal) =>
    readOrg<ConsoleKey[]>(`${org(slug)}/console-keys`, signal),
  createConsoleKey: (slug: string, label: string, origins: string[]) =>
    writeOrg<ConsoleKey>(`${org(slug)}/console-keys`, {
      method: 'POST',
      body: JSON.stringify({ label, allowed_origins: origins }),
    }),
  revokeConsoleKey: (slug: string, keyId: string) =>
    writeOrg<ConsoleKey>(`${org(slug)}/console-keys/${encodeURIComponent(keyId)}`, {
      method: 'DELETE',
    }),
  /** One assist panel's question. See `app/routers/assist.py` for the gate.
   *
   *  A write rather than a read, though it changes nothing an organization
   *  can see: it needs an account, it spends the org's budget, and it is
   *  refused here when signed out rather than after a round trip.
   */
  assist: (slug: string, panel: string, question: string) =>
    writeOrg<{
      panel: string
      answer: string
      tokens_used: number
      tokens_left_today: number | null
    }>(`${org(slug)}/assist`, {
      method: 'POST',
      body: JSON.stringify({ panel, question }),
    }),
  /** Whether this organization has opted in, for the panel and for Settings.
   *
   *  A read through `readOrg` even though the endpoint is admin-only: the
   *  server is the gate here as everywhere (`app/routers/assist.py` refuses
   *  both this and `/assist` on its own), and a token rides along when there
   *  is one, which is all an admin's browser has to offer.
   */
  assistConsent: (slug: string, signal?: AbortSignal) =>
    readOrg<AssistConsent>(`${org(slug)}/assist-consent`, signal),
  setAssistConsent: (slug: string, optedIn: boolean) =>
    writeOrg<AssistConsent>(`${org(slug)}/assist-consent`, {
      method: 'PUT',
      body: JSON.stringify({ opted_in: optedIn }),
    }),
  exportOrg: (slug: string) => writeOrg<Record<string, unknown>>(`${org(slug)}/export`),
  deleteOrg: (slug: string) => writeOrg<void>(org(slug), { method: 'DELETE' }),
  stepBack: (slug: string, assignmentId: string) =>
    writeOrg(`${org(slug)}/assignments/${encodeURIComponent(assignmentId)}/step-back`, {
      method: 'POST',
    }),
}
