"""OurHike's curated highlights: reference/highlights.json, reviewed in git, one row per stretch worth going to.

10 highlights, keyed by `id` (ELT.md, "One key per table"). Each names its
basis, so the app never says "popular" flatly (lib/highlights.py). Monthly,
with the suggested hikes it is published beside (ELT.md, `_shared/`'s
editorial row).
"""

from extract._kinds import reviewed_file

TYPE = "suggested_hikes"
CLAIMS = ("reference/highlights.json",)
RESOURCES = [reviewed_file("reference/highlights.json", rows_key="highlights")]
