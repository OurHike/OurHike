"""OurHike's own moderator-verified closures, from its Postgres, as `raw_ourhike__closures`. Hourly.

Decision 6: one `closures` mart for every org plus OurHike. The query is
export_conditions.py's PUBLIC_CLOSURES_SQL, whole: `moderation_status =
'verified'`, and never `reported_by` or `verified_by`. A reader that cannot
see the table stops the lane, as it stops the bake, because an unreadable
closures table reads exactly like a trail with none.
"""

from extract._kinds import conditions_query

TYPE = "closures"
UNREGISTERED = "OurHike's own database: export_conditions.py's PUBLIC_CLOSURES_SQL is the query's one home"
RESOURCES = [conditions_query("closures")]
