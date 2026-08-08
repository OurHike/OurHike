# COSTS.md (template)

Use this file to document any new or changed feature that could introduce recurring monetary costs (APIs, hosted map tiles, paid routing, cloud compute, telemetry/storage, third-party services). Money Man requires a COSTS.md for any PR that introduces an external service or new long-running server-side component.

Template
-------

Feature: <short feature name>
PR: <link to PR>
Owner: <name/email>

1) Does this change introduce any new external/paid dependency?
   - yes/no: <answer>
   - If yes: list dependency, provider, and exact billing model (monthly, per-request, tiered):
     - provider: <e.g., Mapbox>
     - product: <e.g., map tiles, directions>
     - estimated cost: $<monthly estimate> / $<yearly estimate>

2) Does this change require server-side background processing, long-term storage, or continuous hosting?
   - yes/no: <answer>
   - If yes: estimate compute, storage and bandwidth needs (monthly):
     - compute: <e.g., 0.0 vCPU-hours>
     - storage: <e.g., 0 GB>
     - bandwidth: <GB/month estimate>

3) Proposed mitigation or zero-cost alternative
   - Option A (preferred): <OSS/local alternative with effort estimate>
   - Option B: <caching, precomputation, client-only approach>
   - Option C (paid, non-core): <sponsorship/donation/opt-in with owner>

4) Approval
   - Is a funding/coverage plan required? yes/no
   - If yes: named approver(s) and date of approval

5) Notes and links
   - Links to vendor docs, pricing calculators, and design decisions


If a PR introduces a recurring cost and no coverage plan is recorded here, the Money Man CI check will fail the PR until a satisfactory COSTS.md is added and approved.
