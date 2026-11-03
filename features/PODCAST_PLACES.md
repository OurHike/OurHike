# Finding the places a podcast talks about (Plan v1)

Companion to [PODCASTS.md](PODCASTS.md) (the card, the list, the Podcast desk) and to
[ORG_BULK_LOAD.md](https://github.com/OurHike/OurHike/blob/claude/modest-hamilton-sxasji/features/ORG_BULK_LOAD.md) on `claude/modest-hamilton-sxasji` (the bulk load of trail
organizations, **#1543 — 165 trail organizations exist and the registry knows 14, with no way to
load the rest that does not cost one pull request each**). The gap this plan closes is
**#1721 — A podcast episode can be tagged only to an A.T. POI, because lib/podcasts.py checks ids
against the A.T.'s ledger alone**.
The work is tracked as **#1723 — Match every podcast's place names against everything OurHike
publishes, for each new show, each weekly run, and each data release**.

The maintainer, 2026-09-29: *"make a plan for what need to happen to search those place names for
all the podcasts … this will be something we do again and again when we add podcasts. it also
should be checked each time the weekly podcast update runs."*

**Provenance.** Every number below was measured on 2026-09-29, against production data release
`cf8ff270` (`https://data.ourhike.org/latest.json`), the Podcast desk's own records, and the
external sources named beside each figure. The scripts that produced them are scratch files, not
committed; each figure says what it was measured against, so it can be measured again. Where a
choice rests on nothing yet, it says `@unvalidated`.

---

## What has to happen, three times over

A place name reaches OurHike three ways, and all three must end in the same state: every
mention an episode makes is either matched to a place a hiker's phone can open, or says plainly
why it isn't.

| when | what arrives | how often |
|---|---|---|
| **a new show** | hundreds of episodes at once (National Park After Dark: 469; Backpacker Radio: 424) | each time the maintainer adds a podcast |
| **the weekly run** | one or two new episodes per show | every Tuesday, per show |
| **a new data release** | no new episodes, but new places to match old mentions against — the bulk load's NPS, BLM and state layers | whenever a release publishes new layers |

The third is the one a naive design misses. National Park After Dark's Half Dome has no OurHike
place today; the day the NPS layers ship, it does. If matching only ran when an episode arrived,
that episode would never be looked at again.

## What doing it by hand taught us

The first two shows were matched by hand on the desk: Claude read the notes, named the place, and
a search over ATC's POIs proposed a point. What that showed, measured:

- **The words an episode uses rarely name a POI.** Of 46 ticked places whose notes carried the
  words verbatim, the desk's name search put the right POI first for **15** (33%) and in its top six
  for 23. Searching the *corrected* name Claude wrote got 78 of 80 right — but that number is
  circular, because Claude wrote those names after looking at ATC's list.
- **Five things broke it**, each a class the design below handles by name:
  1. *Abbreviation.* "Mount Washington" found "South Mount Marshall" before "Mt Washington Summit
     Vista", because nothing maps Mount to Mt.
  2. *Parks, not points.* "Great Smoky Mountains National Park" names no POI at all; the
     maintainer's rule gives it one spot, Newfound Gap. Park names were 16 of the 31 verbatim misses.
  3. *One landmark, several points.* "McAfee Knob" is both "McAfee Knob 2" and "McAfee Knob
     Summit"; "Katahdin" is a stream, a tableland and two summits.
  4. *A feature that isn't a POI.* The Lemon Squeezer and the Roller Coaster are real, named, and
     nowhere in ATC's layers; the ticks put them at the nearest POI.
  5. *A description, not a name.* "a thriving coal mining and railroad town" is Rausch Gap only
     to someone who knows the history.
- **The automatic pick never picked wrong.** The desk auto-chooses when one candidate scores
  ≥ 0.9 and beats the next by 0.1. It fired 85 times across both inputs and was right all 85 —
  and fired on only 9 of the 46 verbatim mentions. It is precise and nearly useless alone, which
  is the right way round.
- **Public geocoding is not a pipeline.** Locating the 254 off-A.T. places through OpenStreetMap's
  public Nominatim took 235 distinct queries (plus retries) at about one a second and drew
  repeated HTTP 429s. Its
  [usage policy](https://operations.osmfoundation.org/policies/nominatim/) says bulk geocoding
  "is not encouraged" and that scripts run at regular intervals "are restricted to 4 requests per
  minute", with results cached. That one run was already past what the policy allows a weekly
  job; it must not be repeated as a schedule.
- **Pins and hits both lie sometimes.** The show's map put the Grand Canyon 252 miles from the park.
  OpenStreetMap answered "K2" with a road in Skardu and "Brown Mountain" with Brown Mountain Beach
  Road (six road hits refused in all). The 9 parks where pin and OpenStreetMap disagreed by more
  than 60 miles were all large ones, 62 to 134 miles apart, where both points may well be inside.

Backpacker Radio was the third show (2026-09-30), and the first read with the rule "a major theme
or a segment only". Eight parallel readers took its 419 episodes; assembly dropped 89 news
headlines, 16 gear surveys that list trails, 98 regions, cities and businesses, and 4 bike routes.
What that left, measured on the desk:

- **A trail show proposes trails, not places.** Of 1,081 places proposed across 341 episodes, 810
  are a whole trail (177 different trails) and 78 a named section; 33 are A.T. POIs, 74 got a
  names-only point (53 from GNIS, 21 an NPS visitor center), and 86 have no point at all. For this
  kind of show the trail *is* the answer. 265 of the 341 episodes have at least one trail OurHike
  already draws (after the re-match below; 274 before it withdrew the Colorado Trail).
- **A published trail name is not one trail.** `places.json` groups USFS trails by name, so
  `trail:usfs_trails:TIMBERLINE` has a box from −121.8° to −106.4° longitude, and `LONE STAR`
  from −118.6° to −95.1°: many unrelated trails, neither the one an episode means. The resolver
  must check a trail's extent against the mention's `where` before it believes a name.
  `trail_name_aliases.json` (#1544) rejects both for the same reason, measured on the live
  service.
- **Some matches are a part of the trail.** The Long Trail is published only where it is the A.T.,
  as `APPALACHIAN TRAIL/LONG TRAIL`, and the desk says so. The first pass also matched the
  Colorado Trail to a USFS line named `COLORADO` (252 miles, 38.35°–39.55° N) from its name and
  extent alone; the reviewed join records that same line as "might be the Colorado Trail -
  UNRESOLVED, and left out because a wrong badge is worse than a missing one", so the re-match
  withdrew all 46 of those matches.
- **Short words need whole-word matching.** "AT" was highlighted inside "navigation" until the
  desk matched `said` on word boundaries. The resolver's name search has the same trap.

### The first re-match, after the bulk load (2026-09-30)

The bulk load (#1544 — Catalogue 173 trail organizations, ship every steward's trail marker, and
badge the trail rather than the feed) added a *catalogue*, not new lines: `sources.json` holds 46
sources before and after it, and UA's 2026-09-30 release draws fewer trails than production, 123
long trails in `places.json` against 163, because #1712 — Remove NH GRANIT, and drop USFS
motorized trails: ship only hiking trails — took 40 out. What it did add is what a resolver
needs: `trail_name_aliases.json`, a reviewed join from 19 trails to their published spellings with
16 spellings rejected, and 153 candidate trails with their stewards.

Every desk mention was re-matched by hand-run script against UA (`2b95b221`) in that order —
reviewed join, then an exact name whose every segment lies in the states the episode names, then
the catalogue — and ticked places were left alone. Of Backpacker Radio's 810 whole-trail
mentions: 425 reviewed matches, 40 unreviewed (the Long Trail's shared miles and 15 new ones such
as the Loowit, Uinta Highline and Art Loeb trails), 173 only catalogued, and 172 with nothing.
New from the reviewed join: the John Muir Trail, which OurHike draws for 14 of its 211 miles.
Every match now carries the miles it draws and the release it was measured on, because "OurHike
publishes the PCT" was true of 377 of its 2,650 miles.

Two thresholds are `@unvalidated`: an unreviewed name match needs 5 drawn miles (Oregon Coast,
1.1 mi, and Chinook, 2.7 mi, fell under it), and a place matches a named waypoint within 25
miles of its point. The maintainer's ticks on what they let through would settle both.

It also found four trails a podcast talks about that UA already draws under spellings the
reviewed join does not list — for the join's owner to decide, not a resolver:
`FNST - <name> SECTION` (the Florida Trail, 12 mentions), `ICE AGE NST-A/B/C` (66 miles in
Chequamegon NF; the Ice Age Trail, 10), `MST - <district> RD` (the Mountains-to-Sea Trail, 2), and
`LONE STAR`, which the join rejects for spanning −118.6° to −95.1° but which on UA, after #1712's
motorized filter, is 97 miles inside Sam Houston National Forest only (3). `OUACHITA NRT`, a
reviewed spelling, is not in UA's release at all.

**The maintainer took the first three the same day** ("add the FNST, Ice Age and MST spellings to
the alias table"), and they are rows in `trail_name_aliases.json` now, each checked feature by
feature against its state. `LONE STAR` stays rejected. Re-running the match against the new join
changed exactly 23 desk docs, and in each the only change was 24 mentions moving from "catalogued"
to a reviewed match: Florida 12 (153 drawn miles), Ice Age 10 (67) and Mountains-to-Sea 2 (166).
Nothing else on the desk moved. Eight episodes gained their first drawn trail, so 273 of the 341
now have one, up from 265. Two things the rows turned up belong to the join rather than to podcasts:
the Forest Service's `RD` suffix is a ranger district, which the join had read as a road-walk
and so left out 73 miles of the Bartram Trail and 31 of the Benton MacKaye; and two of the three
`BARTRAM` lines it already badges are Alabama's own Bartram trail — **#1781 — The spelling BARTRAM
badges 7.8 miles of Tuskegee National Forest, Alabama, as the Georgia–North Carolina Bartram
Trail**. The maintainer took both fixes by poll the same day. The three ranger-district spellings
are rows now, and every row carries an `extent`, the box a line must lie in to wear its badge.
For the resolver, that box is the same kind of check it already makes against a mention's
`where`, written down once per trail.

## What OurHike can already match against

The first draft of #1721 said OurHike publishes nothing off the A.T. It publishes a great deal:

| artifact | named places | extent | opens a place card |
|---|---:|---|---|
| `poi_*.geojson` (`export_poi.py`) | 2,273 shelters, campsites, viewpoints, parking areas and towns | A.T. corridor | yes |
| `nearby_poi.geojson` (`export_nearby_poi.py`) | 17,234 of 20,506 | no clip: USFS nationwide (9,066 named), DEC/OPRHP New York, NYC, the Long Path | yes |
| `places.json` parks (`export_places.py`) | 257 | New York (OPRHP units) | no — moves the map |
| `places.json` trails | 163 | any trail with 50+ published miles, including the PCT, CDT, NCT, AZT | no — moves the map |

**Against the desk's 254 National Park After Dark places off the A.T., that finds almost
nothing.** 105 have some published OurHike place within 25 miles; **4** match one by name. The show
is national parks, and nothing OurHike publishes covers NPS ground.

**And the bulk load, as planned, does not change that.** Every `ship` row in
`pipeline/reference/trail_orgs.json` on the bulk-load branch is a trail-line layer —
`NPS_Public_Trails`, BLM's GTLF, PCTA's centerline. None is a POI dataset.

**One NPS dataset would.** `NPS_Public_POIs_Geographic`
(`mapservices.nps.gov/arcgis/rest/services/NationalDatasets/`) is public domain, 35,639 points
(30,779 named), with `POINAME`, `POIALTNAME` (an alternate name), `POITYPE` (382 types: Trailhead,
Peak, Waterfall, Visitor Center …) and `UNITCODE`. Measured against the same 254 places:

- **Park mentions (187).** 84 name an NPS unit exactly enough (token-sort ratio ≥ 90), and 82 of
  those units have a Visitor Center point — the national-park equivalent of the A.T.'s "one spot
  per park". The other 103 are national forests, state parks and parks abroad.
- **Specific places (67).** An NPS point carries the name within 15 miles for 12. About half of
  those are right (Half Dome, Guadalupe Peak, Grand Teton, Hoh Rain Forest, Lake Crescent Lodge) and
  half are a facility that happens to share a word ("Potomac River" → East Potomac Tennis; "White
  House" → a restroom). So a POI layer this broad needs a type allowlist before it can propose
  anything.

The recommendation to the bulk load is therefore concrete: **register `NPS_Public_POIs` beside
`NPS_Public_Trails`**, and hold it at `reaches_hikers: false` like the rest until #1231's scope
question is answered.

## The design: mentions, a gazetteer, a resolver, the desk

Four parts, and the split between the first two is the whole design:

### 1. A mention is what the episode said, read once

An LLM reads each episode's notes — from the show's own RSS feed, never from Spotify (below) —
and writes one row per place the episode is about:

```
episode        apple-<trackId>
said           the words, verbatim, so the desk can highlight them
name           the usual name, spelled out ("Mount Washington", not "the Whites")
trail          the trail it is on, named first, or "" (the maintainer's "identify the trail first")
kind           summit | gap | shelter | campsite | lake | falls | park | trail | town | …
where          park, state or country, when the notes say or plainly imply it
role           major | segment | passing   (only the first two are ever proposed)
context        the show's own map pin, when it has one
```

A mention is **never re-read**. Reading costs an LLM call per episode; matching costs nothing.
So when the gazetteer grows, the mentions are re-matched and the notes are left alone.

### 2. The gazetteer is what a phone can open, plus names that help find it

One table, rebuilt for each data release from its published artifacts, plus the layers registered
but held at `reaches_hikers: false` (decided below). Every row says which it is. A match to a held
row waits on the desk as "waits for data"; only a match to a published row can reach the list, so
a tag never points at a place the phone does not hold:

```
id, name, alt_names[], kind, lat, lon, source, unit (park/forest it sits in), trail, release,
status (published | held)
```

Two layers of extra names, kept apart:

- **Generated:** Mt/Mount, St/Saint, Ft/Fort; apostrophes; "Lean-to" as "Shelter"; ATC's
  `SHEN - ` prefixes stripped; the generic word ("Shelter", "Gap", "Falls") moved out of the name
  and into `kind`, because rapidfuzz's `token_set_ratio` scores Hawk Mountain against Hawk
  Mountain Shelter at 100 (research, 2026-09-29).
- **Curated:** `pipeline/reference/place_aliases.json`, one row per judgement a person made —
  "the Smokies" is Great Smoky Mountains National Park; "the Whites" is the White Mountains; the
  Lemon Squeezer is at Island Pond. It is small by construction and reviewed row by row, which is
  what `pipeline/reference/` is for.

**Names-only authorities** fill the one hole the published data leaves — a named feature with no
OurHike point — and never become a POI:

- **GNIS** (USGS, public domain, refreshed every other month): 981,708 names in 43 classes, 268,012
  variants. But **57% of its names are shared with another feature** ("Low Gap" is 131 places), and
  it dropped trails and parks in 2021. It is a point for "where", never an id.
- **NPS API** `/places` (17,478, public domain, free key, 1,000 requests an hour) — the NPS's own
  names for things inside its parks.
- **Wikidata** (CC0) for peaks and parks; it holds only 643 US hiking-trail items.

### 3. The resolver is deterministic, and runs the same everywhere

`pipeline/resolve_podcast_places.py`, DuckDB like the rest of the pipeline, no network. For each
mention:

1. **Block by the trail first.** The maintainer's instinct is the geoparsing literature's best
   heuristic: restrict candidates to the named trail's corridor, or the named park's boundary, or
   the show pin's neighbourhood, before comparing a single name. Without it, "Mount Washington" has
   22 GNIS candidates; inside the White Mountains, one (reasoned, not yet run).
2. **Find candidates** by normalised name and alias, then Jaro-Winkler within the block.
3. **Rank** by name score, kind compatibility (a "summit" mention wants a summit or vista, not a
   parking area), and closeness to the episode's other resolved mentions ("spatial minimality").
4. **Prefer the landmark's representative point** where one feature has several (McAfee Knob Summit
   over McAfee Knob 2), from a small reviewed table, not a guess.
5. **Parks get their spot.** A park mention resolves to the park's one spot: the A.T. table the
   maintainer set on 2026-09-29, and for NPS units a reviewed choice of visitor center (the first
   visitor center in the data is not always the one — Yosemite's first was Wawona).
6. **Abstain when unsure.** A verdict of `none` or `ambiguous` is an answer. The geoparsing
   benchmarks' own warning applies: Mordecai 3 declines correctly only 40–100% of the time when the
   right place is not among its candidates, and "incorrectly geolocating a place name is a worse
   error than failing to geolocate" (Halterman 2023).

Every verdict carries its grade — `exact`, `alias`, `fuzzy`, `park-spot`, `nearest-to-feature` —
and the release it was computed against.

### 4. The desk decides; nothing is ever ticked by a machine

The desk shows each mention with its verdict and candidates. A person ticks one. **The tick is
stored against the mention and the place id, not against the verdict**, so re-resolving after a
data release can propose something new without undoing anybody's decision. Only ticked places
reach `podcast_episodes.json`.

## Where it runs

| trigger | who runs it | what it does |
|---|---|---|
| **a new show** | a session, on the maintainer's request | fetch the feed; LLM readers write mentions (in parallel, as on 2026-09-29); resolve; write to the desk |
| **the weekly run** | one routine per show: National Park After Dark (`trig_01R1d7LAqZ3Y7RhyPV4Fmpci`) and Backpacker Radio (`trig_01WeUhK3WkaF6oXamymvz5ii`), Tuesdays | new episodes as above; then **if `latest.json`'s version changed since the last run**, re-resolve every mention on the desk and report what newly matched |
| **a data release** | the same check, the next Tuesday | nothing extra: the version check above is the trigger |

The desk keeps one `meta` record: the data release it last resolved against. That one field is
what makes the third row free.

**The desk has two limits a new show can hit.** One query delivers at most 1,000 documents, and
after Backpacker Radio the desk held 940 episodes, so it now watches each show on its own, named in
a `shows` collection, with one more window for any show not named there yet (desk version 9,
2026-09-30). That holds up to 29 named shows at 1,000 episodes each. The artifact's database caps
at 25,000 documents in all, according to the write results on 2026-09-30. At the roughly 450
episodes a show has brought so far, that is about 50 shows, after which skipped episodes would need
archiving. So adding a show means adding its row to `shows` too.

**Why not a GitHub workflow?** CI cannot read the desk: its database is reachable only through the
claude.ai tools a session holds. So resolution runs in a session and the repository holds the
code, the tests and the reviewed tables — the same split the podcast list already has.

## How we know it works

The maintainer's ticks are a gold set, and it grows every time somebody ticks:
**80 places today** (the Green Tunnel's 62 and National Park After Dark's 21, less the ones added by
request). A test runs the resolver over the gold mentions and prints two numbers — how many it
got right first, and how many it proposed that were wrong — into the test's own output, and fails
if the second rises. Every change to the aliases, the thresholds or the blocking is then
**Measured**, not reasoned, which is the standard CLAUDE.md sets.

The two thresholds this plan inherits are `@unvalidated` until that test exists: the desk's 0.9 /
0.1 auto-pick and the 60-mile pin-agreement radius.

## The gate

`lib/podcasts.py` must accept ids a phone can open, and today it accepts only the A.T. ledger's.
A committed ledger for the other waypoints is not the answer: `nearby_poi.geojson`'s 20,506 rows
would be 1.7× the 12,000-line ceiling `test_no_committed_data.py` sets on a reference file, and
that test's own docstring says the next raise should be a split, not a bigger number.

So the gate checks nearby ids **against the published artifact of the release it publishes into**,
at publish time in `publish-podcasts.yml`, and against fixtures in the unit tests. A tagged id
that a release retires is caught the same way `poi_identity.json`'s `retired` rows are caught now.

## Rules this plan inherits and does not relax

- **Places on one episode stay 500 miles apart** — trail miles on the A.T., a straight line
  elsewhere (never shorter than the trail, so it can only err toward dropping a place).
- **Crime stories are tagged where they happened.**
- **Only a major theme or a segment counts.** A passing mention is recorded (`role: passing`) and
  never proposed.
- **Show notes come from the show's own feed.** Spotify's Developer Policy (effective 2025-05-15)
  forbids ingesting "Spotify Content into a machine learning or AI model", so Spotify is used for
  the episode's id and nothing else.
- **A point from a podcast is not a place to walk to.** A location anchor never renders in the
  voice of a surveyed POI (CLAUDE.md, "Never let a display outrun its source").

## What this plan deliberately does not do

- Geocode on a schedule against a public service.
- Tick anything, or push anything to `podcast_episodes.json` without a person.
- Re-read episode notes when the data changes.
- Treat a GNIS or Wikidata point as a POI a hiker can open.

## Decided

The maintainer, by poll on 2026-09-29, against the diagram page drawn for this plan (four
frames, each with a recommended option). Every recommendation was taken:

| question | chosen | offered and not taken |
|---|---|---|
| which places a mention may match | everything a phone can open, **and** layers registered but held (`reaches_hikers: false`), shown on the desk as "waits for data" so a tag goes live the day the data ships | published places only |
| how the gate checks a nearby waypoint's id | against the published release's own `nearby_poi.geojson`, at publish time in `publish-podcasts.yml`; fixtures in unit tests | a committed ledger, which would first need the reference ledger split |
| NPS's POI layer | ask the bulk load to register `NPS_Public_POIs` beside `NPS_Public_Trails`, held at `reaches_hikers: false` until #1231's scope question is answered | not yet |
| a named place with no OurHike point | a names-only point from GNIS, the NPS API or Wikidata on the desk, marked as not a place to walk to — never a POI, never on a hiker's map | leave it unlocated |

The alternatives are written down so the next reader knows they were considered, not so they get
re-argued.
