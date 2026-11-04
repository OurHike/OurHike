# Handoff: OurHike structure inventory

## Overview

A roving-volunteer programme and the module that runs it: a club's volunteers walk the parts
of the trail the data is thinnest on and log every built thing they pass — bridge, puncheon,
shelter, privy, campsite, water source, blaze, sign, kiosk, parking, steps, and the small
drainage works — where it is and what shape it is in. The club's own chain reviews; the
club keeps the inventory, the history and the exports.

Thirty-six artboards across five surfaces: six enrolment screens, eleven field screens, one
upload screen, four web screens for the club console, twelve field cards with a printable
plate sheet, and the icon set.

The spine is one idea: **a record is a dated observation, never an edit.** Nothing is
overwritten, so nobody has to adjudicate; two volunteers on the same bridge is two rows.
Every screen assumes that, and the review screens exist to accept rows, not to merge truth.

Read `SPEC.md` in this folder before writing code — it carries the decisions, the six
conflicts with the current codebase (two are questions for the maintainer, four have a
resolution written down), the data model, the permission table, and the packaging answer
("a second front door"). This README is the map; `SPEC.md` is the argument; `ISSUES.md` is
the phased list; `KICKOFF.md` is the prompt.

## About the design files

The artboards are **design references created in HTML** — prototypes showing intended look
and behaviour, not production code to copy. The task is to **recreate them inside the OurHike
codebase's existing environment**: React + TypeScript on the client (`client/src/`), Astro
for the marketing site (`site/src/`), FastAPI + SQLAlchemy + Postgres on the backend
(`backend/app/`), Supabase Auth for identity, Cloudflare R2 for photos.

Use the repo's established patterns. Specifically:
- The phone screens belong in a new `client/src/survey/` tree, as the second Vite entry
  `SPEC.md` §Packaging describes; they import `client/src/lib/*` and never copy it.
- The web screens belong in `client/src/org/screens/` under a new `/org/:slug/inventory`
  route, the same popstate router (`client/src/lib/orgRoute.ts`) and `?page=` grammar the
  volunteers console uses.
- New tables need one Alembic revision **with `RLS_TABLES` and `rls_statements()` in it**
  (`backend/alembic/versions/b3d1c7a94e02_enable_row_level_security.py` is the model;
  `test_migration_rls.py` fails the build otherwise).
- The landing page belongs in `site/src/pages/for-orgs/survey.astro`.

## Fidelity

**High fidelity.** Final copy, hierarchy, spacing and interaction on every phone screen;
final structure on the web screens. Recreate with the design system's tokens rather than
transcribing hex values — every colour in these files is one of the token values in
`client/src/design-system/tokens/colors.css` (the hexes are listed under Design tokens so a
reviewer can match them).

Three deliberate exceptions, all in `SPEC.md`'s Known gaps:
- **Maps are schematic** except the readings grid on 2c, which is built exactly as drawn (a
  plain grid, a scale bar, a north arrow, no basemap, no trail line — by design).
- **Numbers and names are sample data.** Section names, counts, dates, "Pat R." and
  "[YOUR NAME]" are density, not facts.
- **Three of the 79 plates exist.** Sign, Blaze and Steps open on finished art (real
  photographs in the house treatment, credited); every other plate is a "photo wanted"
  tile on purpose. `plates_manifest.json` and `tools/fetch_plates.py` are how the rest get
  made; a drawing never stands in for a photograph.

## Screens

Codes match the canvas titles and the walkthrough. Each `.dc.html` is one artboard.

### 1 · Enrol, once, at home (phone, 390×844)
| Code | Screen | File | What it does |
| --- | --- | --- | --- |
| 1a | Join the survey | `Main.dc.html` | Three steps and one button. Club name and mark are a slot the club fills; "Already enrolled? Open my stretch" |
| 1b | Sign the waiver | `Waiver.dc.html` | The club's text word for word, a checkbox, a typed name, the version and date recorded |
| 1e | Training: the field guide | `Lessons.dc.html` | Twelve types in a grid; "Start here: trail eyes"; progress "1 of 13 done"; an optional ATC video link |
| 1c | Training: call it | `Training.dc.html` | The practice question is the real Condition screen's; feedback quotes the source |
| 1d | Roaming opportunities | `PickStretch.dc.html` | Map coloured by need, three nearest places pinned, swipeable cards, "Claim it for a day" up to 14 days ahead, "Walk it anyway" when claimed |
| 1g | Area detail | `StretchDetail.dc.html` | The area, its parking, known structures, a day picker for the claim |

### 2 · Log a structure (phone)
| Code | Screen | File | What it does |
| --- | --- | --- | --- |
| 2a | Where I'm walking | `Stretch.dc.html` | Map strip of the area, structures as dots, "2 to upload", "Structures here" |
| 2b | What is it? | `Type.dc.html` | Twelve tiles in the map's glyph style; everything else is Something else |
| 2c | Where is it? | `Location.dc.html` | Readings populate a grid as they arrive: dots, the accuracy circle, a 50 ft bar, N; "23 readings · 38 s"; "Within 14 ft ✓ Good, you can save"; chips only for what the platform knows; "Can't stand at it? Mark it from here" |
| 2i | Is this the same one? | `SameOne.dc.html` | Asked when two fixes' error circles overlap, with the overlap drawn (±14 / ±50, 60 ft apart); swipeable photo strip |
| 2d | Photos | `Photos.dc.html` | Two shots always, one or two suggested per type, all optional; "No people in the frame, please." |
| 2e | About how long? | `Dimensions.dc.html` | Four buckets, railings yes/no, "Measured it? Enter the number", "Skip this"; "4 of 6 · optional" |
| 2f | What shape is it in? | `Condition.dc.html` | The type's reminder card (one line, the rule, a link to the full card), Good/Fair/Poor/Unsafe with definitions, problem chips |
| 2g | What should happen? | `Repair.dc.html` | Leave it, Minor, Major, Replace, Take it out; timing; "The Local Chair decides what happens and when." |
| 2h | Check and save | `Check.dc.html` | Chips, no sentences; "Not saved yet. Tap a line to change it." |
| 2j | A structure's history | `Structure.dc.html` | Everyone's visits, read-only; `AT-NY-BR-014`; "minor repair, next year" |
| 2k | Finish this walk | `Finish.dc.html` | Stopped early: the walked part from the track, a handle to place where you stopped |

### 3 · Upload, then the club reviews
| Code | Screen | File | What it does |
| --- | --- | --- | --- |
| 3a | Waiting to upload | `Outbox.dc.html` (phone) | "9 records have been waiting a day"; "No signal here"; cellular toggle; "Try now"; the reminder on open |
| 3b | Review | `ReviewQueue.dc.html` (web, 1280×900, fluid) | Accept / Send back / Merge / Not ours; "Sent back · 2"; Area filter; the estimate rendered as an estimate |
| 3c | Coverage and priority areas | `Coverage.dc.html` (web) | Trail picker, Needs a walk / Everything on it, "3 of 22 areas · 19 covered, hidden"; the rule and its thresholds |
| 3d | Inventory and history | `Inventory.dc.html` (web) | Worst first, Area column, a history per structure, the Chair's note, exports |
| 3e | Review map | `ReviewMap.dc.html` (web) | Every record as a dot by review status, the Unsafe ones called out, same records as the list |

### 4 · Field cards (phone) and the plate sheet
| Code | File | Opens on |
| --- | --- | --- |
| 4a–4l | `Guide.dc.html` (Bridge), `GuidePuncheon`, `GuideShelter`, `GuidePrivy`, `GuideCampsite`, `GuideWater`, `GuideBlaze`, `GuideSign`, `GuideKiosk`, `GuideParking`, `GuideSteps`, `GuideOther` | One photograph at a time with its caption and credit, thumbnails to jump, "Unsafe means", the one rule, the sources. Sign, Blaze and Steps open on real plates; the rest show the "photo wanted" tile |
| 4m | `FieldPlates.dc.html` (web, 1280 wide, tall) | Every plate on one printable sheet |

### 5 · Icons
| 5 | `Icons.dc.html` | Twelve structure glyphs: six are the map's own POI pins, six drawn to the same rules |

The same card is shown in training (1e → the card) and on the trail (2f's "Bridge card" link
opens 4a), so there is one component and one content file.

## Interactions and behaviour

- **One question per screen.** Each field step is a screen with a progress line
  ("5 of 6 · Works offline") and "Save for later" in the header; Back is always the
  previous step. Nothing scrolls to find what was missed.
- **Every field screen works offline.** Save writes to the outbox; the Stretch screen's
  "2 to upload" is the queue length; the Outbox screen is the queue.
- **Location.** Sampling starts on entry and plots as it goes; the verdict line comes first
  ("Within 14 ft ✓ Good, you can save"); the secondary button marks the point from where the
  volunteer stands when they cannot reach the structure, and records `fix_source`.
- **Same one?** Appears only when the new fix's error circle overlaps a known structure's;
  the volunteer's answer sets `same_as_structure_id` and nothing is merged on the phone.
- **Unsafe** selects the Report a Problem hand-off on Check and save (one tap, no
  re-typing), and is first in the review queue.
- **Claims** pick a day, show as "Claimed by Pat R. until Sat Nov 14 · you can still walk
  it" to others, and clear on their own.
- **Review** is four verbs and a note; "Send back" returns the record to the volunteer with
  the note on their Structure screen.
- **Motion.** Design-system motion only; no bounce. **Hit targets** 44–60 px on the phone.
- **Responsive.** Phone screens are a fixed 390 design; web screens reflow with
  `flex-wrap` and `minmax(0,1fr)` and work at phone width.

## State that is really UI state

| State | Purpose |
| --- | --- |
| `step` | Which of the six field steps is showing; app state, not the URL |
| `draft` | The observation being built, persisted to the outbox on "Save for later" |
| `readings[]` | The GPS samples, plotted live, kept whole in the record |
| `sameAs` | The answer to 2i |
| `cellularUpload` | The Outbox toggle, default on, persisted per device |
| `claimDay` | The day picked on 1g |
| `reviewFilter`, `trail`, `area` | Web filters, in the query string like the volunteers console's `?page=` |

Everything else is server state through the endpoints `SPEC.md` lists.

## Design tokens

Do not transcribe values. Every colour in these files is one of
`client/src/design-system/tokens/colors.css`'s; the ones used, for matching:

- **Paper** `#f7f3e9` (page), `#fffdf7` (surface, headers), `#ffffff` (cards)
- **Stone** `#122016` (display text), `#2b2620` (body), `#5a5346` (secondary), `#8a8271`
  (tertiary), `#c3baa4` (borders, strong), `#e4ddca` (borders, light)
- **Greens** `#355c3a` (accent, buttons), `#47784b`, `#284029` (on sage), `#e3ecda` (sage,
  callouts), `#c7dabd` (map ground)
- **Blaze orange** `#c1611a`, `#994e15` (Unsafe, and the saved point on the readings map)
- **Yellow** `#d69a2d` (under-3-records), **Blue** `#1c6ea4` (sent back, "you", claims)
- **Type** Bitter 600/700 for headings, Public Sans for everything else, IBM Plex Mono for
  miles, counts and anything machine-ish — the same three the design system self-hosts
- **Radius** 12–16 px on cards and buttons, 999 px pills on chips; **spacing** on the 4 px
  grid, 20 px page gutter on the phone

The one prop every artboard exposes is `accent` (the club's colour, default `#355c3a`);
`clubName` on the web screens. They are the whitelabel levers.

## Assets

- **Icons:** twelve glyphs drawn as `<path>` in a 1×1 viewBox in the map pins' own style
  (`Icons.dc.html` carries all twelve; `client/src/survey/fieldGuide.ts` should import the
  six that exist in the map's sheet and add the six new ones). No icon font, no emoji.
- **Plates:** `plates/sign_good.jpg`, `plates/blaze_good.jpg`, `plates/steps_good.jpg` in
  this folder, 660×660, the house treatment applied to
  `client/src/design-system/assets/photos/heroes/14-jefferson-rock.jpg` (Harpers Ferry
  NPS · CC BY 2.0) and `22-blaze-in-snow.jpg` (Shenandoah NPS · public domain) — both
  already in the repo's licence-checked pool (`client/src/lib/heroPhotos.ts`). **The credit
  line under a plate must stay**; CC BY asks for it and the pool renders it.
- **The house treatment** is `tools/duotone.py` (Pillow + NumPy): square crop, ink
  `#2b2620` on paper `#fffdf7`, local contrast, a soft vignette. Every plate goes through it.
- **The rest of the plates** come from `plates_manifest.json` through `tools/fetch_plates.py`
  (fetch → contact sheet → approve by eye → treat), run where the network is open. Its
  treat stage writes `plates/<type>/<n>.jpg` and `plates.ts` with a credit per plate, and
  prints what is still wanted from the club.
- **"Photo wanted" tiles** are what a card shows for a plate with no photograph: the
  type's glyph and the caption on paper. They are the honest state, not a placeholder to
  hide.
- **The OurHike mark** is drawn inline in the web screens as a dashed "logo" slot: the
  club's mark goes there when the branding block exists, the OurHike mark from
  `site/src/components/Mark.astro` until then.

## Files

**In this folder, to commit** (text and the two small plates; about 250 KB):
- `copy/*.txt` — each of the 36 screens' rendered text, captured from the artboards in a
  real browser, one file per screen, for the "does what shipped say what was asked for"
  check. Sentences, not layout: a question about spacing is not answerable from here.

**Beside this folder in the handoff bundle, not committed** (`design-references/`, about
1.5 MB; the maintainer holds them, the same rule as the org-onboarding handoff):
- `project/*.dc.html` — the 36 artboards as source, `project/canvas.json` their layout.
  They render inside the canvas, not from a file on disk (each expects the canvas's
  `support.js`); the canvas link is where to look at one.
- `walkthrough/index.html` — every screen in order, with the note beside each.
  Self-contained: open it in any browser.

**Content and tools:**
- `fieldGuide.json` — the twelve cards as data: `name`, `good`, `checks` (the problem chips,
  in order), `unsafe`, `rule`, `sources`. This is `client/src/survey/fieldGuide.ts`'s
  content, verbatim; every line of it is from ATC or NYNJTC and the `sources` field says
  which. Do not add a line to a card without a source.
- `icons.json` — the twelve glyphs as `d` paths in a 1×1 viewBox, with which six are the
  map's existing pins.
- `plates/` — the three finished plates
- `plates_manifest.json` — licensed candidate photographs for the 79 plates (Wikimedia
  Commons, NPS, Forest Service), each with its page, author, licence, what it shows and a
  confidence; rows with `rank: 0` are the plates no collection had
- `tools/duotone.py` — the house treatment; `tools/fetch_plates.py` — fetch, licence
  re-check, contact sheet, approve, treat, registry
- `SPEC.md` · `ISSUES.md` · `KICKOFF.md`

**Not here, deliberately:** the two Claude Docs (the brief and the Field Guide with its
"What the sources don't say" section) — the maintainer holds them; `fieldGuide.json` is the
part of the Field Guide the code needs.
