-- The network lines an organization's own notice closes by naming their
-- section: step_section_closures's table
-- (pipeline/step_section_closures.py), staged like any table a source lands.
-- int_trail_lines__network_section_closures closes them.
--
-- Key: the line, which one notice closes at most: the step takes a line set
-- only when exactly one set carries the section, and a line is in one set
-- (lib/section_closures.py's line_sets()). Two notices naming the same
-- section each close it, and the dedupe below keeps the first by notice id,
-- so the line carries one reason.
with source as (
    select * from {{ source('derived', 'section_closures') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'section_closures'",
            'trail_segment_key',
        ]) }} as section_closure_key,
        trail_segment_key,
        notice_id,
        closure_source,
        closure_reason,
        line_set,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='section_closure_key', order_by='notice_id'
) }}
