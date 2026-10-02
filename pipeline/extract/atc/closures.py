"""ATC's Trail Updates: the reviewed file reference/atc_updates.json, and what ATC's website shows now.

What a person stands behind is the reviewed file: the registry row is the
upstream, and a person reviews ATC's posts into the file
(features/ATC_TRAIL_UPDATES.md, "the parse proposes; a human publishes"), so
that loads. The split into closures and warnings is dbt's, on
`obstructs_trail` (decision 7), so one resource feeds both types and
warnings.py shares it.

Each row lands whole, as the JSON its reviewer wrote (ReviewedFile's
`verbatim`), because lib/atc_updates.py's row checks are about JSON types:
a mile written "476.6" is "not a mile", and `obstructs_trail` must be a
real boolean. Typed columns would hide exactly those typos. Measured on dlt
1.30.0 for the podcast file: a bigint hint landed "34" as 34, and
sql_ci_v1 folded a misspelt key into the right column. dbt's
int_closures__atc_checked reads the fields and refuses what the Python
refuses.

The file also lands whole, as one row (`raw_atc__atc_updates`), because
the review is a fact about the file and not about a row: with no rows in
`updates`, the rows' table has nowhere to carry `reviewed_at`, and an empty
reviewed file is a real answer export_atc_updates.py publishes as
`atc_updates: []` ("we looked, and ATC has nothing placeable"). dbt's
int_closures__gate reads the review from this row.

The third resource is ATC's website itself, one row per update in its
trail-updates sitemap, as lib/atc_scrape.py parses the page
(`raw_atc__atc_trail_updates_pages`, extract/_kinds.py's AtcTrailUpdatePages).
It replaces fetch_atc_updates.py's scrape: the rows ATC posted since the
review, which export_atc_updates.py publishes without a person when they
have one reading, and which dbt's int_closures__atc_automatic now decides
(CL07-CL10). It reads the same registry row as the reviewed file, so it
claims nothing more; its `part` keeps the two reads apart.
"""

from extract._kinds import atc_trail_update_pages, reviewed_file, reviewed_input

CLAIMS = ("atc_trail_updates", "reference/atc_updates.json")
RESOURCES = [
    reviewed_input("atc_trail_updates", rows_key="updates", verbatim=True),
    reviewed_file("reference/atc_updates.json", rows_key=None, verbatim=True),
    atc_trail_update_pages("atc_trail_updates"),
]
