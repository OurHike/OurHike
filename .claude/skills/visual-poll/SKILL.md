---
name: visual-poll
description: Show the maintainer what you mean before you build it, and keep showing it - a poll about anything a hiker sees carries a picture (a rendered mock or a screenshot sent to the side panel and named in the question) before any code, after the first build and at every fork. Use whenever a decision is going to the maintainer, whenever a screen is about to change shape, and when a poll came back with the hook's paragraph saying it carried no picture. Covers the three kinds of picture a session can make here and what each cannot show, the loop, the one-line answer for a choice with nothing to draw, and what the hook does and does not check.
user-invocable: true
---

# Show the maintainer what you mean, then ask

The maintainer, 2026-09-17: *"I need you to start polling me with more questions with
more visuals. Actual screenshots or wireframes. I'm getting questions, but we aren't
communicating well. The visuals really help me understand what you plan to do."* And:
*"This shouldn't just happen once in the session either, we are doing a constant
feedback loop."*

That is a bug report about how a session asks, and it has the same shape as the one
[`plain-language/SKILL.md`](../plain-language/SKILL.md) opens with: the thinking is
fine and the surface the maintainer reads is not.
[CLAUDE.md](../../../CLAUDE.md)'s "Be concise in chat, and never bury a question" put
the question in the poll tool (`AskUserQuestion`). What it never said is what the poll
has to *show*, and "badge or ring?" about a card the maintainer has never seen drawn is
the words-only failure again, one tool over.

CLAUDE.md still wins wherever this file could be read as disagreeing with it. Its rule
that routine judgment calls are yours to make is not touched here: this file is about
how to ask, not a licence to ask more.

## What was decided, and what was offered instead

Poll, 2026-09-17, on **#1566 — A session's questions to the maintainer carry no
wireframe or screenshot, so the plan cannot be seen from the words**, put with a
wireframe page of the proposal (7,486 bytes of hand-written HTML, rendered in the side
panel) and two real frames from this sandbox's camera:

| question | chosen | offered and not taken |
|---|---|---|
| the default picture | a rendered HTML mock in the side panel | a drawing inside the poll; a screenshot sent first; a table or diagram when there is no screen |
| how hard the repository holds it | let a picture-less poll through, tell the session afterwards | refuse the poll; prose only |
| the reminder | one line at session start, resume and compaction | one line on every prompt; none |

The alternatives are written down so the next reader knows they were considered, not
so they get re-argued. The two not chosen as the default are still the fallbacks below:
a screenshot when the question is about a screen that already exists, a drawing inside
the poll when there is no side panel to send to.

## The one rule

**A poll carries a picture, and the question names it.**

Three things count, and the hook (last section) accepts any of them:

1. **A file sent to the side panel first**, named in the question — `water-card-mock.html`,
   `legend.png`. The default. The name is not decoration: it is what tells the
   maintainer which panel to look at, the same reason a `## Screenshot` section says
   which shot to look at.
2. **A `preview` on an option** — a drawing inside the poll. The fallback for a session
   with no side panel, or for a change so small that a box and an arrow say it.
3. **The line `No visual: <why>`** in the question — the honest answer for a choice with
   nothing to draw, in the same words the pull request template's `## Screenshot`
   section accepts. The reason is the answer; a bare `No visual:` is the section left
   blank, and the hook reads it as blank.

A picture with no question is a demo. A question with no picture is the bug report at
the top of this file. Both halves, every time.

## When — the loop, not the once

The maintainer's second sentence is the one this section exists for. Three checkpoints,
and the third already existed:

1. **Before any code.** The plan, drawn: one frame per option, A/B/C, and the screen as
   it stands beside them when it already exists. Poll. Nothing about the screen gets
   built until this comes back.
2. **After the first build.** A screenshot of what got built, sent beside the mock the
   maintainer chose. Poll: does it match, and what moves. This is the checkpoint a
   session skips when it is going well, and it is the one the maintainer asked for.
3. **Before the pull request.** The recipe re-photographs the screen in CI and
   `## Screenshot` names the difference —
   [`pr-screenshot/SKILL.md`](../pr-screenshot/SKILL.md), unchanged. Poll only if a
   fork is still open.

**And at every fork in between.** A screen that changes shape midway goes back to
checkpoint 1 for that screen. A choice that turns up while building — where a control
sits, what a state says, which of two layouts survives a small phone — is a fork if the
two answers lead to different work, and it goes to the maintainer drawn.

**What is not a fork.** A name, an ordering the code already implies, anything CLAUDE.md
calls a routine judgment call. Make it, say in the pull request that you made it, move
on. A poll on every decision is the words-only failure's mirror image: the maintainer
stops reading them.

**Two things about timing**, because a poll blocks until it is answered and the
maintainer may be away:

- Do everything that does not depend on the answer first, then ask. The research, the
  issue claim, the mock itself — none of that waits on the poll.
- One poll, several questions, rather than several polls. The tool takes four; a
  decision that needs five is two decisions.

**The night shift never polls.** `night-shift/SKILL.md`: "nothing here waits for an
answer." An unattended session that reaches a fork a maintainer should see stops, says
so on the issue with the pictures it would have polled with, and takes the next issue.
Everything below is for a session with somebody on the other end.

## Picture 1 — a rendered mock, the default

A mock is a page of the screen as it would be, drawn in the design system's own
tokens, sent to the side panel. It is a drawing: nothing in it was photographed, and
its caption says so.

1. **Write it to the scratchpad**, never the repository. A mock is a working file. Committing
   one is the mistake committing a screenshot was (#984, replaced by #988), and the same
   reason applies — bytes nobody can retract.
2. **One phone frame per option**, side by side, labelled A, B, C to match the poll's
   options in order. 390 px wide — `PHONE` in
   [`client/scripts/screenshot.mjs`](../../../client/scripts/screenshot.mjs), the phone
   WIREFRAMES.md sizes against — and 375 px when the question is whether something fits
   on the smallest phone (`PHONE_SMALL`, the #1374 room audit).
3. **Colours, type and spacing from
   [`.claude/OurHike Design System/tokens/`](../../OurHike%20Design%20System/tokens/)** —
   `colors.css`, `typography.css`, `spacing.css`, `effects.css`, 4 KB each. Copy the
   variables the page uses into its own `<style>`; the page must not fetch anything to
   render. The fonts (Bitter, Public Sans, IBM Plex Mono) are Google Fonts substitutes
   per the design system's readme, so declare a system fallback after each.
4. **Placeholders, not claims.** "Reported 9 days ago" in a mock is a number somebody
   made up to fill a line, and the caption says so, because a reader who cannot tell a
   placeholder from a measurement has been handed a claim nobody stands behind —
   CLAUDE.md's first section, applied to a drawing.
5. **Send it**: `SendUserFile` with `display: "render"`, a caption saying what is drawn
   and what is real, then the poll, naming the file in the question. Sent this way on
   2026-09-17 (the wireframe page and two frames), the page rendered in the maintainer's
   side panel and the poll was answered against it.

Minutes to make. What it cannot show: real data, real spacing quirks, anything the
running app does that a drawing does not — which is why checkpoint 2 exists.

## Picture 2 — a screenshot of the screen as it stands

For a question about a screen that already exists, the "before" is a photograph, not a
drawing. `pr-screenshot/SKILL.md`'s "Taking one" is the by-hand route:

```
cd client
node scripts/screenshot.mjs <name>
```

That reaches the screen the app opens on past first run. For a screen further in, drive
an existing recipe through `capture()` from a scratch runner — this is what "add the taps
you need to a copy of the script" means in practice:

```js
// <scratchpad>/shoot.mjs — one frame, driven by an existing recipe
import { capture, PHONE, PHONE_SMALL, CAPTURE_SCALE, DEFAULT_WAIT_MS } from '<repo>/client/scripts/screenshot.mjs'

const recipe = await import('<repo>/client/preview-shots/legend.mjs')
await capture({
  name: 'legend', outDir: '<scratchpad>/shots', url: undefined, dist: false,
  skipEntry: !recipe.entry, waitMs: recipe.wait ?? DEFAULT_WAIT_MS, scale: CAPTURE_SCALE,
  fullPage: false, viewport: recipe.small ? PHONE_SMALL : PHONE, drive: recipe.default,
})
```

Run it from `client/` (`cd client && node <scratchpad>/shoot.mjs`): `capture()` starts
the dev server from there, and a recipe's fixtures are client-relative. Measured
2026-09-18, this sandbox, dev server, two frames (the standing trail screen and the
legend sheet): 47.8 s wall, 52,677 and 105,867 bytes at 390×844 and 2×.

What the frame shows, and does not: chrome, cards, sheets and pickers render; the map
canvas is paper, because the corridor archive lives in IndexedDB and nothing downloads
it here (`screenshot.mjs`'s header, measured 2026-08-25, and the two frames above show
the same). Say that in the caption rather than letting the maintainer wonder where the
trail went. `--url` at a deployed preview does not work from a sandbox, for the reason
the same header measures; a session that needs real tiles under a question asks the
maintainer for a frame, and says so.

**Look at the whole frame before sending it.** The four things that never appear in a
shot — a signed-in account, anybody's reports or photos, a dispersed campsite at a
readable zoom, a real location fix — are `pr-screenshot/SKILL.md`'s list and apply
unchanged; a frame in the side panel is a publication to one person rather than to a
pull request, and the account and location halves are the ones a sandbox frame can
actually carry.

## Picture 3 — a drawing inside the poll, the fallback

`AskUserQuestion` takes a `preview` on each option, shown when that option is focused:
markdown, and a fenced block keeps a box drawing's columns. Use it when there is no side
panel to send to — a terminal session — or when the whole difference is one row moving
and a frame would be theatre. Under forty columns, so it survives a narrow pane:

```
 A · text line              B · ring on the pin
┌────────────────────┐     ┌────────────────────┐
│ ◉ Spring · 0.4 mi  │     │ (◉) Spring · 0.4 mi│
│ Flowing · 9 d ago  │     │  ^ amber ring      │
│ [Report]  [Go]     │     │ Flowing            │
└────────────────────┘     └────────────────────┘
```

The box-drawing style is the one
[`features/HIKE_PLANNING.md`](../../../features/HIKE_PLANNING.md) already uses for the
timeline. Whether a preview rendered on the maintainer's side is not yet confirmed from
their seat — the 2026-09-17 poll carried one on every option and the maintainer chose
the rendered mock, which the option itself described as "like the one just sent". Until
somebody says, treat a preview as the fallback it was chosen to be, not the default.

## No screen — the table or the flow

A pipeline or backend choice has no card to draw, and the same rule
`## Screenshot` applies to a change with no UI applies here: the picture is whatever the
evidence actually is. A before-and-after table of the numbers the choice moves. The
step of a flow that changes, drawn with an arrow at it. Either fits a `preview`; a
table of more than a few rows is better as an `.html` page in the side panel. A choice
that moves no number and no step is the `No visual:` case, and the line says why.

## The poll itself

- **The question names the picture** and says what to look at in it: "See
  `water-card-mock.html`, frames A and B: where should the card show how old a report
  is?"
- **Options match the picture's labels**, in the same order. A reader should not have to
  map "the second one" onto "B".
- **The recommended option goes first**, labelled `(Recommended)`, and its description
  says why in one sentence. The maintainer may disagree; they cannot disagree with a
  reason that was never given.
- **`multiSelect` when the choices are not exclusive.** The 2026-09-17 poll's first
  question was one, and the answer was a single pick, which is information too.
- **`No visual: <why>`** when there is genuinely nothing to draw. It is not for skipping
  the drawing because the drawing is work.

## After the answer

**Write the decision where it lands, dated.** The commit body, the pull request body,
the docstring on the constant it settled — "the maintainer chose a ledger over an
ownership-only fix (poll, 2026-09-17)" is the form, from 22662d6 (Keep a ledger of
community-photo takedowns that outlives the row they were recorded on). A decision that
lives only in the chat transcript is a decision the next session re-asks.

If the session stops before the work does, the decision goes on the issue too, with the
mock or frame it was made against described in a sentence — the same reason a claim
gets released when a branch is abandoned.

## What the hook does, and does not

[`.claude/hooks/visual_poll.py`](../../hooks/visual_poll.py), registered in
[`.claude/settings.json`](../../settings.json), is the maintainer's chosen shape: **let
the poll through, tell the session afterwards.**

- **`check`**, after every `AskUserQuestion`: reads the poll, and when none of the three
  things above is present, hands the session one paragraph of context saying so and
  naming this file. It never blocks and never fails the poll — on unreadable input it
  says nothing. That paragraph arriving is the signal to send a picture before the
  *next* poll, not to re-ask the one that just went out.
- **`remind`**, at session start, resume and compaction: one line, the rule and this
  file's path. Chosen over a line on every prompt.
- **Stateless.** It reads only the poll. It cannot see whether the named file was sent,
  and does not try: the maintainer sees an empty panel and says so, and the hook is a
  reminder rather than a gate.
- **Reasoned, not yet observed.** That the PostToolUse hook fires for
  `AskUserQuestion` with the poll's `questions` under `tool_input` follows from the
  hooks documentation — a matcher is a regex on the tool name, `tool_input` is the
  tool's input object — and has not been seen from inside a session as of 2026-09-18.
  The first session that sees the paragraph in its context should say so on #1566, and
  the docstring in `visual_poll.py` can then stop hedging.
- [`.github/tests/test_visual_poll_hook.py`](../../../.github/tests/test_visual_poll_hook.py)
  holds what counts as a picture, that the check never blocks, and the wiring.

## What this does not change

- **The evidence grades.** A mock's placeholder is a placeholder; a frame's paper canvas
  is paper. Plain is not confident, and a picture can overclaim as easily as a sentence.
- **`pr-screenshot/SKILL.md`.** That is the pull-request end of the same rule and is
  unchanged; this file is the planning end.
- **CLAUDE.md's routine-call rule.** More pictures, not more polls.
- **The night shift**, which does not ask.
