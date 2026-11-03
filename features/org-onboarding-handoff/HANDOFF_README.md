# Handoff: OurHike organization onboarding

## Overview

Everything an organization does on OurHike, from never having heard of it to running its volunteers year after year. Twenty-three screens across five surfaces: two additions to the existing consumer homepage, four public pages, an admin console, the volunteer's own screens, and four embeddable widgets that run on the org's own website.

The spine of the whole thing is one idea: **an org's trail data stays theirs.** They publish it, three codeowners approve changes as real pull requests, nothing about a named volunteer is ever published, and they can export or leave without asking us. Every screen assumes that; several screens exist only to make it visible.

Read `SPEC.md` in this folder before writing code — it carries the decisions, the six conflicts with the current backend (two of which were blocking and are now resolved), and the seven things worth settling first. This README is the map; SPEC.md is the argument.

## About the design files

The files in this bundle are **design references created in HTML** — prototypes showing intended look and behaviour, not production code to copy. The task is to **recreate these designs inside the OurHike codebase's existing environment**: React + TypeScript on the client (`client/src/`), Astro for the marketing site (`site/src/`), FastAPI + SQLAlchemy + Postgres on the backend (`backend/app/`), with Supabase Auth for identity.

Use the repo's established patterns. Specifically:
- The marketing pages belong in `site/src/pages/` as Astro pages, using `site/src/styles/site.css` and the existing `Mark.astro` / `Contours.astro` components. The visual language in these prototypes was lifted from those files — contour field, painted-blaze section marks, ridge silhouette, pine bands.
- The console and volunteer screens belong in `client/src/screens/` as React components.
- New tables need Alembic migrations **with RLS policies in the same revision** (see Conflicts, SPEC.md).

## Fidelity

**High fidelity.** Final colours, typography, spacing, copy and interaction behaviour. Recreate the UI faithfully using the design system's tokens rather than transcribing hex values — every colour in these files is a `var(--token)` reference from `_ds/ourhike-design-system-*/tokens/`, and the equivalent values already exist in `site/src/styles/site.css`.

Two deliberate exceptions, both flagged in SPEC.md's Known gaps:
- **Maps are schematic.** Central Park's coordinates are real and surveyed; every other map is a projected sketch. Production draws the org's own GIS. Treat the map components as layout, not cartography.
- **Numbers are plausible, not real.** Section counts, hours and volunteer totals are invented for density. The only figures taken from real sources are the Hike Finder field set (repo issue #1427) and the Central Park coordinates.

## Screens / views

All screens live in `Join Us.dc.html` and are selected by a `screen` state value, listed here as `id`. The dark strip at the top of that file is **prototype scaffolding, not product** — it switches roles and toggles states so a reviewer can see every variant. Do not build it.

The full screen-by-screen table — purpose, states, the repo files each was built from, and a "watch out" note where the obvious implementation would break a promise — is in **SPEC.md**. Summarised here:

### Public (no account needed)
| id | Name | Purpose |
| --- | --- | --- |
| `homeadds` | Homepage links | The two additions to the existing consumer homepage, shown before/after. Not a page — a spec for editing `NavBar.astro`, `index.astro` and `Footer.astro`. |
| `pitch` | For clubs | Why an org joins, what registering involves, and the form. Belongs at `/for-orgs`. |
| `demo` | Demo org | Central Park Throughikers — a whole published org to walk through. Mounts the real components, deliberately. |
| `nominate` | Nominate an org | Any signed-in hiker submits a club's trails on their behalf. |
| `claim` | Claim your org | An org already listed with no admins. An email at the org domain is the whole check. |

### Admin console (`/org/:slug/setup`)
| id | Name | Purpose |
| --- | --- | --- |
| `approve` | Admin approval | Per-admin status, reminders, audit trail. Includes the declined state. |
| `hub` | Setup hub → Org home | One screen with two lives: stage checklist while onboarding, then permanent management home. |
| `registry` | Hike registry | Claude reads their GIS — files or a server URL — and asks only about what it cannot resolve. |
| `signoff` | Registry sign-off | Three-tier table with blaze mapping, and the PR window where approvals are recorded. |
| `addtrail` | Add a trail | Scoped registry run for one new trail. Diff shows additions only. |
| `emails` | The three emails | Every email we send in the org's name, in full. |
| `leaving` | Settings and leaving | Export everything, remove an admin, unpublish a trail, delete the org. |

### Manage volunteers (`/org/:slug/volunteers`)
| id | Name | Purpose |
| --- | --- | --- |
| `roles` | Roles | Definitions with category and reporting line, hierarchy visual, per-trail mandates, bulk assignment. |
| `workdays` | Workdays | Post a workday, answer signups, confirm hours. Handles orgs who keep their own calendar. |
| `coverage` | Coverage report | Sections with no assigned role, by region, on a map. |
| `volunteers` | Your roster | One table plus three load paths: add one, upload any file, or an IT-configured live endpoint. |
| `person` | Volunteer profile | One person's record. Editable by an admin and by that volunteer. |
| `welcome` | Welcome volunteers | Sends one welcome email each, carrying their own section and supervisor. |

### Volunteer (`/my/tread`)
| id | Name | Purpose |
| --- | --- | --- |
| `section` | Your Tread | The volunteer's own miles. The most important screen in the product. |
| `field` | On your phone | Four phone designs — Your Tread offline, report, confirm hours, POI upkeep. Not narrowed desktop. |
| `volunteer` | What you hand back | The hiker's half — contributing without joining anything. |
| `ridge` | Ridge Runner At-Large | A self-closing commitment window, up to seven days. |

### Embeds (served onto the org's own domain)
Four widgets, reached from Org home's "Put this on your own website". Three are public and paste-only; the fourth is the private management console behind a server-signed 15-minute token. The auth handshake, the six key guards and the server-side code sample are all on that screen and in SPEC.md.

## Interactions & behaviour

- **Navigation.** Left sidebar for org work, top bar public-facing. The sidebar shows only sections the current role permits, with counts on items awaiting action.
- **Everything is a proposal.** Editing anything published opens a draft → diff → pull request → codeowner approvals → merge. Same loop for onboarding and for a correction two years later.
- **Error states are inline**, not a gallery — toggle "show failures" in the prototype strip: GIS that will not parse, an admin who declines, a contested claim frozen for a human, a failed map build.
- **Empty states are inline** too — toggle "show a new org": org home, roles, roster and coverage each explain themselves at zero.
- **Signed-out** — toggle "show signed out": the registration form gates on identity, because registering names you as the org's first admin.
- **Form validation.** At least one admin must hold an email at the org's domain; the check re-evaluates live as the active account changes. Flat files (PDF, spreadsheet) are refused as GIS sources on purpose — they cannot be re-read.
- **Motion.** Design-system motion only: 120–200ms ease-standard fades and colour transitions, buttons to 97% on press. No bounce, no spring.
- **Responsive.** Desktop screens reflow at `minmax(0,1fr)` and wrap; the phone screens are a separate design at 390px, with 44–56px hit targets.

## State management

The prototype holds everything in one component's state. In production most of it is server state; these are the ones that are genuinely UI state:

| State | Purpose |
| --- | --- |
| `screen` | Which view is shown. Becomes routes. |
| `activeOrgName` | Which org the console is scoped to — one person can belong to several. |
| `isAdmin` / `canManage` / `isVolunteer` | Role gates. Server-derived in production; never a client claim. |
| `onboarded` | Whether the hub shows the stage checklist or org home. |
| `signedOut` | Identity. Supabase session in production. |
| `volTab`, `embedTab`, `wdTab` | Tab selection within a screen. |
| `selectedTrail` | Row-to-map isolation on the registry table. |
| `poiQuery`, `poiKind`, `poiAge` | POI search and filters. |
| `blazePicks` | The org's colour mapping, overriding what we proposed. |
| `prStep`, `leaveStage`, `closeReq` | Multi-step flows: pull request, deletion, closure request. |

Data fetching: see the endpoint list in SPEC.md. Paths follow the backend's existing unversioned convention (`/clubs`, `/closures`, `/profiles/me`) — **not** a `/v1` prefix.

## Design tokens

Do not transcribe values. Every colour, type size, radius and shadow in these files is a `var(--*)` reference resolving against `_ds/ourhike-design-system-60cee1fb-e057-43dd-ac0e-abd164795ab7/tokens/` (bundled). The same values exist in the repo at `site/src/styles/site.css`.

The ones worth knowing by name:
- **Greens** `--pine-900` `--pine-800` `--pine-700` `--forest-600` `--forest-500` `--moss-400` `--moss-300` `--sage-200` `--sage-100`
- **Neutrals** `--paper-0` `--paper-100` `--stone-150` `--stone-300` `--stone-500` `--stone-700`
- **Blazes** `--blaze-white` `--blaze-blue` `--blaze-yellow` `--blaze-orange` `--blaze-orange-dark` — these are trail blaze colours and carry meaning. Blaze colours in map and table contexts are data, not decoration.
- **Semantic** `--brand-primary` `--fg-1` `--fg-2` `--fg-3` `--bg-surface` `--bg-page` `--border-1` `--border-2` `--danger` `--warning`
- **Type** `--font-display` (Bitter, slab — headings), `--font-body` (Public Sans), `--font-mono` (IBM Plex Mono — coordinates, mile markers, eyebrows, anything machine-ish)
- **Spacing** 4px base: 4 / 8 / 16 / 24 / 32 / 48 / 64 / 80 / 96 / 128
- **Radius** 8–14px on cards; `999px` pills on buttons and filter chips
- **Shadow** `--shadow-card` and `--shadow-raised` only

One caution found in review: the global `a` colour is a light-background colour. On the pine footer it measured 2.21:1, and needs an on-dark override — `footer a { color: var(--sage-200) }`.

## Assets

- **Photography** — two files in `photos/`, both from the repo's own licence-checked pool (`client/src/lib/heroPhotos.ts`, which admits only public-domain / CC0 / CC BY / CC BY-SA and requires the credit rendered on the image):
  - `blue-folds.jpg` — hero. Evelyn Mostrom, CC0.
  - `welcome-blaze.png` — welcome email header, cropped from `16-water-gap-blaze.jpg`. C. G. P. Grey, CC BY 2.0.
  - Credit pills are rendered on both and **must stay** — the licence requires it.
- **The OurHike mark** is drawn inline as SVG, lifted from `site/src/components/Mark.astro`: a split forest/stone gradient square with a turbulence-roughened white blaze. Use the real component; do not re-trace it. Note each instance needs unique filter/gradient ids.
- **Icons** are inline 1.5px-stroke line SVGs in the design system's recommended style. No icon font, no emoji.
- **Maps** are hand-authored SVG paths. Replace with real geometry.

## Files

**Design references** (open in a browser; `Join Us.dc.html` is the main one):
- `Join Us.dc.html` — all 23 screens
- `Handoff Spec.dc.html` — the spec, rendered
- `SPEC.md` — the same content as text, and the one to read first
- `Registry Table.dc.html`, `Hike Finder.dc.html`, `Workdays Widget.dc.html`, `Coverage Badge.dc.html`, `Console Tiles.dc.html`, `Tread Card.dc.html`, `Page Header.dc.html`, `Phone Frame.dc.html` — the eight shared components
- `Join Us Onboarding Wireframes.dc.html` — the low-fidelity exploration these came from, kept for the reasoning
- `support.js` — the prototype runtime. **Not part of the design**; needed only to open the files.
- `_ds/` — the design system: tokens, stylesheet, component bundle
- `photos/` — the two licensed photographs

**Nine components, not twenty-three copies.** The eight shared files above carry every repeated surface, and the demo org mounts the real ones on purpose. If the demo gets its own copies it starts lying about the product — that is the one structural note worth carrying into the codebase.
