# Alerts and notices, org by org — a qualified survey (August 2026)

Companion to [../features/ATC_TRAIL_UPDATES.md](../features/ATC_TRAIL_UPDATES.md) (the one
org whose notices already reach a hiker, and the design this survey holds every other org
against), [../features/CONDITIONS_DELIVERY.md](../features/CONDITIONS_DELIVERY.md) (how a
notice reaches a phone once it exists), [SOURCE_SURVEY.md](SOURCE_SURVEY.md) and
[NYC_SOURCE_SURVEY.md](NYC_SOURCE_SURVEY.md) (where each org's *trail* data came from —
this survey is the same reconnaissance for their *alerts*).

Why this exists: the maintainer's ask, 2026-08-27 — *"We should have the Alerts and
Notices from all the orgs, not just the ATC."* Today `conditions/atc_updates.json` carries
ATC's Trail Updates and nothing carries anyone else's, while the map now draws OPRHP, DEC,
NYNJTC and Mohonk Preserve trails. Every org was probed twice: **its map layers first**
(the ask's own ordering, and the right one — structured beats scrapeable), **its webpages
second**. Written 2026-08-27 from live probes; every ArcGIS date below is the layer's own
`editingInfo.dataLastEditDate` read that day, every count a live `returnCountOnly` query,
and every "no feed found" names the URLs that answered 404.

## Two lanes, so the verdicts mean one thing each

The repository already delivers "something is wrong ahead" two different ways, and an org
can supply either without the other:

- **The geometry lane** — a closed line or area drawn on the map.
  [#964 — NYS Parks closes areas, not trail segments, and the closure model has nowhere to
  put one](https://github.com/OurHike/OurHike/issues/964) built this for OPRHP's closure
  polygons; ATC updates become mile-range bands.
- **The notice lane** — a dated, titled entry a hiker can read and follow to its source:
  `conditions/atc_updates.json`, `kind: published_notices` in `sources.json`, the reviewed
  file, the banner. **This is the lane that is ATC-only today**, and the one the ask is
  about.

What a notice-lane entry has to carry, per ATC_TRAIL_UPDATES.md's artifact: a title, a
category, a location, **the org's own last-updated date**, and a link back. The date
column below is the one to watch — it is the field most orgs turn out not to publish, and
a notice without its own date can only ever render in the voice of "when we last looked",
which CONDITIONS_DELIVERY.md's staleness rule treats as the weaker of the two ages.

## 0. The verdicts, one line each

| org | notices in map layers? | notices on webpages? | dated? | structured? | verdict |
|---|---|---|:-:|---|---|
| ATC | no — prose site (SOURCE_SURVEY §4) | Trail Updates, ~89 entries | ✓ | scraped + human-reviewed | **shipping** — the baseline |
| NPS (APPA) | Helene program layers only (SOURCE_SURVEY §3c) | conditions page is a 2016 template | — | Alerts API exists, needs a free key | §2 — thin; ATC is the A.T. channel |
| NYS OPRHP | **✓ closure polygons — registered, shipping** | **✓ per-park alert blocks, richer than the layer** | ✓ posted dates | server-rendered HTML; no feed | §3 — **the layer under-covers their own site**, measured |
| NYS DEC | none anywhere in the estate | prose hubs + per-place pages, notices woven into paragraphs | ✗ none | none; RSS is an empty stub | §4 — the weakest; honest answer is "not ingestable today" |
| NYNJTC | 3 conditions-shaped extracts, no status/date fields | **✓ Trail Alerts — a real WordPress REST API** | ✓ date + modified | **✓ JSON, queryable** | §5 — **the find; the second notices source** |
| Mohonk Preserve | deer-hunt restriction zones, fresh, no dates | ✓ one Alerts page, edited in place | page-level ✓ | one page + machine-readable `modified` | §6 — small and current |
| NJDEP (next in line) | unknown | advisories page + park status map exist | ? | unprobeable — Incapsula wall | §7 — needs a browser |

## 1. ATC — the baseline, restated in one paragraph

Shipping since [#461 — Show ATC updates on the map, as the ATC's word rather than
OurHike's](https://github.com/OurHike/OurHike/issues/461): `fetch_atc_updates.py` reads
the listing as content, a person reviews `reference/atc_updates.json`, and
`export_atc_updates.py` publishes facts and a link — never ATC's prose. Everything below
is measured against that shape. Worth carrying from the A.T. survey: ATC's own ArcGIS org
publishes **no** general notices layer either (the Helene closure polygons are a
program-lifetime product, SOURCE_SURVEY.md §3c) — so the org whose notices we ship is
itself a webpage scrape. Nobody should expect the other orgs to be tidier.

## 2. NPS (APPA) — the A.T.'s co-steward, and a dead surface

The NPS hosts ten of the twelve A.T. layers (SOURCE_SURVEY.md §1), so it is an org in its
own right, checked separately from ATC:

- **Map layers: nothing.** No alerts-shaped service beside the APPA layers; the Helene
  status twins are catalogued in SOURCE_SURVEY.md §3c and are recovery-program-scoped.
- **Webpages:** `nps.gov/appa/planyourvisit/conditions.htm` answers 200 and is a template
  whose alerts section reads "Last updated: March 23, 2016" with no alerts in it —
  fetched and read 2026-08-27. The park homepage embeds no alert content server-side
  (grepped the fetched HTML; the banner loads by script). In practice the Service defers
  A.T. conditions to ATC, which is where this project already reads them.
- **The structured channel that does exist:** the NPS Alerts API
  (`developer.nps.gov/api/v1/alerts?parkCode=appa`) — title, description, a category
  vocabulary (Park Closure / Danger / Caution / Information), URL, per-alert dates, for
  every park unit. It needs a (free) API key; probed 2026-08-27 with the shared
  `DEMO_KEY` and rate-limited away (HTTP 429), so **what APPA currently has in it is
  unverified**. Given the 2016 template above, expect little.

**Verdict: no action for the A.T.** — ATC's feed is the living one. The API is worth
remembering for a different reason: if OurHike ever draws trails in a *staffed* NPS unit
(Harriman's neighbor Bear Mountain is state, but e.g. the Delaware Water Gap NRA is NPS),
one key covers every unit's alerts in one structured vocabulary. **NEEDS REVIEW** only
when such a unit ships.

## 3. NYS OPRHP — a shipping layer, and the site that outruns it

The one org that publishes closures as *data* — and the survey's second-most important
finding is that the data is the smaller half of what they publish.

### 3a. The layer, re-probed

`oprhp_trail_closures` (`NY_State_Parks_Temporary_Trail_Closure/FeatureServer/0`,
registered by [#769](https://github.com/OurHike/OurHike/issues/769), shipping through
`export_nearby_trails.py` since #964): **4 polygons on 2026-08-27**,
`dataLastEditDate` 2026-06-16 — three Bear Mtn./Harriman "extreme rainfall event in 2023"
areas and one Hudson Highlands "Closed Until 2027 due to construction" (the Breakneck
Fjord Trail project). Everything #964 recorded still holds: areas not segments, reasons as
prose in a field named `Name`, no dates anywhere but the layer-level edit stamp.

Nothing else alert-shaped exists in the org: all 160 public services listed 2026-08-27,
and an AGOL item search for alert/closure/advisory returns the closure service, a web map
that draws it ("Bear Parks App w/ Closures"), and two false positives. The two
`Beach_Status` services are the same idea for swimming and are not trail data.

### 3b. The website, measured against the layer

parks.ny.gov is Drupal 10 (its own generator tag), and **every park page carries an
Alerts block, server-rendered**. Minnewaska's page on 2026-08-27: five alerts, posted
2025-01-01 through **2026-08-13**, including "Lake Awosting Carriage Road Closed for
Restoration" (posted 2025-10-24).

**The markup is better than a scrape usually gets, and this section first understated
it.** One alert, verbatim off the live page:

```html
<section class="c-alert is-dismissible" id="40611-110711"
         aria-labelledby="alert--40611-110711--label">
  <div class="c-alert__content">
    <h2 class="c-alert__title" id="alert--40611-110711--label">
      Boating and SCUBA diving will have a delayed start time on August 30th
    </h2>
    <div class="c-alert__message" id="alert--40611-110711--description">…</div>
    <div class="c-alert__date">
      Posted <time datetime="2026-08-13T04:02:00Z">August 13, 2026 12:02 am</time>
    </div>
  </div>
</section>
```

Three properties that decide what a parser costs:

- **A stable per-alert identity.** The `id` is `{park node}-{alert node}` — `40611-110711`
  — so a notice has a real `notice_id` without one being minted, and an alert can be
  followed across bakes.
- **A machine-readable date.** `<time datetime="…Z">` is ISO 8601 in UTC, so `updated_at`
  is read rather than parsed out of the printed "August 13, 2026 12:02 am".
- **Semantic BEM classes** — `c-alert__title` / `__message` / `__date` — rather than
  positional guesswork.

So the parse would be *cheaper and less fragile than ATC's*, which needs a regex over
prose to find a mile. What it would not get is a category: the icon is `sprite…#bell` on
all five alerts, carrying no severity or type, so `category` would be null exactly as it
is for NYNJTC (features/ORG_NOTICES.md §2).

**And the same five alerts show why review is not optional.** "No Smoking" and "Live
Minnewaska Weather" sit in identical markup to the carriage-road closure. Nothing in the
page distinguishes a trail closure from a park rule, which is the mechanically-unambiguous
-subset problem `lib/atc_updates.py` solves for ATC by hand.

**That closure is not in the GIS layer.** Four polygons, none of them Minnewaska — so a
hiker reading OurHike's OPRHP-derived closure marks sees the Harriman and Breakneck areas
and not the Awosting one, while OPRHP's own site (and NYNJTC's alerts, §5) both carry it.
The layer is real and worth shipping; it is also **a subset of what its own org publishes,
measured on one park** — the display-outrunning-its-source rule in reverse, and worth a
line in any surface that presents OPRHP closures as complete. How big the subset is
trail-wide is unmeasured (one park checked); `@unvalidated` — settling it means scraping
the alert blocks of every park page whose ground carries shipped trails and diffing
against the four polygons.

**No aggregate exists to fetch instead:** `/alerts` 404, `/api/alerts` 404, Drupal's
JSON:API disabled (`/jsonapi` 404), and `rss.xml` is a six-item site-section index with no
alerts in it (all probed 2026-08-27). The alerts are per-park pages or nothing.

**What a scrape would actually cost, measured 2026-08-27** — the "~250 requests on some
cadence" this section first estimated was a guess, and the real numbers are better in one
way and decisively worse in another:

| | measured |
|---|---|
| park pages | **194** under `/visit/state-parks/` (plus 37 historic sites, 20 nature centers), enumerable from `sitemap.xml` in one request |
| `robots.txt` | **permits it** — only Drupal internals (`/core/`, `/profiles/`, READMEs) are disallowed, and there is no `Crawl-delay` |
| page weight | **358 KB** each, so a full sweep is **≈ 68 MB** |
| parks carrying trails we draw | **187 of 194**, so scoping to "parks we ship" saves nothing |

**And there is no change-aware path, which is the finding that decides it.** The sitemap
carries `<lastmod>` on every entry and looks like the answer. It is not:
**Minnewaska's `lastmod` reads 2026-08-04 while its page carries an alert posted
2026-08-13.** Alerts are referenced entities in Drupal and do not touch the park node's
timestamp, so a fetcher trusting `lastmod` would skip that park and silently miss a new
notice — the worst failure available to a safety source, and invisible without testing
against a park known to have a recent alert. Nor do the pages offer a validator: no
`ETag`, a `Last-Modified` that is the render time (it answers *now*), and Drupal's own
`x-drupal-dynamic-cache: UNCACHEABLE (poor cacheability)`.

So a sweep cannot ask "has this changed?" — it can only fetch all 194 and hash the bodies.
Narrowing by geography is not the escape either: [#1019](https://github.com/OurHike/OurHike/issues/1019)'s
standing decision is *"Don't limit data from orgs based on geography."*

The alert mix is also broader than trails — Minnewaska's five include no-smoking and a
weather-page link — so a scrape needs the same mechanically-unambiguous-subset thinking
`lib/atc_updates.py` encodes, or the same human review, before anything renders as a
safety notice.

**Verdict: ask OPRHP for a feed before building this.** They run Drupal; a view exposing
these alerts as JSON is small work for them and would give what NYNJTC's API gives for
free (§5b) — and the alerts are already structured entities with their own node ids and
ISO timestamps, so such a view would be exposing what the page markup above proves they
hold, not asking them to author anything new. That ask belongs in the licence conversation already open with them
([#769](https://github.com/OurHike/OurHike/issues/769)). The scrape stays buildable — a
daily sweep, body-hashed, human-reviewed before publication — and if it is built, the
68 MB a day and the reason for it belong in the registry entry's notes rather than in
anybody's memory.

## 4. NYS DEC — real notices, published like it is 1998

DEC's trails ship statewide (5,286 segments, `dec_hiking_trails`) with **no closure
signal at all** — the layer has no status column (recorded in `sources.json` at
registration), and this survey confirms there is nothing to join one from:

- **Map layers: none.** The full server root and the `dil` folder enumerated 2026-08-27 —
  22 `dil` services, every one an asset inventory (lean-tos, fire towers, parking) or
  reference layer. `dil_permits_and_regs` is environmental-facility permits (landfills,
  air permits), not recreation regulations; `dil_sensitive_areas` is wetlands. Nothing
  carries a closure, a notice, or a date-bounded restriction.
- **Webpages: notices exist and are undated prose.** Two hub pages — "Adirondack
  Backcountry Information" and "Catskill Backcountry Information" — carry genuine,
  current notices (the Catskill hub on 2026-08-27: a flooding advisory, Route 23A/Platte
  Clove parking restrictions, the Blue Hole permit season, the Molly Smith lot closure).
  Per-place pages carry more of the same (Kaaterskill Wild Forest checked: four notices
  **woven into the page's paragraphs, no dedicated section, no posted dates**). Nothing on
  any of these pages carries a machine-readable date or identity — there is nothing to
  anchor "their last-updated" to, which is the field the notice lane is built on.
- **Feeds: none that work.** `dec.ny.gov/rss.xml` answers 200 and contains an empty
  channel — zero items, probed 2026-08-27. The change channel DEC actually operates is
  GovDelivery email ("Catskill Outdoor Recreation Bulletin"); its bulletin pages 403
  scripted fetches, so whether an ingestable archive exists behind it is unknown from
  this sandbox.
- **The partner channel:** the Catskills Visitor Center (run by the Catskill Center, not
  DEC) publishes weekly "Catskill Trail Conditions" posts — a WordPress `trail_update`
  post type, which would be exactly §5's shape — but the site is Cloudflare-walled and
  403s `wp-json`, the RSS feed, and this sandbox's page fetcher alike (all probed
  2026-08-27). **NEEDS REVIEW with a real browser**; and it would enter as a
  partner-tier source, not DEC's own word.

**Verdict: DEC has no ingestable notice source today**, and the gap is the widest of any
org — statewide DEC trails render with no closure state and there is nowhere upstream to
get one. An honest unknown outranks a confident answer: the export's current posture
(every DEC row ships as open because DEC publishes no status) is correct, and the fix is
DEC's to make. The ask NYC_SOURCE_SURVEY.md §10(c) already wants — bundle DEC into the
OPRHP licence conversation — should add one line: *does DEC publish trail
closures/notices anywhere structured, or plan to?*

## 5. NYNJTC — the find: a real alerts API, better-shaped than ATC's

### 5a. Map layers: conditions-shaped, but not a feed

The org's 25 services include three that publish *conditions as geometry* — what
NYC_SOURCE_SURVEY.md §4 called "the shape ATC_TRAIL_UPDATES.md wishes ATC used" — and on
a closer read none of them can carry the notice lane:

| service | rows | data last edited | what the rows say |
|---|---:|---|---|
| `Long_Path_Minnewaska_Fire_Detour` | 2 | **2023-04-20** | "Temporary detour to avoid closed areas impacted by Minnewaska forest fire of **summer 2022**" |
| `Long_Path_West_Point_Seasonal` | 3 | 2025-01-09 | recurrence windows as prose in `Comments` — "Closed May 1 through August 15 and during fall hunting season", "closed February 1 through July 31" |
| `Long_Path_Shawangunk_Ridge_Trail` | — | — | route variant, not a condition |

No status field, no effective dates, no way to tell in-effect from historical — the fire
detour is a 2022 event whose current validity the layer cannot state (the NYC survey's
"live detour" read the item's existence, not its age; the age is three years). These are
**reroute geometry to attach to a notice**, not notices. Useful in exactly that role:
NYNJTC is the one org that publishes the *detour line itself* as data.

### 5b. The website: a queryable, dated, actively-tended alerts feed

nynjtc.org runs WordPress with a **"Trail Alerts" category (id 6) exposed in full through
the standard REST API** — read live 2026-08-27:

```
GET nynjtc.org/wp-json/wp/v2/posts?categories=6&per_page=30
```

**18 posts, 2024-01-11 → 2026-06-16**, each with `slug`, `date`, **`modified`** (they
maintain old alerts in place — the Bear Mountain advisories post, published 2025-11-21,
was modified 2026-05-04), `title`, `link`, and the full HTML body. An RSS sibling exists
(`/category/trail-alerts/feed/`, 12 items) — the JSON API is the better interface and the
RSS the free change-signal, the exact division `atc_trail_updates`' freshness entry
already uses. Current entries: an A.T. detour at Harriman, the Breakneck Ridge trailhead
closure, the Giant Stairs rockfall closure, Delaware Water Gap winter closures, the Lake
Awosting carriage-road closure.

Three properties, stated with their costs:

- **It is machine-readable at the source** — no scrape, no parse gamble; `per_page`,
  `modified_after`, and `_fields` are query parameters. The fragility budget a scraper
  spends on markup, this spends on nothing.
- **It is cross-org** — NYNJTC reports on OPRHP parks, NJ state forests, PIPC, DWG.
  That is its value (one feed covers the region's grounds) and its hazard: several
  entries restate what a land manager published (Breakneck, Awosting both appear here
  *and* on parks.ny.gov), so shipping both sources needs a dedup posture, and the
  attribution must say NYNJTC-reporting-on-OPRHP-ground, not OPRHP.
- **Locations are names, not miles** — no NOBO-mile convention exists off the A.T., so an
  update whose place cannot be drawn is still one a hiker is told about (list entry first,
  geometry when a place resolves), which is ATC_TRAIL_UPDATES.md's own fallback.

  **Corrected the same day, and the correction is the reason this source is worth having.**
  The sentence above was written from the alert *prose*, where the names do indeed sit in
  paragraphs — and it understated the payload, because a first read of one post's fields
  stopped at the ones ATC's shape had taught this survey to look for. **NYNJTC tags every
  alert from its own closed taxonomies**, and the API returns them as term ids:

  | taxonomy | terms | populated on the 18 alerts |
  |---|---:|---:|
  | `trail` | 45 | 10 |
  | `park` | 125 | 17 |
  | `region` | 13 | 7 |
  | `state` | 3 | 7 |

  So placement is a join against **45 trail terms**, not a fuzzy match of prose against the
  21,805 exported network features — a table a person reviews in one sitting rather than a
  guess with a hiker's location attached. Two things measured while confirming it, both now
  carried in the registry entry: `park` answers exactly 100 to a single `per_page=100`
  request and has 125 terms, so a vocabulary asked for once is silently truncated; and
  `highlands-trail` is a term in **both** the trail and park taxonomies (ids 31 and 405),
  so a join table must key on `taxonomy:slug` and never on the slug alone.

  This is §0's own frame catching this survey out — *structured beats scrapeable* — one
  level below where it first looked.

**Verdict: this is the second `published_notices` source**, and the machinery to receive
it exists end-to-end — `lib/source_registry.py`'s kind, the fetch-as-content pattern, the
reviewed file, `conditions/*.json` delivery. The licence caveat is the standing one:
NYNJTC has stated no terms (`nynjtc_licence`), the facts-not-prose split that shipped
ATC's updates applies verbatim here, and the maintainer's open NYNJTC conversation
([#768 — v2: trails within reach of NYC](https://github.com/OurHike/OurHike/issues/768))
should add trail alerts to its scope. **NEEDS REVIEW** on exactly that: republishing
title + date + category + link is the same conservative posture #458 settled for ATC,
decided then by the maintainer's judgement — someone has to make the same call in
NYNJTC's name, ideally NYNJTC.

## 6. Mohonk Preserve — one page, tended, with a timestamp

- **Map layers:** `MP_Deer_Management_with_Restrictions` — 16 hunt-zone polygons,
  `dataLastEditDate` **2026-08-18**, nine days before this survey. Zone name and acreage
  only; the season's dates live on the website, not in the layer. Seasonal-restriction
  geometry awaiting a notice to explain it, same standing as NYNJTC's seasonal routes.
  Nothing else in the 23-service org is alert-shaped (listed 2026-08-27).
- **Webpage:** `mohonkpreserve.org/visit/alerts/` — a single WordPress *page* (id 13789)
  edited in place, current closures with date ranges in the body ("Undercliff Carriage
  Road… Monday through Thursday from July 20 – Aug 28", resurfacing). The page's
  `modified` stamp is readable as JSON
  (`wp-json/wp/v2/pages/13789`, reading **2026-08-25T17:03** on 2026-08-27 — edited two
  days before this survey), so a fetcher gets a real change signal even though the
  entries themselves carry no per-item identity. One page to parse, no archive, no
  categories — a scrape the size of a lunch break, with the usual unstated-licence
  caveat (`mohonk_licence`'s open question, [#992](https://github.com/OurHike/OurHike/issues/992)).

**Verdict: ingestable as a single-page notice source with page-level freshness** —
per-item dates would have to be parsed out of prose or left absent, and absent-means-
unknown is the rule if they don't parse.

## 7. Next in line: NJDEP, noted so the blank is a recorded blank

Not yet a registered org (NYC_SOURCE_SURVEY.md §5's NEEDS REVIEW on the Data Distribution
Agreement stands), but the moment NJ ships this question arrives with it. What is
already knowable: NJDEP operates a "Park Advisories" page and a **"Park Status Map"** —
a status *map* implies a service behind it — but the whole estate
(nj.gov meta-refreshes to dep.nj.gov) sits behind an Incapsula bot wall that returns
challenge stubs to every fetcher this sandbox has (probed 2026-08-27, 212-byte
responses). **NEEDS REVIEW with a real browser when NJ registers** — specifically whether
the status map is an ArcGIS layer, which would make NJDEP the second org after OPRHP to
publish closures as data.

## 8. Placement off the A.T., named as its own problem

> **Superseded 2026-08-27 by [../features/ORG_NOTICES.md](../features/ORG_NOTICES.md)**
> ([#1077](https://github.com/OurHike/OurHike/issues/1077)), which owns this question and
> answers it — a tagged `place` union with *unplaced* as a first-class arm, and a reviewed
> join table over each org's own vocabulary. This section is kept as the statement of the
> problem, and §5b's correction is the fact that changed its shape: NYNJTC's half of it is
> a join over 45 terms rather than the prose name-match described below.

ATC's updates were cheap to place because ATC writes NOBO miles and the build already had
the mile-to-coordinate table (ATC_TRAIL_UPDATES.md's "the find that makes this cheap").
**No other org has a mile axis.** What they have instead:

- **OPRHP:** closure *polygons* — placement solved by intersection, built (#964).
- **NYNJTC:** park and trail *names* in prose — a name-join against `nearby_trails`
  features and park polygons, with the list-not-band fallback for anything that does not
  resolve. Occasionally a paired detour layer (§5a) is the geometry.
- **Mohonk:** carriage-road names on one page; same name-join, tiny namespace.
- **DEC:** nothing to place yet.

The join target exists: every exported network feature carries its name and source org.
What does not exist is the reviewed mapping from "the names an alert uses" to "the
features we ship" — that is the `reference/`-shaped, human-reviewed piece any
implementation would add, and it is the piece that keeps a notice from landing on the
wrong trail, which on the notice lane is the cry-wolf failure.

## 9. Licensing, summarized

Same rule as both parent surveys: public ≠ licensed, and the notice lane adds one
distinction that already earned its keep with ATC — **facts about the trail versus the
org's prose**. Every verdict above assumes the ATC split: mile/name, category, date,
headline, link out; never the body text.

| org | notices licence reality | covered by an existing conversation? |
|---|---|---|
| NYS OPRHP | site terms not read for the alerts pages; the GIS terms (`oprhp_licence`) are stated and permit reuse with attribution, non-commercial | yes — [#769](https://github.com/OurHike/OurHike/issues/769)'s open ask; add the web alerts to it |
| NYS DEC | nothing to license yet (no ingestable source) | yes — the DEC bundle in the OPRHP ask (NYC survey §10(c)); add the "anything structured?" question |
| NYNJTC | unstated, like their extracts (`nynjtc_licence`) | yes — [#768](https://github.com/OurHike/OurHike/issues/768); add trail alerts explicitly |
| Mohonk Preserve | unstated (`mohonk_licence`) | yes — [#992](https://github.com/OurHike/OurHike/issues/992)'s open question |
| NPS | public domain if ever used (federal work) | n/a |

## 10. What to do with all this, ranked

Candidate follow-ups, deliberately not done in this survey:

1. ~~**Register NYNJTC's Trail Alerts as the second `published_notices` source** (§5b)~~ —
   **done 2026-08-27** ([#1078](https://github.com/OurHike/OurHike/issues/1078)):
   `nynjtc_trail_alerts` is in [sources.json](sources.json) with the RSS feed as its
   freshness marker and `reaches_hikers: false`, fetched by `fetch_nynjtc_alerts.py` into
   a review cache. The delivery design the registration deliberately does not settle —
   placement, dedup against OPRHP's own alerts, whose voice a notice speaks in — is
   [../features/ORG_NOTICES.md](../features/ORG_NOTICES.md)
   ([#1077](https://github.com/OurHike/OurHike/issues/1077)), which supersedes §8 below.
   Republication is still NYNJTC's conversation to conclude (#768).
2. **Say, wherever OPRHP closures render, that they are the layer's four areas and not
   OPRHP's full alert list** (§3b) — one sentence of honesty available immediately, ahead
   of any scraper. The measured instance: Lake Awosting closed on OPRHP's own site since
   2025-10, absent from the layer.
3. **Ask OPRHP for an alerts feed, and decide the scrape only if they decline** (§3b's
   measurements): 194 pages at 358 KB with **no usable change signal** — the sitemap's
   `lastmod` does not move when an alert is posted, and the pages carry no `ETag` — so a
   sweep is ≈68 MB every time it runs. The old wording of this item, kept so the
   correction is visible, read: **~~Decide whether the OPRHP per-park alert scrape is
   worth ~250 pages of surface~~**
   (§3b), or a pilot scoped to the parks whose ground carries the most shipped trail.
   Posted dates and stable ids exist; a feed does not. **NEEDS REVIEW** — this is a
   maintainer-sized cost/benefit call.
4. **Mohonk's alerts page as a single-page source** (§6) — smallest possible version of
   the same pattern, page-level `modified` as the date of record.
5. **Add one question each to the conversations already open** (§9) — OPRHP/DEC: anything
   structured behind the alerts? NYNJTC: may the alert facts be republished? Mohonk:
   same.
6. **CVC and NJDEP need a human with a browser** (§4, §7) — both bot-walled from this
   sandbox; one is the Catskills' only weekly conditions feed, the other possibly the
   second closures-as-data org.

### Marked for maintainer review, collected

| item | why it needs eyes | where |
|---|---|---|
| OPRHP web-alert coverage vs. the 4-polygon layer | safety under-coverage, measured on one park only | §3b |
| OPRHP per-park scrape breadth | 194 pages × 358 KB ≈ 68 MB a sweep, and **no change signal exists** — measured §3b. Ask for a feed first | §3b, §10(3) |
| CVC weekly trail conditions | Cloudflare-walled; partner-tier trust question too | §4 |
| DEC GovDelivery archive | bulletin pages 403 scripted fetches | §4 |
| NYNJTC alert republication | unstated terms; same call #458 settled for ATC | §5b |
| NPS Alerts API content for APPA | unverified (DEMO_KEY rate-limited) | §2 |
| NJDEP park status map | Incapsula-walled; possibly closures-as-data | §7 |

---

*Method note for whoever refreshes this: the ArcGIS claims re-verify the same way as both
parent surveys (`?f=pjson` for `editingInfo`, `/query?returnCountOnly=true`). The web
claims are one `curl` each — NYNJTC's API and Mohonk's page answer plain fetches;
parks.ny.gov wants any browser-shaped User-Agent; CVC, GovDelivery and everything NJDEP
403 this sandbox outright, so their rows are only as old as the last person with a real
browser. Club sites rot faster than federal servers; the A.T. survey's warning holds
here doubled, because alert feeds rot faster than trail layers.*
