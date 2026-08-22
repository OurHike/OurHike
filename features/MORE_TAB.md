# OurHike — The More Tab (Design Draft v1)

Companion to [WIREFRAMES.md](../WIREFRAMES.md) §10 (wireframed as "Settings", frame
`16a`) and [UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md), which designed most of what
lives on this screen. This doc is about the screen's *shape* — the individual
preferences already each have a design authority; this is where their container
gets one.

**Scope note:** navigation and information architecture only. No new preference,
toggle, or backend field is proposed here — everything below is already built and
already shipped; the ask is to organize it, and to reconsider what it is called now
that there is enough of it to have an opinion about.

## The problem, measured

**995 lines across five files render as one continuous scroll, ten sections deep,
with no sub-navigation of any kind** (measured 2026-08-18 by line count:
`client/src/screens/More.tsx` 175, `Settings.tsx` 489, `AboutBuild.tsx` 113,
`ReportBug.tsx` 101, `chrome/DownloadsLink.tsx` 117. `More` renders two sections of
its own, then mounts `<Settings>`, which renders five more and appends the last
three).

Ordered top to bottom, today:

1. **Your hike** — a link to the hike picker, or a prompt to start one
2. **Contribute** — report a problem, a moderator's queue (moderators only), and a
   hiker's own stuck/failed reports with retry or delete
3. **You** — trail name, reporter type, account sign-in/out
4. **The map** — background source, map style, night-hike red-light mode, detail
   level, which waypoint types show, roads & walkability (*Later*)
5. **Display** — theme, units
6. **Safety & privacy** — use-my-location, wrong-way alert (*Later*), hide my name
   (*Later*), and the locked notice that closures and warnings are never hideable
7. **Your data** — last synced + sync, export GPX/GeoJSON, attribution
8. **About this build** — version, commit, build time, copy-build-details
9. **Report a bug** — four linked GitHub issue forms, plus the in-app
   app-failure report above them ([APP_FAILURE_REPORTS.md](APP_FAILURE_REPORTS.md))
10. **Downloads** — one footer link to the download window

Every section already shares the same `settings__group` / `settings__heading`
markup — [WIREFRAMES.md](../WIREFRAMES.md) §10's own five groups, still visible in
the class names, plus the three sections built after that wireframe was written.
So the content is not undifferentiated; it is differentiated into ten pieces and
then laid end to end with nothing to move between them except scrolling. **That is
the whole defect: grouping without navigation.**

## What to call it — a decision this repo has taken seriously before

[VOLUNTEERING.md](VOLUNTEERING.md) treated its own tab's name as a real design
question rather than a label, scored four rejected candidates against `Volunteer`,
and recorded the argument so it would not be reopened from scratch. The same
treatment, for this tab:

| Candidate | The case for | Why it loses |
|---|---|---|
| **More** (current) | No relearning cost — every hiker who has opened the app once already knows where it is. Honestly admits to being "everything that is not the map," which today is still roughly true. | The honesty is the problem. It gives a first-time hiker no prediction of what is behind it, and a tab with no identity of its own has nothing to push back with when a tenth section gets added — which is most of how this screen reached 995 lines in the first place. |
| **Settings** ✅ | [WIREFRAMES.md](../WIREFRAMES.md) §10 has called this screen "Settings" internally since it was first wireframed — the shipped label disagrees with this repo's own design doc, not the other way round. Seven of the ten sections above (`You`, `The map`, `Display`, `Safety & privacy`, `Your data`, `About this build`, and the reference half of `Report a bug`) are exactly what this word already means on both phone platforms. | Undersells `Your hike`, `Contribute`, and the support links in `Report a bug` — three of ten sections that are actions or reference material, not preferences. |
| **You** / **Profile** | Centers the one thing here that is genuinely personal. | A worse mismatch than `Settings`, in the other direction: map display, safety toggles, data export and About have nothing to do with "you" as a person. |
| **Other** / **Everything else** | Fully honest about being a catch-all. | Reads worse than `More` for the same honesty — a hiker is no more likely to open a tab that admits to being leftovers. |

**Recommendation: `Settings`.** The objection that it undersells three sections is
real, but those three already take the shape every Settings screen on both major
phone platforms uses — an account or support row or two above the preferences,
reference material below them — so nothing about the *content* needs to change to
fit the word, only the label does. That is the opposite of `Volunteer`'s resolution,
where the fix was to change the screen and keep the word; here the screen (once
sectioned below) already earns the word, so change the word and keep the screen.

This is a recommendation, not a ruling. A maintainer who disagrees should say so on
the issue rather than the rename shipping by default because nobody objected.

## The sections

Four groups, sharing the corridor-download window's own tab-strip component
([`client/src/screens/Tabs.tsx`](../client/src/screens/Tabs.tsx) — already built for
Onboarding and the downloads window: one panel rendered, not three hidden with CSS,
arrow keys move the selection, the WAI-ARIA tabs pattern throughout). This screen
would be a third caller of a component that already exists, not a new one.

| Tab | Carries | Why grouped together |
|---|---|---|
| **You** | Your hike, You, Contribute, What your account has, Taking your data or leaving | Everything about this hiker specifically — who they are on a report, what they are walking, what they have already reported. The last of those arrived with [#894](https://github.com/OurHike/OurHike/issues/894) and is a deliberate placement rather than a spare slot: it reports what has reached the hiker's *account*, so it sits under the account row and the sign-out button, where somebody asking "what happens to my things" is already looking. It is emphatically **not** in *About* beside `Your data`, whose "Last synced" is the published conditions bucket — a different clock, and two rows reading as one number is the confusion that section exists to prevent. *Taking your data or leaving* ([#895](https://github.com/OurHike/OurHike/issues/895)) sits last, below both — export and delete from one screen, which is what that issue asks for, and the irreversible control furthest from the thumb that opened the tab. Both sections are signed-in only. |
| **Map & Display** | The map, Display | Everything about how the app looks and draws, map-specific or not. `UX_CUSTOMIZATION.md` keeps these as two data models (`MapDisplaySettings`, and the app-wide `theme` + `unit_system`) for a real reason — they change independently — but that is a reason to keep two data models, not two tabs. A hiker asking "how do I make this look right" does not care which model answers. |
| **Safety & Privacy** | Safety & privacy | Kept alone deliberately, not folded into Map & Display. [CLAUDE.md](../CLAUDE.md) names four ways this app can hurt somebody, and the location toggle and the wrong-way alert are two of the controls that answer them — a control worth finding quickly should not share a tab with detail-level radio buttons. |
| **About** | Your data, About this build, Report a bug, Downloads | Reference material and rarely-touched actions — things a hiker consults, not things a hiker sets. **One row here is neither**, and it arrived after this table was written: the app-failure report at the top of `Report a bug` ([APP_FAILURE_REPORTS.md](APP_FAILURE_REPORTS.md)) is a hiker saying this software failed them out on the trail, which is not reference material and is not rarely-touched by the person doing it. It sits here because `Report a bug` does; whether a report about being nearly lost belongs behind the same tab as the attribution list is a fair question this doc does not settle. |

**Row order inside each tab matters less than tab membership, and is deliberately
not pinned down further here** — `UX_CUSTOMIZATION.md` made the same call about its
own open questions repeatedly ("worth deciding once there's a real settings screen
in front of you"), and the same reasoning applies to exact row order inside one.

## What this does not decide

Two overlaps this doc noticed while auditing the current screen, and is
deliberately not resolving:

- **`Your hike`'s natural home may move.** [features/HIKE_PLANNING.md](HIKE_PLANNING.md)'s
  build (V2_PLAN.md group T) is the `Plan` tab's whole subject. Once it ships, a
  hiker's current hike may belong there more than here. Worth revisiting once group
  T lands, not before — moving it now would relocate something into a tab that does
  not yet have anywhere to put it.
- **`Contribute`'s report-a-problem entry sits next to where the `Volunteer` tab's
  own condition-nudge surface is about to ship.** **#759 — The Volunteer tab and the
  contribution toggle — which is where DATA_NUDGES.md finally ships** puts an opt-in,
  passive condition-confirmation flow in the new `Volunteer` tab — a different
  mechanism (a nudge vs. a filed `Report`) reaching a similar place for a similar
  reason. Whoever builds #759 should look at this tab's `Contribute` section before
  deciding where the seam between the two should read; that decision does not belong
  in this doc.

Neither blocks the work below. Both are notes for whoever touches the neighboring
tabs next, in the spirit of saying so rather than staying silent about a gap noticed
in passing.

## Build order

Two pieces, independent of each other but touching the same file
(`client/src/chrome/tabs.ts`), so [BRANCHING.md](../BRANCHING.md) §3's stacking
allowance covers doing both on one branch if whoever picks this up prefers that:

1. **Reorganize into sections** — the `Tabs` shell, the four groupings above,
   `More.tsx` / `Settings.tsx` / `AboutBuild.tsx` / `ReportBug.tsx` /
   `DownloadsLink.tsx` redistributed under them with no behavior change to any
   individual control. This is the fix for "too long."
2. **Rename the tab** — `client/src/chrome/tabs.ts`'s `more` entry, label only; the
   `id` can stay `more` since nothing outside that file reads the label as a value.
