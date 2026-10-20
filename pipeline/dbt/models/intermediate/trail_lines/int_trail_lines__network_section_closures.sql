{{ config(materialized='table') }}
-- Every network line, with the ones an organization's own notice closes by
-- naming their section marked closed (for #1801 —
-- The junction graph routes hikers onto the Tuscarora's Doll Ridge section,
-- which PATC says is closed for loss of landowner permission). Read between
-- NYS Parks' area closures (int_trail_lines__network_area_closures) and the
-- 1 m pass, so a closed line is drawn closed in nearby_trails.geojson and
-- int_trail_network__routable refuses it, as it refuses every closed line.
--
-- THE RULE is lib/section_closures.py's, run by step_section_closures over
-- the conditions/notices.json the hourly lane published: a notice that
-- closes the trail in its own words, has no geometry of its own, and is the
-- line's steward's or a club's naming the trail, closes the one line set
-- whose name is the section it names. This model only applies the step's
-- answer: the whole line closes, `closure_kind` 'section', and the reason is
-- the notice's own title verbatim (the closing sentence, for a
-- page notice), the closing organization its source (#1142: the sheet speaks
-- the closing organization's name, not the line's).
--
-- A LINE ALREADY CLOSED KEEPS ITS OWN CLOSURE. The step reads only lines
-- that are not closed, so a line its steward marks closed, or a section
-- inside one of NYS Parks' areas, is never here. A step that read no notices
-- lands no row, and every line ships as the area pass left it.
with lines as (
    select * from {{ ref('int_trail_lines__network_area_closures') }}
),

section_closures as (
    select * from {{ ref('stg_derived__section_closures') }}
)

select
    lines.trail_segment_key,
    lines.source_key,
    lines.club,
    lines.file_row,
    lines.trail_line_id,
    lines.published_id,
    lines.name,
    case
        when section_closures.trail_segment_key is null then lines.trail_status
        else 'closed'
    end as trail_status,
    case
        when section_closures.trail_segment_key is null
            then lines.trail_status_basis
        else 'closed_section'
    end as trail_status_basis,
    case
        when section_closures.trail_segment_key is null then lines.closure_kind
        else 'section'
    end as closure_kind,
    case
        when section_closures.trail_segment_key is null
            then lines.closure_reason
        else section_closures.closure_reason
    end as closure_reason,
    case
        when section_closures.trail_segment_key is null
            then lines.closure_source
        else section_closures.closure_source
    end as closure_source,
    lines.blaze_color,
    lines.duplicate_of,
    lines.geom_wkt,
    lines._loaded_at
from lines
left join section_closures
    on
        lines.trail_segment_key = section_closures.trail_segment_key
        and coalesce(lines.trail_status, '') != 'closed'
