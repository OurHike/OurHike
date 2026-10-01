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
"""

from extract._kinds import reviewed_input

CLAIMS = ("atc_trail_updates",)
RESOURCES = [reviewed_input("atc_trail_updates", rows_key="updates")]
