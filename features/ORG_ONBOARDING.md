# OurHike — Organization onboarding (Feature Design v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md) and
[OurHikeValues.md](../OurHikeValues.md). Builds on [VOLUNTEERING.md](VOLUNTEERING.md) (this is its
phase E, the club-admin module, with the four screens either side of it that phase always implied),
[SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) (an organization registering where its data lives, and the
rule that nothing self-service reaches a hiker without a merge), [AUTHENTICATION.md](AUTHENTICATION.md)
(nobody registers an org without an identity, and the provider-linking this needs is the half that doc
names and has never been built), [SAYING_THANKS.md](SAYING_THANKS.md) (whose `publicly_creditable`
question this dissolves rather than answers), [ONBOARDING.md](ONBOARDING.md) (whose money correction of
2026-08-27 governs every word of the pitch copy) and [PRICING_MODEL.md](PRICING_MODEL.md) (whose
40-hour fee exemption depends on a confirmed hours figure this produces).

**Provenance.** The design is the maintainer's, handed over 2026-09-17 as a 23-screen HTML prototype
with its own build spec. This document is that spec rewritten as a repository feature doc, because a
zip in one session's scratch directory is not a home. Where a number below came from the prototype
rather than from a measurement, it says so and carries `@unvalidated`.

---

## The gap this closes, stated plainly

**Every trail on the map today arrived because a maintainer went looking.** SOURCE_REGISTRY.md already
made this point about data: the 33 registered sources across nine organizations
(`pipeline/sources.json`, counted 2026-08-27) each got there by somebody reading terms by hand, which
is knowing someone rather than a way in.

This document is the way in, and it is wider than data. An organization that registers gets its
sections drawn from its own geometry, its blaze colours, its workdays in front of hikers who are
standing on its trail, its membership and donation links on every section it maintains — and, on the
other side of the same console, the roles, roster, coverage report and hours its volunteers have been
tracked in spreadsheets for. None of it asks the org to change how it already works.

**The asymmetry worth sitting with is VOLUNTEERING.md's, one level up.** That doc's observation was
that a maintaining club's hardest problem is finding people. The club-side observation is the same
shape: a club's second-hardest problem is that the people it has are tracked in a spreadsheet only one
person understands, and when that person steps back the coverage map goes with them.

---

## Read these five first — every screen assumes them

1. **Nothing is overwritten — every change is dated.**
   A report filed three weeks ago must still route to whoever covered that mile then. Assignments,
   roles and registry rows are append-only with effective dates; "current" is a query, not a column.
   This is not new: `MaintainerAssignment` has shipped that way since 2026-07-29 and
   `backend/app/models/maintainer_assignment.py` carries the argument. What is new is that every other
   table this design adds obeys it too.

2. **Nothing publishes without codeowner approval.**
   Registry changes need all three admins; smaller edits need one. This includes the nightly GIS
   re-read — our own automation proposes, it does not publish. Implemented as real pull requests
   against the public repository, which is DATA_RELEASES.md's fourth lane and
   SOURCE_REGISTRY.md's "the bridge is a bot-opened pull request", not a new mechanism.

3. **A signup is an introduction, not an enrolment.**
   VOLUNTEERING.md is explicit: states are `interested | confirmed | waitlisted | declined`, and the
   app must never leave somebody believing they are on a roster when they are not. Real workdays carry
   waivers, minimum ages and tool training. `confirmed` is set by the org, never by the app.

4. **Nothing about a named volunteer is ever published.**
   Thanks attach to a place and a category, never to a person. Attribution is inferred privately —
   whoever covers that section sees it, and so do their supervisors. Nobody outside the org learns who
   maintains which mile.

5. **No money passes through OurHike.**
   ONBOARDING.md records the maintainer's correction of 2026-08-27 — *"There is no funding model today
   for the orgs. The hope is we will drive membership and donations to those orgs"* — and a test
   guards the value-prop copy against the sentence coming back. We link the org's own membership and
   donation pages and take no cut, because there is no cut to take.

---

## Decisions, with the reasoning kept

Settled with the maintainer. Recorded here because the reasoning is the part that stops them being
reopened from scratch.

**Thanks never name a person.** A hiker thanks a place and a category. The volunteer assigned to that
section sees it, and so do their supervisors. *Why: this dissolves SAYING_THANKS.md's
`publicly_creditable` problem rather than solving it — there is no consent flag to design because
nothing about a named person is published. The column stays, defaulted off, with no UI. Let
SAYING_THANKS.md keep the question if public credit is ever wanted.*

**Roster and assignments write over HTTP.** Protected by RLS, with an audit row for every sync run.
*Why: `backend/README.md`'s no-HTTP-writes rule was about **publication**, and the roster is never
published. RLS answers who may write; it was publication that needed the reviewed file. The
reviewed-file path stays where it belongs — the registry, which is public by definition.* See
Conflicts §3.

**A bad sync cannot empty your roster.** A run that would deactivate more than 10% of active
assignments applies its additions and holds its deactivations for an admin. *Why: a changed API field
at 4am must not release three hundred roles and blank the coverage report before anyone wakes up.* The
10% is `@unvalidated` — see Known gaps.

**Supervisors propose, admins confirm.** Admins change any assignment; a supervisor proposes and an
admin confirms. *Why: RLS says who may write, never whether a write was right — and a wrong section
assignment sends a hiker's report to the wrong person.*

**A volunteer can step back themselves.** Any time, without asking. It notifies their supervisor and
frees the section. *Why: the org's feed can already deactivate them; they should have at least that
much say. Separate from deleting their OurHike account, which `DELETE /profiles/me` already does.*

**A new gap is flagged, not escalated.** It appears on the coverage report and the supervisor is told.
Hikers are not told a section is unmaintained. *Why: most gaps fill within a season, and treating each
as an incident trains people to ignore the report.* This is the same reasoning VOLUNTEERING.md used
against a lack-state, applied to the org's side of the screen.

**Orgs are identified by a readable slug** — `/org/ramapo-trail-conference`, chosen at registration.
*Why: it appears in every route, every embed's `data-org`, and the pull-request paths. Cheap today,
expensive in week three.*

**One release, not three.** *Why: the maintainer's call, and defensible — a registry with no
volunteers behind it is a map nobody maintains, which is the thing OurHike is trying not to be.*

**Three approvals for the registry, one admin elsewhere.** *Why: three-for-everything makes small
corrections cost more than they are worth, and the corrections stop happening.*

**Your Tread is reachable five ways** — from the hiker app once assigned, from the welcome email,
embedded in the org's members area, from its own bookmarkable URL, and from a banner when something is
waiting. *Why: it is the most important screen in the product and was previously reachable only from
an admin console.* Three of the five are a URL, which is why this design cannot avoid
[#970](https://github.com/OurHike/OurHike/issues/970).

**GitHub is offered twice** — at registration alongside Google, and again at the pull-request moment.
*Why: asked in context it converts; asked only in settings, the contribution gets attributed to
nobody.*

**A workday is not a map feature, so it may be edited self-service.** SOURCE_REGISTRY.md's rule that
nothing self-service changes a hiker's map without a merge is **deliberately relaxed for work
projects, and only for work projects.** *Why: a workday carries no geometry a hiker navigates by, and
a wrong one costs somebody a Saturday rather than a wrong turn. That is a different risk class from a
trail line.* This answers the open question
[#763](https://github.com/OurHike/OurHike/issues/763) left rather than discovering it during the
build; argue with it here.

**Shared-revenue copy ships as written, marked clearly as not live.** *Still wants a legal read* — see
Known gaps.

---

## The handoff this was built from

[`org-onboarding-handoff/`](org-onboarding-handoff/) holds the design as it was given:
`SPEC.md`'s argument, the handoff README's map of the 23 screens, and 27 per-screen extracts
of the prototype's own rendered text. It is source material and is never edited to match what
shipped — a handoff corrected after the fact stops being evidence. **This file stays the
design's one home**; that folder is the record of where it started, and its own README says
what it does and does not carry.

## Where this lives

None of this replaces the hiker-facing homepage. The consumer front door stays as it is and gains two
links, one of which `NavBar.astro` already reserved.

| Route | Who | What |
| --- | --- | --- |
| `/` | Hikers | **Unchanged.** Gains one nav link, one card and one footer column. |
| `/for-orgs/` | Anyone | Pitch and registration form. WEBSITE.md §5.7 already names this page. |
| `/for-orgs/demo/` | Anyone | Central Park Throughikers — a whole published org to walk through. |
| `/for-orgs/nominate/` | Signed-in hiker | Submit an org's trails on its behalf. |
| `/for-orgs/claim/` | Signed-in hiker | Claim an org listed with no admins. |
| `/org/:slug/setup` | Org admins | Onboarding hub, then permanent org home. |
| `/org/:slug/volunteers` | Admins + supervisors | Roles, workdays, coverage, roster, welcome. |
| `/my/tread` | Volunteers | Your Tread. Reachable from the hiker app, not only the console. |
| their site + `embed.js` | Their visitors | Four embeds. Three public, one token-gated. |

`NavBar.astro`'s reservation is the standard the first link has to meet:

> Explore the trail (Phase 4), For clubs and Get involved (Phase 6) join this row when they are real —
> and not a day before: a nav link to a page that is not there is a promise the site breaks on its
> second click.

The page is now real. **Get involved is still not**, and the nav link for it stays out.

---

## Conflicts with the existing codebase

Checked against the repository rather than assumed.

### 1. GitHub as a fourth SSO provider — decided, and the codebase is ready

`features/AUTHENTICATION.md`, `client/src/lib/auth.ts`.

AUTHENTICATION.md already calls for this: *"A user can have more than one of these linked to the same
account… worth designing for from the start rather than retrofitting."* Supabase supports GitHub OAuth
natively, so this is a Cloud-side registration plus a `VITE_AUTH_PROVIDERS` entry, not new auth code.

**The linking flow has three rules, and each one is a hole it would otherwise leave:**

- **Link only while already signed in.** Never auto-link on a matching email — GitHub addresses are
  often private `noreply` aliases, and matching on an unverified address is an account-takeover path.
- **A GitHub identity is optional and additive.** A trails chair who will not make a developer account
  still registers, approves and publishes. They are simply not the commit author.
- **Unlinking must not orphan the account**, so it is refused when GitHub is the only linked identity.

**Opening a pull request and approving one need different access, and running the two together is
what made one objection look like it settled both.** Opening needs write access to this repository,
so it cannot be a person's — which is why `core/registry_pr.py` holds a service identity's token.
Approving needs no write access at all: on a public repository any account may submit a review. So
an organization's codeowners approve with **their own** accounts, which is the moment that matters,
and none of them becomes a committer here. **The registry pull request, and who signs it** below is
the whole of it.

**Note against [#397](https://github.com/OurHike/OurHike/issues/397), which is closed.** That issue
shipped Google *alone* in v1, deliberately, so that the sign-in screen offered nothing that could not
finish. GitHub here is a **fourth provider for org admins**, not a reopening of that decision: it is
offered on the org registration path, where the person registering is by definition not a hiker on a
ridge with one bar, and it costs no SMTP and no Apple membership.

### 2. Endpoint paths — no `/v1` prefix

`backend/app/routers/*.py` serve unversioned paths: `/reports`, `/closures`, `/profiles/me`, `/hikes`,
`/maintainer-assignments`. The entity is `clubs` in the database; **Org is a UI rename only**, so the
route stays `/clubs`. Renaming the table would be a migration across every existing foreign key to buy
a word.

### 3. The no-HTTP-writes rule on `clubs` and `maintainer_assignments` — resolved

`backend/README.md`'s "Loading maintainer assignments" forbids HTTP writes to these two tables:

> an assignment says a named volunteer is at a known place on a predictable schedule, which is the
> fact `features/SAYING_THANKS.md` declines to publish without consent.

Read closely, **that is a rule about publication, not about access**, and the two come apart. RLS
answers who may write; it was publication that needed the reviewed file — and rule 4 above means
nothing about a named volunteer is published at all.

Decided: roster and assignments write over HTTP with RLS and an audit row. Two guardrails replace the
reviewed file: the 10% deactivation hold, and supervisors proposing while an admin confirms.
`load_assignments.py` stays — it is still the right answer for one org getting started from a file,
and its docstring already says the larger module is where an admin surface belongs.

### 4. Hours-confirmation endpoints already exist — reuse them

`POST /volunteer-hours/{id}/confirm` and `/dispute` were built on
[#761](https://github.com/OurHike/OurHike/issues/761), club-admin-gated, with the audit pair. **Do not
design a second hours model.** What is missing is the screen, which is
[#877](https://github.com/OurHike/OurHike/issues/877)'s half and is built here: the supervisor's
confirmation queue on Workdays, and the phone sheet in the field screens.

The 2026-08-20 decision on #761 rides through unchanged: **a claim counts until disputed, and the
state travels with the hour** wherever it is shown or exported.

### 5. Closures already have a moderation model — reconcile, do not fork

`POST /closures`, `PATCH /closures/:id` and the verify/dismiss pair exist behind a role gate. The
three-volunteer rule becomes **data on the existing closure** (an approvals list), with the existing
supervisor gate as the single-approver path. One lifecycle, two ways to satisfy it.

### 6. Any new table needs RLS in its own migration

`backend/alembic/versions/b3d1c7a94e02_enable_row_level_security.py`, LAUNCH_CHECKLIST.md 349–353.

PostgREST is a second front door into the same Postgres that never passes through FastAPI. Alembic
creates plain tables, so **a new table without a policy is readable and writable by anyone who views
source and copies the anon key**, and it will not fail loudly. Also: never add `force row level
security` — it applies to the owner and would take every endpoint down.

### 7. A role cannot be granted at all

[#1169](https://github.com/OurHike/OurHike/issues/1169) measured it on 2026-08-28: **no router in
`backend/app/routers/` assigns `role`.** `core/auth.py` sets it once to `Role.hiker` when a profile is
auto-provisioned and nothing ever changes it. Every console screen in this design assumes a role that
can be granted, held alongside others, and offered to somebody who has never signed in. That issue is
therefore not adjacent to this work — it is underneath it.

---

## Data model

Names match the repository where the repository already has them.

```
Org                         (repo: clubs — the table keeps its name, conflict 2)
  id · slug · name · domain · website · verified_by (dns|email)
  state (unclaimed|pending|claimed|frozen|deleted)
  membership_url · donation_url · created_by
  assist_opted_in_at · assist_opted_in_by · assist_opted_out_at
  registry_pr_number · registry_pr_url
```

Renamed from Club **in the UI only** — not every org is a club, and the ones that are not are land
trusts and agencies. `state` drives Claim your org: an unclaimed org has live trails and no admins,
which is exactly what a source registered by a maintainer looks like today.

**`pending` and `unclaimed` are opposites and read like neighbours, so this is the paragraph that
separates them.** An unclaimed org is real and untaken — a maintainer wrote its row, hikers are
walking its trails, and it is public for that reason. A pending org is one somebody registered
where the only address at its domain was one **they typed for a colleague**. Nothing about it is
published, it is absent from `GET /clubs`, and `verified_by` stays null, because nobody has
verified anything: an address a registrant types is a claim about a third party, not evidence about
the registrant.

Holding it rather than refusing it is the decision, taken by poll 2026-09-20 over refusing the
registration outright. Refusing is safe and costs a real organization whose chair uses a personal
address — a common enough shape that the original permissive check was written for it. Holding
keeps that chair's registration and simply declines to call it proven.

**One thing releases it: somebody who holds an address at the domain approves an admin seat**
(`routers/clubs.py`'s `approve_seat`). Both halves are load-bearing and neither alone would do. The
provider verified that caller's address, which is what makes it evidence; approving is what makes
it agreement. A sign-in alone would prove only the first, and an organization "confirmed" by a
secretary who opened OurHike to look at a trail has confirmed nothing. The registrant approving
their own seat releases nothing, because theirs is the address that failed the check.

**The real organization is never locked out.** `pending` is not `claimed`, so Claim your org stays
open to anybody holding an address at the domain, and taking it makes them a codeowner of the org
that was sitting in their name. That recourse is why holding is enough.

The three `assist_*` columns are the org's answer to "may a model read our registry" — dated and
attributed rather than a flag, because an organization asking six months later who agreed to this
needs a name and a date, and a boolean has neither. Null means never agreed, which is every row.
See **The assist panels** below.

```
OrgAdmin                    (new: club_admins)
  org_id · person_id · title · is_codeowner
  approved_at · declined_at · decline_reason

Person                      (repo: profiles — existing table, one column added)
  … · github_login
```

`github_login` is stored **where the email deliberately is not**, and the reason is mechanical
rather than a change of mind about addresses: `.github/CODEOWNERS` is generated when nobody is
making a request, so there is no token to read a login off and it has to be on a row to be
readable at all. It is written by `POST /profiles/me/github` from the **verified token and never
the request body** — same rule and reason as the registration domain check, because a caller who
could name the account would be naming whose approval counts on somebody else's organization.

At least one must hold an email at the org domain — and whether that one is the *registrant* or
somebody they named decides `claimed` against `pending`, above. One admin registers; three
approvals publish. **A decline pauses the org and is reversible — never a rejection**, because the
common cause is a secretary who does not know what OurHike is rather than a board that said no.

The other named admins become `RoleInvite` rows rather than seats, because OurHike cannot create a
user (#1169's problem 3). **The seat appears the first time that person opens the organization** —
`core/org_access.py` claims any invite waiting for the address on their token, and
`core/role_invites.py` turns an admin invitation into an un-approved `OrgAdmin` row. Nothing did
that until #1547's review, and the consequence was not a missing convenience: an org registered
through the product had exactly one admin, permanently, so the three-codeowner rule every registry
change needs could not be satisfied by anybody.

```
Park / TrailSystem          (new: org_parks)
  id · org_id · name · kind (park|system|forest)
```

Top level of the three-tier naming. ATC has one trail with many sections; NYNJTC has many systems.
**This tier can be thin without being wrong** — an org with one park has one row.

```
Trail                       (new: org_trails)
  id · park_id · name (nullable) · blaze_value_raw · blaze_mapped · miles
```

**A trail with no name and no blaze is legitimate** — a route on a map is a real thing orgs publish.
`blaze_value_raw` keeps the org's own string exactly as their GIS spells it; `blaze_mapped` is what we
can render, and the mapping is theirs to confirm rather than ours to assume.
See [TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md) for what we can render.

```
Section                     (repo: maintainer sections)
  id · trail_id · name · start_anchor · end_anchor · miles · geometry
```

Anchors reference mile markers or POIs, **never free text** — SEGMENTS.md's rule, and the thing that
lets a report written three weeks ago find the right maintainer years later.

```
Role                        (new: org_roles)
  id · org_id · name · category (Trail Maintenance|Stewards|Environmental)
  reports_to_role_id · section_id (nullable)
  required · required_by · retired_at
```

`required` + `required_by` covers mandates an org inherits — ATC requiring roles of its member clubs is
the real case. **A retired role keeps its holders' history; only an unheld role is deletable.**

```
MaintainerAssignment        (repo: maintainer_assignments — extended, not replaced)
  person_id · role_id · section_id
  effective_from · effective_to · publicly_creditable
```

Several people can hold the same section, and one person can hold many roles. Deactivation releases
roles **so coverage never looks covered when it is not** — which is the failure the coverage report
exists to catch, so it must not be the failure the roster introduces.

```
WorkProject                 (repo: WorkProject, VOLUNTEERING.md)
  id · org_id · title · starts_at · meet_point · cap (nullable)
  source (ourhike|mirrored) · signup_url
```

`source=mirrored` means **the org's own calendar is authoritative** and signup goes to their form.
Both paths coexist, and that is the hard part rather than an afterthought: an org with a working
calendar is not going to abandon it, and an app that pretends otherwise gets a stale mirror.

```
WorkProjectSignup           (new — VOLUNTEERING.md phase D, #762)
  id · work_project_id · person_id
  state: interested | confirmed | waitlisted | declined | cancelled_by_volunteer
  reply_message · attended
```

```
Closure                     (repo: closures — extended, conflict 5)
  + approvals[] · approved_by_supervisor
```

```
HoursEntry                  (repo: volunteer_hours — unchanged, conflict 4)
```

---

## Permissions

Four tiers. **A person can hold several at once, and the UI shows the union of what they allow — never
a role picker.** Somebody who is a trails chair at one org and a maintainer at another is the normal
case, not the edge one.

| Tier | Can | Cannot |
| --- | --- | --- |
| Signed-in hiker | Nominate an org · claim an org on their domain · view any published org | See any roster, hours or unpublished work |
| Volunteer | Your Tread · report issues · request closures · log hours · edit POIs · edit own profile | See others' records · confirm hours · touch the registry |
| Supervisor / chair | All of the above, plus workdays, signup replies, hours confirmation and roster loading for their crews | Registry changes · admin membership · deletion |
| Org admin (codeowner) | Registry, roles, regions, giving links, embeds, keys, leaving. Approves proposals. | Act alone on a registry change — three approvals, always |

**Role is server-derived, never a client claim.** The client renders what the server says the person
holds; a flag in local state is a display detail, never a gate.

---

## Endpoints

Unversioned, per conflict 2. `EXISTS` means exactly that — do not add a second path.

```
GET    /clubs/:id                        Org with admins, giving links, state
POST   /clubs                            Register. One admin creates; three approve to publish
POST   /clubs/:id/claim                  Domain-verified claim. Returns frozen on dispute
POST   /clubs/:id/gis-source             Register a server URL. Refuses flat files
GET    /clubs/:id/registry/diff          Proposed vs live. Backs sign-off and the nightly re-read
GET    /clubs/:id/coverage?region=       Sections with no assigned role, with geometry
POST   /workdays/:id/signups/:sid/reply  confirmed | waitlisted | declined, with a message
POST   /closures                         EXISTS — reuse
PATCH  /closures/:id                     EXISTS — the approval count rides on this
POST   /reports/:id/verify               EXISTS (moderation) — the supervisor gate is here
GET    /maintainer-assignments           EXISTS — read-only today; see conflict 3
GET    /profiles/me/export               EXISTS — the volunteer half of "take your data"
DELETE /profiles/me                      EXISTS — a person leaving is not an org leaving
POST   /console/session                  NEW — secret key + signed-in email → 15-min scoped token
POST   /clubs/:id/assist                 The three console panels. 409 until the org has opted in
POST   /assist/nominate                  The public one. No account, no org, smaller budget
GET    /clubs/:id/assist-consent         Admin only — where consent stands, who set it, when
PUT    /clubs/:id/assist-consent         Admin only — `{opted_in}`. The whole of the switch
```

### Console embed auth

The org's server posts the signed-in person's email with the secret key; we return a 15-minute token
scoped to **one person, one org, one origin**. They send only the email — we resolve roles from the
roster, so their system never mirrors our permissions and never drifts from them.

**Somebody not on the roster gets a no-permission token rather than an error**, so the page still
renders rather than showing an org's own members a stack trace.

Six guards, designed for the day somebody hardcodes a key into a public page:

1. The public key alone opens nothing.
2. Origins are allow-listed.
3. Tokens expire in 15 minutes.
4. Two keys live at once, for zero-downtime rotation.
5. Every token request is logged with its origin.
6. **A new key is read-only until write is deliberately granted.**

---

## The screens

Twenty-three, across five surfaces. **Nine components, not twenty-three copies** — the eight shared
widgets below carry every repeated surface, and the demo org mounts the real ones on purpose. *The
moment the demo gets its own copies it starts lying about the product*, which is the one structural
note worth carrying into the codebase.

### Public — no account needed

| Screen | Purpose |
| --- | --- |
| Homepage links | Two additions to the existing consumer homepage. A spec for editing `NavBar.astro`, `index.astro` and `Footer.astro`, not a page. |
| For orgs | Why an org joins, what registering involves, and the form. |
| Demo org | Central Park Throughikers — a whole published org to walk through. |
| Nominate an org | Any signed-in hiker submits an org's trails on its behalf. |
| Claim your org | An org already listed with no admins. An email at the org domain is the whole check. |

### Admin console — `/org/:slug/setup`

| Screen | Purpose |
| --- | --- |
| Admin approval | Per-admin status, reminders, audit trail. Includes the declined state. |
| Setup hub → Org home | **One screen with two lives:** stage checklist while onboarding, then permanent management home. |
| Hike registry | We read their GIS — files or a server URL — and ask only about what cannot be resolved. |
| Registry sign-off | Three-tier table with blaze mapping, and the pull-request window where approvals are recorded. |
| Add a trail | Scoped registry run for one new trail. The diff shows additions only. |
| The three emails | Every email we send in the org's name, in full. |
| Settings and leaving | Export everything, remove an admin, unpublish a trail, delete the org. |

### Manage volunteers — `/org/:slug/volunteers`

| Screen | Purpose |
| --- | --- |
| Roles | Definitions with category and reporting line, hierarchy visual, per-trail mandates, bulk assignment. |
| Workdays | Post a workday, answer signups, confirm hours. Handles orgs who keep their own calendar. |
| Coverage report | Sections with no assigned role, by region, on a map. |
| Your roster | One table plus three load paths: add one, upload any file, or an IT-configured live endpoint. |
| Volunteer profile | One person's record. Editable by an admin **and by that volunteer**. |
| Welcome volunteers | Sends one welcome email each, carrying their own section and supervisor. |

### Volunteer — `/my/tread`

| Screen | Purpose |
| --- | --- |
| Your Tread | The volunteer's own miles. **The most important screen in the product.** |
| On your phone | Four phone designs — Your Tread offline, report, confirm hours, POI upkeep. Not narrowed desktop. |
| What you hand back | The hiker's half — contributing without joining anything. |
| Ridge Runner At-Large | A self-closing commitment window, up to seven days. |

**The name is qualified wherever a third party can see it.** VOLUNTEERING.md §3 and
[#763](https://github.com/OurHike/OurHike/issues/763): "Ridge Runner" is ATC's own programme name, and
a hiker who believes they are talking to an ATC Ridgerunner may take instructions from a volunteer
with no authority to give them. So **"Ridge Runner At-Large" is the in-app name for the person who
opted into it, and anything org-facing or public reads "volunteer trail monitor."** The
`blocked-external` label on #763 is attached to the unqualified name reaching a third party and stays
on.

### Embeds — served onto the org's own domain

Four widgets, reached from Org home's "Put this on your own website". Three are public and
paste-only; the fourth is the private management console behind a server-signed 15-minute token.

### The eight shared components

Registry Table · Hike Finder · Workdays Widget · Coverage Badge · Console Tiles · Tread Card · Page
Header · Phone Frame.

---

## Interaction rules that are not per-screen

- **Navigation.** Left sidebar for org work, top bar public-facing. The sidebar shows only sections
  the current role permits, with counts on items awaiting action.
- **Everything is a proposal.** Editing anything published opens draft → diff → pull request →
  codeowner approvals → merge. The same loop for onboarding and for a correction two years later.
- **Error and empty states are inline, not a gallery.** GIS that will not parse, an admin who
  declines, a contested claim frozen for a human, a failed map build. Org home, roles, roster and
  coverage each explain themselves at zero.
- **The registration form gates on identity**, because registering names you as the org's first admin.
- **At least one admin must hold an email at the org's domain**, and the check re-evaluates live as
  the active account changes.
- **Flat files are refused as GIS sources on purpose.** A PDF or a spreadsheet cannot be re-read, and
  a source that cannot be re-read cannot have a nightly diff.
- **Motion is design-system motion only:** 120–200ms ease-standard fades and colour transitions,
  buttons to 97% on press. No bounce, no spring.
- **Responsive.** Desktop screens reflow at `minmax(0,1fr)` and wrap. The phone screens are a separate
  design at 390px with 44–56px hit targets — **not** the desktop ones made narrow.

---

## The assist panels

Four of them, drawn by the wireframes: the registry assistant, add-a-trail, "read the gaps" on the
coverage report, and the public one on the nominate form. Sonnet, and **the model is a setting rather
than a request parameter** — a caller who can name the model can name the expensive one and bill
somebody who did not choose it. The system prompt is looked up by panel for the same reason.
They suggest and never decide: nothing a panel returns writes a section, creates a role or registers
a source, because a registry is what reaches a hiker's phone and a model's reading of a GIS layer is
a suggestion to check.

### The organization decides, not us

**An organization's data does not leave without that organization's consent, and the gate is in
`app/core/assist.py` rather than at the route.** `ask` takes the `Club` row and not its id, so there
is no argument shaped like "an org, but skip the check": a route added next year has to hand over
the row that carries the answer. The panel saying on screen what goes over is true and is not
consent.

- **Off for every organization until an admin turns it on**, in Settings, where the sentence naming
  what leaves can be read. `assist_opted_in_at` null is the state of every row.
- **Nothing is asked before the organization exists.** Registration collects no consent — there is
  nobody at an organization that does not exist yet to give it, and a checkbox on a sign-up form is
  the weakest place to collect a decision about somebody else's data. A field smuggled into the
  registration body is ignored rather than honoured.
- **The refusal is 409**, not 403. A 403 is already what an authorization failure answers here, and
  a screen cannot tell two 403s apart — telling a supervisor their organization has not agreed, when
  what happened is that they are not an admin, would be a screen reporting somebody else's decision.
- **Turning it off does not erase that it was on.** `assist_opted_in_at` stays and
  `assist_opted_out_at` is written beside it, so "was our data ever sent, and between which dates"
  has an answer. `assist_usage` carries the other half — tokens, a day and a panel, never a prompt.
- **A tie reads as off.** Two timestamps equal to the microsecond is a row somebody edited or a clock
  that went backwards, and of the two ways to be wrong, sending a registry to a third party that
  never agreed is the one that cannot be taken back.
- **The public nominate panel is outside all of this**, deliberately. It runs before any org record
  exists, sends a website address a hiker typed into a public form, and carries nothing of any
  organization's. Asking a hiker to agree on an organization's behalf would be a consent worth less
  than none.
- **Deleting the admin's account does not withdraw it.** The agreement was the organization's; the
  name beside the date goes with the person, the date stays, the panels keep working.

Budgeted per organization per rolling day, counted from the usage the API itself reports rather than
an estimate, and checked before the call rather than after. The public panel is two orders of
magnitude smaller and counted per address.

---

## Nominating an organization

A hiker who is not affiliated with a club offers its trails on its behalf. The design's own
eyebrow on that screen reads **ANY SIGNED-IN HIKER CAN DO THIS**, and until 2026-09-17 the
built version was neither signed-in nor doing it.

**What it was.** `POST /assist/nominate` took a website from anybody on the internet, sent the
URL to a model with no tools, and `/for-orgs/nominate/` rendered the reply under the heading
**WHAT WE COULD SEE ON THEIR SITE**. Nothing had ever been opened — the answer came out of the
model's training memory. `POST /clubs/nominations` then created an `unclaimed` club row from a
name and a website, discarded the `data_url` and `note` it had just validated, and told nobody
at the organization anything at all.

The maintainer took four decisions on 2026-09-17 and all four are built.

### 1. We really read their site, and only a signed-in hiker can make us

A server fetching an address a stranger typed is server-side request forgery in its plainest
form, so the guard is a module of its own —
[`backend/app/core/urlguard.py`](../backend/app/core/urlguard.py) — with
[`sitefetch.py`](../backend/app/core/sitefetch.py) on top of it. The decisions worth
disagreeing with on the merits:

- **`is_global`, not `is_private`.** Measured on both Pythons this repository runs, 3.11.15 and
  3.13.12: `ipaddress.ip_address("100.64.0.1").is_private` is **False**. That is RFC 6598
  carrier-grade NAT — a hundred million real devices, none publicly routable. An explicit table
  of fifteen v4 and eleven v6 networks sits underneath so a change in the standard library's
  classification fails a test rather than widening what we open. `169.254.169.254` is in it by
  name as well as by range, because a range is a thing a later edit loosens.
- **Every resolved address must pass, not the first.** A name answering with one public address
  and one private one is DNS rebinding's ordinary shape. A mixed answer refuses the host.
- **And the connection is checked once it is open.** Between the guard's decision and the
  socket, DNS can answer differently, and whoever runs it picks the moment. So the fetcher asks
  the connection what it actually reached and refuses before reading a byte of the body. An
  unknown peer is a refusal rather than a pass — which is why an egress proxy is a deployment
  that must turn the reading off deliberately rather than run it unverified.

Six pages of one organization's own site, a megabyte each, ten seconds each, robots.txt
honoured per RFC 9309 (4xx opens the site, 5xx closes it). No cookie and no Authorization
header ever leaves.

### 2. The contacts are proposed, and the hiker abandons the ones that are wrong

The design's contacts step lists named people with the addresses their organization publishes
— "Dale Whitford · Volunteer coordinator · volunteers@… · Listed on the Get Involved page". The
maintainer allowed it **on the condition that the hiker reviews and can drop each one**, and
that condition is implemented literally rather than as a display convention:

**`POST /assist/nominate` stores nothing.** It returns proposed sources and proposed people to
the browser; only what comes back on `POST /clubs/nominations` becomes a row. A person whose
address the reading found and the hiker dropped was never written down — there is no row to
leak, to export, or to delete later on their behalf. That is why
[`schemas/nomination.py`](../backend/app/schemas/nomination.py) has two schemas where one would
have been shorter.

**And nothing reaches the hiker that was not on a page we opened.**
[`core/nominate.py`](../backend/app/core/nominate.py) checks every address and every URL in the
model's answer back against the literal text of the fetched pages and drops anything absent. A
model asked who to contact at a club produces plausible addresses whether or not the page had
any — `president@carolinamountainclub.org` is exactly the shape of the thing that gets invented
— and a hiker reading a screen headed "what we could see on their site" cannot tell an
invention from a reading. Then we would email it. The citation is checked too: a contact whose
`source_page` names a page we never opened has it corrected to the page the address was
actually on, or is dropped.

### 3. A proof of work, because sign-in bounds who and not how fast

[`core/challenge.py`](../backend/app/core/challenge.py) and
[`client/src/lib/proofOfWork.ts`](../client/src/lib/proofOfWork.ts). A CAPTCHA would put a third
party in front of every hiker who nominates a club, on a page whose whole subject is somebody
else's public data; this is arithmetic in the hiker's own browser and needs no vendor.

MEASURED 2026-09-17, medians of fifteen solves on a CI-class container:

| difficulty | median | p90 |
| --- | --- | --- |
| 16 bits | 124 ms | 421 ms |
| 18 bits | **382 ms** | 2,680 ms |
| 20 bits | 3,675 ms | 6,398 ms |

18 by default. Two measurements changed the code rather than confirming it: `await
crypto.subtle.digest` once per candidate costs ~44 µs, nearly all of it the await, which puts
16 bits at a 2.9 second median; and calling `sha256Hex` per candidate cost 3.1 s at 18 bits,
because `digest()` allocates two folds and a hex string every time. `reset()` and `finishInto()`
were added to `sha256.ts` rather than a second SHA-256 being written. **@unvalidated on a
phone** — every figure above came off a desktop CPU, and what would settle it is this solver on
hardware somebody owns.

The server stores no challenge it issues; the HMAC covers nonce, subject, difficulty and expiry,
and the subject is inside it so a solved challenge cannot be handed to somebody else. A wrong
answer does not burn the nonce.

### 4. We write to the people the club publishes, properly

Nothing in this repository sent mail before 2026-09-17.
[`core/mail.py`](../backend/app/core/mail.py) carries four promises, each a promise rather than
a preference: **off unless switched on** (with an allow-list so UA can exercise the flow without
reaching a real club), **the suppression list is checked on the send path and never by callers**,
**a bounce or complaint writes a suppression**, and **every message carries `List-Unsubscribe`
and `List-Unsubscribe-Post`** (RFC 8058) so a mail client can offer one click.

The message itself is in [`core/nomination_mail.py`](../backend/app/core/nomination_mail.py).
Plain text only — an HTML message about somebody's data from a sender they do not know is the
shape of every phishing attempt they have been trained to distrust. It names the organization,
says nothing has been published, carries the link that stops it forever, and **does not name the
hiker**: the design's rule runs both ways, so the club is not handed a way to contact whoever
proposed them and the hiker is never told who declined.

Sent once, read from the send log rather than from `nomination.state` — a run that sent two of
three and then failed leaves those two written to and the nomination still `proposed`. And the
nomination moves to `emailed` only if something actually went, because a row reading `emailed`
with nothing sent is the row a maintainer would trust to decide it needs no follow-up.

**The DNS half is the maintainer's and is not code.** SPF, DKIM and a DMARC policy on the
sending domain are what stop this being filed as junk, and sending before they exist is how a
domain earns a reputation it cannot spend. `mail_enabled` is off by default for that reason as
much as for the preview one.

### Where the flow lives, and why it is split across two hosts

The reading needs an account and the marketing site has none — `site/` is four static Astro
pages with no Supabase client at all. So `/for-orgs/nominate/` is the **door**: it explains,
takes the address, and hands it to the app at `/app/nominate?website=…`, where there is an
account to check and a browser that can do the arithmetic. The club's own answer is at
`/app/n/:token`, unauthenticated by design — nobody at a nominated club has an account and
asking them to make one in order to answer "is this yours?" would be a sign-up wall in front of
a question we asked them.

One refusal ends it; three approvals are needed to proceed. The asymmetry is deliberate and is
the same one the rest of this project applies to anything that reaches a hiker: a club that does
not want this has said so once and should not have to say it three times, while publishing their
data is a thing we make hard. `never_ask_again` is not a stronger word for declining — it writes
a `nomination_refusals` row keyed by the club's own domain, and the next hiker to try is stopped
before anybody there is written to a second time.

---

## The coverage badge, and the one it replaced

The design's embed 3: **miles maintained · active volunteers · hours this season**, one snippet
in two shapes — a strip for a footer, a card for a donate page. Its own caption says where each
figure comes from: *"miles from the registry, volunteers from the roster, hours from the ones a
supervisor signed off."*

**The badge that shipped before this could never have worked.** It drew the gap count by reading
`GET /clubs/{slug}/coverage`, which depends on `org_access` and therefore on `get_current_user` —
so an anonymous visitor got a **401** and the badge rendered nothing. On every real site, always.
It only ever appeared to work on `/for-orgs/demo/`, where a fixture answers it with no auth.

The coverage report is right to be gated. A public list of which miles nobody is looking after is
a list of miles to avoid, and a hiker reading it makes a routing decision out of an
organization's staffing problem. **Pointing a public embed at it was the mistake**, not the gate.

`GET /clubs/{slug}/scoreboard` is the public shape: no `org_access`, three numbers, and
`ScoreboardOut` has no array in it. That last part is the enforcement rather than a convention —
the old badge read `coverage.gaps.length` and discarded the section names beside it, which put a
safety property in a browser where the next edit could drop it. There is nothing to discard now.

Three decisions in it worth disagreeing with on the merits:

- **"Miles maintained" is the registry's own total, not the covered part of it.** An organization
  saying "we maintain 13.8 miles" means the trail it looks after, not the subset with somebody's
  name against it today — and the second number would *fall when a volunteer stepped back*, which
  would put an organization's staffing on its own donate page. Checked against the design's badge,
  which prints 13.8 for the demo organization: 6.1 + 1.58 + 2.4 + 1.2 + 1.7 + 0.8 = **13.78**.
- **A section with no length contributes nothing and is not a zero.** `SUM` skips nulls, which is
  the wanted behaviour: absent means nobody has measured it, the same rule the shelter-capacity
  export follows.
- **"This season" is the calendar year so far, and that is picked rather than derived.**
  `@unvalidated` — a club in Georgia works through the winter and one in Maine does not, so the
  honest answer differs by organization and nobody has been asked. January is the boundary every
  club's own annual report already uses, and `season_started` goes out beside the number so the
  window is stated rather than implied. **What would settle it:** asking the first organizations
  what they call a season, and a column on `clubs` if the answers differ.

**Two deviations from the mock-up, both because the mock-up says something the mechanism does
not do.** Its card is headed *"Our park, live"* — an organization's own words about its own page,
which we cannot know, so `data-title` is how they say it and their registered name is the
fallback. And its foot reads *"Updated nightly from our own registry"*; these figures are counted
when the badge loads, so the foot says that. A line claiming a freshness nothing delivers is the
same defect as a heading claiming a reading nobody did.

---

## The registry pull request, and who signs it

The maintainer's decision of 2026-09-21, taken from a drawing of both wirings: **org admins get
GitHub accounts and approve the registry pull request directly.** Building it resolved a
contradiction this design had been carrying, and the resolution is the part worth keeping.

**Opening and approving are different questions.** Opening a pull request needs write access to
this repository, so it cannot be an admin's credentials — giving one the power to cause a push
would make every org admin a committer to a public repository, which is the objection §1 was
written against and it still stands. Approving needs no write access at all: on a public
repository any account may submit a review. So a service identity opens, the organization's own
codeowners approve, and neither half gives anybody access the other half was protecting against.

### What carries it

| Piece | What it does |
| --- | --- |
| `Profile.github_login`, `POST /profiles/me/github` | The linked account, read off the verified token and never the request body. |
| `pipeline/reference/orgs/<slug>/` | The registry as files, because CODEOWNERS maps paths to people and the registry had no path here at all. |
| `core/registry_file.py` | Renders an org's tiers as that directory's contents — sorted at every tier, no ids, no timestamps, no geometry. |
| `core/codeowners.py` | One line per claimed org, naming its directory and its approved codeowners' linked accounts, inside a generated fence. |
| `core/registry_pr.py` | Opens the pull request from the service identity, one commit through the git data API rather than one per file. |
| `clubs.registry_pr_number`, `clubs.registry_pr_url` | Where it went, so the console can stop describing a pull request nothing opened. |

`reference/`'s stated exception in [CONTRIBUTING.md](../CONTRIBUTING.md) is "a join that encodes
judgement somebody reviews row by row", which is what a sign-off **is** rather than a description
stretched to fit.

### Three decisions worth disagreeing with on the merits

**A directory per organization, a file per park, and the split is measured.** A section serializes
to 9 lines, so one file per organization would hold about 1,330 of them before
`MAX_REFERENCE_LINES` (12,000). Ample for a club on a stretch of the A.T. and **not** ample for one
maintaining a whole trail system — which is the organization whose registry matters most, so a
format that fails exactly there is the wrong format. A test pins the 9 lines, because a field added
later shrinks the headroom silently until a real organization's pull request is refused by a guard.

**The reviewed file is the manifest, not the map.** No row ids, no timestamps, no geometry. A
linestring per section would bury the names, mileages and blaze words a person is actually
approving under megabytes nobody reads — defeating the review the file exists for — and it is
derived data, whose home is `pipeline/data/` and not a commit. The shapes keep coming from the
organization's own GIS, which is authoritative for them anyway.

**Containment is the guard with teeth, because it is the one this process can actually make.**
Scoping the token GitHub-side is a console setting no code here can assert. What code can assert,
before anything is written, is that no path leaves the organization's own directory — a write
outside it is a change to this repository that no organization's codeowners review. It **refuses
rather than filters**: a writer producing a bad path has gone wrong, and dropping those paths would
commit the rest as though nothing had happened.

### The branch-protection gate is off, and that was a decision too

`.github/CODEOWNERS`'s catch-all `* @jaimito-asuntos-gringuenos` matches every file. With "Require
review from Code Owners" enabled it would require the maintainer's approval on **every** pull
request, and GitHub has no toggle letting an author approve their own —
`expected-protections.yml` already records that platform rule. Nothing in this repository would be
mergeable again, including the pull request making the change.

Verified against GitHub's documentation rather than assumed: **code-owner review is its own
requirement, independent of the approval count**, so `required_approving_review_count: 0` is not
what stands in the way. The catch-all is.

So the gate stays off and the codeowner lines still do real work: last-match-wins means a pull
request touching an organization's registry requests review from *that* organization rather than
only the maintainer, which is how its people find it at all. Their approval **requests rather than
requires**, and a maintainer still merges having seen it. `registry_signoffs` therefore stays —
with nothing enforcing the three, deleting the backend's count would leave no in-product record of
approval at all. The recipe for turning the gate on later is written into `.github/CODEOWNERS`
rather than left to be rediscovered.

## Known gaps

What this design does not answer, stated plainly.

- **The registry pull request is built and inert, because all three things it needs are settings
  outside this repository.** The code is above, under **The registry pull request, and who signs
  it**; what it waits on is the GitHub OAuth provider enabled on Supabase, a service identity's
  token with write scoped to `pipeline/reference/orgs/`, and `registry_pr_enabled`. Until all
  three land, every sign-off takes the "could not be opened" branch — correctly, and saying so on
  the screen rather than pretending. Tracked as
  [#1623](https://github.com/OurHike/OurHike/issues/1623). **A nomination is the half that is
  still genuinely unbuilt:** three approvals reach `accepted` and stop there, and nothing opens a
  pull request against `pipeline/sources.json` — the registry opener writes an organization's own
  directory, which is a different path and a different act.
- **Which claim carries a GitHub login is `@unvalidated`.** `core/auth.py` reads both
  `user_metadata.user_name`, the documented place, and `preferred_username`, the OIDC spelling,
  because nobody here has seen a real GitHub token from this project. **What would settle it:** one
  sign-in with the claims printed — after which the losing branch should be deleted rather than
  left as a guess that looks like breadth.
- **Nobody has run the proof of work on a phone.** Every timing in the section above came off a
  desktop CPU. A mid-range phone is commonly two to four times slower at single-thread
  JavaScript, which would put the p90 between two and five seconds — tolerable next to a fetch
  that takes seconds anyway, and unmeasured. **What would settle it:** the solver in a page, on
  hardware somebody owns, at 16, 18 and 20 bits.
- **A deployment behind an egress proxy cannot run the reading at all, and that is the intended
  behaviour rather than a limitation to work around.** Through a proxy the socket's peer is the
  proxy and the hostname is resolved by something we are not asking, so the DNS-rebinding window
  the peer check closes is wide open and invisible. `site_fetch_require_peer_match` exists to be
  turned off deliberately by somebody who knows what they gave up; with it on, an unknown peer is
  a refusal. **What would settle it:** a resolver-pinned transport that hands the proxy an
  address rather than a name, which httpx does not offer today.

- **Every address this console is reached by answers 404 in production today.** Measured against
  the live site 2026-09-17: `https://ourhike.org/` and `/app/` answer 200, and
  `/app/my/tread` and `/app/org/central-park-throughikers/setup` both answer GitHub Pages' own
  "Page not found". There is no `404.html` and no `_redirects` anywhere in this repository for
  GitHub Pages to fall back to, so every deep link under `/app/` misses. That is the whole of how
  this surface is entered — [`client/src/lib/orgRoute.ts`](../client/src/lib/orgRoute.ts) exists
  because a welcome email, an organization's members area and a bookmark are the three doors, and
  the hiker's app links to none of it. **What would settle it:** a static fallback in the published
  tree — a `404.html` that boots the app for a path under `/app/` and stays a not-found page for
  everything else. It is a change to how hikers are served rather than a change to this feature, so
  it is the maintainer's call and not this branch's. Pull-request previews carry the Cloudflare
  equivalent (`_redirects`, in `pr-preview.yml`) so the console can be reviewed at all; that file is
  preview-only and GitHub Pages ignores it.
- **One admin's click is the whole of an organization's consent, and that is a judgement call rather
  than a finding.** Three codeowners approve a registry change because a registry reaches a hiker's
  phone; agreeing that a model may read that registry takes the ordinary admin gate that
  `membership_url` takes, on the argument that it changes nothing a hiker sees and any admin can
  reverse it in one request. An organization that wants it to be a board decision has to make it one
  off-app — what the columns record is who clicked and when, so that conversation has something to
  point at. **What would settle it:** an org telling us they wanted the stronger gate. Nobody has
  been asked, because no organization has used this yet.
- **Nothing has told an organization what a model did with their registry, because none has sent
  one.** `assist_usage` records tokens, a day and a panel; it does not record what was asked, by
  design. An organization auditing a month of use can see how much and on which screens, and cannot
  see what was said. That is the trade taken deliberately — a transcript we kept would be a
  transcript we would then have to protect — and it is worth stating rather than discovering.
- **Nobody has watched a real organization approve a registry pull request, because none has been
  opened.** The chain has tests at every joint and no end-to-end run: the three signatures, the
  generated codeowner line, the opener's containment refusal, and a GitHub review arriving from an
  account this product linked. **What would settle it** is #1623's three settings and one
  organization walking it — which is also the only way to learn whether a trails chair will make a
  GitHub account at all, the assumption the whole wiring rests on and the one thing no test here
  can reach.
- **No screen has ever rendered a real API response.** Every one of the seventeen renders from
  `client/src/org/demoOrg.ts` and `demoVolunteer.ts`, because #600 leaves the production backend
  unbuilt. The endpoints have their own tests and the screens have theirs; what nothing on this
  branch can catch is a mismatch between `orgApi.ts`'s types and what the server actually sends.
  This is the largest untested seam in the work.
- **The public assist budget is one bucket for every caller behind an address-stripping proxy.**
  `client_fingerprint(null)` hashes the word "unknown", so they share a day. It fails in the safe
  direction — the spend stays bounded — and it means one person can exhaust the free lookup for
  everybody behind that proxy. The nominate form works without the panel.

- **The 10% deactivation hold is `@unvalidated`.** Picked, not measured. What would settle it: one
  real roster sync against an org's live feed, and the distribution of how much a normal run actually
  changes. A threshold below the normal churn of a seasonal roster would hold every run for an admin,
  which is the same as having no sync.
- **Every count on every screen is `@unvalidated` and most are invented.** 312 sections, 96 roles, 37
  uncovered sections, 29 demo volunteers, the 28-minutes-from-merge-to-live figure. They come from the
  prototype, where they exist to make layouts dense enough to judge. **The two exceptions are real:**
  the Hike Finder field set comes from [#1427](https://github.com/OurHike/OurHike/issues/1427)'s
  measured export, and Central Park's coordinates are surveyed. Nothing downstream may treat any other
  number as a fact about an org.
- **Maps are schematic.** Central Park's coordinates are real; every other map in the prototype is a
  projected sketch. Production draws the org's own GIS. The map components are layout, not
  cartography.
- **Tables page but do not search or sort.** At 312 sections and 96 roles both are needed and
  unspecified.
- **Maps are mouse-only.** Row-to-map isolation works by click; keyboard and screen-reader equivalents
  are not designed. This is an accessibility gap with a known shape rather than an unknown one.
- **Shared-revenue copy needs a legal read.** It is a promise about money — the one thing here that
  could be a liability rather than a bug. It ships marked as not live.
- **One contrast defect carried forward from the design review:** the global `a` colour is a
  light-background colour and measured 2.21:1 on the pine footer. It needs an on-dark override.
- **What `ReporterType.maintainer` becomes is not decided.** #1169 names the collision — one word
  meaning both a self-declared attribution and a granted role — and records `trail_crew` as a working
  suggestion only. Shipping a console that grants the second while the first stays spelled the same is
  how the collision becomes load-bearing.
