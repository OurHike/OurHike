"""ATC's challenges, one reviewed file per challenge under reference/challenges/atc/.

The files came with #1780 — Let a club publish a challenge — places on its own
trails that hikers opt into and tag at camp — starting with the ATC's A.T.
Summer Bucket List, and they are reviewed row by row; this only loads them.
That pull request asked for ATC's written permission to be recorded in
sources.json before the challenge reaches a phone, and none is recorded yet,
so publication stays with rule 6 of ELT.md's "Who may publish".
"""

from extract._kinds import reviewed_dir

CHALLENGES = "reference/challenges/atc"

CLAIMS = (CHALLENGES,)
RESOURCES = [reviewed_dir(CHALLENGES)]
