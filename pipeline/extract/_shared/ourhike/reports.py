"""OurHike's public hiker reports, from its Postgres, as `raw_ourhike__reports`. Hourly.

The query is export_conditions.py's PUBLIC_REPORTS_SQL, whole: `status IN
('verified', 'resolved') AND visibility = 'public'`, with `verified_at` and
never `verified_by` or `reporter_id`. Every public report lands. The serious
ones are the warnings mart's (decision 7's split), and that choice is dbt's.
Like closures, an unreadable table stops the lane.
"""

from extract._kinds import conditions_query

TYPE = "warnings"
UNREGISTERED = "OurHike's own database: export_conditions.py's PUBLIC_REPORTS_SQL is the query's one home"
RESOURCES = [conditions_query("reports")]
