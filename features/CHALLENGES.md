# OurHike — Challenges (Feature Design v1)

Companion to [VOLUNTEERING.md](VOLUNTEERING.md) (whose §5 guardrail this feature has to get
past, and does below), [HIKE_PLANNING.md](HIKE_PLANNING.md) (the plan a challenge's places are
laid against), [POI_PHOTOS.md](POI_PHOTOS.md) (the hiker's own photo a tagged place shows),
[ORG_ONBOARDING.md](ORG_ONBOARDING.md) (the console a club authors one in),
[ACCOUNT_SYNC.md](ACCOUNT_SYNC.md) (which keys follow the account),
[EVENTING.md](EVENTING.md) (the k-anonymity floor the club's counts answer to) and
[../OurHikeValues.md](../OurHikeValues.md) #1, #2, #4 and #9.

Tracked by [#1780 — Let a club publish a challenge — places on its own trails that hikers
opt into and tag at camp — starting with the ATC's A.T. Summer Bucket
List](https://github.com/OurHike/OurHike/issues/1780). Drawn in the design handoff *Trail
Challenges*, five rounds, 2026-09-30.

---

## What a challenge is

**A list of places on one organization's trails, a date window, an optional finish line, and
an optional reward.** Hikers opt in, walk, and tag the places at camp. A club authors its own;
a hiker can be in several at once.

The first is the ATC's **A.T. Summer Bucket List**. Today it is a two-page PDF
([2025 edition](https://appalachiantrail.org/wp-content/uploads/2025/05/ATC_Summer-Bucket-List_2025.pdf),
co-branded "ATC x Altra") and an email form sent on August 15: 97 checklist items in three
sections plus three mystery items announced on social media, "complete at least 25 items by
September 1 to be eligible for the grand prize drawing." A hiker keeps it on paper and types it
back into a form. Everything in that loop is something the phone already knows — where the
hiker walked, which shelter they slept at, how high they climbed — and none of it reaches the
form.

## Decisions

- **2026-09-30, maintainer (handoff revisions).** Never "passport" — that is the ATC's own word
  for its stamp programme. The working term is **tag**: "Tag it", "Tagged", "Your challenges".
  The final word is the maintainer's and is one constant, `CHALLENGE_WORDS` in
  `client/src/lib/challengeWords.ts`. No digital stamp and no stamp animation: a tagged place
  shows the hiker's own photo, the moment, and the club's note. Rewards are optional, and most
  challenges have none.
- **2026-09-30, maintainer (poll, with a scope page drawn from the handoff's own frames).**
  The whole handoff ships in one stacked pull request, over a foundation-plus-tag-by-hand
  slice and over a foundation-only slice.
- **2026-09-30, maintainer (same poll, three drawn frames).** **A challenge marked `draft`
  publishes everywhere, labelled** — "Draft · not yet confirmed by the ATC" on every surface
  that names it — over never publishing a draft, and over publishing drafts to the UA bucket
  only. The ATC's 2025 transcription is the first draft. A draft takes no entries: a hiker can
  join, walk and tag, and the finish screen says the club has not confirmed the list, rather
  than collecting a sweepstakes entry nobody agreed to run.

## The guardrail argument

[VOLUNTEERING.md](VOLUNTEERING.md) §5 rule 2 forbids "a progress bar toward a target nobody
set." A challenge has a progress bar toward a target. This is the argument for why it ships
anyway, recorded so the next feature to meet the guardrail does not relitigate it.

**The maintainer's position, 2026-09-30:** a challenge is valid gamification because it is
measured in **days on trail, not clicks**, and it pulls time **away** from the app. The target
is set by the publishing organization — a real external rule, the same shape as the fee
exemption's 40-hour threshold §5 already excepts — and it is shown only to someone who joined.
Nobody is shown a target they did not choose.

What §5 was protecting against is comparison and pressure, and four of its rules survive here
unchanged:

1. **Never comparative.** No leaderboard, no "other hikers", no rank, no average, no count of
   how many people finished. The org console's "Hikers in" is a count the club sees, never a
   hiker.
2. **No lack-state.** Nothing says "you haven't…". The Today card lists what the hiker passed
   and never what they missed; a missed item has no numeral anywhere.
3. **Private by default.** The record is the hiker's. The club learns a name only when the
   hiker sends an entry.
4. **Counts real places, not points.** Progress is drawn in the challenge's own unit — places
   tagged, sections walked — and there is **no composite score across challenges**.

And the test §5 closes on applies: *would this ship with no external consumer, to drive
retention?* No. The consumer is the club, which today collects the same list by email form.

## The contract

These are the handoff's six principles, verbatim. They are acceptance criteria rather than
taste, and each has a negative assertion somewhere in the suites (listed under "What proves
it" below).

1. **Days, not clicks.** Every item is a place, a waypoint type, a walked section, or a workday.
   There is no in-app task that can be completed by tapping. Progress only moves by being on
   trail.
2. **The walking view does not change.** No notification, sound, haptic, banner, or count on
   the map plate (`chrome/Header.tsx`) near a challenge place. The map layer is off by default.
3. **Asked at camp.** Detection runs against the day's GPS track; the prompt is one card on
   Today after the hiker stops.
4. **Offline-first.** Challenge definitions ship in the data refresh; tags queue in
   `lib/outbox.ts`.
5. **Scoped to the publisher.** A challenge can only use places on trails its organization
   publishes. The ATC's list is A.T.-only for that reason, not a special case.
6. **The hiker's record is theirs.** Nothing leaves the phone except queued tags (item id +
   authored time) and, only when the hiker sends it, one entry (name, email or mailing
   address, tagged items). No GPS track, no photos, no register notes.

**Three qualifications the build had to make, stated rather than smoothed over:**

- Principle 1's "no task completed by tapping" has one named exception the handoff also makes:
  **`self_report`** items, the PDF's at-home Learn and Protect lines ("Take our A.T. trivia
  quiz"). They are 76 of the ATC's 97 items. They never appear on the map, on Plan or on
  Today, and are tagged from the challenge's own page.
- A place can also be **tagged by hand from its card**, because GPS has gaps — the handoff's own
  open question names this as the answer. Every tag records how it was made (`gps` or `hand`),
  and an entry carries that to the club, so the club decides what a hand tag is worth rather
  than the app deciding for it. That is "never let a display outrun its source" pointed at the
  club instead of the hiker.
- **Principle 3's "the day's GPS track" is the day's walked miles, because the app keeps no
  track.** `lib/passedToday.ts` holds today's walking as "mile INTERVALS, merged — no fixes,
  no coordinates, no timestamps, no ordering", and `lib/walkedMiles.ts` the same for all
  time. That is a privacy posture this repository chose before this feature existed, and
  a challenge does not get to add a finer record of where somebody went. So a place is
  "passed" when its published mile falls inside today's walked intervals, and the hiker
  confirms it at camp. The cost is stated rather than hidden: **a place off the trail (a town,
  a visitor centre) can only be tagged by hand**, because a mile interval says nothing about
  one, and a place's tag radius is checked by the exporter rather than against a fix.

## Data model

### The reviewed file

`pipeline/reference/challenges/<org>/<challenge id>.json`, one file per challenge, committed
and reviewed row by row — the argument `reference/highlights.json` already makes, and for the
same reason: each row is somebody's judgement that a line of a PDF is a particular place.

```jsonc
{
  "id": "atc-summer-bucket-list-2027",   // = the file name
  "org": "atc",                          // an organization the pipeline knows
  "trail": "AT",                         // one of that org's trails
  "name": "A.T. Summer Bucket List",
  "status": "draft",                     // draft | published
  "window": { "opens": "2027-05-15", "closes": "2027-09-01" },  // either may be null
  "finish": { "count": 25, "label": "for the drawing" },          // null = a record, no finish
  "reward": { "kind": "drawing", "rules_url": "https://…" },       // null = no reward (most)
  "sections": [{ "id": "experience", "title": "Experience the A.T.", "short": "Anywhere" }],
  "items": [
    { "id": "mcafee-knob", "section": "experience", "title": "…",
      "note": "optional, 1–3 sentences, the club's", "note_by": "Roanoke A.T. Club",
      "match": { "kind": "place", "poi": "atc_viewpoints:95a1…", "radius_m": 150 } }
  ],
  "reviewed": "2026-09-30"
}
```

**Items name published POI ids, never typed miles or coordinates.** The exporter copies the
published record's own mile, coordinate and name into the artifact, so what the phone matches
against is the number every other screen already shows.

### Match kinds

| Kind | Tagged how | On the map, Plan and Today? |
|---|---|---|
| `place` | its mile falls inside today's walked miles, confirmed on Today; or by hand from the place card or the list. An `off_trail` place by hand only | yes |
| `places_all` | as `place`, per place; the item is done — and its tag leaves the phone — when the last one is ("Virginia's Triple Crown") | yes |
| `poi_type` | a published POI of that type whose mile falls inside today's walked miles, confirmed on Today ("you passed Campbell Shelter") | Today only |
| `elevation_min_ft` | automatically, when today's walked miles include a mile whose profile elevation is at or above the value | no |
| `section_walked` | automatically, when the miles walked inside the section **since joining** cover `min_fraction` of it; the ends are POI ids | Plan only |
| `workday` | automatically, when the hiker's own logged hours (not disputed, since joining, inside the window) name a mile on the challenge's trail — and, when the match names the challenge's own org, a workday of that club | no |
| `self_report` | a tap on the challenge's own page, and only there | no |

**A place must lie within its own radius of the trail, or say `"off_trail": true`.**
`export_poi.attach_miles` gives any point an A.T. mile — it has no failure mode — so a mile
proves nothing about distance. The exporter measures each place against the published
centerline and refuses one that is too far and does not say why. **Measured 2026-09-30 against
release 2026-09-24-2**, nearest centerline vertex: McAfee Knob Summit 41 m, Springer Mtn Summit
Vista 6 m, Katahdin Summit (E) 20 m, The Priest Shelter 119 m, the Harpers Ferry community
point 236 m, the Monson community point 2,867 m. The last two are towns, and their items say
`off_trail`.

**Default radii are `@unvalidated`:** 150 m for a named place, 60 m for "any shelter", both the
handoff's examples. For scale, the median ATC shelter is 63 m from the centerline and the
75th percentile 140 m (same release), so 60 m around a shelter means "went to it", not "walked
past its side trail", which is the intent. What would settle them is tag prompts from real
tracks: how often a hiker who stood at a place was missed, against how often one who walked
past a junction was asked.

### Mystery items

An item may carry `"mystery": { "number": 2, "reveal_on": "2027-07-20" }`. Exported before
that date, its title does not appear in the artifact in the clear: it ships as `sealed_title`,
base64 of the text, and the phone decodes it on or after the date with no network. **Base64 is
a spoiler guard, not a secret** — the rot13 on a puzzle answer. Anyone reading the artifact
with a decoder can read an item early, and nothing here claims otherwise. The ATC's 2025 list
announced its three mystery items only on social media, so the transcription carries them with
no title and no date. They show as "Sealed — announced by the ATC", and the ATC reveals one by
republishing.

### The published artifact

`export_challenges.py` writes `challenges.json` beside `highlights.json`, in every release. A
challenge record is the reviewed file with every POI resolved:

```jsonc
{ "source": "reference/challenges",
  "challenges": [{
    "id": "…", "org": "atc", "trail": "AT", "name": "…", "status": "draft",
    "org_name": "Appalachian Trail Conservancy", "org_short": "ATC",  // sources.json's name, provider
    "window": {…}, "finish": {…} | null, "reward": {…} | null, "sections": […],
    "items": [{ "id": "mcafee-knob", "section": "experience", "title": "…",
                "note": null, "note_by": null, "photo": null,
                "match": { "kind": "place", "radius_m": 150, "off_trail": false,
                           "places": [{ "poi": "…", "name": "McAfee Knob Summit",
                                        "poi_type": "viewpoint", "mile": 714.92,
                                        "lat": 37.39, "lon": -80.03 }] } }],
    "reviewed": "2026-09-30" }] }
```

The coordinates travel so that matching a day's track needs nothing else loaded, and so do
`org_name` and `org_short` — `sources.json`'s `organizations.orgs["org:<org>"]` `name` and
`provider` — because "ATC · until Sep 1" and "Draft · not yet confirmed by the ATC" are
rendered from them and the phone has no other source for either. The artifact carries no
`generated_at`: a stamp would change its sha256 on every run and publish a new version when
no challenge changed. Each record's `reviewed` is the date that means something.

### On the phone

| Key | What it holds | Follows the account? |
|---|---|---|
| `ourhike:conditions:challenges.json` | the published artifact, kept through `lib/conditionsCache.ts` as `lib/suggestedHikesData.ts` keeps its shelf; re-downloadable | no — published data |
| `ourhike:challenge-state` | joined challenges, tags (item, time, `gps`/`hand`, optional register line), the mile intervals walked inside a `section_walked` item since joining, the Plan suggestions a hiker hid per hike, the day the Today card was last answered, the map layer switch | the hiker's own — device-only until a sync for it is built; the tags also reach the server |

An item's completion enqueues one `challengeTag` outbox cargo: challenge id, item id, authored
time, `gps`/`hand`. A `places_all` item queues nothing until its last place. The register line
never leaves the phone (principle 6).

### On the server

`challenge_tags` (id is the outbox idempotency key; unique on user, challenge, item) and
`challenge_entries` (name, email or mailing address, the tagged item ids, consent time). Four
routes: `POST /challenges/tags`, `POST /challenges/{id}/entries`,
`GET /orgs/{slug}/challenges/{id}/counts` (a count, never names) and
`GET /orgs/{slug}/challenges/{id}/entries` (org admins, CSV). A tag after the window closes is
accepted and flagged; an entry after it closes is refused with a reason the phone shows.
Nothing here blocks the phone: until the backend is hosted, tags stay queued and the screen
says so.

## Where it lives

| Frame | Home |
|---|---|
| #2b Your challenges | More → **Challenges**, a destination after "Volunteer & report" |
| #5 Challenge detail, #7 mystery | `screens/ChallengeDetail.tsx` — filters *On the trail · each section's short name · Mystery* |
| #4b Tagged place | a sheet over the detail: the hiker's own photo (matched on the phone by time and place, never uploaded) or the club's photo labelled so, the moment, the club's note, the line walked, a private register line |
| #5a Browse | `screens/ChallengeBrowse.tsx` — Trail, Club and Open-now filters; "On your plan" first, then the rest by distance from the plan. **No popularity sort and no hiker counts.** |
| #1 Map layer | a Legend switch "Challenge places", **off by default**, listed only when a joined challenge is on the chosen trail; a diamond pin from `map/poiIcons.ts`, hollow until tagged. The trail line is never recoloured. |
| #2, #2c Place card | "On your challenges" under the description, one row per item, **Tag it** |
| #3 Today | "From today's walk", once, after the day's walk ends, only when something was passed |
| #6, #6b Plan | the places on this route by day; when no joined challenge touches the route, the one best match, dashed, with Join and Hide |
| #8b, #8c Finish | with a reward, the entry; with none, "You walked …" and Done |
| #2a Org console | Org home → **Challenges**, and its **Finishers** sub-page |

## What proves it

- **Pipeline** — every POI resolves on the challenge's own trail; every place is within its
  radius of the centerline or says `off_trail`; windows are valid; a sealed item carries no
  clear title in the artifact; a finish line that can no longer be reached drops the challenge.
- **Client** — a sealed item never renders its title before `reveal_on`; progress never
  compares to anyone; leaving a challenge removes its pins and its Today card at once; the
  Today card lists only passed items and has no numeral for missed ones, and is absent when
  nothing was passed and after "Not tonight"; no challenge screen contains
  `/other hikers|behind|streak|rank|leaderboard/i`; the map with a challenge joined and the
  layer on adds no live region, no notification call, and does not change the plate; the
  Legend row is off by default and hidden with no challenge on the chosen trail; a tag
  written offline survives a flush with its authored time; Plan's route, mileage and day
  targets do not move.
- **Backend** — a repeated tag is idempotent; counts never carry a name; an entry after close
  is refused; only an org admin reads entries.

## What this is not

- **Not a leaderboard, a streak, a badge a hiker can show another hiker, or a score.** Rules
  1–4 above.
- **Not a notification.** OurHike sends none, and a challenge place is not an exception.
- **Not a new tab.** Today · Map · Plan · More are unchanged.
- **Not a way to farm taps.** Apart from the named `self_report` items, nothing moves without
  the hiker having been somewhere.
- **Not a photo upload.** The hiker's photo on a tagged place is matched on the phone and
  stays there.

## Open questions

- **The ATC's written terms** for sweepstakes entries collected through OurHike, and who is
  the data controller for an entry. Until they exist, the ATC's list stays `draft` and takes
  no entries.
- **Whether "Hikers in" is shown at all below a k-anonymity floor.** EVENTING.md uses k = 25.
  The console shows "fewer than 25" below it, which is this doc's placeholder rather than
  anybody's decision.
- **The tag radius per match kind**, above, and how GPS gaps are handled beyond the hand tag.
- **Whether the yellow diamond conflicts with yellow-blazed trails off the A.T.**
  HIKE_PLANNING.md refused a yellow route highlight for this reason; the diamond is a pin
  rather than a line, and is off by default, which is why it shipped anyway.
- **The ATC's 2027 dates.** `2027-05-15` to `2027-09-01` are the handoff's placeholders. The
  2025 PDF gives only the close ("by September 1").
