# The pathway — first run → Today → Hike → Route → Details → walking it → what today changes

The design of record for the front end since 2026-09-10:
[#1373 — The front end becomes one pathway: first run → Today → Hike → Route →
Details → walking it → what today changes, from the ClaudeDesign flow
review](https://github.com/OurHike/OurHike/issues/1373), built in
[#1374 — One pathway from first run to a walk finished: the front-end rebuild from
the ClaudeDesign flow review](https://github.com/OurHike/OurHike/pull/1374). The
review itself (`design_handoff_frontend_rebuild`, ClaudeDesign, exported 2026-09-09
against tree `5e4ed2f`) is a maintainer upload rather than a repository file, so this
page holds what a reader of the code needs from it: the defects it named, the rules and
decisions it fixed, where each lands, and what was deliberately not built. The issue
holds the plan and the inventory's findings; the pull request holds the ledger of what
changed, surface by surface.

The argument in one line: **OurHike was a set of capable surfaces a hiker had to
assemble themselves; this replaces them with a pathway.** Three visible steps in the
middle — Hike → Route → Details — always visible, always bailable, always showing what
they claim.

## The six defects it exists to fix

| | Defect | Where it lived | What fixed it |
|---|---|---|---|
| D1 | Three front doors, no address — Today, the Map, Plan's two rooms, nothing saying which you were in | `chrome/tabs.ts`, `screens/Today.tsx`, `chrome/MapScreen.tsx` | The navigator (`lib/navigator.ts`): four tabs, a stack over each, one `navigate()`; the mode read-out in the tab row (R11) |
| D2 | The same fork asked twice — the mode switch decided the Plan room, then the kind sheet asked again | `lib/hikerMode.ts`, `screens/PlanHome.tsx`, `chrome/PlanKindSheet.tsx` | `PlanKindSheet` retired; the mode is the answer to step 1's first stop (D6 below) |
| D3 | Plan was a filing cabinet — storage for a plan a new hiker could not yet make | `screens/PlanHome.tsx`, `TripList.tsx`, `DayHikeList.tsx` | Step 1 — "Where do you want to go?" (`screens/PlanStart.tsx`) — where the Plan tab's primary and Today's pinned Plan both land |
| D4 | Four grammars for one journey — a bar, a sheet, a panel, a card | `chrome/DayHikePickBar.tsx`, `RouteStopsPanel.tsx`, `screens/DayHikeCard.tsx` | One rail (`chrome/StepRail.tsx`) at the head of each, "‹ back" and "on ›" as each foot, Save the last button |
| D5 | Bailing cost work, silently | `sweepForBuilder` in `App.tsx`, `lib/dayHikeDraft.ts` | The bail sheet: the navigator parks a tab tap that would leave a live builder and asks |
| D6 | Empty states were refusals | `lib/trailNetworkText.ts`, `screens/PlanHome.tsx` | A setup screen per mode on Today; a refusal is a sentence with a door beside it (R5, D10) |

## The eleven rules

Each is held by a test somewhere; the file named is where to look first.

- **R1 · Bailing asks.** Leaving a step mid-build always asks — keep the draft, discard it, or stay. Never silent, never assumed. `lib/navigator.ts`'s guard, `App.pathway.test.tsx`.
- **R2 · The map never leaves.** Map and step column share the screen — side by side on a desktop, stacked on a phone; Details is read against the route it describes. On a desktop, since the maintainer's review of #1374, all three steps are one column on the right of the map — step 1 handed to the same beside-the-map slot as steps 2 and 3, the builder's bar folded into the column's foot with its figures left to the column, and a figure following the pointer over the route (`chrome/useRouteHover.ts`) — where #1194 had put step 2's rail on the left with the bar along the bottom of the map (`desktop.css`, `App.dayHike.test.tsx`, `App.desktopSpine.test.tsx`); on a phone step 1 is Plan's page, step 2 the band and the bar, step 3 a sheet over the map.
- **R3 · One rail, three stops.** Hike, Route, Details; a finished step can be gone back to without losing the later one. `chrome/StepRail.tsx`; "‹ Hike" keeps the route, "‹ Route" keeps the name and date.
- **R4 · The mode stays global.** "Today I'm…" keeps re-ranking Today and sets step 1's default answer; it never moves a hiker between rooms behind their back. `lib/hikerMode.ts`.
- **R5 · No refusal without a door.** A missing capability names what a hiker can do instead, in the same block as the refusal — download, retry, or a published route. Audited per phase in the pull request's ledger.
- **R6 · Figures are the same figures.** Miles, time at your pace, gain and gaps print through `lib/units.ts` and `lib/pace.ts` everywhere. `test/unitDisplay.test.ts` is the guard.
- **R7 · A day is always three figures** — distance, time at the hiker's pace, gain — in one row component (`chrome/DayRow.tsx`). Where a figure is unmeasured the row says so rather than printing zero.
- **R8 · The map keeps its own controls** (`map/mapChrome.ts`): compass and locate bottom-right, the scale bar bottom-left, the legend beside it; locate is absent, not disabled, where location is off.
- **R9 · Any day can be edited, and it cascades** — shown as the diff first (`lib/cascadeDiff.ts`), applied when the hiker says so, undoable in one action.
- **R10 · A legend names five trails, then condenses** (`NAMED_TRAILS_SHOWN` in `chrome/Legend.tsx`, `@unvalidated` — the frame's own count).
- **R11 · Four tabs and the mode, on every screen** — a read-out that opens the one control, never a second switch (`chrome/TabBar.tsx`); since 2026-09-10 the left chip of the tab row rather than a row above it, because the row wrapped the phone's bar to three rows (105 px measured at 375×667, against 45 px) and the brand mark it displaced had nothing to say that the tabs did not. First run carries no read-out, but since the review of #1374 it asks the mode once, on its second card, rather than assigning Day hike silently; a desktop's sidebar carries the switch itself.

## The decisions, which were the acceptance list

D1 a hike mid-walk **is** editable from step 2, and entering the builder stops following, said on screen first · D2 **Find a hike and step 1 are one screen**, the full finder behind "N hikes ›" · D3 the GPS trace is a plain row at the foot of "Where this map comes from", labelled a field-test tool, keeping #1201's gate · D4 the source registry carries the `isModerator` gate moderation has · D5 three encounter-only surfaces got doors — your own photos and notes, a way to ask for day hikes near here, one shelf for walked history · D6 the kind of hike is answered by the mode switch and never asked again · D7 Save lives on step 3, never as a step of its own · D8 every exit from a half-built route shows the bail sheet · D9 publisher names are read from the registry, never written into a sheet · D10 a refusal is a sentence, never a disabled control · D11 nothing is replaced without the hiker being asked · D12 no score, no streak, no leaderboard · D13 omit rather than guess — a null line is absent, never "Unknown" · D14 figures never outrun their source — cached says cached, unmeasured says so, durations are never arrival clocks.

## The spine, and where each step lives

| step | screen | file |
|---|---|---|
| First run — value, **what brings you out** (the mode, asked rather than assigned — the maintainer's review of #1374, 2026-09-10; a skip says it means Day hike), **where you hike** (a synced preference, `default_place`; a place named, never a fix — `lib/defaultPlace.ts`), the download, location | five cards over the map | `screens/Onboarding.tsx`, `chrome/PlaceField.tsx` over #1371's `places.json`, `lib/hikerMode.ts` |
| Today — a setup head per mode until something is loaded; the walk dated today as a card; "Ahead of you" as waypoint rows; the pinned Find / Plan bar | | `screens/Today.tsx`, `chrome/PinnedBar.tsx`, `chrome/PoiRow.tsx` |
| Step 1 · Hike — "Where do you want to go?" | the Plan tab's slot | `screens/PlanStart.tsx`, the bail sheet in `chrome/BailSheet.tsx` |
| Step 2 · Route — the rail on both builders, the shape as one control | the map, the rail on a desktop | `chrome/DayHikePanel.tsx`, `chrome/DayHikePickBar.tsx`, `chrome/RouteStopsPanel.tsx` |
| Step 3 · Details, and Save — the review card, water and stops on the walk's own axis, the long hike's days before they are kept | the map's sheet on a phone, the rail on a desktop | `screens/DayHikeCard.tsx`, `screens/PlanTargetSheet.tsx`, `lib/dayHikeWater.ts` |
| Walking it — the next-turn card with the coverage note at its head, "What's left today", the finish asked | over the map | `chrome/NextTurnCard.tsx`, `lib/openWalk.ts` |
| When today changes — the cascade's moves with costs, the diff, one undo | the timeline | `screens/Plan.tsx`'s cascade sheet, `lib/cascade.ts`, `lib/cascadeDiff.ts` |
| Plan — one hike, sections, day hikes, "What's left ›", the walked shelf | | `screens/PlanHome.tsx`, `screens/WhatsLeft.tsx` |
| Reporting — your reports with status, your photos and notes | More | `screens/YourReports.tsx`, `screens/YourWork.tsx`, `lib/sentReports.ts` |
| The Map — In view, the two safety sheets on their taps, the legend's fold | | `chrome/InViewSheet.tsx`, `chrome/alertSheetsPanel.tsx`, `map/closureLayers.ts`, `map/warningLayers.ts` |
| Volunteering — the shovel pin, the day window, workdays in view, a place search | the map | `chrome/workdayPanel.tsx`, `lib/workProjects.ts`, `chrome/Search.tsx` |
| A desktop — the journal beside the map, step 3 in the rail | | `desktop.css`, `chrome/MapScreen.tsx`'s `journal` and `builderPanel` slots |

## What was deliberately not built, and why

The pull request's "Deferred inside the phases" list is the full record; the pattern is one rule applied many times. **A figure with no evidence grade is not printed** — "last water for 9 mi", the remaining climb, a day's high point, "3 routes through these stops" and the closure-to-day join are each a derivation nobody has measured, and the last of them would be a confident wrong answer on the one path that is about danger (ATC's closure miles disagree with the published axis by a median 7.7 mi, HIKE_PLANNING.md Finding 3). **A door is a claim** — the GPX export, "Check what's downloaded", "Invite someone" and the four-tab strip are drawn nowhere until something stands behind them. **Nothing closes a walk on its own** — the finish is asked, and asked again the next morning; an arrival detector is alert-shaped and a false one would be crying wolf on the record that says a walk was done. **Nothing is persisted that the phone deliberately does not keep** — where and when a walk stopped, a parked draft across a restart.

## Where the design and the code disagreed, and which won

Recorded in the issue's inventory section with a decision per item. The ones a reader of the code will meet: the cooling-off on a photo is 2 h, not 12 (#577); the plan text prints no time (maintainer, 2026-08-25); ten topo palettes, not two (`map/liveTopo.ts`); photo flags keep #579; the four-tab More strip was replaced by destination rows on the maintainer's approval (#1062) and the design's four groups are those rows'; the sidebar stacks the mark icon-over-wordmark, a recorded deviation from the design system's horizontal lockup.

## The camera

Every screen on the spine has a recipe under `client/preview-shots/` (`plan-step-1.mjs`, `day-hike-builder.mjs`, `day-hike-step-3.mjs`, `plan-step-3.mjs`, `day-hike-card.mjs`, `following-a-day-hike.mjs`, `whats-left.mjs`, `your-reports.mjs`, `your-work.mjs`, `in-view.mjs`, `today-desktop.mjs`, `day-hike-step-3-desktop.mjs`, among the standing ones), so a pull request that changes one is photographed at review. What a recipe cannot reach — a walked day, a fix on a route, a moderator — the named test holds instead, and the pull request says which.
