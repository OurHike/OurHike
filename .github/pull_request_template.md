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
What the change looks like. A UI change gets a picture of the thing that
changed; a pipeline or backend change gets whatever the evidence actually is —
a before-and-after table, a test going red then green, a render. A change with
genuinely nothing to show says so in one line and why, which is a real answer.
Do not attach an unrelated screenshot to fill the section.

`cd client && node scripts/screenshot.mjs <name>` takes one and prints the line
to paste here. Full instructions, and what must never appear in a screenshot,
are in .claude/skills/pr-screenshot/SKILL.md.
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
