# OurHike — Pricing Model (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md) (extends its existing "Business model" section directly, not a rewrite), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Builds on [AUTHENTICATION.md](AUTHENTICATION.md) (entitlements live on `User`), [SEGMENTS.md](SEGMENTS.md) (a Hike's `type` scopes the thru-hike pass), [VOLUNTEERING.md](VOLUNTEERING.md) (the volunteer exemption needs real hour-tracking that doesn't fully exist yet), [TRIP_PLANNING.md](TRIP_PLANNING.md) and [COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md) (the actual gated content).

**Scope:** Post-MVP, and deliberately not time-boxed to a phase - you said the timing is genuinely undecided ("right away, or... wait a while"). This doc is about building the *structure* now so turning it on later is a flag flip, not a redesign - per your own framing, not about landing on exact dollar amounts.

---

> ## Superseded in part, 2026-08-27 — read this before the rest
>
> **Every part of this document that routes a hiker's money *through* OurHike to
> a trail organization is no longer the plan.** Not deferred, not unbuilt —
> decided against. The maintainer, 2026-08-27, in their own words:
>
> > *"There is no funding model today for the orgs. The hope is we will drive
> > membership and donations to those orgs."*
>
> and, asked directly whether the pass-through model still stood, chose direct
> giving as the model: **money never passes through OurHike.** A hiker who wants
> to support the trail gives to the ATC, a club or a preserve on that
> organization's own site. OurHike links out, takes no cut and holds no money.
>
> **What survives**, and is still the useful half of this doc: everything about
> **OurHike's own** sustainability — what it might charge for its own
> convenience features, where that charge can live, and the values that keep
> safety free for everyone. Pricing values #1–#5 are untouched.
>
> **What does not survive:** `revenue_beneficiary`, "a thru-hike pass funds the
> ATC", "revenue routes to that specific club", "a mission-funding alternative",
> and the framing of a pass as a way to give to the trail. Those are struck
> through in place below rather than deleted, so the reasoning that produced
> them stays readable — the same treatment [MAP_OPTIONS.md](MAP_OPTIONS.md)
> gives its closed questions.
>
> Value #6 is rewritten rather than struck, because [WEBSITE.md](../WEBSITE.md)
> §5.5 cites it **by number** and a dangling citation is worse than a corrected
> one.

---

## The real tension this doc has to resolve

Two of OurHike's own values are now in direct tension for the first time in this project: value #5 (free/accessible) and value #8 (sustainable). Every other feature so far has treated these as compatible by default. This one can't - it exists because they aren't, always. The rest of this doc is one resolution, not the only possible one.

## Pricing values, the same way OurHikeValues.md states principles before features

1. **Never gate safety.** Core map, water, shelters, GPS, elevation, closures, and warning pins stay free forever, for everyone, regardless of ability to pay. This isn't a new principle - it's FEATURES.md's existing "never a gate on safety-relevant info" line, made concrete.
2. **Access before revenue, when they conflict.** Day-hikers and hardship cases resolve in favor of access, not the other way around.
3. **Contribution stays free.** Reporting a problem, confirming conditions, marking a closure - gating any of these would shrink the data that makes every tier, including the free one, valuable. A two-sided resource doesn't get better by charging the side that supplies it.
4. **Volunteers don't owe us money.** Confirmed trail work earns complementary access, offered with appreciation - never withheld as leverage, never assumed without being asked.
5. **Pay for convenience and connection, not facts.** The underlying data and code stay open (values #3, #6) - what's actually sold is a maintained, polished experience on top of open data, the same relationship GitLab or Mattermost have to their own open cores. If someone would rather build their own tool from the open data, that was always the deal.
6. **Money never passes through OurHike.** A hiker who wants to support the trail gives to that organization **directly, on the organization's own site** - OurHike links out, takes no cut and holds no money. The registry carries, for the three stewards of seven that have one, that organization's own donate URL and their own button text verbatim - plus `donate_recipient` where the destination is somebody else, as it is for NYS OPRHP, a state agency whose link resolves to the Natural Heritage Trust. It carries no words of OurHike's about what the money does: `donate_blurb` is a field for the *organization's* own sentence and no organization has sent one, which `test_no_organization_has_sent_words_about_what_the_money_does` holds against the real registry. **Settled by the maintainer 2026-08-27**, replacing *"Money follows the trail it came from. A thru-hike pass funds the ATC; a regional pass funds that region's own club - not a shared, undifferentiated pool."* That sentence was a routing rule for money OurHike would have held; there is no such money and there is not going to be. See the superseded banner above.

## The one rule that resolves almost everything else: reuse the MVP/Post-MVP line, don't invent a new one

**Everything already committed to v1 MVP stays free - the paywall boundary is the same line already drawn between MVP and Post-MVP, not a new classification scheme.** This project has already spent a dozen design docs deciding what's safety-critical enough for MVP (trail line, water, shelters, GPS, elevation profile, closures, serious warnings, the wrong-way alert) versus what's a genuine convenience layer (Trip Planning, Community Building, most of Map Options, most of UX Customization). That existing line is exactly where the free/paid boundary belongs.

**Real competitive validation, checked directly rather than assumed:** AllTrails+ and Gaia GPS's premium tiers both gate **offline map download** specifically - the single feature this project has repeatedly, deliberately kept free in MVP ("why would I use this over a browser tab"). That's not an oversight to reconsider - it's a genuine point of differentiation worth naming plainly: where the two dominant competitors paywall the thing a hiker needs most when they have no signal, OurHike doesn't, because that's exactly the safety data value #5 already commits to keeping free. Same story with AllTrails+'s paid "wrong-turn alerts" versus OurHike's free (and only) wrong-way notification.

**Two nuances worth being precise about, since the MVP/Post-MVP line isn't a perfect copy-paste:**
- **Hiker Safety's weather section splits down the middle.** Section 3 (the NWS alert relay - severe weather warnings) is safety-relevant enough to stay free even though it's Post-MVP. Section 4 (daily conditions/forecast - a nice-to-have, not a warning) is a legitimate convenience feature and a reasonable paid candidate.
- **Community contribution features (Report a Problem, Data Nudges) stay free even though they're Post-MVP** - not because they're safety-critical in the same way closures are, but because of pricing value #3 above: paywalling the supply side of a shared resource undermines the resource itself.

## Personas, mapped to what actually gets built

### Thru-hikers - the clearest, highest-conversion case

**Checked directly: FarOut's own current AT guide is $74.99, marketed as a "Thru-Hiker Special," one-time purchase for lifetime access to the whole 2,190-mile guide.** That's within a dollar of your own $75 anchor - not a coincidence to second-guess, a real signal that this price point is already market-tested for exactly this use case. Thru-hikers already pay almost this exact amount today; the ask isn't "start paying for a map," it's ~~"pay a comparable amount to a mission-funding alternative."~~ **Superseded 2026-08-27** - OurHike funds no organization, so it cannot be pitched as the mission-funding alternative, and a pitch that implies otherwise is the exact claim `client/src/screens/Onboarding.tsx` was corrected to stop making. What is true is narrower and still worth saying: a comparable amount for the planning and community layer, on a map whose safety half is free for everyone and whose maker takes no cut of anything a hiker gives the trail.

**What actually gets unlocked, not just "the app":** the full Trip Planning toolset (bulk multi-day date shifts, POI-aware planning assistance) and Community Building (Tramily, check-ins, mentions), scoped to a specific `Hike` with `type: thru` - the exact record [SEGMENTS.md](SEGMENTS.md) already models. The core map, water, shelters, elevation, and closures a thru-hiker actually needs to be safe are already free per the rule above - the pass is for the planning/community layer built on top, not the safety layer underneath.

**The hardship concern is structurally resolved by the rule above, not by a separate mechanism:** nobody is locked out of the trail's safety data regardless of ability to pay - a thru-hiker who can't afford the pass still gets the full free map. Worth adding an explicit scholarship/waiver request path on top of that structural floor, as a further act of generosity (value #5), not because access is otherwise at risk.

~~**Revenue routing:** a thru-hike pass (the whole AT) funds the ATC directly, not a specific local club - matching your framing exactly, and cleanly modeled once a purchase's `revenue_beneficiary` is just another reference into the same Club/org concept [Multi-club support](../FEATURES.md) already plans.~~ **Superseded 2026-08-27.** There is no revenue to route: a pass would cover OurHike's own costs and nothing else, and `revenue_beneficiary` is not a field anything needs. Note the trap this sentence set for a reader, since it is the reason the whole doc had to be re-read rather than grepped - "directly" here modified *the ATC rather than a local club*, not *hiker gives to the org*. The money still went through OurHike.

### Day-hikers - volume and access, not the revenue story

Everything in the free tier is already enough for a day-hiker - keeping it that way is the point, not a gap to close. Growth here should look like **donation-framed nudges at a genuine positive moment**, not a paywall: e.g., a soft "did this help? consider supporting the trail" prompt right after a hike gets marked complete (reusing [SEGMENTS.md](SEGMENTS.md)'s existing completion tracking), the same "ask in context, not upfront" instinct [ONBOARDING.md](ONBOARDING.md) already applies to permissions. **Deliberately not gamified** - no "unlock a badge by donating," consistent with the anti-gamification guardrail this project has now applied four times elsewhere.

### Volunteers - free ride, offered not assumed

**The 40-hours-a-year threshold is a real, quantifiable rule, not a vague gesture** - but it needs something that doesn't exist yet to actually work. **This is a real, direct dependency worth naming plainly: the volunteer exemption can't ship until Volunteering's attendance/hours tracking does.**

**Unblocked as a design 2026-08-06, though not yet as a build.** [VOLUNTEERING.md](VOLUNTEERING.md) is now v2's second feature and fills in the `VolunteerHoursRecord` sketched at the foot of this doc — `claimed` when the volunteer logs it, `confirmed` when a club admin says so, and attaching to a standalone Tuesday afternoon's work as readily as to an organised workday, since most trail maintenance is the former. **The exemption waits on that doc's Phase D specifically** (in-app signup and club confirmation), which is a named phase rather than the open-ended dependency this paragraph used to carry.

Two things from that doc are worth knowing here. **Hours are claimed, not computed** — GPS would be wrong constantly, and the person knows. And the number has a consumer beyond our own pricing: clubs report volunteer hours to ATC and to land-managing agencies, where they carry weight in real funding decisions. That is the reason confirmation is a club admin's job and not a formality.

**Grant, don't self-report — softened 2026-08-20, deliberately.** As first written:
hours get confirmed by a club admin (the same permission tier
[AUTHENTICATION.md](AUTHENTICATION.md) already designs for club-admin access), not
self-declared by the volunteer - the same "don't let users unlock value by asserting it
themselves" reasoning [Hiker Safety's severity tier](HIKER_SAFETY.md) already applied to
serious warnings. **The maintainer revised this when the hours record was built
([#761](https://github.com/OurHike/OurHike/issues/761), decision recorded there):
claimed hours count toward the exemption immediately, and a club's action runs the
other way — a *dispute* removes them.** The trust posture inverts from allow-list to
deny-list; what survives unchanged is that the state is always labeled wherever an hour
is shown or exported, so whoever administers the exemption can still see exactly how much
of a total is a volunteer's own word. If gaming appears in practice, this paragraph is
where the original posture is preserved to return to.

**Complementary, with an ask, not a mandate.** A confirmed volunteer defaults to full access at no cost, with a "want to also support the trail directly?" option surfaced with genuine appreciation - never framed as owing anything, per pricing value #4 above.

### Heavy/local users - the real product opportunity, not just a persona

**"Access to multiple trails, not just the AT" is the biggest structural ask in this whole doc**, and it graduates an existing principle into an actual product surface: [Multi-club/inheritance support](../FEATURES.md) has so far been "keep the schema future-proof for a hypothetical next club" - this persona needs that to become a real, built feature (a genuine multi-trail data model, not just an inheritable one), since a regional pass needs more than one trail network in the product. The networks arrived — 4,002 trail features to 21,805, measured either side of [#1019 — *A survey's proposed ring decides which of NYS Parks' and NYNJTC's trails ship, and DEC's ship not at all*](https://github.com/OurHike/OurHike/issues/1019) on 2026-08-25 ([pipeline/README.md](../pipeline/README.md)) — and this clause read "is meaningless without more than one trail network actually existing in the product" until 2026-08-27. What is still missing is the model underneath them, which is the ask that survives: [NEARBY_TRAILS.md](NEARBY_TRAILS.md) keeps the centerline "always the **chosen trail**; one trail at a time", and [HIKE_PLANNING.md](HIKE_PLANNING.md) records that on a Harriman day hike the route builder "has **nothing to ask for**" ([#928 — *A day hike built by touching lines, because a park has no single mile axis to drop stops on*](https://github.com/OurHike/OurHike/issues/928)). Worth having front of mind: this pricing model doesn't just monetize Multi-club support, it's the reason to actually build it.

**A regional pass covers one club/region's full trail network** (the AT section they steward, plus other trails/state-or-federal land they maintain, per your framing) - ~~revenue routes to that specific club, not the ATC, mirroring the thru-hike-pass-funds-ATC distinction above.~~ **Superseded 2026-08-27:** revenue routes nowhere but OurHike's own costs. What a regional pass would still be *about* is unchanged - one club's whole network as the unit a heavy local user actually wants - and that unit is the interesting half. The club is supported by the hiker giving to the club, which needs no pass to happen.

### The all-access ceiling - protecting heavy users from being nickel-and-dimed

**An annual cap (illustratively $100, per your own anchor - not committed here) that includes every regional pass plus Trip Planning plus Community Building everywhere**, so a hiker active across several regions never pays more than one flat ceiling regardless of how many individual regional passes that would otherwise add up to. A standard, well-understood SaaS pattern (buy the parts, or cap out at the whole) - not a new mechanic to invent.

## How purchasing actually works, given the existing web-only constraint

**FEATURES.md already commits to no purchases inside the mobile app shell - this doesn't change that, it's the mechanism for how it works within that constraint.** A hiker in the wrapped app who wants a pass gets linked out to a web checkout (Stripe or similar, already a Phase 4 stub in ROADMAP.md) - completes payment there, and the resulting entitlement is stored server-side on their `User` record. Because the web and app versions share one codebase and one account (per TECHNICAL_ARCHITECTURE.md), the unlocked status is simply *true* the next time either client checks it - no separate sync mechanism needed, no purchase logic inside the wrapped app at all.

## Data model sketch

```
Entitlement                        (extends AUTHENTICATION.md's User)
  user_id
  tier: free | thru_hike_pass | regional_pass | all_access | volunteer_complementary
  scope: trail/club id              (which trail/region this covers - null for thru_hike_pass,
                                     which is whole-AT by definition; a specific club id for
                                     regional_pass; irrelevant for all_access)
  granted_by: purchase | club-admin-grant (the volunteer path)
  valid_from, valid_until           (thru_hike_pass scoped to a Hike's duration;
                                     regional_pass/all_access annual)
  revenue_beneficiary: REMOVED 2026-08-27. Read "club/org id (ATC for
                       thru_hike_pass; the specific regional club otherwise)"
                       until then. No revenue routes anywhere but OurHike's
                       own costs, so a pass has no beneficiary to name. See
                       the superseding banner at the top of this file.

VolunteerHoursRecord               (new - the volunteer exemption's real dependency;
                                     needs VOLUNTEERING.md's v2 attendance/hours
                                     tracking to exist first, not designed here)
  user_id, club_id, hours, period (year), confirmed_by (club admin)
```

## What's deliberately not decided here, per your own framing

- **Exact dollar amounts** - $75 and $100 above are your own anchors, strongly validated by FarOut's real $74.99 price point, but this doc's job was structure, not a final price list.
- **Launch timing** - you were explicit this might happen right away or much later; nothing here assumes a date.
- **Whether the all-access ceiling auto-applies once spending crosses it within a year, or requires an explicit "upgrade me" action** - a real product decision once there's a real billing system in front of you.

## Open questions (for you, not decided here)

- **The scholarship/waiver request mechanism for the thru-hike pass** - flagged above as worth adding on top of the structural free-safety-data floor, but the actual request/verification flow isn't designed here.
- **Whether a free trial period makes sense for a regional pass** before a heavy user commits - a real conversion-tuning question once there's usage data to look at, not answerable from this doc.
- **Whether Hiker Safety's "daily conditions" (as opposed to alerts) is really worth gating**, given it needs the same NWS backend plumbing either way - a real cost/benefit call, not decided here.
- ~~**How all-access-ceiling revenue actually splits across multiple clubs a heavy user's usage touched** - flagged, not designed; the thru-hike-pass-to-ATC and regional-pass-to-one-club cases are clean, but an all-access hiker using five regions' trails in one year doesn't have an obvious single beneficiary.~~ **Closed 2026-08-27 - the question dissolves.** No pass revenue reaches any club, so there is no split to design and no beneficiary to pick. Both cases this called "clean" are struck above. See the superseding banner.
