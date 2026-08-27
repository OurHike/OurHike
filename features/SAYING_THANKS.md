# OurHike — Saying Thanks to a Maintainer (Feature Design v1)

Companion to [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md), [VOLUNTEERING.md](VOLUNTEERING.md), [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md), and [WIREFRAMES.md](../WIREFRAMES.md).

**Resolves [WIREFRAMES.md](../WIREFRAMES.md) Known Deviations #2**, open since 2026-07-28. Turn 14 of the wireframe introduced a "Say thanks to a maintainer" card with no data model behind it, and the wireframe doc itself flagged that this needed a product decision rather than a docs-hygiene pass. **Decided 2026-07-29:** a thanks is *a comment from a user about a specific place* — a report type, with the same fields plus photos, optionally tagging the maintainer responsible.

That decision is small to state and drags a real dependency behind it: to let someone thank a maintainer they can't name, the app has to know **who looks after which stretch of trail, and when**. That model is designed in [VOLUNTEERING.md](VOLUNTEERING.md) alongside `Club`, and referenced here.

---

## The shape

A thanks is the seventh `Report` type. Same location reference, same note, same photo, same authored timestamp:

```
Report
  type: blowdown | trash | bad_hikers | flooding | shelter_repair | animals | thanks
  ...all existing fields unchanged...

  maintainer_id   (optional) - who this is for, when the hiker knows
  club_id         (optional) - who this is for, when they only know the club
```

Both attribution fields are optional and both can be empty: "someone cleared forty blowdowns out of this mile and I have no idea who" is a *complete* thanks, and the app resolves it by location (below) rather than refusing it.

**Why a report type and not a new model.** It shares every field, the same offline outbox, the same location anchoring, and the same photo path. A parallel model would duplicate all of it to express one different word. The places it genuinely diverges are handled explicitly below rather than by forking the whole thing.

## Where a hiker reaches it (added 2026-08-27, #1133)

Three entry points, and each is there because it answers a different question.
The first two shipped in #1133; the third is the map's long-press plate, still
to come.

- **The foot of Today**, beside "Report a problem" at the same width and the
  same weight. The pair is the point: reporting a problem and thanking a crew
  are two sides of one relationship, and an outline button beside a filled one
  would say, in the only language a button has, which of the two is the
  afterthought. This is the general-purpose entry — it anchors on the hiker's
  own fix.
- **A place's card**, under the "Something wrong here?" plate and in the same
  construction with a green accent instead of a red one. **This is the one
  that knows which place is being thanked for**, so the thanks carries a
  `poiId` and can be routed by the same club lookup described below, rather
  than landing on whatever stretch the hiker happens to be standing on when
  they remember to send it.
- **The map's long-press plate**, for a stretch of trail with no waypoint on
  it — the "someone cleared forty blowdowns out of this mile" case this doc
  opens with. Not built yet.

**A thanks never files on a tap**, unlike the six condition types that do
(REPORT_A_PROBLEM.md's core flow). It always opens the form. The reason is not
symmetry: a thanks is a message to a person, and an empty one sent by accident
is worse than none sent at all. `reporting/categories.ts`'s `filesOnTap` names
it alongside "something unsafe happened" as the two exceptions.

**No entry point claims who maintains the place.** The card's hint reads "Say
thanks to whoever keeps it up" rather than naming a crew, because the app does
not know until the form asks — and the lookup below returns null for a stretch
with nobody assigned. Naming a maintainer on the entry would be the card
asserting, in warm words, a fact it has not looked up.

## Where it diverges from a condition report — and why each one matters

These are not incidental. A thanks routed through the report machinery unchanged would behave badly in four specific ways.

### 1. It never enters the moderation queue

There is nothing to verify. A blowdown is a claim about the world that a maintainer can go and check; a thank-you is not. Putting it in the queue that [MAP_OPTIONS.md](MAP_OPTIONS.md)'s closures and [HIKER_SAFETY.md](HIKER_SAFETY.md)'s warnings share would bury real safety work under mail that needs no decision.

It still needs a *removal* path — someone will eventually write something unkind in a thanks box — but that is abuse handling, not verification. Moderators can hide one; nobody has to approve one.

### 2. The four report states do not apply

[WIREFRAMES.md](../WIREFRAMES.md) pins Waiting → Confirmed → Fixed, or Not confirmed as load-bearing words. Every one of them is wrong here, and **"Not confirmed" on a thank-you note would be actively insulting** — it reads as the app telling someone their gratitude was rejected.

A thanks has one state the sender cares about: it was delivered. `Sent` while queued in the outbox, `Delivered` once the server has it. Nothing else.

### 3. It is not public, and not `internal_only` either

The existing `visibility` enum is `public | internal_only`, and neither fits:

- **Not `public`.** A thanks is not a hazard and does not belong as a pin on the safety map. More importantly, publishing praise that names a specific volunteer exposes a private individual's identity and movements — the same concern [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md) applies to hikers applies at least as strongly to unpaid volunteers who never signed up to be publicly visible.
- **Not `internal_only`.** That value was named for `bad_hikers` and means *"goes to safety moderators."* Thanks go to the **club and the maintainer** — a different audience, for a different reason (morale, not risk). Reusing the value would make "who can see this" depend on reading the type as well, which is exactly how a privacy rule gets misapplied later.

So: **add a third value, `club_only`.** Distinct recipients deserve a distinct value.

### 4. `severity` and `follow_up` stay untouched

Both are already server-controlled and both stay at their defaults. Noted only so nobody wires a "how thankful" scale into `severity`.

## Resolving "who do I thank?" by location

The hiker usually will not know a name. They know they are at mile 1,043 and someone has clearly been working.

**Resolution:** given the thanks' location and its **authored time**, look up the `MaintainerAssignment` records covering that point at that moment (model in [VOLUNTEERING.md](VOLUNTEERING.md)).

**Authored time, not now** — this is the part that is easy to get wrong. If someone thanks a maintainer in June for June's work, and the segment is reassigned in July, and the thanks syncs from an outbox in August, it belongs to **the June maintainer**. Resolving against "now" would hand a stranger someone else's credit and silently rob the person who earned it. The `authored_at` field on reports exists precisely so this is answerable.

**Resolution returns zero or more, never exactly one.** Stretches overlap, hand off, and go unassigned. Zero is a normal answer — the thanks still goes to the club, or is simply held with its location. Two is also normal, and both hear about it.

## Individual attribution is opt-in

A maintainer's name is only ever shown to a hiker if that maintainer has opted in to being publicly creditable. Default is **club-level**: "the Mountain Club looks after this stretch."

This is a deliberate privacy default, not caution for its own sake. Maintainers are volunteers, frequently older, often working alone on a remote trail section on a predictable schedule. A feature that tells strangers a named individual's regular location is a real safety exposure, and one they never asked for by signing up to clear blowdowns. Clubs can opt individuals in where they have consent.

## What this deliberately is not

- **Not a rating or review system.** No stars, no scores, no "rate this section." [WIREFRAMES.md](../WIREFRAMES.md) already states negative feedback is nudged to the club directly rather than becoming a public complaint, and value #1 (hike your own hike, no prescriptive gamification) rules out the leaderboard this would otherwise grow into.
- **Not a volunteer scoreboard.** [VOLUNTEERING.md](VOLUNTEERING.md) already forbids leaderboards of volunteer hours; a "most-thanked maintainer" ranking is the same idea wearing a nicer hat, and would quietly turn unpaid work into a competition.
- **Not a contact channel.** A thanks is one-way. Building replies means building moderated messaging between strangers and volunteers, which is a much larger feature with a much larger safety surface.

## Open questions (for you, not decided here)

- **Does a maintainer get notified?** OurHike's one-notification policy says the wrong-way alert is the only push. A thanks should almost certainly reach a maintainer as in-app or digest email, never a push — but "email volunteers" is a channel this project does not have yet, and adding one is its own decision.
- **Can a hiker see the thanks they have sent?** Their own, certainly. Whether they see that it was read is a different question, and "read receipts on gratitude" may add pressure where none is wanted.
- **Club-level vs crew-level.** WIREFRAMES.md's original copy offered "the club or a specific crew." Crews are a real organisational unit in some clubs and absent in others; modelling them now risks inventing structure that does not match how partner clubs actually work. Recommend club + optional individual for v1, crews later if clubs ask.
- **Abuse handling specifics.** Hiding an unkind "thanks" is clearly needed. Whether that reuses the moderation queue's dismiss action or gets a lighter path is a moderation-policy call, and this doc has deliberately kept thanks *out* of that queue.
