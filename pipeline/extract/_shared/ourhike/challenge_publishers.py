"""Which trails each organization may put a challenge on: reference/challenges/publishers.json, reviewed in git.

OurHike's own judgement, not any club's (#1780 — Let a club publish a
challenge — places on its own trails that hikers opt into and tag at camp —
starting with the ATC's A.T. Summer Bucket List): one row per organization,
with the trails, the reason and the web domain a reviewer checked (the file's
own `_README`). export_challenges.py's publisher_scope() reads it, and so does
the int_challenges__publishers model that ports it. One row on 2026-10-02, the
ATC on the A.T.

The whole file lands as one verbatim row, as sources.json does, because the
port reads `publishers` the way load_publishers() does: a value that is not a
list publishes no organization, rather than failing the extract. Verbatim for
the reason ReviewedFile's `verbatim` gives: `why`, `domain` and each trail are
refused for their JSON type, which typed columns would coerce away.
"""

from extract._kinds import reviewed_file

TYPE = "challenges"
CLAIMS = ("reference/challenges/publishers.json",)
RESOURCES = [reviewed_file("reference/challenges/publishers.json", rows_key=None, verbatim=True)]
