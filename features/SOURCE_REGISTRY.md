# OurHike — Source Registry (Feature Design Draft v1)

Companion to [../TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), [../FEATURES.md](../FEATURES.md) and [../OurHikeValues.md](../OurHikeValues.md). Extends [../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md) (a registration proposes; only a merged pull request releases), [../pipeline/DBT.md](../pipeline/DBT.md) (a registered source is a row; a source that needs real reshaping is a staging model), [AUTHENTICATION.md](AUTHENTICATION.md) (who signs in to register) and [VOLUNTEERING.md](VOLUNTEERING.md) (`Club`, and the `MaintainerAssignment` that answers "who looks after this mile").

The A.T. is maintained by thirty clubs — ATC's own `trail_club_sections` layer has one polygon each — plus the National Park Service, the Forest Service, and a long tail of state agencies and land trusts. Everything OurHike ships today comes from **one** of them: twelve ArcGIS layers under a single ATC-run org, found by a script that walks a public web map nobody published for that purpose. Every other organization holding trail data has no way to reach this project except by knowing someone.

This is the mechanism for the rest of them: an organization registers where its data lives and who to tell when it breaks, and that data reaches hikers through the same reviewed, versioned path everything else does.

**Scope: Post-MVP**, with one cheap piece worth doing much earlier — see "Do this part first" at the end. It is also a **prerequisite for something already scheduled**: ROADMAP.md Phase 5 expects NYNJTC's own non-A.T. network on a near-term timeline, and calls the dbt layer ([#100](https://github.com/OurHike/OurHike/issues/100)) the thing that makes onboarding it "new rows and new staging models rather than a second parallel pipeline." This document is where those rows come from.

---

## What already exists, checked rather than assumed

### The registry is already here. It just has one author.

[`pipeline/sources.json`](../pipeline/sources.json) is a registry of upstream layers with a `key`, `title`, `provider`, `url`, and a `discovered_via` trail of provenance. It already carries a **`provider`** field — set to `"ATC"` on all twelve entries — which is this feature's central idea in one word with nothing behind it yet. [`discover_sources.py`](../pipeline/discover_sources.py) is already provider-agnostic: `pipeline/README.md` says outright that pointing it at another club's Experience Builder app needs "that app's URL and a `--provider` label — nothing else in the script is ATC-specific."

### The schema already expects this, and says so

[`lib/poi_schema.py`](../pipeline/lib/poi_schema.py)'s `unify_poi()` docstring:

> `field_map` carries everything source-specific […] so a new source or club only ever needs a new field_map plus a caller-side loop, never a change here.

and:

> `trail_id` is entirely caller-supplied, never hardcoded to "AT" here — this project starts AT-only but the schema itself must not assume a single trail (value #7).

That is a cheque this feature cashes rather than a design it introduces. The gap is where the field maps live: [`export_poi.py`](../pipeline/export_poi.py)'s `DIRECT_SOURCES` is a Python tuple of literals. A new source today is a code change by whoever owns this repository — which is exactly the wall an outside organization cannot climb.

### Freshness is already normalised across four unrelated upstreams

[`check_freshness.py`](../pipeline/check_freshness.py) already maps four incompatible "did this change?" signals onto one verdict — ArcGIS `editingInfo.dataLastEditDate`, S3 `Last-Modified`, HTTP `ETag`, and a published-edition set — and already keeps `STALE` and `UNKNOWN` apart because they call for different responses. A fifth source kind is a fifth marker, not a new mechanism.

### And the release process already has the property this must not break

DATA_RELEASES.md separates four things on purpose:

| | can write to R2 | can change what hikers get |
|---|---|---|
| Daily freshness check | no — holds no credentials | no |
| Weekly candidate build | only under `releases/<new>/` | no |
| Verification battery | no | no |
| Release | no | **yes — and it is a merged pull request** |

**Self-service registration must not become a fifth lane that bypasses that.** Anything that lets an outside organization change the bytes on a hiker's phone without a human merge undoes the one property that whole document exists to establish.

### What is missing

Nobody outside this repository can add anything, nobody outside it can be told when their data breaks, and the licence question gets asked too late. Both of this project's unresolved data-terms problems — ATC's redistribution terms, and opentrail.org's ([#98](https://github.com/OurHike/OurHike/issues/98), open and `blocked-external`) — are the same failure: the data was fetched first and the right to ship it was investigated afterwards. A registration form is the one moment where that question can be asked *before* the bytes are in the build.

## The shape: registration is a form, the build input is a file

The sharpest question here is whether the registry becomes a database table. Both answers are half right, so it is split by what each half is for:

| | lives in | why |
|---|---|---|
| **The registration** — who the org is, the contact, verification state, review status, probe results | Backend (Postgres) | An org needs a form, not a pull request. Contact addresses change, get re-verified annually, and bounce — that is weekly churn no git history should carry, and a role inbox in a public repo is a spam magnet. |
| **The source the build reads** — endpoint, kind, licence, field map, freshness marker | `pipeline/sources.json`, in git | The build runs from a checkout. Keeping the build's inputs in reviewed source is *precisely* what makes "only a merged pull request changes what hikers get" true rather than aspirational. It is also what a club forking this repo inherits (value #7). |

**The bridge is a bot-opened pull request.** An approved registration is rendered into a `sources.json` entry by a job that opens a draft PR — the same `propose` step DATA_RELEASES.md already specifies for the weekly build, with a second producer rather than a second mechanism. A human reviews the diff; merging it is what admits the source. The organization's experience is a web form. The build's experience is unchanged. The safety property holds exactly.

`sources.json` therefore stores a **stable steward id, not an address** — `"steward": "org:nynjtc"` resolving to the backend record. Two consequences worth having: no contact details in git history, and a corrected address takes effect on the next send rather than waiting for a data release.

## 1. Registering a source

### The kinds, and what each actually costs

The registry entry names a `kind`. Adapters are **per protocol, not per organization** — the second club with an ArcGIS server costs nothing, and the first club with a new protocol pays for everyone after them.

| kind | who has this | fetch | freshness marker | new code |
|---|---|---|---|---|
| `arcgis_feature_layer` | ATC; most agencies with a GIS department | [`lib/arcgis.py`](../pipeline/lib/arcgis.py) | `editingInfo.dataLastEditDate` | **none** |
| `arcgis_experience` | a club with a public web map and no idea what a FeatureServer is | `discover_sources.py`, expanding to N `arcgis_feature_layer` rows | per expanded layer | **none** |
| `http_file` | anyone who can put a GeoJSON/GeoPackage/zipped shapefile at a stable URL | plain GET | `ETag` / `Last-Modified`, as `fetch_opentrail.py` already does | small |
| `ogc_features` | state agencies running GeoServer | paged GET | **none standardised** — see below | one adapter |
| `drive_folder` | a volunteer with a folder of shapefiles | see below | Drive `modifiedTime` | real work |
| `push_upload` | an org whose data only exists in a database | *they* push; we serve it back to ourselves as `http_file` | upload timestamp | backend endpoint |

**`ogc_features` deserves an honest note.** OGC API – Features standardises the query interface and standardises nothing about "has this changed" — some servers support HTTP conditional requests, many don't. Where the server can't answer cheaply, the fallback is hashing the fetched payload, which means paying the full download to learn nothing changed. That is a real recurring cost, not a rounding error, and it should be visible to the reviewer at registration rather than discovered in a CI bill.

### "a database" — the one we say no to, and what we say instead

An organization offering direct database access is offering us their credentials. **We should not take them.** Holding a club's Postgres password buys nothing the alternatives don't and creates a liability a volunteer-run project should not carry — a breach here is *their* incident, caused by our convenience.

The alternative is `push_upload`, and it costs us almost nothing because the backend already exists: an authenticated endpoint writes the org's export to a per-org prefix in R2, which *is* a stable URL, which the `http_file` adapter already reads. Their scheduled `pg_dump`-to-GeoJSON job pushes; nothing else changes. No credential custody, no new fetch adapter, and the org keeps control of what leaves their database — which is the same shape as value #6 pointed back at them.

### "a Google Drive of shapefiles" — supported, and honestly the worst tier

This is the case the ask names by hand, and it is worth taking seriously precisely because it is what a small club actually has. It is also the one where guessing hurts:

- **A folder is not a dataset.** A shapefile is four-plus files that must travel together, and a folder accumulates `trails.shp`, `trails_v2.shp`, `trails_final_REAL.shp`. Picking one by filename is a coin flip with a safety-relevant outcome.
- **A missing `.prj` means the CRS is unknown**, and this pipeline has already been bitten once by getting a coordinate system silently wrong — see `ST_Transform`'s `always_xy` gotcha in `pipeline/README.md`, which "succeeded" while producing geometry on the wrong side of the globe. Guessing a CRS is the same class of error with the same shape of failure.
- **It is unversioned by construction**, which is the exact opposite of the immutable-release discipline everything downstream depends on.

**So: supported, with a manifest.** The folder must contain a small `ourhike.json` naming which files are the real dataset, their CRS if the `.prj` is missing, and the licence. With it, ingestion is mechanical: snapshot the named files into our own storage at build time and treat the snapshot as the source of record. Without it, the registration stays `needs_info` and a human asks — rather than the pipeline picking a file and being confidently wrong.

The form should say plainly that a stable URL is better and offer to help them get one (`push_upload` is that offer). Meeting an org where they are is the point of the feature; leaving them there forever is not.

*Unverified and worth checking at implementation time:* whether listing a link-shared Drive folder works with a plain API key or needs full OAuth. If it needs OAuth, this becomes credential custody again and `push_upload` is the answer instead. Same "confirm against the real API, don't trust this doc" caution AUTHENTICATION.md applied to Supabase pricing.

### The probe: we check, we don't take their word

On submission the backend fetches the endpoint **once, read-only**, and reports back what it actually found: feature count, geometry types, field names, CRS, whether the declared freshness marker exists, and approximate transfer size. It does not record the submitter's claims as facts. This is the same instinct as `fetch_all.py` refusing to write a manifest on a zero-feature "success", applied at the front door instead of the back.

It is also what makes the form self-correcting. An org sees *"we reached this and found 0 features"* or *"no `.prj`, and we can't tell what projection this is in"* in the same sitting, not three weeks later in an email.

**A user-supplied URL fetched by our own server is server-side request forgery**, and naming it here is cheaper than discovering it later. The probe runs out of band from the API request, resolves DNS and refuses private, loopback, link-local and cloud-metadata ranges (`169.254.169.254` included), refuses non-`http(s)` schemes, re-checks every redirect hop rather than only the first, and caps both bytes and time.

### Required at submission: licence and attribution

Not optional, not "we'll sort it out later" — a registration without a licence and an attribution string is incomplete and cannot be approved. An SPDX identifier where one applies, the exact attribution text to render, and a named human at the org who says the org has the right to grant it.

This single required field is the whole reason to prefer a form over an email thread. It is also the one thing that would have prevented both open licence questions this project already carries.

### The field map is data, not code

For a self-serve registry, `unify_poi`'s `field_map` has to move out of `export_poi.py`'s Python literals and into the registry entry. The constraint that keeps this safe is that field maps stay **declarative** — rename a field, select a subset, set a constant, map a coded domain onto ours (which [`lib/blaze.py`](../pipeline/lib/blaze.py) already does for `Blaze`). Never an expression, never a script.

Anything that needs real reshaping is **a dbt staging model in a pull request** — which is what DBT.md and ROADMAP.md Phase 5 already say the transform layer is for. Declarative mapping covers the easy majority; the rest goes through code review like code.

**There is never a plugin system here.** An org-supplied transform script is remote code executing in our build, with our credentials, producing the map a hiker navigates by. No amount of sandboxing makes that a good trade for the convenience it buys.

## 2. The contact

### A role address, not a person

`trails@nynjtc.org`, not the volunteer coordinator's personal mail. Volunteers turn over; the trail doesn't. Value #8 asks the project to "survive turnover in maintainers", and that applies to the *other* organizations' maintainers just as much as ours. A personal address is accepted but flagged at review with the reason.

### Verified, and re-verified

An unverified contact is worse than no contact — it makes us believe we can reach someone we can't, and the moment we need it is the moment their layer is broken. So: a confirmation link at registration, reusing the same verification flow AUTHENTICATION.md already specifies for email changes, and an **annual "is this still you?"** re-verification. A contact that goes unconfirmed doesn't silently rot; it visibly degrades, and the source's own state follows it down.

### What a contact hears about — and what it never hears about

Three tiers, deliberately unequal:

- **Breaking** — the endpoint is unreachable, authentication changed, or a layer that had 3,000 features returned zero. Email immediately, plus a tracking issue. This is time-sensitive because it means their data is about to stop reaching hikers.
- **Degrading** — schema drift (a field the field map depends on has vanished), a feature count that moved more than a threshold, a licence URL that now 404s. Weekly digest.
- **Informational** — aggregate hiker signal about their features ("11 reports this month say this water source is dry"), and freshness. Monthly, and opt-out-able. This is the tier most likely to be genuinely valuable to a club, and the least likely to be urgent.

**The firewall that matters: an org contact never receives raw hiker reports.** Those go through [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md)'s moderation queue and route by location via `MaintainerAssignment` — a mechanism that already exists and already knows who looks after which mile. Piping a blowdown report to a GIS inbox would bury the one message that matters (your feed is down) under a hundred that don't, and would forward unmoderated hiker text about places, and sometimes people, to a third party. Two pipes, different contents, no crossing.

**Volume is capped structurally, not by good intentions.** One tracking issue per source, **updated in place** — DATA_RELEASES.md's existing rule ("never a second issue, never a comment per day"), applied to a second producer. At most one email per source per week no matter how many times a nightly job fails. A weekly build that fails five times sends one message.

And to be explicit, because this project guards it hard: these are emails to organizations. The wrong-way alert remains the only push notification OurHike sends to a hiker.

### When nobody answers: quarantine, not deletion

A source whose endpoint has been broken for weeks with no reply should **not** disappear from the map. `discover_sources.py` already set this precedent — a source that vanishes from ATC's app is "kept, not deleted, with a warning", because that usually means the app changed, not that the data is gone.

The release machinery makes the humane answer nearly free. Every release folder is complete, and unchanged artifacts are copied forward server-side; **a quarantined source is indistinguishable from an unchanged one** as far as the build is concerned. Its last good bytes ship in the next release, and the verification battery's "no artifact present in the previous release is missing from this one" check passes without special-casing.

Two things keep that from becoming a lie:

- **The staleness has to be visible to the hiker**, not just to us — the "last confirmed" surface [DATA_NUDGES.md](DATA_NUDGES.md) already designs for aging POI data, not a silent copy-forward.
- **Quarantine expires.** After a bounded period a human decides retire-or-keep. Otherwise a layer gets copied forward for five years because nobody looked, which is the same failure as showing it fresh.

**There is now a shipped precedent for the general shape of this.** [MAP_OPTIONS.md](MAP_OPTIONS.md)'s live topographic sheet (2026-08-03) took a dependency on a donation-funded tile host with no SLA, and mitigated it structurally rather than by trusting it: one constant in one file, a standard schema, and a named drop-in replacement that needs no cartography changes. Every registered source is that same bet at smaller stakes — someone else's server, outside our control, that the map reads from. Registration should ask the same question that decision answered: *when this goes away, what is the swap, and is it written down?*

## 3. Taking in the new data

### Nothing a registration does can change a hiker's map

Worth restating as a property rather than a step, because it is the design:

```
org submits  →  probe  →  human review  →  bot opens PR against sources.json
                                                      ↓
                                        a person merges it   ← the only gate
                                                      ↓
                       weekly candidate build picks it up like any other source
                                                      ↓
                            verification battery  →  release PR  ← the second gate
```

The weekly build treats a newly registered source exactly like the twelve that are already there: fetch if the freshness marker moved, clip to the corridor, unify, export, hash, stage under `releases/<new>/`, verify over the public URL. There is no "new source" code path, which is the point.

### Size is a review criterion, not a discovery

An org can register a layer that would add hundreds of megabytes to a download hikers already weigh against phone storage. The probe reports transfer size, and a registration that would push an archive past its tier budget is flagged **at review**, against the real measured baselines (z11 ~64 MB, z12 ~314 MB, z13 ~1.18 GB). Value #8 is a hosting-cost argument and a hiker's-data-plan argument at the same time.

### Geometry scope, honestly bounded

Points and lines in v1 — points because `unify_poi` handles them today, lines because [`export_trails.py`](../pipeline/export_trails.py) does. **Polygons are deferred** ([LAND_OWNERSHIP.md](LAND_OWNERSHIP.md) is the one polygon design and it is Post-MVP with its own unmeasured size question).

**Rasters are out, and the project just spent a release learning why.** The size argument alone would be enough — an org's raster needs the whole mosaic/reprojection/tiling path, and that is the 1.18 GB archive, not a layer. But [MAP_OPTIONS.md](MAP_OPTIONS.md)'s 2026-08-03 build note is the better reason: a raster mosaic is "a picture of a map", with labels baked into the pixels at one scale, seams between quads of different vintages, and contours that cannot be recoloured — "not defects in the pipeline, they are what a raster mosaic is." Accepting registered rasters would be signing this project up to inherit that from every organization that offers one.

Following the `crossing` precedent — declared in `POI_TYPES`, shipped empty rather than faked — a registered source whose geometry we can't yet carry should be *recorded as registered and not exported*, rather than rejected and forgotten.

### Trust: claimed stewardship is not verified stewardship

Anyone can fill in a form claiming to maintain a stretch of trail, and this data is safety-relevant. So the registry carries the distinction rather than flattening it:

- **`authoritative`** — a verified steward for that geography. Verified means a human confirmed it, ideally against `trail_club_sections` or an existing `MaintainerAssignment`, not against the submitter's say-so.
- **`community`** — a real, identified organization publishing data about ground it doesn't manage. Useful, shipped, and labelled.
- **`unverified`** — registered, probed, not yet vouched for. **Does not ship to hikers.** This is the default, and a registration sitting here is a queue problem, not a data problem.

This maps onto the existing `CONFIDENCE_HIGH`/`CONFIDENCE_LOW` tiers in `poi_schema.py` rather than introducing a second, competing notion of trust — the same reason ATC's Communities layer is already `CONFIDENCE_LOW`.

### When two organizations map the same thing

They will. A club's own centerline will disagree with ATC's; two orgs will both put a shelter near the same spot, tens of metres apart.

**Do not average, and do not silently dedupe.** A midpoint between two reported water sources is a location that exists in neither dataset — value #4's exact failure mode, and worse than either input. `unify_poi` already makes ids `source:feature_id`, so both records survive with distinct identities and provenance intact; that part needs no change.

The precedence rule this recommends: prefer the steward with a `MaintainerAssignment` covering that mile — the app can already answer "who looks after this spot?" from a location and a date, and reusing it here is one query, not a new subsystem. Where there is a real conflict, **show one and disclose the other** ("ATC also maps a shelter 40 m north"), rather than picking silently. The honest-uncertainty pattern this project already uses for water reliability, applied to provenance.

## Data model sketch

Backend — the registration side:

```
Organization
  id, name, kind (club | agency | nonprofit | land_manager | other)
  homepage, region (free text, for a reviewer, not a query)
  created_at

  Recommendation, not a mandate: `clubs.organization_id` references this.
  A maintaining club is one kind of organization; a state park's GIS office
  is not a club, and MaintainerAssignment/SAYING_THANKS genuinely mean club.
  One nullable FK plus a backfill — not a rename of the existing table.

SourceContact
  id, organization_id
  role_label            "GIS team", "Trails Director"
  email                 a role address (see above)
  verified_at           null until the confirmation link is followed
  reverify_due          annual
  notify                breaking | digest | none
  (no phone; no personal name required)

SourceRegistration      the submission, not the source
  id, organization_id, submitted_by (Profile), submitted_at
  kind                  arcgis_feature_layer | arcgis_experience | http_file
                        | ogc_features | drive_folder | push_upload
  endpoint              a URL — never credentials
  declared              title, geometry kind, trail_id(s), licence, attribution
  field_map             declarative only
  freshness             how to ask "did this change?" — required
  probe_result          what our own fetch actually found (JSON)
  status                draft | submitted | probing | needs_info | approved
                        | rejected | superseded
  review_notes, proposed_pr
```

Pipeline — what an approved registration renders into, per `sources.json` entry:

```
  steward       "org:nynjtc"          stable id; resolves to the record above
  registration  "reg:0193…"           provenance, the job discovered_via does today
  kind          "http_file"
  licence       { spdx, attribution }
  field_map     { … }                 declarative
  freshness     { marker: "http_etag" }
  trust         authoritative | community | unverified
  state         active | quarantined | retired
```

Existing entries keep working unchanged: `provider: "ATC"` becomes `steward: "org:atc"`, and everything else they already carry (`discovered_via`, `notes`, `blaze_field`) stays exactly as it is.

## What this deliberately isn't

- **Not a live proxy.** We never serve an org's endpoint straight through to the app. Offline-first means data goes through the build; a live third-party dependency is a 404 on a mountain.
- **Not auto-publish.** Registration proposes. A merge releases. There is no urgency that justifies collapsing those.
- **Not a plugin system.** See above — no org-supplied code runs in our build, ever.
- **Not credential custody.** We do not hold an organization's database passwords or OAuth tokens on their behalf.
- **Not a map hosting service.** "Upload your PDF map and we'll host it" is Avenza, and Avenza shutting down is why this project exists. This registry ingests data OurHike renders in its own map; it does not become a place other people's maps live.
- **Not a governance body.** Deciding whose data is authoritative where is a trail-community question. This gives that decision a place to be recorded — it does not make it.

## Eventually: the much larger app

Three stages, and the honest thing to say is that only the first is designed here.

1. **Today's shape, generalised.** One registry, many organizations, humans still merge. Still A.T.-shaped: one corridor, one download. Everything above.
2. **Multi-trail.** `trail_id` stops being decoration. Corridors become plural, and the download-chunking question TECHNICAL_ARCHITECTURE.md already has open — "this only works if hiker downloads are chunked […] that chunking scheme isn't decided yet" — gets harder rather than easier, because the chunks are now also *whose*. That question should be decided once, and this is a second reason to decide it.
3. **Any club stands up their own trail on shared infrastructure.** Value #7's "could another club pick this up with minimal friction" made literal rather than aspirational.

What stage 3 needs that this document does not cover: per-organization admin UI, per-trail moderation queues and moderator roles, storage and cost accounting per organization (someone pays for the bytes), and a real governance answer to precedence. Naming them is the useful thing here; designing them from a document written before the first outside organization has registered anything would be inventing requirements.

## Do this part first

The subset worth doing well before any form exists, because it costs little and pays immediately:

**Give the twelve existing entries a real steward, a licence field and a contact.** ATC is already the de facto registered organization; recording it in the shape above turns [#98](https://github.com/OurHike/OurHike/issues/98) and the unconfirmed ATC terms from two one-off unknowns into two rows with an empty required field — which is a question someone can answer, rather than a thing everyone remembers is unresolved. It also proves the schema against real data before an outsider depends on it.

## Open questions (for you, not decided here)

- **Who reviews.** The gate is a human merge, and today that is whoever runs this repository. That does not scale past a handful of organizations, and per-region or per-trail reviewers tied to `Profile.role` are the obvious direction — but that is a governance decision about the project, not a data model.
- **Whether an org signs in at all.** AUTHENTICATION.md notes Supabase supports SAML/OIDC SSO on a paid tier "if/when a real need to federate with an external club or organization's identity system shows up." A registering GIS staffer is that need arriving. Whether it justifies the tier depends on how many organizations there actually are — worth revisiting with a real number rather than now.
- **Generalising `Club` into `Organization`.** Recommended above with a migration that is genuinely small, but it touches `MaintainerAssignment` and [SAYING_THANKS.md](SAYING_THANKS.md)'s attribution path, and it is the kind of change better made once, deliberately, than twice.
- **What `push_upload` costs to operate.** Per-org R2 prefixes, quotas, and what happens when an org pushes 4 GB. Unmeasured, and the answer probably shapes whether it is offered to everyone or only on request.
- **Whether a registration expires.** An organization that registers a source and disappears leaves data ageing in the map behind a quarantine timer nobody set. Bounded above; the bound itself is a judgement call about how long a club's silence should be given the benefit of the doubt.
- **Drive folder access mechanics** — API key versus OAuth, flagged unverified above. If it needs OAuth, `drive_folder` should probably not exist and `push_upload` should be the answer for that whole tier of organization.

## Related: reused elsewhere

[../pipeline/DBT.md](../pipeline/DBT.md) and [#100](https://github.com/OurHike/OurHike/issues/100) are the other half of this: the registry supplies the rows, dbt's staging models absorb the sources whose shape a declarative field map can't express. Neither makes the other unnecessary.

[#99](https://github.com/OurHike/OurHike/issues/99) (expanding the unified POI schema beyond its first slice) becomes considerably more urgent once sources arrive from organizations who did not read `poi_schema.py` before deciding what to call their columns.

[PRICING_MODEL.md](PRICING_MODEL.md)'s regional pass is priced on "dozens of trails beyond the A.T." existing. This is the mechanism by which they would.
