# Getting a published data fix onto a phone that already has the app

Companion to [../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md), which owns how
data is published, and to [../RELEASING.md](../RELEASING.md), which owns how code ships.
This one owns the step neither of them had: **what happens after a correct release exists
and a hiker is still holding the old one.**

**Status: designed and built, 2026-08-21** ([#919](https://github.com/OurHike/OurHike/issues/919)).
Written alongside the code rather than before it, which is a deviation from this project's
usual convention and worth naming: the four decisions below were taken by the maintainer
in one sitting, and the value of writing them down is that they are *decisions* — a later
reader can disagree with any of them on the merits, which they cannot do with behaviour
inferred from code.

## 1. The defect this ends

A phone that finished one download never fetched another. The whole of the decision was
`useTrailData.ts`:

```ts
if (await haveTrailData()) return
```

and `haveTrailData()` asked whether there were trail lines and whether the last download
completed. It never asked **which** release, and nothing stored could have answered — the
data keys held bytes and a completion flag, no version, no hashes, no date. There was also
no way out by hand: `deleteTrailData()` existed and had no caller outside its own tests.

**Measured, not imagined.** [#749](https://github.com/OurHike/OurHike/issues/749) gated OSM
water on whether a hiker could walk to it. The gate shipped, the bucket served the corrected
layer, and every installed phone went on drawing the layer built before it: 1,535 ungated
points, 1,159 of them more than five miles from anything a hiker walks, the farthest 29.9 mi
— drinking fountains in Manhattan, drawn in the style that says *there is water here*.

The pipeline was fixed. The publish was green. The hiker still had the old answer.

## 2. What a refresh costs

Measured 2026-08-21 against the live bucket, bytes on the wire with `Accept-Encoding: gzip`:

| | gzipped |
|---|---|
| one `poi_*.geojson` | ~0.10 MB |
| all eight `poi_*.geojson` | 0.67 MB |
| `trails.geojson` | 4.14 MB |
| `elevation_profile.json` | 0.92 MB |
| **the whole vector set** | **5.78 MB** |
| the six `*.pmtiles` archives | 2.89 GB |

Those two orders of magnitude are the whole design. 5.78 MB is worth asking a hiker about;
2.89 GB is not something to re-fetch because a description changed.

## 3. The four decisions

Taken by the maintainer on 2026-08-21, in answer to the questions #919 left open.

### 3a. What makes an update safe: severity computed per release — *and the hiker is always asked*

`publish.py` diffs each artifact against the copy it is replacing and grades the change
([`lib/data_change.py`](../pipeline/lib/data_change.py)):

- **`routine`** — only additions and attribute edits. A new privy, a corrected shelter name.
- **`consequential`** — a feature was removed or its geometry moved.

**The grade decides what the prompt says, never whether it appears.** Nothing is replaced
without being asked, for either grade. That is the decision, and the cost of it is real and
worth stating: a hiker who never taps *Update* keeps the old map, which is the failure this
whole mechanism exists to end. It is accepted because a map that rearranges itself under
somebody standing at a junction is the worse of the two — and because "not now" is
remembered against **one version**, so the next release asks again.

**A change nobody could grade is `consequential`, not `routine`.** An artifact whose shape
the differ does not understand, previous bytes it could not fetch, a phone more than one
release behind: all take the louder grade. This is CLAUDE.md's rule that an honest unknown
outranks a confident answer, applied where the confident answer would be "nothing much".

### 3b. When: on launch, when online

Beside the `conditions/*.json` refresh that already works this way
(`useConditions.ts`) — one `latest.json` read, the same 3.5 KB the launch fetch pays anyway.

The cost, stated: a phone that is never relaunched is never asked. On a phone that is a
non-case, and the alternative — checking mid-session — is what puts the prompt in front of
somebody at the moment they are reading a fork.

### 3c. The archives do not take part

Vector only. The 2.89 GB of `*.pmtiles` stay the manual, user-triggered download they are
today.

**What this leaves open, deliberately:** a basemap tier that is genuinely wrong still has
no route to a phone. That is a real gap and not an oversight; it wants its own design,
because the answer is either a notification with no download attached or a wifi-gated
transfer, and neither is this change.

### 3d. Built against `latest.json` as it stands; the `DATA_RELEASE` pin comes later

RELEASING.md §10 plans `client/src/lib/dataRelease.ts`, a constant naming which published
dataset a build reads. Pinning and refreshing point in opposite directions and whichever is
built second inherits the first's constraints. The order chosen is **refresh first**: nothing
built here has to be undone, and when the pin arrives it decides *which manifest is read*,
inside which this mechanism operates unchanged.

## 4. How it works

**Publisher.** For every artifact whose sha256 differs from what is live, and whose key ends
`.geojson` or `.json` and is not under `conditions/`, `publish.py` fetches the currently
published copy, decompresses it, and grades the difference. The verdict goes into
`latest.json` beside the hash. Two more fields ride along:

- `previous_version` — the version every `change` block is relative to. A release describes
  exactly **one hop**, and this is what lets a phone further back know it is reading somebody
  else's transition rather than being handed a caveat it cannot check.
- `transfer_bytes` — the gzipped size, which is what a hiker actually spends. `size_bytes` is
  the decoded size and about 3× larger for the text artifacts; showing that as the cost would
  be a plainly wrong number in front of somebody deciding whether to pay it.

The diff runs **before** the uploads, because the upload overwrites the side being diffed
against. A failure to describe never fails the publish: the data is fine, and an ungraded
change is `consequential`, so the phone still asks.

**Phone.** `downloadTrailData` records which version it fetched and each artifact's hash
(`dataRefresh.ts`, `ourhike:trail-data-release`). On launch, when online, `useTrailData`
reads `latest.json`, compares, and offers what differs. Accepting re-downloads the whole
vector set rather than the changed artifacts alone — 5.78 MB against ~0.67 MB for a POI-only
release — because that buys the all-or-nothing commit `downloadTrailData` already makes. A
phone holding half of one release and half of another is a state nothing else in this app
has to reason about and nothing should have to.

**The prompt** is a row at the foot of the map column, beside the ATC new-alerts row and
borrowing its geometry (`chrome/TrailDataUpdate.tsx`). It says what changed, what it costs,
and cautions about mobile data when the update is over `LARGE_UPDATE_BYTES` and the
connection is not known to be wifi. An unknown size counts as large — the only direction
that cannot quietly spend somebody's allowance.

## 5. What this does not do, and what would settle it

- **It cannot describe a hop of more than one release.** The phone is told so rather than
  told a number. Cumulative descriptions would need the publisher to keep a chain, which is
  a bigger thing than the failure warrants today.
- **`spurs.json`, `elevation_profile.json` and `trail_miles.json` are always `consequential`.**
  They are not FeatureCollections, so the differ cannot identify features inside them and
  refuses to guess. (`trail_miles.json`, #1192, only ever changes with `trails.geojson`,
  whose own diff describes the change; the sidecar adds nothing a hiker would read.)
  A structural diff for them is worth adding the day somebody decides what "changed" means for
  an elevation profile.
- **`LARGE_UPDATE_BYTES` is derived, not measured against hikers.** One megabyte is the gap
  between a POI-only release (0.67 MB) and one that moved the trail lines (4.81 MB more), so
  it separates the two kinds of release that actually occur. Whether a hiker on a mobile plan
  agrees with where it sits is not something this project has asked anybody.
- **Nothing here has run against a real multi-release history.** The classification is tested
  against synthetic pairs and the wiring against moto; the first real evidence will be the
  first publish after this lands, and the counts it puts in `latest.json` are worth reading
  before trusting the sentence a hiker sees.
