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

/** A write from somebody with no account, addressed by a token in the URL.
 *
 *  The one shape in this file that sends no Authorization header at all, and
 *  it is deliberate rather than an oversight: three people at a nominated club
 *  answer "is this yours?" from a link in an email, and requiring an account
 *  to say no would be a sign-up wall in front of a question we asked them.
 *
 *  The token IS the authorization, which is why `backend/app/routers/
 *  nominations.py` gives expired, withdrawn and never-existed the same 404
 *  with the same sentence - a distinguishing error is an oracle for guessing
 *  one. */
async function postWithoutAnAccount<T>(path: string, body: unknown): Promise<T> {
  const response = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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

/** A CSV an org admin downloads, refused here when signed out.
 *
 *  `writeOrg`'s stance rather than `readOrg`'s, although it changes nothing:
 *  a challenge's entries carry the names, addresses and emails hikers chose
 *  to send one club, so there is no signed-out caller this could ever answer,
 *  and the refusal costs no request. Text rather than JSON because
 *  `GET /clubs/{slug}/challenges/{id}/entries` answers `text/csv` only - the
 *  console never parses the rows, which is how no hiker's name reaches the
 *  screen (screens/ChallengeFinishers.tsx). */
async function readCsv(path: string): Promise<string> {
  const token = await accessToken()
  if (token === null) throw new NotSignedInError()
  const response = await apiFetch(path, {
    headers: { Accept: 'text/csv', Authorization: `Bearer ${token}` },
  })
  return response.text()
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
  // `pending` and `unclaimed` are opposites, not neighbours - see the backend's
  // `OrgState`. An unclaimed org is real and nobody has taken it; a pending one
  // was registered on an address the registrant typed for somebody else, and
  // nothing about it is published or verified until that person approves a seat.
  state: 'unclaimed' | 'pending' | 'claimed' | 'frozen' | 'deleted'
  /** The pull request this registry is sitting in, or null for every
   *  organization until a service identity's token is issued and
   *  `registry_pr_enabled` is switched on. Null has to read as null: a
   *  screen implying somebody is waiting to approve when nothing was
   *  opened is the defect this field exists to end. */
  registry_pr_url: string | null
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

/* ------------------------------------------------------------------ *
 * Challenges (#1780, features/CHALLENGES.md)
 *
 * NOT `NominateChallenge` below, which is the nominate flow's proof of work
 * and shares nothing with these but a word. Every type here is prefixed or
 * named for the club's list of places so the two cannot be confused in an
 * import.
 * ------------------------------------------------------------------ */

/** Either end may be null: no opening date, or never closes. */
export interface ChallengeWindow {
  opens: string | null
  closes: string | null
}

/** How one item is tagged, in the REVIEWED file's shape - the one a club's
 *  definition is saved in and `pipeline/lib/challenges.py` resolves.
 *
 *  **Places are published POI ids, never typed miles or coordinates**
 *  (features/CHALLENGES.md, "Items name published POI ids"). The exporter
 *  copies the published record's own mile, coordinate and name into the
 *  artifact, so nothing typed in this console becomes a position a hiker's
 *  phone matches against. That is why no type here has a mile or a latitude
 *  field to fill. */
export type ChallengeDefinitionMatch =
  | { kind: 'place'; poi: string; radius_m?: number; off_trail?: boolean }
  | { kind: 'places_all'; pois: string[]; radius_m?: number; off_trail?: boolean }
  | { kind: 'poi_type'; type: string; radius_m?: number }
  | { kind: 'elevation_min_ft'; value: number }
  | { kind: 'section_walked'; from_poi: string; to_poi: string; min_fraction?: number }
  | { kind: 'workday'; org?: string | null }
  | { kind: 'self_report' }

export type ChallengeMatchKind = ChallengeDefinitionMatch['kind']

export interface ChallengeDefinitionItem {
  id: string
  section: string
  /** Null for a mystery item nobody has announced yet. */
  title: string | null
  /** The club's own words on the tagged place, one to three sentences. */
  note?: string | null
  note_by?: string | null
  /** The club's photo of the place, shown labelled as the club's. */
  photo?: string | null
  mystery?: { number: number; reveal_on: string | null } | null
  match: ChallengeDefinitionMatch
}

export interface ChallengeDefinitionSection {
  id: string
  title: string
  short?: string | null
}

/** What somebody who finishes is offered. `null` - nothing - is the common
 *  case, not a gap: most challenges offer no reward. */
export type ChallengeRewardKind = 'patch' | 'postcard' | 'sticker' | 'drawing'

/** One challenge as a club authors it: `pipeline/reference/challenges/<org>/
 *  <id>.json`, before anything is resolved against published data. */
export interface ChallengeDefinition {
  id: string
  org: string
  /** One trail, and one the organization publishes (design principle 5). */
  trail: string
  name: string
  status: 'draft' | 'published'
  summary?: string | null
  window: ChallengeWindow
  /** Null is a challenge with no finish, just a record. */
  finish: { count: number; label?: string | null } | null
  reward: { kind: ChallengeRewardKind; rules_url?: string | null } | null
  /** Collect entries through OurHike. The reviewed file carries it so the
   *  phone knows whether to ask a finisher for a name and an address; the
   *  backend row's own flag is set from it on save. Only a published
   *  challenge with a reward can. */
  takes_entries?: boolean
  sections: ChallengeDefinitionSection[]
  items: ChallengeDefinitionItem[]
  /** What the club said counts, for whoever reviews the file and picks the
   *  places. See `screens/Challenges.tsx` for why it travels. */
  what_counts?: ChallengeMatchKind[]
  reviewed?: string | null
}

/** One row of `GET /clubs/{slug}/challenges`.
 *
 *  `hikers_in` is a count the club sees and never a hiker: null when it is
 *  below `hikers_in_floor`, the k-anonymity floor EVENTING.md sets at 25.
 *  Showing "fewer than 25" there is features/CHALLENGES.md's placeholder,
 *  which that doc's open questions say is nobody's decision yet.
 *
 *  `live` and `definition` are optional because the endpoint is being built
 *  alongside this screen and its contract as handed over names neither. The
 *  screen reads an absent `definition` as "the file could not be shown here"
 *  and an absent `live` as unknown - never as live, and never as not. */
export interface OrgChallengeRow {
  challenge_id: string
  name: string
  status: 'draft' | 'published'
  window: ChallengeWindow | null
  hikers_in: number | null
  hikers_in_floor: number
  /** How many sent an entry at the finish. A count, no names. */
  finished: number
  /** Whether a data refresh has carried it to phones yet. */
  live?: boolean
  definition?: ChallengeDefinition | null
}

/** What pressing "Publish with next refresh" did. `pull_request` is null
 *  whenever nothing was opened - the registry's opener is off by default
 *  (ORG_ONBOARDING.md, Known gaps) - and `detail` then says why, in words
 *  the screen shows as they are. */
export interface ChallengePublishResult {
  pull_request: string | null
  detail: string
}

const org = (slug: string) => `/clubs/${encodeURIComponent(slug)}`

/** The work a browser does before the backend will read a website.
 *
 *  Every field is public by construction - see `lib/proofOfWork.ts` and
 *  `backend/app/core/challenge.py`. The signature is what makes them
 *  unforgeable, not secrecy. */
export interface NominateChallenge {
  nonce: string
  difficulty: number
  expires_at: number
  signature: string
}

export type SourceVerdict =
  'usable' | 'closures' | 'found' | 'not_accepted' | 'unreadable'

export interface ProposedSource {
  label: string
  url: string
  verdict: SourceVerdict
  detail: string | null
}

/** One person or role, as published on the club's own pages.
 *
 *  `name` is null when nobody published one - the design's own example is
 *  "Board president · Leadership · president@… · no name given". Absent means
 *  unknown, never an empty string and never a guess. */
export interface ProposedContact {
  name: string | null
  role: string | null
  email: string
  source_page: string
}

/** What the reading saw. STORED NOWHERE until the hiker submits it.
 *
 *  `read_at_all` is separate from an empty `sources` on purpose: a reading
 *  that reached the site and found nothing is a different answer from one
 *  that could not reach the site, and a hiker deciding whether to type the
 *  sources in by hand needs to know which one they got. */
export interface NominateReading {
  website: string
  read_at_all: boolean
  pages_read: number
  org_name: string | null
  /** The reading's own sentence about what it read.
   *
   *  **IT MAY CARRY UNITS WE DO NOT CONVERT**, and that is a deliberate
   *  exception to the rule `src/test/unitDisplay.test.ts` enforces. A model
   *  summarising a trail club's website will write "38 miles of footpath",
   *  and a hiker who chose kilometres reads it as written. Rewriting it would
   *  be worse: this is a description of somebody else's page, shown under a
   *  heading saying so, and a converted number in it would be us editing what
   *  we claim to have read. Every figure the APP owns - miles maintained,
   *  section lengths - goes through lib/units.ts as usual. */
  summary: string | null
  sources: ProposedSource[]
  contacts: ProposedContact[]
  membership_url: string | null
  donation_url: string | null
  licence_note: string | null
  tokens_used: number
}

export interface KeptSource extends ProposedSource {
  proposed_by: 'reading' | 'hiker'
}

export interface KeptContact extends ProposedContact {
  proposed_by: 'reading' | 'hiker'
}

export interface NominationSubmission {
  website: string
  org_name: string
  region: string | null
  sources: KeptSource[]
  contacts: KeptContact[]
}

export interface ProposalContact {
  name: string | null
  role: string | null
  email: string
  source_page: string
  responded: boolean
}

/** What somebody at the club sees when they open the link we mailed them. */
export interface Proposal {
  org_name: string
  website: string
  proposed_by_display: string
  proposed_at: string
  sources: ProposedSource[]
  contacts: ProposalContact[]
  approvals_required: number
  approvals_so_far: number
  state: 'proposed' | 'emailed' | 'accepted' | 'declined' | 'withdrawn'
}

export const orgApi = {
  list: (signal?: AbortSignal) => readOrg<Org[]>('/clubs', signal),

  // THE NOMINATE FLOW. The challenge and the reading both need an account -
  // `writeOrg` refuses before spending a request when signed out, which is
  // the right answer here because the whole screen is behind sign-in.
  nominateChallenge: () => writeOrg<NominateChallenge>('/assist/nominate/challenge'),
  nominateRead: (body: NominateChallenge & { website: string; solution: string }) =>
    writeOrg<NominateReading>('/assist/nominate', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  nominateSubmit: (body: NominationSubmission) =>
    writeOrg<{ id: string; club_slug: string }>('/clubs/nominations', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // THE CLUB'S OWN SCREEN NEEDS NO ACCOUNT, which is why these two use the
  // plain read rather than `writeOrg`. Nobody at a nominated club has one, and
  // asking them to make one in order to answer "is this yours?" would be a
  // sign-up wall in front of a question we asked them.
  proposal: (token: string, signal?: AbortSignal) =>
    readOrg<Proposal>(`/nominations/${encodeURIComponent(token)}`, signal),
  proposalDecision: (
    token: string,
    body: { approve: boolean; never_ask_again?: boolean; note?: string },
  ) =>
    postWithoutAnAccount<Proposal>(
      `/nominations/${encodeURIComponent(token)}/decision`,
      body,
    ),
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
  challenges: (slug: string, signal?: AbortSignal) =>
    readOrg<OrgChallengeRow[]>(`${org(slug)}/challenges`, signal),
  saveChallenge: (slug: string, challengeId: string, definition: ChallengeDefinition) =>
    writeOrg<unknown>(`${org(slug)}/challenges/${encodeURIComponent(challengeId)}`, {
      method: 'PUT',
      // The row's flag and the file's, in one place, so the server's answer
      // and the phone's offer cannot disagree.
      body: JSON.stringify({
        definition,
        takes_entries: definition.takes_entries === true,
      }),
    }),
  publishChallenge: (slug: string, challengeId: string) =>
    writeOrg<ChallengePublishResult>(
      `${org(slug)}/challenges/${encodeURIComponent(challengeId)}/publish`,
      { method: 'POST' },
    ),
  /** The entries hikers sent, as the CSV the server writes. Never parsed. */
  challengeEntriesCsv: (slug: string, challengeId: string) =>
    readCsv(`${org(slug)}/challenges/${encodeURIComponent(challengeId)}/entries`),
  exportOrg: (slug: string) => writeOrg<Record<string, unknown>>(`${org(slug)}/export`),
  deleteOrg: (slug: string) => writeOrg<void>(org(slug), { method: 'DELETE' }),
  stepBack: (slug: string, assignmentId: string) =>
    writeOrg(`${org(slug)}/assignments/${encodeURIComponent(assignmentId)}/step-back`, {
      method: 'POST',
    }),
}
