-- The maintaining clubs' stretches of the A.T., which a highlight's `club` is
-- read from (lib/highlights.py's club_for_mile()): club_sections.json's
-- `clubs`, as export_highlights.py's load_club_runs() reads them, one row per
-- stretch. They are int_trail_lines__club_sections' named clubs, the rows
-- pub_club_sections writes `clubs` from, in its order: `club_order` the
-- club's place in that list and `stretch_order` the stretch's place in its
-- club's `stretches`, each from 0. The unattributed runs are not a club, and
-- club_for_mile() never reads them, so a mile in one has no club.
with clubs as (
    select
        acronym,
        club_order,
        cast(stretches_json as json) as stretches
    from {{ ref('int_trail_lines__club_sections') }}
    where acronym is not null
),

stretches as (
    select
        acronym,
        club_order,
        unnest(cast(stretches as json[])) as stretch,
        generate_subscripts(cast(stretches as json[]), 1) - 1 as stretch_order
    from clubs
)

select
    acronym,
    cast(json_extract(stretch, '$.start_mile') as double) as start_mile,
    cast(json_extract(stretch, '$.end_mile') as double) as end_mile,
    club_order,
    stretch_order
from stretches
