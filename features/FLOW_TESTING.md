# Flow testing (Playwright)

`client/src/test/reachability.test.ts` already names the ladder this document climbs one
rung higher: "Imported is weaker than rendered, and rendered is weaker than findable... A
door a hiker can find without knowing the screen exists is the review's standard, and
that is read from the screens, not from this graph." As of #1374 the client suite proves
_imported_ (that graph) and _rendered_ (7,255 vitest + testing-library assertions,
measured at `6f29a093`) exhaustively. Nothing proves _findable_ — that a hiker, in a real
browser, can actually tap their way from the app's real entry point to a screen — or its
mirror, _exitable_ — that every screen can be left, and that a guarded exit's every
branch does what it promises. jsdom does not run real layout, real CSS visibility, real
focus and event dispatch, or the real bundled build a phone actually loads; a component
can pass every unit test and still be unreachable, or un-leaveable, in a real browser.
That gap — not a shortage of tests — is what keeps letting a broken flow through: the
suite is large and disciplined and still cannot see it.

This document is the rules. The coverage checklist near the end says what actually has a
Playwright test today and what is a named, open gap — not an exemption, the same
distinction `reachability.test.ts`'s own ledger comment insists on for itself.

## The four rules

**1. Entrance.** Every screen the app can show has at least one Playwright test that
reaches it via a real, currently-shipped door — an actual tap sequence from boot, never
a URL or an injected navigator state — and asserts it is actually visible (`toBeVisible`,
which checks real layout and CSS, not merely present in the DOM).

**2. Exit.** Every screen can be left. Where a move is guarded (the bail sheet — decision
**D8**, "every exit from a half-built route shows the bail sheet"), the test drives every
branch — `proceed` and `stay`, and each button behind them — and asserts the end state
each one promises, not just that the sheet opened. Where a move is unguarded, the test
still drives the escape and asserts it actually lands — a swallowed tap is exactly the
regression this rule exists to catch, and "nothing is guarding it" is not the same claim
as "it works."

**3. States.** Each screen's data-driven states get their own seed and their own
assertion, not just the default happy path. A screen's states are read off its own
conditional rendering (see the checklist), not off a generic list — this app's actual
branches are things like "no download yet" vs. "a `Notice` " (Today), "the network is
unreachable" vs. "three live doors" (step 1), "cached figures because the network is
gone" vs. "live" (step 3's review card) — not a boilerplate loading/error/empty triad
that would fit any app and describe none of them precisely.

**4. Visible at design time.** Whoever specs a screen — a design doc, a wireframe, a
review — writes its entrance, its exit, and its states down as part of that spec, the
same way `features/PATHWAY.md` and #1374's own pull request ledger already narrate what
each screen became and how. Not left for whoever implements the test to infer later from
the component. A spec that says "Details, and Save" without saying what Details looks
like with no water on the route, or what happens if Save is tapped and then the tab bar
is tapped before it resolves, has not finished specifying the screen — it has specified
the happy path and called it the screen.

## What "entrance" and "exit" are, mechanically

`client/src/lib/navigator.ts` is the one navigator (#1373, phase 0): four tabs
(`today` | `map` | `plan` | `more`), each with a stack of `Screen`s, and one `navigate()`
every move goes through. This is what the two rules above cash out to in code, and a
test that does not respect this model is testing something other than what the app does:

- A `push` is an **entrance**. It is never guarded — "a card or a sheet opened over step 2
  leaves the step on the stack and is not asked about."
- An **exit** is whatever a `tab` / `back` / `home` / `replace` move causes `applyMove` to
  drop from a stack, _if the currently-set guard says so_. The guard is
  `(leaving, move, state) => B | null`, run against a throwaway copy of the next state
  before it is committed; a non-null return **parks** the move as `state.pending` instead
  of applying it, and nothing changes until `proceed()` (re-applies the parked move,
  guard not re-consulted) or `stay()` (drops it, state untouched).
- **`leaving` can be empty on a real exit.** "The builders live on the map," not on a
  stack, so a tab tap away from a live map builder can guard-park with `leaving === []`.
  A test must not infer "this move is guarded" from a non-empty diff — assert on whether
  the bail sheet actually appears, not on the stack shape.
- Two hard-coded exceptions, not screen-by-screen special cases: `keptAcrossTabs` (only
  `more` screens survive a tab switch elsewhere) and `returnsToOrigin` (only `more`
  screens' Back returns to the tab that opened them; the spine's `step` screens always
  return Back to Plan's room, "whatever door opened it").
- **Not a router.** Nothing here touches the URL or the History API. A Playwright spec
  can never shortcut to a screen with `page.goto()` or by writing navigator state
  directly — every entrance is a real tap sequence from the app's actual boot, exactly
  as `client/preview-shots/*.mjs`'s `drive(page)` recipes already do it, because that is
  the only way "findable" means anything.

## How a spec seeds state

This app is offline-first: almost everything a screen reads is in IndexedDB
(`idb-keyval`), not fetched live. The existing infrastructure already has the idiom —
reuse it rather than inventing a second one:

- **Seed via IndexedDB, then reload.** `client/scripts/screenshot.mjs`'s `skipFirstRun()`
  and `client/preview-shots/fixtures/longHike.mjs`'s `seedLongHike()` both write directly
  into the `keyval-store` database via `page.evaluate(() => indexedDB.open(...))`, then
  `page.reload()` so the app boots already hydrated. A spec seeds the same way. Import
  the existing fixtures (`tripStore`, `finishedStore`, `seedLongHike` from
  `preview-shots/fixtures/longHike.mjs`; `suggestedHikes.mjs`) rather than re-deriving
  hike data — one home per fixture, same as one home per recipe.
- **Mock geolocation with Playwright's own primitives**, not a manual stub —
  `context.setGeolocation()` and `context.grantPermissions(['geolocation'])` are real
  browser APIs Playwright exposes for exactly this, unlike `appHarness.ts`'s vitest-only
  `navigator.geolocation` stub, which has no equivalent in a real browser context.
  `reportFixAtMile`'s vitest math (`client/src/test/appHarness.ts`) is still the source
  for what latitude a given mile of the synthetic centerline sits at — reuse the
  constant, not the stub.
- **Locators are accessible-role queries, exactly as the vitest suite already writes
  them** — `getByRole('tab', { name: 'Plan' })`, `getByRole('dialog', { name: '...' })` —
  never CSS selectors. The app's ARIA is already strong enough that `App.pathway.test.tsx`
  and every `preview-shots` recipe already query this way; a Playwright spec that reached
  for a class name would be testing markup the component owns no contract over.
- **Wait on something observable, never a fixed timeout**, per CLAUDE.md's own rule.
  `legend.mjs`'s `drive` is the worked example: it polls `scrollHeight` until it stops
  changing rather than sleeping a guessed duration, specifically because the sandbox and
  CI settle at different speeds and a fixed wait that passes on one fails on the other.
- **Run anything awaiting an effect three times before it is pushed** — CLAUDE.md's
  existing rule for the vitest suite applies exactly as hard here, and more: a real
  browser adds real animation frames and real network waterfalls on top of the mocked
  promises vitest already made ordering-sensitive.
- **Mocking boundary.** `maplibre-gl` is mocked at the module level for vitest
  (`vi.mock('maplibre-gl', ...)`); a real browser cannot intercept an import statement,
  so MapLibre runs for real in a Playwright spec. This is already proven to work without
  a network path: `screenshot.mjs` already runs a real MapLibre instance against a vite
  dev server with no reachable tile source and gets a blank paper background rather than
  a crash. A spec that touches the map only needs the DOM/chrome around it (sheets,
  taps, the legend), never the rendered tiles — pixel-level map rendering stays the
  screenshot recipes' job, not this suite's.

## Boundaries — what this does not do

- **No visual regression.** Playwright's `toHaveScreenshot()` is not used here. A picture
  of what changed is `client/preview-shots/`'s job (`.claude/skills/pr-screenshot/SKILL.md`);
  this suite asserts DOM/accessibility state, not pixels.
- **No duplicating the vitest layer.** Where `App.pathway.test.tsx`, `App.dayHike.test.tsx`,
  `App.navigator.test.tsx`, `App.desktopSpine.test.tsx` or `navigator.test.ts` already
  hold a piece of logic at the rendered layer, a Playwright spec for the same flow is
  there to prove _findable_, not to re-derive the same assertion — it should drive the
  same user-visible sequence and assert the same outward state, and may be shorter than
  its vitest counterpart precisely because it is not also responsible for covering every
  branch of the underlying logic.
- **Map tile data.** From an agent sandbox, Chromium cannot reach any external host at
  all (measured against `data.ourhike.org` and against `example.com`, both
  `net::ERR_CONNECTION_RESET` — `client/scripts/screenshot.mjs`'s own comment). A spec
  that needs real trail geometry seeds it into IndexedDB (as above); a spec that
  genuinely needs a live network round trip only runs meaningfully in CI, against a real
  preview, the same split `screenshot.mjs --url` already lives with.

## New dependency

`playwright` (the raw browser-automation package) is already a devDependency, used by
`client/scripts/photograph-preview.mjs` to run the screenshot recipes — it is not a test
runner and has no `describe`/`test`/`expect`, and there is no `playwright.config.ts` or
`client/e2e/` anywhere in the repo today. This work adds `@playwright/test` (the test
runner built on the same engine) as a new devDependency, specifically for the config,
retries, HTML report, and `expect` matchers a real assertion suite needs and a sequence
of `capture()` calls does not.

## Coverage checklist

The rows are `features/PATHWAY.md`'s own spine table. **Playwright** columns are this
suite; **vitest** notes what already exists at the rendered layer, so this table does not
read as though nothing was tested before it. A blank Playwright cell is a gap, named
here rather than silently absent — the same ledger discipline `reachability.test.ts`
applies to itself.

| screen                                                    | vitest (rendered)                                                            | Playwright (findable / exitable)                                                                                                                                                       |
| --------------------------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| First run (5 cards)                                       | `Onboarding.test.tsx`                                                        | `e2e/onboarding.spec.ts` — entrance (fresh boot), the mode and place cards, skip exit                                                                                                  |
| Today                                                     | `Today.test.tsx`                                                             | `e2e/today.spec.ts` — entrance per mode, download `Notice` present/absent, alerts block                                                                                                |
| Step 1 · Hike (`PlanStart.tsx`)                           | `App.pathway.test.tsx`                                                       | `e2e/planSpine.spec.ts` — entrance from Today's pinned bar and from Plan's own primary, the network-refusal state, Cancel exit                                                         |
| Step 2 · Route                                            | `App.dayHike.test.tsx`                                                       | `e2e/planSpine.spec.ts` — the rail's round trip (R3), "‹ Hike" exit with the draft kept                                                                                                |
| Step 3 · Details, and Save                                | `App.dayHike.test.tsx`                                                       | `e2e/planSpine.spec.ts` — "‹ Route" exit, Save landing on the saved card                                                                                                               |
| The bail sheet (D8)                                       | `App.pathway.test.tsx`                                                       | `e2e/bailSheet.spec.ts` — all three branches (Stay / Discard / Keep it for later), the unguarded-app-move negative case, and the `sweepForBuilder` gap (`test.skip`, blocked on #1387) |
| Walking it (the follow card, the finish ask)              | `App.followDayHike.test.tsx`                                                 | _(open — needs `context.setGeolocation`; not yet written)_                                                                                                                             |
| When today changes (the cascade)                          | `Plan.test.tsx`                                                              | _(open)_                                                                                                                                                                               |
| Plan home / What's left                                   | `PlanHome.test.tsx`, `DayHikeList.test.tsx`                                  | _(open)_                                                                                                                                                                               |
| Reporting (Your reports / Your work)                      | `App.yourReports.test.tsx`, `YourReports.test.tsx`, `YourWork.test.tsx`      | _(open)_                                                                                                                                                                               |
| The Map (In view, the two safety sheets, the legend fold) | `App.mapOverlays.test.tsx`, `closureLayers.test.ts`, `warningLayers.test.ts` | _(open)_                                                                                                                                                                               |
| Volunteering                                              | `workdayPanel.test.tsx`, `workProjects.test.ts`                              | _(open)_                                                                                                                                                                               |
| Desktop layout variants                                   | `App.desktopSpine.test.tsx`, `desktopLayout.test.ts`                         | _(open — every row above, at the desktop breakpoint)_                                                                                                                                  |

## Known gaps this framework did not create

- **`sweepForBuilder` is the one exit the guard cannot see.** #1374's review found it and
  named it explicitly: a live day-hike draft under step 1 survives an ordinary tab tap
  (the guard asks, correctly), but switching the hiker-mode to Long and then tapping
  "Pick on the map" sweeps the same draft with no bail sheet at all —
  `sweepForBuilder` runs outside `navigate()`, so the guard never sees the move.
  `e2e/bailSheet.spec.ts` carries the repro written out in full as a `test.skip`, not a
  currently-red case: building it surfaced a second, smaller gap first — day mode's step 1
  hides its entire "Start from" doors group (decision D10's own "Where I am" included)
  behind a trail-network refusal, and nothing in this repo can make that network read
  `ready` without either a real fetch (unreachable from an agent sandbox, and from
  anywhere this suite's own CI job runs, per the boundaries above) or a graph-shard
  fixture that does not exist yet. That's **#1387 — Neither the Playwright suite nor the
  screenshot recipes can put a live draft in the day-hike builder without a reachable
  bucket**. The skipped test is the target, not a placeholder: once #1387 lands, seeding
  the shard and deleting the `.skip` is the whole remaining change.
- **The `Today.tsx` pinned-bar comment cites "rule R4"** for "Find and Plan on every
  state of this screen, forever" — but `features/PATHWAY.md`'s actual R4 is "The mode
  stays global," unrelated. Likely a citation surviving from the original ClaudeDesign
  review's own numbering rather than PATHWAY's curated R1–R11. Not fixed here — flagged
  so the next person citing a rule number checks it against PATHWAY.md rather than
  against another comment.
- **PATHWAY.md reuses the label "D" for two different, independently-numbered lists** —
  six defects (D1–D6) and fourteen decisions (D1–D14). They collide: defect **D5**
  ("Bailing cost work, silently") and decision **D8** ("every exit... shows the bail
  sheet") are both about the same mechanism, under different numbers in different lists.
  Every citation in this document says which list.
