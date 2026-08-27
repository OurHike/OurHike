# A notice from an organization that is not the ATC

Companion to [ATC_TRAIL_UPDATES.md](ATC_TRAIL_UPDATES.md) (the one org's notices that
ship, and the design this generalizes rather than replaces),
[CONDITIONS_DELIVERY.md](CONDITIONS_DELIVERY.md) (how a notice reaches a phone),
[NEARBY_TRAILS.md](NEARBY_TRAILS.md) (the network lines a non-A.T. notice has to land on)
and [../pipeline/ALERTS_NOTICES_SURVEY.md](../pipeline/ALERTS_NOTICES_SURVEY.md) (which
org publishes what, measured).

This document owns one question: **the map now draws five organizations' trails and ships
one organization's notices. What has to be true for a second one's to reach a hiker?**

The answer is that almost all of the delivery machinery already generalizes, and exactly
one thing does not — **where a notice is**. ATC says it in miles from Springer. Nobody
else can, and pretending otherwise is the failure mode this document exists to prevent.

Everything measured here was measured on **2026-08-27** against live services;
`pipeline/fetch_nynjtc_alerts.py` reproduces the NYNJTC half and
`pipeline/tests/test_lib_nynjtc_alerts.py` pins the parse against their real payloads.

## 1. What ATC's design assumed without having to say so

[ATC_TRAIL_UPDATES.md](ATC_TRAIL_UPDATES.md) calls its central join "the find that makes
this cheap", and it is exactly right:

> `start_mile_marker` and `end_mile_marker` […] are *that same number*. And
> `sources.json`'s ninth entry — `half_mile_points_from_springer` […] is **ATC's own table
> converting one into the other**.

Two organizations sharing one coordinate system is a coincidence, and it does not repeat.
What the other orgs publish instead, from the survey:

| org | how a notice says where it is | shape |
|---|---|---|
| ATC | `NOBO mile 476.6 to 485.8` | a number on the A.T.'s own axis |
| NYNJTC | tags from their own **closed trail and park vocabularies** | a term id, resolvable to a name |
| NYS OPRHP | closure **polygons** in GIS; per-park web alerts naming trails in prose | geometry, or prose |
| Mohonk Preserve | carriage-road names in prose on one page | prose |
| NYS DEC | nothing placeable, and nothing dated | — |

So the shipped row cannot carry them. `start_mile_marker` is the A.T.'s number and there
is no honest value to put in it for a closure on the Brook Trail — which is in Hudson
Highlands State Park Preserve, forty miles off the A.T., on a trail NYNJTC maintains.

**This is not a naming problem.** The client's whole placement chain —
`atcUpdateAsClosure` → `closureBands`/`atcUpdatePoints` → `trailSlice`/`trailPointAtMile`
— takes a mile against `trailPosition.ts`'s `miles` axis, and that axis *is* NOBO distance
from Springer. There is no lat/lon or name-based entry point anywhere in it. A renamed
field would not help; the mechanism has to gain an arm.

## 2. The row, made org-agnostic

Today's row (`client/src/lib/atcUpdates.ts`, and `lib/atc_updates.py`'s `REQUIRED_FIELDS`)
is nine fields, of which three are ATC-shaped: `atc_id`, and the two mile markers.

The generalization keeps every field that is genuinely about a notice and moves the
location into one place:

| field | what it is | changed? |
|---|---|---|
| `notice_id` | `<source key>:<the org's own slug>` — e.g. `nynjtc_trail_alerts:brook-trail-closure` | replaces `atc_id` |
| `source_key` | the `sources.json` key, which is how the client finds the org's name | new |
| `title` | the org's own headline, verbatim | unchanged |
| `category` | from **that org's** vocabulary, per-org closed set | scope changes |
| `locality` | states, region, or park — the coarse "roughly where" a list entry prints | replaces `states` |
| `place` | **the tagged union of §3** | replaces the two mile markers |
| `obstructs_trail` | whether a hiker is stopped walking through | unchanged |
| `updated_at` | the **org's** own last-updated stamp | unchanged |
| `source_url` | link back to the org's page | unchanged |
| `review_state` | `reviewed` \| `unreviewed` | unchanged |

**`notice_id` is namespaced by the source key rather than by a short org name**, because
the registry key is the thing that already exists, is unique, and is what
`export_sources.py` and `client/src/lib/stewards.ts` already join organizations on. The
client's current `ATC_BAND_ID_PREFIX = 'atc:'` becomes that namespace, which is a
generalization of something already there rather than a new concept.

**`category` stays a closed set and stays per-org.** `lib/atc_updates.py`'s `CATEGORIES`
is twelve words ATC uses, and its comment records the two occasions the list caught ATC
starting to use a new one — that is the mechanism working. A second org gets its own list
for the same reason, and **must not be forced into ATC's**: NYNJTC files every alert under
one category ("Trail Alerts") and publishes no per-alert vocabulary at all, so the honest
value for them today is *absent*, not a guess mapped onto ATC's word list. Absent means
unknown, which is this project's rule everywhere else.

## 3. `place` is a tagged union, and *unplaced* is a real answer

This is the design's one genuinely new idea, and the arm that matters most is the third.

```
{ "kind": "at_miles",  "start": 476.6, "end": 485.8 }              ATC — ships today
{ "kind": "org_terms", "terms": ["trail:brook-trail", …] }         NYNJTC — §4
{ "kind": "unplaced" }                                             honest, and common
```

**ATC's rows become `at_miles` and nothing about their behaviour changes.** That arm is
the existing mechanism, named. The migration is mechanical and the client's mile
arithmetic — `atcUpdateBanner`, `atcUpdateDistanceAhead`, `closureSpan.ts`'s
`MAX_BAND_MILES` — keeps working on it untouched, because it is still the only arm that
carries a mile.

**`unplaced` has to be first-class, and ATC_TRAIL_UPDATES.md already proved it.** That
document's "What is not a map feature, and must not become one" argues exactly this case —
a region-wide severe-weather advisory across ten states, and a law-enforcement request that
"is not a place at all, and pinning it to one would be actively wrong" — and then had no
field for it, so those notices are carried today by *omission* from the reviewed file.
Measured on NYNJTC: **one of the 18 alerts names no trail and no park**, and eight more
name only a park. Giving the state a name is what lets a notice be shown honestly instead
of dropped, and the client already has the surface for it —
`AtcNoticeList.tsx` renders a "not drawn on the map — read it here" branch today.

**Nothing is ever promoted between arms by inference.** A park-only notice does not become
a trail notice because a park contains one trail we happen to draw. That is the
cry-wolf direction, and `wrongWay.test.ts`'s asymmetry — "false negatives are acceptable;
false positives are the failure this whole module exists to prevent" — is the rule for a
mark a hiker is meant to obey.

## 4. The join: a reviewed table over a closed vocabulary, not a matcher

The survey (§5b) said NYNJTC's "locations are names, not miles" and proposed a name-join
against exported features. **That was true of their prose and understated their payload**,
and the correction is what makes this tractable. NYNJTC tags each alert from its own
taxonomies, returned as term ids on the post:

| taxonomy | terms | populated on the 18 alerts |
|---|---:|---:|
| `trail` | 45 | 10 |
| `park` | 125 | 17 |
| `region` | 13 | 7 |
| `state` | 3 | 7 |

So the left-hand side of the join is **45 trail terms**, not a prose string matched
against the 21,805 network features the build exports. That is the difference between a
table a person can review in one sitting and a guess with a hiker's location attached.

**It is still a reviewed table, and it must be.** `reference/blaze_mapping.json` is the
precedent this repository already set for exactly this shape of problem — an upstream
vocabulary mapped onto ours by a person, row by row, in a file a pull request releases.
A proposed `reference/notice_places.json` does the same:

```
"nynjtc_trail_alerts": {
  "trail:brook-trail": { "features": ["oprhp_trails:…"], "reviewed_by": "…", "note": "…" },
  "trail:appalachian-trail": { "features": [], "note": "ATC's own — see §5" }
}
```

Three properties that are not optional:

- **Keyed on `taxonomy:slug`, never on the slug alone.** Measured 2026-08-27:
  `highlands-trail` is a term in **both** NYNJTC's trail and park vocabularies (ids 31 and
  405). A table keyed on the bare slug would collapse a line and an area into one place.
- **Keyed on the slug, never on the term id.** A WordPress migration can renumber a term
  and keep its slug; it cannot renumber one and keep its meaning.
- **An unmapped term places nothing.** It does not fall back to the park, and it does not
  fall back to a fuzzy match. The notice renders `unplaced` and says so.

**OPRHP's and Mohonk's prose alerts do not get this table.** They have no term vocabulary
to key on, and a reviewed mapping from a sentence to a feature id is a person doing the
placement by hand — which is fine, and is what the `place` union's `org_terms` arm would
carry for them too, keyed on whatever stable identifier their page offers. Neither is in
scope here; both are named so the design is not mistaken for covering them.

## 5. Two organizations, one closure

The ring is where OurHike first has multiple orgs reporting on the same ground, and
notices inherit the problem NYC_SOURCE_SURVEY.md §8 recorded for trail data. Measured
instances, both live on 2026-08-27:

- **Breakneck Ridge** — closed until 2027. On parks.ny.gov as an OPRHP alert, in OPRHP's
  closure-polygon layer, *and* as a NYNJTC trail alert.
- **Lake Awosting Carriage Road** — on parks.ny.gov as an OPRHP alert and as a NYNJTC
  trail alert, and **absent from OPRHP's own GIS closure layer**.
- **The A.T. itself** — NYNJTC's Harriman detour is tagged `trail:appalachian-trail`, the
  same trail ATC publishes notices about.

**The rule: never merge, never silently drop, and let the map collapse rather than the
data.** Each org's notice stays its own row in its own voice, because merging two
organizations' words into one unattributed warning invents a claim neither of them made,
and dropping one means a hiker who follows a link lands on a page that does not match what
they were shown.

What may collapse is the **banner**, which is a scarce surface rather than a record:
`atcAlertsBanner.ts` already shows at most two notices and only the nearest of each lane,
so two orgs warning about one closure should surface once there. The list and the sheet
show both.

**Where two orgs disagree, the land manager's word is the one to lead with** — OPRHP
decides whether an OPRHP trail is closed; NYNJTC reports it and maintains the trail. That
is a preference for display order, deliberately not a filter: NYNJTC carried Lake Awosting
when OPRHP's own layer did not, so a rule that suppressed the maintainer's notice in
favour of the manager's would have shown a hiker nothing.

## 6. Whose voice, and where the name comes from

ATC_TRAIL_UPDATES.md's rule is that an ATC update must be visibly ATC's, and the client
implements it with literal strings — "Appalachian Trail Conservancy", "Read the ATC's
notice", "This is the ATC's notice, not OurHike's" across five render sites, plus the
banner's `` `ATC · ${category}` ``.

**Generalized: the org's name is read from the registry, never written in the client.**
`client/src/lib/stewards.ts` is already a generic per-organization registry driven by
`pipeline/export_sources.py`, carrying `provider`, `name`, `trust`, `licence` and
`attribution` — so a notice's `source_key` resolves to a display name through machinery
that exists. A string in a component is how the app ends up telling a hiker that NYNJTC's
closure is ATC's word.

The disclaimer generalizes with it: *this is <org>'s notice, not OurHike's* is the same
sentence with a variable in it, and it is the one that keeps the app honest about which
claims are its own.

## 7. What ships, and what gates it

Two gates, and they are independent — a source can be perfectly placeable and still not
publishable:

1. **`reaches_hikers` in `sources.json`.** Already the mechanism, already enforced by
   `export_sources.py` refusing to run without it. `nynjtc_trail_alerts` carries `false`.
2. **The licence.** `nynjtc_licence` covers NYNJTC's two public trail extracts "and
   nothing else" and says it must not be read as precedent — so it does not stretch to
   their notices, and that entry says so rather than borrowing it. ATC's own notices ship
   on a facts-and-a-link split that #458 settled by the maintainer's judgement; the same
   call has to be made in NYNJTC's name, ideally by NYNJTC, inside
   [#768](https://github.com/OurHike/OurHike/issues/768).

**The facts-and-a-link split generalizes and should.** A title, a category, a date, a
place and a link are facts about a trail; the paragraphs are the org's writing. That
posture let ATC's notices ship without waiting on a redistribution answer, and it is the
same conversation-shortener for every org after them.

## 8. What the client needs, sized

From a read of the delivery path as it stands. The encouraging half: **most of it is
already generic.**

Works unchanged once a row exists: `publishedConditions.ts`'s fetch/cache/validate
machinery (parameterized over key and field — it needs a payload key added to three
string-literal unions, not a rewrite), `atcAlertsBanner.ts` (needs only `updated_at`),
`atcUpdateStyle.ts`'s paint spec (already takes a `sourceId` argument),
`alertLayerPanel.ts` (no per-source knowledge), and `stewards.ts`.

Needs real work, in rough order of size:

1. **Split the row type** into a publisher-agnostic base plus the optional `place` union,
   and make `mileRange`, the `byMile` sort and `obstructsTheTrail` tolerate a missing mile.
2. **The name join and a second placement path** — `trailSlice`/`trailPointAtMile` take
   miles only, so an `org_terms` notice needs a path onto the `nearby_trails` source,
   which already carries `name` and `source` per feature.
3. **Parameterize the single-tenant pieces** — the id prefix, the map source and layer
   ids, and the localStorage silence key (one shared key would silence NYNJTC when a hiker
   dismisses ATC).
4. **Replace the literal org strings** at the five render sites with values off the row.
5. **Generalize the header line's two-way arbitration** to N sources.

**The cheap first slice, if one is wanted:** the list and the "new alerts" banner need only
`title`, `category`, `updated_at`, `source_url` and a locality string — no map ink and no
header line. A second org could reach a hiker through those alone, in the honest
`unplaced` state, before any of the geometry work happens.

## 9. Open questions, not resolved here

- **Whether a park-only notice should draw anything at all.** It could tint a park
  boundary — OPRHP's park polygons are registered and consumed by nothing — or it could
  stay a list entry. Drawing an area for a notice about one trail inside it is the
  cry-wolf direction; drawing nothing loses a hiker standing in that park. Undecided, and
  it wants the same measurement #964 did for closure polygons: how much of a park is
  actually affected.
- **Whether an org's notice about the A.T. should reach A.T. hikers.** NYNJTC tags the
  Harriman detour `trail:appalachian-trail`, and the A.T. *does* have a mile axis, so it
  could in principle be placed as `at_miles` — by a person, since NYNJTC publishes no
  mile. Attractive and not obviously right: it would put a second org's word on ATC's
  surface.
- **How many notice sources the banner can carry** before it stops being a warning and
  becomes a feed. Two lanes is today's design; the survey found four orgs that publish.
- **Whether `unplaced` notices need a locality filter** so a hiker in Georgia is not shown
  a Catskills advisory. The `locality` field exists for this and nothing reads it yet.
