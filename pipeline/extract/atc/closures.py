"""ATC's Trail Updates, as reviewed into reference/atc_updates.json.

What ships today is the reviewed file, not a scrape: the registry row is the
upstream, and a person reviews ATC's posts into the file (features/ATC_TRAIL_UPDATES.md,
"the parse proposes; a human publishes"), so that is what loads. The split
into closures and warnings is dbt's, on `obstructs_trail` (decision 7), so one
resource feeds both types and warnings.py shares it.

Its change check is the file's sha256. Moving the check to ATC's
trail-updates sitemap, so a changed post is noticed without a person, is
ELT.md's design ("The skip-unchanged check, by platform") and not built yet;
propose_atc_updates.py proposes from ATC's site today.

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
"""

from extract._kinds import reviewed_file, reviewed_input

CLAIMS = ("atc_trail_updates", "reference/atc_updates.json")
RESOURCES = [
    reviewed_input("atc_trail_updates", rows_key="updates", verbatim=True),
    reviewed_file("reference/atc_updates.json", rows_key=None, verbatim=True),
]
