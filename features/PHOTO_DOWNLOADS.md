# OurHike — Downloading photos for a hike (v2 Research Spike)

Companion to [POI_PHOTOS.md](POI_PHOTOS.md) (which owns the photo slot, the sources that may fill it, and where the bytes live), [HIKE_PLANNING.md](HIKE_PLANNING.md) (which owns the plan this scopes to), [SEGMENTS.md](SEGMENTS.md) (which owns what a "section" is), and [../pipeline/R2_LAYOUT.md](../pipeline/R2_LAYOUT.md) (which owns `photos/`).

**This is a spike, not a build plan.** Its job is to name the decisions, answer the ones this repository already holds the data to answer, and leave the rest visibly open. [`pipeline/spike_photo_scope.py`](../pipeline/spike_photo_scope.py) is the runnable half.

**It does not re-open POI_PHOTOS.md's decisions.** Which photo fills a slot, whose it may be, what licence it carries and whether the bytes are mirrored are all settled there and unchanged here. This document owns exactly one question that document deliberately left open — *"Offline delivery… the card still fetches a URL when it renders, and offline it falls back down the ladder"* — and answers it.

Scope: **v2**. Nothing here is v1, and nothing here blocks launch.

---

## What is being asked for

1. **Photos on the phone before the hike starts**, because a photo fetched on a ridge is a photo that does not arrive.
2. **Three verbs** — download all photos, get an update, refresh.
3. **Each of them scoped to one hike or one section**, not only to "everything".
4. **Smart downloads that happen on their own** when the hike is planned within the next ten days, and on wifi.
5. **On wifi and within 100 miles, just refresh the photos.**

Items 1–3 are a feature. Items 4 and 5 are the interesting half, because both name a condition the app cannot currently evaluate, and one of them turns out to be measuring the wrong thing.

## What already exists, so this does not re-litigate it

| Already built | Where | What it gives this feature |
|---|---|---|
| Content-addressed photo bytes | `pipeline/lib/photo_store.py`, `photos/<digest>.jpg` | The key **is** the sha256 of the image. This is the single most load-bearing fact in this document — see Finding 3. |
| The photo reference on every POI | `pipeline/export_poi.py` → `photo_key` | The phone already holds the list of every photo it might want, in data it already downloaded. **No new artifact is needed.** |
| A resumable, verified download engine | `client/src/lib/archiveDownload.ts` | The pattern, and `lib/sha256.ts`'s chunked digest. Not the code — see Finding 3 on why photos need far less of it. |
| Streaming sha256 | `client/src/lib/sha256.ts` | Verification of a photo against its own key, with no manifest fetch. |
| An offline package catalog with measured sizes | `client/src/lib/packages.ts` | The Downloads screen's shape, its "sizes are measured, never estimates" rule — and an explicit warning that photos must **not** become an entry in it. See "Where this does not fit". |
| Storage durability and eviction reporting | `client/src/lib/storageHealth.ts` | Photos evict the same way the archive does, and the same screen has to say so. |
| Data Saver as a consent signal | `client/src/lib/dataSaver.ts` | The one network-condition field that works on every platform, and the project's established policy for it (#122). |
| The hike a hiker declared | `client/src/lib/plannedHike.ts` | Two numbers — `startMile`, `endMile`. The scope. Note what it does **not** have: a date. See Finding 5. |
| GPS → a mile on the trail | `client/src/lib/trailPosition.ts` | `locateOnTrail()`, for the proximity scope. It refuses beyond 3 miles off corridor, which Finding 6 has to work around. |

## The questions, and where each one stands

| # | Question | Status |
|---|---|---|
| Q1 | How many bytes is "all the photos", really? | **Answered: measured, and it is far smaller than POI_PHOTOS.md's size budget implies.** Finding 1. |
| Q2 | What is a "hike" or a "section" scope, mechanically? | **Answered: a mile range, and all five scopes are one query.** Finding 2. |
| Q3 | What do download, update and refresh each mean here? | **Answered: two verbs and a local check.** Finding 3. |
| Q4 | Can the app tell it is on wifi? | **Answered: no — not in the PWA, and on iOS not at all.** Finding 4. |
| Q5 | Is there a planned date to trigger a 10-day rule on? | **Answered: no such field exists, and making one mandatory would break the trigger.** Finding 5. |
| Q6 | Is "within 100 miles" the right proximity test? | **Answered: no. It is the right instinct measured against the wrong thing.** Finding 6. |
| Q7 | Can a PWA download while it is closed? | **Answered: not dependably, and not on iOS at all.** Finding 7. |
| Q8 | What is the worst *actual* section, in bytes — not the average one? | **Measurable, not yet measured** — `spike_photo_scope.py` answers it, and needs the fetched ATC data to run. |

---

## Finding 1 — the corpus has been measured since the size budget was written, and it is much smaller than the budget assumed

[POI_PHOTOS.md](POI_PHOTOS.md)'s size budget concluded *"Against this project's own numbers, bundling everything is out"* and put the floor for offline photos at *"~140 MB… at 3,000 POIs"*. That table is explicitly arithmetic — *"not measured from real files"* — and it has since been overtaken by measurement, in both of its terms and in opposite directions.

| | size budget's assumption | from measurement, 2026-08-09 |
|---|---|---|
| POIs with a photo | 3,000 (i.e. all of them) | **489** |
| bytes per 640px photo | ~47 KB (1.5 bits/pixel, stated as a floor) | **~145 KB** |
| whole trail, one photo per POI | ~137 MB | **~71 MB** |
| whole trail, every photo available | ~670 MB (at 5/POI) | **~189 MB** (at 1,301 photos) |

Where those numbers come from, so they can be re-derived rather than trusted:

- **489** is POI_PHOTOS.md's own measured ATC coverage — 270 of 280 shelters (96.4%) and 219 of 232 campsites (94.4%) — and it is the same 489 that document uses when it sizes the `originals/` archive. [#471](https://github.com/OurHike/OurHike/issues/471) measures the identical set independently.
- **~145 KB** is derived from [#471](https://github.com/OurHike/OurHike/issues/471)'s measured aggregate: 812 additional photos cost *"~118 MB more in R2"*. That is a bulk figure over real files, and it agrees with POI_PHOTOS.md's separately sampled single ATC rendering at ~114 KB. The 47 KB in the size budget is roughly a third of the truth, which is what "a floor" was warning about.
- **1,301** is 489 kept plus #471's 812 currently discarded.

**The comparison that decides the shape of this feature is with what the app already puts on a phone**, not with the old estimate:

| | bytes |
|---|---|
| Terrain package (`dem.pmtiles`, measured) | **607 MB** |
| USGS sheet, Standard tier | **314 MB** |
| A phone holding both, at Standard | ~790 MB |
| **Every photo on the trail, as published today** | **~71 MB** |
| **Every photo on the trail, after #471** | **~189 MB** |

**Every photograph on the Appalachian Trail is about one eighth of the terrain file the app already hands people, and 9% of what a fully-downloaded phone is carrying.** The conclusion that bundling everything is out was reached honestly against an estimate that happened to be wrong in both of its factors; the measured corpus says the opposite.

This does not make the ask redundant, and it is worth being precise about why:

- **Disk is not the constraint; the data plan is.** 71 MB on a hostel's wifi is nothing. 71 MB on a tethered phone at a trailhead is a real cost, and value #8 plus the Data Saver incident ([#122](https://github.com/OurHike/OurHike/issues/122)) both point the same way. Scoping is worth building for the *transfer*, not for the storage.
- **The corpus is small today and is not bounded.** POI_PHOTOS.md's community rung caps a POI's gallery at 15 photos. Across 817 corridor POIs that is **~1.78 GB** — twenty-five times today's corpus, and past the point where "just download it all" stops being defensible. Scope is what makes that growth survivable, and it is much cheaper to build now, against 489 photos, than to retrofit against 12,000.

**Recommendation: offer the whole trail as the default and make it one small opt-in pack, with scope as the answer for metered connections and as the mechanism the community rung will need.** That is close to the opposite of what the ask assumes, and it is the finding most worth a maintainer's disagreement.

## Finding 2 — every scope in this feature is a mile range, so there is one mechanism rather than five

A hike is `[startMile, endMile]` (`plannedHike.ts`). A section is a `Segment`'s start and end references ([SEGMENTS.md](SEGMENTS.md)). A day is a smaller `Segment`. "Near me" is a window around `locateOnTrail()`'s answer. The whole trail is `[0, trailMiles]`.

**All five are the same query — "which photos lie between mile A and mile B" — and it returns a set of digests.** There is no per-scope artifact, no per-scope key, no per-scope package. A scope is a filter the phone evaluates over POI data it already has.

That has one prerequisite, and it is one this repository has already decided to do: **the POI artifacts must carry a `mile`.** This is [HIKE_PLANNING.md](HIKE_PLANNING.md)'s Finding 2, and its Phase A — *"Do this first regardless of what follows; it also fixes a real, existing inconsistency."* Without it the phone has to linear-reference 817 POIs against the centerline to answer a scope query; with it, a scope is a slice of a sorted array. **This feature and the planner want the same prerequisite, which is worth knowing when Phase A is scheduled.**

What a scope costs, at Finding 1's measured density (~32.5 KB per trail mile today, ~86 KB after #471). **These are averages over uniform spacing and the worst case is what matters** — Q8, and what the runnable half measures:

| scope | today | after #471 |
|---|---|---|
| A 15-mile day | ~0.5 MB | ~1.3 MB |
| A week, ~100 miles | ~3.2 MB | ~8.6 MB |
| A long section, ~500 miles | ~16 MB | ~43 MB |
| The whole trail | ~71 MB | ~189 MB |

**A section is single-digit megabytes.** That number is what makes Finding 4's resolution possible.

## Finding 3 — content-addressing has already done most of this feature's work, and it collapses the three verbs into two

`photos/<digest>.jpg` is the sha256 of the image bytes. `lib/photo_store.py` already states the consequence — *"The key is the checksum. A client that fetched `photos/<digest>.jpg` can verify the bytes by hashing them, with no manifest lookup."* Applied to downloading rather than to publishing, that fact removes most of what a download feature normally has to build:

- **No manifest.** `archiveDownload.ts` fetches `latest.json` on every attempt to learn what an artifact should hash to. A photo's expectation travels in its name. Nothing to fetch, nothing to be offline from.
- **No resume machinery.** The archive engine exists because re-pulling 300 MB from zero is unaffordable. A photo is ~145 KB. A failed photo is retried; the unit is already small enough that resume is the wrong abstraction.
- **No version scheme.** A photo cannot go stale. Different bytes are a different key, so a digest the phone holds is *by construction* the bytes that digest names, forever.
- **Dedupe is free**, including across scopes: two overlapping sections share their photos with no bookkeeping.

So the three verbs asked for are not three operations over one store. They are:

| asked for | what it actually is | needs the network? |
|---|---|---|
| **Download** | Fetch every digest in scope the phone does not have. | To fetch. |
| **Update** | Recompute the scope's digest set from the newest POI artifacts on the phone, fetch the difference, drop digests no POI references any more. | Only because a **data release** has to land first — this is the photo half of the trail-data refresh, not a photo operation. |
| **Refresh** | Re-hash what is stored against its own key; re-fetch only mismatches. | **No** — to detect. Only to repair. |

**"Refresh" is the verb worth arguing with, gently.** For tiles or conditions it means "the thing I have may be out of date". For content-addressed photos that state cannot exist. What a hiker means by "refresh my photos" is almost always *"a new data release changed which photos my POIs point at"* — which is Update — or *"something looks broken"* — which is Refresh in its true, local, integrity-check sense. Both are worth having and they are worth having different names, because a button that re-downloads 71 MB to fix a problem the phone could have detected for free is exactly the kind of quiet waste value #8 exists to prevent.

**Recommendation: ship Download and Update as the two visible actions, and make Refresh a repair that runs locally and only asks for the network when it finds something wrong.**

## Finding 4 — the PWA cannot tell wifi from cellular, and on iOS it cannot tell anything

This is the hard finding, and it is already documented inside this repository. `lib/dataSaver.ts` on `navigator.connection`:

> *"Hand-written because TypeScript's DOM lib does not declare `navigator.connection` at all, and every field is optional because every field genuinely is: Safari implements none of this, so on iOS the whole object is undefined… `@capacitor/network` would close that gap with a real `connectionType`, but Capacitor is not wired up yet."*

Three separate problems, and they do not have one answer:

- **iOS has no Network Information API at all.** For an installed PWA on an iPhone, `navigator.connection` is `undefined`. There is no field to read, no permission to request, and no polyfill — the information is not exposed to the page.
- **Where the API does exist, the reliable field does not answer this question.** `effectiveType` reports `'4g'` for anything fast, which is exactly what a good LTE connection reports. `type` — the field that actually distinguishes `'wifi'` from `'cellular'` — is the less widely implemented half and has historically reported `'unknown'` on desktop. A rule that fires on `type === 'wifi'` fires on some Android phones and nowhere else.
- **`saveData` is the one field with real coverage and real meaning**, and this project already has a policy for it: Data Saver wins, and it is told to the hiker's face rather than applied silently.

**Capacitor ([#101](https://github.com/OurHike/OurHike/issues/101), already open and already scoped for app-store packaging) is the only honest route to a real wifi test.** `@capacitor/network` reports a genuine `connectionType`. Until then, "only on wifi" cannot be implemented as written — and building it against `effectiveType` would produce a rule that claims to protect a data plan while silently spending it on LTE, which is worse than not having the rule.

**Recommendation: cap the bytes, not the link type.** This is where Finding 2's numbers pay off. The reason "only on wifi" was asked for is a bill, not a radio — and a byte ceiling protects a bill on every platform, today, with no new API:

| what the app can tell | ceiling on an automatic fetch |
|---|---|
| `saveData === true` | **Zero.** Never automatic. Existing policy, unchanged. |
| A real `connectionType === 'wifi'` (after #101) | The whole scope, whatever its size. |
| Anything else — including every iPhone today | A byte budget the hiker sets. **Default: 10 MB.** |

A 10 MB default covers a week-long section outright (Finding 2: ~3.2 MB today, ~8.6 MB after #471) and refuses the whole trail. That is the ask's actual intent — photos there before you leave, no bill shock — delivered on the platform the app actually runs on, and it gets strictly better rather than being replaced when #101 lands.

## Finding 5 — there is no planned date to trigger on, and requiring one would stop the trigger firing

`plannedHike.ts` stores two numbers and says why:

> *"Two numbers. Everything the app needs from them… falls out of the pair, and every field beyond them is features/HIKE_PLANNING.md arguing its way into v1 early."*

A date is not among them. [SEGMENTS.md](SEGMENTS.md) has `planned_start_date` on a `Hike` and [HIKE_PLANNING.md](HIKE_PLANNING.md) carries it into v2's model — but **optional**, and for a stated reason: *"thru-hikers plan loosely, this will shift."*

So a ten-day rule has no field to read today, and after v2's planner ships it has a field most hikers will leave empty. **A trigger that only fires for hikers who entered a start date will mostly not fire** — and the hikers least likely to have entered one (loose plans, spontaneous section hikes) are not the hikers least likely to want photos.

**Recommendation: the hike is the permission; the date is the urgency.**

- **Having set a hike is a declaration of intent**, and it is enough to justify quietly fetching that hike's photos next time the phone is on a connection the ceiling allows. No date required.
- **A `planned_start_date` within ten days raises the ceiling and surfaces the offer** — this is the last reliable wifi before the trailhead, so it is worth showing "Your hike starts Tuesday. 3.5 MB of photos for miles 812–912." on the Downloads screen and letting the ceiling go to the whole scope.
- **Ten days is a good number and should be a constant with its reasoning attached**, in the way `MAX_PHOTO_AGE_DAYS` is: long enough to catch the packing week, short enough that it is not just "eventually".

This makes the ask work *better* than specified, and it costs one optional field this repository has already designed rather than a new required one.

## Finding 6 — "within 100 miles" is the right instinct measured against the wrong thing

Two problems with the rule as written, and one thing it is genuinely good for.

**Distance to the trail is not distance to the hike.** Philadelphia is within 100 miles of the AT. A hiker there, planning a section in Maine, satisfies the rule and gains nothing from it. Meanwhile a hiker 150 miles out and driving to their trailhead tomorrow fails it. The measurement that carries the intent is **distance to the hike's own stretch**, and where a hike is set that is what should be measured.

**Nothing computes it today, and the one function that comes close refuses to.** `locateOnTrail()` returns `null` beyond 3 miles off corridor — deliberately, because there is no honest mile to give a point that far away. A 100-mile test is a different question (*"roughly how far is this phone from that stretch of trail"*) and wants a coarse great-circle distance against the hike's endpoints, not a corridor snap. Cheap to add; it must not be bolted onto `locateOnTrail()`, whose refusal is load-bearing.

**And "refresh" is the wrong verb to hang on it**, per Finding 3 — nothing on the phone can be stale, so proximity should trigger *filling the gaps*, which is Download.

**What proximity is genuinely good for is supplying a scope to a hiker who has no plan.** That is the case the other findings do not cover: someone who opens the app at a trailhead having declared nothing. For them, "you are at mile 812" is the only scope available, and *"here are the photos for the next 30 miles"* is a small, obviously-useful fetch that no plan was needed to justify.

**Recommendation: proximity scopes; it does not trigger.** Hike set → the scope is the hike. No hike but located on or near the trail → the scope is a window around the fix. Neither → nothing automatic, which is the honest answer when the app does not know what someone is doing.

One cost to state rather than discover: this reads GPS in order to decide about a *download*, which is a different act from reading it to draw a position. `useGeolocation` already pauses when the tab is hidden and stops on a denied permission, so the mechanism is well behaved — but a hiker who denied location gets no proximity scope at all, and that is a correct outcome rather than a gap to work around. GPS never leaves the device ([IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)), and this scope is computed entirely on the phone.

## Finding 7 — a PWA cannot download while it is closed, so "smart" means "opportunistic on open"

The ask implies the app acts on its own. In a PWA it can only act when it is running:

- **Periodic Background Sync** is Chromium-only, requires an installed PWA, and fires at the browser's discretion under a site-engagement heuristic. It is not a schedule.
- **Background Sync** fires on regained connectivity, not on a calendar, and is likewise Chromium-only.
- **iOS supports neither.** The client already ships a service worker (`vite-plugin-pwa`) and already uses it for update detection, so this is a platform limit rather than a missing dependency.

**Recommendation: the trigger is evaluated when the app is opened and visible**, and the copy should never imply otherwise. In practice this loses very little — a hiker packing for a trip opens the app — and the alternative is a promise the platform cannot keep, which [HIKER_SAFETY.md](HIKER_SAFETY.md)'s bar rules out for anything the hiker might rely on. Capacitor (#101) would allow a real background fetch later; it is not needed for this to be useful.

---

## The design

### One rule, evaluated on open

```
when the app becomes visible:
  if automatic photos are off                     -> nothing
  if saveData is on                               -> nothing, and say why if asked
  scope := the hike, else a window around the fix, else none
  if scope is none                                -> nothing
  need := digests in scope not already stored
  if bytes(need) > ceiling                        -> offer it on the Downloads screen, do not fetch
  else fetch, and record what was fetched
```

`ceiling` is Finding 4's table, raised to the whole scope when a `planned_start_date` is within ten days (Finding 5).

Three properties worth keeping as this is built:

- **It is a pure function of its inputs**, in the way `effectiveBackground()` is, so the Downloads screen can state exactly what the app will do and never disagree with what it does. `dataSaver.ts` argues this case already and the argument carries over unchanged: *"the app is allowed to override a preference, and is not allowed to do it silently."*
- **Nothing here is a safety path.** Photos are an enhancement — POI_PHOTOS.md says so, and it is why an empty slot is an acceptable resting state. No part of this may compete for bandwidth with conditions data or block the map.
- **Every automatic fetch is visible afterwards.** `downloadActivity.ts` already exists so that a transfer is never invisible while it runs; an automatic transfer needs the same honesty *after* it runs — "1.0 MB of photos, Tuesday, miles 812–842" on the Downloads screen. The Data Saver incident's rule was *the archive is a size on a button someone taps*, and an automatic download is precisely the case that rule was written about. It is why the whole mechanism is off until turned on once, with the ceiling stated in the same breath.

### What the hiker sees

One card on the Downloads screen, beside the background sheets rather than inside them:

```
  Photos                                          3.5 MB
  Photographs of the shelters and campsites on your hike.
  miles 812–912 · 22 of 24 on this phone

  [ Download ]   Get small updates automatically (up to 10 MB)  [ on ]
```

- **Scope follows the hike by default**, with "whole trail" available for anyone who wants it and can see what it costs.
- **The size is measured, never estimated** — `packages.ts`'s rule, and photos can meet it exactly: the phone knows every digest in scope, and a digest set's byte count is knowable once photo sizes travel on the POI feature (see "Open questions").
- **Partial coverage is stated rather than implied.** "22 of 24" is the honest line; a card showing a silhouette must not be indistinguishable from a place that has no photograph at all. A POI whose `photo_key` is present but whose bytes are absent is *"not downloaded"*, and that is different from *"no photo exists"* in exactly the way value #4 cares about.

### Where this does **not** fit, and why it matters

**Photos must not become an entry in `MAP_PACKAGES`.** That file is explicit:

> *"these packages are keyed by what they ARE… and never by which trail wanted them. Nothing in this file is trail-scoped, and nothing downstream may make it so."*

A hike-scoped photo set is scoped by definition, so adding it there would break the invariant that file exists to protect. It also does not need what that file provides: the anti-duplication rule is there because a per-trail tile key would silently store hundreds of megabytes twice, and content-addressing solves that structurally for photos — two trails sharing a POI share the digest, with nothing written down.

So photos are a **sibling** of the sheets on the Downloads screen and a different mechanism underneath: a set of small content-addressed objects, not an archive with a lifecycle.

### Storage

One IndexedDB entry per photo, keyed by digest. POI_PHOTOS.md raised PMTiles as the alternative — *"a single file with an internal index"* — and it is the right pattern at tile scale and the wrong one here:

- The unit count is ~489 today and ~1,301 after #471, not the hundreds of thousands a tile archive holds. A few thousand IndexedDB entries is unremarkable.
- **A scope is a set of individual objects**, so individual storage is what makes "download my section, then later my next section" cheap rather than a range-request problem.
- Individual entries make eviction and garbage collection ordinary: a digest no POI references is deletable on sight.

The cost of that choice is read volume, and it is worth stating with a number: a full whole-trail download is 1,301 GETs. At 25,000 devices doing one each that is 32.5M R2 reads, or **about $8/month** against the free 10M and $0.36/M — versus one read for a bundle. Storage and egress remain $0. **Eight dollars is not a reason to give up scoping**, but it is the honest trade, and it argues for scope-by-default rather than whole-trail-by-default on the *read* side even where the byte side does not care.

---

## What this spike deliberately does not settle

- **Anything about which photo fills the slot.** POI_PHOTOS.md's ladder, sources, licences and moderation are unchanged and out of scope here.
- **The hiker's own photos.** They are already on the device and were never a download. POI_PHOTOS.md keeps them off this project's disks and this document does not touch that.
- **The community rung's bytes.** Finding 1 sizes it (~1.78 GB at the 15-photo cap) to show why scope is worth building; how shared photos are *delivered* depends on a moderation and consent path that does not exist yet.
- **Whether photos should be a paid convenience.** POI_PHOTOS.md raises "the offline photo pack" as the one defensible photo-shaped premium and recommends against a quality tier. Finding 1 weakens even that: a $0-cost 71 MB download is a thin thing to charge for. Recorded, not decided — it is [PRICING_MODEL.md](PRICING_MODEL.md)'s call.

## Open questions (for you, not decided here)

- **Should photo *sizes* travel on the POI feature?** Without a byte count per photo the card cannot honour `packages.ts`'s measured-sizes rule — it would have to estimate, or issue 489 HEAD requests. One integer per photo in the artifact fixes it and costs almost nothing (a few KB across the corpus). This is the smallest unresolved dependency in the whole design and probably the first thing to settle.
- **What the default scope is.** Finding 1 argues the whole trail is small enough to be the default; the ask assumes the hike is. The difference is 71 MB versus ~3 MB and it is a judgement about whose data plan we are spending.
- **Whether "automatic" should default on or off.** Off is consistent with #122 and with every consent decision this project has made. On is what makes the feature actually help the hiker who never opens the Downloads screen — which is most of them. A middle answer exists (on, with a small ceiling, disclosed in onboarding) and it is a maintainer's call.
- **What happens to a photo that leaves scope.** Deleting it the moment a hiker edits their hike is tidy and wastes the bytes they already paid for; keeping everything makes storage grow silently. A "keep what you have, fetch what you need" default with an explicit clean-up action is probably right, and it is the kind of thing that should be decided against a real storage screen.
- **Whether ten days is the right window**, and whether it should scale with the size of the hike — a thru-hiker starts packing rather earlier than a day-hiker.

## Suggested build order

Each phase is useful on its own. None is a bet on the next landing.

| Phase | What | Depends on |
|---|---|---|
| **A** | Photo sizes on the POI feature, so a scope has a measured byte count. | Nothing. Smallest piece; unblocks every honest size string below. |
| **B** | The scope query and the digest set: "which photos lie between mile A and mile B". | HIKE_PLANNING.md's Phase A (`mile` on every POI) — **the same prerequisite that feature already needs**. |
| **C** | Download and Update as manual actions on a Photos card, scoped to the hike or the whole trail. Refresh as a local integrity check. | A, B. |
| **D** | The automatic rule, with the byte ceiling, Data Saver respect, and the after-the-fact record. | C. |
| **E** | The proximity scope, for hikers with no hike set. | C, and a coarse distance-to-stretch function that is **not** `locateOnTrail()`. |
| **F** | A real `connectionType` raises the ceiling on wifi. | [#101](https://github.com/OurHike/OurHike/issues/101) (Capacitor). Strictly an improvement to D, never a prerequisite for it. |

Sections as a scope arrive with [SEGMENTS.md](SEGMENTS.md)'s tree — they need no work here beyond passing a different mile range into Phase B's query, which is the point of Finding 2.

## Running the spike

```
cd pipeline
python spike_photo_scope.py                        # needs data/raw from fetch_all.py + fetch_atc_photos.py
python spike_photo_scope.py --windows 15,100,500
python spike_photo_scope.py --all-photos           # model #471's full corpus rather than today's
```

It answers Q8 — **what the worst section actually costs, not the average one.** Every per-scope number in Finding 2 assumes photos are spread evenly along the trail, and they are not: they cluster where shelters and campsites cluster. The script measures real file sizes from the content-addressed cache, projects each POI onto the same ordered, merged centerline `export_elevation.py` uses (deliberately, so this does not invent a third way to measure a mile — [HIKE_PLANNING.md](HIKE_PLANNING.md)'s Finding 1), and reports the p50, p95 and maximum bytes over every rolling window of the requested lengths.

**It has not been run.** The environment this document was written in has no route to ATC's servers and no fetched `data/` tree, which is the same position [`spike_day_planner.py`](../pipeline/spike_day_planner.py) is in. Every byte figure in Finding 2 is therefore arithmetic over measured aggregates — the corpus totals in Finding 1 are real measurements, the *distribution* across the trail is not. Closing that is the first thing to do, and it is the one number that could change Phase C's shape: if the worst 100-mile window is three times the average, the ceiling in Finding 4 needs to be chosen against that rather than against a mean.
