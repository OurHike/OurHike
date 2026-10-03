"""OurHike's curated highlights: reference/highlights.json, reviewed in git, one row per stretch worth going to.

10 highlights, keyed by `id` (ELT.md, "One key per table"). Each names its
basis, so the app never says "popular" flatly (lib/highlights.py). Monthly,
with the suggested hikes it is published beside (ELT.md, `_shared/`'s
editorial row).

Each row lands verbatim, as the JSON the reviewer wrote, because the gate dbt
runs over it (int_suggested_hikes__highlights, lib/highlights.py's resolve())
refuses a row for its value types: an id or a name that is not a string, legs
that are not a list, a leg that is not an object. Typed columns would have let
dlt coerce exactly those typos away (ReviewedFile's `verbatim` has the
measurement).
"""

from extract._kinds import reviewed_file

TYPE = "suggested_hikes"
CLAIMS = ("reference/highlights.json",)
RESOURCES = [reviewed_file("reference/highlights.json", rows_key="highlights", verbatim=True)]
