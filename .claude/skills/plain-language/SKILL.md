---
name: plain-language
description: Write comments, test names, commit subjects, pull request bodies and chat replies that somebody who was not in the session can follow. Use whenever writing prose another person reads - a code comment, a docstring, a test name, a commit message, a PR body, an issue, or a reply to the maintainer. Covers the three checks that catch a cryptic sentence before it ships, the five habits that produce one, and what must not be sanded off while fixing it.
user-invocable: true
---

# Write it so the next reader does not have to be you

The maintainer, 2026-09-15: *"you are using confusing, cryptic word choice…
we dont actually understand what you are saying."*

That is a bug report about this repository's prose, and this file is the fix.
It is written to its own standard: if a sentence here needs a second read, that
is a defect in this file rather than a house style.

[CLAUDE.md](../../../CLAUDE.md) still wins wherever this file could be read as
disagreeing with it. Its evidence grades — measured, reasoned, `@unvalidated` —
are not a source of the problem and are not touched here. This file adds one
thing that standard never asked for: **the reader has to be able to tell what
the sentence is about.**

## The thinking is not the problem, the one-liners are

Three commits from the last fortnight, each subject line against what its own
body already said:

> **`Answer the bucket in the detail recipes, rather than racing it`** (48b5de0)
>
> The body names the failing selector, the 30-second timeout, the hook
> (`useSuggestedHikes`), the fixture that gets replaced, and says outright that
> the diagnosis was *reasoned, not reproduced*. Everything a reader needs is
> in there.
>
> The subject could have been: `Stub suggested_hikes.json in the detail shot
> recipes` — 51 characters.

> **`Re-price the elevation leg, which had not been measured since the graph
> went nationwide`** (e7bfd2a)
>
> The body carries a four-row before-and-after table, a run number and a date.
>
> The subject could have been: `Re-measure the elevation leg: 28m44s at
> 466,966 edges, not ~40 min` — 66 characters.

> **`Let the recovery's stages hand their work to each other`** (131fd3e)
>
> The body says exactly what broke: each dispatch gets a fresh runner,
> `pipeline/data/` dies with it, so `match` read a directory that did not exist.
>
> The subject could have been: `Cache data/raw/ between NYNJTC recovery stages
> so match sees pages` — 66 characters.

All three landed on 2026-09-15, inside eight hours. The information existed
and did not reach the line people actually read. **This is a surface problem,
not a thinking problem** — which is why it is fixable with checks rather than
with trying harder.

### Measured, 2026-09-15

**10 of the last 100 non-merge commit subjects** contain anything a reader could
search for — a path, a `snake_case` or `camelCase` token, a digit, or an issue
number:

```sh
git log --format='%s' -100 --no-merges |
  grep -cE '\.(py|ts|tsx|md|yml|sh|json)|[a-z]_[a-z]|[a-z][A-Z]|[0-9]|#[0-9]+|`'
```

**471 of 7,202 `it()` names** in `client/src` name a symbol or a number:

```sh
grep -rhoE "^\s*it\('[^']*'" client/src --include=*.test.ts --include=*.test.tsx |
  grep -cE '[a-z]_[a-z]|[a-z][A-Z]|[0-9]|`|\.(ts|tsx)'
```

7,202 of the 7,241 `it(` lines are single-quoted, so that sample is 99.5% of
them.

**Read these as a proxy, not a defect count.** `shows the distance in miles when
the hiker chose miles` names no symbol and is perfectly clear. What the figures
measure is how rarely this repository's prose touches ground somebody can grep
for — and 6.5% is low enough to explain a reader who cannot follow along.

## The one rule

**Name the thing, then say the thing about it.**

Almost every cryptic sentence here is the second half of that shipped without
the first. `Answer the bucket` is a comment about a referent the writer had in
working memory and the reader has never met.

## Three checks, before the sentence ships

Run them on anything another person reads. They take seconds and they fail
loudly, which is the point — "try to be clearer" has never worked.

### 1. The search test

**Does the sentence contain one thing a reader could find?** A file path, a
function, a constant, a number with a unit, an issue number, a string the app
actually renders. One is enough. Zero means the sentence is about something the
reader cannot look up, and the sentence is not finished.

### 2. The "the" test

**Go through every `the X`. Was X named in the previous sentence, or is `X` the
literal name of something in this repository?** If neither, you are writing from
a context window the reader does not have.

`the bucket`, `the seam`, `the settle`, `the gates`, `the camera`, `the shelf`
— each is a real thing with a real name, and each arrives in the prose as if
already introduced. It never was. Write `the R2 bucket hikers download maps
from` once, then `the bucket` freely for the rest of the paragraph. The article
is not the problem; the missing introduction is.

### 3. The 2 a.m. test — tests only

**This test goes red in CI and you see the name and nothing else. Do you know
what broke?**

```ts
// ships
it('holds it back for less than the outbox is willing to hold anything')

// what it asserts
expect(UNDO_WINDOW_MS).toBeLessThan(MAX_UNDO_HOLD_MS)

// passes the 2 a.m. test
it('keeps UNDO_WINDOW_MS under the outbox MAX_UNDO_HOLD_MS ceiling')
```

Nothing was lost. The second name is four characters shorter and says which
two constants disagree, which is the whole content of the failure.

## Five habits that produce a cryptic line

These are the actual mechanisms, in the order they cost the most. Each is a
find-and-fix, not an aspiration.

**1. A pronoun-shaped noun.** `the bucket`, `the leg`, `the settle`. *Fix:*
introduce it once, by its real name, on first use in this artifact.

**2. Definition by contrast alone.** `X, rather than Y` / `X, not Y` is the
house sentence shape and it tells a reader where a thing *stops* without ever
saying what it *is*. Keep the contrast, but only after the plain statement:
`Intercept the request with page.route (rather than widening the timeout)`.

**3. Anthropomorphism instead of a verb.** `the stages hand their work to each
other`, `the outbox is willing to hold`, `the camera kept losing the race`.
These read well and hide the mechanism. *Fix:* use the verb that is actually
happening — passes, returns, writes, awaits, caches, overwrites. `the camera
kept losing the race` → `the shot fired before the climb row rendered`.

**4. The aphorism as the only statement of the rule.** *"A worse thing to be
than merely conservative."* Good writing; incomplete documentation when nothing
above it says the rule plainly. Keep the line — put the plain sentence first
and let the aphorism land after it.

**5. Elegance checked instead of information.** A sentence that sounds finished
stops you re-reading it. The three checks above are the antidote: they ask what
the sentence *contains*, not how it sounds.

## By surface

### Code comments — the strongest of the four, two things still break them

`staleness.ts` and `upcomingClimb.ts` are good comments. Keep writing those.

- **Lead with the sentence that would survive if the rest were deleted.** The
  finding, not the approach to it. A reader who stops after one line should
  still have the point.
- **Apply the "the" test hardest here**, because a comment is read by someone
  who has just arrived at an unfamiliar file. A comment longer than a dozen
  lines that never names a symbol from its own file is describing something the
  reader cannot locate.

### Test names

```
it('<subject> <does what> [when <condition>]')
```

`<subject>` is the symbol under test, the screen, or the exact string the app
renders — something a reader can search for. `<does what>` is the observable
outcome. `<condition>` only when the test is about a particular case.

- Prefer the real name to a description of it: `UNDO_WINDOW_MS`, not `the hold`.
- Quote user-visible strings exactly: `it('says "Filed — blow down here", never
  "at here"')` beats `it('does not say "at here"')`, which never says what it
  does print.
- The `describe()` block is context, not an excuse. Runners print the chain, so
  a name may lean on its parent — but `undo > holds it back for less than the
  outbox is willing to hold anything` still names nothing.
- `TESTING.md`'s existing rules stand: name it for the behaviour it guards
  (`test_full_band_read_catches_late_strip_corruption`, never `test_bug_47`),
  and assert against imported constants rather than literals.

### Test bodies — make the failure legible, not just the name

**Assert on values, so the runner prints them.** `expect(isValid).toBe(true)`
fails with `expected false to be true` and sends the reader to the source.
`expect(tier).toBe('never')` fails with both strings, and often that is the
whole diagnosis.

Where the body needs a comment, it answers *why this case matters* — the
failure the test is standing in front of — not what the lines below do.

### Commit subjects, PR titles, issue titles

**The subject names what changed, in terms that exist outside your session.** A
file, a function, a workflow, a screen, a number. The body is where the
reasoning goes, and this repository's bodies are already good — the subject is
a summary, not a title, and nothing is gained by making it elegant.

A subject that passes the search test and still fits git's 72 characters is
nearly always available. The three rewrites at the top of this file are the
proof — 51, 66 and 66 characters, against 62, 87 and 55 for what shipped. Two
are longer by a few characters and every one of them names something you can
grep for.

### Chat with the maintainer

This is the surface the complaint was actually about.

- **First sentence is the answer**, in words that would make sense to somebody
  who has never opened this repository. Everything else is support.
- **Gloss a repo noun the first time it appears in a reply** — three words in
  parentheses. `the bucket (R2, where the app downloads map data from)`.
- **Numbers carry a unit and a comparison.** `28m44s, down from the ~40 min the
  form advertises` — not `re-priced`.
- **Say what you want them to do**, as the last line, starting with a verb.
- **Never name a thing only by what it is not.**
- A question goes in `AskUserQuestion`, never inside a paragraph — that is
  CLAUDE.md's rule and it is part of the same failure: a question the reader has
  to notice is a question that gets missed.

## What this does not touch

**Do not sand off the honesty.** The evidence grades, `@unvalidated` and what
would settle it, "reasoned rather than reproduced", the refusal to print a
number nobody stands behind — that is the best thing about this repository's
writing and none of it is what the maintainer could not follow. Plain does not
mean confident. `We do not know how fast a spring's condition goes stale` is
plainer than anything it would be replaced with.

**Length is not the defect either.** A long comment carrying provenance is
working. A short line naming nothing is not.

**This governs what you write.** It is not a licence to go rewriting test names
in files you are not otherwise touching — the same limit CLAUDE.md puts on
retitling issue references. When you are already editing a file, its names are
fair game.

**There is no linter for this, deliberately.** What has gone wrong is missing
referents, and grep cannot see an antecedent that was never written. The
measurement commands above are a thermometer for the repository, not a gate on
a pull request: a test named `shows the distance in miles when the hiker chose
miles` would fail every regex here and is exactly right.
