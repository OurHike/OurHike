"""OurHike's field notes and the disputes they corroborate, from its Postgres, as `raw_ourhike__notes` and `raw_ourhike__disputes`. Hourly.

Both are export_conditions.py's queries, whole: notes are each place's five
most recent visible ones inside 90 days, and disputes need two accounts and
carry a count, never a `reporter_id`. Neither reaches a mart. Both stay in the
hourly bake as today (WN11). They are typed `warnings` for the lane and for
the zero rule: a week with no dispute is real, and the query's own count
proves it.

When `field_notes` is not configured for the reader, both are Unavailable
rather than empty, as export_conditions.py's PENDING_READER_SETUP omits
them from the bake: left out of the run, withdrawn from the warehouse, and
closures and reports carry on.
"""

from extract._kinds import conditions_query

TYPE = "warnings"
UNREGISTERED = "OurHike's own database: export_conditions.py's PUBLIC_NOTES_SQL and PUBLIC_DISPUTES_SQL are the queries' one home"
RESOURCES = [conditions_query("notes"), conditions_query("disputes")]
