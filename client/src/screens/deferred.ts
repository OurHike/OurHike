// The screens a launch does not show, loaded when first shown or on idle
// (#1302, lib/deferredScreen.ts) - one list, so the shell's import block says
// which screens are eager by what is NOT here, and so the preload below cannot
// forget one.
//
// What stays eager, and why: Today and the tab bar (the first frame),
// Onboarding (a first run's first frame), and the map's own overlays that
// the shell composes itself. Everything a hiker reaches by a tap on another
// tab or by starting a flow is here.
//
// THE REPORT WINDOW IS HERE SINCE #1563, and it was kept out on purpose
// before: it opens on a ridge the instant a hiker taps Report, and the shell
// read its UNDO_WINDOW_MS. The second reason was the trap LAUNCH_BUDGET.md
// §4.4 names - a constant read out of a screen brings the screen - and the
// constant lives in reporting/undoWindow.ts now. The first holds for every
// screen in this list: a chunk is a precache read on any phone that has
// installed the app, and the idle preload below has fetched it within a
// second of launch. What forced the move is the budget: the window's #1563
// growth measured 256,121 eager bytes in CI against 256,000 (commit
// 53315108, `check:build`), and deferring only its sheet and reporter block
// left 232 bytes of headroom locally against a CI build that runs ~400
// bytes larger. The sheet (Change, or a refused tap) and the block the
// receipt signs with are deferred separately, because the long form and the
// closure form render the same pair and one chunk serves all three hosts.

import { deferredScreen, type DeferredScreen } from '../lib/deferredScreen'
import type { ComponentType } from 'react'

/**
 * Every screen declared below, in declaration order, for `preloadScreens`.
 * Filled by `screen()` as each is declared rather than listed by hand: the
 * hand list forgot two (#1374 review), and the only symptom was that those
 * screens rendered asynchronously under test where every other one did not.
 */
const registry: Array<{ preload(): Promise<void> }> = []

function screen<P extends object>(
  load: () => Promise<ComponentType<P>>,
  name: string,
): DeferredScreen<P> {
  const declared = deferredScreen(load, name)
  registry.push(declared)
  return declared
}

export const MapScreen = screen(
  () => import('../chrome/MapScreen').then((m) => m.MapScreen),
  'MapScreen',
)
export const PlanScreen = screen(() => import('./Plan').then((m) => m.PlanScreen), 'Plan')
export const More = screen(() => import('./More').then((m) => m.More), 'More')
export const Moderation = screen(
  () => import('./Moderation').then((m) => m.Moderation),
  'Moderation',
)
export const Registry = screen(
  () => import('./Registry').then((m) => m.Registry),
  'Registry',
)
export const Downloads = screen(
  () => import('./Downloads').then((m) => m.Downloads),
  'Downloads',
)
export const DownloadsDialog = screen(
  () => import('./DownloadsDialog').then((m) => m.DownloadsDialog),
  'DownloadsDialog',
)
export const InstallPrompt = screen(
  () => import('./InstallPrompt').then((m) => m.InstallPrompt),
  'InstallPrompt',
)
export const ClosureForm = screen(
  () => import('./ClosureForm').then((m) => m.ClosureForm),
  'ClosureForm',
)
export const ReportForm = screen(
  () => import('./ReportForm').then((m) => m.ReportForm),
  'ReportForm',
)
export const ReportWindow = screen(
  () => import('../reporting/ReportWindow').then((m) => m.ReportWindow),
  'ReportWindow',
)
export const LocationSheet = screen(
  () => import('../reporting/LocationSheet').then((m) => m.LocationSheet),
  'LocationSheet',
)
export const ReporterDetails = screen(
  () => import('../reporting/ReporterDetails').then((m) => m.ReporterDetails),
  'ReporterDetails',
)
export const KeepSpotSheet = screen(
  () => import('../reporting/KeepSpotSheet').then((m) => m.KeepSpotSheet),
  'KeepSpotSheet',
)
export const GroupScreen = screen(
  () => import('./GroupScreen').then((m) => m.GroupScreen),
  'GroupScreen',
)
export const TripList = screen(
  () => import('./TripList').then((m) => m.TripList),
  'TripList',
)
export const WalkedHike = screen(
  () => import('./WalkedHike').then((m) => m.WalkedHike),
  'WalkedHike',
)
export const PlanTargetSheet = screen(
  () => import('./PlanTargetSheet').then((m) => m.PlanTargetSheet),
  'PlanTargetSheet',
)
export const IdentitySetup = screen(
  () => import('./IdentitySetup').then((m) => m.IdentitySetup),
  'IdentitySetup',
)
export const SignInPrompt = screen(
  () => import('./SignInPrompt').then((m) => m.SignInPrompt),
  'SignInPrompt',
)
export const EmailSignIn = screen(
  () => import('./EmailSignIn').then((m) => m.EmailSignIn),
  'EmailSignIn',
)
export const AppFailureReport = screen(
  () => import('./AppFailureReport').then((m) => m.AppFailureReport),
  'AppFailureReport',
)
export const Volunteer = screen(
  () => import('./Volunteer').then((m) => m.Volunteer),
  'Volunteer',
)
export const VolunteerHours = screen(
  () => import('./VolunteerHours').then((m) => m.VolunteerHours),
  'VolunteerHours',
)
export const VolunteerImpact = screen(
  () => import('./VolunteerImpact').then((m) => m.VolunteerImpact),
  'VolunteerImpact',
)
// Challenges (#1780): the list, one challenge, and Browse - reached from
// More, never on a first frame.
export const Challenges = screen(
  () => import('./Challenges').then((m) => m.Challenges),
  'Challenges',
)
export const ChallengeDetail = screen(
  () => import('./ChallengeDetail').then((m) => m.ChallengeDetail),
  'ChallengeDetail',
)
export const ChallengeBrowse = screen(
  () => import('./ChallengeBrowse').then((m) => m.ChallengeBrowse),
  'ChallengeBrowse',
)
export const FindHike = screen(
  () => import('./FindHike').then((m) => m.FindHike),
  'FindHike',
)
export const HikeDetail = screen(
  () => import('./HikeDetail').then((m) => m.HikeDetail),
  'HikeDetail',
)
export const HikePicker = screen(
  () => import('./HikePicker').then((m) => m.HikePicker),
  'HikePicker',
)
// Step 1 of the planning spine (#1373): reached by a tap on Plan, or the
// pinned bar - never on the first frame.
export const PlanStart = screen(
  () => import('./PlanStart').then((m) => m.PlanStart),
  'PlanStart',
)

// The long hike's own screens (#1317). Every one is reached by starting a
// flow - setting a hike up, opening the day inside it, finishing it, reading
// the record afterwards, or handing it to somebody - so all five meet this
// module's stated rule rather than being an exception to it. The three
// SHEETS stay eager: they are shell-composed overlays, and one of them opens
// from the mode switch that is on the first frame itself.
export const HikeSetup = screen(
  () => import('./HikeSetup').then((m) => m.HikeSetup),
  'HikeSetup',
)
export const HikeDay = screen(() => import('./HikeDay').then((m) => m.HikeDay), 'HikeDay')
export const HikeFinish = screen(
  () => import('./HikeFinish').then((m) => m.HikeFinish),
  'HikeFinish',
)
// The on-trail conditions peek Today mounts per stop (#1373, frame 2d) is
// the waypoint card's own section, and the card lives in the map's chunk.
// Imported statically from Today it rode into the eager bundle with its
// note roll-up, photo and dispute readers behind it - measured 2026-09-10
// at 254,104 of the 256,000-byte budget with it eager (#1374 review).
// The crews section (#1440), deferred for FieldNoteSection's reason and by
// the same measurement: Today is the first frame and is eager, and this
// section carries a month calendar, a row component and six selection
// helpers. Imported statically from Today it put the budget 1,641 bytes over
// (measured 2026-09-15, features/LAUNCH_BUDGET.md §3) - and moving it here,
// with the crew-against-a-walk helpers split into lib/crews.ts so they stop
// riding on the eager lib/workProjects.ts, brought it back to 255,844.
//
// chrome/ReportPickBar.tsx was tried here too and is deliberately NOT: it is
// small enough that the registry entry and the import stub cost 21 bytes MORE
// than the module weighed. A lazy boundary that makes the bundle bigger is a
// boundary bought for its own sake.
export const CrewsSection = screen(
  () => import('../chrome/CrewsSection').then((m) => m.CrewsSection),
  'CrewsSection',
)
export const FieldNoteSection = screen(
  () => import('../chrome/FieldNoteSection').then((m) => m.FieldNoteSection),
  'FieldNoteSection',
)
export const YourReports = screen(
  () => import('./YourReports').then((m) => m.YourReports),
  'YourReports',
)
export const YourWork = screen(
  () => import('./YourWork').then((m) => m.YourWork),
  'YourWork',
)
export const FinishedHike = screen(
  () => import('./FinishedHike').then((m) => m.FinishedHike),
  'FinishedHike',
)
export const ShareHike = screen(
  () => import('./ShareHike').then((m) => m.ShareHike),
  'ShareHike',
)

// THE SHEETS, PANELS AND CARDS A TAP OPENS, deferred for the reason the
// screens above are (#1735). App.tsx and two panel hooks rendered each of
// these conditionally and imported it statically, so the closure a launch
// parses before its first frame carried all ten for a Today screen that
// opens none of them: 50,631 raw bytes, measured 2026-09-30 by attributing
// the built chunks to their sources (DayHikeCard 8,863, DayHikePanel 7,292,
// RouteEntranceSheet 7,262, RouteStopPicker 6,174, DayHikePickBar 5,231,
// RouteStopsPanel 4,003, NextTurnCard 3,417, LineSheet 2,673, StepAwaySheet
// 2,437; NoticeList 3,279 through chrome/noticesPanel.tsx). preloadScreens warms them on the first idle with the screens, so a
// tap after that pays nothing; a tap before it waits for the chunk, which the
// service worker serves from its cache on every launch but the first. Two of
// them can be on screen when a launch starts - the turn card mid-walk and
// the saved day-hike card - and arrive that one chunk later.
export const DayHikeCard = screen(
  () => import('./DayHikeCard').then((m) => m.DayHikeCard),
  'DayHikeCard',
)
export const DayHikePanel = screen(
  () => import('../chrome/DayHikePanel').then((m) => m.DayHikePanel),
  'DayHikePanel',
)
export const DayHikePickBar = screen(
  () => import('../chrome/DayHikePickBar').then((m) => m.DayHikePickBar),
  'DayHikePickBar',
)
export const RouteStopPicker = screen(
  () => import('../chrome/RouteStopPicker').then((m) => m.RouteStopPicker),
  'RouteStopPicker',
)
export const RouteEntranceSheet = screen(
  () => import('../chrome/RouteEntranceSheet').then((m) => m.RouteEntranceSheet),
  'RouteEntranceSheet',
)
export const RouteStopsPanel = screen(
  () => import('../chrome/RouteStopsPanel').then((m) => m.RouteStopsPanel),
  'RouteStopsPanel',
)
export const NextTurnCard = screen(
  () => import('../chrome/NextTurnCard').then((m) => m.NextTurnCard),
  'NextTurnCard',
)
export const StepAwaySheet = screen(
  () => import('../chrome/StepAwaySheet').then((m) => m.StepAwaySheet),
  'StepAwaySheet',
)
export const NoticeList = screen(
  () => import('../chrome/NoticeList').then((m) => m.NoticeList),
  'NoticeList',
)
export const LineSheet = screen(
  () => import('../chrome/LineSheet').then((m) => m.LineSheet),
  'LineSheet',
)

/**
 * Every deferred screen's module, ahead of any tap.
 *
 * The shell calls this on idle once the first frame is up, so the second
 * a hiker taps Plan the code is already parsed; the test harness calls it
 * before every test, so the suite renders exactly as it did when these were
 * static imports. A module that fails to load fails here too, which is the
 * right answer for both: the shell tries again on the tap, and a test finds
 * out at once.
 */
export async function preloadScreens(): Promise<void> {
  await Promise.all(registry.map((declared) => declared.preload()))
}
