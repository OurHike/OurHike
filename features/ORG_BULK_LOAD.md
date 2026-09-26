# OurHike — Loading the trail organizations in bulk (Plan v1)

Companion to [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) (what a registered source is, and the rule that
nothing self-service reaches a hiker without a merge) and [ORG_ONBOARDING.md](ORG_ONBOARDING.md) (the
four public doors, one of which this plan drives). The catalogue this plan operates on is
[`pipeline/reference/trail_orgs.json`](../pipeline/reference/trail_orgs.json), and the tracking issue
is **#1543 — 165 trail organizations exist and the registry knows 14, with no way to load the rest
that does not cost one pull request each**.

**Provenance.** The organization list is the maintainer's research pass of 2026-09-17: 165 rows
covering national umbrellas, all 11 National Scenic Trail stewards, the National Historic Trail
stewards, all ~30 Appalachian Trail maintaining clubs, regional nonprofits, federal agencies,
aggregators and route-only trails, each with a GIS endpoint where one was found and its licence
terms. Every count below is measured against that pass as loaded into the catalogue file, and says
so. Nothing here has been fetched — **no endpoint in this plan has been probed by this repository**,
and the research's own caveat is that `inferred` rows were never opened.

---

## The reframe: it was never 400 pull requests

The maintainer's constraint was *"without me having to review 400 PRs."* The useful finding is that
the number was never near 400, and seeing why is most of the plan.

Measured against the catalogue, 2026-09-17, across its 172 rows:

| `load` verdict | rows | what it costs to load |
| --- | ---: | --- |
| `via` — geometry arrives through another row | 79 | **nothing.** No entry, no fetch, no bytes. |
| `hold` — recorded, `reaches_hikers: false` | 39 | nothing. A row in a file. |
| `none` — no geometry exists, now or later | 25 | nothing. |
| `refuse` — stated commercial or waiver-gated terms | 4 | nothing. |
| `ship` — open terms and a usable endpoint | 25 | a fetch, a clip, and download budget |

Of the 25 `ship` rows, **9 are already registered** — USFS, ATC, OpenStreetMap and NJDEP all have
entries in `sources.json` today. So the work this whole catalogue produces is:

> **11 new endpoints.**
>
> National Park Service · Bureau of Land Management · Colorado COTREX · Washington RCO ·
> Utah SGID · Wisconsin DNR · AZGeo · City of Duluth · Pacific Crest Trail Association ·
> Continental Divide Trail Coalition · North Country Trail Association

Eight are public domain, one is CC BY 4.0, and two are published openly with no stated terms.

**The 59 `via` rows are where the leverage is, and they are the reason a club-shaped form would have
produced 400 pull requests.** All 30 A.T. maintaining clubs consolidate into the ATC centerline this
repository already fetches — the Maine Appalachian Trail Club publishes nothing, and its 267 miles
are already on the map. Twenty-three National Historic Trail and National Scenic Trail stewards hold
no geometry and point at the National Park Service; **one NPS registration answers all 23.** Florida
Trail and Arizona Trail resolve to USFS and AZGeo. Washington Trails Association and The Mountaineers
both defer to WA RCO.

A form that asks each organization for its endpoint gets 59 organizations inventing one, or 59
organizations bouncing. A catalogue that lets a row say *"real organization, geometry lives there"*
gets the same map for eleven fetches.

## What the licence question actually blocks, which is almost nothing

The maintainer's instruction was to treat an unstated licence as open rather than as a blocker. That
turns out to change two rows, because licence was never the binding constraint:

- **51 of the 58 `hold` rows have no endpoint at all.** They are blocked on a URL nobody has found —
  Connecticut Forest & Park Association's 825 miles of Blue-Blazed trails, the Appalachian Mountain
  Club's White Mountains inventory, North Carolina's Mountains-to-Sea corridor. The licence question
  has not been *reached* on any of them, because there is nothing yet to licence.
- **7 `hold` rows have an endpoint.** Three are public domain and held for other reasons (USACE
  publishes facilities rather than centerlines; USGS's National Map is a human downloader with no
  service URL to poll; NY State Parks is held because the same data is already registered under
  NYS OPRHP at `reaches_hikers: false` and this must not become the way that holdback is bypassed).
  One is held on format rather than terms — Tahoe Rim Trail publishes shapefile, GPX and KMZ for
  free behind an email form, and a form-gated download is not a URL a freshness check can poll.
- **That leaves two rows genuinely waiting on somebody reading terms**: Friends of the Mountains-to-Sea
  Trail and the Ozark Trail Association, both of which publish an interactive web map rather than a
  dataset anyway.

So: **assume-open costs nothing here and buys two rows, neither of which has a fetchable endpoint.**
The instruction is recorded and applied — `cdtc` and `ncta` ship on it, both being open ArcGIS hubs
with public downloads and no stated restriction — and the catalogue records `licence_basis:
"unstated"` rather than claiming a grant nobody made. That distinction is the whole point: a row may
ship on an unstated licence, and a reader must still be able to see that nobody stated one.

**Six rows state a real restriction and stay out**: Buckeye Trail (1,444 miles behind paid apps),
Sheltowee Trace and Ozark Highlands (commercial GPX and printed maps), Avenza's store, TrailLink,
and the Oregon Desert Trail, whose GPX is released only after a liability waiver. Assume-open does
not reach a stated restriction, and three of those six have their ground managed by the Forest
Service, so the open path to the same trail is a row already on the list.

## The binding constraint is download budget, and it has a measured precedent

**#1231 — usfs_trails and usfs_rec_sites ship nationwide (Arizona and beyond), when only the region
near the corridor was the point of registering them** is what this plan has to answer before anything
flips to `reaches_hikers: true`. One federal source, registered with no geographic scope, produced
(measured 2026-09-04 against the published UA release) a 228 MB `nearby_trails.geojson` carrying
112,378 features of which **68,622 fell outside the A.T. corridor** — Arizona trails on the phone of
somebody walking through Georgia.

This catalogue adds **NPS and BLM, both nationwide, and eight state-scale layers.** Colorado COTREX
alone is 45,076 miles from 236 land managers. Against archive baselines of z11 ~64 MB, z12 ~314 MB
and z13 ~1.18 GB, that is not a rounding error.

The tension is real and is not this plan's to resolve: the maintainer's own documented policy
(`export_nearby_trails.py`, #1019) is *"Don't limit data from orgs based on geography."* That was
written about organizations whose services are themselves state-scoped, where it costs nothing. A
nationwide federal layer is the case it did not anticipate. **#1543 carries this as the open
question, and no `ship` row flips to `reaches_hikers: true` until it has an answer.** That is why the
plan below registers before it ships, rather than as caution for its own sake.

## The load, in four pull requests

Batched by **the decision a reviewer is making**, not by organization. A reviewer approving eight
public-domain federal rows makes one decision eight times; a reviewer approving eight bespoke
licences makes eight decisions. The first is worth batching and the second is not.

| | what it contains | the reviewer's decision | ships? |
| --- | --- | --- | --- |
| **1** | This plan and the 163-row catalogue | Is the `load` column right? | no |
| **2** | 8 public-domain endpoints, probed, `reaches_hikers: false` | Is public domain the right reading, and did the probe run honestly? | no |
| **3** | 3 open-licence endpoints + attribution strings, `reaches_hikers: false` | Are the attribution strings correct? | no |
| **4** | The `reaches_hikers` flip, once #1231's scope question is answered | Which geography, and what does the archive weigh? | **yes** |

Pull request 1 is this one. Each of 2 and 3 carries a **summary table, not 163 diffs** — the probe
result per endpoint (feature count, geometry kind, CRS, whether the freshness marker exists,
transfer size), which is what a reviewer needs and what `sources.json`'s existing entries already
record by hand. `nh_granit_trails` is the standard to meet: four column findings, each measured, each
dated.

**Four pull requests, and the fourth is the only one that changes a hiker's map.** The gate
SOURCE_REGISTRY.md and DATA_RELEASES.md exist to protect is untouched, because registering and
shipping were already two acts and `reaches_hikers` already separates them.

### This is existing practice, not a new lane

Worth stating plainly, because the batching sounds like a shortcut and is not. **GATC and all four
NYS OPRHP layers are registered in `sources.json` right now at `reaches_hikers: false`** — fetched,
recorded, and deliberately absent from every hiker's screen until their licence answers land.
`export_sources.py` names both organizations and says why in its own docstring. The bulk load is that
arrangement at scale.

## What the nominate form needs — re-checked against the built form

**This section was written against `ORG_ONBOARDING.md`'s design on 2026-09-17. The form shipped in
the nine days since, so on 2026-09-26 it was re-checked against the code** —
`site/src/pages/for-orgs/nominate.astro`, `backend/app/core/nominate.py` and
`backend/app/schemas/nomination.py` on `main` at 46148d70. Two of the five gaps are closed, one of
them better than this document proposed, and the largest one is still open.

### Two are closed, and the contacts answer is better than the ask

- **Contacts: solved, and solved harder.** This document reported *0 contacts of 163* and argued that
  163 plausible coordinator names would be worse than none *"because they would be believed"*.
  `nominate.py` reaches the same conclusion from the other direction and enforces it: it reads the
  organization's own pages, asks a model, then **grounds every address and URL back against the
  literal page text and drops whatever is absent.** Its own docstring names the failure exactly —
  `president@carolinamountainclub.org` is *"precisely the shape of thing that gets invented - correct
  domain, obvious role, no such mailbox"*. `ProposedContact.source_page` is NOT NULL, and a citation
  naming a page nobody opened is corrected or the contact goes. That is a better answer than leaving
  the field empty, and it is this project's own "never let a display outrun its source" applied to
  the one path where the display is about a named person.
- **Membership and donation links: solved.** `NominateReading` carries `membership_url` and
  `donation_url`, and `for-orgs/index.astro` collects both at registration. This document reported
  both as 0 of 163.

### One is half-closed

- **Provenance.** `KeptSource` and `KeptContact` both carry `proposed_by: Literal["reading",
  "hiker"]`, which is the distinction this document asked for — a submission's origin recorded as a
  kind rather than as a person. **What it has no value for is a bulk research load**, so a catalogue
  row still has nowhere honest to sit. One more enum member.

### Two are still open, and the first is the largest saving in the plan

- **There is still no `via` pointer.** `NominationSubmit` takes `website`, `org_name`, `region`,
  `sources` and `contacts`. **79 of the 172 catalogue rows hold no geometry of their own**, and the
  form can express "here is my endpoint" but not "I am real, my trails are on the map, and that row
  over there is where they come from". Those 79 either invent an endpoint or never register, and the
  Maine Appalachian Trail Club stays absent from a product that has drawn its 267 miles since v1.
- **`region` is free text, not an extent.** `region: ShortName | None` is a reviewer's note. #1231 is
  what that field not being geographic costs: 228 MB and 68,622 out-of-corridor features from one
  nationwide source. COTREX at 96,897 features and Utah at 47,986 are the next two.
- **Licence evidence is prose.** `licence_note` is a `Detail`, and `nominate.py` is explicit that
  prose is *deliberately* not grounded the way an address is — right for a summary, and not the same
  thing as `licence_basis` plus a `licence_evidence_url` and a read date. **54 of 172 rows are
  `unstated`**, which a free-text note cannot distinguish from "nobody looked".
- **Dedupe.** `NominationOut` carries a `club_slug`, so a slug exists. Whether two submissions for one
  organization collide is not visible from the schema and was not tested here — recorded as unchecked
  rather than as either answer.

## The probe pass, and what inference had missed

The catalogue's first version carried the research pass's own `verified`/`inferred` marks, and its
caveat that an `inferred` row's URL was never opened. **On 2026-09-17 this repository probed the
endpoints itself**, and the difference is worth recording because it moved sixteen organizations
without adding a single fetch.

**Eleven trails turned out to be inside layers this pipeline already pulls.** Counted live, each
re-runnable:

| Trail | Already in | Features |
| --- | --- | ---: |
| Sheltowee Trace | `usfs_trails` | 87 |
| Maah Daah Hey | `usfs_trails` | 31 |
| Ouachita | `usfs_trails` | 25 |
| Pinhoti | `usfs_trails` | 21 |
| Ozark Highlands | `usfs_trails` | 16 |
| Benton MacKaye | `usfs_trails` | 14 |
| Bartram | `usfs_trails` | 7 |
| Lone Star Hiking | `usfs_trails` | 6 |
| Condor | `usfs_trails` | 2 |
| Northville-Placid | `dec_hiking_trails` | 117 |
| Monadnock-Sunapee Greenway | `nh_granit_trails` | 145 |

**Two of those were `refuse`, and the refusal was about the wrong thing.** Sheltowee Trace and Ozark
Highlands both sell their own GPX, which restricts *their product* and says nothing about the trail.
The Forest Service manages the ground and publishes the geometry as public domain. Both trails ship;
neither organization's product is touched. That is a mistake worth naming rather than quietly fixing,
because it is the shape an over-cautious licence read takes: refusing a trail because somebody sells
a map of it.

**Five organizations OurHike already ships data from were absent from the research pass entirely** —
NYS DEC (8 registered layers, 5,291 trail features), NH GRANIT (19,877 statewide segments), Mohonk
Preserve, NYC Parks and NYC DOT. A survey of who exists that omits five organizations already on the
map is a survey with a blind spot in the one place it was cheapest to check, which is why the
catalogue now carries them.

**One endpoint the research recorded could not have been fetched.** COTREX was a Hub dataset page;
the queryable layer is `CPW_Trails_08222024/FeatureServer/2`, and it holds **96,897 trail features**.
That is a download-budget number rather than a detail — see #1231.

**One cheap answer was ruled out by measurement.** The Cohos Trail is not in NH GRANIT: zero features
match on either `TRAILNAME` or `TRAILSYS` across the 19,877-segment state layer. The row stays
`hold`, but now on evidence rather than on nobody having looked.

**After the first probe round: 90 organizations reachable, from the same 11 new fetches.** Every one
of the sixteen came from data already on disk.


### Round two: eight state clearinghouses

The first round asked "is this already in a layer we pull". The second asked "does a state publish
this at all", against the eight clearinghouses the catalogue's own notes kept naming. **Four more
organizations the research pass omitted, and nine more rows off `hold`:**

- **MassGIS** — a `Long Distance Trails` layer of 32 features across 7 named trails, and a
  `DCR Roads and Trails` layer of 36,859. It answers the Blue Hills and the Trustees. **It also holds
  the Bay Circuit Trail at 241.8 miles, which appears in no row of the research pass at all** — a long
  trail with published open geometry that the survey simply missed.
- **CT DEEP** — `BlueBlazedHikingTrails`, 351 features, carrying `TrailName`, `Par_Name`, `Blaze`,
  `Map_Color`, `Length`, `Gains` and `Losses`. A blaze column *and* an elevation column, which is more
  than most already-registered sources publish. This is the Connecticut Forest & Park Association's
  825-mile network published as open state data, and CFPA was a gap only because nobody looked here.
- **PASDA / PA DCNR** — `DCNR Statewide Land Trails 2023`, 684 features, carrying Mid State, Laurel
  Highlands, Mason-Dixon, Standing Stone and Baker; PA DCNR's State Forest layer adds Loyalsock, Donut
  Hole and Quehanna. **Eight Keystone-affiliated long trails, none of which any organization publishes
  itself.**
- **North Carolina** — a `Mountains_to_Sea_Trail` FeatureServer of 328 polylines. The catalogue had
  the 1,175-mile trail as blocked on a URL nobody had found.
- **Utah SGID** — the endpoint was a Hub page and is now the queryable layer: 47,986 features,
  carrying the Bonneville Shoreline Trail at 281 and the Wasatch Mountain Club's ground at 40.

**Two cheap answers were ruled out by measurement rather than left unexamined.** The Superior Hiking
Trail is *not* in MN DNR's state trails layer — zero features match across its 978 rows, so the 42
Duluth miles remain the only published portion anybody here has found and the other 267 are a real
gap. And NC OneMap's own recreation service holds only paddle trails, so looking there first would
have confirmed the Mountains-to-Sea gap rather than closed it.

**The load after both rounds: 103 organizations reachable, against 15 new fetches** — up from 74
reachable when the catalogue was first written. `hold` fell from 58 to 40, and **every row that moved
did so on a feature count anybody can re-run.**


### Round three: the ArcGIS Online catalogue, not the organization's website

The maintainer's observation of 2026-09-26 is the whole reason for this round: *"AMC has no map on
its website. But that is available in arcgis."* Both halves are true, and the second one was never
checked — the first two rounds probed each organization's **own server root**, which finds nothing
when an organization has no server of its own but does have an ArcGIS Online account.

All 172 rows searched against the public ArcGIS Online item catalogue. **39 of 172 have a
trail-shaped item.** The finding that matters is how few of those are the organization itself:

**Only two organizations publish their own trails from their own account.**

| org | item | features | was |
| --- | --- | ---: | --- |
| **Alaska Trails** | `Alaska_Trail_Database`, owner `alaskatrails` | **1,602** | `hold` — "no findable data" |
| Mohonk Preserve | `Mohonk Preserve: Trails and Carriage Roads` | 304 | already registered |

Alaska Trails is the verdict this round moves. It was recorded as advocacy-only with nothing to
fetch; it has a 1,602-feature trail database, plus `AKLT Trail Segments` (286) and four regional
layers, published from its own account.

**AMC is the case that prompted the round, and it is stranger than expected.** 702 items under
`cpoppenwimer_AMC` — `HT_entire_trail_network`, `PA Highlands Land Trails`, `AMC Destinations`,
`AMC Properties and Landscapes`, `Appalachian Trail Mid Atlantic Region`, `AMC Chapter Boundaries`.
But that is AMC's **Highlands and mid-Atlantic conservation programme**, not the White Mountain trail
inventory the row was held for. So "no findable data" was wrong and the White Mountains question is
still open — which is a more useful state than either "no data" or "solved".

**Three leads that change a reason without changing a verdict:**

- **Superior Hiking Trail** — Lake County, Minnesota publishes `Superior_Hiking`, **576 features**.
  That is the first lead on the 267 miles MN DNR's state trails layer does not carry. A county, not
  the association.
- **Tahoe Rim Trail** — a layer literally named `TRT_System_Shapefile`, **236 features**: the same
  system shapefile the association releases only behind an email form. The owner is Esri's own JS API
  team, so this is a third party mirroring it, and asking the association is still the honest route.
- **USACE** — a Corps district account publishes 149 recreational-trail features. One district
  rather than the nationwide centerline, so the row stays held and its reason improves from "nothing
  found" to "found one district".

**Two route-only trails have geometry and stay `none`, which is the point.** A `Sierra High Route
Line` (1 feature, a personal account) and `The Grand Enchantment Trail` (41 features, a water
management district) both exist. Nobody maintains either route, so shipping a traced line as a trail
would make exactly the claim the route-only verdict refuses. Geometry existing is not a trail
existing.

**Why "found on ArcGIS Online" is weaker evidence than it looks.** Thirty-seven of the 39 hits belong
to somebody other than the organization — counties, state agencies, university accounts, Esri
itself, private individuals. An item a third party uploaded is not the organization choosing to
publish, carries no licence anybody stated, and can vanish when its uploader's account does. Each is
recorded in the row's `agol` field as a lead with its owner named, and none of them moves a row to
`ship` on its own.


## Filling the form: one run, not 172 people typing

[ORG_ONBOARDING.md](ORG_ONBOARDING.md)'s `/for-orgs/nominate/` screen is not a blank form. It reports
what OurHike **found** about an organization — each endpoint with what is in it, the licence
position, the membership and donation links, and the flat files we refuse — and asks a human to
confirm it. The prototype's own licence row reads *"nothing restricting use — published publicly, no
terms attached"* against a pill saying **no restrictions**, which is the maintainer's assume-open
position already drawn into the design rather than a new argument.

[`pipeline/build_org_nominations.py`](../pipeline/build_org_nominations.py) fills that report for
every catalogue row. Its output is generated, so it lands in `pipeline/data/` and not in the
repository — the reviewed artifact is the catalogue, and the run is what turns it into submissions.
It prints the review table rather than a diff:

```
163 nominations built, none reaching a hiker.

  verdict     orgs   what it costs to load
  ship          15   a fetch, a clip and download budget
  via           59   nothing - another row already carries it
  hold          58   nothing - a row in a file
  refuse         6   nothing - stated terms refuse it
  none          25   nothing - no geometry exists
```

**Two gaps the run makes visible, and neither is filled with a guess.**

- **Contacts: 0 of 163.** The form asks for a named human and a role address, and SOURCE_REGISTRY.md
  makes a verified contact the thing that stops a broken layer going unnoticed. The research pass
  collected none. Every nomination carries an empty list and the reason, because 163 plausible
  coordinator names would be worse than none — they would be believed.
- **Membership and donation links: 0 of 163.** These are the whole of what an organization gets back
  — OurHike takes no cut because there is no cut to take — and the research did not gather them.
  Both are null rather than invented.

Both are one scrape away and neither blocks the load. They are recorded here because a form field
silently defaulting to empty is how a promise to an organization quietly stops being kept.

## Long trails get a badge, and the mark is not ours to draw

[TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md) records that after dash style was tried and withdrawn
twice, **line width** carries the hue-independent channel: a through-route is drawn wider than the
spurs off it. That document also says exactly how long that holds:

> It answers it for exactly as long as that stays true: […] a second through-route on the map turns
> the question width answers into "through-route or spur".

The 11 new endpoints above are that second through-route arriving several times over. Width will
still say *this is a through-route* and will no longer say *which*.

**The client already has the mechanism, and it already has this gap written down.**
`client/src/map/trailBadges.ts` draws one badge per through-route in view — mark, plate, name — and
takes the mark from `BADGE_MARK_BY_SOURCE`, which has **two entries**: `centerline` (the A.T.) and
`nynjtc_long_path` (the Long Path). Its own header says what happens to everything else — *"every
other source falls through to the OurHike blaze chip in the trail's own blaze hue"* — and what would
change that: *"When a `trail_id` arrives, `BADGE_MARK_BY_SOURCE` becomes a lookup against the
registry and nothing else here changes."*

[`pipeline/reference/trail_emblems.json`](../pipeline/reference/trail_emblems.json) is the list that
tier grows to: **67 long-distance trails** — the 11 National Scenic Trails, 43 named regional long
trails, and the 13 route-only trails — each with its steward and the blaze its chip takes.

### What it does not contain, and why that was a correction

An earlier draft of that file carried a per-trail shape, ground colour and letterform, so that every
long trail would have a drawn emblem. **That draft was wrong**, and the rule it broke is the
repository's own, written before this branch existed. `sources.json`'s `org_marks` block:

> **UNTIL A GRANT ARRIVES, THE SLOT RENDERS EMPTY** — never a placeholder mark, never an initial,
> never a generated shape. An organization's identity is the one thing in this app that must not be
> approximated, and a visibly empty slot is also the thing most likely to prompt somebody to go and
> ask.

`pipeline/tests/test_org_marks.py` gives that teeth for assets: a mark file in the client tree for an
organization whose state is not `granted` fails the suite, and **every one of the 14 rows reads
`not_asked`**. So neither shape of the original idea could ship — 44 drawn emblems are the generated
shapes that sentence forbids, and 44 real logos are assets at `not_asked`, which turns the suite red.

What a trail without a granted mark wears is **the blaze chip**, which is already built, already
shipping, and says something true about paint on a tree rather than something invented about an
organization. `org_marks`' own `brand_colour_chip_only` permission exists to protect exactly that
channel — *"an organization's brand colour touching a trail line would make the map say something
false about paint on a tree."*

So the file carries `blaze` and `mark_state`, the latter in `org_marks`' own four words rather than a
fifth vocabulary beside it. Every row reads `not_asked`, because that is true.

### The ask this actually unblocks

Asking is the only thing that moves a row off `not_asked`, and asking was expensive because nobody
had the list. **`reference/trail_orgs.json` is now that list** — 163 organizations with their
websites — which makes the mark ask the same shape as the licence ask and roughly as cheap.

The A.T. and Long Path marks ship on the maintainer's own authorisation, recorded in
`client/src/lib/trails.ts` and in `org_marks`. That is a real basis, it is the same footing
`atc_licence` stands on, and it does not extend to anybody else's mark.

**One pre-existing defect is worth naming rather than leaving.** `client/src/lib/trails.ts` carries
PCT and CDT marks it describes as *"placeholder marks of OurHike's own design, since PCTA's and
CDTC's official logos aren't sourced here"* — two invented shapes standing in for two organizations'
identities, which is what the `org_marks` comment forbids. They predate that block. Neither
organization is in `sources.json`'s provider list, so `test_org_marks.py`'s org-derived check does
not reach them today. **Registering PCTA — one of the 11 endpoints above — brings it into that list
and those marks into scope**, which makes this the branch that has to say so even though it is not
the branch that fixes it.

## What this plan deliberately does not do

- **It does not fetch anything.** No endpoint here has been probed by this repository. Every
  `verified` mark is the research pass's, and its own caveat is that `inferred` rows were never
  opened. Re-validating federal service URLs before a production load is recommendation 5 of the
  research and is pull request 2's job, not this one's.
- **It does not ship a single byte to a hiker.** See the four-pull-request table.
- **It does not settle the corridor question.** #1231 is named, quantified and left open, because the
  answer is a maintainer's policy call about what a hiker downloads, not a data question.
- **It does not chase the 51 endpointless rows.** They are recorded with the next place to look —
  PASDA for Pennsylvania, MassGIS for the Trustees and the Blue Hills, CT DEEP for the Blue-Blazed
  trails, and `nh_granit_trails`' undocumented `MAINTORG` integer codes for the Appalachian Mountain
  Club, which is the cheapest unopened lead in the catalogue.

## Open questions

- **Does an aggregated state layer beat a steward's own?** Colorado Trail Foundation publishes its
  own trail and is also in COTREX; this plan takes COTREX, because public domain beats unstated. That
  is a licence-driven answer to a data-quality question, and the quality answer might differ — a
  steward's own centerline is likelier current than a clearinghouse's copy of it. Unmeasured.
- **What `ogc_features` costs.** North Country's hub is the catalogue's best-published source and
  serves WFS/WMS, which SOURCE_REGISTRY.md names as the one adapter this pipeline does not have and
  the one whose freshness is unstandardised. 4,800 miles is a reason to build it; the recurring cost
  of hashing payloads to detect change is the reason it was deferred.
- **Whether the A.T. clubs should be rows at all.** All 30 resolve to ATC and none publishes
  geometry. They earn their rows here because `trail_club_sections` already puts one polygon per club
  on the map and [SAYING_THANKS.md](SAYING_THANKS.md) and `MaintainerAssignment` already mean *club* —
  so the registry knowing their names is worth something even though it fetches nothing from them.
  That is an argument, not a measurement.
