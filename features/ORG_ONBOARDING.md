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

A pull request opened under a service identity credits nobody and puts nobody on the hook, so the
commit is authored by the person's own GitHub account. That is the whole point of the moment.

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
  state (unclaimed|claimed|frozen|deleted)
  membership_url · donation_url · created_by
```

Renamed from Club **in the UI only** — not every org is a club, and the ones that are not are land
trusts and agencies. `state` drives Claim your org: an unclaimed org has live trails and no admins,
which is exactly what a source registered by a maintainer looks like today.

```
OrgAdmin                    (new: club_admins)
  org_id · person_id · title · is_codeowner
  approved_at · declined_at · decline_reason
```

At least one must hold an email at the org domain. One admin registers; three approvals publish. **A
decline pauses the org and is reversible — never a rejection**, because the common cause is a
secretary who does not know what OurHike is rather than a board that said no.

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

## Known gaps

What this design does not answer, stated plainly.

- **An organization has not consented to their registry reaching a third party, and the assist
  panels send it.** `POST /clubs/{slug}/assist` puts section names, trail names, mileages and the
  coverage gap list in front of a model at `api.anthropic.com`. The panel says on screen that what
  goes over is what is on the screen, which is true and is not consent — nobody at the organization
  was asked. It ships inert (`assist_enabled` defaults false) so nothing has been sent, and the
  three public embeds do not touch it. **What would settle it:** a per-organization opt-in stored
  beside the org record, shown at registration and revocable from Settings. That is a schema
  decision for the maintainer rather than one to slip into the branch that found it.
- **Whose credentials open the pull request at registry sign-off is undecided, and the endpoint no
  longer pretends otherwise.** Three codeowners signing produces three rows in `registry_signoffs`
  and nothing else; no code in this repository opens a pull request. It must not be an admin's
  credentials — an org admin has no GitHub account here, and giving one the power to cause a push
  would make every org admin a committer to a public repository. The shape that survives review is
  a service identity with write scoped to the registry path and a person still merging, but that is
  a decision rather than a detail.
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
