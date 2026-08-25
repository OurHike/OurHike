# Shot recipes

A recipe is how a pull request points the preview's camera (#998). Each `.mjs`
file here drives the built app to one screen and captions it;
`pr-preview.yml` photographs every recipe a pull request adds or changes —
plus the standing two, `first-run.mjs` and `trail-screen.mjs` — and leads the
preview comment with the results.

The contract, the local commands, and what must never appear in a shot are in
[`.claude/skills/pr-screenshot/SKILL.md`](../../.claude/skills/pr-screenshot/SKILL.md);
`legend.mjs` is the worked example. Recipes accumulate as reusable ways of
reaching a screen — reuse one by touching it, not by copying it.
