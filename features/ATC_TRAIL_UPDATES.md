# Putting the ATC's own Trail Updates on the map

Companion to [MAP_OPTIONS.md](MAP_OPTIONS.md) (what a closure *is*),
[CONDITIONS_DELIVERY.md](CONDITIONS_DELIVERY.md) (how safety data reaches a phone) and
[SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) (how an outside organization's data gets in at
all). This document owns one question: **the ATC publishes trail closures, detours and
hazards at [appalachiantrail.org/trail-updates](https://appalachiantrail.org/trail-updates/),
and none of it reaches a hiker using OurHike. Can it?**

The answer is yes, and more cheaply than it looks — but the cheap part is the geometry, and
the part that actually needs deciding is who is allowed to publish a safety claim. Those get
argued separately below, because conflating them is how this ships badly.

Everything measured here was measured on **2026-08-09** against the live site and ATC's live
ArcGIS services. `pipeline/spike_atc_updates.py` reproduces it; `pipeline/tests/test_spike_atc_updates.py`
pins the parser against the real prose.

## The gap this closes, which this repository has already written down

[MAP_OPTIONS.md](MAP_OPTIONS.md)'s closures section says, correctly:

> **none of the 12 already-registered ATC layers** […] **has anything resembling a closure
> or status field.** This has to be modeled from scratch, not extracted from data that
> already exists.

That is true of ATC's *GIS layers*, and it led to a reasonable conclusion that turns out to
be too narrow: that the only source of closure data is hikers and club volunteers typing into
OurHike's own moderation queue. ATC does publish closures. It publishes them as **prose on
their website**, which is why a script that walked their ArcGIS org never saw them.

So today the situation is: the organization that actually knows the trail is shut says so in
public, and OurHike — a map for hikers — does not show it. The nine updates live on
2026-08-09 include a nine-mile Forest Service closure in southwest Virginia that a hiker
"must stay out of […] for their safety", a closed shelter in Connecticut, and a footbridge
closure at Harpers Ferry.

## What ATC actually publishes, measured

Nine updates were live on 2026-08-09. Each has a title, one or more states, a category
(**Detour, Alert, Closure, Parking, Hiking Safety**), a "last updated" stamp, and a body.

**The body is where the location lives, and ATC writes it in NOBO miles from Springer.**
Real examples, verbatim:

| Update | As ATC wrote it |
|---|---|
| NC/TN: Iron Mtn Gap Reopened | `(NOBO mile 360.6 to 364.8)` |
| SW Virginia: VA Creeper Trail Closure/Detour | `(NOBO miles 476.6 to 485.8)` |
| Connecticut: Limestone Spring Shelter Closed | `(NOBO mile 1,503.6)` |
| Harpers Ferry Footbridge Closure | `(NOBO mile 1,026.7)` |
| Hurricane Helene Storm Damage | `(NOBO miles 239.4 to 637.8)` |
| Vernie Swamp Area Trail Flooding | `(approx. NOBO mile 1,346.3)` |

**Seven of the nine carry at least one mile reference.** The convention is consistent enough
to parse: a `NOBO`/`SOBO` marker, `mile` or `miles`, then a number or a range, almost always
parenthesised at the end of the sentence naming the place.

### The find that makes this cheap

`start_mile_marker` and `end_mile_marker` on `backend/app/models/closure.py` are *that same
number*. And `sources.json`'s ninth entry — `half_mile_points_from_springer`, already
registered, already fetched by `fetch_all.py` — is **ATC's own table converting one into the
other**: 4,395 points, a `Measure` field running 0.5 to 2197.5, one every half mile.

ATC and OurHike already share a coordinate system, from the same organization, and both
halves are already in this repository. Placing an update is a **join against data the build
already has** — not geocoding, not NLP, not a map-matching problem.

Spot-checked against the live layer, and every one lands where ATC's own prose says it does:

| ATC's mile | Resolves to | ATC's own words |
|---|---|---|
| 364.5 | 36.14231, -82.23534 | "Iron Mountain Gap" |
| 1026.5 | 39.32330, -77.73850 | "footbridge […] across the Potomac River" |
| 1503.5 | 41.98070, -73.39270 | "Limestone Spring Shelter" (Salisbury, CT) |
| 239.5 → 638.0 | 35.77092, -83.10973 → 37.33986, -80.75770 | "from Davenport Gap to Pearisburg, VA" |

That last row is the whole argument in one line: parse two numbers out of a sentence, and the
coordinates they produce are the two towns the same sentence names.

### It also answers an open question this repository was holding

MAP_OPTIONS.md's open questions end with:

> **Closure geometry precision** — whether a closure needs to reference exact start/end
> points along the centerline […] or a looser "this general stretch" description

The organization that maintains the trail already decided, and publishes to tenths of a mile.
That is not binding on what a club volunteer should be asked to type into a form, but it does
settle what the *data model* has to be able to carry, and it already can.

## What is not a map feature, and must not become one

Two of the nine updates carry no mile reference, and **neither is a defect to fix**:

- **"NC – VT: Severe Weather"** — a region-wide advisory spanning ten states. It is real
  information with no location finer than "the eastern seaboard".
- **"New York: Help Identifying Individual"** — a law-enforcement request. It is not a place
  at all, and pinning it to one would be actively wrong.

A third case is worse because it *does* parse. **Hurricane Helene Storm Damage spans NOBO
239.4 to 637.8 — 398 miles.** Rendered as a dashed red band the way `closureLayers.ts` draws
closures, it paints a fifth of the Appalachian Trail as closed, at every zoom, permanently.
It would visually swamp the nine-mile Creeper Trail closure that a hiker actually has to walk
around — the more urgent warning buried under the broader one. The update itself says the
damage is patchy: *"The worst of the damage occurred along the section between…"*.

**So band length needs a ceiling, and above it an update becomes a list entry rather than a
band.** Where exactly that ceiling sits is an open question below; that there must be one is
not. This is the same instinct as `HIKER_SAFETY.md`'s conservative wrong-way alert — a
warning that fires too broadly trains people to ignore warnings.

The ceiling now exists in code, as `MAX_BAND_MILES` in `client/src/lib/closureSpan.ts` — one
constant, provisional, with the reasoning for its current value beside it (#462). It governs
OurHike's own closures too, not only ATC's: nothing stops a moderator entering a 300-mile
range, and ATC's data only made that certain rather than hypothetical.

## The design

### 1. Extract facts, link for prose

**The artifact carries the facts and ATC's own headline. It does not carry ATC's body text.**

Per update: `atc_id` (their slug), `title`, `category`, `states`, `start_mile_marker`,
`end_mile_marker`, `updated_at` (their `dateModified`, which every update page publishes as
proper schema.org metadata), and `source_url`.

This is a licensing posture as much as a payload decision, and it is deliberately the
conservative one. [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) is blunt that ATC's redistribution
terms are one of two unresolved data-terms questions this project carries, and that both
arose the same way: *"the data was fetched first and the right to ship it was investigated
afterwards."* Republishing ATC's authored paragraphs into an artifact on our CDN is squarely
inside that unresolved question. A mile number, a date and a category are facts about the
trail; the paragraph describing them is ATC's writing.

**This is not a workaround for asking.** The conversation SOURCE_REGISTRY.md wants with ATC
should still happen, and this feature is a good reason to have it — a request to mirror
safety notices is a much easier conversation than a general redistribution ask, and it comes
with something ATC wants (their notices reaching more hikers, credited). What the split buys
is that **the useful version ships without waiting on that answer**, rather than joining the
queue behind it.

**And the facts alone are genuinely enough to act on.** *"Closure — SW Virginia: VA Creeper
Trail Closure/Detour — mi 476.6–485.8 — ATC, updated 17 Jul"* tells a hiker to stop and find
out more. That is the job of a warning; the paragraph is the job of the page it links to.

### 2. It reaches a hiker the way closures already do

[CONDITIONS_DELIVERY.md](CONDITIONS_DELIVERY.md) built this path already. A new artifact in
the family it established:

```
conditions/closures.json        verified OurHike closures      (built)
conditions/reports.json         verified public reports        (step 3 there)
conditions/atc_updates.json     the ATC's own notices          (this document)
```

Published from `pipeline/`, referenced from `latest.json` with a sha256, read from R2 with no
account and no backend. It inherits that document's three-state model — `live` / `baseline` /
`unavailable` — and its rule that **a baseline must carry its own generation timestamp and
the client must render it**. Here that matters twice over, because the artifact has two ages:
when OurHike last looked, and when ATC last edited the update. Both are real, they differ,
and the one a hiker cares about is ATC's.

### 3. The client work is nearly done already

The rendering path exists and needs no new geometry code:

- **`lib/trailPosition.ts`'s `trailSlice(index, start, end)`** turns a mile range into
  coordinates against the centerline index.
- **`map/closureLayers.ts`'s `closureBands`** turns those into a `MultiLineString` source.
- **`lib/closureBanner.ts`** warns from a mile number alone — which is exactly why it is the
  load-bearing surface: an update whose range cannot be drawn is still one a hiker is told
  about, a property that module already documents.
- **`chrome/ClosureSheet.tsx`** renders reason, dates and an outbound `reroute_url`, with the
  `http(s)`-only scheme validation a safety sheet needs.

What is new is **presentation, not geometry**: an ATC update must be visibly ATC's, not
OurHike's, and it needs its outbound link.

### 4. Provenance is the part that must not be smoothed over

An ATC notice, a verified hiker report, and an unverified hiker report are three different
kinds of claim. They must not render identically.

`SOURCE_REGISTRY.md` already has the vocabulary — `authoritative` / `community` /
`unverified` — and an ATC notice about the A.T. is the definitive `authoritative` case. The
sheet should say *"Appalachian Trail Conservancy — updated 17 July 2026"* with a link, not
present it as something OurHike verified. **OurHike did not verify it; ATC published it, and
those are different statements.** Laundering the second into the first is the exact failure
value #4 exists to prevent, and it would also misrepresent ATC.

### 5. `closures` is the wrong table, and the schema says so

The obvious implementation — write parsed updates into the existing `closures` table — hits a
wall worth naming before someone works around it:

```python
reported_by = Column(String, ForeignKey("profiles.id"), nullable=False)
```

**An ATC update has no reporter.** The workaround is a synthetic "ATC" profile row, and it
should be refused: it puts a fictional person in the identity table, makes ATC's notices
indistinguishable from a member's submissions in `GET /moderation/queue`, and quietly implies
someone accepted responsibility for a claim they never made.

**So ATC updates are their own artifact, joined at read time in the client, and never written
to `closures` at all.** That also keeps the ingest entirely inside the pipeline: no backend
change, no migration, no new credential — a real simplification, not just a schema nicety.

### 6. The parse proposes; a human publishes

**No parsed range reaches a hiker without a person confirming it.**

`DATA_RELEASES.md` already establishes the pattern and `SOURCE_REGISTRY.md` restates it:
registration proposes, a merged pull request releases. Here that means a scheduled job reads
the updates, parses them, and **opens a pull request against a reviewed file in git** with the
proposed rows. A human compares each parsed range against ATC's sentence and merges.

The reasons this cannot be automatic are specific, not procedural caution:

- **A regex is deciding what a safety surface says.** `spike_atc_updates.py`'s comments
  record one real near-miss: a number pattern without the thousands separator reads
  `NOBO mile 1,503.6` as **mile 1** — a shelter in Connecticut rendered as a point in
  Georgia. It parses, it looks plausible, and it is 1,502 miles wrong. That class of error
  produces a *confident* wrong answer, which is the kind a review catches and a schema check
  does not.
- **Some updates are the end of a closure, not the start of one.** "NC/TN: Iron Mtn Gap
  **Reopened**" is an update whose content is that the trail is open again. An ingest that
  only ever adds closures accumulates barriers across trail people have been walking for
  weeks. `ClosureStatus.open` already means exactly "reopened" — but deciding that a page
  means it is a reading comprehension task, and MAP_OPTIONS.md already reserves reopening as
  *"the maintainer's judgment"*.
- **Multiple ranges per update.** Iron Mtn Gap states three different ranges as it was edited
  over months; the current one is not mechanically distinguishable from its own history.

The volume makes this trivially affordable: **nine updates, edited maybe weekly**. A human
gate on nine items is minutes, and one wrong band on a safety map costs more than that.

## What the feed does not carry

`/trail-updates/feed/` is a real RSS feed with full `content:encoded` bodies — but on
2026-08-09 it held **3 items while the page showed 9**. Trail Updates are ordinary WordPress
posts (there is no custom post type in `/wp-json/wp/v2/types`, checked), so the feed reflects
recent *publishing* rather than the live notice board. Three of the nine were absent from it,
including the Creeper Trail closure — the most consequential one on the list.

**So the feed alone is not the source of truth, and building on it as though it were would
silently drop the updates that matter most.** Reading the listing page for the current set is
the honest input, with the feed as a cheap change signal. Recorded here because the feed looks
like the right answer, and finding out otherwise costs a release.

`check_freshness.py` already normalises four incompatible "did this change?" signals and
already keeps `STALE` and `UNKNOWN` apart. A fifth marker here is a row, not a mechanism.

## Honest costs

- **Staleness on top of staleness.** ATC's update is already some hours old when we read it,
  the bake adds up to a day, and a hiker's download adds more. MAP_OPTIONS.md names this
  exact tension for closures generally. The mitigation is the same and it is not a fix: show
  both dates, and never let "we have not looked recently" read as "nothing is happening."
- **Someone has to review, weekly.** Small, but it is a standing commitment, and a review
  queue nobody services becomes an ingest that silently stopped. The artifact's own timestamp
  is what makes that visible rather than invisible.
- **Their HTML is not an API.** A theme change breaks the parse. It should fail loudly and
  publish nothing rather than publish a partial set — an empty band where a closure is, is
  the failure mode `export_conditions.py` was written to prevent, and it applies verbatim.
- **Half-mile markers are half-mile markers.** ATC quotes tenths; the marker layer resolves
  to the nearest 0.5, up to a quarter mile of slop. Fine for a warning band, and the reason
  the published range should come from `trailSlice` against the centerline rather than from
  the marker coordinates themselves.
- **It is one more thing to un-break when ATC reorganises their site**, which is a real cost
  a fork inherits along with the feature.

## Order of work

1. ~~**Ask ATC.**~~ **Not done, and closed as such** (#458). The maintainer settled the
   conservative version on their own judgement as an ATC trail volunteer, which is what the
   `licence` field on `atc_trail_updates` now records: facts and a link, and no mirroring of
   ATC's prose. The broader question — may we carry their body text, and what attribution
   string do they want — is still unasked, and SOURCE_REGISTRY.md's diagnosis still applies
   to it.
2. ~~**Register the source.**~~ **Built.** The thirteenth `sources.json` entry and the first
   that is not an ArcGIS layer, with `kind`, `trust: authoritative`, a `licence`, a steward,
   and a freshness marker — the feed's ETag, compared against what the reviewer recorded, so
   a STALE verdict means *go and re-read ATC's page* rather than *refetch*. `lib/source_registry.py`
   is what reads `kind`; `fetch_all.py` skips anything that is not a feature layer.
3. ~~**Bake `conditions/atc_updates.json`**~~ **Built.** `export_atc_updates.py` reads
   `reference/atc_updates.json`, validates every row, and publishes through the existing
   machinery. It refuses two ways, differently on purpose: an *unreviewed* file publishes
   nothing and exits 0, and a *reviewed* file with a bad row publishes nothing and fails.
4. ~~**Render it**~~ **Built.** `lib/atcUpdates.ts` adapts an update into the shared
   `Closure` shape for geometry alone; `chrome/AtcUpdateSheet.tsx` carries ATC's name, both
   dates and the outbound link; the banner names the ATC before anything else; the
   band-length ceiling comes free with the shared path.
5. **Then** the proposing job, once the reviewed-file path is proven by hand.

**What is left before a hiker sees anything is the rows themselves.**
`reference/atc_updates.json` ships empty and unreviewed, because its contents are a claim
about where the Appalachian Trail is shut and this document is explicit that no such claim
reaches a hiker without a person confirming it against ATC's own sentence. Filling it in is
that person's pull request. Until then the artifact is not published at all, the client reads
a 404, and no ATC layer is drawn — which is the honest rendering of "we have not looked yet"
and deliberately not the same as an empty document saying ATC reports nothing.

## Open questions

- **The band-length ceiling — the number, not the mechanism.** The mechanism is built
  (`MAX_BAND_MILES`, above), so an update over the ceiling is already no longer drawn as a
  band. What is still open is the value: 398 miles is clearly over it and 9 miles clearly
  under, and everything between is unconstrained by the data ATC publishes — their nine
  updates measure 0, 0, 0, 4.2, 9.2 and 398.4 miles, so more updates would not settle it
  either. Worth setting against what the map looks like at real zooms. The current value errs
  toward drawing, because a suppressed band buries nothing while the hiker keeps the banner.
- **Where the suppressed ones go.** "List entry" still has no surface: an update that loses
  its band keeps its banner and nothing more. Two things reach that state rather than one —
  an over-ceiling advisory, and an update that does not actually stop a hiker walking
  through.

  **The second was nearly got wrong, and the mistake is worth recording.** It was first
  built as a rule over ATC's `category`: draw `Closure` and `Detour`, banner the rest. Live
  data on 2026-08-12 killed that. ATC files these two under the same word:

  | Update | Category | Is the trail passable? |
  |---|---|---|
  | Connecticut: Limestone Spring Shelter Closed | `Closure` | **yes** — the shelter is shut, the trail is not |
  | Harpers Ferry: Footbridge Closure | `Closure` | **no** — the way across the Potomac is gone |

  A band drawn for the first is a barrier a hiker walks straight past, which is how they
  learn the barriers can be ignored — the exact failure the rule existed to prevent, arriving
  through the one case nobody thought to check. So it is now `obstructs_trail`, a field the
  reviewer sets per row, and it sits with every other judgement this data needs rather than
  being inferred. Which is the argument this document already makes about the mile ranges,
  landing a second time somewhere nobody expected it.
- **Whether "reopened" updates should be ingested at all**, or whether ATC removing an update
  is the signal. An update that disappears from their page is not the same as one marked
  reopened, and `discover_sources.py`'s precedent — a vanished source is "kept, not deleted,
  with a warning" — suggests disappearance is the weaker signal of the two.
- **What happens when ATC and a hiker disagree.** A verified OurHike closure and an ATC
  notice covering overlapping miles will happen. SOURCE_REGISTRY.md's rule for two
  organizations mapping the same thing — *show one and disclose the other, never average,
  never silently dedupe* — is the obvious starting point, and worth confirming against what
  the closure sheet can actually display.
- **Whether the non-mappable updates deserve a home.** A region-wide severe-weather advisory
  is real information with no place on a map. HIKER_SAFETY.md's Post-MVP NWS weather relay is
  the closer fit, and this document deliberately does not design a general notices screen.
- **The other direction.** OurHike will accumulate verified closures ATC does not know about.
  Whether anything should flow back is a conversation with ATC, not a feature — but it is the
  half of the relationship that makes registering as a data *consumer* less one-sided, and
  SOURCE_REGISTRY.md's contact tiers already contemplate telling an organization something
  useful about their own geography.
