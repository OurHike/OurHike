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
 * THE SUITE HAS TWO HALVES SINCE 2026-09-11, and a `spec` naming
 * `e2e/data/` means the second one. `e2e/` drives a phone that has downloaded
 * nothing - a real state, and the only one this suite could reach until now.
 * `e2e/data/` drives the same app reading the release lib/dataRelease.ts
 * pins, which is what makes the builder, the route and the waypoint screens
 * drivable at all (the gap #1387 records). The cost of the second half is
 * that it reads a network; playwright.config.ts's FLOW_DATA comment carries
 * the three things that bound it, and it is its own CI job so a bucket outage
 * never reads as a broken client.
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
  'screens/InstallPrompt.tsx': {
    step: 'F1 first run',
    flow: { status: 'covered', spec: 'e2e/settingsRooms.spec.ts' },
  },

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
  'chrome/ModeSwitch.tsx': {
    step: 'F2 Today',
    flow: { status: 'covered', spec: 'e2e/reportingDoors.spec.ts' },
  },
  'chrome/WelcomeBackCard.tsx': {
    step: 'F2 Today',
    flow: { status: 'covered', spec: 'e2e/longHikeRooms.spec.ts' },
  },
  // SAME BLOCKER AS THE RIBBON BELOW, read from the source rather than
  // measured (2026-09-11): chrome/MapScreen.tsx renders the rail only when
  // `waypoints !== undefined && elevation !== undefined`, and App.tsx's
  // `elevation` is what `ribbonView` returns — "undefined on a null profile
  // and MapScreen omits the block entirely". So the rail is absent for
  // exactly the reason the ribbon draws nothing, and the same published
  // elevation cell would move both.
  'chrome/NextUpRail.tsx': { step: 'F2 Today', flow: { status: 'planned' } },
  'chrome/FieldNoteSection.tsx': {
    step: 'F2 Today',
    flow: { status: 'covered', spec: 'e2e/data/mapSheets.spec.ts' },
  },
  'chrome/TrailDataUpdate.tsx': {
    step: 'F2 Today',
    flow: { status: 'covered', spec: 'e2e/data/newerData.spec.ts' },
  },

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
  'chrome/RouteStopPicker.tsx': {
    step: 'F3 step 1 · Hike',
    flow: { status: 'covered', spec: 'e2e/data/longSpine.spec.ts' },
  },
  'chrome/RouteEntranceSheet.tsx': {
    step: 'F3 step 1 · Hike',
    flow: { status: 'covered', spec: 'e2e/data/longSpine.spec.ts' },
  },
  'chrome/HikePickSheet.tsx': {
    step: 'F3 step 1 · Hike',
    flow: { status: 'covered', spec: 'e2e/planRooms.spec.ts' },
  },
  'screens/HikeSetup.tsx': {
    step: 'F3 step 1 · Hike',
    flow: { status: 'covered', spec: 'e2e/longHikeRooms.spec.ts' },
  },
  'screens/HikePicker.tsx': {
    step: 'F3 step 1 · Hike',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },

  // ---- F4 step 2, Route ---------------------------------------------------
  'chrome/DayHikePickBar.tsx': {
    step: 'F4 step 2 · Route',
    flow: { status: 'covered', spec: 'e2e/data/builder.spec.ts' },
  },
  'chrome/DayHikePanel.tsx': {
    step: 'F4 step 2 · Route',
    flow: { status: 'covered', spec: 'e2e/data/builder.spec.ts' },
  },
  'chrome/RouteStopsPanel.tsx': {
    step: 'F4 step 2 · Route',
    flow: { status: 'covered', spec: 'e2e/data/longSpine.spec.ts' },
  },
  'chrome/RouteMapPickBar.tsx': {
    step: 'F4 step 2 · Route',
    flow: { status: 'covered', spec: 'e2e/data/longSpine.spec.ts' },
  },
  'chrome/routeBuilderPanel.tsx': {
    step: 'F4 step 2 · Route',
    flow: { status: 'covered', spec: 'e2e/data/longSpine.spec.ts' },
  },
  'chrome/RouteHover.tsx': {
    step: 'F4 step 2 · Route',
    flow: { status: 'covered', spec: 'e2e/data/desktopMap.spec.ts' },
  },
  'chrome/SectionPlanner.tsx': {
    step: 'F4 step 2 · Route',
    flow: { status: 'covered', spec: 'e2e/longHikeRooms.spec.ts' },
  },

  // ---- F5 step 3, Details and Save ---------------------------------------
  'screens/DayHikeCard.tsx': {
    step: 'F5 step 3 · Details',
    flow: { status: 'covered', spec: 'e2e/dayHikeCard.spec.ts' },
  },
  // STILL PLANNED, with one thing worth carrying (2026-09-11). Its refusal is
  // the same sentence chrome/RouteEntranceSheet.tsx used to show while the
  // waypoints were still arriving — "This download predates trail miles on
  // waypoints" — and it rests on the same conflation: `preview === null`
  // comes from `planDaysVia`, which is null exactly when `candidateStops`
  // finds no poi carrying a mile, and an EMPTY poi set satisfies that too.
  // Read rather than measured, and NOT fixed by symmetry: the entrance's
  // `refused` only chose between two valid renders, where this branch also
  // guards a body that needs the preview it is standing in for.
  'screens/PlanTargetSheet.tsx': {
    step: 'F5 step 3 · Details',
    flow: { status: 'covered', spec: 'e2e/data/longSpine.spec.ts' },
  },
  'screens/LeaveWithSomeone.tsx': {
    step: 'F5 step 3 · Details',
    flow: { status: 'covered', spec: 'e2e/dayHikeCard.spec.ts' },
  },
  'screens/ShareHike.tsx': {
    step: 'F5 step 3 · Details',
    flow: { status: 'covered', spec: 'e2e/reportingDoors.spec.ts' },
  },
  'chrome/AddDayHikeSheet.tsx': {
    step: 'F5 step 3 · Details',
    flow: { status: 'covered', spec: 'e2e/tripRooms.spec.ts' },
  },

  // ---- F6 walking it ------------------------------------------------------
  'chrome/NextTurnCard.tsx': {
    step: 'F6 walking it',
    flow: { status: 'covered', spec: 'e2e/data/followMode.spec.ts' },
  },
  'chrome/TurnCard.tsx': {
    step: 'F6 walking it',
    flow: { status: 'covered', spec: 'e2e/data/followMode.spec.ts' },
  },
  'chrome/OffRouteCard.tsx': {
    step: 'F6 walking it',
    flow: { status: 'covered', spec: 'e2e/data/followMode.spec.ts' },
  },
  'screens/HikeFinish.tsx': {
    step: 'F6 walking it',
    flow: { status: 'covered', spec: 'e2e/data/followMode.spec.ts' },
  },
  'screens/DaySummary.tsx': {
    step: 'F6 walking it',
    flow: { status: 'covered', spec: 'e2e/planRooms.spec.ts' },
  },
  // STILL PLANNED, AND THE REASON IS A MEASUREMENT RATHER THAN AN OMISSION
  // (2026-09-11). e2e/data/followMode.spec.ts reaches the followed map, which
  // is where the ribbon draws — but the release it pins answers 404 for
  // `trail_graph_elevation_cell_n41w075.json` and
  // `trail_graph_profile_cell_n41w075.json`, the cells under that walk, so
  // there is no profile to draw and the ribbon correctly renders nothing.
  // preview-shots/following-a-day-hike.mjs states the opposite as an
  // expectation ("THE ELEVATION RIBBON #1045 ADDED SHOULD NOW DRAW"), which
  // was honest when written — the whole-corridor profile artifact is
  // published — and is not what the cell-sharded fetch actually finds.
  // Covering this needs a walk under a published elevation cell, or that cell
  // published; neither is this spec's to decide. #1401 — "The elevation cells
  // under the followed walk 404, so the ribbon and the next-up rail both draw
  // nothing".
  'chrome/ElevationRibbon.tsx': { step: 'F6 walking it', flow: { status: 'planned' } },
  'screens/TrailRibbon.tsx': {
    step: 'F6 walking it',
    flow: { status: 'covered', spec: 'e2e/planRooms.spec.ts' },
  },

  // ---- F7 when today changes ---------------------------------------------
  'screens/HikeDay.tsx': {
    step: 'F7 when today changes',
    flow: { status: 'covered', spec: 'e2e/longHikeRooms.spec.ts' },
  },
  'chrome/StepAwaySheet.tsx': {
    step: 'F7 when today changes',
    flow: { status: 'covered', spec: 'e2e/longHikeRooms.spec.ts' },
  },

  // ---- F8 Plan ------------------------------------------------------------
  'screens/Plan.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/planRooms.spec.ts' },
  },
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
  'screens/DayHikeList.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/planRooms.spec.ts' },
  },
  'screens/TripList.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/tripRooms.spec.ts' },
  },
  'screens/FinishedHike.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/planRooms.spec.ts' },
  },
  'screens/WalkedHike.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/planRooms.spec.ts' },
  },
  'screens/StretchCard.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/settingsRooms.spec.ts' },
  },
  'screens/HikeDetail.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/data/findHike.spec.ts' },
  },
  'screens/FindHike.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/data/findHike.spec.ts' },
  },
  'chrome/FacetSheet.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/data/findHike.spec.ts' },
  },
  'chrome/SuggestedHikeCard.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/data/findHike.spec.ts' },
  },
  'chrome/DayHikesHere.tsx': {
    step: 'F8 Plan',
    flow: { status: 'covered', spec: 'e2e/mapChrome.spec.ts' },
  },

  // ---- F9 reporting -------------------------------------------------------
  'screens/YourReports.tsx': {
    step: 'F9 reporting',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/YourWork.tsx': {
    step: 'F9 reporting',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  // STILL PLANNED, and the near miss is recorded because the door that looks
  // like this screen's is not. reportingDoors.spec.ts drives "Report a
  // problem" -> a kind, and the six simple kinds are answered INSIDE
  // reporting/ReportWindow.tsx - one tap files, and "Anything to add?" is an
  // optional note after the fact. This form's own door is a waypoint card's,
  // which needs published waypoints this suite does not reach.
  'screens/ReportForm.tsx': {
    step: 'F9 reporting',
    flow: { status: 'covered', spec: 'e2e/reportingDoors.spec.ts' },
  },
  'screens/ClosureForm.tsx': {
    step: 'F9 reporting',
    flow: { status: 'covered', spec: 'e2e/reportingDoors.spec.ts' },
  },
  'reporting/ReportWindow.tsx': {
    step: 'F9 reporting',
    flow: { status: 'covered', spec: 'e2e/reportingDoors.spec.ts' },
  },
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
  'chrome/InViewSheet.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/data/builder.spec.ts' },
  },
  // NOT A NEEDLE — NO NEEDLE. Measured 2026-09-11 against the UA environment:
  // `conditions/closures.json` carries 0 closures and `conditions/reports.json`
  // 0 reports, and the serious warnings ARE escalated reports. So
  // alertSheetsPanel has nothing to place, the marks never draw, and a camera
  // derived from a mile would find nothing at it. The three ways
  // out are in #1400 — "Two safety sheets have no published data to open them, so
  // the map's alert taps go untested". This is the safety path CLAUDE.md names
  // third of four, so the gap is worth more than its line count.
  'chrome/ClosureSheet.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/SeriousWarningSheet.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/OrgNoticeSheet.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/data/mapSheets.spec.ts' },
  },
  'chrome/alertSheetsPanel.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/noticesPanel.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/data/mapSheets.spec.ts' },
  },
  'chrome/NoticeList.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/data/mapSheets.spec.ts' },
  },
  'chrome/LineSheet.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/data/mapSheets.spec.ts' },
  },
  'chrome/tappedLinePanel.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/data/mapSheets.spec.ts' },
  },
  'chrome/PoiCard.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/data/mapSheets.spec.ts' },
  },
  // NOT BLOCKED AFTER ALL, and this ledger said otherwise until 2026-09-11:
  // `retired_poi.geojson` ships inside EACH release, so the single pinned one
  // already carries tombstones and no second release is needed. The door is
  // the hiker's own work rather than the canvas — a retired place draws no pin
  // — which is the part that made it look unreachable.
  'chrome/RemovedPoiCard.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/data/newerData.spec.ts' },
  },
  // NOT A CAMERA AFTER ALL, and this ledger implied otherwise until
  // 2026-09-11. The card's "Add from your photos" is a plain file input — the
  // door a hiker uses when the picture is already in their library — so
  // `setInputFiles` reaches the share sheet without a camera and without a
  // fake. The photo is eight pixels built as bytes in the spec, never a file
  // in the tree and never anybody's picture.
  'chrome/PoiShareSheet.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/data/mapSheets.spec.ts' },
  },
  'chrome/PlaceSheet.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/identityRooms.spec.ts' },
  },
  'chrome/PressPlate.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/data/mapSheets.spec.ts' },
  },
  'chrome/Search.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/mapChrome.spec.ts' },
  },
  'chrome/Header.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/mapChrome.spec.ts' },
  },
  // NO DOOR RATHER THAN NO TEST. map/corridorLayers.ts removed the highlight
  // marks on 2026-09-08 (#1292) — "the maintainer's call was that the opening
  // camera shows trail lines only" — so nothing on the canvas raises this
  // sheet. The features and the tap path are still built; the mark is not.
  // Measured 2026-09-11: highlights.json publishes 10, and a full sweep at
  // McAfee Knob's own miles finds trail lines and nothing else, above the seam
  // and below it. #1403 — "The highlight marks were removed from the map, so
  // HighlightSheet has no door — give it one or retire it" — is the decision:
  // a band above the seam, or retire the sheet with its module.
  'chrome/HighlightSheet.tsx': { step: 'F12 the map', flow: { status: 'planned' } },
  'chrome/ElevationChart.tsx': {
    step: 'F12 the map',
    flow: { status: 'covered', spec: 'e2e/data/desktopMap.spec.ts' },
  },

  // ---- F14 volunteering ---------------------------------------------------
  'screens/Volunteer.tsx': {
    step: 'F14 volunteering',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/VolunteerHours.tsx': {
    step: 'F14 volunteering',
    flow: { status: 'covered', spec: 'e2e/reportingDoors.spec.ts' },
  },
  'screens/VolunteerImpact.tsx': {
    step: 'F14 volunteering',
    flow: { status: 'covered', spec: 'e2e/identityRooms.spec.ts' },
  },
  // NOT A DRIVE PROBLEM, measured 2026-09-11: release 2026-09-10 publishes
  // 1,943 artifacts and NONE of them is a workday or opportunities file, so
  // there are no pins to tap and the panel correctly renders nothing. A spec
  // cannot fix that; a publish can — #1402, "No workday artifact is published,
  // so the volunteer pins and their sheet have nothing to draw". Left
  // `planned` rather than
  // `unit-only` because the surface is meant to be drivable, and will be the
  // day the pipeline publishes what it reads.
  'chrome/WorkdaySheet.tsx': { step: 'F14 volunteering', flow: { status: 'planned' } },
  'chrome/workdayPanel.tsx': { step: 'F14 volunteering', flow: { status: 'planned' } },
  'chrome/ClubSheet.tsx': {
    step: 'F14 volunteering',
    flow: { status: 'covered', spec: 'e2e/data/mapSheets.spec.ts' },
  },
  'screens/GroupScreen.tsx': {
    step: 'F14 volunteering',
    flow: { status: 'covered', spec: 'e2e/tripRooms.spec.ts' },
  },

  // ---- F13 More, settings and identity -----------------------------------
  'screens/More.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/Settings.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/settingsRooms.spec.ts' },
  },
  'screens/AboutBuild.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/Registry.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'screens/GpsTrace.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/more.spec.ts' },
  },
  'screens/PaceSettings.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/settingsRooms.spec.ts' },
  },
  'screens/IdentitySetup.tsx': { step: 'F13 More', flow: { status: 'planned' } },
  'screens/EmailSignIn.tsx': {
    step: 'F13 More',
    flow: {
      // Not "planned": no build this project ships can render it. Measured
      // 2026-09-11 by driving More → You → Sign in, which offers "Continue
      // with Google" and nothing else. lib/supabase.ts is why - email left
      // ENABLED_PROVIDERS' default because Supabase's built-in sender "is
      // not a delivery path this project can ship on", and this screen is
      // only mounted when SignInPrompt offers the email provider. It comes
      // back with a sender behind it, and a flow test comes back with it.
      status: 'unit-only',
      why: 'Unreachable in any shipped build: ENABLED_PROVIDERS defaults to google alone (lib/supabase.ts), and this screen is mounted only when the sign-in prompt offers email. EmailSignIn.test.tsx holds the form; a flow test would need a build flag no deployment sets.',
    },
  },
  'screens/SignInPrompt.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/identityRooms.spec.ts' },
  },
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
  'screens/MapDetailPicker.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/settingsRooms.spec.ts' },
  },
  // COVERED IN THEIR ABSENT STATE, WHICH IS THE ONLY ONE THIS SUITE CAN
  // REACH - and is a real assertion about the surface rather than a pass
  // through it, so `covered` is the honest status. Both render null on the
  // phone the flow suite drives, each for a stated reason: the background
  // picker because #855 withdrew the raster archive and "a segmented pair
  // with one segment left in it is not a choice", the sources section
  // because an empty steward list gets nothing rather than an empty heading.
  // The present halves - two backgrounds to choose between, one card per
  // organization with its licence verbatim - need published data this suite
  // deliberately does not reach (playwright.config.ts), and stay unwritten.
  'chrome/BackgroundPicker.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/settingsRooms.spec.ts' },
  },
  'chrome/SourcesSection.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/settingsRooms.spec.ts' },
  },
  'chrome/DownloadsLink.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/settingsRooms.spec.ts' },
  },
  'screens/ReportBug.tsx': {
    step: 'F13 More',
    flow: { status: 'covered', spec: 'e2e/failurePaths.spec.ts' },
  },

  // ---- The download, which is its own flow at every step ------------------
  // The window on an EMPTY phone: what it offers, and every trail-data row
  // answered for. The transfer itself - a bar moving, a pause, a delete - is
  // a network journey against the bucket, and stays out of this suite.
  'screens/Downloads.tsx': {
    step: 'The download',
    flow: { status: 'covered', spec: 'e2e/settingsRooms.spec.ts' },
  },
  'screens/DownloadsDialog.tsx': {
    step: 'The download',
    flow: { status: 'covered', spec: 'e2e/settingsRooms.spec.ts' },
  },
  'screens/DownloadCard.tsx': {
    step: 'The download',
    flow: { status: 'covered', spec: 'e2e/settingsRooms.spec.ts' },
  },

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
  // NOT STATIC AFTER ALL, and this entry said it was until 2026-09-11. The
  // exemption read "static credit text required on every frame", which is
  // true of WHAT it says and wrong about WHAT IT IS: the component forks on
  // width. A phone gets a `<details>` whose summary reads "© OpenStreetMap
  // contributors · 2 more", because ODbL demands prominence and a 390px
  // column cannot carry three clauses without eating map; a laptop gets all
  // three on one line with nothing behind a disclosure. Measured on the same
  // boot in both projects. That is a `@desktop` claim rather than a leaf, so
  // it is driven rather than exempted.
  'chrome/MapAttribution.tsx': {
    step: 'shared',
    flow: { status: 'covered', spec: 'e2e/desktopSpine.spec.ts' },
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
