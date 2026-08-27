# A route thirty organizations hold together

Companion to [NEARBY_TRAILS.md](NEARBY_TRAILS.md) §5 (which hands this lattice here by
name and leaves its own "selected org" resolving against whatever lands here),
[POI_DEDUPLICATION.md](POI_DEDUPLICATION.md) (per-field precedence, whose tier 1 is the
thing this document splits), [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) (per-*source* trust,
a different axis — §7), [ORG_NOTICES.md](ORG_NOTICES.md) §5 (two organizations, one
closure — the measured case §5 below builds on), [CORRIDOR_VIEW.md](CORRIDOR_VIEW.md)
(thirty named stretches, tap to see who maintains one), [SAYING_THANKS.md](SAYING_THANKS.md)
and [VOLUNTEERING.md](VOLUNTEERING.md) (`Club`, `MaintainerAssignment`), and
[../pipeline/NYC_SOURCE_SURVEY.md](../pipeline/NYC_SOURCE_SURVEY.md) §8 (one ground, many
sources, tabulated).

Deliverable of **#780 — Research route ownership: the AT in NY has thirty owners, a
landowner with final say per section, and a maintainer besides**, itself part of
**#768 — v2: trails within reach of NYC — the AT stops being the only trail on the map**.

This document owns one question: **on a route no single organization owns, whose sentence
is on the card, and whose closure stops a hiker?**

The maintainer's ask, 2026-08-18, verbatim, because the example is theirs and carries the
weight of an ATC volunteer describing their own trail:

> The owner of a route is going to be extremely complicated. Can you write up an issue to
> research ownership and to describe how dual ownership should be allowed.
>
> Take for example the Appalachian Trail. In NY, the AT has a superowner, joint ownership
> between 30 orgs (ATC, NYNJTC, State Parks like Harriman & Fahnestock, & the DEC). Each
> section has a landowner who is the final say on what happens in that area. Also on those
> sections is a trail maintainer org responsible for the day to day trail upkeep.

**Scope: v2 research and design. Nothing here is built**, and two thirds of it turns out
not to need building — §4 finds that the model's two load-bearing rules are already shipped
under other names, and the work this document actually asks for is a great deal smaller
than the question sounded.

---

## What this is not, said first because the filenames invite the confusion

[LAND_OWNERSHIP.md](LAND_OWNERSHIP.md) and this document share one word and nothing else.

That document is about **polygons of ground beside the corridor**, drawn from USGS PAD-US,
so that a hiker stepping fifty feet off-trail to camp can see they have left mapped
protected land. This document is about **roles attached to sections of a route** — who owns
the route, who has final say on the ground it crosses, who clears the blowdowns.
Different unit (area against linear section), different question (what is this ground
against who decides here), and a maintainer role that LAND_OWNERSHIP.md does not have at
all.

The postures are opposite in the way that matters most. LAND_OWNERSHIP.md:105-106 is
explicit that it is **not an authority surface**:

> **Not a routing constraint.** It does not affect snapping, wrong-way detection, or
> anything that computes.
> **Not a substitute for signage and blazes.** On the ground, the blazes and the
> landowner's own signs are authoritative. This is orientation, not permission.

§5 below is the exact opposite: a landowner's closure on their section is meant to stop a
hiker. Nothing here licenses LAND_OWNERSHIP.md's polygons to start deciding anything, and
nothing there supplies §5's authority.

**It is also not built.** `pipeline/fetch_land_ownership.py` and
`pipeline/export_land_ownership.py` are named in that design and do not exist — checked
2026-08-27. So PAD-US is cited below as corroboration and as a future source, never as
something this project can read today.

**Three things there are load-bearing here and are cited rather than re-derived:**

- **PAD-US already codes `Joint` as a value of `Mang_Type`** (LAND_OWNERSHIP.md:36). The
  canonical national dataset for protected land needed a joint category, which is external
  corroboration that §3's list-shaped owner is not this project inventing a complication.
- **`Own_Name` and `Mang_Name` are two different fields on the same polygon**
  (LAND_OWNERSHIP.md:38). PAD-US separates owner from manager as a matter of course; so
  does Mohonk Preserve's live layer (§1), independently.
- **`Des_Tp = "National Scenic or Historic Trail"` combined with `Own_Name = "National Park
  Service"` is how AT-owned corridor land identifies itself** (LAND_OWNERSHIP.md:42) — the
  only route this repository has written down for learning who owns the ground under the
  A.T., and it runs through a source nothing fetches yet.

**And one rule is inherited wholesale rather than restated: absence is absence**
(LAND_OWNERSHIP.md:44-54). Applied per role: a section with **no recorded maintainer is
unattributed, never unmaintained**; a section with **no recorded landowner is unrecorded,
never unowned and never "nobody's say"**. This is not aspiration — it is shipped
behaviour, in `pipeline/export_club_sections.py:237-238`:

> Published, not omitted. 41 miles the fresh source cannot name reads as "not recorded";
> leaving it out would read as "no trail here".

---

## 1. The lattice is half in the data — every claim checked, and four of the five come back changed

The body of **#780 — Research route ownership: the AT in NY has thirty owners, a landowner
with final say per section, and a maintainer besides** asserts five per-source attribute
facts under the heading "The lattice is already half in the data (measured 2026-08-18)".
They are the evidence the whole design stands on, so each was re-read against the survey
text and `pipeline/sources.json` on **2026-08-27**. One checks out verbatim, three check out
with a caveat that changes what can be built on them, and one is **partly wrong**.

| # | #780's claim | verdict |
|---|---|---|
| 1 | ATC's centerline carries the maintainer per segment (`Trail_Club`/`Acronym`) | **verified** |
| 2 | NYNJTC's public Long Path layer carries a per-segment `Maintainer` | **verified, and it is a constant** |
| 3 | NJ's statewide compilation carries `MANAGING_AGENCY`, 166 distinct values | **verified in the survey; the source is not registered** |
| 4 | OPRHP's layer carries `Unit`/`Facility` | **verified, and neither field is what it sounds like** |
| 5 | DEC's layers carry `UNIT`/`REGION`/`OFFICE` | **`UNIT` yes; `REGION` and `OFFICE` not found anywhere** |

### 1 — ATC's centerline, verified

`pipeline/SOURCE_SURVEY.md:283-284`, measured 2026-08-13:

> **The centerline already carries the club.** `ANST_Centerline` has `Trail_Club`,
> `Acronym` and `Reg_Acro` on **every one of its 3,025 features**, and so does
> `at_treadway`.

This is the **maintainer** role and only that role. `pipeline/lib/club_sections.py:1`
names its own subject "Which club maintains which stretch of trail". Nothing in ATC's
estate carries the landowner of a section at all — the open questions below return to that,
because it leaves the role with *final say* unsourced on the flagship route.

Two hygiene facts travel with it and both are load-bearing for §8. First, 47 features carry
a digit string where an acronym belongs — 41.4 miles, 1.90% of the trail — and those miles
publish as unattributed rather than being backfilled from the two-year-old polygon layer
(`pipeline/lib/club_sections.py:31-36`, measured 2026-08-13). Second, the join key,
`pipeline/lib/club_sections.py:37-40`:

> **Two clubs are misspelt** in `Trail_Club` and correct in `Acronym`: "Potomac Appalachain
> Trail Club" (PATC) and "New York - New Jersey Trail Conference" (NYNJTC, spacing). Every
> acronym maps to exactly one spelling, which is what makes the acronym a safe key and the
> name an unsafe one.

Read that twice, because it is the whole of §8c: **the two organizations ATC misspells are
a maintaining club and the other route steward in the ring.** A lattice keyed on
organization names would key two of its most important rows on a typo.

### 2 — NYNJTC's Long Path, verified, and it is a constant

`sources.json`'s `nynjtc_long_path` notes, measured live **2026-08-24**:

> Fields Trail_Name/Blaze/Maintainer/Mileage/Source/Comments/LP_Section/GuideURL; all 43
> rows read Trail_Name 'Long Path', Maintainer 'NYNJTC' and Source 'NYNJTC'.

That is the registry's read and nothing else. `pipeline/NYC_SOURCE_SURVEY.md:203-204` is the
corroborating one, six days earlier, and it is thinner than the quote above: on 2026-08-18
it found the same **43 segments** and the same six-field core —
`Trail_Name`/`Blaze`/`Maintainer`/`Mileage`/`LP_Section`/`GuideURL` — naming neither
`Source` nor `Comments`, and saying nothing at all about what the 43 rows contain. The
constancy below rests on the 2026-08-24 measurement alone.

So the column exists and is real, and **its information content today is zero**: 43 of 43
rows say the publisher's own name. That is not a defect in NYNJTC's data — it is what a
single-organization extract of a single route looks like — but a design that reads
"NYNJTC publishes a per-segment maintainer" as evidence that maintainers vary per segment
in their data would be reading a constant as a variable. Measured, and the weaker sentence
is the true one.

### 3 — NJ's `MANAGING_AGENCY`, verified as a survey finding, unregistered as a source

`pipeline/NYC_SOURCE_SURVEY.md:252-254`:

> **`MANAGING_AGENCY`, 166 distinct values**: counties (Morris, Atlantic, Burlington…),
> boroughs, land trusts, even corporate campuses. **This one layer is the answer to the
> NJ-county question** — per-segment agency attribution instead of eight county portals.

Read 2026-08-18 on the NJ Geospatial Forum's "Statewide Trails in New Jersey", 13,296
segments. **It is not in `sources.json`** — checked 2026-08-27, the registry holds no NJ
entry at all — so unlike every other row in this table, nothing in this project has fetched
it and no per-value figure here has been re-measured since the survey. The survey also
records the layer's own description calling it "a first iteration and in no way complete".

It is still the most interesting of the five, because 166 values in one column is the only
evidence any of these sources gives that a role really does vary section by section at
scale. It is also the one whose terms are furthest along — the item carries the NJDEP Data
Distribution Agreement, which the survey flags **NEEDS REVIEW** before registration.

### 4 — OPRHP's `Unit`/`Facility`, verified, and neither field is what its name suggests

`pipeline/NYC_SOURCE_SURVEY.md:95` and `:101-103`:

> `Unit` is OPRHP's **eleven regions** — `Palisades` and `Taconic` are the ring's two […]
> all `Facility: Hudson Highlands State Park Preserve`. NYNJTC *maintains* most of those
> trails but publishes no data for them.

`Unit` is an **administrative region of the agency**, not a parcel and not a landowner
name; `sources.json`'s `oprhp_trails` entry adds that it is "how OPRHP's own stewards talk
about where a trail is". `Facility` is the park. Neither says who holds title. What they
do say — and this is what makes them the landowner frame in practice — is *which agency's
desk a decision about this trail lands on*, which is what a hiker needs and is not the same
claim as ownership. The doc should say the weaker thing: OPRHP's fields identify the
**administering agency and its unit**, and the project infers final-say-on-this-ground from
that, one inference deep, marked as such.

### 5 — DEC's `UNIT`/`REGION`/`OFFICE` — half of it could not be verified

`pipeline/NYC_SOURCE_SURVEY.md:113-115` and `sources.json`'s `dec_hiking_trails` notes give
**overlapping but not identical** field lists, and the difference is worth carrying rather
than flattening. The survey's, on the 5,277 segments it counted:

> fields `UNIT`/`FACILITY`/`NAME`, per-use flags (`FOOT`/`HORSE`/`BIKE`/`XC`/`SNOWMB`/
> `ATV`/`MOTORV`), `MILES`, `ACCESSIBLE`, `DESCRIP` — and **`MARKER`**, DEC's word for the
> blaze.

The registry's, counted live 2026-08-25 on **5,286** rows — nine more than the survey found,
which the entry itself reads as the layer moving rather than either count being wrong — is
`UNIT`/`FACILITY`/`NAME`/`ASSET`/`MILES`/`DESCRIP`/`PUBLICUSE`/`UPDATED`, plus the
`CORRIDOR USE` matrix
(`FOOT`/`HORSE`/`BIKE`/`XC`/`SNOWMB`/`ATV`/`MOTORV`/`ADMIN`/`ACCESSIBLE`/`MAPPWD`), plus
`MARKER`. Five of those fields are in no version of the survey's list — `ASSET`,
`PUBLICUSE`, `UPDATED`, `ADMIN`, `MAPPWD` — and **neither carries `REGION` or `OFFICE`**.
That the two reads disagree about five other columns is what makes their agreement here
worth something: two independent looks at the layer, a week apart, and the two fields claim
5 rests on are in neither.

`UNIT` is there. **`REGION` and `OFFICE` appear nowhere** — not in
`pipeline/NYC_SOURCE_SURVEY.md`, not in `pipeline/SOURCE_SURVEY.md`, not in the registered
`dec_hiking_trails` field list (grepped 2026-08-27; the only `Office` hits in `sources.json`
are inside OPRHP's full legal name). Either they were read on a sibling DEC layer the
survey does not name, or the claim is wrong. **Nothing here should be designed on them
until somebody probes the live service and says which.**

And DEC's `UNIT` is the dirtiest of the five —
`pipeline/NYC_SOURCE_SURVEY.md:130-133` warns that it "mixes preserve codes (`CFP`, `AFP`)
with hundreds of per-county state-forest codes […] and real dirt — `-99`, blank,
`Sullivan06`, an `Ostego` misspelling, trailing spaces."

### The find that was not in the issue, and is the best evidence in this document

**Mohonk Preserve's shipped trail layer carries `Owner` and `Manager` as separate
per-segment fields, and on six segments they disagree.** From `sources.json`'s
`mohonk_trails` notes, measured live **2026-08-25** and independently recorded in
**#992 — Register Mohonk Preserve's Trails and Carriage Roads: the state listing died,
their own ArcGIS layer didn't**:

> The layer is already a filtered VIEW — its own definitionQuery is `(General_Classification
> = 'Carriage Road' OR General_Classification = 'Trail') AND (Manager = 'Mohonk Preserve')`
> — so this is Mohonk's own curated public extract, not their full internal dataset; 298 of
> 304 rows carry Owner 'Mohonk Preserve', the other 6 ('Marakill Woods North/South') carry
> Owner 'NYS OPRHP/PIPC' with Manager still 'Mohonk Preserve'.

Three things fall out of one measurement, and every one of them is a claim §2 would
otherwise have had to argue:

- **Owner and manager are separate roles that come apart per section**, in live data this
  project ships today (`reaches_hikers: true` since 2026-08-25), on 6 of 304 segments —
  1.97%. **@unvalidated** — that those 6 rows are a genuine owner/manager split rather than
  an upstream data-entry artifact is unchecked; it would be settled by reading the Marakill
  Woods parcels against PAD-US's `Own_Name`, or by asking Mohonk.
- **The owner value is already joint, written as `NYS OPRHP/PIPC`** — two organizations in
  one string, exactly the "superowner" shape, arriving from a source that never read **#780 —
  Research route ownership: the AT in NY has thirty owners, a landowner with final say per
  section, and a maintainer besides**. It arrives as a *string* rather than as a list, which
  is the modelling failure §3 exists
  to avoid inheriting: nothing downstream can tell `NYS OPRHP/PIPC` from a park called
  "NYS OPRHP/PIPC" without a table saying so.
- **A publisher's own definition of its dataset can be a role filter.** Mohonk publishes
  what it *manages*, irrespective of who owns it. Read against §2, that means a source's
  extent is itself a role assertion, and reading its rows as ownership claims would be
  wrong on 6 of them.

Nothing consumes `Owner` or `Manager` today: `export_nearby_trails.py` reads `Blaze`,
`Name` and the use/status flags, and the two role columns go nowhere. **That is the
cheapest experiment in this document** — see §10.

---

## 2. The model: a role assertion is a claim by one source about one section

Three roles, per **section**, never per route:

| role | the question it answers | who says so today |
|---|---|---|
| `route_owner` | whose route is this, and whose line is the line | `sources.json`'s `owns_route_names` (shipped) |
| `landowner` | who has final say on what happens on this ground | OPRHP `Unit`/`Facility`, Mohonk `Owner`, PAD-US (unbuilt) |
| `maintainer` | who does the day-to-day upkeep | ATC `Trail_Club`/`Acronym`, NYNJTC `Maintainer`, Mohonk `Manager`, backend `MaintainerAssignment` |

The record:

```
RoleAssertion
  trail_id                which route's frame this section is expressed in
  leg      { start_mile, end_mile, start_lat/lon, end_lat/lon }
  role     route_owner | landowner | maintainer
  orgs     [ "org:atc", "org:nynjtc", … ]      ALWAYS a list — see below
  source_key                                    who says so: a sources.json key
  asserted_on                                   the SOURCE's own edit date, not our fetch
  note                                          the source's own words, where it has any
```

Four decisions in that shape, each with an alternative that was live:

**`orgs` is a list on every role, not a scalar with a `joint` flag.** The alternative —
`org` plus `joint: true` — was rejected because it makes the flagship route the exceptional
case, and every consumer has to remember to check the flag before trusting the scalar. The
one that forgets renders "the A.T. is maintained by ATC" and is wrong in a way nobody sees.
A list of one is a list; a list of thirty is the same code path. PAD-US reached the same
conclusion from the other end and stopped half way — it has a `Joint` value in `Mang_Type`
(LAND_OWNERSHIP.md:36) and still one `Mang_Name`, so it can say *that* something is jointly
managed and not *by whom*. Whether PAD-US carries the parties anywhere else is
**@unvalidated** — it would be settled by probing `Manager_Name_PADUS` for a polygon whose
`Mang_Type` is `Joint`, which is a ten-minute query once `fetch_land_ownership.py` exists.

**A section is a leg — `(trail_id, mile range)` anchored by captured lat/lon** — and this
is not invention, it is the third appearance of a shape this repository has already
converged on twice. `backend/app/models/closure.py:75-118` is the argument in full, and it
is about exactly this failure:

> A mile is a reading against one particular measurement of the centerline, and the ATC
> re-measures. The same physical stretch gets a slightly different number, so a closure
> authored against this year's measurement quietly refers to a different stretch under next
> year's […] So the geometry is the anchor and the mile becomes a per-release PROJECTION of
> it.

[POI_IDENTITY.md](POI_IDENTITY.md):388 is the general statement ("Miles are a projection,
not an anchor"), and [CORRIDOR_VIEW.md](CORRIDOR_VIEW.md)'s `Highlight` is the same shape
arrived at for a different reason — "the mile range moves down a level into an ordered list
of legs, since a mile only means something relative to one trail". A role assertion is a
leg for both reasons at once.

The alternative — **a set of the asserting source's own feature ids** — is more precise and
was rejected on POI_IDENTITY.md's evidence: upstream re-keys, and a section defined by
`GlobalID`s silently empties when ATC deletes and re-creates a feature. The feature ids are
worth *recording* as provenance; they are the wrong thing to define the section by.

**Derived assertions are a published artifact; authored assertions stay in the backend.**
This is the split SOURCE_REGISTRY.md:58-59 draws in a table — the registration in Postgres
because an org needs a form rather than a pull request, the source the build reads in
`sources.json` because the build runs from a checkout — pointed at a different noun, and
CORRIDOR_VIEW.md already stated the precedence for the one case that exists:

> The backend already holds `Club` and `MaintainerAssignment` for the *authoritative*
> answer used when a thanks is resolved […] this is the map's copy for drawing and for
> working offline, and where the two disagree the backend is right.

So the pipeline derives role assertions from source columns and ships them with the map;
the backend keeps the maintainer assignment a club can actually edit. **Two stores, one
authority, and the tie-break already written down.** Building a second authority is the
thing to refuse.

**Absence is per role and per section, and it is never a default.** No maintainer means
unattributed. No landowner means unrecorded. No route owner means the route has no
publisher of record — which for a route drawn from one source is the ordinary case, not a
gap. There is no rule anywhere in this design that fills one role from another.

---

## 3. Joint ownership, and the thing "superowner" actually is

The maintainer's word for what holds the A.T. is *superowner*: "joint ownership between 30
orgs (ATC, NYNJTC, State Parks like Harriman & Fahnestock, & the DEC)."

The model represents that directly — `role: route_owner`, `orgs` with thirty entries — and
the honest thing to add is that **this document cannot tell you what those thirty
organizations jointly hold.** Nothing in this repository establishes the legal instrument.
What the repository does establish, and it is worth separating carefully:

- **ATC publishes the line.** `export_nearby_trails.py:277-289`'s `owned_route_names()`
  reads `owns_route_names` off the registry, and `centerline` — an ATC layer — is where
  "Appalachian Trail" resolves.
- **NPS is the owner of record for corridor land** in the only query this repository has
  written down for the question (LAND_OWNERSHIP.md:42) — and that query runs against a
  source nothing fetches. **@unvalidated**: what fraction of the A.T. corridor PAD-US
  actually attributes to NPS is unmeasured here, and would be settled by the corridor clip
  LAND_OWNERSHIP.md §1 specifies and nobody has run.
- **ATC also holds ground of its own** — §9.
- **Thirty clubs maintain it**, and that one is measured to the mile (§1).

So `route_owner` in this model is a **claim about who the route belongs to**, and the
project's evidence for the A.T.'s membership list is the maintainer's own statement, dated
2026-08-18, recorded above. That is a legitimate grade of evidence — a maintainer's
decision is one of the three CLAUDE.md names — and it must be carried as that rather than
laundered into a measurement. If the app ever prints the thirty names, they come from a
reviewed file somebody signed, in `reference/`'s posture, not from a matcher.

**The one thing joint ownership must not become is a committee in the render path.** Thirty
organizations do not co-author a card. Which is §4.

---

## 4. "Selected org gets precedent" — the hypothesis, and where it breaks

The rule this document was asked to compose with, from the maintainer on 2026-08-18,
recorded verbatim on **#772 — Design the map when trails cross: one chosen centerline,
every other trail visible, and safety pins that ignore the choice**:

> POI's should be attached to the route chosen. POI's need to be deduped and shared across
> the orgs. But the current selected org should always get precedent for the information
> shown.

And the starting hypothesis on **#780 — Research route ownership: the AT in NY has thirty
owners, a landowner with final say per section, and a maintainer besides**, offered
explicitly as a thing to argue *with* rather than *from*: **route owner for identity and
centerline, landowner for rules and closures on their ground, maintainer for conditions,
thanks and reports.**

It survives, amended in three places. Two of its three limbs turn out to be shipped code
rather than proposals, and the amendments are where the joint case actually bites.

### 4a. Route owner for identity and centerline — shipped, and the word "owner" is wrong

This is not a proposal. `pipeline/export_nearby_trails.py:92-96` states it as one of the
export's three filters —

> THE ROUTE OWNER'S LINE WINS - features/NEARBY_TRAILS.md §5. A source that
> `owns_route_names` in the registry supplies that route's geometry, and another
> organization's copy of it is suppressed.

— on the maintainer's decision of 2026-08-18, taken with the measurements from
**#771 — Spike: Harriman's crossing trails next to the AT — find what a trail network
breaks that a linear trail never could** in front of them: OPRHP's copy of the A.T. agrees
with ATC's line at 1.8 m median and diverges past 150 m on 14% of the in-park length,
peaking at 1.24 km. An old alignment, rendered, would be a wrong map.

**The amendment: what `owns_route_names` holds is not ownership, it is publication.** On a
route thirty organizations own together, no single one of them can be "the owner" in the
registry, and the mechanism does not need one to be — it needs *one source of record for
this route's geometry*. ATC is that for the A.T. because ATC publishes the centerline, not
because ATC owns the trail more than the other twenty-nine. NYNJTC is that for the Long
Path on the same footing.

So the key should be read as **publisher of record**, a job the joint owners delegate, and
the three-role model should not try to derive it from `route_owner`. The practical
consequence is nil in code and large in what the code means: `owns_route_names` stays
exactly where it is, per source, and stops looking like a field that will need thirty
entries one day.

The restraint already in that function is worth keeping in view, because it is the same
restraint the whole lattice needs (`export_nearby_trails.py:292-305`): the match is on the
source's own `Name` field and nothing else, because 26 OPRHP segments carry
`Alt_Name: Appalachian Trail` while their own `Name` is the 1777 East Trail or the
Ramapo-Dunderberg — *"Those are not copies of the A.T. They are distinct trails the A.T.
runs along for a stretch"*. A lattice that inferred roles from alternate names would delete
real trails.

### 4b. Landowner for rules and closures — the amendment is the whole of §5

Short version, argued there: **a landowner's assertion outranks a contrary assertion on
their ground. A landowner's *silence* outranks nothing.** The hypothesis as written invites
reading the landowner as a filter, and there is a measured case where that would have shown
a hiker nothing.

### 4c. Maintainer for conditions, thanks and reports — holds, and half of it is wired

Thanks already resolve this way. SAYING_THANKS.md's resolution takes the thanks' location
and its **authored** time and looks up the `MaintainerAssignment` records covering that
point at that moment — and it already returns "zero or more, never exactly one", which is
the joint case handled correctly a year before anybody called it that:

> **Resolution returns zero or more, never exactly one.** Stretches overlap, hand off, and
> go unassigned. Zero is a normal answer […] Two is also normal, and both hear about it.

Reports are the half that is not wired, and FIELD_NOTES.md already names the limit rather
than leaving it to be found — a correction routes upstream to the **source steward**, not
to the section's maintainer, because:

> `maintainer_assignments` is not in the conditions reader role's grant, so the nightly bake
> cannot see who covers a mile; a covering maintainer's lone report reaches a phone through
> the live read and never reaches the routing.

With a lattice, "the steward" becomes "the right role", and the three destinations are
genuinely different desks: **geometry corrections to the publisher of record, ground rules
and closures to the landowner, conditions and blowdowns to the maintainer.** That is the
useful generalization of FIELD_NOTES.md §"And it files upstream" and it is blocked on a
database grant, not on this design.

### 4d. The amendment the hypothesis is missing: the hiker never selects an org

A hiker selects a **route**. The rule on **#772 — Design the map when trails cross: one
chosen centerline, every other trail visible, and safety pins that ignore the choice** says
"the current selected org", and on a single-owner route those are the same thing. On the
A.T. they are not, and "the selected org" has no referent at all — thirty organizations are
not a display voice.

**So the resolution runs: selected route → publisher of record for identity fields →
section roles for everything else.** Concretely, a hiker walking the A.T. through Harriman,
tapping a spring both ATC and OPRHP know:

| field | whose | why |
|---|---|---|
| the line under their feet | ATC | publisher of record for this route (4a, shipped) |
| the spring's name and position | POI_DEDUPLICATION.md's per-field tier rule, unchanged | this document does not reopen #772's POI decisions |
| a rule about camping there | OPRHP | landowner of the section |
| whether it is closed | OPRHP, **and NYNJTC, and ATC — all of them** | §5 |
| how the water looked in June | whoever observed it, newest first | FIELD_NOTES.md owns the condition axis |
| who to thank | the club holding that section | 4c |

The row that reads "all of them" is the one that matters, and it is the only row where the
lattice is allowed to *add* voices rather than choose between them.

### The guard rail on the whole thing

Already decided on **#772 — Design the map when trails cross: one chosen centerline, every
other trail visible, and safety pins that ignore the choice** and inherited here without
amendment: **a safety-relevant fact only one org carries never loses to precedence. Safety
completeness outranks display preference.** Every rule in this section is a rule about
*which of two answers to show first*, and none of them may be implemented as a rule about
which answer to keep.

---

## 5. Closure authority — a safety path, in those words

This is one of CLAUDE.md's four ways this app can hurt somebody: **in front of something
dangerous.** A closure a hiker is not shown is that failure directly, and the rule below is
written to fail in the survivable direction.

### The measured case, and why it decides the design

[ORG_NOTICES.md](ORG_NOTICES.md):170-173 is the home of the measured pair — Breakneck Ridge
and Lake Awosting Carriage Road, both live on **2026-08-27** — and both are read there
rather than copied here. Only one of them does any work in this document:

- **Lake Awosting Carriage Road** — on parks.ny.gov as an OPRHP alert and as a NYNJTC trail
  alert, and **absent from OPRHP's own GIS closure layer**.

That absence is the argument. OPRHP is the landowner and the closing authority at Lake
Awosting, and OPRHP's own machine-readable closure layer does not carry the closure. A rule
that read "prefer the land manager" as a **filter** — take OPRHP's closure set, discard the
maintainer's — would have shown a hiker walking toward a closed carriage road **nothing at
all**. NYNJTC's alert was the only record of it in any layer this project ingests — OPRHP's
own alert lives on parks.ny.gov, which nothing here reads (`pipeline/sources.json` registers
`oprhp_trails`, `oprhp_trail_closures`, `oprhp_facilities`, `oprhp_park_polygons` and no
alert feed).

ORG_NOTICES.md §5 already states the rule this design inherits — *"never merge, never
silently drop, and let the map collapse rather than the data"*, with the land manager's word
leading as **display order, deliberately not a filter** — and this section adds one thing to
it rather than restating it.

### The rule, stated for roles

**A landowner's closure on their section outranks every other source's silence. A
landowner's silence outranks nothing.**

That is a deliberately asymmetric sentence and both halves are needed:

- **Outranks silence.** If OPRHP says a section of their ground is closed and no other
  source mentions it, that closure ships, drawn, with no corroboration required and no
  moderation queue between it and the hiker. It does not matter that the route's publisher
  of record has said nothing; ATC does not know what OPRHP has closed in Harriman, and
  waiting for ATC to agree is waiting for a message nobody is sending.
- **Silence outranks nothing.** If NYNJTC says a section is closed and OPRHP's layer does
  not, the closure still ships, in NYNJTC's voice, attributed to NYNJTC. Lake Awosting is
  the case, measured. The landowner's absence of an assertion is not a denial, and a design
  that treats it as one has made the land manager's data-publishing cadence into a safety
  guarantee it never offered.

Both halves are the same instinct the rest of the project already runs on: **miss rather
than cry wolf** governs a mark a hiker is asked to *obey*, and a closure is the one mark
where the cheap error is showing one too many. A hiker who walks up to an open trail
labelled closed loses an hour. A hiker who walks into a closed one because two organizations
disagreed in a database loses more.

**What is never permitted is synthesis.** Two organizations' closures on one stretch stay
two rows in two voices. Merging them produces a warning neither organization issued — and a
hiker who follows the link lands on a page that does not say what they were shown, which is
how a safety surface stops being believed.

### What is built, and the shape it took

**#964 — NYS Parks closes areas, not trail segments, and the closure model has nowhere to
put one** is this rule already meeting reality, and it went the way §2 predicts: the
landowner's closure is *area-shaped*, and the app's closure model was route-shaped.

Measured on the live layer 2026-08-24, all four features: polygons over ground, **no dates
at all** — "Closed Until 2027" exists only inside the prose of a field called `Name` — and
two of the four never touch the A.T. The A.T. closure model is
`start_mile_marker`/`end_mile_marker` on one trail, so forcing them in would — in that
issue's words — "publish two negligible A.T. closures and silently drop everything that
matters."

The fix, shipped: `export_nearby_trails.py:546`'s `apply_area_closures()` intersects the
polygons with the exported network lines and marks what falls inside — 99 exported features
touch the 4 closed areas, **66 lying wholly inside and 33 only partly**, and the 33 are
split at the boundary (`export_nearby_trails.py:551-553`, measured 2026-08-24). Split rather
than closed whole, because closing one of those 33 whole would have drawn the barred band
along the *entire* Ramapo-Dunderberg on the strength of the 16.7% of its length that is
actually inside a closure, which is the cry-wolf failure on a mark a hiker is meant to obey.

**Three things that case establishes for this document**, and they are more useful than
anything the abstract rule could have asserted:

1. **The landowner's authoritative closure carries *less* structure than a hiker's report
   of one** — no dates, prose reason, a field called `Name` that is not a name. Authority
   and data quality are unrelated axes, and a pipeline that requires a landowner's closure
   to parse as cleanly as a form submission will drop the most authoritative closures it
   receives.
2. **A role assertion and a closure are the same shape of problem** — one organization
   making a claim about a piece of ground that has to be projected onto somebody else's
   route geometry to be shown. `apply_area_closures()` is the working precedent for how a
   landowner-frame claim lands on a route-frame line, and §2's leg is the same projection
   done at build time.
3. **It must not fail a publish when the layer is empty.** `may_be_empty: true` is already
   set on `oprhp_trail_closures` because zero closures in a good week is a fact about the
   parks, not a broken fetch. Any per-role artifact needs the same property for the same
   reason: a landowner asserting nothing this week is normal.

### The backend gap this exposes, which is a safety finding nobody asked for

It is on no list — **#780 — Research route ownership: the AT in NY has thirty owners, a
landowner with final say per section, and a maintainer besides** does not name it, and it
turned up on the way to something else. `backend/app/models/closure.py` models a
**community-reported** closure and has no way to record an authoritative one. Read straight
off the columns:

- `reported_by` is `nullable=False` and a foreign key to `profiles.id` (line 65). Every
  closure in this table was filed by a person with an account. There is no
  `issued_by_org`, no role, no authority field of any kind.
- `moderation_status` defaults to `submitted`, and the module docstring is explicit that
  "public queries filter on `moderation_status == verified`" (lines 15-23, 157-164).

Put those together: **if OPRHP's "Closed Until 2027" ever entered this table, it would sit
invisible in a moderation queue until a volunteer moderator verified the landowner.** That
is not a live defect today — OPRHP's closures reach hikers through the pipeline
(`apply_area_closures()`), never through this table — but it is a loaded gun pointed at the
obvious next step, which is exactly the maintainer's instinct on **#964 — NYS Parks closes
areas, not trail segments, and the closure model has nowhere to put one**: *"I think we
should have the oprhp_trail_closures added to the closures just like the atc's."*

Saying so here rather than fixing it, per CLAUDE.md: **where a hiker's safety is at stake,
name the gap even when fixing it is out of scope.** The fix is small — an org-issued closure
needs an authority column and a path that skips the community moderation queue, the way
SAYING_THANKS.md's thanks already skips it for its own reasons — and it should be its own
issue rather than a paragraph in a design doc.

---

## 6. Provenance when the roles disagree

[NEARBY_TRAILS.md](NEARBY_TRAILS.md) §6 owns the display voice and is half built: OPRHP's
licence makes attribution a condition, so `client/src/map/credits.ts:182` names all four
stewards whose lines are drawn — OPRHP, NYNJTC, Mohonk Preserve and NYS DEC, read
2026-08-27 — and the per-trail line in the tap sheet is still missing (NEARBY_TRAILS.md:258
names that gap as its own). NEARBY_TRAILS.md:253 still says "both stewards"; it was written
2026-08-24, before Mohonk and DEC were registered, and it is that line that is stale rather
than the code. This section adds only what changes when a section has three organizations on
it rather than one.

**Name the role, not just the organization.** "NYS OPRHP" on a card answers a question the
hiker did not ask. *"Closed by NYS OPRHP, who manage this ground"* and *"Maintained by the
NY-NJ Trail Conference"* are different sentences about different authority, and printing
both organizations without their roles produces the impression of a contradiction where
there is none.

**Read the name from the registry, never from the client.** ORG_NOTICES.md §6 already
generalized this — `client/src/lib/stewards.ts` is driven by `pipeline/export_sources.py`
and carries `provider`, `name`, `trust`, `licence` and `attribution` — and the lattice makes
the point sharper, because there are now three places in one card that could hardcode an
organization's name and be wrong about which one.

**Where two roles genuinely contradict, both sentences print, in role order, attributed.**
Never one merged sentence. This is ORG_NOTICES.md §5's "never merge" applied to roles
instead of to notices, and it costs a line of card space to avoid inventing a claim nobody
made.

**Never let a display outrun its source, per role.** OPRHP's own licence text disclaims
accuracy; ATC's centerline club attribution is 1.90% unattributable, measured 2026-08-13;
NYNJTC's `Maintainer` column is a constant. Those are three different confidences on one card, and
the honest render distinguishes them or says less. This is also the reason a role assertion
carries `asserted_on` as **the source's own edit date** and not our fetch date — the fetch
date says when we asked, which is a fact about us.

---

## 7. Per-source trust and per-section roles are two axes, and the doc must not fuse them

SOURCE_REGISTRY.md's three tiers are a property of a **source**:

> **`authoritative`** — a verified steward for that geography […] **`community`** — a real,
> identified organization publishing data about ground it doesn't manage […]
> **`unverified`** — registered, probed, not yet vouched for. **Does not ship to hikers.**

A role is a property of a **section**. They cross, and the crossing is not decorative:

|  | `authoritative` | `community` |
|---|---|---|
| **asserting about its own role** | ATC on which club maintains mile 1,043; OPRHP on a closure in Harriman | — |
| **asserting about somebody else's role** | **NYNJTC's alert about an OPRHP closure** — Lake Awosting, §5 | an OSM way tagged with an operator |

The top-right cell is the one that matters and is the reason the axes must stay separate.
NYNJTC is `trust: authoritative` in the registry, and at Lake Awosting they are
authoritative about a closure on ground they do not own. **A source's trust tier says how
much to believe what it publishes; a role says whose decision it is describing.** A design
that collapsed them would have to either demote NYNJTC (losing the only record of that
closure) or promote NYNJTC's word into OPRHP's authority (inventing a claim OPRHP did not
make). Both are wrong and the second is worse.

The concrete request this puts on POI_DEDUPLICATION.md, whose model this document does not
otherwise touch: **its tier 1 is "land manager or trail steward"**, which is precisely the
two roles **#780 — Research route ownership: the AT in NY has thirty owners, a landowner
with final say per section, and a maintainer besides** asks to be separated, sharing a rank.
That is fine for the job that table does today — deciding which of two rows wins a field —
and it will not be fine the moment a land manager and a route steward disagree about a
field, because the tier cannot break the tie. Flagged rather than redesigned here:
POI_DEDUPLICATION.md owns its own hierarchy, and this document's contribution is the
vocabulary that lets it split tier 1 when it needs to.

`pipeline/NYC_SOURCE_SURVEY.md:306-308` reached the same conclusion from the outreach side
and said it in one sentence:

> The steward-versus-owner distinction matters for outreach too: OPRHP's answer covers the
> *data*; NYNJTC's covers the *stewardship* and the network — one does not substitute for
> the other.

---

## 8. What the backend needs to gain

Four gaps, read off the models on 2026-08-27. The first is the largest and it is fatal to
the A.T. case as stated.

### 8a. A club cannot hold a section without a named individual

`backend/app/models/maintainer_assignment.py:43`:

```python
maintainer_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)
```

Not nullable. **Every assignment must name a person with an OurHike account.** And
`backend/app/models/club.py:5-7` says the opposite is the norm — `Club` exists "because
SAYING_THANKS.md needs somewhere for a thanks to go when the hiker knows the club but not
the person - **which is the common case**."

So the thirty A.T. clubs, which are the entire subject of the example on **#780 — Research
route ownership: the AT in NY has thirty owners, a landowner with final say per section, and
a maintainer besides** and of CORRIDOR_VIEW.md's shipped corridor view, **cannot be stored
as holding their own sections.** The table can say "Dana holds mile 1,043 for PATC" and
cannot say "PATC holds mile 1,043."

The fix is one nullable, and it has a consequence worth stating with it: with
`maintainer_id` nullable, `publicly_creditable` becomes a field about a row that may have
no individual to protect, and SAYING_THANKS.md's opt-in default must keep meaning the same
thing — a club-held assignment is club-attributed by construction, which is the default
that document already wants.

### 8b. No `trail_id`, and the miles are the A.T.'s

`start_mile`/`end_mile` are documented in the same file as "Inclusive range along the trail
centerline, in miles from the southern terminus - the same origin the pipeline's half-mile
markers use." One trail, singular, unnamed because it did not need naming when there was
one. NEARBY_TRAILS.md is blunt that this does not survive contact with a network —
"switching trails swaps the mile frame" — and POI_IDENTITY.md:388 is blunt that the mile
does not survive contact with a re-measure.

**The precedent for the fix is in this same codebase and is already argued**:
`backend/app/models/closure.py:75-118` stores `start_lat`/`start_lon`/`end_lat`/`end_lon`
alongside the miles, captured at write time, with the miles kept exactly as they are because
"they are what every existing row and every existing client has, and they remain correct
against the release they were authored on." `MaintainerAssignment` wants the same three
things closures got: a `trail_id`, captured endpoint geometry, and no migration of the
existing miles.

That is also §2's leg, which means the backend row and the published artifact end up the
same shape without either being bent to fit the other.

### 8c. `Club` has no acronym, and the acronym is the only safe join key

`club.py` is `id`, `name`, `region` — "deliberately minimal", and correctly so for what it
was built for. But the key the pipeline joins on does not exist on it, and §1 has the
measurement: ATC's centerline **misspells two club names and spells every acronym
correctly**, and one of the two misspelt is NYNJTC. `pipeline/lib/club_sections.py:39-40`:

> Every acronym maps to exactly one spelling, which is what makes the acronym a safe key and
> the name an unsafe one.

Add `acronym`, unique. Without it, joining the published `club_sections` artifact to the
backend's `clubs` rows is a name match against a source with known typos in it, which is the
kind of join that works in testing and drops PATC in production.

### 8d. The fourth: the model can express exactly one role, and only for a club

This is the one the list on **#780 — Research route ownership: the AT in NY has thirty
owners, a landowner with final say per section, and a maintainer besides** does not name,
and it is structural rather than a missing column. `MaintainerAssignment` has no `role` —
the role is the table's name — and
`club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)`
(`backend/app/models/maintainer_assignment.py:44`) means the holder must be a row in
`clubs`.

Both halves have to give:

- **There is no home for a landowner or a route owner.** The lattice's other two roles
  cannot be written down at all. Either the table gains a `role` and becomes
  `SectionRoleAssignment`, or the landowner lives only in the pipeline artifact and the
  backend can never hold an authored one — which forecloses a club admin ever correcting a
  landowner attribution through the app.
- **A state agency is not a club.** OPRHP, DEC, PIPC and NJDEP hold sections in the ring
  and none of them is a maintaining club. Storing them in `clubs` makes SAYING_THANKS.md's
  resolution capable of thanking a state GIS office for clearing a blowdown, and
  VOLUNTEERING.md's whole model of crews and hours is about volunteers, not agencies.
  SOURCE_REGISTRY.md already recommends the shape — an `Organization` with a `kind`, and
  `clubs.organization_id` referencing it, "one nullable FK plus a backfill — not a rename of
  the existing table" — and lists "Generalising `Club` into `Organization`" as an open
  question because it touches `MaintainerAssignment` and SAYING_THANKS.md's attribution
  path. **#780 — Research route ownership: the AT in NY has thirty owners, a landowner with
  final say per section, and a maintainer besides is the second independent reason to do
  it**, which is worth recording on that open question rather than deciding here.

A fifth thing, smaller and worth a line: nothing constrains two assignments from covering
the same miles on the same dates, and that is **deliberate** — SAYING_THANKS.md's "zero or
more, never exactly one" needs overlap to be legal. Do not let a well-meaning migration add
a uniqueness constraint that breaks the joint case the moment it is modelled.

### What the identity ledger needs: nothing, and here is why

[POI_IDENTITY.md](POI_IDENTITY.md)'s ledger is a row per **place** ever published, with
three rules — never re-mint, never reuse, never delete — because a hiker's photos and
reports anchor to those ids. A section is not a place, nothing anchors to it, and adding
thousands of section rows to a file that just doubled to 8,563 rows and had its
reference-line ceiling raised to 12,000 — **#1026 — The POI identity ledger doubled and
crossed the reference-dir ceiling, so the publish path is blocked at both ends** — would be
the wrong move on volume alone.

**What does need the ledger's three rules is the organization id namespace.**
SOURCE_REGISTRY.md's `"steward": "org:nynjtc"` is already that identifier, and organizations
merge, rename and dissolve exactly the way POI upstream keys re-key. `org:nynjtc` must
never be re-minted, never reused, and never deleted — a club that merges into another gets
a `superseded_by` edge, not a rewrite, or every role assertion and every stored thanks
pointing at it silently changes meaning. That is the ledger's contract applied to a second
namespace, not a second ledger, and it is one paragraph in SOURCE_REGISTRY.md rather than
work here.

The one thing that would change this answer: if a role assertion ever becomes something a
hiker can attach a report to — "this section's maintainer attribution is wrong" — it needs
a stable id with the ledger's guarantees, and that is the moment to revisit.

---

## 9. The role does not have to be held by three different organizations

Two ways the lattice collapses, both real, and a model that assumes three distinct
organizations gets both wrong.

**The route owner also owns ground.** `pipeline/SOURCE_SURVEY.md:268` records ATC's own
lands layers — `2022_ATC_Lands_Fee_Parcel_Shapefile` and its easement sibling, **24 fee
parcels and 33 easement parcels**, data dated 2025-05, filed there as "LAND_OWNERSHIP.md
material, Post-MVP".

So on 24 parcels ATC holds the ground in fee and on 33 more it holds an easement, while
being a joint owner of the route that crosses them — and wherever the A.T. does cross one, a
club is still the maintainer, because the centerline's `Acronym` does not stop at a parcel
boundary. This is a fourth relationship the three-role model does not name — the roles are
not a partition of organizations, they are a relation, and one
organization can hold two or three of them on the same section. The consequences are small
and specific: no rule may derive one role by exclusion from another ("the landowner is
whoever is not the route owner" is wrong on 57 parcels), and a card that prints three roles
must collapse to one line when one organization holds all three, or it reads like a
bureaucracy where there is a single steward.

An easement is the more interesting half and this document does not model it. A conservation
easement splits final-say between the fee owner and the easement holder along whatever the
instrument says, which is genuinely two landowners with divided authority rather than joint
authority. DEC's `dil_trails` layer even has a sibling for it —
`pipeline/NYC_SOURCE_SURVEY.md:118` names "a 42-feature conservation-easement variant
(`PUBRIGHTS` field)". **@unvalidated**: whether the two-landowner case needs its own role or
fits inside `orgs` as a list of two would be settled by reading `PUBRIGHTS` on those 42
features and one of ATC's 33 easement parcels, which is an afternoon and has not been done.

**And the roles collapse the other way too.** On 298 of Mohonk Preserve's 304 shipped
segments, owner and manager are the same organization (§1). The interesting rows are the six
where they are not; the model has to make the 298 cheap.

---

## 10. What to build first, and it is very small

The subset worth doing before any of the model exists, because it costs almost nothing and
produces the evidence the rest of this document is short of:

**Export Mohonk's `Owner` and `Manager` onto the network lines.** Both fields are already
fetched — `fetch_external_layers.py` pulls the whole layer, and
`export_nearby_trails.py` reads only `Blaze`, `Name` and the use/status flags. Six segments
would ship with an owner that is not their manager, and the app would carry its first
per-section role assertion from live data, on a source that already reaches hikers. It also
forces the first real decision the model needs: `Owner: NYS OPRHP/PIPC` is two organizations
in one string, and whatever splits it is the beginning of the reviewed table §3 says the
thirty names will need.

Two things to check rather than assume before doing it. It rides Mohonk's existing
maintainer authorisation, so no new licence question — but confirm that, because §7's whole
point is that a source's terms cover what it publishes and these are two columns nothing has
shipped yet. And `nearby_trails.geojson` is a download hikers weigh against phone storage:
two short strings on 304 features is almost certainly nothing, and "almost certainly
nothing" is the sentence this repository asks to be measured rather than written.

**Then give `sources.json` a `role_fields` block per source** — `{"maintainer": "Manager",
"landowner": "Owner"}` for Mohonk, `{"maintainer": "Acronym"}` for the centerline,
`{"maintainer": "Maintainer"}` for the Long Path. That is the same "the fact lives next to
the organization making the claim" posture `owns_route_names` already has, it needs no new
mechanism, and it turns §1's table from prose in a design doc into something the build can
be wrong about visibly.

Neither of those needs the backend changes in §8, the `RoleAssertion` artifact, or any
client work. They produce the data that would tell us whether the rest is worth building.

---

## What this deliberately isn't

- **Not a claim about who legally owns anything.** This project records what sources say
  about roles and who said it. The blazes and the landowner's own signs are authoritative on
  the ground — LAND_OWNERSHIP.md's line, and it holds here twice over.
- **Not a governance body.** SOURCE_REGISTRY.md already refuses this and the refusal
  transfers: "Deciding whose data is authoritative where is a trail-community question. This
  gives that decision a place to be recorded — it does not make it."
- **Not a second authority on who maintains a mile.** The backend's `MaintainerAssignment`
  stays authoritative; the published artifact stays the map's copy for drawing and for
  working offline; where they disagree the backend is right (CORRIDOR_VIEW.md, unchanged).
- **Not a re-opening of the POI precedence decisions taken on #772 — Design the map when
  trails cross: one chosen centerline, every other trail visible, and safety pins that
  ignore the choice.** This supplies the definition of "the org" those rules were missing
  and changes none of them.
- **Not a new closure feed.** §5 is a rule about ordering and about what may never be
  dropped. The feeds are ORG_NOTICES.md's, ATC_TRAIL_UPDATES.md's, and the one shipped by
  **#964 — NYS Parks closes areas, not trail segments, and the closure model has nowhere to
  put one**.
- **Not a matcher.** No role is inferred from a name, an alternate name, or proximity.
  `suppressed_by_owner()`'s 26-segment `Alt_Name` finding is what that costs.

---

## Open questions, not resolved here

- **Whether the thirty names should ever be printed.** The A.T.'s joint owners are a list
  this project has from one sentence by one person. A reviewed file in `reference/`'s
  posture could carry them with a signature; printing them off anything less would be the
  strongest-plausible-sentence failure this repository's standard exists to prevent. It is
  also not obvious a hiker wants thirty names on a card.
- **What `REGION`/`OFFICE` were.** §1's claim 5 could not be verified. Either a sibling DEC
  layer carries them or the claim is wrong, and one live probe settles it.
- **Whether the landowner role can be populated for the A.T. at all today.** It cannot from
  ATC's estate. PAD-US is the only route written down and it is unbuilt, which makes the
  role with *final say* the one role no shipped source names for the flagship route. That is
  an uncomfortable place for this design to be and it is where it is.
- **Whether the easement case needs a fourth role** — §9, `@unvalidated`, settled by reading
  `PUBRIGHTS` on 42 DEC features and ATC's 33 easement parcels.
- **How a section's boundaries are decided when two sources disagree about where it ends.**
  ATC's club sections tile the trail exactly (2,197.5 miles, no seams or overlaps);
  OPRHP's `Facility` boundaries and DEC's `UNIT` boundaries do not align with them and there
  is no reason they should. A leg per assertion sidesteps the question rather than answering
  it, and the first render that has to draw three role bands over one stretch will find out
  whether that was enough.
- **Whether an org-issued closure gets its own backend path.** §5's last part says the gap
  exists and declines to design the fix, which wants an issue of its own — with an authority
  column and a moderation bypass, both of which are decisions about who may write to a
  safety surface rather than schema.
- **Whether `Club` becomes `Organization`.** SOURCE_REGISTRY.md's open question, and §8d is
  the second independent reason to answer it. Better made once, deliberately, than twice.
