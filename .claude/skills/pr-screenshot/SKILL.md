---
name: pr-screenshot
description: Show what a pull request changed, with a picture. Use when opening a pull request, when updating one after a review, or whenever a PR body is being written or rewritten here. Covers pointing the preview's camera at the changed screen with a shot recipe, what the standing shots already show, what to show for a change with no UI, how to capture a screen by hand, and what must never appear in a screenshot.
user-invocable: true
---

# Show what you changed

A pull request body that says "adds the legend toggle" asks its reviewer to
build the picture in their head and then check yours against it. A pull request
that shows the legend toggle has already answered the question the reviewer was
going to open the branch to ask.

**Three things happen, and two of them are yours.**

`pr-preview.yml` photographs every pull request's build into the preview
comment. Two standing shots — first run, and the trail screen past it — happen
whether you think about them or not; they answer "does the app still come up on
this branch", and they are not an answer to "what did you change". Before #998
they were the only pictures, which is how every comment came to show the entry
page and nothing about the change.

The rest of the camera is yours to point. The comment leads with a shot of
every **recipe** under `client/preview-shots/` that your pull request adds or
changes — so a change a hiker can see gets photographed by writing (or
touching) the recipe that reaches its screen. See "Point the camera at the
change" below.

The `## Screenshot` section in
[`.github/pull_request_template.md`](../../../.github/pull_request_template.md)
is also yours: say which shot to look at and what is different in it, and carry
everything no recipe can reach — the numbers a pipeline change moves, or the
line saying there is nothing to show. It sits between "What this changes" and
"How it was checked" because it belongs to the same argument — what is
different, what it looks like, and how you know it works.

## What goes in it

The section wants *evidence of the change*, and a screenshot is what that
usually means. Three cases, and the third is not a loophole:

**A change with a UI.** A recipe, so the preview comment leads with the thing
that changed on the phone the app is for — and a sentence in this section
naming that shot and the difference to look for. One recipe for the screen the
change is about; two where a second state is the point. A gallery of eight is
not more evidence, it is less — nobody scrolls it.

**A change with no UI** — the pipeline, the backend, a workflow, a doc. Show
the evidence that actually exists. This is the common case here, and it is
where the section earns its place rather than filling it:

- The numbers, as a before-and-after table. `export_poi.py` dropping 41 sites
  that used to ship is a two-column table, and it is far better evidence than a
  paragraph claiming the filter is tighter now.
- Terminal output where the output *is* the finding — a test going red on the
  defect and green on the fix, in that order, which is the confirm-red-once
  rule CI cannot show you.
- A render, where the change is about something visible that is not the app: a
  contact sheet from `client/scripts/preview-poi-pins.ts`, a map at the zoom
  where a label collides.

**A change with genuinely nothing to show.** Write one line saying so and why —
"No visual: this renames a helper and no rendered output moves." That line is a
real answer and takes ten seconds. It is not an apology, and a reviewer reading
it knows the author checked rather than forgot.

**Do not decorate.** A screenshot of an unrelated screen, attached because the
section wanted an image, is worse than the honest line above: it looks like
evidence, and it is the same failure as
[CLAUDE.md](../../../CLAUDE.md)'s comments asserting things nobody had checked.
If the picture does not show the change, do not attach the picture. The same
rule bounds recipes: point the camera at the screen your pull request changed,
not at extra screens to make the comment fuller.

## Point the camera at the change

A recipe is a small ES module in [`client/preview-shots/`](../../../client/preview-shots/)
that gets the built app to one screen and captions it.
[`legend.mjs`](../../../client/preview-shots/legend.mjs) is the worked example:

```js
export const caption = 'The legend'
export const alt = 'The legend sheet, open over the trail screen'

export default async function drive(page) {
  await page.getByRole('button', { name: 'Legend' }).click()
}
```

The contract, everything optional but the file:

| | |
|---|---|
| `caption` | heads the shot's cell in the comment (default: the file name) |
| `alt` | the image's alt text (default: the caption) |
| `entry` | `true` keeps first run on screen; the runner skips it otherwise |
| `wait` | settle in ms after load, and again after the drive (default 3500) |
| default export | the drive: Playwright taps from the loaded app to the state worth photographing. Omit it for a screen the app opens on by itself |

`pr-preview.yml` hands the runner
([`client/scripts/photograph-preview.mjs`](../../../client/scripts/photograph-preview.mjs))
the pull request's file list; every recipe the pull request adds or changes is
photographed from the same build being deployed and leads the comment,
captioned, above the standing two. In CI the map data is real, so the shot can
show actual tiles — the one thing no sandbox capture can.

Three consequences worth knowing before writing one:

- **Touching a recipe re-photographs it.** Reaching a screen gets written once
  and reused: when the recipe for your screen already exists, changing it is
  enough to put its shot on your pull request.
- **A recipe that cannot drive becomes a sentence in the comment** — "The
  camera could not take `water-card`" — not a silent gap. Usually it means the
  pull request moved the thing it photographs, which is exactly what a
  reviewer should hear about.
- **A `client/src/` change with no recipe gets nudged.** The comment says no
  shot above is the pull request's own. If the change genuinely has no screen,
  answer the nudge in `## Screenshot`; it is a question, not a failure.

Check the drive locally before pushing — it either reaches the screen or it
does not, and CI should not be the first to find out:

```
cd client
npm run build
node scripts/photograph-preview.mjs preview-shots/legend.mjs --dist
```

That shoots your recipe plus the standing two into `client/dist/__screenshot/`
(gitignored), and writes the same `comment.md` block CI will post. The sandbox
canvas holds no map data, so judge the chrome and the drive there, not the
tiles.

## Taking one

For a frame you want to look at, or describe, without putting it in the
comment — a recipe is how a shot gets *into* the comment:

```
cd client
node scripts/screenshot.mjs legend-toggle
```

That serves the app itself on a free port, skips first run, photographs a
390×844 phone at 2× into `client/dist/__screenshot/` (gitignored), and stops the
server. Options:

| | |
|---|---|
| `--dist` | photograph the **built** app via `vite preview` rather than the dev server. What CI shoots, so it is the same bytes that get deployed — run `npm run build` first |
| `--entry` | keep first run on screen — the default skips past it, because otherwise every screenshot is of the same three entry cards |
| `--url=…` | photograph something already running: your own dev server, or a deployed preview |
| `--desktop` | 1280×800 and not a phone, for `site/` |
| `--wait=6000` | longer settle, for a screen that animates in |
| `--full` | the whole scrollable page rather than the viewport |

**Getting the app into the state you want to photograph** is the part the
script cannot do for you. Reach for `--url` against a dev server you are
already driving, or add the taps you need to a copy of the script — it exports
`capture()` for exactly that.

**What it cannot show.** Not map *data*: the corridor archive lives in
IndexedDB and nothing downloads it in a sandbox, so the map canvas renders
paper and no trail (measured 2026-08-25 — the console says
`ArchiveNotDownloadedError`). Chrome, cards, sheets, pickers, the legend and
first run are all DOM and photograph correctly.

For real tiles underneath, a recipe is the first answer: CI photographs it
against the real data source and hosts the result. By hand, point `--url` at
the pull request's own Cloudflare preview, which is built the same way — the
PR preview bot comments the link on every pull request. **The `--url` route
works from a laptop and not from an agent sandbox.** Chromium there cannot reach any external host:
measured 2026-08-25 against the live preview and against `example.com`, both
`net::ERR_CONNECTION_RESET`, with and without Playwright's `proxy` option
pointed at `HTTPS_PROXY`. `curl` reaches the same URL and answers 200, so the
host is allowed and the browser is the part that cannot use the egress proxy.
Do not work around it. A session that needs a map-data screenshot has to ask
somebody with a browser, and should say in the pull request that it could
not take one.

## Where an image can live at all

A pull request body is markdown text with no attachment field, so an image in
one is always a URL. Two facts bound what is possible, and both were checked
rather than assumed:

**You cannot upload to GitHub.** Dragging an image into the web editor posts it
to `github.com/user-attachments/` through an authenticated endpoint that is part
of the web UI and not the REST API — checked against the GitHub MCP tool
surface 2026-08-25, which exposes no attachment, asset or gist call.

**You cannot inline the bytes.** A pull request body caps at 65,536 characters
and a 79,290-byte PNG base64-encodes to 105,720 — 161% of the limit. Even the
smallest legible variant measured, a 23,928-byte JPEG at scale 1, eats 49% of
the body. (GitHub's markdown sanitiser is also understood to strip `data:`
image sources, but that half is recalled rather than measured; the arithmetic
settles it either way.)

So an image has to be *served* from somewhere. **The preview is that
somewhere**, and it is why the automated screenshot exists: `pr-preview.yml`
writes the capture into the directory it uploads to Cloudflare Pages, so the
image comes from the same deployment as the app it shows, at
`https://pr-<n>.<project>.pages.dev/__screenshot/<name>.png`.

**It dies when the pull request closes**, because the preview does — the
workflow tears previews down on close so a build vouched for by nobody does not
stay reachable. That is the deliberate trade: the picture lasts exactly as long
as review does, and in exchange nothing permanent enters a public tree. The
first version of this rule committed the PNG instead and it cost 79,290
unretractable bytes per pull request (#984, replaced by #988). **Do not commit a
screenshot to get around this.** If the archaeology matters, the merged diff is
the record.

### When no recipe can reach it

A recipe is how a shot of your own gets hosted: the runner writes it into the
deployment, and the comment serves it from there. Fall back to describing only
when no recipe can photograph the thing — a transient state with no stable
drive to it, a screen that would need somebody's real data on it, a rendering
outside the app. Then take the frame by hand (above), look at it, and say in
the `## Screenshot` section what it showed. A sentence a reviewer can check
against the preview themselves — "the toggle sits above the attribution strip
and the legend no longer covers the scale bar" — is worth more than a picture
nobody can see, and it is the honest thing available.

If a change genuinely needs a picture in the thread that no recipe can take,
ask the maintainer to drag one in. That is not a workaround; it is the only
path that both hosts the bytes and keeps them out of a commit.

## Never photograph these

A screenshot is a publication, and it publishes whatever was on screen —
including things you were not looking at. Before committing one, look at the
whole frame, not the part you changed.

A recipe raises the stakes, because it is these rules on a timer: its shot
re-takes whenever the recipe is touched, on whatever the app then holds, so a
drive that ends on somebody's submissions publishes them on every future pull
request too. Write the drive to end on fixture-shaped or public state, and
look at the frame it produces before pushing it.

- **A signed-in account.** A real email address, a display name, an avatar, a
  session in a URL. Sign out, or use a fixture identity.
  ([features/IDENTITY_AND_PRIVACY.md](../../../features/IDENTITY_AND_PRIVACY.md).)
- **Anybody's reports, photos or trip data.** Personal by construction. The
  moderation queue is the obvious trap: it is *made of* other people's
  submissions.
- **A dispersed or user-created campsite at a readable zoom.**
  [`pipeline/SOURCE_SURVEY.md`](../../../pipeline/SOURCE_SURVEY.md) §3b records
  2,333 of these in ATC's own index — the ones land managers are often trying
  to close — and publishing their locations is exactly the thing this project
  has decided not to do. A map screenshot is a publication of coordinates.
- **Anything from a real device with a real location fix.** That is somebody's
  location, and it is usually yours.

If you notice one of these *after* committing, say so in the pull request
rather than quietly force-pushing over it: the bytes are already in every fork
that fetched the branch, and the maintainer needs to know which ones.

## When the automated shot is wrong

If the preview comment's screenshot shows a broken or blank app, that is a
finding, not a glitch — it is the build a reviewer would open. Chase it before
explaining it away.

If one recipe's shot is missing, the comment names it and carries the error in
a sentence; the job log has the trace. A drive that stopped reaching its
screen usually means the pull request moved that screen — fix the recipe or
the screen, whichever is wrong.

If every image is missing, the workflow says why in the job log and the
comment says so in one line. A pull request from a fork gets no secrets, so it
gets no preview and no screenshot; that is expected and is not something to
fix in the pull request.
