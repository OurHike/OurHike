# OurHike — Challenges as the blaze card (Build brief v1)

Companion to [CHALLENGES.md](CHALLENGES.md) (the feature this re-skins; its data model,
server, CSV and guardrail argument are unchanged), [VOLUNTEERING.md](VOLUNTEERING.md) §5,
[POI_PHOTOS.md](POI_PHOTOS.md) (the photo ladder the tile reuses) and
[../OurHikeValues.md](../OurHikeValues.md) #1, #4, #6 and #9. The frames this brief builds
are under `features/design/blaze-card/` — one `.dc.html` per phone screen, two components
(`BlazeCard.dc.html` holds the icon set and the 100-item mapping; `StateStrip.dc.html` the
fourteen-stop line), and three `map-*.svg` that are the target look for the map. The design
review that produced them, and the adversarial pass on them, are the maintainer's.

---

## What this is

**The ATC's A.T. Summer Bucket List as a card of 100 tiles.** A participant opens the list
from a link in the ATC's email, keeps it on their phone, **earns a white blaze** for each
item they do (honor system, as the ATC runs it), records where the on-trail ones happened,
and enters the ATC's drawing at 25. For a hiker already using OurHike, the challenge appears
as one prompt on Today when a walk passed a place, and as one strip at the bottom of Today
for the season.

The ATC's rules do not move: 100 items in the ATC's sections, any 25 by the closing date,
one entry per person, name and email, three mystery items each with its own drawing.

## Decisions (maintainer, from the canvas comments, 2026-11-03)

- **The verb is "earn"**, not "paint": painting blazes is maintainer work and unauthorized
  blazing is a thing clubs fight. "Earn it", "12 blazes earned", "Your blazes". One constant,
  `CHALLENGE_WORDS`. (Poll it once with the frames edited both ways; "earn" unless overruled.)
- **The season lives at the bottom of Today, never the top.** Top of Today is today's
  business: the walk prompt (`ChallengeCampCard`, once a day, only when something was passed).
- **The card is a picture; the list is the control.** Tiles are tappable only in the expanded
  56 px state. The list in the ATC's four sections is the accessible, findable form.
- **The share poster defaults to the state strip; the map is opt-in** behind the sentence
  "This shows where you've been."

## What this is not

- Not a change to what leaves the phone: a tag is still item id + authored time + `gps`/`hand`;
  an entry is still name, email or address, item ids, consent. A tag's `place` is device-only.
- Not a server, CSV or org-console change (except slice 8).
- Not a notification, a leaderboard, a streak, a score, or a numeral for what is missing.
- Not stock photos. A tile with no reviewed photo shows its icon.
- Not sponsor names or ATC marks until the ATC's letter grants them. The welcome footer is the
  hashtag alone.

## Hard requirements (the review's blockers)

1. **No tap target below 44 px.** The card's tiles at 24–29 px have no handler; a tap on the
   card opens the list at that section. An expanded card at 56 px is where tiles are tapped.
2. **"Where did it happen?" only when it can mean something.** Never for an at-home item
   (`on_trail: false`), never for a `gps` tag (the place is known). "Here" is offered only when
   there is a fix inside the corridor (`lib/trailPosition.ts`). The sheet always has
   **"On the trail, somewhere"** with a state, for the hiker with no signal and no download.
3. **The web entry point does not lose the card.** On iOS the home-screen app has its own
   storage; the welcome offers the install (or sign-in) *before* the first blaze. Nothing is
   earned before that choice, so nothing is lost either way.
4. **The outbox cargo is byte-identical to today's.** A test proves it.

## The slices, in order (one issue, one branch, one draft PR each)

Open the issue first; claim it with a comment naming the branch; name it in full in every
reference. `scripts/test.sh` before every push. `scripts/pipelines.sh` on every PR; a slice
that touches the exporter fills the PR template's Data pipelines section and is dispatched
to `ua` after merge. Every changed screen gets a shot recipe and a `## Screenshot` section
that names it. Every picked number carries `@unvalidated` and what would settle it.

| # | Issue | Scope | What proves it |
| --- | --- | --- | --- |
| 1 | Challenges: one verb, the ATC's sections, and one status line | `CHALLENGE_WORDS` → earn; pills become Learn · Experience · Protect · Mystery · Done; `lib/challengeText.ts` prints place/walk sub-lines only (no "at home"); DRAFT chip → one banner; the `API_CONFIGURED` note → one status line | Existing suites renamed; the `/other hikers\|behind\|streak\|rank\|leaderboard/i` assertion over every new string; recipe `challenge-detail.mjs` touched |
| 2 | Challenges: the blaze card — 100 tiles, one blaze per earned item | `icon` per item in `pipeline/reference/challenges/atc/*.json` (the mapping is in `BlazeCard.dc.html`), through `export_challenges.py` with a schema check; `chrome/BlazeCard.tsx`, `chrome/BlazeTile.tsx`; the card in the detail header replacing the diamond strip; expanded 56 px state; `aria-hidden` card with a one-line summary | Export test: every item resolves to a known icon; render test: no handler on a tile under 44 px; recipe `challenge-card.mjs` (new); Data pipelines section |
| 3 | Challenges: the tile sheet asks where, and only when it can mean something | Tile sheet replaces `TaggedPlace` (photo-or-icon header, Earn it, own photo, two small cards); `on_trail` per `self_report` item; `chrome/WhereSheet.tsx` (Here · Somewhere I walked today · Pick a place via `lib/searchPoi.ts` · On the trail, somewhere · Not on the trail); `place` on `ChallengeTag` in `ourhike:challenge-state`, device-only | Unit tests for each availability branch; the cargo-identity test; recipes `challenge-tile.mjs`, `challenge-where.mjs` |
| 4 | Challenges: the season at the bottom of Today, the entry visible from day one | `season` slot at the end of `Today.tsx`'s ordered record; `chrome/ChallengeSeasonStrip.tsx` (mini card, blazes earned, states, chevron); `Finish` reachable at 0 of 25 with "what the ATC receives" and the mystery-drawings line; mystery `reveal_on` + `teaser` | Today ordered-record test; no numeral for unearned items; recipes `challenge-today.mjs`, `challenge-entry.mjs` |
| 5 | Challenges: where your blazes are — the map, the list, the poster | `lib/blazeMap.ts`: static SVG from the simplified published centerline + bundled outlines (`features/design/blaze-card/map-*.svg` are the look, built by `mapbuild/` in the same folder); Where view = list first, map once a blaze is on the trail, state strip; poster render to PNG on device; share sheet (strip default, map opt-in, the sentence) | Golden-image test on three fixtures; recipes `challenge-map.mjs`, `challenge-poster.mjs` |
| 6 | Challenges: a link from the ATC's email opens the card, after the install | `/atc/bucket-list` route inside the PWA (never `site/` — see `lib/useInstallPrompt.ts`); iOS install-first, Android `beforeinstallprompt`; the four-beat explainer (3.5 s, tap to step, reduced motion, `aria-live="polite"`); transcribe the 2026 list (100 items, closes Sep 7) as the draft | e2e: the route joins and opens the card; no tag possible before the install/sign-in choice on iOS; recipe `challenge-welcome.mjs` |
| 7 | Challenges: photos for the items that have a place | `pipeline/fetch_nps_photos.py` (NPGallery National Trails System archive, public domain, credit NPS) with `nps_licence` in `sources.json`; reviewed `photo`, `photo_credit`, `photo_licence` per item; the photo tile layout with the credit line | Export refuses an item photo with no licence record; recipe `challenge-tile.mjs` touched |
| 8 | Challenges: reveal a mystery item without a release | Document the dispatch path (`challenges.json` republished on a reviewed-file change); v2: an org-console reveal | A changed `reveal_on` reaches `challenges.json` with no client change |

## Polls to the maintainer — with the picture, at every fork

1. Slice 1, before code: the verb, both frames edited.
2. Slice 2, after the first build: the card screenshot beside `Card.dc.html`.
3. Slice 3: the Where sheet with location off, beside `Where.dc.html`.
4. Slice 5: the poster render beside `Poster.dc.html`; the share sheet's default.
5. Slice 6: the iOS install-first welcome, as a GIF from the camera.

## Numbers picked, not measured

Tag each `@unvalidated` and finish the sentence with what would settle it: the 3.5 s rotation
(a reading test on five people); 24 / 26 / 56 px tiles (a thumb on a real phone); the state
mile bands in `StateStrip.dc.html` (replace with the pipeline's state boundaries); the
150 m / 60 m tag radii (unchanged from CHALLENGES.md, still unvalidated).

## What gates the public

The ATC relationship is settled (maintainer, 2026-11-03); no letter is needed. CHALLENGES.md
still records the list's licence as open and says the PR "is not to merge until the ATC's
written permission is recorded in sources.json": slice 1 closes that by recording the basis
the way `photo_licence` does — author "Appalachian Trail Conservancy", basis "Maintainer
authorisation, on the basis of the ATC's agreement to run the Bucket List on OurHike",
`recorded_date` 2026-11-03 — in a block named `atc_bucket_list_licence`, and rewrites the open
question to point at it. `takes_entries` flips to true when the ATC confirms OurHike is its
submission form for 2027; until then the entry screen shows the ATC's form link. The 2027
list arrives in May; the card runs on the 2025 transcription as a labelled preview until it
does. Releases go through `RELEASING.md`'s train; data publishes go to `ua` from a merged PR
and to production only from the train.

## What is not in the tree, and must not be invented

- **The 2026 list.** The ATC emailed it to sign-ups and the web page shows no items; sign-ups
  are closed. Do not fetch or reconstruct it. The reviewed file carries the 2025 text verbatim;
  keep it, change only the window to 2026's dates (May 13 – Sep 7) with a note, and swap in
  the 2027 list when the maintainer supplies it.
- **Photos.** Nothing from the web into the tree. Slice 7's fetcher reads NPGallery's archive
  (public domain, credit NPS) through the proxy allowlist the pipeline already uses for ATC
  layers; each file lands with its licence record or is refused.
- **State boundaries by mile.** `StateStrip.dc.html` carries approximate bands. Derive the
  real ones in the pipeline by intersecting the published centerline with state outlines
  (`us-atlas`, ISC licence, US Census TIGER source — record it in `sources.json`), and emit
  them beside `challenges.json`.
- **The trail line for the static map.** The mocks' `map-*.svg` now use the real A.T. line
  (OpenStreetMap relation 156553, ODbL, 2,698 points, from a public-domain repo's export)
  with miles placed proportionally along it (@unvalidated: OSM's simplified length is 1,812
  mi against the ATC's 2,198, so a mile lands within a few miles of where it belongs). The
  build replaces it with the pipeline's own published centerline, which is already the axis
  every POI mile is projected onto (`lib/route.ts`'s rule), simplified to ~1,000 points at
  phone scale; and never ships the OSM line.
- **The icon per item and the on-trail judgement.** Both are judgement calls and both are in
  `features/design/blaze-card/`: `item-icons.json` (id → one of the 26 icon names in
  `BlazeCard.dc.html`) and `self-report-on-trail.json` (id → whether "Where" is asked; 35 of
  the 76 at-home items are on-trail by the ATC's own wording). Copy them into the reviewed
  file's items; do not re-derive them.

## Behaviours that must survive the re-skin

Everything `ChallengeDetail.tsx`, `ChallengeCampCard.tsx` and `lib/useChallenges.ts` do
today, in particular: Join / Leave with the confirm and the pins-and-card removal; no earning
outside the window and "Opens May 13" / "Closed Sep 7" said plainly; a closed challenge keeps
its record; a sealed mystery item shows no title before `reveal_on`; a `places_all` item
(the Triple Crown) tags per peak and queues nothing until the last; `off_trail` places by hand
only; a walked tag upgrades a hand tag and never the reverse; "Not tonight" on the camp card
leaves every row earnable from the list; the register line never leaves the phone; the
outbox order (tag, untag, leave) is preserved; the DRAFT label wherever a draft is named,
now as one banner.

## The map: reuse, do not invent

The static map in the mocks is drawn from OurHike's own map vocabulary, and the build keeps it
that way:

- **Ground** is the Field palette (`features/MAP_STYLE_SPEC.md` `TOPO_PALETTE`, the day
  default): `wood #dcebd2` for the rest of the land, `park #d3e6c6` for the fourteen trail
  states with `parkEdge #5f8f57`, `water #8fc0dc`, `boundary #6f6753`, `label #14130f`. A
  paper map on a paper page — never a dark map inside a dark card, which is unreadable in sun.
- **The trail** is cased the way `map/style.ts` cases the A.T.: `#14130f` casing under a
  `--blaze-white` line (`trailCasingColor`, `blazeLineColor`). Walked miles are
  `--blaze-yellow` over it, the taken-trail colour the app already uses.
- **A place** is the challenge pin from `map/challengePin.ts`: the diamond is the body
  (`body: 'diamond'`), `CHALLENGE_COLOR` `#d69a2d`, hollow until earned, filled with the tick
  when earned — the same pin the live map draws, so the static map and the Legend layer are
  one visual language. Several earned at one spot cluster with a count.
- **The A.T. mile is the axis**: ticks every 500 miles, the termini named, a 200 mi scale bar,
  and the attribution line (`© OpenStreetMap · US Census · Natural Earth` in the mocks; in the
  build, whatever the pipeline's sources are).
- **Outlines**: US states from `us-atlas` (US Census TIGER, ISC licence) and Canada from
  `world-atlas` (Natural Earth, public domain), simplified with `topojson-simplify` at build
  time, projected with `d3-geo`'s conic conformal (parallels 38/43, rotated to 76.5°W) — the
  recipe is `features/design/blaze-card/mapbuild/build2.mjs` + `assemble2.py`. Record both in
  `sources.json` the way every other source is.
- **Where sheet**: the chosen place is ringed in `--blaze-orange`; the sheet's heading is
  "Where it lands on the map".
- **Welcome**: every place on the card, hollow, with five mile markers (Springer mi 0,
  Kuwohi mi 200, McAfee Knob mi 715, Harpers Ferry mi 1,027, Katahdin mi 2,198).

What the static renderer must not do: fetch tiles, load MapLibre, or render anything the
corridor archive is needed for. It is a few hundred KB of SVG paths in the shell, and the
poster is that SVG rasterised on device.

## Vocabulary and tokens

- Add **blaze (challenge)** to GLOSSARY.md beside the trail-marking sense: "one earned item on
  a challenge card, drawn as a white blaze; never the paint on a tree." The word is already
  overloaded in the app (the logo, blaze colours), which is exactly what GLOSSARY.md exists for.
- The mocks use hex; the build uses tokens from `design-system/tokens/colors.css`:
  `#122016` → `--pine-900`, `#1c2f1f` → `--pine-800`, `#284029` → `--pine-700`,
  `#355c3a` → `--forest-600`, `#96b98c` → `--moss-300`, `#c7dabd` → `--sage-200`,
  `#e3ecda` → `--sage-100`, `#f7f3e9` → `--paper-100`, `#fffdf7` → `--paper-0`,
  `#fdfaf2` → `--blaze-white`, `#d69a2d` → `--blaze-yellow`, `#c1611a` → `--blaze-orange`,
  `#e0813c` → `--blaze-orange-light`, `#5a5346` → `--stone-700`, `#706859` → `--stone-600`,
  `#8a8271` → `--stone-500`, `#c3baa4` → `--stone-300`, `#e4ddca` → `--stone-150`.
  Type is the app's own (`--font-display`, `--font-body`, `--font-mono`); nothing below 11 px.
- **No stamp animation** (maintainer, 2026-09-30). A tile becoming a blaze is a 150 ms
  opacity change, no confetti, no sound, no haptic.
- Launch budget: `client/scripts/check-launch-speed.mjs` and `measure-first-run.mjs` still
  pass; the card component, the icon set and the bundled state outlines (~12 KB) are in the
  shell, item photos are never in the shell.

## The second look: difficult users

Nine changes from the maintainer's second design pass (the review doc, "Second look"). Four
are already in the mocks (three words only: card, blaze, map; "earn"; the explainer rests
after one pass; nothing under 11 px). The five for the build: tiles never toggle on tap and
every blaze has a one-tap "Take it back"; the list is numbered 1–100 in the ATC's order with
"Print my card" as a PDF; the Where sheet opens on "On the trail, somewhere" when there is no
fix and no challenge screen ever asks to turn location on; the entry screen says "One entry
per person — use the email you signed up with"; nothing on a challenge screen waits on the
network, and the poster renders on demand with a visible progress state.

## Open questions

- Whether the ATC wants the card to carry its sections' exact names and order for 2027 (the
  2026 web page shows no sections; the 2025 PDF had three).
- Whether a hand-chosen place should ever reach the CSV. This brief says no: `gps` means the
  day's walked miles covered the place; everything else is `hand`.
- The expanded card's zoom gesture (pinch vs a button) — a thumb question, poll it with the
  build.
