-- One row per network line source: how many rows it landed, kept and
-- dropped, and why, as export_nearby_trails.py prints them and writes them to
-- nearby_trails_manifest.json's `sources` (`kept`, `dropped`). Counted over
-- every source, held back or not, before any line is compared with another
-- source's, as the Python counts them.
--
-- THE COMPLETENESS GATE is this model's test: a source that kept no row
-- stops the build, export_trails.py's gate for the same reason
-- (lib/completeness.py's fail_if_incomplete): a source that silently returns
-- nothing, from a schema change or a renamed status value, must fail the run
-- rather than quietly shrink the map. A source whose every row an owned route
-- suppresses fails it too, on purpose (tests/test_export_nearby_trails.py,
-- test_a_source_whose_every_feature_is_suppressed_also_fails_the_run).
with sources as (
    select * from {{ ref('int_trail_lines__network_sources') }}
),

judged as (
    select * from {{ ref('int_trail_lines__network_judged') }}
),

reasons as (
    select
        source_key,
        dropped_because,
        count(*) as row_count
    from judged
    where dropped_because is not null
    group by source_key, dropped_because
),

drops as (
    select
        source_key,
        json_group_object(dropped_because, row_count) as dropped
    from reasons
    group by source_key
),

kept as (
    select
        source_key,
        count(*) as rows_landed,
        count(*) filter (where dropped_because is null) as rows_kept
    from judged
    group by source_key
)

select
    sources.source_key,
    sources.file_row,
    sources.may_publish,
    coalesce(kept.rows_landed, 0) as rows_landed,
    coalesce(kept.rows_kept, 0) as rows_kept,
    coalesce(drops.dropped, json('{}')) as dropped
from sources
left join kept on sources.source_key = kept.source_key
left join drops on sources.source_key = drops.source_key
