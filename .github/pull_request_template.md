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

---

## PR checklist (please complete)

- [ ] PR links to an existing issue or is labeled `no-issue` (explain why)
- [ ] Tests added or updated for new behavior
- [ ] Lint and type checks are passing locally
- [ ] If this PR adds/changes data models, include a data-docs link or COSTS.md if it introduces external services

### Cost & external services
If this PR introduces a new external dependency, paid API, hosted dataset, or long-running server process, add a COSTS.md to the repo root describing the expected recurring cost, mitigation plans, and approver information.

### Data and docs
If this PR touches pipeline or data models, link the data docs entry and list any tests added to validate critical metrics.

### Agents and reviewers
- [ ] Money Man (costs/COSTS.md) — required if new external services
- [ ] Mapping Expert — required for changes to map data, GPX, GeoJSON, DEMs
- [ ] Analytics Engineer — required for changes to public metrics or data models
- [ ] Full-Stack Dev — review for architecture, CI, and ops impact

### Notes
Any additional notes for reviewers.
