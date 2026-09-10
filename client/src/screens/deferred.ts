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

import { deferredScreen } from '../lib/deferredScreen'

export const MapScreen = deferredScreen(
  () => import('../chrome/MapScreen').then((m) => m.MapScreen),
  'MapScreen',
)
export const PlanScreen = deferredScreen(
  () => import('./Plan').then((m) => m.PlanScreen),
  'Plan',
)
export const More = deferredScreen(() => import('./More').then((m) => m.More), 'More')
export const Moderation = deferredScreen(
  () => import('./Moderation').then((m) => m.Moderation),
  'Moderation',
)
export const Registry = deferredScreen(
  () => import('./Registry').then((m) => m.Registry),
  'Registry',
)
export const Downloads = deferredScreen(
  () => import('./Downloads').then((m) => m.Downloads),
  'Downloads',
)
export const DownloadsDialog = deferredScreen(
  () => import('./DownloadsDialog').then((m) => m.DownloadsDialog),
  'DownloadsDialog',
)
export const InstallPrompt = deferredScreen(
  () => import('./InstallPrompt').then((m) => m.InstallPrompt),
  'InstallPrompt',
)
export const ClosureForm = deferredScreen(
  () => import('./ClosureForm').then((m) => m.ClosureForm),
  'ClosureForm',
)
export const ReportForm = deferredScreen(
  () => import('./ReportForm').then((m) => m.ReportForm),
  'ReportForm',
)
export const GroupScreen = deferredScreen(
  () => import('./GroupScreen').then((m) => m.GroupScreen),
  'GroupScreen',
)
export const TripList = deferredScreen(
  () => import('./TripList').then((m) => m.TripList),
  'TripList',
)
export const WalkedHike = deferredScreen(
  () => import('./WalkedHike').then((m) => m.WalkedHike),
  'WalkedHike',
)
export const PlanTargetSheet = deferredScreen(
  () => import('./PlanTargetSheet').then((m) => m.PlanTargetSheet),
  'PlanTargetSheet',
)
export const IdentitySetup = deferredScreen(
  () => import('./IdentitySetup').then((m) => m.IdentitySetup),
  'IdentitySetup',
)
export const SignInPrompt = deferredScreen(
  () => import('./SignInPrompt').then((m) => m.SignInPrompt),
  'SignInPrompt',
)
export const EmailSignIn = deferredScreen(
  () => import('./EmailSignIn').then((m) => m.EmailSignIn),
  'EmailSignIn',
)
export const AppFailureReport = deferredScreen(
  () => import('./AppFailureReport').then((m) => m.AppFailureReport),
  'AppFailureReport',
)
export const Volunteer = deferredScreen(
  () => import('./Volunteer').then((m) => m.Volunteer),
  'Volunteer',
)
export const VolunteerHours = deferredScreen(
  () => import('./VolunteerHours').then((m) => m.VolunteerHours),
  'VolunteerHours',
)
export const VolunteerImpact = deferredScreen(
  () => import('./VolunteerImpact').then((m) => m.VolunteerImpact),
  'VolunteerImpact',
)
export const FindHike = deferredScreen(
  () => import('./FindHike').then((m) => m.FindHike),
  'FindHike',
)
export const HikeDetail = deferredScreen(
  () => import('./HikeDetail').then((m) => m.HikeDetail),
  'HikeDetail',
)
export const HikePicker = deferredScreen(
  () => import('./HikePicker').then((m) => m.HikePicker),
  'HikePicker',
)
// Step 1 of the planning spine (#1373): reached by a tap on Plan, or the
// pinned bar - never on the first frame.
export const PlanStart = deferredScreen(
  () => import('./PlanStart').then((m) => m.PlanStart),
  'PlanStart',
)

// The long hike's own screens (#1317). Every one is reached by starting a
// flow - setting a hike up, opening the day inside it, finishing it, reading
// the record afterwards, or handing it to somebody - so all five meet this
// module's stated rule rather than being an exception to it. The three
// SHEETS stay eager: they are shell-composed overlays, and one of them opens
// from the mode switch that is on the first frame itself.
export const HikeSetup = deferredScreen(
  () => import('./HikeSetup').then((m) => m.HikeSetup),
  'HikeSetup',
)
export const HikeDay = deferredScreen(
  () => import('./HikeDay').then((m) => m.HikeDay),
  'HikeDay',
)
export const HikeFinish = deferredScreen(
  () => import('./HikeFinish').then((m) => m.HikeFinish),
  'HikeFinish',
)
export const FinishedHike = deferredScreen(
  () => import('./FinishedHike').then((m) => m.FinishedHike),
  'FinishedHike',
)
export const ShareHike = deferredScreen(
  () => import('./ShareHike').then((m) => m.ShareHike),
  'ShareHike',
)

const ALL = [
  MapScreen,
  PlanScreen,
  More,
  Moderation,
  Registry,
  Downloads,
  DownloadsDialog,
  InstallPrompt,
  ClosureForm,
  ReportForm,
  GroupScreen,
  TripList,
  WalkedHike,
  PlanTargetSheet,
  IdentitySetup,
  SignInPrompt,
  EmailSignIn,
  AppFailureReport,
  Volunteer,
  VolunteerHours,
  VolunteerImpact,
  FindHike,
  HikeDetail,
  HikePicker,
  PlanStart,
  HikeSetup,
  HikeDay,
  HikeFinish,
  FinishedHike,
  ShareHike,
]

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
  await Promise.all(ALL.map((screen) => screen.preload()))
}
