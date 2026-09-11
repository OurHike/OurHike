/**
 * Every screen surface, and what the flow suite (client/e2e/) says about it.
 *
 * WHY THIS IS A LIST AND NOT A HABIT. `reachability.test.ts` already holds
 * every screen module to having a door - "a screen module nothing imports is
 * code shipped to nobody." This is the next question about the same set: a
 * screen with a door nobody has said how to *drive* is a screen whose flow
 * regresses silently. features/FLOW_TESTING.md is how a flow test is formed
 * and what each journey step has to assert; this is the ledger of which
 * surfaces have one, and `flowCoverage.test.ts` is what stops it rotting -
 * a new screen module fails that test until it appears here, so a feature
 * carries its own entry in the change that adds it rather than in a sweep
 * somebody schedules later.
 *
 * THREE STATUSES, AND ONLY ONE OF THEM IS FREE.
 *
 * - `covered` - a spec in client/e2e/ drives this surface today, and names
 *   which. Claimed only where the spec actually asserts on the surface;
 *   passing through a screen on the way somewhere else is not coverage of it.
 * - `planned` - belongs in the battery and is not written. The honest
 *   majority right now. This is the work list, not an apology: #1386 opened
 *   the layer with four specs deliberately, and the rest is scoped in
 *   features/FLOW_TESTING.md by journey step rather than file by file.
 * - `unit-only` - deliberately never a flow test, with the reason. A leaf
 *   with no state of its own is proved by a component test; driving a browser
 *   to it proves the same thing more slowly. An entry here is a decision
 *   somebody can disagree with, which is why it carries a sentence.
 *
 * The `step` field is the journey step from features/PATHWAY.md's spine, so
 * the ledger groups the way a hiker moves rather than the way the directory
 * sorts - and so "what is left on F6" is one filter rather than a reading.
 */

export type FlowStatus =
  | { readonly status: 'covered'; readonly spec: string }
  | { readonly status: 'planned' }
  | { readonly status: 'unit-only'; readonly why: string }

export interface FlowSurface {
  /** The journey step from features/PATHWAY.md, or the surface's own home
   *  where it sits outside the spine (settings, moderation, failure paths). */
  readonly step: string
  readonly flow: FlowStatus
}

/**
 * Keyed by the module path under `src/`, which is exactly what
 * `reachability.test.ts` enumerates - same three directories, same spelling,
 * so the two ledgers cannot disagree about what a screen is.
 */
export const FLOW_COVERAGE: Readonly<Record<string, FlowSurface>> = {
  // ---- F1 first run -------------------------------------------------------
  'screens/Onboarding.tsx': {
    step: 'F1 first run',
    flow: { status: 'covered', spec: 'e2e/onboarding.spec.ts' },
  },
  'chrome/PlaceField.tsx': {
    step: 'F1 first run',
    flow: { status: 'covered', spec: 'e2e/firstRunStates.spec.ts' },
  },
  'screens/InstallPrompt.tsx': { step: 'F1 first run', flow: { status: 'planned' } },

  // ---- F2 Today -----------------------------------------------------------
  'screens/Today.tsx': {
    step: 'F2 Today',
    flow: { status: 'covered', spec: 'e2e/today.spec.ts' },
  },
  'chrome/PinnedBar.tsx': {
    step: 'F2 Today',
    flow: { status: 'covered', spec: 'e2e/today.spec.ts' },
  },
  'chrome/TabBar.tsx': {
    step: 'F2 Today',
    flow: { status: 'covered', spec: 'e2e/today.spec.ts' },
  },
  'chrome/ModeSwitch.tsx': { step: 'F2 Today', flow: { status: 'planned' } },
  'chrome/WelcomeBackCard.tsx': { step: 'F2 Today', flow: { status: 'planned' } },
  'chrome/NextUpRail.tsx': { step: 'F2 Today', flow: { status: 'planned' } },
  'chrome/FieldNoteSection.tsx': { step: 'F2 Today', flow: { status: 'planned' } },
  'chrome/TrailDataUpdate.tsx': { step: 'F2 Today', flow: { status: 'planned' } },

  // ---- F3 step 1, Hike ----------------------------------------------------
  'screens/PlanStart.tsx': {
    step: 'F3 step 1 · Hike',
    flow: { status: 'covered', spec: 'e2e/planSpine.spec.ts' },
  },
  'chrome/StepRail.tsx': {
    step: 'F3 step 1 · Hike',
    flow: { status: 'covered', spec: 'e2e/planSpine.spec.ts' },
  },
  'chrome/BailSheet.tsx': {
    step: 'F3 step 1 · Hike',
    flow: { status: 'covered', spec: 'e2e/bailSheet.spec.ts' },
  },
  'chrome/RouteStopPicker.tsx': { step: 'F3 step 1 · Hike', flow: { status: 'planned' } },
  'chrome/RouteEntranceSheet.tsx': {
    step: 'F3 step 1 · Hike',
    flow: { status: 'planned' },
  },
  'chrome/HikePickSheet.tsx': { step: 'F3 step 1 · Hike', flow: { status: 'planned' } },
  'screens/HikeSetup.tsx': { step: 'F3 step 1 · Hike', flow: { status: 'planned' } },
  'screens/HikePicker.tsx': { step: 'F3 step 1 · Hike', flow: { status: 'planned' } },

  // ---- F4 step 2, Route ---------------------------------------------------
  'chrome/DayHikePickBar.tsx': { step: 'F4 step 2 · Route', flow: { status: 'planned' } },
  'chrome/DayHikePanel.tsx': { step: 'F4 step 2 · Route', flow: { status: 'planned' } },
  'chrome/RouteStopsPanel.tsx': {
    step: 'F4 step 2 · Route',
    flow: { status: 'planned' },
  },
  'chrome/RouteMapPickBar.tsx': {
    step: 'F4 step 2 · Route',
    flow: { status: 'planned' },
  },
  'chrome/routeBuilderPanel.tsx': {
    step: 'F4 step 2 · Route',
    flow: { status: 'planned' },
  },
  'chrome/RouteHover.tsx': { step: 'F4 step 2 · Route', flow: { status: 'planned' } },
  'chrome/SectionPlanner.tsx': { step: 'F4 step 2 · Route', flow: { status: 'planned' } },

  // ---- F5 step 3, Details and Save ---------------------------------------
  'screens/DayHikeCard.tsx': {
    step: 'F5 step 3 · Details',
    flow: { status: 'covered', spec: 'e2e/dayHikeCard.spec.ts' },
  },
  'screens/PlanTargetSheet.tsx': {
    step: 'F5 step 3 · Details',
    flow: { status: 'planned' },
  },
  'screens/LeaveWithSomeone.tsx': {
    step: 'F5 step 3 · Details',
    flow: { status: 'covered', spec: 'e2e/dayHikeCard.spec.ts' },
  },
  'screens/ShareHike.tsx': { step: 'F5 step 3 · Details', flow: { status: 'planned' } },
  'chrome/AddDayHikeSheet.tsx': {
    step: 'F5 step 3 · Details',
    flow: { status: 'planned' },
  },

  // ---- F6 walking it ------------------------------------------------------
  'chrome/NextTurnCard.tsx': { step: 'F6 walking it', flow: { status: 'planned' } },
  'chrome/TurnCard.tsx': { step: 'F6 walking it', flow: { status: 'planned' } },
  'chrome/OffRouteCard.tsx': { step: 'F6 walking it', flow: { status: 'planned' } },
  'screens/HikeFinish.tsx': { step: 'F6 walking it', flow: { status: 'planned' } },
  'screens/DaySummary.tsx': { step: 'F6 walking it', flow: { status: 'planned' } },
  'chrome/ElevationRibbon.tsx': { step: 'F6 walking it', flow: { status: 'planned' } },
  'screens/TrailRibbon.tsx': { step: 'F6 walking it', flow: { status: 'planned' } },

  // ---- F7 when today changes ---------------------------------------------
  'screens/HikeDay.tsx': { step: 'F7 when today changes', flow: { status: 'planned' } },
  'chrome/StepAwaySheet.tsx': {
    step: 'F7 when today changes',
    flow: { status: 'planned' },
  },

  // ---- F8 Plan ------------------------------------------------------------
  'screens/Plan.tsx': { step: 'F8 Plan', flow: { status: 'planned' } },
  'screens/PlanHome.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/plan.spec.ts' },
  },
  'screens/WhatsLeft.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/plan.spec.ts' },
  },
  'screens/HikeZoom.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/plan.spec.ts' },
  },
  'screens/DayHikeList.tsx': { step: 'F8 Plan', flow: { status: 'planned' } },
  'screens/TripList.tsx': { step: 'F8 Plan', flow: { status: 'planned' } },
  'screens/FinishedHike.tsx': { step: 'F8 Plan', flow: { status: 'planned' } },
  'screens/WalkedHike.tsx': { step: 'F8 Plan', flow: { status: 'planned' } },
  'screens/StretchCard.tsx': { step: 'F8 Plan', flow: { status: 'planned' } },
  'screens/HikeDetail.tsx': { step: 'F8 Plan', flow: { status: 'planned' } },
  'screens/FindHike.tsx': { step: 'F8 Plan', flow: { status: 'planned' } },
  'chrome/FacetSheet.tsx': { step: 'F8 Plan', flow: { status: 'planned' } },
  'chrome/SuggestedHikeCard.tsx': { step: 'F8 Plan', flow: { status: 'planned' } },
  'chrome/DayHikesHere.tsx': { step: 'F8 Plan', flow: { status: 'planned' } },

  // ---- F9 reporting -------------------------------------------------------
  'screens/YourReports.tsx': {
    step: 'F9 reporting',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/YourWork.tsx': {
    step: 'F9 reporting',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/ReportForm.tsx': { step: 'F9 reporting', flow: { status: 'planned' } },
  'screens/ClosureForm.tsx': { step: 'F9 reporting', flow: { status: 'planned' } },
  'reporting/ReportWindow.tsx': { step: 'F9 reporting', flow: { status: 'planned' } },
  'screens/Moderation.tsx': { step: 'F9 reporting', flow: { status: 'planned' } },

  // ---- F12 the map --------------------------------------------------------
  'chrome/MapScreen.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/mapRoom.spec.ts' },
  },
  'chrome/Legend.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/mapRoom.spec.ts' },
  },
  'chrome/InViewSheet.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/ClosureSheet.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/SeriousWarningSheet.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/OrgNoticeSheet.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/alertSheetsPanel.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/noticesPanel.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/NoticeList.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/LineSheet.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/tappedLinePanel.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/PoiCard.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/RemovedPoiCard.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/PoiShareSheet.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/PlaceSheet.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/PressPlate.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/Search.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/mapChrome.spec.ts' },
  },
  'chrome/Header.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/mapChrome.spec.ts' },
  },
  'chrome/HighlightSheet.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/ElevationChart.tsx': { step: 'F12 the map', flow: { status: 'planned' } },

  // ---- F14 volunteering ---------------------------------------------------
  'screens/Volunteer.tsx': {
    step: 'F14 volunteering',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/VolunteerHours.tsx': { step: 'F14 volunteering', flow: { status: 'planned' } },
  'screens/VolunteerImpact.tsx': {
    step: 'F14 volunteering',
    flow: { status: 'planned' },
  },
  'chrome/WorkdaySheet.tsx': { step: 'F14 volunteering', flow: { status: 'planned' } },
  'chrome/workdayPanel.tsx': { step: 'F14 volunteering', flow: { status: 'planned' } },
  'chrome/ClubSheet.tsx': { step: 'F14 volunteering', flow: { status: 'planned' } },
  'screens/GroupScreen.tsx': { step: 'F14 volunteering', flow: { status: 'planned' } },

  // ---- F13 More, settings and identity -----------------------------------
  'screens/More.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/Settings.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'screens/AboutBuild.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/Registry.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'screens/GpsTrace.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/PaceSettings.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'screens/IdentitySetup.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'screens/EmailSignIn.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'screens/SignInPrompt.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'screens/ThemePicker.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/UnitPicker.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/MapStylePicker.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/MapDetailPicker.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'chrome/BackgroundPicker.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'chrome/SourcesSection.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'chrome/DownloadsLink.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'screens/ReportBug.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/failurePaths.spec.ts' },
  },

  // ---- The download, which is its own flow at every step ------------------
  'screens/Downloads.tsx': { step: 'The download', flow: { status: 'planned' } },
  'screens/DownloadsDialog.tsx': { step: 'The download', flow: { status: 'planned' } },
  'screens/DownloadCard.tsx': { step: 'The download', flow: { status: 'planned' } },

  // ---- Failure paths ------------------------------------------------------
  'screens/AppFailureReport.tsx': {
    step: 'Failure paths',
    flow: { status: 'covered', spec: 'e2e/failurePaths.spec.ts' },
  },
  'chrome/ErrorBoundary.tsx': {
    step: 'Failure paths',
    flow: { status: 'covered', spec: 'e2e/failurePaths.spec.ts' },
  },

  // ---- Leaves: proved by a component test, not by a browser ---------------
  'chrome/ModeIcon.tsx': {
    step: 'shared',
    flow: {
      status: 'unit-only',
      why: 'A glyph. ModeIcon.test.tsx draws it; a flow test would be a slower way to look at the same SVG.',
    },
  },
  'chrome/PoiRow.tsx': {
    step: 'shared',
    flow: {
      status: 'unit-only',
      why: 'A row rendered from props, with no state and no door of its own - the screens that mount it own the flow.',
    },
  },
  'chrome/DayRow.tsx': {
    step: 'shared',
    flow: {
      status: 'unit-only',
      why: 'Same shape as PoiRow: three figures from props (rule R7), asserted where the figures are computed.',
    },
  },
  'chrome/Notice.tsx': {
    step: 'shared',
    flow: {
      status: 'unit-only',
      why: 'A presentational shell for a sentence and one action; the action belongs to whichever screen passes it.',
    },
  },
  'chrome/HikeFinderIcon.tsx': {
    step: 'shared',
    flow: { status: 'unit-only', why: 'An icon set with no behaviour.' },
  },
  'chrome/MapAttribution.tsx': {
    step: 'shared',
    flow: {
      status: 'unit-only',
      why: 'Static credit text required on every frame; style.test.ts and the map chrome tests already hold it present.',
    },
  },
  'chrome/JunctionDiagram.tsx': {
    step: 'shared',
    flow: {
      status: 'unit-only',
      why: 'A drawing computed from a junction - geometry, asserted numerically where it is derived rather than by looking at it in a browser.',
    },
  },
  'chrome/StatusStrip.tsx': {
    step: 'shared',
    flow: {
      status: 'unit-only',
      why: 'Reads state the screens under test already assert; its own chip wrapping is a CSS rule with a component test.',
    },
  },
  'screens/Tabs.tsx': {
    step: 'shared',
    flow: {
      status: 'unit-only',
      why: 'A generic tab control. The screens that mount it (first run, Downloads) carry the flow assertions.',
    },
  },
  'screens/DetailPicker.tsx': {
    step: 'shared',
    flow: {
      status: 'unit-only',
      why: 'A generic radio ladder; the download-size rules it renders are asserted in lib and in first run.',
    },
  },
}
