{{ config(materialized='table') }}
-- NYNJTC's Hike Finder hikes, one row each, as export_suggested_hikes.py
-- reads a cache entry: the facts every published record carries, the slug
-- the client holds for the publisher's difficulty (SH07), and what stops the
-- hike reaching a phone as it stands (SH02). step_form_route.py reads this
-- table to form each hike's route (SH03), so it is a table, not a view: a
-- Python step reads it from outside dbt, with DuckDB 1.5.5.
--
-- SH02, `problems`, is lib/hikefinder.py's hike_problems(), check for check
-- in its order and in its words. It is a review aid and never a gate: the
-- `warn` test on it lists the hikes a person should read, and nothing here
-- or downstream drops a hike for it. Its parse-time copy rides beside it
-- (`parse_problems_json`) until stage 5 of #1793 stops the extract stamping
-- one.
--
-- SH07, `difficulty_slug`, is difficulty_slug(): the export's label,
-- stripped as str.strip() strips and lowercased, looked up in
-- suggested_hike_difficulty_slugs. No row there is no slug, and the card
-- prints no badge rather than a guessed one; "Very Strenuous" takes
-- `strenuous`, which understates it, so `difficulty` keeps the publisher's
-- own word beside it.
with hikes as (
    select * from {{ ref('base_nynjtc__nynjtc_hike_finder') }}
),

slugs as (
    select * from {{ ref('suggested_hike_difficulty_slugs') }}
),

read_hikes as (
    select
        hikes.hike_number,
        -- f"{SOURCE_KEY}:{hike['id']}", the record id the client keys on.
        '{{ var("suggested_hikes_source_key") }}:'
        || cast(hikes.hike_number as varchar) as hike_id,
        hikes.name,
        hikes.source_url,
        hikes.summary,
        hikes.stated_miles,
        hikes.difficulty,
        slugs.difficulty_slug,
        hikes.estimated_hours,
        hikes.route_type,
        hikes.dogs,
        hikes.park,
        hikes.region,
        hikes.author,
        hikes.start_json is not null as has_start,
        cast(json_extract(hikes.start_json, '$.lat') as double) as start_lat,
        cast(json_extract(hikes.start_json, '$.lon') as double) as start_lon,
        json_extract_string(hikes.start_json, '$.label') as start_label,
        coalesce(hikes.features_json, json('[]')) as features_json,
        hikes.published_on,
        hikes.updated_on,
        coalesce(hikes.directions_json, json('[]')) as directions_json,
        coalesce(hikes.description_json, json('[]')) as description_json,
        coalesce(
            hikes.public_transport_json, json('[]')
        ) as public_transport_json,
        hikes.has_published_route,
        hikes.gpx,
        hikes.parse_problems_json,
        hikes._loaded_at
    from hikes
    left join slugs
        on
            lower({{ python_strip("coalesce(hikes.difficulty, '')") }})
            = slugs.difficulty_label
)

select
    *,
    -- hike_problems(), in its order and its words (SH02).
    to_json(
        list_filter(
            [
                case
                    when not has_start
                        then
                            'no GPS coordinate on the page'
                            || ' - a route has nowhere to start from'
                end,
                case
                    when json_array_length(description_json) = 0
                        then
                            'no Description card - nothing to build a route'
                            || ' from and nothing to print'
                end,
                case
                    when stated_miles is null
                        then 'no stated Length to check a built route against'
                end,
                case
                    when route_type is null
                        then
                            'no Route Type, so whether the walk closes back'
                            || ' on itself is unknown'
                end,
                case
                    when json_array_length(features_json) = 0
                        then 'no Features tags'
                end,
                case
                    when author is null
                        then
                            'no Author - nobody''s name to carry with the'
                            || ' write-up'
                end
            ],
            lambda problem: problem is not null
        )
    ) as problems_json
from read_hikes
