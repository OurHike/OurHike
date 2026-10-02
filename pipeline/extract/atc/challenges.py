"""ATC's challenges, one reviewed file per challenge under reference/challenges/atc/.

The files came with #1780 — Let a club publish a challenge — places on its own
trails that hikers opt into and tag at camp — starting with the ATC's A.T.
Summer Bucket List, and they are reviewed row by row; this only loads them.
That pull request asked for ATC's written permission to be recorded in
sources.json before the challenge reaches a phone. None is: the list publishes
on the maintainer's authorisation instead, given as an ATC volunteer
(pipeline/ELT.md decision 47, 2026-10-02: "For the ATC challenges list. I
have their permission as a volunteer."), through the folder's row of
pipeline/dbt/seeds/unregistered_publishing_sources.csv. No written grant from
the ATC is in this repository.

Each file lands verbatim, as the JSON its reviewer wrote (ReviewedDir's
`verbatim`), because the gate dbt runs over it (the int_challenges__ models,
lib/challenges.py's rules) refuses a file or an item for its field names and
value types: `"radius_m": "150"` is not a number and `"takes_entries": "yes"`
is not a boolean, and typed columns would have let dlt coerce exactly those
away, as ReviewedFile's `verbatim` measured for the podcast episodes.
"""

from extract._kinds import reviewed_dir

CHALLENGES = "reference/challenges/atc"

CLAIMS = (CHALLENGES,)
RESOURCES = [reviewed_dir(CHALLENGES, verbatim=True)]
