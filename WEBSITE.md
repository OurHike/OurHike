# OurHike — the website, planned properly

Companion to [OurHikeValues.md](OurHikeValues.md), [FEATURES.md](FEATURES.md) and
[WIREFRAMES.md](WIREFRAMES.md). WIREFRAMES.md specs the app's screens; this
document specs the other surface — everything that lives at a URL rather than on
a home screen.

It exists because the current site is the app with different CSS, and that is a
category error rather than a polish problem. What follows is the diagnosis, the
principle that replaces it, the page-by-page shape, and a build order.

**Scope note.** "The website" is two things and this plan covers both, because
the same mistake produced both: the marketing/organisational site at the root
(§5), and the app itself opened on a laptop (§6). They are separate workstreams
with separate sequencing (§9).

---

## 1. The diagnosis, from the files

Not "it feels off" — five specific things, each traceable.

**1.1 It borrowed the app's tokens and left the brand behind.**
`site/index.html:25` says so outright: *"Palette lifted from the app's own
tokens... so the site and the thing it installs are recognisably one product."*
Reasonable instinct, wrong execution. It copied the *colours* into a hardcoded
`<style>` block and dropped everything else that makes OurHike look like
OurHike. The design system specifies Bitter (slab serif, "evokes carved trail
signage") for display, Public Sans for body, IBM Plex Mono for mile markers and
coordinates. The site uses `ui-sans-serif, system-ui, -apple-system, "Segoe UI",
Roboto...` for all of it. A page set entirely in the OS default sans is a page
with no typographic voice, and type is most of what "looks first class" means at
a glance.

**1.2 It hand-rolled components that already exist, built for this exact
surface.** `.claude/OurHike Design System/components/navigation/` contains a
NavBar and a Footer. `client/src/design-system/README.md` records why they were
deliberately *not* copied into the app: *"marketing-site chrome (Trails/Get
Involved/Shop/About links, a Donate button), a different surface from this
app."* So the pieces for a website were identified, built, and then the website
was written without them — along with `Card`, `Badge`, `Callout`, and a
`ui_kits/website/` homepage composition that already demonstrates the intended
layout. The site reimplements a worse version of each in inline CSS.

**1.3 It is a phone screen rendered at desktop width.** `.wrap` is
`max-width: 44rem` — about 700px — and there is no width breakpoint anywhere in
the file (the only two `@media` rules are `prefers-color-scheme` and
`prefers-reduced-motion`). The design system's own `--container-max` is 1200px
with a `--container-narrow` of 760px for prose. So the site runs at the *prose*
width for its entire length, on every device, with no grid, no two-column
section, and no image of any kind. On a laptop it is a narrow ribbon of text in
a large field of paper. That single measure is the strongest visual signal that
this was designed for a phone and shipped to a browser.

**1.4 The content is the app's Downloads screen restated as prose.** The page's
substance is: install steps, three download tiers with megabyte counts and
proportional size bars, a resumable-download note, and a "what works today / not
yet" checklist. That is `client/src/screens/Downloads.tsx` and
`client/src/screens/InstallPrompt.tsx` with different styling, plus release
notes. A visitor who has never heard of OurHike is asked to weigh 64 MB against
1.18 GB before being given a reason to care. Storage-budget decisions are a
job for someone who has already decided to use the thing.

**1.5 It has no navigation, because it has nowhere to go.** One page, one
scroll, ending in two GitHub links. There is nothing for the ATC, nothing for a
maintaining club evaluating whether to adopt this, nothing for a volunteer,
nothing for a journalist, and — most consequentially — nowhere to give money,
which per FEATURES.md is a thing only this surface is allowed to do.

**1.6 The app's large-screen layout, which this section was written to demand,
exists now.** When this was written, `grep -rn "@media"` over the client returned
zero matches and every screen was a phone screen stretched wide; #117 closed that
on 2026-08-03 (`client/src/desktop.css`, with tests — the grep now hits in five
files, re-run 2026-08-17, #661). The paragraph is kept because its demand shaped
§6 and because the *site* half is still true: the landing page remains the
Downloads screen restyled, and the site's own line — *"It runs in a desktop
browser for a look around, but it's built for a phone"* — no longer describes the
app, only the page saying it. FEATURES.md's MVP line — **"Same core experience
on phone and web"** — is now met by the app and still owed by the site.

---

## 2. The principle that replaces "make the site match the app"

**The phone and the web are the same person at different moments, doing
different jobs.**

The phone is a field instrument. One hand, cold fingers, gloves, glare, no
signal, a decision to make in the next ninety seconds: where am I, where's the
next water, which way at this junction. Every choice in the app is right for
that — the bottom tab bar, the 44px hit targets behind 38px buttons, the
deliberate absence of a router, the mono position readout. None of it should
change.

The web is a desk. A large screen, a keyboard, a mouse, full signal, an hour to
spend, and a completely different set of questions:

- Is this trail right for me, and what will it actually be like?
- Where do I sleep on nights three through nine?
- What is OurHike, who made it, and can I trust it with my safety?
- How do I give money, and where does it go?
- Can my club adopt this? Who do I talk to?
- How do I help — a work trip, a correction, code?

The current site fails because it answers the field question for someone asking
the desk question. Fixing the CSS would not fix that.

### Three jobs only the web can do

These are not nice-to-haves; they are why this surface has to be good.

**Money.** FEATURES.md: *"No purchases, subscriptions, tips, or payment prompts
inside the mobile app shell — this avoids the ~15-30% Apple/Google App Store
cut... Any paid tier, donation flow, or sponsorship purchase lives on the web
version only."* Any charge OurHike ever makes for itself therefore has exactly
one available surface, and it is this one. A weak website is a weak business
model, not a weak brochure.

> *Corrected 2026-08-27.* This paragraph read *"The entire funding mechanism for
> the ATC and its maintaining clubs — the stated point of the project"*, and that
> was never true: no money reaches the ATC or a club through OurHike, and since
> 2026-08-27 that is settled design rather than an unbuilt stage
> ([features/PRICING_MODEL.md](features/PRICING_MODEL.md) pricing value #6). The
> site's job for the organizations is real but different — it is where their own
> donate and membership pages are linked, so a hiker can reach them in one click
> and give them money that never touches us. That is a traffic job, not a
> treasury one, and it is if anything harder to do well.

**Being found.** An installed app is opaque to search engines. A website is not.
Somebody typing "water sources near Harpers Ferry AT" or "AT shelters in the
Whites" should be able to land on OurHike. The pipeline already produces the
data that would answer them (`trails.geojson`, `poi_*`, `elevation_profile.json`
— see LAUNCH_CHECKLIST.md §1.6). This is the cheapest acquisition channel the
project will ever have and it currently does not exist.

**Being inheritable.** Value #7 asks of every decision: *"could another
ATC-affiliated club pick this up with minimal friction?"* A club officer
evaluating that needs a page written for them, not a repository README. Avenza's
shutdown left NYNJTC stranded; the argument for why that cannot happen here is a
piece of writing, and it needs somewhere to live.

---

## 3. Design direction

The direction already exists in `.claude/OurHike Design System/`. It has never
been used. Most of this workstream is application, not invention.

**Typography, the biggest single visual win.** Bitter for display, Public Sans
for body, IBM Plex Mono for anything numeric and trail-specific — mile markers,
coordinates, elevations, distances, download sizes. The mono face doing data is
what will make the site feel like it was made by people who know the trail
rather than people who know Tailwind. Self-host the files rather than pulling
Google Fonts at runtime (`tokens/typography.css` currently `@import`s from
`fonts.googleapis.com`): one less third-party request, no privacy footnote, no
FOUT.

**Measure and rhythm.** Prose at `--container-narrow` (760px). Everything else —
grids, maps, imagery, footer — out to `--container-max` (1200px). Vertical
rhythm from the 4px scale (`--space-16` / `--space-20` between sections rather
than the current flat 2.5rem everywhere). The point is contrast between
full-bleed and narrow; a site at one width for its whole length reads as a
document, not a site.

**Photography, and this is the real gap.** The design system flags it: *"No real
photography was available, so placeholders (soft green/stone gradients) stand
in — swap in real trail photography when available."* Those placeholders are
still what the UI kit renders. A trail site with no photograph of a trail cannot
look first class, and no amount of typography compensates. This needs actual
sourcing — NYNJTC and ATC volunteer photographers, or a properly-licensed set —
and it is the one item on this plan that cannot be solved by writing code. Start
it early; it has the longest lead time. Warm natural grade, per the DS, not
desaturated stock-outdoors.

**The blaze as the organising motif, used sparingly.** The site already found
this instinct — the white blaze marking each `h2`, the ridge silhouette closing
the hero, the topographic contour lines. Those are genuinely good and are the
best things on the page. Keep them; give them room. The blaze accent colours
(orange/yellow/blue) stay reserved for CTAs and status, per the DS.

**Motion:** minimal, 120–200ms, `--ease-standard`, no parallax. Respect
`prefers-reduced-motion`, which the current page already does.

### ⚠ Do not ship the design system's placeholder copy

The DS was built from nynjtc.org as an aesthetic reference, and its example
content is **NYNJTC's actual facts**, not OurHike's:

- `components/navigation/Footer.jsx` — "600 Ramapo Valley Rd, Mahwah, NJ 07430"
  (NYNJTC's headquarters) and a "Trail Walker Magazine" link (NYNJTC's
  publication).
- `ui_kits/website/Homepage.jsx` — "Est. 1920 · Volunteer-Powered" and "2,100+
  miles of public trails across New York and New Jersey."

OurHike was not established in 1920 and does not maintain 2,100 miles of trail.
Shipping any of that would put false claims and another organisation's address
on the site. Take the **layout and component structure**; write every word
fresh. The DS's own readme is explicit that its copy is interpretive.

---

## 4. Voice

The DS specifies it and the existing page mostly gets it right, which is worth
saying plainly — the writing is the best thing about the current site. Warm,
plain-spoken, sentence case, no emoji, numbers used concretely and sparingly.
Low-pressure CTAs.

Two things the redesign must not lose:

**Honesty about beta status.** *"This is a beta, and worth treating as one... 
Carry a paper map and a compass."* That paragraph is the single most valuable
thing on the page and it embodies value #4. A prettier site creates real
pressure to soften it, because a polished page implies a finished product. It
must stay prominent and be *designed* rather than bolted on — a considered
element in the layout, not a yellow warning box in the flow. Same for the
"What's not built yet" list.

**Honesty about uncertainty in data.** When POI pages ship (§5), water sources
sourced from OSM/NHD are *approximate and unverified*, and ATC facility data is
authoritative. FEATURES.md is explicit that the UI must distinguish them. That
distinction has to survive onto a public web page where it will be read out of
context and indexed.

---

## 5. Workstream A — the site

Nine surfaces. Not all at once; see §9 for order.

### 5.1 Home
The one job: in five seconds, what this is and why it exists. Full-bleed hero
with real trail photography, Bitter headline, the beta badge kept. Then, in
order: the offline promise shown rather than described (the map, working, with
the phone in airplane mode); where the money goes; what's built and what isn't;
the three doors out — *Get the app*, *Support the trail*, *Get involved*.
Not the install steps. Not megabyte counts.

### 5.2 Explore the trail — the interactive map
The page that makes the case better than any copy could: the actual trail, in
the browser, at desktop scale. Shares the client's MapLibre + PMTiles setup
(§6), streaming from R2 rather than downloading — the offline archive is a phone
concern. Deep-linkable by section, POI, and mile. This is also the page that
converts: someone who has just spent ten minutes browsing shelters is the right
person to ask about installing it on their phone.

### 5.3 Generated pages — sections, shelters, water, resupply
The SEO surface, and the reason the site can be found at all. One page per
shelter/campsite/resupply point and one per named trail section, generated at
build time from the published pipeline artifacts. Each carries what a planner
actually wants: location, mile, elevation, the profile for the surrounding
stretch, what's nearby, how the data is sourced and how confident it is, and a
map. Several hundred pages, all static.

**Two gates before any of this is published, and neither is optional:**

- **A publication review of what may be indexed.** Everything in the app is
  already available to anyone who downloads it, but a public indexed page is a
  different act with different consequences. `features/REPORT_A_PROBLEM.md`
  routes "bad hikers" reports internal-only; `features/HIKER_SAFETY.md`'s
  warning pins are moderated; `features/LAND_OWNERSHIP.md` bears on what is safe
  to publish about private land and permissive crossings. Decide the whitelist
  of publishable types deliberately — do not derive it from "whatever's in
  `poi_*`."
- **Licensing.** LAUNCH_CHECKLIST.md §7: opentrail.org's terms are unconfirmed
  and their water/resupply data is in the build. Republishing it as indexed web
  pages is a materially larger ask than shipping it inside an app archive. This
  raises the priority of ROADMAP.md's open item to contact that maintainer.

### 5.4 Get the app
Where the current install content goes, done properly: platform-detected,
Android and iOS paths shown separately rather than progressively disclosed,
screenshots, and what to expect on a first download.

**⚠ Preserve the constraint the current page discovered.** `site/index.html:841`
documents it at length: installation *must* happen from `/app/`, because that is
the page carrying the manifest and service worker, and the SW scope cannot be
raised to cover the root without a `Service-Worker-Allowed` header GitHub Pages
will not send. A browser's "Add to Home Screen" on the marketing page produces a
plain bookmark that looks exactly like a successful install and works offline
not at all — *"Someone could carry that into the woods."* That is hard-won and
safety-relevant. A redesign that adds a friendly install button to the homepage
reintroduces it silently. Carry the comment across with the code.

### 5.5 Support the trail — the money page
The business model's only surface. Per `features/PRICING_MODEL.md`: the
thru-hike pass, the regional pass, the all-access ceiling, the volunteer
exemption, and direct links to the organizations' own giving pages. Structure
the page now even though pricing is Post-MVP and deliberately un-timed — today
it is those links plus an honest statement of intent. (This read "a plain
donation path… today it can be a donation path plus an honest statement of
intent" until 2026-08-27. A donation path OurHike ran on an organization's
behalf is the thing that got decided against, so the spec had to move with the
page.) What the page has to make unmistakable, because it
is the entire differentiator against FarOut: **where the money goes**, and that
nothing safety-relevant is ever behind it. Pricing value #6 — "money never
passes through OurHike" — is a design problem as much as a copy problem. (It
read "money follows the trail it came from" until 2026-08-27; the value keeps
its number precisely so this citation still resolves.)

### 5.6 Get involved
Volunteering with maintaining clubs, reporting conditions, contributing code and
data. Per `features/VOLUNTEERING.md` this is contact details and external signup
links for v1, which is fine — the point is that the door exists. Value #2 says
the community that built the trail builds this too; right now the site says that
nowhere.

### 5.7 For clubs
The inheritability page, written for a club officer, not a developer. What
OurHike is, what adopting it costs, what data it needs, what happens if OurHike
disappears (value #3: fork it and keep going), and who to talk to. Avenza's
shutdown is the argument and it should be made explicitly. This page is how the
project stops being "NYNJTC's app that others might use" and starts being what
value #7 asks for.

### 5.8 About — mission, values, open data, safety
OurHikeValues.md, edited for a public audience. The privacy and data-handling
position from `features/IDENTITY_AND_PRIVACY.md`. Data sources and attribution
(ATC, USGS, OSM/ODbL, opentrail) — currently one line in the footer, and the
ODbL attribution requirement is a legal obligation, not a courtesy. Also the
home for the privacy policy the app stores will require (ROADMAP.md Phase 3).

### 5.9 Status and changelog
Where "what works today / not yet" lives — moved off the homepage, kept, and
kept current. A beta that publishes its own known gaps is more trustworthy than
one that doesn't, and this is the page that makes value #4 visible rather than
merely asserted.

---

## 6. Workstream B — the app on a big screen

Distinct from the site and, past the first two phases, more valuable. Today the
web app is the phone app stretched; FEATURES.md promises "the same core
experience on phone and web," and `features/MAP_OPTIONS.md:150` already sketches
the answer:

> **Web:** mouse/keyboard/scroll-wheel zoom as primary, hover states become
> available, and the extra screen real estate means the legend can be a
> persistent expandable panel rather than a modal that has to be dismissed to
> see the map underneath it.

That is one sentence of spec for an entire platform. Expanding it:

**Layout.** One breakpoint around 900px. Above it: the bottom tab bar becomes a
left sidebar (the tab bar's placement is a thumb-reach decision that means
nothing with a mouse), the map takes the full remaining frame, the legend
becomes the persistent panel described above, and search moves into the chrome
as a permanent field rather than a sheet. Sheets become side panels; nothing
that covers the map should need dismissing to see the map.

**Branding.** The sidebar's foot — the bottom-left corner of the page — carries
the OurHike mark, wordmark included, stacked rather than side by side. The
design system's horizontal lockup ties the wordmark to the icon at a fixed
ratio, and at a size where the wordmark reads as a wordmark rather than a
caption, that lockup is wider than the sidebar; stacking is what buys the type
its size back. The icon is the design system's own, and the wordmark mirrors
its type styling so the two cannot drift apart. It is chrome, not map:
a watermark over the canvas would spend terrain a hiker may be reading, and the
sidebar's empty bottom spends nothing.

The wordmark is the desktop-only half. A phone's bar is the same element and so
is still the page's bottom-left corner, but it is a single row shared with three
thumb targets, so it carries the icon alone (WIREFRAMES.md §1). That is a
deliberate floor rather than the answer: how much chrome this screen should
carry before the map gets what is left is a real design question, and is tracked
as its own spike rather than settled here.

**The elevation profile earns the space.** `ElevationRibbon` is a thin strip
because a phone has no room. On a desktop it can be the full interactive chart
FEATURES.md describes — scrubbing, gain/loss for a selected stretch, the
Naismith estimate — across the bottom, linked to the map. This is FarOut's
signature feature and the desktop is where it can actually be better.

**Input.** Hover states, keyboard shortcuts, focus rings, `Esc` to close, arrow
keys to pan. Touch targets can relax from 44px where the pointer is fine
(`@media (pointer: fine)`), which tightens the whole UI visually.

**Routing — the decision to revisit.** `App.tsx:1` explains the absence of a
router: *"Every screen is reached from the tab bar or from a flow that owns its
own back-out, so URLs would be a second navigation model to keep in sync with
the first for no gain a hiker would notice."* Correct for a hiker.
Wrong for the web, where it costs deep links, the browser back button,
shareable views, and the ability for the site (§5.2, §5.3) to link into a
specific shelter or mile. Adding routes is the largest single change in this
workstream and the one that unlocks the most.

**Download UX.** On desktop, "download 1.18 GB to this browser" is close to
meaningless — a laptop has signal. Default the desktop experience to streaming
from R2, and reframe the Downloads screen as *"set your phone up"*, with a QR
code to hand off. Right now desktop users are offered a decision that only makes
sense on a phone.

---

## 7. Technical approach

**Recommendation: Astro, static output, deployed alongside the app on the
existing Pages workflow.**

Reasoning, weighed against value #8 (boring, well-supported, survives maintainer
turnover):

- Static HTML out. No server, no runtime cost, same free hosting. Hosting cost
  and operational burden stay at zero, which is a hard constraint here.
- React islands. The design system components are already `.jsx` and the app is
  already React, so there is **one** component vocabulary across both surfaces
  rather than two. The interactive map (§5.2) is an island; every other page
  ships no JavaScript.
- `getStaticPaths` over the pipeline's published artifacts generates §5.3's few
  hundred pages from data that already exists, with no CMS.
- Content collections give the editorial pages (§5.7, §5.8) Markdown authoring,
  which matters if a non-developer is ever to edit a word of this.

The honest tension: this adds a framework, and value #8 favours boring. The
mitigations are that the output is plain static files (if Astro were abandoned,
the built site keeps working and can be replaced incrementally) and that it is
widely used. If the team would rather not, **Eleventy** is the smaller-surface
alternative at the cost of not sharing React components. What is *not* viable is
continuing to hand-write HTML — §5.3 alone is several hundred pages.

**Deployment.** `.github/workflows/pages.yml` already assembles `site/` → root
and `client/dist/` → `/app/`. The change is one build step before the copy;
paths and the app's `base` are untouched. Worth doing at the same time:
**move onto `ourhike.org`** — registered 2026-08-15 through Cloudflare
Registrar, with `data.ourhike.org` already serving the R2 bucket
(LAUNCH_CHECKLIST.md §1.5), and `ourhike.github.io/
OurHike/` is not a URL to put on a site meant to be trusted with somebody's
navigation. Done ahead of this work rather than as part of it (#733), so the
Astro build in Phase 1 stands up at the apex from its first commit.

**Design system, first real task.** The DS components are demo artifacts:
inline-styled `.jsx` loaded via a `window.OurHikeDesignSystem_60cee1` global
bundle. Before anything is built on them they need to become importable
components with real stylesheets, shared by both surfaces —
`client/src/design-system/` is the existing precedent and it was a one-time copy
that has now drifted. Decide where the canonical copy lives before there are
three.

**Performance budget**, because it is a trail site and people load it in towns
on bad wifi: every page under 100KB excluding images, no render-blocking
third-party requests, images responsive and lazy past the fold, LCP under 2s on
a 3G profile. The current page is genuinely good at this — no dependencies at
all — and that is worth not regressing while adding photography.

**Accessibility:** WCAG AA, which the DS already targets for the waypoint icon
palette. Full keyboard operation, visible focus, real landmarks, alt text on the
trail photography. The map island needs a non-map path to the same information —
which §5.3's generated pages conveniently already are.

---

## 8. What must not change

Collected in one place because a redesign is exactly when things like this get
lost:

1. **Install happens from `/app/`, never from the marketing site** (§5.4). The
   reasoning in `site/index.html:841` moves with the code.
2. **The beta warning stays prominent** (§4). Designed, not softened.
3. **OSM/ODbL attribution** appears wherever OSM-derived data is shown, site
   included (LAUNCH_CHECKLIST.md §7).
4. **No purchase surface inside the mobile app shell.** The app links out; the
   web transacts (FEATURES.md).
5. **Nothing safety-relevant behind a paywall, ever** (value #5,
   PRICING_MODEL.md pricing value #1) — a commitment the pricing page should
   state out loud, since it is the differentiator.
6. **Data provenance and confidence are shown, not flattened** (§4).
7. **The app's field ergonomics are not touched** by the desktop work: 44px
   targets, bottom tab bar, glare-legible contrast all stay at phone widths.

---

## 9. Build order

Sequenced so each phase is independently landable and the earliest work has the
highest ratio of value to effort.

**Phase 0 — Start the photography sourcing.** Longest lead time, blocks the
visual ceiling of everything else, cannot be coded around. Begin immediately and
in parallel with everything below.

**Phase 1 — Foundations.** Promote the design system to real importable
components with self-hosted fonts. Stand up the Astro build inside the existing
Pages workflow, emitting the current single page unchanged. No visible change;
everything after this is cheap.

**Phase 2 — The real site, first four pages.** Home, Get the app, About,
Support the trail. Real NavBar and Footer (with OurHike's own facts — §3),
proper containers, Bitter/Public Sans/IBM Plex Mono, the beta position kept
prominent. **This is the phase that answers the original complaint**, and it is
mostly application of decisions already made.

**Phase 3 — Desktop app layout.** The 900px breakpoint, sidebar, persistent
legend, hover and keyboard, the full elevation chart, the desktop download
reframe. Ships the "same core experience on phone and web" promise. Independent
of the site work and can run in parallel with a second person.

**Phase 4 — Explore, and routing.** Add routes to the client; build §5.2 on top
of them. These are one piece of work — the map page is not deep-linkable without
the routes, and the routes have no consumer without the page.

**Phase 5 — Generated pages.** Only after the §5.3 publication review and the
opentrail licensing answer. Highest long-term value, most preconditions.

**Phase 6 — For clubs, Get involved, Status.** Lower traffic, high strategic
weight. Written once the rest of the site gives them somewhere to sit.

**Deliberately not planned here:** a blog, user accounts on the website, a
community forum, and anything with a login. Each is a maintenance commitment on
a volunteer project, and none is needed for the jobs in §2.

---

## 10. Decisions needed before Phase 2

1. **Domain. Decided (#733), and no longer blocking anything here.** `ourhike.org`
   is registered, `data.ourhike.org` has served the R2 bucket since 2026-08-15,
   and the app moves to `ourhike.org/app/` with the landing page at the root —
   the structure §5 and §8 already assume. LAUNCH_CHECKLIST.md §3b is the
   ordered migration, and the ordering is the substance: the app's origin is
   what `.github/expected-origins.yml`, the R2 CORS allow-list and both Supabase
   redirect allow-lists are keyed on, and #427 — the eight days the deployed app
   drew a topo sheet with no Appalachian Trail on it — is what one of those
   moving without the others looks like.

   What this settles for the site work: pages built here are served from the
   apex, so §5.3's generated pages and §5.2's map get real paths under
   `ourhike.org/` rather than under a repository name.
2. **Astro, Eleventy, or hand-written?** §7. Determines Phase 1's shape.
3. **Photography.** Who is asked, under what licence, by when? §3.
4. **Whose site is this, in the copy?** OurHike as an independent project, or as
   something NYNJTC/ATC-affiliated? The DS's voice notes assume an organisational
   "we" that does not yet map onto a real organisation, and every page's copy
   depends on the answer. This is the one open question that blocks writing.
5. ~~**Money, today.** Does Phase 2's Support page take donations now (needs a
   Stripe account and an answer to "who receives it"), or state intent until
   PRICING_MODEL.md's structure is built?~~ **Answered 2026-08-27.** Neither, as
   posed. The page ships, it takes nothing, and it links to the organizations'
   own giving pages — so "who receives it" stops being OurHike's question to
   answer, which is the half of this that was actually hard. Whether OurHike
   ever takes a donation toward **its own** costs is still open and is a
   different question; see [features/PRICING_MODEL.md](features/PRICING_MODEL.md)
   value #6 and its superseding banner.

---

## 11. How to tell it worked

- Someone who has never heard of OurHike can say what it is and why it exists
  after five seconds on the homepage — without encountering a megabyte count.
- A club officer can evaluate adoption without opening the repository.
- A hiker can plan a section at a desk, on a big screen, without being asked to
  download 1.18 GB to a laptop.
- Somebody who wants to give money can, in under a minute, and can see where it
  goes.
- A search for a specific shelter or water source can reach OurHike.
- The site is unmistakably the same product as the app — and unmistakably not
  the same *screen*.
- Every safety commitment in §8 survives, checked explicitly at each phase.
