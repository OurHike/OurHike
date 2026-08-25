---
name: pr-screenshot
description: Show what a pull request changed, with a picture. Use when opening a pull request, when updating one after a review, or whenever a PR body is being written or rewritten here. Covers what to show for a change with no UI, how to capture the app, how an image is made to render in a PR body at all, and what must never appear in one.
user-invocable: true
---

# Show what you changed

A pull request body that says "adds the legend toggle" asks its reviewer to
build the picture in their head and then check yours against it. A pull request
that shows the legend toggle has already answered the question the reviewer was
going to open the branch to ask.

**Every pull request carries a `## Screenshot` section.** It is in
[`.github/pull_request_template.md`](../../../.github/pull_request_template.md),
between "What this changes" and "How it was checked", because it belongs to the
same argument: what is different, what it looks like, and how you know it works.

## What goes in it

The section wants *evidence of the change*, and a screenshot is what that
usually means. Three cases, and the third is not a loophole:

**A change with a UI.** A screenshot of the thing that changed, on the phone
the app is for. Two images at most: a before and an after where the difference
is the point, one otherwise. A gallery of eight is not more evidence, it is
less — nobody scrolls it.

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
If the picture does not show the change, do not attach the picture.

## Taking one

```
cd client
node scripts/screenshot.mjs legend-toggle
```

That starts vite on a free port, skips first run, photographs a 390×844 phone
at 2× into `.github/pr-screenshots/`, stops the server, and prints the exact
line to paste into the pull request body. Options:

| | |
|---|---|
| `--entry` | keep first run on screen — the default skips past it, because otherwise every screenshot is of the same three entry cards |
| `--url=…` | photograph something already running: a deployed preview, or your own dev server |
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
first run are all DOM and photograph correctly. For real tiles underneath,
point `--url` at the pull request's own Cloudflare preview, which is built
against the real data source — the PR preview bot comments the link on every
pull request.

## Getting it to render in the pull request body

This is fiddlier than it looks, and the reason is worth knowing so you do not
spend the discovery again:

**The bytes have to live somewhere GitHub can fetch.** A pull request body is
markdown text; there is no attachment field on it. Dragging an image into the
web editor uploads it to `github.com/user-attachments/` through an
authenticated endpoint that is part of the web UI and not the REST API, so no
agent session can use it — checked against the GitHub MCP tool surface
2026-08-25, which exposes no attachment, asset or gist call.

Embedding the bytes inline does not work either, and the reason that settles it
is arithmetic rather than a claim about GitHub's behaviour: **a pull request
body caps at 65,536 characters, and a 79,290-byte PNG base64-encodes to
105,720.** It does not fit, at any capture scale worth looking at — the
smallest legible variant measured, a 23,928-byte JPEG at scale 1, still eats
half the body. Separately, GitHub's markdown sanitiser is understood to allow
only `http`/`https` image sources and to strip `data:` — but that half is
recalled rather than measured, because `api.github.com` is blocked by the
sandbox's egress policy and its `/markdown` endpoint could not be asked. The
size limit is the load-bearing half and needs no such caveat.

**So the image is committed, and the body links to it.** Verified — a raw URL
answers `200 image/png` and GitHub proxies it into the rendered body.

1. Write the capture to `.github/pr-screenshots/` (the script's default). Not
   under `client/`: everything there is in the client suite's scope, so a
   committed PNG would run the whole client suite to prove a PNG still parses.
   `.github/` is in no suite's scope.
2. Commit it on the branch, with the change it is evidence for.
3. Put the printed line in the body, with that commit's sha in place of
   `<sha>`:

   ```html
   <img src="https://raw.githubusercontent.com/OurHike/OurHike/<sha>/.github/pr-screenshots/legend-toggle.png" width="390" alt="the legend, with the toggle open">
   ```

**Pin the sha, not the branch.** A branch reference breaks the moment the
branch is deleted after merge; the commit survives in `main`'s history and so
does the URL naming it. That last part is a property of *how this repository
merges*, not of GitHub: pull requests land here as merge commits — checked
2026-08-25, `ccd1df0` from #965 is reachable from `main` — so every branch
commit is preserved. **If the repository ever switches to squash merging, this
breaks quietly**: the pinned commit would never reach `main`, and the image
would keep working until the branch was deleted and then 404 in a body nobody
re-reads. Committing the screenshot in the pull request's own final commit is
not enough to save it; the fix would be to link the merge commit instead. **Keep the `width`** — a 2× capture is 780 px wide and
GitHub renders an image at its natural size, so without the attribute a phone
screenshot arrives at twice life size. `<img>` rather than `![]()` for that
reason alone: markdown image syntax carries no width.

**What this costs, since it is a permanent publication.** One phone screenshot
is 79,290 bytes measured; the whole repository packs to 14.3 MiB, so each one
is roughly half a percent of it, and a commit cannot be retracted
([CONTRIBUTING.md](../../../CONTRIBUTING.md), "Data does not go in commits").
That is the reason for *one* image and not eight, and for the 150 KB budget the
script warns past. It is also why an honest "no visual" line is a perfectly
good outcome rather than a failure to try.

## Never photograph these

A screenshot is a publication, and it publishes whatever was on screen —
including things you were not looking at. Before committing one, look at the
whole frame, not the part you changed.

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

## Updating one

Re-run the script over the same name, commit, and update the sha in the body.
Same file name, so the directory does not accumulate a shot per push — the
history keeps the old ones, and the old URLs keep working, which is the point
of pinning a sha.
