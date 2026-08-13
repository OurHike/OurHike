# R2 bucket layout and key naming

Companion to [DATA_RELEASES.md](DATA_RELEASES.md) and [README.md](README.md)'s Publish
section. Those two own *when* data is published and *how the release mechanism works*.
This one owns a narrower question, asked every time somebody adds an artifact: **where
does it go in the bucket, and what is it allowed to be called.**

The rules below are enforced by [`lib/r2_keys.py`](lib/r2_keys.py), which `publish.py`
runs over every key before its first upload of a run. Adding a rule here that the
validator does not implement is how this file starts lying; the two change together.

## Why a key is not a filename

Every object in this bucket is served publicly, and its key is the URL path. Three
things follow, and every rule on this page is one of them:

1. **A published key is permanent.** `publish()` merges manifests additively, so a name
   that is live stays live. Worse, `DATA_RELEASE` is compiled into the client and
   app-store builds cannot be forced forward — a phone that shipped in March asks for
   March's keys until its owner updates. A key cannot be renamed, only joined by a
   sibling and served alongside the mistake forever.
2. **The same string is typed in three places** — `publish.py`'s artifact names,
   `client/src/lib/config.ts`, and (once built) `verify_release.py`. A mismatch is not a
   build error, it is a 404 on a mountain. `test_publish.py` already checks the tier
   mapping covers what the app offers, because a tier the app advertised and the bucket
   lacked has happened.
3. **Case and encoding are not forgiving.** R2 keys are case-sensitive and served as-is.
   `Trails.geojson` and `trails.geojson` are two different objects, and nothing in the
   stack will tell you which one you uploaded.

## What belongs in the bucket

Published map data, the manifest that names it, build metadata describing that data, and
the POI photos that data points at. That is the whole list.

The photos are the one payload here rather than a dataset, and they follow a different
rule from everything else because they are **content-addressed**: the key is the sha256
of the image bytes, so `photos/<digest>.jpg` never needs renaming (the thing this layout
cannot do), identical images shared by two waypoints are one object, and a client can
verify a download by hashing it against the key it asked for. They are also the one
hiker-facing thing in the bucket that gets **deleted** — a shared photo can be withdrawn,
which is why they are not under `releases/` and why no prune rule may treat them as
release output.

**What does not, and why it matters that it never starts:** user accounts, condition
reports, closures, comments and anything a hiker typed live in Postgres behind the
FastAPI backend. This bucket is world-readable with no auth in front of it, so an object
put here is published, not stored. Also never: credentials, mirrors of raw upstream pulls
(14 GB of USGS quads that re-fetch on demand — see `TECHNICAL_ARCHITECTURE.md`'s rule
about generated data), and anything whose licence has not been established
([CONTRIBUTING.md](../CONTRIBUTING.md)).

## Top-level prefixes

These are the places an object can be, and a new one is a design decision — recorded in
a design doc and added to `TOP_LEVEL_PREFIXES` — rather than something a script invents on
its first upload. The reason is retention: prune rules are written per prefix, so a prefix
nobody declared is a prefix no prune job knows to spare, and the failure mode is deleting
data a phone is pinned to.

| prefix | holds | mutable | hiker-facing |
|---|---|---|---|
| *(root)* | today's flat keys, plus `latest.json` | frozen; `latest.json` is the one mutable pointer | yes |
| `releases/` | one immutable folder per dated release, plus `index.json` and `pinned.json` | written once, never overwritten | yes |
| `_internal/` | build intermediates, keyed by release | rewritten per build | no |
| `photos/` | POI photos, one object per image, content-addressed | mutable: objects are added and deleted, never rewritten | yes |
| `originals/` | full-resolution originals of the photos above, content-addressed | mutable: objects are added and deleted, never rewritten | **no** |
| `conditions/` | published safety data — verified closures, verified reports, and the ATC's own trail updates | mutable: rewritten in place, daily | yes |
| `environments/` | one subtree per non-production environment, each holding a whole copy of this layout | as whatever it holds | to that environment's audience |

`releases/` and `_internal/` are the layout [DATA_RELEASES.md](DATA_RELEASES.md) designs.
That document owns the tree, the retention clocks and the migration — this one only says
what the segments may be called, which is why no prune rule is restated here.

**`releases/` is written now** (#500). Every publish that writes a new `latest.json`
version also copies that version's artifacts into `releases/<id>/`, writes a
`manifest.json` describing the folder, and appends to `releases/index.json`. The copies
are server-side, so a complete folder costs one `copy_object` per artifact rather than a
second upload of 1.6 GB. `latest.json` gained a `release` field naming the folder that
holds the same bytes, and is otherwise unchanged: **the root keys stay live and stay the
thing every client in the field reads.** That is deliberate rather than transitional —
`DATA_RELEASE` is compiled into app-store builds that cannot be forced forward, so moving
the flat keys is a change no phone already in the field could survive.

`_internal/` is still not written by anything. It holds build intermediates keyed by
release — per-cell mosaics and their state — whose producer is the raster build, and
creating the prefix without that would be a prefix a prune job knows to spare and nothing
ever puts anything in.

`conditions/` is the one prefix that is neither versioned nor content-addressed, and both
are deliberate ([../features/CONDITIONS_DELIVERY.md](../features/CONDITIONS_DELIVERY.md)).
A closure that has reopened must stop being served, which an immutable release folder
cannot express — it could only add a second answer beside the first. And the freshness a
hiker needs is *inside* the document, as `generated_at`, rather than in which folder it
came from: the client renders it as "as of &lt;date&gt;", which is what makes a day-old
baseline honest instead of misleading. It is on a different clock from the trail data —
daily, against a release cadence measured in months — which is the other reason it does
not live under `releases/`.

Retention is therefore trivial and needs no prune job: one object per artifact, overwritten
in place, never accumulating. That is the exemption to DATA_RELEASES.md's rule that a new
prefix needs a retention clock written for it — there is nothing to retain.

`originals/` is a preservation copy and never a download. `photos/` holds the 640px
rendering a card actually shows; this holds the full-resolution file it was reduced from,
so that losing an upstream does not also lose the photograph. The prompt was ATC's
photos, whose upstream is another organisation's Google Drive: those links are one
sharing-policy change away from 404, and without this the surviving copy of a 2015–2017
trail inventory would be a set of 640&times;427 thumbnails
([../features/POI_PHOTOS.md](../features/POI_PHOTOS.md)). "Served: no" is load-bearing
rather than descriptive — a multi-megabyte camera original is exactly what value #8 says
never to put on a hiker's data plan, and the client has no key shape that would reach one.

It shares `photos/`'s retention rule and its content-addressing, so the same digest names
both the rendering and the original it came from. It does **not** share the "never
personal photos" exemption: what may be archived here is what OurHike is licensed to hold
— ATC's and clubs' photos, and hikers' *shared* ones — never a hiker's private library,
which POI_PHOTOS.md keeps off this project's disks entirely.

`_internal/` is named to be obvious rather than to hide: on a public r2.dev bucket it is
readable by anyone. It means "nothing here is a download", not "nobody can see this".

`environments/` is the one prefix that holds no objects of its own. `environments/ua/` is this
whole page again — root keys, `releases/`, `photos/`, `conditions/`, all of it — belonging to
UA, and the same for any other environment
([../features/DATA_ENVIRONMENTS.md](../features/DATA_ENVIRONMENTS.md)). Two consequences follow,
and both are why it is a row here rather than a note:

- **Production is the root, and stays there.** It is not `environments/production/` and never
  will be, because point 1 above is not recoverable: every key live today is a URL some deployed
  build goes on requesting, and moving production under a prefix would rename all of them at
  once. The asymmetry is the rule rather than an exception to it — production is where the data
  already is.
- **The prefix is stripped before every rule on this page is applied.** `lib/r2_keys.py` takes
  `environments/ua/` off the front and then judges what is left exactly as it judges a
  production key, so the segment limit is counted from the environment's own root. Otherwise
  `environments/ua/releases/2026-08-13/trails.geojson` would be five deep and illegal while
  production's identical key was four and fine — a dataset that could not be staged in the place
  it exists to be verified.

An environment name is not something a script invents either: `lib/data_env.ENVIRONMENTS` is a
closed set of the three [../RELEASING.md](../RELEASING.md) §3 declares, for the reason this
table's own preamble gives about prefixes. `environments/uat/` is a typo, and the failure it
would otherwise produce is a complete, correct dataset in a tree nobody is looking at.

## Naming rules

Enforced, in `lib/r2_keys.py`:

- **Lowercase ASCII, digits, and `_` between words.** `elevation_profile.json`.
- **`-` is reserved for release ids** (`2026-08-07`, `2026-08-07-2` for a same-day
  rebuild), so a date can never turn up inside an object name by accident.
- **Exactly one extension, from the set the bucket serves** — `.geojson`, `.fgb`,
  `.pmtiles`, `.json`, `.tif`, `.jpg`. Adding a format is one line in the validator,
  reviewed alongside the artifact that needs it, rather than a `.tar.gz` appearing in a
  public bucket unremarked. `.jpg` arrived that way, for POI photos; there is
  deliberately no `.jpeg` alias, because two spellings of one format is two keys for one
  photo and neither can be renamed afterwards.
- **No version or date in the name.** Not `trails_v2.geojson`, not
  `trails_2026_08_07.geojson`. Which build an object came from is what the release folder
  says, and it is the only place that stays true.
- **No `new`, `old`, `final`, `tmp`, `temp`, `copy`, `draft`, `backup`, `test`.** Each of
  these was accurate the day it was uploaded and misleading a month later.
  `background_new.pmtiles` is not new. `latest.json` is exempt by name — it is the mutable
  pointer, and that is exactly what "latest" is banned for describing everywhere else.
- **At most four segments deep.** Deeper usually means a prefix is doing a manifest's job.

Not enforceable by a regex, and just as load-bearing:

- **Family first, variant last.** `poi_shelter.geojson`, not `shelter_poi.geojson`: a
  bucket listing is sorted, so the family prefix is what puts related objects next to each
  other. The zoom-capped variants read the same way — `background.pmtiles` beside
  `background_z11.pmtiles` and `background_z13.pmtiles`, `at_basemap_package.pmtiles`
  beside `at_basemap_package_z13.pmtiles`.
- **`_z<maxzoom>` is the variant suffix for a zoom-capped cut**, and it means the archive
  really is capped there — a download must be exactly the bytes its advertised size and
  published hash describe.
- **Name the thing, not the process that made it.** `dem.pmtiles`, not
  `export_dem_output.pmtiles`.
- **The extension is the real format.** A `.json` that is actually newline-delimited JSON
  will be opened as JSON by something, eventually, on a phone with no signal.

## Adding an artifact

1. The name follows the rules above and is chosen once. Take the extra minute: point 1 of
   [Why a key is not a filename](#why-a-key-is-not-a-filename) is not recoverable.
2. `publish.py` learns to collect it — a constant in `BACKGROUND_ARCHIVES` /
   `OFFLINE_SHEET_ARCHIVES`, or a branch in `collect_artifacts()`. Sidecars (build
   metadata, not downloads) go in `SIDECARS` instead, and the distinction is explained in
   that file, not here.
3. The client learns the same string in `client/src/lib/config.ts`. It is now spelled in
   two languages with nothing compiling both, so whatever holds them together has to be a
   test — the way `test_publish.py` holds the download tiers to the ones the app offers.
4. `tests/test_r2_keys.py` gains the name in the list of what the pipeline can publish, so
   the convention is checked against reality rather than against itself.
5. If it is not fetchable by every client that will ask for it, the client treats its
   absence as "this release has no such data" rather than as a failed download — the way
   `spurs.json` and `elevation_profile.json` are already handled in `lib/trailData.ts`.

## Enforcement

`publish.py` is the only thing in this repository that writes to the bucket — every
workflow's publish step runs it, and `R2_WRITE_ENABLED` gates that single step. One writer
means one enforcement point, so the check sits there: all keys of a run are validated
before a connection is opened, and an illegal name fails the run rather than leaving half
a release uploaded under keys nobody meant to publish.

What this deliberately does not do is validate the bucket's *existing* contents. Every key
live today passes, but the check is on what is about to be written, not on what is already
served — the point is to stop the next mistake, and a rule that failed the current bucket
would be a rename plan, which is the one thing this layout cannot do.
