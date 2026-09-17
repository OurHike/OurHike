/**
 * One invented volunteer, so the five volunteer screens have something in
 * them to judge.
 *
 * **EVERY FIGURE HERE IS @unvalidated AND MOST ARE INVENTED OUTRIGHT** - the
 * hours, the thanks, the mile marks, the dates. They exist to make a layout
 * dense enough to look at, exactly as `demoOrg.ts` says of its own numbers,
 * and for the same reason: a demo whose figures leak into a screenshot and
 * then into a claim is how an invented number becomes a fact about a product.
 * What would settle any of them is a real volunteer's record, which nobody
 * has because the endpoints behind these screens are not built yet.
 *
 * **NOBODY REAL IS NAMED.** The supervisors, the hikers who left thanks and
 * the person whose profile this is are all made up. The thank-yous carry no
 * author at all, which is not a redaction here but the shape of the real
 * thing: rule 4 means nothing upstream ever carries a hiker's name, so there
 * is no field to leave blank.
 *
 * **THE PLACES ARE THE DEMO ORG'S PLACES.** Mile marks and section names line
 * up with `demoOrg.ts` rather than inventing a second geography, so somebody
 * clicking from the console to a volunteer screen stays in one park.
 */

import type { SyncRun } from './screens/Roster'
import type { LoggedHour, PassedPlace } from './screens/HandBack'
import type { RunnerDay, RunnerFiling } from './screens/RidgeRunner'
import type {
  TreadAlert,
  TreadClosure,
  TreadHelpRequest,
  TreadIssue,
  TreadPoi,
  TreadQuestion,
  TreadRole,
  TreadThankYou,
} from './screens/YourTread'
import type {
  VolunteerActivity,
  VolunteerDetails,
  VolunteerRoleHeld,
} from './screens/VolunteerProfile'

export const DEMO_POIS: readonly TreadPoi[] = [
  {
    id: 'demo-poi-spring',
    name: 'The Ramble spring',
    kind: 'Water source',
    note: 'Piped spring, a short way west of the path.',
    checked: 'confirmed by you · Aug 28',
    age: 'current',
  },
  {
    id: 'demo-poi-shelter',
    name: 'Belvedere shelter',
    kind: 'Shelter',
    note: 'Three-sided, sleeps 6. Bear box just north.',
    checked: 'confirmed by a co-maintainer · Jun 14',
    age: 'current',
  },
  {
    id: 'demo-poi-bench',
    name: 'The overlook bench',
    kind: 'Viewpoint',
    note: 'Bench installed 2024. Faces southwest.',
    checked: 'last checked Mar 2025',
    age: 'needs a look',
  },
  {
    id: 'demo-poi-lot',
    name: 'West 100th entrance',
    kind: 'Parking',
    note: '12 cars, no fee. Gate closes at dusk.',
    checked: 'last checked Feb 2025',
    age: 'needs a look',
  },
]

export const DEMO_ALERTS: readonly TreadAlert[] = [
  {
    id: 'demo-alert-bridge',
    title: 'Bridge out at the creek crossing',
    where: 'MM 2.9',
    source: 'the park',
    since: 'Sep 9',
    kind: 'Closure',
    detail: 'Park order. Detour signed at both ends — do not send volunteers through.',
  },
  {
    id: 'demo-alert-food',
    title: 'Food storage required',
    where: 'MM 1.0 → 4.3',
    source: 'the managing partner',
    since: 'Aug 22',
    kind: 'Notice',
    detail: 'Canister or hang. Applies to the whole stretch, including the shelter.',
  },
  {
    id: 'demo-alert-fire',
    title: 'No open fires, county-wide',
    where: 'all your miles',
    source: 'the county',
    since: 'Jul 30',
    kind: 'Fire restriction',
    detail: 'Stoves permitted. Worth repeating at your workday.',
  },
]

export const DEMO_CLOSURES: readonly TreadClosure[] = [
  {
    id: 'demo-closure-stringer',
    title: 'Footbridge stringer cracked',
    where: 'MM 3.1',
    requestedBy: 'you · 2 days ago',
    standing: '2 of 3 volunteers',
    detail:
      'Two other volunteers have walked it and agreed. One more volunteer, or a supervisor, and it goes live to hikers.',
    live: false,
  },
  {
    id: 'demo-closure-washout',
    title: 'Washout at the creek',
    where: 'MM 1.9',
    requestedBy: 'a co-maintainer · Sep 3',
    standing: 'approved by a supervisor',
    detail: "A supervisor's word is enough on its own. Live on the map since Sep 3.",
    live: true,
  },
]

export const DEMO_ISSUES: readonly TreadIssue[] = [
  {
    id: 'demo-issue-blowdown',
    title: 'Blowdown across the path',
    where: 'MM 2.4',
    on: 'Sep 12',
    reportedBy: 'reported by a hiker',
    detail: 'Large oak, needs a saw. Passable on the uphill side.',
    open: true,
  },
  {
    id: 'demo-issue-blaze',
    title: 'Blaze missing at the junction',
    where: 'MM 3.1',
    on: 'Sep 5',
    reportedBy: 'reported by 3 hikers',
    detail: 'People are turning downhill onto the service road by mistake.',
    open: true,
  },
  {
    id: 'demo-issue-spring',
    title: 'Spring running dry',
    where: 'MM 1.8',
    on: 'Aug 28',
    reportedBy: 'reported by a hiker',
    detail: 'Last reliable water before the ridge — worth a note on the map.',
    open: true,
  },
  {
    id: 'demo-issue-washout',
    title: 'Washout on the switchbacks',
    where: 'MM 1.2',
    on: 'Aug 2',
    reportedBy: 'reported by you',
    detail: 'Needs rock work, not a one-person job.',
    open: true,
  },
]

export const DEMO_HELP: readonly TreadHelpRequest[] = [
  {
    id: 'demo-help-rock',
    title: 'Rock work on the switchbacks',
    where: 'MM 1.2',
    posted: 'Aug 4',
    standing: '2 volunteers offered',
  },
  {
    id: 'demo-help-saw',
    title: 'Certified sawyer for the 2.4 blowdown',
    where: 'MM 2.4',
    posted: 'Sep 12',
    standing: 'waiting on the crew',
  },
]

export const DEMO_THANKS: readonly TreadThankYou[] = [
  {
    id: 'demo-thanks-steps',
    words:
      'Walked this Saturday with my daughter — the new stepping stones at the creek made it doable for her. Thank you.',
    on: 'Sep 8',
  },
  {
    id: 'demo-thanks-blazes',
    words:
      'Whoever keeps this stretch clear: the blazes are perfect. Never once had to guess.',
    on: 'Aug 30',
  },
  {
    id: 'demo-thanks-reroute',
    words: 'Found the reroute around the wet meadow. Beautiful work.',
    on: 'Aug 11',
  },
  {
    id: 'demo-thanks-bench',
    words: 'Thank you for the bench at the overlook. Sat there an hour.',
    on: 'Jul 22',
  },
]

export const DEMO_QUESTIONS: readonly TreadQuestion[] = [
  {
    id: 'demo-q-water',
    words: 'Is the water at 1.8 reliable in September?',
    on: 'Sep 10',
  },
  {
    id: 'demo-q-marker',
    words: 'Any chance of a marker where the service road splits off?',
    on: 'Sep 2',
  },
]

export const DEMO_TREAD_ROLES: readonly TreadRole[] = [
  { id: 'demo-role-maintainer', label: 'Maintainer · The Ramble' },
  { id: 'demo-role-monitor', label: 'Corridor monitor · Bridle Path' },
]

export const DEMO_PASSED: readonly PassedPlace[] = [
  {
    id: 'demo-passed-spring',
    name: 'The Ramble spring',
    kind: 'Water source',
    ask: 'Running?',
  },
  {
    id: 'demo-passed-shelter',
    name: 'Belvedere shelter',
    kind: 'Shelter',
    ask: 'Privy still standing?',
  },
  {
    id: 'demo-passed-bench',
    name: 'The overlook bench',
    kind: 'Viewpoint',
    ask: 'Add a photo?',
  },
]

export const DEMO_HOURS: readonly LoggedHour[] = [
  {
    id: 'demo-hour-sep2',
    on: 'Sep 2',
    hours: 6,
    what: 'Maintenance · The Ramble',
    standing: 'confirmed by a supervisor · Sep 4',
    state: 'confirmed',
  },
  {
    id: 'demo-hour-aug19',
    on: 'Aug 19',
    hours: 4,
    what: 'Monitoring · Bridle Path',
    standing: 'yours immediately — counts until an organization disputes it',
    state: 'claimed',
  },
  {
    id: 'demo-hour-aug2',
    on: 'Aug 2',
    hours: 7.5,
    what: 'Maintenance · washout repair',
    standing: 'confirmed by a supervisor · Aug 6',
    state: 'confirmed',
  },
  {
    id: 'demo-hour-jul14',
    on: 'Jul 14',
    hours: 3,
    what: 'Cleanup · pack-out, west entrance',
    standing: 'the organization queried the date — removed from every total',
    state: 'disputed',
  },
]

export const DEMO_RUNNER_DAYS: readonly RunnerDay[] = [
  {
    iso: '2026-09-14',
    weekday: 'Mon',
    dayOfMonth: '14',
    submissions: 4,
    today: false,
    future: false,
    last: false,
  },
  {
    iso: '2026-09-15',
    weekday: 'Tue',
    dayOfMonth: '15',
    submissions: 2,
    today: false,
    future: false,
    last: false,
  },
  {
    iso: '2026-09-16',
    weekday: 'Wed',
    dayOfMonth: '16',
    submissions: 0,
    today: true,
    future: false,
    last: false,
  },
  {
    iso: '2026-09-17',
    weekday: 'Thu',
    dayOfMonth: '17',
    submissions: 0,
    today: false,
    future: true,
    last: false,
  },
  {
    iso: '2026-09-18',
    weekday: 'Fri',
    dayOfMonth: '18',
    submissions: 0,
    today: false,
    future: true,
    last: false,
  },
  {
    iso: '2026-09-19',
    weekday: 'Sat',
    dayOfMonth: '19',
    submissions: 0,
    today: false,
    future: true,
    last: true,
  },
]

export const DEMO_FILINGS: readonly RunnerFiling[] = [
  {
    id: 'demo-filing-cans',
    what: 'Packed out a bag of cans',
    when: 'Today, 11:20',
    where: 'MM 2.4 · the creek crossing',
    kind: 'trash',
  },
  {
    id: 'demo-filing-barberry',
    what: 'Barberry, a good patch of it',
    when: 'Today, 9:05',
    where: 'MM 1.6',
    kind: 'invasive',
  },
  {
    id: 'demo-filing-brush',
    what: 'Brushed the corridor, 300 yards',
    when: 'Tue, 4:40pm',
    where: 'MM 3.0 → 3.2',
    kind: 'clearance',
  },
  {
    id: 'demo-filing-spring',
    what: 'Spring running well',
    when: 'Tue, 8:15',
    where: 'MM 1.8 · The Ramble spring',
    kind: 'condition',
  },
  {
    id: 'demo-filing-privy',
    what: 'Privy door hinge broken',
    when: 'Mon, 5:30pm',
    where: 'MM 4.3 · Belvedere shelter',
    kind: 'report',
  },
]

export const DEMO_SYNC_RUNS: readonly SyncRun[] = [
  {
    id: 'demo-run-3',
    ranAt: 'Today, 4:02am',
    added: 14,
    deactivated: 3,
    active: 1104,
    firstRun: false,
  },
  {
    id: 'demo-run-2',
    ranAt: 'Sep 15, 4:02am',
    added: 2,
    deactivated: 0,
    active: 1093,
    firstRun: false,
  },
  {
    id: 'demo-run-1',
    ranAt: 'Sep 14, 4:02am',
    added: 1091,
    deactivated: 0,
    active: 1091,
    firstRun: true,
  },
]

const DEMO_DETAILS: VolunteerDetails = {
  fullName: 'Alex Mercer',
  email: 'alex@example.org',
  phone: '',
  trailName: 'Switchback',
}

const DEMO_HELD_ROLES: readonly VolunteerRoleHeld[] = [
  {
    id: 'demo-held-ramble',
    name: 'Maintainer',
    section: 'The Ramble',
    supervisor: 'the trails chair',
    since: 'Apr 2019',
  },
  {
    id: 'demo-held-bridle',
    name: 'Corridor monitor',
    section: 'Bridle Path',
    supervisor: 'the trails chair',
    since: 'Sep 2023',
  },
]

const DEMO_ACTIVITY: readonly VolunteerActivity[] = [
  { id: 'demo-act-1', on: 'Sep 14', what: 'Approved the organization registration' },
  { id: 'demo-act-2', on: 'Sep 9', what: 'Logged 11 hours · The Ramble' },
  { id: 'demo-act-3', on: 'Aug 30', what: "Confirmed 6 volunteers' logged hours" },
  { id: 'demo-act-4', on: 'Jul 2', what: 'Took on Corridor monitor · Bridle Path' },
]

/** The person whose five screens these are. */
export const DEMO_VOLUNTEER = {
  personId: 'demo-person-alex',
  displayName: 'Alex Mercer',
  initials: 'AM',
  joined: 'Apr 2019',
  sectionName: 'The Ramble',
  anchors: 'MM 1.0 → 4.3',
  miles: 3.3,
  standing: 'Maintainer since March 2025 · supervised by the trails chair',
  details: DEMO_DETAILS,
  roles: DEMO_HELD_ROLES,
  treadRoles: DEMO_TREAD_ROLES,
  activity: DEMO_ACTIVITY,
  hoursLogged: 142,
  reportsFiled: 41,
  sectionsCovered: 2,
  publicCredit: false,
  lastEditedBy: 'Alex',
  lastEditedOn: 'Sep 9',
} as const
