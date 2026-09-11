# Flow testing (Playwright)

[TESTING.md](../TESTING.md) is the project's testing philosophy and this does not replace
it. This is the flow layer specifically: what it is for, how a flow test is formed, what
every flow has to be tested across, and what must be tested. TESTING.md's long-term
strategy item 3 asked for exactly this layer — "a real-browser layer lands between jsdom
and the trail" — and #1386 is where it started.

`client/src/test/reachability.test.ts` names the ladder: "Imported is weaker than
rendered, and rendered is weaker than findable... A door a hiker can find without knowing
the screen exists is the review's standard, and that is read from the screens, not from
this graph." The client suite proves _imported_ (that graph) and _rendered_ (7,255 vitest
assertions) exhaustively. Nothing proved _findable_ — that a hiker, in a real browser, can
tap their way from the app's real entry point to a screen — or its mirror, _exitable_.
jsdom does not run real layout, real CSS visibility, real focus and event dispatch, or the
real bundled build a phone loads; a component can pass every unit test and still be
unreachable, or un-leaveable, in a real browser. That gap — not a shortage of tests — is
what lets a broken flow through a large, disciplined suite.

## The four rules

**1. Entrance.** Every screen has at least one test that reaches it by a real,
currently-shipped door — an actual tap sequence from boot, never a URL and never an
injected navigator state — and asserts it is actually visible (`toBeVisible`, which reads
real layout and CSS, not mere presence in the DOM).

**2. Exit.** Every screen can be left. Where a move is guarded (the bail sheet — decision
**D8**), the test drives every branch — `proceed` and `stay`, and each button behind them
— and asserts the end state each promises, not just that the sheet opened. Where a move is
unguarded, the test still drives the escape and asserts it lands: a swallowed tap is
exactly the regression this rule exists to catch, and "nothing is guarding it" is not the
same claim as "it works".

**3. States, across every axis below.** Not the happy path plus a shrug. A screen's states
are read off its own conditional rendering, and the axes in the next section are the ones
that have already produced defects here.

**4. Visible at design time.** Whoever specs a screen writes its entrance, its exit and its
states down as part of that spec — the same way `features/PATHWAY.md` and #1374's ledger
already narrate what each screen became. A spec that says "Details, and Save" without
saying what Details shows with no water on the route, or what happens when the tab bar is
tapped mid-save, has specified the happy path and called it the screen.

## The axes every flow is tested across

A "state" here is not a vague adjective. These five axes are the ones this app actually
varies along, each with a defect or a code branch behind it rather than a hypothetical.

### Mode — day, long, **and volunteer**

`lib/hikerMode.ts` has three values and the third is routinely forgotten, including by the
first pass of this suite. The mode is not cosmetic: it re-ranks Today, picks Plan's room,
and answers step 1's first question.

- **Today** renders one of three arrangements from three `order` arrays. Day with nothing
  planned heads "Nothing planned today"; long with no hike heads "You have no hike yet";
  **volunteer has no setup head at all** — `setup` is a two-branch ternary, so it is null in
  volunteer mode, and the crew card leads instead (`today__card--volunteer-lead`).
- **Plan** has two rooms, not three: `screens/PlanHome.tsx` — "VOLUNTEER GETS THE DAY ROOM,
  and there is no third room." Volunteer plans as a day hiker (`PlanStart.tsx`'s
  `planMode = mode === 'long' ? 'long' : 'day'`), so a day-room assertion covers it and a
  third room would be wrong to test for.
- The rule: **if a screen reads the mode, all three modes are asserted.** If it demonstrably
  does not, one is enough and the spec says which and why.

### Device — phone and desktop

`lib/useDesktop.ts`'s breakpoint is a real fork, not a reflow, and the worked example is
the one that cost this suite an afternoon: the bail guard is
`move.to === 'tab' && mapShownUnder(state.tab) && !mapShownUnder(move.tab)`, and
`mapShownUnder` is `tab === 'map' || (isDesktop && tab === 'today')`. So **tapping Today
while a builder is live is a guarded exit on a phone and not an exit at all on a desktop**,
because the desktop keeps the map beside Today. A suite that ran only one width would call
the other's behaviour a bug.

The suite currently runs one project, a phone at 390×844 (the viewport
`client/scripts/screenshot.mjs` sizes against, so a spec and a shot describe the same
device). **A desktop project is a block, not a project:** add a second entry to `projects`
in `playwright.config.ts` with the desktop viewport, and scope specs to the device they
mean with a `@phone` / `@desktop` tag or a per-project `testMatch` — because most specs are
meaningful at one width and running all of them at both would assert the wrong layout
twice. `App.desktopSpine.test.tsx` and `desktopLayout.test.ts` hold the desktop layout at
the rendered layer meanwhile.

### Engine — Chromium and WebKit, which is the iOS-versus-Android question

The client is one codebase wrapped by Capacitor, so **there is no iOS build and Android
build of the logic** — there is one web bundle in two WebViews. TESTING.md's Platforms
section already draws this line and this layer inherits it exactly:

- **What an engine project can attest.** Playwright's Chromium and WebKit are the engines
  the two WebViews embed, so running the same specs on both is a cheap, CI-runnable check
  of the differences that are _rendering and JS engine_ differences. TESTING.md's own words:
  "which makes an engine-level smoke check cheap and runnable in CI."
- **What it cannot.** Storage eviction and WebKit's seven-day cap, permission prompt flows,
  background GPS, real touch, HEIC decoding, service-worker semantics inside a Capacitor
  shell serving from a local origin. These are platform policy and device behaviour. They
  are Phase 3 acceptance runs on real devices plus field testing — a documented manual
  procedure, the same category as the full USGS fetch. **Appium, not Playwright, is the
  tool if those are ever automated**, and nothing here pretends otherwise.
- **Status: not yet run.** A WebKit project is a four-line addition to `projects`, and it is
  deliberately not added yet, because no environment this suite has been written in has
  WebKit installed (`/opt/pw-browsers` holds Chromium alone), and a project whose first run
  is in CI is a project whose first result is a red pull request. Whoever turns it on runs
  it locally first, in an environment with `npx playwright install webkit`, and fixes what
  the engine difference turns up in the same change. `@unvalidated` until then.

### Data freshness — live, cached, and absent

The same screen prints different numbers with different provenance, and CLAUDE.md's "never
let a display outrun its source" is the rule this axis defends. The worked example is
`screens/DayHikeCard.tsx`, which has all three and says which it is showing:

- **Live** — the graph resolved the walk, so the figures are today's and ways off can be
  worked out.
- **Cached** — `resolved === null`, so the card prints the figures stored at save time
  under a sentence naming that, and deliberately prints no climb over them.
- **Which absence** — the same null forks again on `networkAvailable`: "This phone's current
  trail map can't place this walk…" versus "This phone has no trail network…", because what
  a hiker can do about it differs.

Every screen that reads published data has some version of this. **A flow test asserts the
sentence, not just the number** — a card that silently swaps cached figures for live ones is
the defect, and the number alone cannot see it. Note that the sandbox and CI's dev server
both reach _no_ graph, so the cached branch is the one a spec gets by default and the live
branch needs the fixture #1387 tracks.

### Hike profile — an empty install is not the app

Most defects live past the empty state, and the empty state is what a spec gets for free.
Seed a real hike and drive against it:

- `client/preview-shots/fixtures/longHike.mjs` — `tripStore()` (a hike with two sections,
  eight days in, days dated around today), `finishedStore()` (the same walked end to end),
  and `seedLongHike(page)`.
- `client/preview-shots/fixtures/dayHike.mjs` — `DAY_HIKES` and `seedDayHikes(page)`: one
  saved day hike with its legs, figures and a second organisation's credit.
- Both are **nobody's data** by construction — invented names, invented figures, no account,
  no location fix — and both are shared with the shot recipes, so a fixture is fixed in one
  place. Dates are relative to the browser's own today, deliberately: a fixture pinned to a
  date photographs a card in September and no card at all in March.

## What "entrance" and "exit" are, mechanically

`client/src/lib/navigator.ts` is the one navigator (#1373, phase 0): four tabs
(`today` | `map` | `plan` | `more`), each with a stack of `Screen`s, and one `navigate()`
every move goes through.

- A `push` is an **entrance**, and is never guarded — "a card or a sheet opened over step 2
  leaves the step on the stack and is not asked about."
- An **exit** is whatever a `tab` / `back` / `home` / `replace` move drops from a stack, _if
  the currently-set guard says so_. The guard is `(leaving, move, state) => B | null`, run
  against a throwaway copy before the move is committed; a non-null return **parks** the move
  as `state.pending` and nothing changes until `proceed()` or `stay()`.
- **`leaving` can be empty on a real exit** — "the builders live on the map", not on a stack.
  Never infer guardedness from the stack diff; assert on whether the sheet appears.
- `keptAcrossTabs` (only `more` screens survive a tab switch) and `returnsToOrigin` (only
  `more` screens' Back returns to the tab that opened them) are the two hard-coded
  exceptions.
- **Not a router.** Nothing touches the URL or History API, so no spec may shortcut to a
  screen with `page.goto()`. Every entrance is a real tap sequence from boot — which is the
  only way "findable" means anything.

## How a spec is formed

- **Seed IndexedDB, then boot.** `support/seed.ts` writes preferences, hiker mode and taken
  trail through `page.addInitScript` — _not_ `page.evaluate`, because a fresh page is on
  `about:blank`, an opaque origin IndexedDB refuses outright. The fixtures above use
  `page.evaluate` + `page.reload()` instead, which works because a drive has already
  navigated.
- **Geolocation is Playwright's own** — `context.setGeolocation` and `grantPermissions`, not
  a stub; a real browser has no seam to mock. `latOfMile()` keeps a mile meaning the same
  thing here as in `appHarness.ts`.
- **Locators are accessible-role queries**, exactly as the vitest suite and every shot recipe
  already write them. Never CSS selectors: a class is markup the component owns no contract
  over. Prefer the full `aria-label` where one exists (`'Back to Hike, step 1'`) over the
  visible glyph.
- **Mind the punctuation.** JSX text uses `&rsquo;` and renders `’`; a JS string attribute
  usually carries a straight `'`. A locator that guesses wrong matches nothing. Use a regex
  wildcard when it does not matter.
- **Wait on something observable, never a fixed timeout** — CLAUDE.md's rule and TESTING.md's
  rule 2. `preview-shots/legend.mjs` polls `scrollHeight` until it stops changing rather than
  sleeping a guessed duration.
- **Run anything awaiting an effect three times before pushing.** A real browser adds real
  animation frames and real network waterfalls on top of what vitest's mocks already made
  ordering-sensitive.
- **Assert the mechanism or the number, and say which** — TESTING.md's rule holds here too. A
  flow test that pins a rendered figure is pinning a fixture; what it is usually there to
  prove is that the screen was reachable and said which figures it was showing.

## What must be tested

The list below is the battery, by journey step. It is written as behaviours rather than
files so it survives refactors — TESTING.md's own convention for its client list. Each step
is tested across the axes above that it actually varies along.

**F1 first run** — all five cards reachable in order; each card's skip does what its own
words say (card 1's skip finishes the whole flow, cards 2–3's advance); no primary appears
before a choice is taken (decision D10); the download card's figure comes from the manifest
and reads "Unknown offline" without one; the flow cannot be re-entered once finished; a skip
writes no choice the hiker did not make.

**F2 Today** — the setup head per mode, **all three**; the pinned Find/Plan bar present in
every state; the download `Notice` present and absent; a walk dated today leading as its own
card; "Ahead of you" and "Today so far" rows; the alerts block when a closure or warning is
ahead; the journal with a fix, the honest sentence without one; the outbox line; the
next-morning ask after a walk left open.

**F3 step 1 · Hike** — reached from Today's pinned Plan and from the Plan tab's own primary;
the rail reads the mode's kind; the three doors, each **absent rather than disabled** when it
cannot work (D10); the network refusal as a sentence with a retry; the published shelf and
its chips landing pre-filtered; Cancel landing in Plan's room whatever door opened it.

**F4 step 2 · Route** — the rail on both builders; "‹ Hike" back to step 1 with the draft
kept (R3); the shape control's three values; undo; the gap-crossing acknowledgement; a
route that cannot be routed saying so.

**F5 step 3 · Details and Save** — the review card under the rail; the name field committing
on blur rather than per keystroke; water and stop rows **absent rather than "none"** when
there is nothing to list; "‹ Route" keeping the name and date; Save landing on the saved
card; the saved card's doors — Walk this, Leave it with someone, Edit the route, Delete —
and the edit door restoring the name and stopping the follow.

**F6 walking it** — the follow card's turn and leg; the coverage note at its head; "What's
left today" once a position is known; **the finish asked, never assumed**; "Still going"
changing nothing; the next morning asking once with no default.

**F7 when today changes** — each cascade move priced; "Leave it alone" as a choice; the diff
before it applies; one undo; the day screen's three ends landing on the timeline with the
call sheet open.

**F8 Plan** — both rooms; "What's left" with its two figures and its way back; the walked
shelf and its door; a hike's sections; a finished hike's record printing distance alone with
the note that says why.

**F9 reporting** — the report window; a report queued offline and sent on reconnect with the
authoring timestamp; "Your reports" showing waiting and sent with status; "Your photos and
notes" saying what is not kept there.

**F12 the map** — In view counting what is actually in view; the legend's fold and its
switches; the two safety sheets on their taps and **the tap order between them**; a waypoint
card; the search's waypoints and places.

**F13 More** — every settings screen reachable and leaveable; the source registry behind its
gate; the trace recorder behind #1201's gate; unit, theme and map-style choices surviving a
reload.

**F14 volunteering** — the workday window's three spans; workdays in view; a place search
fitting the map to a park.

**The download** — every state of the one flow that can fill a phone: choosing a tier,
progress, resume after a lost connection, "Unknown offline", and what the card says when
the release manifest cannot be read.

**Failure paths** — the error boundary catching a thrown screen and offering the report
door rather than a white page.

## The ledger, and why a new screen cannot skip it

`client/src/test/flowCoverage.ts` holds one entry per screen module — `covered` with the
spec that drives it, `planned`, or `unit-only` with a reason — and
`flowCoverage.test.ts` walks the same three directories `reachability.test.ts` does and
fails when a module has no entry, when an entry names a module that has gone, when a
`covered` entry points at a spec that does not exist, or when an exemption carries no
reason.

That is the mechanism behind rule 4. **A new screen fails the client suite until somebody
says how it is driven** — and `planned` is a real answer, so the cost of honesty is one
line. What it refuses is the third state: a screen nobody considered, which is how a flow
ships with nothing watching it and nobody able to say that was a decision.

## When this happens

**Before the pull request, not after it.** The same place `scripts/test.sh` and
`scripts/pipelines.sh` already sit in the routine:

1. The change adds or alters a screen → its flow-coverage entry moves in the same change.
2. `npx playwright test` in `client/` — three times for anything ordering-sensitive.
3. `scripts/test.sh` as usual; the flow-coverage guard rides the ordinary client suite, so
   a missing entry is caught by the run a contributor already makes.
4. The pull request's **Flow tests** section says which flows the change touches and what
   now drives them — or that nothing user-facing changed, which is a real answer that takes
   ten seconds.

A battery written after the feature is a battery written against the code rather than
against the intent, by someone who has already forgotten which states were meant to exist.
That is the whole reason this is a pre-PR step and not a cleanup sweep.

## Boundaries

- **No visual regression.** `toHaveScreenshot()` is not used. Pictures are
  `client/preview-shots/`'s job (`.claude/skills/pr-screenshot/SKILL.md`); this suite asserts
  DOM and accessibility state.
- **No duplicating the vitest layer.** Where `App.pathway.test.tsx`, `App.dayHike.test.tsx`,
  `App.navigator.test.tsx` or `navigator.test.ts` already hold logic at the rendered layer, a
  flow spec proves _findable_, not the same branch again — and is usually shorter for it.
- **Map data.** Chromium in an agent sandbox reaches nothing external (measured against
  `data.ourhike.org` and `example.com` — `screenshot.mjs`'s own comment), so real tiles and a
  real junction graph are not available; seed IndexedDB instead.
- **Vitest owns `src/`, Playwright owns `e2e/`.** `vite.config.ts` scopes vitest's include to
  `src/` — its default glob does not stop there and swept up `e2e/*.spec.ts`, running
  `@playwright/test`'s `test` through vitest's runner.

## Known gaps

- **`sweepForBuilder` is the one exit the guard cannot see.** #1374's review found it: a live
  day-hike draft under step 1 survives an ordinary tab tap, but switching mode to Long and
  tapping "Pick on the map" sweeps it with no bail sheet. `e2e/bailSheet.spec.ts` carries the
  repro written out in full as a `test.skip`, blocked on **#1387 — Neither the Playwright
  suite nor the screenshot recipes can put a live draft in the day-hike builder without a
  reachable bucket**. The skip comes off in the change that closes it.
- **The engine axis has never been run** — see above. Chromium only, everywhere this has been
  written.
- **The desktop project does not exist yet**, so every assertion here is a phone assertion.
- **`Today.tsx`'s pinned-bar comment cites "rule R4"** for "Find and Plan on every state of
  this screen, forever", but PATHWAY.md's R4 is "The mode stays global". Probably a citation
  from the original review's numbering. Not fixed here; flagged so the next person checks a
  rule number against PATHWAY.md rather than against another comment.
- **PATHWAY.md reuses "D" for two independently-numbered lists** — six defects (D1–D6) and
  fourteen decisions (D1–D14). Defect D5 and decision D8 are both about the bail sheet. Every
  citation in this document says which list.
