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
- **Never the original file — a sized thumbnail or nothing.** A Commons original is a full-resolution camera file, routinely 3–15 MB; the card's slot is 264 CSS pixels wide. The fetch asks for a 640px-wide rendering (`iiurlwidth`) and takes that `thumburl` — as built it stores the URL; per "Where the bytes live" below it will store our own mirrored copy of those bytes. Either way there is deliberately **no fallback to the original**: filling a thumbnail-sized box with a multi-megabyte download on a hiker's data plan is value #8's exact argument against itself.

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

### OurHike is not a photo archive, and will not pretend to be one

**Decided 2026-08-07: personal photos are never backed up to OurHike.** Not as a paid tier, not as a convenience, not later. The reasoning is worth keeping because it looks at first like a hiker-hostile choice and is the opposite:

An app that stores the only copy of someone's memories has taken on a duty it is not built to discharge — durability, migration, export, an answer when a bug eats a year of photos, and a promise that outlives the project. Value #7 asks whether a club could inherit this; inheriting somebody's photo library is a different and much heavier thing than inheriting a map pipeline. Offering backup would also compete, badly, with the backup the hiker already has and which is better than anything this project would build.

**What replaces backup is not holding the original at all.** The photo's home is the hiker's own library — camera roll, iCloud, Google Photos, whatever they already trust — and OurHike keeps a **640px derived rendering for offline display**: a cache, sized for the slot, not a copy of the photograph. Three things follow, and they are the whole answer to "avoid loss without becoming an archive":

- **There is nothing here to lose.** Losing the phone loses a thumbnail; the photograph is wherever the hiker keeps photographs, covered by whatever backs that up.
- **The app says which is which**, in the photo strip rather than a settings page nobody opens: this is a copy, your library has the original.
- **A hiker deleting the original is not our emergency.** The rendering can stay until they clear it, and clearing it is one action that never touches their library.

The one thing this genuinely gives up is a hiker who deletes a photo from their library and expected OurHike to still have it in full resolution. That is the correct thing to give up: the alternative is being the archive, and the moment this app is somebody's archive it has acquired an obligation it should never have taken.

---

### Bringing photos in from a library, and matching them by where they were taken

The version of this that everyone imagines first — connect Google Photos, let the app walk the library, fill every card automatically — **is no longer possible, and it is worth knowing that before anyone scopes it.** Google [removed the broad Library API scopes on 31 March 2025](https://developers.googleblog.com/en/google-photos-picker-api-launch-and-library-api-updates/): `photoslibrary.readonly`, `photoslibrary.sharing` and `photoslibrary` are gone, calls relying on them return `403 PERMISSION_DENIED`, and [the Library API now reaches only media the calling app itself created](https://developers.google.com/photos/support/updates). The replacement is the **Picker API**, where selection happens inside Google Photos and the app receives only what the hiker picked.

The mobile platforms moved the same direction independently: iOS uses `PHPicker` with limited-library selection, and [Capacitor's Camera plugin](https://capacitorjs.com/docs/apis/camera) uses the Android Photo Picker for gallery selection. On Android, `ACCESS_MEDIA_LOCATION` is a separate runtime permission that exists specifically because **the OS redacts EXIF location by default** — the platforms already treat photo coordinates as the sensitive thing this doc treats them as.

So full-library sync is closed. **Batch selection is open, and it keeps most of the magic:**

1. A hiker finishes a section and taps *Add photos from my hike*.
2. The native picker opens. They multi-select — a day's photos, or a whole trip.
3. **Matching runs on the device.** EXIF GPS against corridor POIs, with capture time as the second signal: a burst of photos minutes apart is one stop, and a photo with no usable GPS can still be placed if the hiker's planned hike (`lib/plannedHike.ts`) says roughly where they were that afternoon. Tree canopy makes A.T. GPS unreliable in exactly the places this matters, so time is not a tiebreak — it is half the mechanism.
4. The app reports what it found — *47 of these matched 23 waypoints* — and every match is a **suggestion the hiker confirms or corrects**, never a silent assertion. A wrong match on a hiker's own card is cheap and instantly obvious to the one person who knows; the confirm exists so that cheapness never leaks into a share.

This is better than full-library sync on the merits, not just the only thing left. The hiker hands over a batch rather than their life, the grant is legible at the moment it happens, and nothing background-scans a library forever.

Three constraints to design against rather than discover:

- **Scope the work.** Matching a thru-hike's photo count against every corridor POI is real computation; bounding it to the planned hike's date range and the corridor cuts it to something a phone does without heating up.
- **iCloud and Photos-cloud offloading.** A selected photo may not be on the device at all — [Capacitor has a standing issue where this errors](https://github.com/ionic-team/capacitor-plugins/issues/1807) — so importing a trip can mean pulling originals over cellular. That is a data-plan cost the hiker must be told about before it is spent, not after, and it is the same consent principle as the archive-size button.
- **The permission ask is specific or it is refused.** "Let OurHike read your photo locations, to match your pictures to places on the trail" is answerable. A generic library-access prompt from a hiking app is the kind of thing that gets declined, and should be.

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

**That masking and CC BY-SA's attribution requirement do not conflict, and the reason is worth recording** because it looks like a contradiction on first reading. Under CC 4.0 the attribution owed is the attribution *the licensor asked for* — the licence explicitly accommodates a creator who wants to be credited pseudonymously, or not named at all. A hiker sharing under the anonymity window has requested exactly that, so masking the name is honouring the licence rather than breaching it. What this does require is that the request is **recorded with the photo** alongside its licence, the same way a Commons file's author string travels with it: a downstream reuser needs to be able to see how to credit it correctly, and "credited as *Sawyer*, name withheld until 12 September by the photographer's request" is an answer. An unrecorded masking would leave a reuser unable to comply at all.

---

## Cross-cutting rules

### Privacy: GPS never leaves the device

**The rule is not "never read the location" — it is that the location never leaves the phone.** An earlier draft of this doc said the app should not look at a photo's EXIF GPS at all, on the grounds that the POI association comes from the card the hiker tapped. Bulk import from a photo library (below) is built entirely on reading that GPS, so the rule needed restating rather than quietly breaking:

- **On the device, reading EXIF GPS is fine and is the whole mechanism.** It is the same thing the phone's own Places album does with the same bytes, and nothing is transmitted.
- **Before any upload, GPS and device identifiers are stripped** — on the device, never server-side, because "we will remove it after you send it" is not a promise worth making. A published photo's coordinates pin exactly where someone slept.
- **Capture date is kept** through both: it is what the card prints, and the honesty rule needs it.

This is the same instinct that already governs the pipeline, where `fetch_opentrail.py` drops user comments as "personal contributions from named individuals — a consent concern separate from and in addition to the licensing question." A photo carries more of that than a comment does.

Photos of identifiable people are a moderation matter and a share-sheet warning, not something a client-side check can solve. The queue exists; this is one more thing it looks at.

### Licence: shared photos are CC BY-SA 4.0

**Decided 2026-08-07.** A shared photo is released under **Creative Commons Attribution-ShareAlike 4.0**. The photographer keeps copyright; the licence is what lets the app, the site, and the club that inherits both show it.

Why that licence rather than a bare display grant:

- **It is the same licence this project already accepts from Commons**, so the credit line, the attribution rules and the 4.0-and-newer reasoning are one code path rather than two.
- **Share-alike survives the handover.** Value #7 asks whether another club could pick this project up; a display grant to "OurHike" is a licence with a named beneficiary that has to be re-argued the day the name changes. CC BY-SA has no such dependency.
- **It closes a loop.** Photos hikers contribute under CC BY-SA 4.0 are exactly what Wikimedia Commons accepts, so the corpus this project builds could flow back upstream instead of dead-ending in one app's database. That is value #3 doing real work rather than being a slogan.

**The consequence that must be said out loud, at the moment of sharing: a CC licence cannot be revoked.** This interacts directly with the withdrawal design below and softens it, so neither the doc nor the share sheet may be vague about which half is which:

- **What a hiker can always do:** ask OurHike to stop showing the photo. That is a product promise and it is kept — see the storage consequence below.
- **What nobody can undo:** the licence itself, as to copies already made under it. Someone who took the photo under CC BY-SA before the withdrawal keeps that right, and no takedown reaches them.

The share sheet says this in one plain sentence rather than burying it, because a hiker who learns it afterwards was misled by omission. It is also the strongest argument for the moderation step: an irrevocable licence on a photo containing someone else's child is a worse mistake than a display grant on the same photo.

### Withdrawal, and where that puts the bytes

Release folders under `releases/` are written once and never overwritten ([DATA_RELEASES.md](../pipeline/DATA_RELEASES.md)), and copy-forward is a real `copy_object`, so a photo baked into a published release could never be withdrawn from the releases already serving it. **Therefore community photos are served from the backend, not baked into release artifacts.** A withdrawal then removes the photo from the surface that serves it — a promise the app can keep. This is a genuine architectural consequence of a consent requirement, and the reason the community rung is not simply another pipeline artifact.

### Saying that the photo has been shrunk, and offering the real one

Every photo on a card is a 640px rendering of something larger. **The hiker is told that, and given a way to see the full thing** — value #4 applied to the app's own handling rather than only to its data.

Where it is said matters more than that it is said. A permanent caption under every photo is noise nobody reads, so the disclosure sits where a reduced copy could actually mislead:

- **On a hiker's own photo**, where the gap is largest and most personal — the strip says this is a copy and their library has the original, which is the same sentence that keeps the not-an-archive promise honest.
- **In the share flow**, because what other hikers receive is the reduced version, and a photographer should know what they are publishing before they publish it irrevocably.

And "see it yourself" costs nothing to offer, because in every case the real file is somewhere we are not holding it:

| photo | full-quality original is | how the hiker reaches it |
|---|---|---|
| their own | their photo library | open it there |
| a Commons photo | the Commons file page | the credit line already links it |
| a shared photo | the photographer's own library | theirs; other hikers get the rendering |

That table is the whole feature. The app never has to store a second copy to be honest about the first one.

### What the card renders, for all three sources

One credit line, one shape, whatever the source: who, under what terms, when. A Commons photo names its author and licence and links the file page; a community photo names a trail name (subject to the window) and the date; a hiker's own photo needs no credit at all, because they are looking at their own picture. The rule is that **the slot never shows a photo whose provenance it cannot state.**

---

## Where the bytes live, and what they cost

**Decided 2026-08-07: everything OurHike serves is in R2, no photo is ever hotlinked from anyone else, and no image is ever processed server-side.**

### Mirror Commons rather than hotlinking it

Shipping Commons thumbnail URLs was the first slice, and it is the wrong long-term answer for the reason SOURCE_REGISTRY.md already gives about upstream endpoints: *a live third-party dependency is a 404 on a mountain*. Hotlinking makes every waypoint card depend on `upload.wikimedia.org` being reachable and unchanged. The fetch therefore **downloads the 640px rendering and stores it in our own bucket**, and the artifacts point at our copy.

Two things this fixes at once. The card stops depending on somebody else's uptime — and we stop spending a nonprofit's bandwidth on our traffic. Wikimedia permits hotlinking, but a popular app pushing its image load onto Wikimedia is a cost externalised onto exactly the kind of organisation this project is supposed to be a good citizen toward. Serving it ourselves costs, per the table below, approximately nothing.

Licensing permits this and it is worth stating why rather than assuming: PD and CC0 impose no condition, and CC BY / CC BY-SA permit redistribution provided attribution travels with the copy — which the credit line already does. One consequence to honour: **our 640px rendering of a CC BY-SA original is a derivative and carries the same licence.** OurHike claims nothing over it.

### This needs two deliberate changes to the R2 rules, which is the gate working

Checked against `lib/r2_keys.py` rather than assumed, and it refuses today:

- **`.jpg` is not a served extension.** The set is `geojson`, `fgb`, `json`, `pmtiles`, `tif`, and a JPEG key is rejected outright.
- **There is no prefix for photos.** Only `releases/` and `_internal/` are declared, and `_internal/` explicitly means "nothing here is a download", which photos are.

Neither is a blocker; both are the gate doing its job. R2_LAYOUT.md anticipates exactly this — *"Adding a format is one line in the validator, reviewed alongside the artifact that needs it"* — so mirroring photos means adding `jpg` to `ALLOWED_EXTENSIONS` and declaring a photo prefix with its retention rule, in the PR that needs them. **The prefix must not be `releases/`**: release folders are written once and never overwritten, and a community photo that lands in one could never be withdrawn, which is the consent requirement above. Photos live under a mutable prefix the backend can delete from.

Note also what "everything in R2" does and does not mean. R2 holds **bytes**; photo metadata, moderation state and the withdrawal flag stay in Postgres, because those are records to query, not objects to serve.

### Reduce on the phone, never on a server

**Every user-contributed photo is resized on the device before it is uploaded.** Commons photos arrive already rendered by Wikimedia's own thumbnailer, so nothing in this feature ever runs an image pipeline of our own.

That is a cost decision as much as an architectural one. Storage and egress are close to free; **server-side image transformation is the one part of a photo feature that genuinely is not**, because those services price per image rather than per byte. Pushing the resize onto the device that already holds the photo keeps the whole feature inside the free tier and removes an entire class of running cost before it exists.

### What it actually costs

Prices from [Cloudflare R2](https://developers.cloudflare.com/r2/pricing) — $0.015/GB-month, $0.36 per million reads, **$0 egress**, with 10 GB storage and 10M reads free monthly. Volumes are scenarios; 47 KB per 640px photo is the same estimate the size budget uses, not a measurement.

| shared photos stored | storage | R2 |
|---|---|---|
| 10,000 | 0.45 GB | $0 (free tier) |
| 50,000 | 2.2 GB | $0 (free tier) |
| 50,000 + 1600px copies | 16.6 GB | $0.10/mo |

| devices served | fetches | egress | R2 | Supabase |
|---|---|---|---|---|
| 5,000 | 750k | 34 GB | $0 | $0 (inside Pro's 250 GB) |
| 25,000 | 3.75M | 168 GB | $0 | $0 (inside Pro's 250 GB) |

Mirroring Commons adds a few hundred MB and stays inside the same free tier.

**The one case where the provider choice is not a wash is the offline bundle** — ~137 MB per device, so 5,000 downloads is 669 GB and 25,000 is 3.3 TB. On R2 that is $0; on egress-billed storage it is roughly $38/mo and $279/mo respectively. That is the concrete argument for R2 in the [#89](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/89) storage decision, and it is why that decision should be made once for all three photo kinds.

**Money is not the constraint on this feature.** Moderation is: ten thousand shared photos is ten thousand human decisions on volunteer time, and that is what will limit how fast this can grow.

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

- **Offline delivery.** Mirroring into R2 (above) fixes reliability, not offline: the card still fetches a URL when it renders, and offline it falls back down the ladder. Photos are enhancement and never safety-relevant, so that is an acceptable resting state — the opt-in bundle in the size budget is the full answer, and it is the one case where R2's zero egress is worth real money.
- **A premium tier for higher-quality photos — raised 2026-08-07, and the recommendation is not to.** Four things argue against it, and they should be weighed together rather than dismissed one at a time:
  1. **There is no cost to recover.** Even 50,000 photos with 1600px copies alongside is $0.10/month, and egress is free. A paywall normally recovers a real expense; here there isn't one to point at.
  2. **[PRICING_MODEL.md](PRICING_MODEL.md)'s pricing value #3 is directly on point** — *"Contribution stays free… A two-sided resource doesn't get better by charging the side that supplies it"* — and that doc already extends it past safety to community contribution features, because *"paywalling the supply side of a shared resource undermines the resource itself."* Photos are the supply side. Charging hikers to see hikers' donated photos properly is the cleanest example of the thing that rule exists to prevent.
  3. **CC BY-SA makes it leaky anyway.** A paying hiker may redistribute freely, and the licence forbids applying technological measures that restrict what it grants. A quality paywall over CC content is a speed bump with an ethical cost attached.
  4. **It would reverse the not-an-archive decision**, since offering higher quality means storing a second larger copy of everything.
  
  **If a photo-shaped premium is wanted, the defensible unit is the offline photo pack**, not photo quality: a convenience with a real download cost to the hiker's own data plan, which is exactly pricing value #5's *"pay for convenience and connection, not facts."* Photos are never safety-relevant, so gating that breaks no safety rule. A maintainer's call either way; recorded here with a recommendation rather than decided.
- **Whether an irrevocable licence needs a cooling-off period.** CC BY-SA 4.0 is settled, but a hiker who shares a photo and regrets it ten minutes later cannot un-license it. A short window before a shared photo becomes visible to anyone — hours, not days — would make almost every regret recoverable at the cost of a delay nobody would notice, since moderation already sits in that path. Worth deciding when the share flow is built, not now.
- **Whether a photo whose match was never confirmed may be shared at all.** The safe answer is no: an unconfirmed match is the app's guess, and a wrong guess published under an irrevocable licence with a trail name attached is the failure mode worth spending a tap to avoid. Recorded here rather than decided because it is really a question about the share flow's shape.
- **Whether the Google Photos Picker API is worth integrating at all**, given the native pickers already reach the same photos for anyone whose library is on the phone. It matters for hikers whose photos live only in Google Photos, which is a real population, and it is a separate OAuth integration for a second path to the same feature. Sequence it after the native path works.
- **Whether a club can add photos directly.** A maintaining club is the most authoritative photographer of its own shelter and has no obvious route in here except as an ordinary hiker. Overlaps [VOLUNTEERING.md](VOLUNTEERING.md)'s club-side surface.
- **Wiring the Commons fetch into `publish-vector-data.yml`.** Deliberately not done: it would couple every data release to Commons API availability. The fetch is run by hand before an export, and the export ships cleanly without it.
- **A registry row for Commons.** When SOURCE_REGISTRY.md's licence fields land on `sources.json`, Commons gets an entry (`trust: community`, per-photo licences noted as riding the features). Until then, CONTRIBUTING.md's licence note plus this doc are the record.

**As built today, nothing here adds a bucket key** — the photo fields ride inside the existing `poi_*.geojson` artifacts, and `data/raw/poi_images.json` is a local fetch artifact under the pipeline's gitignored `data/` tree, exactly where R2_LAYOUT.md says a mirror of a raw upstream pull belongs. Mirroring the image bytes changes that, which is why it needs the extension and prefix decisions recorded above rather than a script inventing a key on its first upload.
