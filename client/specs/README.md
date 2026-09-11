# Test plans

Where the Playwright **planner** agent saves what it found, as markdown, before
the **generator** turns a plan item into a spec in `client/e2e/`
(`npx playwright init-agents --loop=claude`, 2026-09-11).

A plan is not a test and does not run. It is the planner's reading of a screen —
its controls, its paths, its states — written down so the generator has
something to work from and a person has something to disagree with. The four
rules in [features/FLOW_TESTING.md](../../features/FLOW_TESTING.md) are what a
plan is judged against: a plan that lists a happy path and no states has
specified the happy path and called it the screen.

Plans are committed. They are cheap, they are reviewable, and the ledger's
`planned` status means nothing if nobody can see what was planned.
