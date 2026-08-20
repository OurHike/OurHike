# OurHike — What the Map Screen Owes the Map (#206)

Companion to [../WIREFRAMES.md](../WIREFRAMES.md) §1 (which draws this screen),
[../WEBSITE.md](../WEBSITE.md) §6 (which settled the desktop half),
[../OurHikeValues.md](../OurHikeValues.md) #4 and #9, and
[HIKER_SAFETY.md](HIKER_SAFETY.md).

**#206 — Design spike: carry the brand on a phone without spending map pixels**
asked one question and correctly suspected it was the small version of a bigger
one: *what does the phone map screen owe the map, and what does it owe
everything else?* This is the written answer that issue asked for. It is a doc,
not code, and its conclusion is mostly that the code already has this right —
which is itself worth writing down, because the alternative is every future
session re-opening the question with a CSS tweak.

---

## 1. The inventory, measured

Top to bottom on a phone, with where each number comes from
(`client/src/chrome/chrome.css` unless said otherwise):

| band | height | measured how |
|---|---|---|
| Status strip | ~19px | 11px mono line + 4px padding × 2 |
| Alerts (closure / warning / advisory) | 0 when clear | conditional block, `role="alert"` |
| Header | ~54px | the two 38px buttons + 8px padding × 2; the identity column (11px eyebrow + 17px position line) fits inside |
| Elevation ribbon | 54px | fixed, WIREFRAMES.md §1.3 |
| Waypoint lanes | 57px | 3 lanes × 19px, WIREFRAMES.md §1.4 |
| **Map canvas** | what is left | — |
| Credit strip | ~17px | 10px line + 2px padding × 2 + border, own row below the canvas |
| Tab bar | ~48px | 44px touch floor + border; plus the home-indicator inset on notched phones |

Fixed chrome ≈ **249px**. On a 375×667 phone that is 37% of the screen and the
map gets ~63%; on a 390×844 it is 29% and the map gets ~71%. (Reasoned from the
constants above, not screenshotted — the constants are the spec, and a
screenshot would only re-measure them.)

## 2. The standard a band has to meet

CLAUDE.md names the four ways this app can hurt somebody: lost, out of water,
in front of something dangerous, unable to get off the trail quickly. The
mid-walk read of this screen is a **glance** — phone out, read, phone away,
attention back on footing. Chrome earns its pixels by answering one of the four
inside that glance; chrome that doesn't is spending map a hiker may be reading
terrain from.

Held to that standard, band by band:

- **Status strip — earns it.** GPS state and sync age are the trust signals:
  they are what say whether everything else on the screen may be believed
  (value #4). A trust signal behind a gesture is a trust signal unread.
- **Alerts — earn it absolutely**, and cost nothing when clear. "In front of
  something dangerous" is their whole subject, and #232 placed them under the
  sync age deliberately so the two are read together.
- **Header — earns it.** The mile and direction are the "lost" answer. The two
  38px buttons are reach, not glance — but controls demoted to a gesture are
  controls nobody discovers, and 38px inside a 44px target is already the
  floor. See §5 for the one measurable question here.
- **Ribbon + lanes — earn their 111px.** They are the push-on-or-stop
  instrument, the reason elevation was promoted into MVP (FEATURES.md), and
  the only band answering "do I beat the dark". This is the most chrome any
  band spends and the most defensible spend on the screen.
- **Credit strip — owed, not earned.** ODbL attribution is a licence
  condition. It used to overlay the canvas and was moved to its own row on
  purpose: the overlay met the condition only where the text happened not to
  land under a control (`chrome.css`'s own comment above `.map-attribution`
  carries the full reasoning). It cannot share a row and it cannot go; ~17px
  is the price of drawing OSM's data at all.
- **Tab bar — earns it.** The way back from everywhere; navigation that
  auto-hides is a trap. Its 44px floor is WCAG's, not ours to shave.

## 3. The brand: the icon is the ceiling, not the floor

The wordmark's home is the desktop sidebar's foot and the website
(WEBSITE.md §6 — built). On the phone, #207 put the 24px icon alone at the tab
bar's left, and this doc's finding is that **that is the end of the brand's
claim on this screen**:

- **Keep the icon.** #206 legitimately contemplated taking it back out if the
  map won the argument — but the icon spends *tab-bar width*, not map pixels.
  At 375px the three tabs still get ~111px each against their 44px floor, so
  the map argument never reaches it, and a phone handed to another hiker
  ("what app is this?") gets its answer from the one corner that was free.
- **Nothing more, ever, on this screen.** No wordmark, no watermark over the
  canvas, no splash element. A watermark spends terrain somebody may be
  reading (WEBSITE.md §6 rejected it for the desktop for exactly that reason,
  with more room to spare), and value #9's "get out of the way once it's
  helped" cuts the same direction. The brand's job mid-walk is to be absent.

## 4. Reclaims considered, and why each is declined

Three came up while writing this; recording the rejections is most of this
doc's value, since each will look like an easy win to whoever finds it next.

**Merge the status strip into the header** (~19px back, one band fewer).
Declined: the sync age sits directly above the alert lines because the two are
read together — a closure line is only as good as the age of the data behind
it, and #232 placed that adjacency deliberately. The merge would also fold two
ARIA roles into one region. Nineteen pixels is ~3% of a small phone's screen;
the adjacency is load-bearing.

**Auto-hide chrome while moving** (up to ~180px back mid-walk). Declined: the
glance is the constraint. A hide/show transition plus visual reacquisition
spends a large fraction of a glance that lasts a few seconds — and gloved,
one-handed use (#105's subject) makes any recovery gesture expensive exactly
when the hiker can least afford it. `@unvalidated`: the glance duration is
folklore, not an OurHike measurement — #105/#106 field testing is what would
settle it, and this doc's declines should be re-read against what they find.

**Thin the ribbon + lanes** (the biggest band). Declined without new evidence:
it is the band doing the most safety work per pixel, and ELEVATION_PROFILE.md
derived its 10-mile window and the lanes' 1.5%-of-window clustering as a piece
— a shorter band re-opens both derivations, not just a CSS number. Shrinking
it to buy generic map is trading a specific answer for an unspecific one.

## 5. What field testing should actually measure (#105, #106)

The issue paired itself with the outdoor-usability pass, and these are the
questions a trail answers that a desk cannot:

1. **How long a mid-walk glance really lasts**, under glare, moving — the
   number every decline in §4 leans on.
2. **Whether the header's two buttons are used mid-walk at all.** If search
   and legend are only ever opened at rest, the header could thin to one
   button on some future evidence — that is the single candidate reclaim this
   doc leaves open.
3. **Whether the lanes are read while moving** or only at stops — which
   decides whether their 57px is a glance instrument or a rest instrument,
   and therefore what may ever be traded against it.

None of these unblock anything today; they are here so the field pass collects
them rather than impressions.

---

*Written 2026-08-20, closing the spike half of #206. The desktop half was
settled by WEBSITE.md §6 and built (`src/desktop.css`); the phone half is this
doc; no implementation issues fall out of it, because the finding is that the
shipped screen already holds the line it should.*
