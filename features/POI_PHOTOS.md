# OurHike — POI Photos (Feature Design Draft v2)

Companion to [FEATURES.md](../FEATURES.md), [WIREFRAMES.md](../WIREFRAMES.md) (the waypoint card, frames 6a–6b, whose photo slot this fills), [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md) and [OurHikeValues.md](../OurHikeValues.md). Pipeline mechanics — invocation, change-awareness, radii, throttling — live in [pipeline/README.md](../pipeline/README.md)'s "Fetching POI photos from Wikimedia Commons" section, not here; this doc is the sourcing decisions and their reasons.

**This doc owns one square of screen:** the photo slot on the waypoint card, and everything that can legitimately fill it. Three sources can, and they are not equals — a hiker's own photo of the shelter where they met their tramily is not the same kind of object as a stranger's geotagged upload, and the design turns on that difference rather than treating all pixels alike.

**Built today:** the Commons source only (`pipeline/fetch_poi_images.py`, the `photo_*` properties, the card's credit line). Everything under "Your own photo" and "Sharing" is designed here and not implemented — the design doc is the first contribution, per CONTRIBUTING.md.

---

## The precedence ladder

One slot, four possible occupants, in this order:

| | what fills the slot | where it lives | works offline |
|---|---|---|---|
| 1 | **Your own photo** of this place | your device | always |
| 2 | **The community default** — a shared photo a moderator promoted | backend | when cached |
| 3 | **A Commons photo** — openly licensed, recent, nearest | published artifact | URL only |
| 4 | **The category silhouette** | the app itself | always |

**Your own photo always wins, and nothing can displace it.** Not a better-composed community photo, not a fresher one, not a moderator. This is the whole point of the feature and it is value #1 stated as a render rule: a hiker's memory of a place outranks the app's opinion about it. The ladder falls through only downward, and rung 4 is a floor rather than a failure — it is what the slot has always shown and the honest answer when nothing better is true.

A hiker who has never added a photo sees exactly what ships today. The ladder adds occupants above the existing behaviour; it changes nothing below.

---

## Source 1: Wikimedia Commons (built)

### The two constraints that shaped it

- **Licence-first is non-negotiable.** CONTRIBUTING.md's rule — establish the licence before fetching, record it — rules out every "scrape the web for pictures" shortcut outright. Google Images results, AllTrails photos, Instagram embeds: all copyrighted, none OurHike's to redistribute, and an unlicensed photo baked into a data release is exactly the inherited liability the rule exists to prevent (value #7).
- **Recent and real.** A 2009 photo of a shelter that has since been rebuilt, burned, or grown a resident bear is worse than the honest silhouette — it is a small lie with a frame around it (value #4). The bar: a real camera photo taken within the last four years (`MAX_PHOTO_AGE_DAYS`). Four is a judgement, not a constant with a right answer — shelters change slowly, and the card prints the capture month either way, so the hiker sees the age rather than being protected from it.

### Why Commons, and what it costs

Commons is the one large photo corpus where every file carries machine-readable licence, author, and EXIF metadata, queryable by coordinates, explicitly built for reuse. Flickr's API needs a key and per-account terms; Openverse aggregates but launders the metadata this needs intact; everything else fails the licence-first rule. Commons it is — as a *source of individually-licensed files*, not as one licensed dataset:

- **Licensing is per photo, not per source.** One Commons file is CC BY 4.0, its neighbour CC BY-SA 2.0, a third public domain. So the licence record travels **on each exported feature** (`photo_license`, `photo_author`, `photo_page_url`), and the card renders the credit line — author, licence name, one link to the Commons file page — the same load-bearing-attribution posture as the map's ODbL line. Only public domain, CC0, and **CC BY / CC BY-SA at 4.0 or newer** are accepted. The version floor is not pedantry: 4.0's §3(a)(2) explicitly allows satisfying attribution via a link to a page carrying the required information (the file page does), while the 2.0/2.5/3.0 licences require the licence URI itself to ship with every copy — a term a one-link credit cannot meet, so those files are rejected the same way NC (breaks any future paid tier), ND (arguably forbids the card's crop) and GFDL (demands the full licence text) are: wholesale, rather than negotiated. The real coverage cost is Flickr-to-Commons imports (still CC 2.0-suite); accepting them later means carrying a licence-deed URL through the artifact and growing a second link in the credit, which is a deliberate follow-up, not an oversight. A CC BY photo with no attributable author is unusable, not "usable, uncredited".
- **"Real photo, recent" is enforced by one honest proxy:** the file must be a JPEG with a parseable EXIF capture date inside the window. Maps, SVG diagrams, screenshots and undated scans fail this naturally, with no image-content classification pretending to judge what the photo shows. The capture date ships with the photo (`photo_taken`) and the card shows the month.
- **Proximity is the match, and its limit is disclosed by design.** The nearest eligible file within a per-type radius wins. This will occasionally pick a photo of the view *from* the shelter rather than *of* it. The credit line linking to the file page keeps provenance one tap away; anything smarter (name matching, depicts-statements) is future refinement.
- **Never the original file — a sized thumbnail or nothing.** A Commons original is a full-resolution camera file, routinely 3–15 MB; the card's slot is 264 CSS pixels wide. The fetch asks for a 640px-wide rendering (`iiurlwidth`) and stores that `thumburl`. There is deliberately **no fallback to the original**: filling a thumbnail-sized box with a multi-megabyte download on a hiker's data plan is value #8's exact argument against itself.

### Expect very little of it

Desk research suggests A.T. coverage on Commons is thin — likely **well under 1% of corridor POIs**, possibly none, once the freshness bar and the 4.0+ licence floor both apply. That estimate has never been measured against the live API and should be, before anyone counts on this source. Either way the design holds: partial coverage is the intended state, the placeholder is the everyday case, and nothing implies completeness. The alternative — loosening the bar to inflate coverage — trades trustworthiness for decoration, which is value #4 backwards.

**This is also the argument for the other two sources.** Commons was never going to photograph a spring in Maine. Hikers walk past every one of these places every season.

---

## Source 2: your own photo

### What it is for

Not data collection. **A memento.** The framing matters because it decides the whole design: a hiker photographs the shelter where they met their tramily, the spring that saved a bad afternoon, the view they walked eleven miles for. That the photo also happens to be current, well-located ground truth is a happy side effect, not the reason to offer it.

Designing it as data collection produces the gamification playbook this project has already rejected — streaks, points, "you've contributed 12 photos this week", leaderboards. [DATA_NUDGES.md](DATA_NUDGES.md) rules those out explicitly under value #1, and they are ruled out here for the same reason. **Nothing ever asks a hiker for a photo.** The affordance sits on the card and waits.

### How it behaves

- **Added from the card.** The waypoint card gains an "Add a photo" affordance; camera or camera roll. The photo is associated with the POI the hiker tapped — never by reading the photo's own GPS, which matters for the privacy rule below.
- **Stored on the device, and nowhere else, until the hiker says otherwise.** Private is not a setting to find; it is what happens. IndexedDB, alongside the trail data and archives that already live there.
- **Resized on the device to the same 640px the Commons path uses.** One size, one code path for what the slot renders, and the phone never stores a 12 MB camera original to fill a 264px box.
- **Several per place, one on the card.** The card shows the chosen one; the rest sit behind it. Most recent first, because a hiker who photographs a shelter twice a year apart usually wants the new one — but they choose, and the choice sticks.
- **Dated like every other photo.** Capture date from EXIF where present, otherwise the date it was added, and shown as a month exactly as the Commons credit line does. The honesty rule does not soften because the photographer is the person reading it.
- **Works with no signal, always.** This is the one rung of the ladder that never needs a network. The bytes are already on the phone: a hiker on a ridge with no bars sees their own photo of the place they are standing in.

### The limit worth stating plainly

Device-local means **a lost or wiped phone loses the photos**, and a memento is exactly the kind of thing whose loss stings. That is a real cost of the private-by-default choice, not a detail to bury. Two honest mitigations, in order of how much they cost to build: the app says so where a hiker would first assume otherwise (the photo strip, not a settings page nobody opens), and private account-backed backup becomes the natural follow-up once accounts carry storage at all — see the open decisions.

---

## Source 3: sharing, and becoming the default

### Sharing is a separate, deliberate act

A photo is private when added. Sharing is a second decision, taken per photo, that a hiker can decline forever without the app mentioning it again. The share sheet says in plain words what happens: **other hikers will see this photo on this waypoint, attributed to your trail name.** Value #9's "clear expectations, no incentives to overshare" is the rule being followed, and it is the reason there is no "share all", no default-on toggle, and no count of how many photos anyone has shared.

Sharing queues in the existing outbox (`lib/outbox.ts`) like every other write, so tapping it on a ridge is fine — it leaves when there is signal.

### Becoming the community default

A shared photo enters the **existing moderation queue** ([REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md)'s `submitted | verified | resolved | dismissed`), and a moderator can promote one to the **community default** for that POI: rung 2 of the ladder, what a hiker with no photo of their own sees.

**Who decides is the whole question, and it is deliberately not a popularity contest.** No likes, no votes, no top-contributor list — the same prohibition DATA_NUDGES.md applies to freshness prompts, for the same reason. Votes would also answer the wrong question: the card needs the photo that best shows what the place *is like now*, and a crowd reliably prefers the prettiest sunset.

So: **hikers offer, moderators promote, recency orders the queue.** Recency is a real signal rather than a tiebreak — a two-month-old photo of a shelter carries information a three-year-old one does not — but it never auto-promotes, because "newest wins" is how one bad photo replaces a good one with nobody in the loop. A club that maintains a shelter is the right party to say which picture of it is the picture of it, which is also value #2 and value #7 pointing the same way.

Where no moderator has promoted anything, rung 2 is simply empty and the ladder falls through to Commons. Nothing degrades.

### Attribution, and the anonymity window

A shared photo is credited to the photographer's **trail name**, never a real name — the identity rule already settled in [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md), reused rather than reinvented. The **anonymity window** ([HIKER_SAFETY.md](HIKER_SAFETY.md)) applies to photo attribution exactly as it does to reports and comments: for `anonymity_window_days`, the name and exact date are masked on the public surface. A photo is a stronger location-and-time claim than a comment is, so exempting it would quietly undo the protection the window exists to provide.

---

## Cross-cutting rules

### Privacy: what is stripped, and why the association is not the EXIF

**GPS coordinates and device identifiers are stripped from the file on the device, before it is uploaded — never server-side.** The photo is already associated with a POI, because the hiker tapped that card; the EXIF location is redundant to the app and dangerous to publish, since it can pin exactly where someone slept. Capture date is kept: it is what the card prints, and the honesty rule needs it.

This is the same instinct that already governs the pipeline, where `fetch_opentrail.py` drops user comments as "personal contributions from named individuals — a consent concern separate from and in addition to the licensing question." A photo carries more of that than a comment does.

Photos of identifiable people are a moderation matter and a share-sheet warning, not something a client-side check can solve. The queue exists; this is one more thing it looks at.

### Licence and consent

The photographer keeps copyright. Sharing grants OurHike — **and the club that inherits it**, which value #7 makes a requirement rather than a nicety — a non-exclusive licence to display the photo in the app and on its site. Plain sentences at the moment of sharing, not a EULA nobody reads, and the grant is recorded with the photo the same way a Commons file's licence is: per photo, travelling with it.

**Withdrawal has to actually work, and that constrains where shared photos live.** Release folders under `releases/` are written once and never overwritten ([DATA_RELEASES.md](../pipeline/DATA_RELEASES.md)), and copy-forward is a real `copy_object`, so a photo baked into a published release cannot be withdrawn from the releases already serving it. **Therefore community photos are served from the backend, not baked into the release artifacts.** A withdrawal then removes the photo from the surface that serves it, which is a promise the app can keep. This is a genuine architectural consequence of a consent requirement, and the reason the community rung is not simply another pipeline artifact.

### What the card renders, for all three sources

One credit line, one shape, whatever the source: who, under what terms, when. A Commons photo names its author and licence and links the file page; a community photo names a trail name (subject to the window) and the date; a hiker's own photo needs no credit at all, because they are looking at their own picture. The rule is that **the slot never shows a photo whose provenance it cannot state.**

---

## Size budget

The numbers that decide whether photos are ever bundled rather than fetched. The JSON figure is measured against the real record shape; the image figures are arithmetic from 1.5 bits/pixel — a defensible rate for detailed foliage at good quality, but **not measured from real files**, and forest photos compress badly, so treat them as a floor.

| | 640px (card size) | 320px | 160px |
|---|---|---|---|
| per photo | ~47 KB | ~12 KB | ~3 KB |
| **5 per POI**, 3,000 POIs | **~670 MB** | ~170 MB | ~43 MB |
| **1 per POI**, 3,000 POIs | **~137 MB** | ~34 MB | ~9 MB |

Metadata is a rounding error: a photo record serialises to **478 bytes**, so even 15,000 of them is ~7 MB raw and ~1.4 MB as the gzipped client subset. Photos are the entire cost.

**Against this project's own numbers, bundling everything is out.** The corridor background archive is 314 MB at Standard and a phone at Standard holds ~790 MB in total ([pipeline/BASEMAP.md](../pipeline/BASEMAP.md)). Five photos per POI at card size would be **more than twice the background archive** and would make photos — an enhancement — the largest single thing the app puts on a phone. That is value #8 answered before it is asked.

Nor can it be shrunk away: the slot is 264 CSS pixels, so a DPR-2 phone needs ~528 device pixels to look crisp. 640px is already close to right-sized, and 320px is visibly soft. **~140 MB is roughly the floor for crisp offline photos at 3,000 POIs.**

What follows:

1. **Only the card photo is ever a candidate for bundling.** Photos 2–5 exist for a gallery someone deliberately opens — usually in town, with signal. Bundling them pays 5× for bytes almost never viewed offline.
2. **If photos are ever bundled, it is an opt-in package**, sized and offered beside the background sheets rather than landing unasked. `lib/packages.ts` already has that machinery and its "sizes are measured, never estimates" rule, and the Data Saver incident ([#122](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/122)) already settled the consent principle: the archive is a size on a button someone taps.
3. **A hiker's own photos cost nothing worth budgeting.** A thru-hiker who photographs 200 places holds ~9 MB. They should be visible in storage management for the same reason everything else is, not capped.
4. **A single bundled file is right for storage and wrong for access, unless it is indexed.** One artifact means one SHA-256 in `latest.json` — the verification model the whole download path already uses (#197) — and one IndexedDB blob rather than thousands of entries, which is exactly why trail lines are stored as one opaque Blob today. But an opaque lump means wanting twelve nearby photos costs the whole archive, and one corrected photo republishes all of it. The pattern that resolves this is the one already in use for tiles: **PMTiles — a single file with an internal index, served over HTTP range requests.** Note that `R2_LAYOUT.md`'s served-extension set is closed to `.geojson`/`.fgb`/`.pmtiles`/`.json`/`.tif`, so a `.zip` or `.tar` would not pass `lib/r2_keys.py` at all; widening it is a reviewed decision, not a side effect of needing somewhere to put bytes.

---

## Decisions deliberately left open

- **Offline delivery of Commons photos.** Today the artifacts carry photo *URLs* (Commons' thumbnail endpoint, which Wikimedia permits hot-loading); the card fetches one when it renders, and offline it falls back down the ladder. That is the right first slice — photos are enhancement, never safety-relevant — but it sits in honest tension with the "data goes through the build" posture (SOURCE_REGISTRY.md's "not a live proxy"). The full answer is the opt-in bundle above, which lands on the same storage decision as [#89](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/89)'s report photos. **Three photo kinds now converge on that one decision** — report photos, shared community photos, and any bundled Commons cut — and it should be made once. Whenever it is, `R2_LAYOUT.md`'s "Adding an artifact" checklist applies before the first upload: `poi_photos.json` is a legal key and reads family-first; an archive format is not.
- **Private backup of a hiker's own photos.** Device-local loses them with the phone. Account-backed private sync fixes that and costs storage, a sync path, and a clear promise that private means private even though the bytes are now on a server. Worth doing once accounts carry storage at all; not worth blocking the memento on.
- **Whether shared photos should carry an open licence.** Value #3 argues for CC BY-SA, which would let the data outlive the app entirely. Against: asking a hiker to CC-license a personal photo at the moment they share it is a real barrier, and a mixed-licence corpus is harder to reason about than a uniform display grant. Recommendation is the display grant above, with an optional "release this openly" for hikers who want it — but this is a maintainer's call, not a design detail.
- **Whether a club can add photos directly.** A maintaining club is the most authoritative photographer of its own shelter and has no obvious route in here except as an ordinary hiker. Overlaps [VOLUNTEERING.md](VOLUNTEERING.md)'s club-side surface.
- **Wiring the Commons fetch into `publish-vector-data.yml`.** Deliberately not done: it would couple every data release to Commons API availability. The fetch is run by hand before an export, and the export ships cleanly without it.
- **A registry row for Commons.** When SOURCE_REGISTRY.md's licence fields land on `sources.json`, Commons gets an entry (`trust: community`, per-photo licences noted as riding the features). Until then, CONTRIBUTING.md's licence note plus this doc are the record.

Nothing in the Commons feature as built adds a bucket key: the photo fields ride inside the existing `poi_*.geojson` artifacts, and `data/raw/poi_images.json` is a local fetch artifact under the pipeline's gitignored `data/` tree — which is exactly where R2_LAYOUT.md says a mirror of a raw upstream pull belongs, nowhere near a world-readable bucket.
