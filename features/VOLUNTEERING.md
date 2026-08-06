# OurHike — Volunteering (Feature Design v2)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Builds on [AUTHENTICATION.md](AUTHENTICATION.md) (nothing here works without an identity), [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) and [DATA_NUDGES.md](DATA_NUDGES.md) (the contribution machinery already exists; this doc gives it a home and a reason), [SAYING_THANKS.md](SAYING_THANKS.md) (which already depends on this doc's `MaintainerAssignment`), and [PRICING_MODEL.md](PRICING_MODEL.md) (whose volunteer exemption has been blocked on the hours tracking designed below).

**Scope call, 2026-08-06: this is v2's second feature, after [HIKE_PLANNING.md](HIKE_PLANNING.md).** The v1 doc this replaces was Post-MVP and much smaller — a club-side work-project module plus a map layer showing upcoming workdays. That design is still here and still correct; it is now one of six pieces rather than the whole thing.

---

## The gap this closes, stated plainly

**OurHike exists to bridge hiking a trail and maintaining one. Every hiker is a potential volunteer.** v1 answers *where am I, what is around me, can I believe it*. [HIKE_PLANNING.md](HIKE_PLANNING.md) answers *where am I going*. Neither gives anything back to the people who cut the tread being walked on.

That gap is not incidental to this project — it is the reason the project exists. Value #2 says the app is "infrastructure for a volunteer culture that already exists, not a replacement for it," and value #9 names the behaviour directly: *"Nudge behavior toward volunteering with trail-maintaining clubs, packing out trash."* Both have been quoted in design docs for months while nothing shipped that a hiker could actually act on.

The asymmetry worth sitting with: a maintaining club's hardest problem is not funding, it is **finding people**. Its easiest recruitment moment is somebody standing on the section, on a good day, thinking *this is nice, somebody looks after this*. That moment happens with a phone already in hand, running this app. Today the app does nothing with it.

**The distance between hiker and volunteer is smaller than either side thinks, and it is mostly a matter of not knowing how.** So the design goal is not persuasion. It is removing the four things that actually stop people: not knowing help is wanted, not knowing when or where, not knowing whether they are qualified, and not knowing whether it mattered.

## What to call it — the tab name is a design decision, not a label

The user's first instinct was **Volunteer**, then **Maintain**. Both were worth a real argument, and the shortlist is worth recording so the question does not get reopened from scratch.

| Candidate | The case for | Why it loses |
|---|---|---|
| **Volunteer** ✅ | The word the clubs on the other end actually use. Verb as well as noun — *to volunteer* is an act, not only a category of person. Unambiguous to a first-time day hiker, which no other candidate manages. | Names a kind of person, and someone who does not think they are one may never open it. **Answered by what is behind the tab, not by renaming it** — see below. |
| **Maintain** | The user's suggestion; a verb, and the trail's actual need. | It is the **club's job description, not the hiker's**, and it is too narrow for what is in the tab: confirming a water source, logging hours, and reading your own record are three of the six pieces and none of them are maintenance. A tab whose label describes half its contents teaches people to skip it. |
| **Steward** | ATC's own register, and accurate — stewardship is exactly the relationship. | Another noun-identity, and a less familiar one. A day hiker on a Bear Mountain loop does not call themselves a steward. |
| **Trail Work** | Concrete, no identity claim, and the phrase clubs already use ("trail work day"). Was the runner-up on merit. | **Sits next to a tab called "Trail."** Two adjacent tabs sharing a first word is a legibility failure in the thumb zone, and renaming the map tab to fix it costs more than it buys. |
| **Give Back** | Warm, invitational. | Implies a debt. Value #1's whole posture is that the hiker owes the app and the app owes the hiker nothing; "give back" quietly asserts otherwise. |
| **Pitch In** | Genuinely inviting, zero identity claim. | Idiomatic. This is a safety tool read in bad weather by people for whom English may be a second language, and its register elsewhere is deliberately plain. |

**Recommendation: `Volunteer`.** The identity objection is real and is the strongest argument against it — but it is a problem about **the first screen, not the word**. A tab that opens on a sign-up form earns that objection. A tab that opens on *"three places near you would like a photo"* and *"a bridge crew nine miles south, Saturday"* does not, because both are things a person does before they would ever call themselves a volunteer. Fix the screen; keep the word everyone already understands.

**Tab count.** This makes three: `Trail`, `Volunteer`, `More`. [`client/src/chrome/tabs.ts`](../client/src/chrome/tabs.ts) already anticipates the tab set growing back and is deliberately data rather than markup, so this is one entry, not an edit to a component. That file also records why the Downloads tab was removed — *"a permanent target in the thumb zone, the most expensive space on the screen"* — and that bar applies here too. It is met: unlike Downloads, this tab has something new to say most days.

## The six pieces

### 1. Contributing trail conditions — a toggle, not a new mechanism

**[DATA_NUDGES.md](DATA_NUDGES.md) already designed this and stays its home.** Staleness tiers, the normalize-then-`match` pin styling, `ConditionConfirmation`, the escalation path into a real `Report` — all of it exists as design, and [`client/src/lib/staleness.ts`](../client/src/lib/staleness.ts) already ships the tiering (fresh ≤14d, ageing ≤60d, stale beyond). What this doc adds is three deltas, and they belong in Data Nudges' own file rather than being restated here.

- **An explicit opt-in.** Data Nudges is passive by construction — a hiker who never notices a differently-styled pin is never asked anything. Opting in says *yes, ask me*, which is what makes a slightly more assertive surface (below) legitimate rather than nagging. Off by default; lives in `UserPreferences` per [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md), not in a fifth settings model.
- **A photo becomes the default, not the escalation.** Data Nudges optimises for one tap because it interrupts someone who did not ask. Someone who opted in has consented to the longer version, and a photo of a dry spring is worth more to the next hiker than the word "dry." Still skippable — never a required field. Depends on [#89](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/89), the photo picker that currently discards photos.
- **Priority, stated as a rule the code can apply.** Water first, then shelters and campsites, then everything else — the user's own ordering, and the same scoping Data Nudges already uses. A viewpoint with no data is not a gap; a spring with no data is a hiker carrying the wrong amount of water.

**Nudging without notifications — four surfaces, all of them places the hiker already looks.** [HIKER_SAFETY.md](HIKER_SAFETY.md) pins the wrong-way alert as the only notification the app ever sends, and this feature must not become the second exception. It does not need to be:

1. **Map prominence.** Data Nudges' existing mechanism, unchanged.
2. **The waypoint lanes.** [`client/src/chrome/WaypointLanes.tsx`](../client/src/chrome/WaypointLanes.tsx) already renders what is coming in the next ten miles alongside the elevation ribbon — the single most-looked-at strip of the app. A stale water source ahead carries the same tier styling there. This is the highest-value surface of the four and it costs a `match` expression, because the lane is already drawn.
3. **The waypoint card.** Tapping a stale POI already opens [`PoiCard.tsx`](../client/src/chrome/PoiCard.tsx); the quick answer lives in it. No new screen.
4. **A "places you passed today" list in the Volunteer tab.** The one genuinely new surface, and the one with a trap in it: a list of missed opportunities is a guilt mechanic wearing a helpful hat. **The rule that keeps it honest: it never counts, and it never mentions what was skipped.** It is a shortcut for logging from memory at camp, not a scoreboard of the day's omissions. If it cannot be built without a number on it, it should not be built.

Everything queues through the existing offline outbox ([`client/src/lib/outbox.ts`](../client/src/lib/outbox.ts)), which already carries `authored_at` so a confirmation written at a spring on Monday and flushed in town on Thursday reads as Monday. That property is load-bearing here: **most of this feature's writes happen with no signal at all.**

### 2. Volunteer opportunities on a map, the next fourteen days

The v1 doc's "more important half," now with the in-app signup [PRICING_MODEL.md](PRICING_MODEL.md) has been waiting on.

**The read path.** Upcoming `WorkProject`s render as map pins, filterable to the next fourteen days, and list in the Volunteer tab sorted by distance from the hiker. They fit the existing ~8-category waypoint icon spec rather than inventing a visual language. No account needed to look — same as every other layer.

**The fourteen-day window forces a thing v1 never had to handle: this data expires.** Every other layer in the app is durable — a shelter is where it was last month. A workday nine days out is wrong the moment it is cancelled, and a downloaded map cannot know that. So:

- Opportunities are **never** baked into the offline package. They are fetched, cached with a fetch timestamp, and rendered with their age visible — reusing [`client/src/lib/syncAge.ts`](../client/src/lib/syncAge.ts) and the StatusStrip, which already exist to say exactly this kind of thing honestly.
- **Stale beyond about 48 hours, the app stops showing them as opportunities and says it is out of date instead.** Sending someone to a trailhead for a workday that was cancelled on Thursday is the failure mode, and value #4 makes that an easy call: an honest "I cannot tell you" beats a confident wrong answer.

**Signing up is an introduction, not an enrolment — and this is the part most likely to be got wrong.** A club workday is not an app event. Real ones carry waivers, minimum ages, tool-use training, and ATC volunteer registration; some are crew-lead-approved rather than open. **The app must never leave someone believing they are on a roster when they are not.** So a signup transmits an expression of interest and the club's own reply — confirmed, waitlisted, or "call me first" — and the app renders that reply plainly rather than a green tick of its own invention. Clubs that want real roster management get it in the admin module; clubs that want a mailto get a mailto. Both are legitimate, and the app's display has to be honest about which one it is talking to.

**Where the data comes from before club admin tooling exists** is unchanged from v1: a reviewed, pipeline-fed file, the same stopgap `sources.json` uses and [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) generalised. It does not scale past a handful of early-partner clubs, and it does not have to — but note the asymmetry the write path introduces: **signups need a live backend even while projects are still a static file.** Reads and writes can arrive in that order.

### 3. Ridge Runner At-Large

ATC runs a real Ridgerunner programme: seasonal, paid or stipended staff who walk assigned sections, talk to hikers about Leave No Trace, monitor shelters, and pack out what they find. **At-Large** is the volunteer, self-appointed version — a hiker already walking a stretch who elects to work while they do it.

**The shape.** A commitment record: a start and end date (**seven days maximum**), and a selection of task types — clean-up and pack-out, invasive species identification, general trail clearance. During the window, the app expects several submissions a day and shapes itself around that: contribution surfaces move to the front, the task selection filters what it asks about, and the pack-out and invasive paths reuse `Report` types that already exist (`trash`, `invasive_species` — both already in [`outbox.ts`](../client/src/lib/outbox.ts)'s draft union, so this is a lens over existing machinery, not new plumbing).

**Two things about this need to be said out loud, because it is the one feature in this repository that comes closest to what every other doc rules out.**

**It is the closest thing to a streak this app will ever have — and the seven-day cap is what keeps it from being one.** A commitment that ends cannot become an obligation that accumulates. There is no renewal prompt, no chain to break, no "you kept it up for 5 days." Missing a day does nothing: **the record shows what was submitted, never what was expected and missed.** A partial week is a week's worth of real work, and the app says so in exactly those terms. If a future change makes the window extendable, this paragraph is the thing it has to argue against.

**The name risks implying a credential, and that is a safety problem, not a branding one.** A hiker who believes they are talking to an ATC Ridgerunner may take instructions — about a closure, a fire, where to camp — from a volunteer with no authority to give them. So: **the app issues nothing that functions as a badge.** No shareable card, no title on a public profile, no on-map presence marking where an At-Large runner is. The role is a mode the app is in, visible to its user and to the club receiving the data, and to nobody else. **Recommendation: qualify the name wherever a third party could see it** ("volunteer trail monitor" in anything club-facing or public), keeping "Ridge Runner At-Large" as the in-app name for the person who opted into it. Flagged as an open question below rather than force-decided, because it is ATC's call as much as ours.

### 4. Logging hours

**Self-logged, club-confirmed — two states, and the distinction is the whole design.** A volunteer records date, hours, club, what they did, and roughly where. That record is immediately real to *them* and provisional to everyone else until a club admin confirms it.

**Why not just trust the number?** Because it has an external consumer. [PRICING_MODEL.md](PRICING_MODEL.md) already ruled on it — *"Grant, don't self-report"* — for the 40-hours-a-year fee exemption, and the same reasoning as [HIKER_SAFETY.md](HIKER_SAFETY.md)'s severity tier: users do not unlock value by asserting it. But there is a bigger consumer than our own pricing. **Clubs report volunteer hours upward, to ATC and to the land-managing agencies, and those numbers carry real weight in real funding decisions.** A number this app feeds into that chain has to be one a club is willing to put its name on.

That is also the reason hours are **claimed, not computed**. The app could infer them from GPS and would be wrong constantly — a lunch break, a drive to the trailhead, a phone in a pack all day. Ask the person. They know.

Hours attach to a `WorkProject` where one exists (a confirmed attendance pre-fills the claim, so the common case is a confirmation rather than a form), and stand alone where none does — most maintenance is somebody going out on a Tuesday because a blowdown needs clearing, and a design that only counts organised workdays would miss the majority of the work it is trying to honour.

### 5. The impact dashboard — and the guardrail it has to get past

**This is the request that contradicts something this repository has written down four separate times**, and pretending otherwise would be the wrong way to build it. [DATA_NUDGES.md](DATA_NUDGES.md) says it most flatly: *"no per-hiker contribution counts shown anywhere."* [SEGMENTS.md](SEGMENTS.md), the v1 of this doc, and [PRICING_MODEL.md](PRICING_MODEL.md) each say a version of the same. A dashboard of everything you have contributed is, on its face, exactly that.

**The reconciliation: the guardrail's target is comparison and pressure, not memory.** Read the four statements together and what they actually prohibit is leaderboards, streaks, public volunteer profiles, ranking against other hikers, and messaging about what you have not done. Every one of those works by putting a second person in the frame — or a future self you are failing. A private record of what you did is a logbook, and maintainers have kept logbooks since long before there was an app to keep them in.

So the dashboard ships, under four rules that are the actual guardrail restated rather than waived:

1. **Never comparative.** No ranking, no percentile, no average, no "other hikers on this section." Nothing that answers *how am I doing compared to.*
2. **Never a lack-state.** It shows what happened. It never shows what did not: no streaks, no "you have not volunteered since June," no progress bar toward a target nobody set. **The single exception is the fee exemption's 40-hour threshold** — a real external rule with a real consequence, shown only to someone who has asked about it, and shown as a status rather than a goal.
3. **Private by default.** No public volunteer profile — the v1 doc's rule, unchanged. Sharing is an **export** (value #6: GPX/GeoJSON/CSV, the same portability commitment everything else in the app makes), which is a hiker handing someone a file, not the app publishing a page.
4. **Counts real things, never points.** Hours, workdays attended, miles walked as an At-Large runner, conditions confirmed, invasives logged, trash packed out. **No single composite score**, because the moment there is one number there is a thing to maximise, and the feature has become the one it promised not to be.

**What makes this defensible is that it is not primarily motivational.** It is a receipt, and the receipt has consumers who are not the hiker: the club that has to certify the hours, the agency the club reports to, and the fee exemption. A dashboard that exists because a number has to leave the building anyway is a different object from one built to keep people engaged — and if the honest answer at build time is "we would ship this even with no external consumer, to drive retention," that is the version this guardrail exists to stop.

The one thing the dashboard should do that a spreadsheet cannot: **show it on a map.** Where you worked, over time, on the trail you worked on. That is the version of "how much good have I done" that a hiker actually feels, and it is the version least convertible into a score.

### 6. Club-side work-project management

Unchanged from v1 and still the last piece to build. Clubs create, schedule and track their own workdays; confirm attendance; confirm hours. It needs real authenticated admin access, which [AUTHENTICATION.md](AUTHENTICATION.md) exists to provide and [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md)'s Backend section already names "multi-club admin" as a use case for.

**The sequencing point from v1 holds and is worth restating: the hiker-facing half does not need this to exist first.** Confirmation is the only place this module is genuinely load-bearing — and hours can sit in `claimed` for a while without harm, because a hiker's own record is real to them immediately and only the exemption depends on confirmation.

## Maintainer assignments — who looks after which stretch, and when

**Added 2026-07-29**, pulled in by [SAYING_THANKS.md](SAYING_THANKS.md): to let a hiker thank a maintainer they cannot name, the app has to be able to answer *"who looks after this mile?"* from a location alone. That question turns out to be useful well beyond thanks — it is the same lookup a closure, a shelter-repair report, or a work project needs to route itself to the right club. Already partly built: [`client/src/lib/maintainerLookup.ts`](../client/src/lib/maintainerLookup.ts).

```
MaintainerAssignment
  id
  maintainer_id      (a Profile with the maintainer role)
  club_id            (the club the assignment is made by)
  trail reference    (which centerline - same inheritability note as Segments)
  start reference, end reference
                     (real trail geography, NOT free text - the same anchoring
                      SEGMENTS.md already specifies: a mile-marker point, a
                      shelter/campsite/parking POI, or a pin snapped onto real
                      trail geometry via MAP_OPTIONS.md's ST_LineLocatePoint math)
  effective_from     (date the assignment starts)
  effective_to       (nullable - null means "current")
  publicly_creditable (bool, default false - see SAYING_THANKS.md's opt-in rule)
```

**Why assignments are versioned rather than edited in place.** Sections change hands. A record that is simply overwritten can answer "who looks after mile 1,043 today" and nothing else — but the questions that actually matter are historical: who cleared this in June, who should hear about a report written three weeks ago, who was responsible when this bridge was last inspected. `effective_from`/`effective_to` make those answerable; an editable `current_maintainer` field destroys the answer every time a section is reassigned.

**Resolution returns zero or more, never exactly one.** Stretches overlap at boundaries, hand off mid-season, and go unassigned when a volunteer steps back. Any consumer of this lookup has to handle all three: zero means fall back to the club, two means both hear about it.

**Lookups are always as-of a date, never implicitly "now."** See [SAYING_THANKS.md](SAYING_THANKS.md) for the case that forces this — a thanks written in June, synced in August, about a section reassigned in July belongs to the June maintainer. Defaulting the lookup to "now" would quietly misattribute it, and misattributed credit is worse than none.

## Data model sketch

```
Club                               (first-class, per Multi-club support, value #7)
  id, name, region/scope

WorkProject
  id, club_id
  title, description
  location reference               (point, or a start/end pair along the centerline for
                                    "clear blowdowns miles 40-45" - the same anchoring
                                    MaintainerAssignment uses above)
  starts_at, ends_at               (a date range covers the single-day case; recurrence
                                    is deliberately not modelled - see open questions)
  status: upcoming | completed | cancelled
  capacity                         (nullable - null means "no cap stated")
  signup_mode: contact | in_app    (a mailto/phone club and a roster club are both
                                    first-class; the app renders which one it is)
  signup_contact                   (contact mode only)

WorkProjectSignup                  (new - the RSVP PRICING_MODEL.md has been blocked on)
  id, work_project_id, user_id
  state: interested | confirmed | waitlisted | declined | cancelled_by_volunteer
                                   (`confirmed` is set BY THE CLUB, never by the app -
                                    see "an introduction, not an enrolment")
  attended                         (nullable - set after the fact, pre-fills an hours claim)

RidgeRunnerCommitment              (new)
  id, user_id
  starts_on, ends_on               (7 days maximum, enforced server-side too)
  tasks[]: cleanup_packout | invasive_species | trail_clearance
  club_id                          (nullable - resolved from MaintainerAssignment where
                                    the hiker does not know which club's section it is)
  -> submissions are ordinary Reports/ConditionConfirmations tagged with this id;
     no new submission model, and no completion/streak state anywhere

VolunteerHoursRecord               (the model PRICING_MODEL.md sketched, filled in)
  id, user_id, club_id
  worked_on (date), hours
  work_project_id                  (nullable - most trail work is not an organised workday)
  ridge_runner_commitment_id       (nullable)
  activity: maintenance | cleanup | monitoring | education | admin | other
  location reference               (nullable)
  state: claimed | confirmed | disputed
  confirmed_by, confirmed_at       (a club admin - never the volunteer)

UserPreferences                    (IDENTITY_AND_PRIVACY.md's existing canonical model)
  + contribute_conditions: bool    (default false - the opt-in toggle, piece 1)
```

## Build order — five phases, each useful alone

The same shape [HIKE_PLANNING.md](HIKE_PLANNING.md) uses, and for the same reason: a phase that is not useful on its own is a phase that can be cut without noticing.

- **A — The tab, and the contribution toggle.** Third tab, the opt-in preference, the waypoint-lane and waypoint-card surfaces. Ships [DATA_NUDGES.md](DATA_NUDGES.md), which has been designed and unbuilt since July, and needs no new backend beyond what [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) already has. **Depends on [#89](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/89)** for photos to survive.
- **B — Opportunities, read-only.** `WorkProject` from a reviewed pipeline-fed file, the fourteen-day map layer and list, honest staleness, contact-mode signup (a mailto). A club can be useful to a hiker here with no admin tooling and no write path at all.
- **C — Hours, self-logged.** `VolunteerHoursRecord` in `claimed`, and the first version of the dashboard on top of it. Useful to the volunteer immediately; useful to nobody else until D.
- **D — In-app signup and club confirmation.** `WorkProjectSignup`, attendance, hours confirmation. **This is the phase [PRICING_MODEL.md](PRICING_MODEL.md)'s volunteer exemption unblocks on** — worth knowing, since that dependency has been sitting in that doc unresolved.
- **E — Ridge Runner At-Large, and the club admin module.** The most scope, the most club conversation needed, and the least useful without A–D underneath. Deliberately last.

**Phase A is worth doing whether or not B follows.** It is the piece that touches every hiker rather than the small number who will attend a workday, and it is the one that makes the trail data better for everyone including people who never open this tab.

## What this deliberately isn't

No leaderboard. No public volunteer profile. No streaks. No comparison to other hikers. No composite score. No badge a hiker can show another hiker. No notification of any kind — [HIKER_SAFETY.md](HIKER_SAFETY.md)'s wrong-way alert remains the only one the app ever sends, and nothing in this feature is an exception to it.

And, per value #9's own warnings: no broadcasting of large gatherings, and nothing that turns a workday into an event to be amplified. Small, well-timed, and local is the whole point.

## Open questions

- **The Ridge Runner name, and whether ATC is comfortable with it.** Recommendation above is to qualify it in anything a third party sees. This is a conversation with ATC, not a decision this repository can make alone — and it should happen before the name reaches a screen, not after.
- **Recurrence for work projects.** Deliberately unmodelled above; a date range covers a single day and a weekend. "Every third Saturday" needs real structure and should be decided from what clubs actually run, not guessed at.
- **Whether hours in `claimed` count for anything before confirmation.** They are real to the volunteer immediately. Whether an unconfirmed hour is exportable, or reportable, or shows in a club's totals, is a policy question with an audit consequence — flagged, not decided.
- **What happens to a signup when a hiker's plan changes**, which on a thru-hike it constantly does. A no-show costs a club a crew slot, and the honest mitigation is probably making cancellation one tap and utterly consequence-free rather than tracking reliability — but that edges toward a reputation score, which rule 1 above rules out. Worth deciding explicitly.
- **Minimum age, waivers, and tool training**, which are real club and ATC requirements the app currently knows nothing about. The introduction-not-enrolment framing keeps this from being a liability the app takes on, but a club will eventually want to state a requirement before someone travels to a trailhead for nothing.
