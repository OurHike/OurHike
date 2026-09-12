// The screens a launch does not show, loaded when first shown or on idle
// (#1302, lib/deferredScreen.ts) - one list, so the shell's import block says
// which screens are eager by what is NOT here, and so the preload below cannot
// forget one.
//
// What stays eager, and why: Today and the tab bar (the first frame),
// Onboarding (a first run's first frame), the report window (it opens the
// instant a report is saved, on a ridge, and its constant UNDO_WINDOW_MS is
// read by the shell), and the map's own overlays that the shell composes
// itself. Everything a hiker reaches by a tap on another tab or by starting
// a flow is here.

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
