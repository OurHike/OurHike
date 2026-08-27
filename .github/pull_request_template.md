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
The preview comment leads with a shot of every recipe under
client/preview-shots/ this PR adds or changes, then the standing two (first
run, the trail screen). A change a hiker can see points the camera at itself:
add or touch the recipe for the screen that changed, then use this section to
say which shot to look at and what is different in it.

A pipeline or backend change: whatever the evidence actually is — a
before-and-after table, a test going red then green, a render. A change with
genuinely nothing to show says so in one line and why, which is a real answer.

Recipes are code and are committed; pixels never are — captures land in
client/dist/__screenshot/, gitignored. Full instructions, the recipe contract,
and what must never appear in a shot: .claude/skills/pr-screenshot/SKILL.md.
-->

## How it was checked

<!--
Which of `npm test` / `pytest` / `ruff` / a real device on a real trail, and
what the result was. New behaviour comes with tests — see TESTING.md.
-->

## Data pipelines

<!--
Run scripts/pipelines.sh. If every publishing path is fresh, delete this
section. If anything is STALE, paste the verdict here and say who arranges
the rerun - the merged data going quietly stale is the dropped handoff this
section exists to prevent (#1123). CLAUDE.md, "A pipeline change is not
finished at the merge", is the rule; production promotion is never part of
it - that is the release train's.
-->

## Docs

<!--
If this contradicts a design doc, the doc changes in this PR too. A doc that
disagrees with the code is worse than no doc. Delete this section if nothing
in docs/ or features/ is affected.
-->
