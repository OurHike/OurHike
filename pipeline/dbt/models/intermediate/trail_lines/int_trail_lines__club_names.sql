{{ config(materialized='table') }}
-- lib/club_sections.canonical_clubs() (TL26): each club's name and region,
-- by acronym, from the trail_club_sections polygons, which spell a club's
-- name and give its region and never decide a stretch
-- (CANONICAL_FROM_POLYGONS). Only polygons from a layer that may publish.
--
-- A polygon's acronym is its ACROYNM stripped as Python strips it; one that
-- is null, empty or all ASCII digits names no club (is_attributable()).
--
-- Two polygons with one acronym: the Python keeps the later in the layer's
-- order, and this keeps the lower GlobalID's, name and region both from that
-- polygon (arg_min_null keeps a null; arg_min would borrow the other
-- polygon's), because stg_atc__club_sections carries no row order. The warn
-- test on polygon_count says when that is happening; it is not today
-- (30 polygons, 30 acronyms, measured 2026-10-02).
with publication as (
    select * from {{ ref('int_sources__publication') }}
),

polygons as (
    select
        polygons.source_id,
        polygons.trail_club,
        polygons.region,
        {{ python_strip('polygons.club_acronym') }} as acronym
    from {{ ref('stg_atc__club_sections') }} as polygons
    inner join publication
        on publication.source_key = 'trail_club_sections'
    where publication.may_publish
)

select
    acronym,
    arg_min_null(trail_club, source_id) as club_name,
    arg_min_null(region, source_id) as region,
    count(*) as polygon_count
from polygons
where acronym != '' and not regexp_full_match(acronym, '[0-9]+')
group by acronym
