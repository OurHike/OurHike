# OurHike — Invasive Species (Feature Design Draft v1)

Companion to [../FEATURES.md](../FEATURES.md), [../OurHikeValues.md](../OurHikeValues.md) and
[../TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md). This document owns **what
happens to an invasive species sighting after a hiker files it** — who is qualified to have
filed it, how a trained surveyor's structured walk differs from a passer-by's glance, who
reviews both, and how either reaches the scientific record NYNJTC already keeps.

It builds on [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) (`invasive_species` has been a real
report type since 2026-07-30 and this adds no eighth one), reuses
[VOLUNTEERING.md](VOLUNTEERING.md)'s `MaintainerAssignment` shape for the credential and its
Ridge Runner At-Large task list for the surveyor mode, extends
`client/src/screens/Moderation.tsx`'s existing queue rather than building a second one, and
inherits [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)'s posture on what a sequence of
timestamped positions discloses about a person.

**Scope: v3, first feature** (2026-08-28). It is the first thing this project has designed
that sends a hiker's contribution **out** of OurHike to a third party, and most of the
design below is about that one sentence.

---

## Why this is worth building at all

NYNJTC runs a real invasive species programme, and it is older and more structured than
anything OurHike would invent. Volunteers are trained at in-person workshops, assigned a
trail section of roughly two miles, and taught to record a short list of target species —
last year beech leaf disease, spotted lanternfly, hemlock woolly adelgid, black swallowwort
and tree of heaven. Their findings go to `invasives@nynjtc.org` and into iNaturalist and
iMapInvasives.

**Two sources disagree about where iNaturalist actually sits in that programme, and this
document does not resolve it.** NYNJTC's own recruitment page says surveyors are trained on
iNaturalist and iMapInvasives; the training-resources page reachable on 2026-08-28 describes
printed field sheets — about ten per volunteer — returned as Excel spreadsheets, and does not
mention iNaturalist at all. Both can be true of different tiers of the programme, or one page
can be stale. It is an open question below, not an assumption here, and **it is the question
that decides whether Phase B or Phase C is the more valuable half of this feature.**

What is not in doubt is the shape of the opportunity. A surveyor walking an assigned
two-mile section, off-grid, recording onto paper is describing OurHike's existing
capabilities back to it: the app already holds the trail geometry, draws an offline map,
knows where the hiker is without a signal, and carries an outbox whose `authored_at` means a
sighting logged on Monday and flushed in town on Thursday still reads as Monday. Nothing
else NYNJTC could adopt has the trail data underneath it.

## The two kinds of reporter, and the two kinds of data

This is the distinction the whole design turns on, and it is not a matter of trust or
seniority. It is a difference in **what the data can support**.

| | Trained surveyor | Opportunistic hiker |
|---|---|---|
| Who | Workshop-trained, credentialed for named species | Anyone with the app |
| Where | An assigned segment, walked deliberately | Wherever they happened to be |
| What a record means | *I surveyed this segment and found X* | *I saw something here* |
| **Absence** | **Recordable and meaningful** | Not recordable at all |
| Volume | Dozens of people | Every hiker |
| Coverage | The segments the programme assigns | Everywhere people walk |

**Absence is the asymmetry that matters.** "I walked these two miles and found no tree of
heaven" is a scientific result — it establishes a negative at a place and time, which is what
lets a programme detect spread by comparing seasons. A passer-by's silence establishes
nothing: they may not have looked, may not have known what to look for, may have walked past
a stand of it at dusk. **A design that pours both into one bucket destroys the survey's
negatives**, because it becomes impossible to tell an unsurveyed mile from a surveyed and
clean one.

So the two are kept structurally distinct all the way through — different records, different
review treatment, and different marking on anything exported. This is
[../CLAUDE.md](../CLAUDE.md)'s "never let a display outrun its source" applied to a CSV
leaving the building.

The corollary is the good news: opportunistic reports are not second-class, they are
*differently useful*. They cover ground no surveyor is assigned to, and they are the top of
the funnel that Phase E turns into surveyors.

## What already exists, which is more than expected

Measured against the tree on 2026-08-28:

- **`invasive_species` is a full `ReportType`** (`backend/app/models/report.py`), deliberately
  separate from `animals` because one is an ecological observation and the other a safety
  encounter. It has a tile in `client/src/reporting/categories.ts`, a place in the outbox's
  draft union, backend tests covering its visibility and moderation, and it already flows
  `submitted → verified → public` through the existing queue.
- **`Moderation.tsx` is already "one queue surface, four resources"** in its own words —
  reports, closures, notes and photos, plus volunteer hours. A fifth resource is an addition
  to a screen that exists, not a new admin surface.
- **`VOLUNTEERING.md`'s Ridge Runner At-Large already names invasive species identification
  as a task type**, and explicitly frames it as "a lens over existing machinery, not new
  plumbing."
- **The outbox already carries `authored_at`**, which is what makes an offline survey
  possible at all.

**What does not exist is any path out.** Nothing in the tree mentions iNaturalist or
iMapInvasives. A verified invasive report today reaches a pin on OurHike's map and stops
there — which is the entire gap this feature closes.

## The rule that shapes everything downstream

iNaturalist's guidance on posting an observation somebody else made permits it under three
conditions, read on 2026-08-28: **you have the observer's permission, the description states
plainly that the observation is not your own, and you hold the date, location and context and
are willing to field questions about it.**

That is not a footnote. It is the constraint that makes a staff-review-then-submit flow
legitimate where a silent automated relay would not be, and three separate decisions below
fall out of it:

- **Consent is explicit and per-report, never inferred.** Filing a trail condition is not
  agreeing to publication on a public science platform under someone else's name. See
  "Consent is a new audience" below.
- **A human submits, and that human is named.** The submitter is the staffer's own
  iNaturalist account, not a shared organisational login — because "willing to field
  questions" is a property of a person, and a shared password makes it a property of whoever
  holds it this year. Observations are grouped by an iNaturalist *project*, which is that
  platform's own mechanism for exactly this and costs nothing.
- **No machine-asserted identification may reach a submitted field.** A staffer cannot field
  questions about an identification they did not make. This is argued at length under
  "Triage, not identification" because it is the point most likely to be optimised away later.

## Two different people, and only one of them is a role

The design needs to describe two people who are easy to conflate and must not be:

| | **The surveyor** | **The coordinator** |
|---|---|---|
| What they do | Produce observations | Review them and submit them |
| How many | Dozens per club | One or two per club |
| Qualified by | Workshop training, per species | The club's trust, and a named iNaturalist account |
| Modelled as | `InvasiveCredential` — many per person, species-scoped, dated | `Role.invasives` — one, on the profile |

**These are not the same grant and must not share a mechanism.** Collapsing them fails in
both directions: give every trained surveyor the power to submit on the organisation's behalf
and you have dissolved the accountability iNaturalist's rule is asking for, since "willing to
field questions" stops meaning anything when a hundred people share it; require the
coordinator to hold a credential for every species and you have a role that lapses the season
the target list changes.

**`Role.invasives` is a new fourth role** (maintainer's call, 2026-08-28), and the rest of
this section is about why it cannot simply join the existing moderator set.

### It must not join `MODERATOR_ROLES`

`MODERATOR_ROLES` is `(maintainer, club_admin)` and its definition in
`backend/app/models/profile.py` says exactly what it is for:

> The roles the moderation queue is gated to, **and** the roles that see a report's
> `reporter_id`. ONE constant, because those two rules must not drift apart: a moderator who
> can act on a report but cannot see who filed it, or worse the reverse, is a permission
> model that only looks like one.

Measured on 2026-08-28, that constant gates **thirteen endpoints in `routers/moderation.py`**,
one in `routers/field_notes.py`, and is the `privileged` flag in both `schemas/report.py` and
`schemas/field_note.py`. Adding `invasives` to it would hand an invasives coordinator the
closure queue, the photo queue, the volunteer-hours queue, every report type, and
`reporter_id` on all of them — including `bad_hikers`, which is `internal_only` precisely
because it reports on *people* and which REPORT_A_PROBLEM.md routes to safety moderators.
**An invasives coordinator has no business reading an account of somebody being followed on
the trail.**

So the role gets its own gate. Worth stating plainly that this makes it **the first scoped
moderation role in the codebase**: `require_role` already accepts any roles, but every call
site in the tree passes `*MODERATOR_ROLES`, so there is no narrower precedent to copy. That is
an architectural addition, not an enum value.

### `Role` becomes multi-valued, decided 2026-08-28

`profile.role` is one column holding one value today. A person is `hiker` **or** `maintainer`
**or** `club_admin` — never two. Adding `invasives` to that makes the problem concrete: a club
admin who also coordinates invasives has to pick one, and the failure path is easy to predict.
Whoever administers it picks `club_admin` because it is the more powerful of the two, nobody
ends up holding `invasives`, and the next person to hit the wall adds `club_admin` to the
invasives gate to unblock themselves. At that point the scoping exists only in the enum.

This document originally proposed working around that with a two-role gate,
`(Role.invasives, Role.club_admin)`, on the reasoning that a club admin can grant themselves
any role so excluding them buys a workaround rather than a restriction. **The maintainer chose
the model fix instead** (2026-08-28), and the argument for it is the stronger one: a workaround
documented today is a workaround somebody re-derives wrongly in a year, and *"this person does
two jobs"* is a fact more than one club will have about somebody. A permission model that
cannot express a true thing about the organisation using it will be worked around, and the
workaround is what stops being visible.

So roles become a set rather than a value. What that touches, named so it is costed rather
than discovered: the profile model and a migration, every `require_role` call site (all of
which pass `*MODERATOR_ROLES` today), `MODERATOR_ROLES` itself, the `privileged` derivation in
two schema modules, and the client's role handling. **This is the single largest item in Phase
A and the reason that phase is worth splitting** — see "Phase A is not really this feature's"
below.

### `reporter_id` needs a narrower answer than the constant gives

The coordinator genuinely needs to know who filed an observation — iNaturalist's rule requires
the observer's permission and an attribution naming them, so an anonymous sighting cannot be
submitted at all. But `privileged` is today a single boolean derived from
`viewer.role in MODERATOR_ROLES`, applied uniformly across every report type.

What this feature needs is narrower on two axes at once: identity **for `invasive_species`
reports only**, and **only where export consent was given**. That makes the serialiser's
`privileged` flag type-aware rather than role-aware alone, which is a real change to
`schemas/report.py` and is called out here so it is costed rather than discovered.

## Getting the coordinator an account, and the role onto it

**OurHike cannot create a user, and that is a deliberate security posture rather than a
missing feature.** `core/auth.py`'s `_get_or_create_profile` provisions a `profiles` row on
the first authenticated request, from the JWT's `sub` — so Supabase mints the identity and
this database follows. Creating (or deleting) a Supabase Auth user needs a service-role key,
which `app/config.py` holds deliberately not: AUTHENTICATION.md calls it "a credential that
can act as any user", and it is the same constraint that stops account deletion removing the
auth user. **So the pattern is invite, not create.** A coordinator signs themselves in with
the provider the deployment has enabled, and the club grants them the role afterwards.

**There is no way to grant any role at all today**, which is a larger gap than this feature's
own. Measured 2026-08-28: no router in `backend/app/routers/` assigns `role`, so it is set
once to `Role.hiker` at auto-provision and nothing changes it afterwards. `Role.invasives` is
therefore not a new enum value on an existing mechanism — **Phase A has to build the first
role-granting mechanism this backend has ever had.**

### For NYNJTC to start, a reviewed file — and the precedent is already here

`backend/load_assignments.py` solved this exact problem for maintainer assignments, and its
reasoning transfers without modification:

> An assignment says a named volunteer is at a known place on a predictable schedule … and it
> comes from a club's own records, in a spreadsheet, updated a few times a season. An endpoint
> would need its own authentication, its own audit trail and its own admin surface to be used
> safely, and would be used four times a year. A file in a pull request already has review,
> history, and a person who pressed merge.
>
> VOLUNTEERING.md's larger module is where a real admin surface belongs when clubs are
> managing themselves. This is the deliberate answer for one club getting started, not a
> substitute for it.

One club, one or two coordinators, a target list revised annually. That is the same shape, and
this section argued the file was therefore the right bootstrap.

**The maintainer decided otherwise on 2026-08-28: build `RoleInvite` instead.** The section is
kept rather than deleted because the argument it makes is still the right one to have had, and
because the *reason* it loses is specific and worth carrying: `load_assignments.py`'s case
rests on "would be used four times a year", and that premise expires at the second club. A
bootstrap whose justification has a known expiry date is one somebody has to come back and
replace, having meanwhile written the migration off it.

What survives from it unchanged is the destination — a real admin surface, in
VOLUNTEERING.md's phase E, which is the right home for value #7 because a reviewed file is
shaped like whoever holds the repository rather than like a club.

### An invite is a pending grant, resolved at first sign-in

The real awkwardness the file does not fix: a club cannot say *"make Jane our coordinator"*
until Jane has signed in and somebody has found her profile id. That is a bad first
experience for the one person whose participation the whole feature depends on.

**Decided 2026-08-28: build it, and it needs no service-role key.** Store a pending
`(email, role, club)` grant, and have the provisioning path apply any matching invite at the
moment it first creates the row. Jane is invited before she has an account, signs in with
Google, and is a coordinator on her first request.

The alternative this document recommended — a `load_assignments.py`-shaped reviewed file, on
the grounds that one club with two coordinators can have a profile id looked up by hand — was
declined in favour of building the real thing. Worth recording why that is defensible rather
than gold-plating: the reviewed file is not *less* work so much as work that gets thrown away,
because every club-admin surface after this one wants the same object, and the file's whole
argument ("used four times a year") stops holding at the second club. The cost is that a
feature branch carries generic infrastructure, which is the next section's problem.

Two things to check before building it, neither of them blocking:

- **Nothing reads an email claim today.** `get_current_user` reads only `sub`, and `claims` is
  in scope where the invite lookup would go — but that the claim is present should be
  confirmed against a real Supabase token rather than assumed from this paragraph.
- **Matching on email is only sound because the provider verifies it.** AUTHENTICATION.md
  already takes that position — "Google/Apple sign-in already verify the email on their end,
  so that is a Provider fact to trust" — which is what makes an emailed invite a safe join and
  would *not* hold for a self-hosted provider that skips verification.

### Whose name goes on the submission

`Profile.display_name` is the **trail name** and deliberately not a legal one
([IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)), so it cannot be what iNaturalist sees.
The coordinator's iNaturalist handle is a new field on the grant rather than on `Profile`,
because the overwhelming majority of accounts will never have one.

**And it is snapshotted onto each `SubmissionBatch`, not only looked up.** Same reasoning
`MaintainerAssignment` versions its rows: the batch has to record who submitted it *at the
time*, which survives the coordinator changing their handle, leaving the club, or deleting
their OurHike account. A submission whose accountable person can only be resolved through a
live foreign key is a submission that becomes anonymous the first time somebody moves on —
and "willing to field questions about it" is exactly the property that must not evaporate.

### Who this lets in, and who it does not

The worry that an open sign-up admits people who do not know what they are looking at is
right, and the answer is that **the three tiers have three different gates, deliberately**:

| | Gate | Inexperience costs |
|---|---|---|
| **Reporter** (opportunistic) | None — anyone with the app | Nothing. A coordinator reads it before it goes anywhere, which is what the review step is *for* |
| **Surveyor** (structured) | `InvasiveCredential`, granted after training | Would corrupt the survey's negatives — hence the credential |
| **Coordinator** | `Role.invasives`, granted by the club | Real, and the reason this one is never self-serve |

So the answer to "do we want inexperienced users" is **yes as reporters and no as
coordinators**, and the role/credential split is precisely what lets both be true at once.
Turning an inexperienced reporter away costs the coverage that is the opportunistic tier's
whole contribution; letting one submit on the organisation's behalf costs the organisation's
standing on a platform it does not own.

**The coordinator's two powers are worth naming, because they are asymmetric.** Submitting
under their own iNaturalist account is largely self-limiting — it is their reputation, in a
community that will correct them. Seeing reporter identities on invasive reports is not
self-limiting at all: it is a privacy exposure that the person exposed never learns about.
The second is the one that makes a careless grant expensive, and the reason the gate is a
deliberate act by a club rather than anything a person can ask for.

## The credential: granted, species-scoped, and dated

Now the other half — the surveyor, and what makes their observations worth more than a
passer-by's.

`ReporterType` is `thru | section | day | maintainer` and **it is self-declared** — the client
reads it from `preferences.reporter_type`. `Role` on the profile is `hiker | maintainer |
club_admin` and **it is granted** — server-side, gating `MODERATOR_ROLES`.

**So "maintainer" already means two different things in this codebase, one an assertion and
one a grant, and nothing connects them.** That ambiguity is harmless today because
`reporter_type` is only ever displayed as attribution — the schema calls it "the public
attribution by design… it informs without identifying." It stops being harmless the moment
anything downstream treats it as a qualification. Wiring a training credential to
`ReporterType` would be the easiest mistake in this feature to make and the hardest to
notice.

**Training follows `Role`.** VOLUNTEERING.md relaxed "grant, don't self-report" for volunteer
*hours* — claimed hours count until a club disputes them — and that was defensible because
the consequence of a wrong claim is bounded at a fee exemption. It does not transfer. A
self-declared credential attached to a species identification that reaches a public dataset
can trigger a management response: a removal crew, herbicide, and in the beech-leaf-disease
case potentially regulatory attention. The consequence is unbounded and lands on somebody
else.

**It is not a boolean.** NYNJTC's training is species-specific and its target list changes
year to year, so a blanket `trained` bit rots the first season the list moves. The credential
carries which species, granted by which club, effective from when — and is **versioned rather
than edited in place**, for the three reasons `MaintainerAssignment` already gives: you need
to know what somebody was certified for *when they filed*, not now; sections and rosters
change hands; and lookups are always as-of a date rather than implicitly "now".

**A club admin grants it in the app.** This is a deliberate choice over mirroring NYNJTC's
workshop roster from a reviewed file, and the argument is value #7: a reviewed file is shaped
like NYNJTC, an admin screen works for the next club that adopts this. The cost is honest and
worth stating — **it depends on [VOLUNTEERING.md](VOLUNTEERING.md)'s phase E club-admin
module, which that document deliberately schedules last.** Phase A below therefore builds the
smallest admin surface that can grant a credential rather than waiting for the whole module,
and says so.

## The survey: an assigned segment, and the negatives it can produce

This is the half that replaces paper, and the half only OurHike can build.

**A survey is a walk, not a sighting.** The record is the segment and the pass over it; the
sightings hang off it. That inversion is what makes absence expressible: a completed survey
with no black swallowwort row *is* the negative, and needs no separate "I saw nothing"
gesture from a tired volunteer at the end of two miles.

- **The segment comes from the club**, anchored the way `MaintainerAssignment` and
  SEGMENTS.md already anchor a stretch — real trail geography, not free text.
- **The target list is the club's and it is dated**, so a survey walked in 2026 is scored
  against 2026's five species rather than whatever the list says when somebody reads it back
  in 2029.
- **Everything is offline-first and nothing waits on a signal**, which is the existing outbox
  contract rather than a new one. A survey is opened at the trailhead, filled in over two
  miles with no bars, and flushed in town.
- **A survey may be abandoned**, and an abandoned survey is not a negative. Half a segment
  walked is half a segment surveyed, and the record says which half rather than quietly
  claiming the whole thing. This is the one place the design has to resist a convenience: an
  app that treats "closed the screen" as "finished the segment" manufactures negatives, which
  is worse than collecting nothing.

**What a surveyor records per sighting** is the ask REPORT_A_PROBLEM.md already lists for
this type — which species if known, rough extent, spreading or contained — plus a photo,
which is the default rather than the escalation for somebody who opted into this mode
(VOLUNTEERING.md's phase-A rule, applied here).

## The review queue

A fifth resource on `Moderation.tsx`, gated to `Role.invasives` per the section above, and
**its own queue rather than a filter on the existing one** — because the reviewer is a
different person doing a different job.

The existing moderator is a trail moderator, and the question they answer is whether a report
is a real trail condition worth showing hikers. Telling beech leaf disease from ordinary leaf
scorch is a different skill, and the club that has it is not necessarily the club that
maintains the mile. The separate role is what makes that separation real rather than a
convention: a trail moderator does not see this queue, and the coordinator does not see
theirs.

**Two verdicts, deliberately independent:**

| Question | Who | Consequence of yes |
|---|---|---|
| Is this a real trail condition worth showing hikers? | Trail moderator (existing) | The pin publishes |
| Is this a submittable observation? | Invasives reviewer (new) | It joins an export batch |

A report can pass either and fail the other, and neither blocks the other. A blurry photo of
a genuinely present stand is a fine trail pin and a poor scientific record; a crisp
photograph of a plant that is nowhere near the trail is the reverse.

**Uncertainty is not a rejection.** iNaturalist accepts an observation identified at genus,
at family, or as bare "plants", and its community refines it — so a reviewer who cannot tell
which knotweed it is submits it at the rank they *can* stand behind rather than discarding
it. That is value #4's honest-unknown posture arriving somewhere it happens to also be the
platform's own convention.

## Triage, not identification

The request that prompted this section was to have Claude sort the queue into what is good,
what is bad and what needs verification. That is worth building, and it is worth building
**narrower than it sounds**.

**What an assistant should do here** — all of it about the record, none of it about the
organism:

- Is there a photo, is it in focus, does it show a feature somebody could identify from
  (bark, leaf underside, growth habit) rather than a green blur at four metres?
- Does the note contradict the coordinates, or the coordinates the trail?
- Is this a duplicate of a report filed twenty metres away last Tuesday?
- Is the claimed species on this season's target list, and is this location within its
  plausible range?

That sorts a queue into *ready to submit / needs a better photo / probable duplicate /
off-target* and saves a reviewer real time while asserting nothing about taxonomy.

**What it must not do is identify**, for two reasons of very different weight.

The weak reason: iNaturalist already runs a computer-vision suggestion engine trained on
exactly this task, at the destination, and building a worse one upstream is wasted effort.

**The strong reason is the submission rule.** iNat's tolerance for posting somebody else's
observation is conditioned on the submitter being willing to field questions about it. A
staffer who forwards a machine-suggested identification they did not personally evaluate
cannot do that — so an automated identification flowing into a submitted field would break
the precise condition that makes this entire flow legitimate. **The assistant may sort the
queue. It may never be the reason something was submitted.** Anything it produces travels
visibly as a suggestion with its provenance attached, per this repository's standing rule
about what a claim rests on, and the record of who submitted an observation names a person.

`@unvalidated` — no part of the triage above has been measured. The photo-quality check in
particular is asserted to be useful and nobody has tested it against a real queue. What would
settle it: a hundred filed reports, a reviewer's own sort, and the disagreement rate between
the two.

## Reading the determination back

**The best thing this feature can do for a hiker costs no write access at all.** iNaturalist's
API is public for reads. Once an observation reaches research grade, OurHike can pull the
community's determination and tell the person who reported it what they actually found.

That is worth doing for three reasons, in ascending order:

1. It closes a loop that otherwise dead-ends. Somebody files a sighting and hears nothing,
   forever, which is the same silence DATA_NUDGES.md already worries about.
2. It is educational in the specific way that makes the next report better, and it is the
   only honest reward this repository's guardrails permit — **not a point, not a badge, an
   actual fact about a plant.**
3. It is the natural opening for Phase E's invitation: *you found a real thing, and NYNJTC
   trains people to do this properly.*

It also feeds back into the survey half. A determination that contradicts a credentialed
surveyor's identification is exactly the signal a club would want to see, and it arrives
without anybody having to audit anything.

## Turning a reporter into a surveyor

VOLUNTEERING.md's whole thesis is that "the distance between hiker and volunteer is smaller
than either side thinks, and it is mostly a matter of not knowing how." This is that
sentence with a specific programme behind it.

**The guardrail it has to clear is real.** That document forbids streaks, lack-states,
comparison and contribution counts used as motivation. *"You have filed five sightings — get
trained!"* is a progress bar wearing a hat, and it is the version of this that must not ship.

The version that clears the bar:

- **Offered contextually**, at the moment of maximum relevance — somebody who has just filed
  an invasive report, or just read back a determination, is already interested. That is
  VOLUNTEERING.md's own recruitment argument: the moment is a person standing on the section
  thinking *somebody looks after this*.
- **Offered once**, and not tracked. No count of how many times it was declined, because a
  count is the thing that becomes a nag.
- **An introduction, not an enrolment.** OurHike cannot make anybody a trained surveyor — the
  credential is NYNJTC's, issued at an in-person workshop. The app's entire role is the
  introduction, which is precisely the rule VOLUNTEERING.md already applies to
  `WorkProjectSignup`.

## Consent is a new audience, not an implied one

Two privacy questions that this feature raises and none of the existing ones do.

**Publication elsewhere is a separate act.** A hiker who files a trail condition has consented
to a pin on OurHike's map and a club moderator reading it. Publishing that observation to a
public science platform, with their name in the description under iNaturalist's
attribution rule, reaches an audience they were never asked about. So consent is explicit,
collected at report time, and revocable up until the batch is submitted — after which it
cannot be, and the surface has to say so, because an iNaturalist observation is not OurHike's
to withdraw.

**A sequence of sightings is a track.** `app/schemas/report.py` already withholds `reporter_id`
from the public report list for exactly this reason — "a stable account UUID next to a trail
position and a time is the linkability IDENTITY_AND_PRIVACY.md names: group by it and a
hiker's route down the corridor falls out, with curl and no account." An export of one
person's observations, timestamped and geotagged, reconstructs the same thing on somebody
else's platform. iNaturalist's CSV format carries a `geoprivacy` column, which is the lever.

**Decided 2026-08-28: exported observations carry open coordinates.** The reasoning is that
obscuring them defeats the record's purpose — an invasive sighting exists so somebody can be
sent to that exact spot, and iNaturalist's obscuring box is wide enough to make that
impossible. A record too vague to act on is not a safer record, it is a useless one that still
names its reporter.

**So the reporter's protection lives entirely in the consent gate, and that raises what the
gate has to say.** If precision is not negotiable, then "may we publish this?" has to be asked
in terms somebody can actually weigh: that the observation goes out with its exact location,
its date, and their name attached, on a platform OurHike does not control and cannot later
withdraw it from. A consent screen that says less than that is not consent to what actually
happens. This is the one place in the design where the honest answer made the copy harder
rather than easier.

Worth recording that the usual counter-argument does not apply: iNaturalist automatically
obscures coordinates for taxa of conservation concern, and invasive species are the opposite
case — precise locations are the point, and nobody is protecting a stand of knotweed. The
exposure here is the **reporter**, not the organism.

## Data model sketch

```
Role                               (EXISTING enum - BECOMES MULTI-VALUED, decided 2026-08-28)
  hiker | maintainer | club_admin
  + invasives                      (the coordinator: reviews and submits. NOT added to
                                    MODERATOR_ROLES - see "It must not join" above; it gets
                                    its own scoped gate, the first in this codebase.)
  -> profile.role stops being one column holding one value. A person holds a SET, so
     "club admin who also coordinates invasives" is expressible instead of being a
     workaround. Touches: the profile model + migration, every require_role call site,
     MODERATOR_ROLES itself, the privileged derivation in schemas/report.py and
     schemas/field_note.py, and the client's role handling.

ReporterType                       (EXISTING enum - `maintainer` IS RENAMED, decided
                                    2026-08-28, so one word stops meaning both a self-
                                    declared claim and a granted fact. Stored on existing
                                    report and field_note rows, so this is a data migration,
                                    not a rename. New value TBD - `trail_crew` is the
                                    working suggestion, not a decision.)
  thru | section | day | maintainer -> thru | section | day | <renamed>

InvasiveCoordinator                (new - the role grant, and where "their info" lives)
  id, profile_id, club_id
  inaturalist_handle               (NOT Profile.display_name, which is the trail name and
                                    deliberately not a legal one per IDENTITY_AND_PRIVACY.md.
                                    Most accounts will never have one of these.)
  granted_by, granted_at
  effective_from, effective_to     (a coordinator hands over; the record says when)

RoleInvite                         (new - a pending grant, so a club can name somebody
                                    BEFORE they have an account. Needs no service-role key:
                                    core/auth.py's provisioning path applies a matching
                                    invite at the moment it first creates the profile row.)
  id, email, role, club_id
  invited_by, invited_at
  consumed_at, consumed_by_profile_id
  -> email-matching is sound only because Google/Apple verify the address, which
     AUTHENTICATION.md already treats as "a Provider fact to trust".

InvasiveCredential                 (new - the grant, versioned like MaintainerAssignment)
  id, profile_id
  club_id                          (who granted it - a club, never self)
  species[]                        (the taxa this credential covers, not a blanket bit)
  effective_from, effective_to     (nullable `to` means current; lookups are as-of a date)
  granted_by, granted_at           (a club admin - never the volunteer)

SurveySegment                      (the club's assignment, not the hiker's choice)
  id, club_id
  trail reference, start/end       (real trail geography, per SEGMENTS.md's anchoring)
  target_species[]                 (dated - see season_year)
  season_year

SurveyPass                         (a walk over a segment - the thing that carries ABSENCE)
  id, survey_segment_id, profile_id
  walked_on
  state: in_progress | completed | abandoned
  covered_from, covered_to         (what was ACTUALLY walked - an abandoned pass says
                                    which half, and never claims the whole segment)
  -> a completed pass with no sighting for a target species IS the negative for it.
     Nothing separate is recorded, and nothing infers a negative from an abandoned pass.

InvasiveSighting                   (hangs off a pass, or stands alone)
  id
  survey_pass_id                   (nullable - null is the opportunistic case)
  report_id                        (the existing invasive_species Report this came from)
  species_claimed                  (nullable - "something is wrong here" is a valid report)
  extent, spreading                (REPORT_A_PROBLEM.md's existing ask for this type)
  export_consent: bool             (explicit, per-report, revocable until submitted)

SubmissionBatch                    (what a reviewer builds and a named person sends)
  id, reviewer_profile_id
  destination: inaturalist | imapinvasives
  submitter_identity               (the staffer's own iNaturalist handle, SNAPSHOTTED here
                                    rather than resolved through InvasiveCoordinator: the
                                    accountable person must survive a handle change, a
                                    hand-over, or that account being deleted)
  state: draft | submitted | failed
  submitted_at
  external_ids[]                   (what came back, so determinations can be read later)

UserPreferences                    (IDENTITY_AND_PRIVACY.md's existing canonical model)
  + invasive_export_consent_default: bool   (default false)
```

**The exported record is deliberately source-neutral.** iNaturalist's CSV import is the first
concrete target — its columns are taxon name, date observed, description, latitude, longitude,
tags and geoprivacy, read on 2026-08-28 — and **v1 needs no OAuth application at all**, which
removes the App ID gate, the token store and the 24-hour JWT expiry that a direct API
integration would have required. A reviewer downloads a file and uploads it.

**iMapInvasives is not a second target, which this document had assumed it would be.**
Researched 2026-08-28: iMapInvasives runs a dedicated New York project *on iNaturalist*, and
observations submitted there are loaded into iMapInvasives after its own quality-control pass.
So the state database is reached **through** iNaturalist rather than alongside it, and the
`destination` field below has one real value for New York rather than two. The source-neutral
record stays worth keeping anyway — a club outside this integration's five states would need a
second target — but it is now insurance rather than a known requirement, which is a smaller
claim than the one this paragraph used to make.

## Phase A is not really this feature's, and should be split out

Three of the four decisions taken on 2026-08-28 — multi-valued roles, `RoleInvite`, and
renaming `ReporterType.maintainer` — **have nothing to do with invasive species.** They are
identity and permissions platform work that this feature happens to be the first thing to
need. Counting what Phase A now contains makes the point better than an argument does:

| Item | Invasives-specific? |
|---|---|
| `Role` becomes multi-valued, with the migration and every call site | **No** |
| `RoleInvite`, and reading an email claim at provisioning | **No** |
| `ReporterType.maintainer` renamed, with a data migration | **No** |
| The first role-granting mechanism this backend has ever had | **No** |
| `Role.invasives` and its scoped gate | Partly — the *pattern* is general |
| Type-aware `privileged` in `schemas/report.py` | Partly — the *mechanism* is general |
| `InvasiveCoordinator`, `InvasiveCredential`, the as-of lookup | **Yes** |

**Four of seven rows are platform, and they are the four that carry migrations.** Building
them inside a branch named for invasive species hides them from everyone who later goes
looking for how roles work — which is the same failure ROADMAP.md records about feature docs
that shipped without ever being indexed.

**Recommendation: split Phase A into a permissions-and-identity piece of its own**, with
invasive species as its first consumer rather than its owner. This repository already has the
shape for that: [POI_IDENTITY.md](POI_IDENTITY.md) and
[POI_DEDUPLICATION.md](POI_DEDUPLICATION.md) are both scoped in ROADMAP.md as *"platform, not
a screen"*, and both were pulled out of the features that needed them for exactly this reason.

It also unblocks differently. Everything below Phase A waits on the NYNJTC question; the
platform work waits on nothing, and is useful to the club-admin module, to
[VOLUNTEERING.md](VOLUNTEERING.md)'s phase E and to any second club regardless of what NYNJTC
answers. **It is the one part of this feature that can start today.**

## Build order — six phases, each useful alone

- **A0 — Permissions and identity. Platform, not this feature.** Multi-valued roles and their
  migration, the first role-granting mechanism this backend has ever had, `RoleInvite` and the
  email claim it reads at provisioning, and the `ReporterType.maintainer` rename. **Useful
  alone and to more than this:** VOLUNTEERING.md's phase E, the club-admin module and any
  second club all want it, and none of it waits on the NYNJTC question. See the section above
  for why it should be split out rather than built here.
- **A — The role and the credential.** `Role.invasives` with its own scoped gate — deliberately
  not `MODERATOR_ROLES`, and the first scoped moderation role in the codebase — plus
  `InvasiveCoordinator`, `InvasiveCredential` and its as-of lookup, and the type-aware
  `privileged` change in `schemas/report.py`, since the role is worthless if it cannot see who
  filed what it reviews. **Useful alone:** it gives a club a way to say who its invasives
  coordinator is, which nothing in the app can express today.
- **B — The survey.** `SurveySegment`, `SurveyPass`, offline-first, absence expressible,
  abandonment honest. **Useful alone:** it replaces paper field sheets and produces better
  data than the current process even if nothing is ever exported from it, because an Excel
  return is a transcription step this removes.
- **C — The review queue and the export.** The fifth resource on `Moderation.tsx`, the
  source-neutral reviewed record, and the iNaturalist CSV. Survey rows first; opportunistic
  reports join the same queue in the same phase, tagged so the two never merge. **Useful
  alone:** it is the whole submission workflow, done by hand, which is what NYNJTC does today
  anyway.
- **D — Triage assistance.** Queue sorting on completeness, duplicates, target-list and range.
  Never identification. **Useful alone:** it is a time-saver over C and removing it leaves C
  working.
- **E — Determinations read back, and the invitation.** The public-read loop, and the
  contextual one-time offer to get trained. **Useful alone, and deliberately last** because
  it is the only phase that needs observations to already exist out there.

**Phase B is the one to build if only one gets built.** It touches the people whose problem
is worst, and it is the piece nobody else can build.

## What this deliberately isn't

**Not a second identification platform.** OurHike does not build community identification,
voting on determinations, or a taxonomy browser. iNaturalist does that well, and FEATURES.md
already flags community upvoting as needing a spam-resistant design while FIELD_NOTES.md
deliberately removed the thing that would be farmed. Submit, and read the answer back.

**Not an eighth report type.** `invasive_species` exists. This adds structure around it.

**Not a removal or treatment tracker.** What a club does about a stand of knotweed — who cuts
it, with what, when — is real work and is not this. It belongs with VOLUNTEERING.md's work
projects if it belongs anywhere.

**Not a notification.** HIKER_SAFETY.md's wrong-way alert remains the only push this app
sends, and nothing here is an exception. A determination read back is waiting in the app when
somebody next opens it.

**No badge, no count, no leaderboard.** A credential is visible to its holder and to the club
that granted it, and appears on nothing another hiker can see. VOLUNTEERING.md's Ridge Runner
reasoning applies unchanged and for the same reason: a credential another hiker can see is a
credential another hiker may take instructions from.

## Open questions

Six of the eight this document opened were closed on 2026-08-28 — four by the maintainer, two
by research. They are kept below the live ones, because a question's *answer* is worth less
than the record that it was asked.

1. **Is NYNJTC's bottleneck submission or transcription?** ⚠️ **The one that blocks, and the
   only one that cannot be answered from inside this repository.** If their surveyors are
   already on iNaturalist and the pain is coordination, Phase C is the feature. If they are on
   paper and the pain is the Excel return, Phase B is. Their own two pages disagree, so this
   is a question for a person at NYNJTC. **Ask before building either.** Note that Phase A0
   waits on none of it.
2. **Does a determination that contradicts a credentialed surveyor do anything automatically?**
   Recommendation is no — it is shown to the club and a human decides — but the alternative
   (a credential that lapses on repeated disagreement) is coherent and should be argued rather
   than dismissed. Phase E, so there is time.
3. **What does the renamed `ReporterType.maintainer` become?** The rename is decided; the new
   value is not. `trail_crew` is a working suggestion and nothing more — it wants whichever
   word a club actually uses, which is a question for NYNJTC alongside #1.

### Closed

- ~~**Which system is NYNJTC's record — iNaturalist or iMapInvasives?**~~ **Answered by
  research, 2026-08-28: the question was malformed.** iMapInvasives runs a dedicated New York
  project *on iNaturalist*, and observations submitted there "will be uploaded into
  iMapInvasives after quality control checks are completed" — reviewed, not automatic. So iNat
  is the submission surface and iMapInvasives is a downstream consumer of it; nothing has to
  choose. This also retroactively strengthens the decision to group observations by an
  iNaturalist *project* rather than a shared organisational login: the project is not just
  tidy, it is the routing. **One caveat worth carrying:** NY iMapInvasives' own "report an
  invasive" page does not mention iNaturalist at all while the network's tools page documents
  the integration, so the project's exact name and current status should be confirmed with
  `imapinvasives@dec.ny.gov` before anything is submitted into it.
- ~~**What is the default `geoprivacy` on an exported observation?**~~ **Decided by the
  maintainer, 2026-08-28: open coordinates.** An invasive record exists so a crew can be sent
  to that spot, and obscuring defeats it. The consequence is carried in "Consent is a new
  audience": the consent copy has to say the location goes out exactly.
- ~~**Should `Role` become multi-valued?**~~ **Decided by the maintainer, 2026-08-28: yes**,
  rather than the two-role gate this document proposed. See "`Role` becomes multi-valued".
- ~~**Does `RoleInvite` belong to this feature at all?**~~ **Decided by the maintainer,
  2026-08-28: build it**, rather than the reviewed-file bootstrap this document proposed. It
  is platform work, which is what "Phase A is not really this feature's" is about.
- ~~**Reconcile `ReporterType.maintainer` with `Role.maintainer`?**~~ **Decided by the
  maintainer, 2026-08-28: rename the self-declared one**, so one word stops meaning both a
  claim and a grant. It is a stored enum value on existing report and field-note rows, so it
  is a data migration rather than a rename. What it becomes is question 3 above.
- ~~**Is the App ID gate real?**~~ **Confirmed, 2026-08-28**, by two independent forum threads
  rather than the single one this document originally cited: registering an iNaturalist OAuth
  application requires an account **at least two months old with at least ten improving
  identifications in the last month**. It gates a *person*, it is satisfiable by any real
  coordinator, and the CSV path needs none of it — so it constrains who could hold a future
  direct-API registration rather than whether one is possible.
