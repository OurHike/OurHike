# OurHike — The Same Account on Two Devices (Feature Design Draft v1)

Companion to [AUTHENTICATION.md](AUTHENTICATION.md) (the account this hangs off),
[IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md) (which kinds of a hiker's data exist and
who sees them), [SEGMENTS.md](SEGMENTS.md) (which named this gap in v1 and deferred it),
[HIKE_PLANNING.md](HIKE_PLANNING.md) (whose trips are the thing worth carrying between
devices), [POI_PHOTOS.md](POI_PHOTOS.md) and [PHOTO_DOWNLOADS.md](PHOTO_DOWNLOADS.md) (the
photo model this must not quietly redefine), [PRICING_MODEL.md](PRICING_MODEL.md) (who pays
for the storage), and [../OurHikeValues.md](../OurHikeValues.md) #4 and #6.

**Scoped 2026-08-20 as v2's ninth feature, by a maintainer ask rather than a doc:** *"we
should let a user move seamlessly between the web and their phone — if a user has an
account, they should be able to see their planned hikes, photos etc between the different
devices."*

[SEGMENTS.md](SEGMENTS.md) is where this was first written down and deliberately declined:
*"no cross-device sync without introducing accounts… 'plan on my phone, check on my laptop'
isn't included unless that tradeoff gets revisited deliberately."* Accounts shipped in v1.
This is that revisit.

Every measurement below was taken on 2026-08-20 against `main` at `657e645`, and each says
how, so the next person can re-take it rather than trust it.

---

## What a hiker is asking for, and the one thing they are not

Three journeys, and they are not the same feature wearing three names:

1. **Plan at home, walk with the phone.** A section hiker lays out four days on a laptop
   over a fortnight, then leaves with a phone. Today the laptop's plan does not exist on
   the phone in any form.
2. **Get a new phone.** A dropped phone in Virginia today loses every trip, every private
   photo and every setting the hiker has. Nothing anywhere is a copy.
3. **Look back on a big screen.** Photos taken at a shelter are 640 px renderings in the
   phone's IndexedDB and are visible on exactly that phone.

And the one that is **not** being asked for and must not be built by accident: OurHike
becoming somebody's photo archive. [../FEATURES.md](../FEATURES.md) states the position
outright — *"OurHike deliberately never becomes anyone's photo archive: the library keeps
the original, the app keeps a thumbnail for the card."* Sync moves the thumbnail. It does
not acquire the original, and it must never be described to a hiker in words that imply it
did — that is the "never let a display outrun its source" rule pointed at a promise rather
than at a number.

## What is on the device today, and which of it is the hiker's

**Measured** (`grep -rho "'ourhike:[a-z-]*'" client/src --exclude='*.test.*'`, 23 distinct
keys outside tests, plus the `:version`/`:progress` suffixes the archive machinery derives
per download):

| The hiker made it — it should follow the account | The device made it — it must not travel |
|---|---|
| `ourhike:preferences` — the `UserPreferences` blob | `ourhike:basemap`, `ourhike:corridor-archive`, `ourhike:dem`, `ourhike:elevation` — downloaded bytes |
| `ourhike:trips` — every saved trip and which is open ([#787](https://github.com/OurHike/OurHike/issues/787) — *Save more than one plan: today the Plan tab keeps exactly one, and the next trip overwrites the last*) | `ourhike:pois`, `ourhike:trails`, `ourhike:spurs`, `ourhike:highlights`, `ourhike:club-sections` — published data, re-downloadable |
| `ourhike:hike` — the hike a person says they are on ([#335](https://github.com/OurHike/OurHike/issues/335) — *There is nowhere to say which way you are walking*) | `ourhike:trail-data-partial`, `ourhike:trails-merged-chains`, `ourhike:released-bytes` — build state of the above |
| `ourhike:plan` — the single plan that predates trips, read once and migrated | `ourhike:camera` — where the map was last left |
| `ourhike:my-photos:<poiId>` — the hiker's own 640 px photos | `ourhike:outbox` — a queue, and see below |
| `ourhike:walked-miles`, `ourhike:passed-today` — where they have actually been | |
| `ourhike:pace` — see the pace issue below, which is deciding this exact question | |
| `ourhike:atc-alerts-silenced-through` — a dismissal | |

The right-hand column is not a shortcut. Every entry in it is either bytes a device chose
to hold (and a second device may have chosen differently, or be a browser tab that cannot
hold them at all) or a derivative of published data that re-downloads in full. Syncing any
of it would move the largest objects in the app to buy nothing.

**Also measured, and it is the useful surprise: half of the server side already exists and
nothing calls it.**

- `GET /preferences/me` and `PUT /preferences/me` are implemented, validated
  (`extra="forbid"`) and tested. `grep -rn "/preferences" client/src/lib/api.ts` returns
  **zero** matches: no client has ever called them, on any surface.
- `/hikes` has full CRUD plus `/hikes/{id}/direction`. `client/src/lib/plannedHike.ts` says
  so in its own comment — *"`POST /hikes` exists and is complete, and nothing here calls
  it"* — and gives the reason it stopped: *"pushing a hike to the server raises 'which
  device wins' the moment there are two."*

So the first phase of this feature is **wiring, not building**, and the question that
stopped the wiring is the question this document exists to answer.

## The rule everything else follows from

**The device holds the truth while it is offline.** This is not a preference between sync
strategies; it is forced by what this app is. A hiker edits tomorrow's mileage at a shelter
with no signal, and that edit is real the moment it is made. A server cannot arbitrate what
it has not seen.

Three corollaries, and each one rules out a design that would otherwise be the obvious one:

1. **No write waits for the network.** Sync is a background reconciliation over IndexedDB,
   never a save path. `lib/outbox.ts` already established this shape for contributions.
2. **Sync never destroys something a hiker made.** Not a trip, not a photo, not a note. A
   delete propagates only when it was *the hiker's own delete*, carried as a tombstone —
   never as an absence inferred from one device's silence.
3. **A conflict is resolved by keeping both.** Which is the honest-unknown rule
   ([../CLAUDE.md](../CLAUDE.md)'s "Four ways this app can hurt somebody") applied to data
   rather than to a number: when two devices disagree about a plan, the app does not know
   which the hiker meant, and last-write-wins is a confident answer to a question nobody
   asked it.

## What syncs, at what grain

**Preferences — the whole blob, last write wins.** The server model is already exactly
this: one JSON column, replaced wholesale on every `PUT`. Losing the older of two edits
costs a toggle a hiker can flip again, and the blob is small enough that a field-level
merge would be machinery bought with nothing. `updated_at` decides.

**Trips and the planned hike — per record, with tombstones, and both kept on a conflict.**
The grain is the trip, not the day inside it. A trip is a `Segment` with an identity
(`lib/trips.ts`); day boundaries inside it are dense, edited together and meaningless
apart, so merging at day level invents plans neither device ever held. Each trip carries
`updated_at` and a `deleted_at`; the sync sends what changed since its last watermark and
takes back the same.

**When two devices have both edited the same trip since the last sync, neither is
discarded.** The newer one keeps the name and the older one is kept beside it, named for
where and when it came from — *"Grayson Highlands (from the phone, 12 Aug)"*. The hiker
opens both, sees the difference and deletes one. That is one moment of friction in exchange
for never being the app that silently ate four days of planning; the cascade design in
[#758 — *The cascade: when today changes, what happens to the rest of the
plan*](https://github.com/OurHike/OurHike/issues/758) already establishes that a plan is a
structure, not a value.

**Contributions do not sync, because they are already server-side.** A report, a field
note, a claimed volunteer hour and a shared photo all leave the device through the outbox
and land in Postgres against the contributing account (`reports.reporter_id`,
`field_notes.reporter_id`, `poi_photos.contributor_id`, all foreign keys to `profiles.id`).
Copying them a second time would be a second source of truth for rows that already have
one.

**But "the second device just reads them back" is not true yet, and it is worth naming
rather than assuming.** Measured 2026-08-20: `/volunteer-hours/mine` is the only
mine-shaped endpoint in the backend. There is no *my reports* and no *my field notes* — a
report is fetched by its own id or by the public list, and a note by its POI. So a hiker
signing in on a laptop sees their published contributions only where they happen to be
standing on the map. That is a real gap, it is small, and it belongs to whoever builds the
screen that would show them rather than to this design.

**The outbox itself must never travel.** It is one device's promise to send something it
holds the only copy of; a second device carrying the same item does not double-file (the
item id is an idempotency key, per `lib/outbox.ts`) but it does turn a failure the hiker
can see and act on into a failure that is somewhere else.

**Private photos sync only if the hiker turns it on** — the section below is the whole
argument.

**Pace does not, yet.** [#881 — *Learn a hiker's real pace — and decide, in the open, that
pace data now leaves the phone*](https://github.com/OurHike/OurHike/issues/881) is deciding
exactly that, with the same data, for a different purpose. Two answers to one question is how
this repository ended up measuring a mile two ways —
[#753 — *Publish a mile on every POI, because this codebase measures a mile two different ways
and a plan cannot survive that*](https://github.com/OurHike/OurHike/issues/753). This design
defers to that issue and takes nothing.

**`walked-miles` and `passed-today` are deferred with it**, for the same reason and one
more: they are a movement history, the most sensitive thing in the left-hand column, and
they are the one entry there whose loss on a new phone costs a hiker nothing they can
act on.

## Photos: two words that must not become one

**Sharing and syncing are different acts and the app must never let one perform the other.**

| | Share ([#577](https://github.com/OurHike/OurHike/issues/577) — *The share sheet: who will see this photo, under what terms, and what cannot be taken back*; built) | Sync (this doc) |
|---|---|---|
| Audience | Everyone, forever | The hiker's own devices |
| Licence | CC BY-SA 4.0, irrevocable after the two-hour window | None granted; still theirs |
| Store | `poi_photos` + the community R2 prefix | A separate private store |
| Undo | Withdrawal within two hours, then never | Delete, at any time, everywhere |

The failure this table exists to prevent is a plausible implementation, not a hypothetical:
a private photo backup that reuses `poi_photos` because the row shape fits is one status
enum away from publishing a hiker's tent.

What travels is the **640 px card rendering and nothing else** — the same object
`lib/poiPhotos.ts` already stores, GPS-free by construction because it came out of
`reportPhoto.ts`'s canvas re-encode rather than being stripped of EXIF. The original never
leaves the library it is in. Where there *is* no original in a library — a photo taken
through the app's own camera — sync makes that promise matter more, not less, so
[#573 — *Save a photo taken inside OurHike to the hiker's own photo library, or stop promising
their library has the original*](https://github.com/OurHike/OurHike/issues/573) should land
before this phase rather than after it.

**The mechanism is already in this repository and should not be reinvented.**
`backend/app/core/photos.py` holds report photos in a private R2 bucket under a key derived
from the owning row (`reports/{id}/{n}.jpg`), reads them through a short-lived signed URL,
and states the direction of truth once: *the row is authoritative, the object is derived and
disposable.* A private photo store is that pattern with `photos/{profile_id}/{photo_id}.jpg`
and no public read path at all.

**What it costs, as arithmetic rather than as a guess.** A 640 px JPEG is
**@unvalidated** — nobody here has measured one. What is known is the shape: the report
path caps a 1600 px photo at 2 MB (`reportPhoto.ts`), and 640 px is 0.16× the pixel count,
so a card rendering is plausibly tens of kilobytes and certainly not megabytes. **Settle it
by encoding twenty real trail photos through `preparePhoto(file, CARD_PHOTO_EDGE)` and
reporting the median**, before any cap is picked. Until then the honest statement is that
per-hiker storage is small and the *aggregate* is a bill nobody has bounded — which is the
subject of [#393 — *What OurHike costs to run, who pays for it, and the guardrails that keep a
bad week off a personal credit card*](https://github.com/OurHike/OurHike/issues/393) and
[#395 — *Put a ceiling on the bill before the app is
public*](https://github.com/OurHike/OurHike/issues/395), and the reason the cap belongs to a
maintainer rather than to a session.

## The web and the phone are not the same device

Sync must be indifferent to which surface it is running on, and the surfaces are not
symmetrical:

- The web tab holds no offline archives and should not be offered them. Everything in the
  right-hand column above is absent there by design, which is another reason it is not
  sync's business.
- Browser storage is evictable. A PWA on iOS is subject to WebKit's eviction of unvisited
  origins — the same platform fact
[#555 — *The Fine tier is offered on iOS, where WebKit will not hold
it*](https://github.com/OurHike/OurHike/issues/555) raised for downloads. **This is an argument for
  sync, not against it**: once a hiker's own content has a home on the server, eviction
  costs them a re-download rather than their planning.
- **@unvalidated:** nothing here has been exercised on a real second device, because no
  environment exists to exercise it in (see below).

## Privacy: this adds a sixth kind of identity

[IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md) enumerates five kinds of identity in
this app. This adds one, and it is worth naming precisely because it looks harmless: **a
hiker's own private content, held on a server for their own convenience.** Not published,
not attributed, visible to nobody else — and, for the first time, out of their sole
physical control.

Three things follow, and the third is a gap this feature creates rather than inherits:

1. **The anonymity window is untouched.** It governs what the public sees on a report.
   Nothing here reaches a public surface.
2. **Row-level security is the floor, not the design.** `b3d1c7a94e02_enable_row_level_security`
   is already applied; a private photo table and a trips table join it, and no endpoint
   serves either to anyone but its owner.
3. **Deleting an account has to mean something, and today it means nothing.** **Measured:**
   there is no delete path anywhere — no endpoint in `backend/app/routers/profiles.py`, no
   mention in [AUTHENTICATION.md](AUTHENTICATION.md). While every private thing lives on the
   hiker's own device, uninstalling *is* deletion and the gap is invisible. The moment their
   trips and photos are on a server, uninstalling stops being deletion, and an app that
   cannot answer *"take it all back"* has quietly changed the deal. Account deletion and
   export are part of this feature, not a follow-up to it.

## What has to be true before any of this ships

Stated plainly because it is the most important paragraph here for anyone about to start:
**none of this is worth building yet, and the reasons are other people's issues.**

- **[#875 — *A hiker cannot finish signing
  in*](https://github.com/OurHike/OurHike/issues/875).** The account this whole feature keys
  off does not currently work end to end in the deployed app.
- **[#600 — *Nothing owns standing up the production backend, and the image has never run
  against a real Docker daemon*](https://github.com/OurHike/OurHike/issues/600).** There is
  nowhere for any of this to sync *to*.
- **[#92 — *Real Apple OAuth has never been exercised end to
  end*](https://github.com/OurHike/OurHike/issues/92).** Half of "their phone".

The design can be settled now — that is what this document is — and the first line of code
should wait on those first two, or it will be written against a system nobody can observe.

## Build order

Five phases. Each is useful alone, and the first is genuinely small.

**A. Preferences actually sync.** Wire `GET`/`PUT /preferences/me`, which already exist, to
the local blob: pull on sign-in, push on change, last-write-wins on `updated_at`. It proves
the whole loop — token, base URL, conflict rule, the offline no-op — against the one payload
where a wrong answer costs a toggle.

The trap here is known and already guarded, which is worth stating because comments in the
client still describe it as live: the schema is `extra="forbid"`, so a key the client invents
becomes a 422 for every hiker on their first sync. That was
[#242 — *The first preferences sync will 422: the client blob carries wrong_way_alert_enabled
and the backend forbids it*](https://github.com/OurHike/OurHike/issues/242), **closed
2026-08-07**, and `backend/tests/test_preferences_contract.py` now round-trips the client's
real `DEFAULT_PREFERENCES` so the two field lists cannot drift apart again. Phase A inherits a
guard rather than the bug — but it is the phase that finds out whether the guard holds.

**B. Trips and the planned hike.** The record grain, the tombstones, the keep-both conflict
rule, and the watermark. This is the phase the maintainer's ask is actually about, and the
one with a real design inside it.

**C. Private photo backup, opt-in.** A separate store, the 640 px rendering only, the R2
pattern from `core/photos.py`, a per-hiker cap decided from a measurement rather than a
guess, and copy that never says "backup" if what we hold is a thumbnail.

**D. The seam a hiker can see.** One screen: what is synced, when it last ran, what is on
this device only, and how to turn it off without losing anything. An offline-first app that
syncs invisibly is an app whose hiker cannot tell whether their plan is safe — and value #4
says the honest answer beats the polished one.

**E. Export and delete.** Everything of mine, in my hands or gone. Ships no later than C,
because C is the phase that makes the current silence a broken promise.

**The spike that should run before C:** encode twenty real photos at `CARD_PHOTO_EDGE` and
publish the median, so the cap in C is measured rather than picked.

## Decisions this document does not take

Four, and each is a maintainer's rather than a session's:

1. **Is sync free?** [PRICING_MODEL.md](PRICING_MODEL.md) keeps contribution and safety
   data free and gates convenience. A hiker's own plans on their own two devices reads as
   the free tier's business; *photo* storage is the line where somebody's bill grows with
   somebody else's memories. Naming that split is a pricing decision, not a technical one.
2. **A per-hiker photo cap**, once the measurement above exists.
3. **Retention after deletion** — how long a deleted photo's object survives in R2 before
   the sweep, and whether "deleted" means the same thing to a hiker as it does to a bucket.
4. **Does pace travel?** Deferred to #881 on purpose; whoever answers it there answers it
   for `walked-miles` too.
