# OurHike organization onboarding — build spec

Written for whoever picks this up. It records the decisions behind the screens, not just their
appearance — the rules are the product here, and most of them came from the repo's own feature docs.

Rendered version: `Handoff Spec.dc.html`. Screens: `Join Us.dc.html`.

---

## Read these five first — every screen assumes them

1. **Nothing is overwritten — every change is dated.**
   A report filed three weeks ago must still route to whoever covered that mile then. Assignments,
   roles and registry rows are append-only with effective dates; "current" is a query, not a column.

2. **Nothing publishes without codeowner approval.**
   Registry changes need all three admins; smaller edits need one. This includes the nightly GIS
   re-read — our own automation proposes, it does not publish. Implemented as real pull requests
   against the public repo.

3. **A signup is an introduction, not an enrolment.**
   VOLUNTEERING.md is explicit: states are `interested | confirmed | waitlisted | declined`, and the
   app must never leave somebody believing they are on a roster when they are not. Real workdays
   carry waivers, minimum ages and tool training.

4. **Nothing about a named volunteer is ever published.**
   Thanks attach to a place and a category, never to a person. Attribution is inferred privately —
   whoever covers that section sees it, and so do their supervisors. Nobody outside the org learns
   who maintains which mile, so `publicly_creditable` ships defaulted off with no UI and there is no
   consent toggle to build. Hours and reports belong to the volunteer and survive the org deleting itself.

5. **No money passes through OurHike.**
   ONBOARDING.md, and a test guards the value-prop copy. We link the org's own membership and
   donation pages. If a shared-revenue programme ever exists, OSC is fiscal host at 10%, Stripe takes
   its fee, and our share covers infrastructure only.

---

## Decisions made

Settled with the product owner, with the reasoning kept.

**Thanks never name a person.** A hiker thanks a place and a category. The volunteer assigned to that
section sees it, and so do their supervisors. *Why: this dissolves the `publicly_creditable` problem
rather than solving it — there is no consent flag to design because nothing about a named person is
published. Let SAYING_THANKS.md keep the question if public credit is ever wanted.*

**Roster and assignments write over HTTP.** Protected by RLS, with an audit row for every sync run —
who, when, what changed. *Why: the old reviewed-file rule was about publication, and the roster is
never published. Visibility is admins and supervisors, plus each volunteer seeing themselves.*

**A bad sync cannot empty your roster.** A run that would deactivate more than ~10% applies its
additions and holds its deactivations for an admin. *Why: a changed API field at 4am must not release
three hundred roles and blank the coverage report before anyone wakes up.*

**Supervisors propose, admins confirm.** Admins change any assignment; a supervisor proposes and an
admin confirms. Count on org home, detail on Roles. *Why: RLS says who may write, never whether a
write was right — and a wrong section assignment sends a hiker's report to the wrong person.*

**A volunteer can step back themselves.** Any time, without asking. It notifies their supervisor and
frees the section. *Why: the org's feed can already deactivate them; they should have at least that
much say. Separate from deleting their OurHike account.*

**A new gap is flagged, not escalated.** It appears on the coverage report and the supervisor is told.
Hikers are not told a section is unmaintained. *Why: most gaps fill within a season, and treating each
as an incident trains people to ignore the report.*

**Orgs are identified by a readable slug** — `/org/ramapo-trail-conference`, chosen at registration.
*Why: it appears in every route, every embed's `data-org`, and the PR paths.*

**One release, not three.** *Why: the owner's call, and defensible — a registry with no volunteers
behind it is a map nobody maintains, which is the thing OurHike is trying not to be.*

**Three approvals for the registry, one admin elsewhere.** *Why: three-for-everything makes small
corrections cost more than they are worth, and the corrections stop happening.*

**Your Tread is reachable five ways** — from the hiker app once assigned, the welcome email, embedded
in the club's members area, its own bookmarkable URL, and a banner when something is waiting.
*Why: it is the most important screen and was previously reachable only from an admin console.*

**GitHub is offered twice** — at registration alongside Google, and again at the pull-request moment.
*Why: asked in context it converts; asked only in settings the contribution gets attributed to nobody.*

**Shared-revenue copy ships as written**, marked clearly as not live. *Still wants a legal read.*

---

## Where this lives

None of this replaces the hiker-facing homepage. The consumer front door stays as it is and gains two
links.

| Route | Who | What |
| --- | --- | --- |
| `/` | Hikers | **Unchanged.** Gains one nav link and one footer column. |
| `/for-orgs` | Anyone | Pitch and registration form. WEBSITE.md §5.7 already names this page. |
| `/for-orgs/demo` | Anyone | Central Park Throughikers — a whole published org. |
| `/for-orgs/nominate` | Signed-in hiker | Submit a club's trails on their behalf. |
| `/for-orgs/claim` | Signed-in hiker | Claim an org listed with no admins. |
| `/org/:slug/setup` | Org admins | Onboarding hub, then permanent org home. |
| `/org/:slug/volunteers` | Admins + supervisors | Roles, workdays, coverage, roster, welcome. |
| `/my/tread` | Volunteers | Your Tread. Reachable from the hiker app, not only the console. |
| their site + `embed.js` | Their visitors | Four embeds. Three public, one token-gated. |

`NavBar.astro` already reserved the first link: *"Explore the trail (Phase 4), For clubs and Get
involved (Phase 6) join this row when they are real — and not a day before: a nav link to a page that
is not there is a promise the site breaks on its second click."* The page is now real.

---

## Conflicts with the existing codebase

Checked against the repo, not assumed.

### 1. GitHub as a fourth SSO provider — decided, and the codebase is ready
`features/AUTHENTICATION.md`, `client/src/lib/auth.ts`, issue #397

AUTHENTICATION.md already calls for this: *"A user can have more than one of these linked to the same
account… worth designing for from the start rather than retrofitting."* It also lists provider linking
as one of two things named in the doc but **not built**. Supabase supports GitHub OAuth natively, so
this is a Cloud-side registration plus a `VITE_AUTH_PROVIDERS` entry, not new auth code.

**Build the linking flow with three rules:** (a) link only while already signed in — never auto-link on
a matching email, since GitHub addresses are often private noreply aliases and matching on an
unverified address is an account-takeover path; (b) a GitHub identity is optional and additive — a
trails chair who will not make a developer account still registers, approves and publishes, they are
simply not the commit author; (c) unlinking must not orphan the account, so refuse it when GitHub is
the only linked identity.

A PR opened under a service identity credits nobody and puts nobody on the hook, so the commit must be
authored by the person's own GitHub account. That is the whole point of the "you are officially a
coder" moment.

### 2. Endpoint paths — no `/v1` prefix
`backend/app/routers/*.py`

The backend serves unversioned paths: `/reports`, `/closures`, `/profiles/me`, `/hikes`,
`/maintainer-assignments`. The entity is `clubs` in the database; Org is a UI rename only, so the route
stays `/clubs`.

### 3. The no-HTTP-writes rule on `clubs` and `maintainer_assignments` — resolved
`backend/README.md` line 86, `features/SAYING_THANKS.md`

The repo forbids HTTP writes to these two tables because *"an assignment says a named volunteer is at a
known place on a predictable schedule, which is the fact SAYING_THANKS.md declines to publish without
consent."* Read closely, that is a rule about **publication**, not access — and the two come apart. RLS
answers who may write; it was publication that needed the reviewed file.

Decided: roster and assignments write over HTTP with RLS and an audit row. Safe because the roster is
never published. The reviewed-file path stays where it belongs — the registry, which is public by
definition. Two guardrails replace it: the ~10% deactivation hold, and supervisors proposing while an
admin confirms.

### 4. Hours-confirmation endpoints already exist — reuse them
`V2_PLAN.md` line 619 (#762)

*"#762's endpoints for hours confirmation exist"* — with the note that the tap still needs a sheet of
its own. That sheet is the phone screen in this prototype. Do not design a second hours model.

### 5. Closures already have a moderation model — reconcile
`backend/app/routers/closures.py`, `routers/moderation.py`

`POST /closures`, `PATCH /closures/:id` and verify/dismiss exist behind a role gate. The three-volunteer
rule should be data on the existing closure (an approvals list), with the existing supervisor gate as
the single-approver path. One lifecycle, two ways to satisfy it.

### 6. Any new table needs RLS in its migration
`backend/alembic/versions/b3d1c7a94e02_enable_row_level_security.py`, `LAUNCH_CHECKLIST.md` 349–353

PostgREST is a second front door into the same Postgres that never passes through FastAPI. Alembic
creates plain tables, so a new table without a policy is readable and writable by anyone who views
source and copies the anon key. Also: **never** add `force row level security` — it applies to the owner
and would take every endpoint down.

---

## Data model

Names match the repo where the repo already has them.

```
Org                         (repo: Club)
  id · name · domain · website · verified_by (dns|email)
  state (unclaimed|claimed|frozen|deleted)
  membership_url · donation_url · created_by
```
Renamed from Club in the UI only — not every org is a club. `state` drives Claim your org: an unclaimed
org has live trails and no admins.

```
OrgAdmin                    (repo: club_admin)
  org_id · person_id · title · is_codeowner
  approved_at · declined_at · decline_reason
```
At least one must hold an email at the org domain. One admin can register; three approvals are needed
to publish. A decline pauses the org and is reversible — never a rejection.

```
Park / TrailSystem          (new)
  id · org_id · name · kind (park|system|forest)
```
Top level of the three-tier naming. ATC has one trail with many sections; NYNJTC has many systems. This
tier can be thin without being wrong.

```
Trail                       (new)
  id · park_id · name (nullable)
  blaze_value_raw · blaze_mapped · miles
```
A trail with no name or blaze is legitimate — a route on a map. `blaze_value_raw` keeps the org's own
string; `blaze_mapped` is what we can render, and the mapping is theirs to confirm.

```
Section                     (repo: maintainer sections)
  id · trail_id · name · start_anchor · end_anchor · miles · geometry
```
Anchors reference mile markers or POIs, never free text — that is what lets a report find the right
maintainer years later.

```
Role                        (new)
  id · org_id · name · category (Trail Maintenance|Stewards|Environmental)
  reports_to_role_id · section_id (nullable)
  required · required_by · retired_at
```
`required` + `required_by` covers mandates an org inherits (ATC requiring roles of NYNJTC). A retired
role keeps its holders' history; only an unheld role is deletable.

```
MaintainerAssignment        (repo: assignments.example.json)
  person_id · role_id · section_id
  effective_from · effective_to · publicly_creditable
```
Several people can hold the same section, and one person can hold many roles. Deactivation releases
roles so coverage never looks covered when it is not.

```
WorkProject                 (repo: WorkProject)
  id · org_id · title · starts_at · meet_point · cap (nullable)
  source (ourhike|mirrored) · signup_url
```
`source=mirrored` means the org's own calendar is authoritative and signup goes to their form. Both
paths must coexist — that is the hard part.

```
Closure                     (new — see conflict 5)
  id · section_id · requested_by · reason · until · detour
  approvals[] · approved_by_supervisor
```

```
HoursEntry                  (repo: SAYING_THANKS.md)
  person_id · section_id · hours · logged_at
  confirmed_by · confirmed_at · disputed_at
```
Claimed by the volunteer first, confirmed by a supervisor after. Clubs report these to ATC and land
agencies, and PRICING_MODEL's 40-hour fee exemption depends on the confirmed figure.

---

## Permissions

Four tiers. A person can hold several at once, and the UI shows the union of what they allow — never a
role picker.

| Tier | Can | Cannot |
| --- | --- | --- |
| Signed-in hiker | Nominate an org · claim an org on their domain · view any published org | See any roster, hours or unpublished work |
| Volunteer | Your Tread · report issues · request closures · log hours · edit POIs · edit own profile | See others' records · confirm hours · touch the registry |
| Supervisor / chair | All of the above, plus workdays, signup replies, hours confirmation and roster loading for their crews | Registry changes · admin membership · deletion |
| Org admin (codeowner) | Registry, roles, regions, giving links, embeds, keys, leaving. Approves proposals. | Act alone on registry changes — three approvals, always |

---

## Endpoints implied

Indicative, not settled — argue with them. Unversioned, per the backend's convention.

```
GET    /clubs/:id                        Org with admins, giving links, state
POST   /clubs                            Register. One admin creates; three approve to publish
POST   /clubs/:id/claim                  Domain-verified claim. Returns frozen on dispute
POST   /clubs/:id/gis-source             Register a server URL. Refuses flat files
GET    /clubs/:id/registry/diff          Proposed vs live. Backs sign-off and the nightly re-read
GET    /clubs/:id/coverage?region=       Sections with no assigned role, with geometry
POST   /workdays/:id/signups/:sid/reply  confirmed | waitlisted | declined, with a message
POST   /closures                         EXISTS — reuse, do not add a second path
PATCH  /closures/:id                     EXISTS — the approval count rides on this
POST   /reports/:id/verify               EXISTS (moderation) — the supervisor gate is here
GET    /maintainer-assignments           EXISTS — read-only today; see conflict 3
GET    /profiles/me/export               EXISTS — the volunteer half of "take your data"
DELETE /profiles/me                      EXISTS — a person leaving is not an org leaving
POST   /console/session                  NEW — secret key + signed-in email → 15-min scoped token
```

### Console embed auth

Your server posts the signed-in person's email with the secret key; we return a 15-minute token scoped
to one person, one org, one origin. You send only the email — we resolve roles from the roster, so your
system never mirrors our permissions. Somebody not on the roster gets a **no-permission token rather
than an error**, so the page still renders.

Six guards, designed for the day somebody hardcodes a key: the public key alone opens nothing; origins
are allow-listed; tokens expire in 15 minutes; two keys live at once for zero-downtime rotation; every
token request is logged with its origin; a new key is read-only until write is deliberately granted.

---

## Before this goes to Claude Code

1. **Answer the two decisions above first.** GitHub-as-provider is decided but the linking flow is
   unbuilt and Supabase-side. The roster-write question needs its answer before the sync is built at
   all, or it gets built twice.
2. **Decide the slug shape now.** Everything links to `/org/:slug`. Cheap today, expensive in week three.
3. **Write the RLS policies into the first migration.** PostgREST is a second front door, and a missing
   policy will not fail loudly.
4. **Get the shared-revenue copy legally read.** It is a promise about money — the one thing here that
   could be a liability rather than a bug.
5. **Hand over the field screens with the desktop ones.** Hours confirmation and issue reporting are
   car-park jobs; if the phone layouts arrive a release later, the desktop versions get built in a way
   that makes them awkward to retrofit.
6. **Do not rebuild the widgets per page.** Eight components carry every repeated surface, and the demo
   org mounts the real ones on purpose. The moment the demo gets its own copies it starts lying about
   the product.

---

## Known gaps

What this prototype does not answer, stated plainly.

- **No empty / first-run states beyond four screens.** Org home, roles, roster and coverage explain
  themselves at zero; the rest still assume a mature org.
- **Maps are schematic.** Central Park's coordinates are real and surveyed; the rest are projected
  sketches. Production draws the org's own geometry.
- **Numbers are plausible, not real.** Only the Hike Finder field set (#1427) and the Central Park
  coordinates come from real sources.
- **Tables page but do not search or sort.** At 312 sections and 96 roles, both are needed and
  unspecified.
- **Maps are mouse-only.** Row-to-map isolation works by click; keyboard and screen-reader equivalents
  are not designed.
- **Shared-revenue copy needs legal review.**
- **One contrast defect to carry forward:** the global `a` colour is a light-background colour and
  measured 2.21:1 on the pine footer. Needs an on-dark override.
