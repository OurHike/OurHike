<!--
Keep the line below and put the issue number on it. CI checks for it: a PR
that closes no issue fails the "PR has a linked issue" check.

If this change genuinely has no issue behind it — a typo, a revert, a
dependency bump — delete the line and label the PR `no-issue`. That is the
intended way out. Opening an issue for the sole purpose of closing it here
is worse than the exemption.
-->

Closes #

## What this changes

<!-- What is different afterwards, and why that is the right difference. -->

## Screenshot

<!--
The preview comment already carries first run and the trail screen, taken from
this build automatically. This section is for what those two cannot reach.

A UI change: say which screen, and what is different about it. A pipeline or
backend change: whatever the evidence actually is — a before-and-after table, a
test going red then green, a render. A change with genuinely nothing to show
says so in one line and why, which is a real answer.

`cd client && npm run build && node scripts/screenshot.mjs <name> --dist` takes
a shot of any screen so you can look at it; the output is gitignored and is not
committed. Nothing here goes in a commit. Full instructions, and what must never
appear in a screenshot, are in .claude/skills/pr-screenshot/SKILL.md.
-->

## How it was checked

<!--
Which of `npm test` / `pytest` / `ruff` / a real device on a real trail, and
what the result was. New behaviour comes with tests — see TESTING.md.
-->

## Docs

<!--
If this contradicts a design doc, the doc changes in this PR too. A doc that
disagrees with the code is worse than no doc. Delete this section if nothing
in docs/ or features/ is affected.
-->
