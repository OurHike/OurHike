"""OurHike's own database's size, from its Postgres, as `raw_ourhike__database_size`. Hourly, one row.

No hiker's data and no conditions artifact: the public data-quality page's
storage check, which warns from 400 MB and fails from 475 MB of the 500 MB
past which Supabase's Free plan turns the database read-only
(lib/database_size.py says why the size is public, and what reads it).

Typed `org`, as the registry's own files are, because it is a fact about an
organization, OurHike itself, and because a closures or warnings type would
make it a notice source (generate_notice_models.py's notice_sources()) and
let it land empty. Hourly by override, for two reasons. The conditions legs
are the only jobs that hold the database's URL. And the room between the
warning and read-only is short: at the usage route's daily budget of 50,000
rows, each as large as a plan row may be, about 1,270 bytes
(features/EVENTING.md §0), usage alone adds about 61 MB a day, so 400 MB
to 500 MB can take under two days (Reasoned from those two figures). Unlike
closures.py's read, a failed one stops nothing but itself
(extract/_kinds.py's DatabaseSize).
"""

from extract._kinds import database_size

TYPE = "org"
UNREGISTERED = "OurHike's own database: lib/database_size.py's DATABASE_SIZE_SQL is the query's one home"
RESOURCES = [
    database_size(
        cadence_override="hourly",
        cadence_reason=(
            "the conditions legs alone hold the database's URL, and a flood at the usage route's daily budget "
            "can take it from the 400 MB warning to read-only in under two days"
        ),
    )
]
