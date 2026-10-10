{{ config(materialized='table') }}
-- Every unioned row that does not ship, with the first reason why: what
-- export_poi.py's log and export_nearby_poi.py's per-source `dropped` stats
-- count, as rows a reviewer can read. One row per dropped unioned row.
-- With the mart's rows that come from the union, it accounts for every
-- unioned row (assert_points_of_interest_accounts_for_every_unioned_row).
--
-- Three stages drop, in the order the rules run:
-- 1. int_points_of_interest__classified: no geometry, not a point, an icon
--    or value that is not a published type, a named exclusion (its
--    `drop_reason`);
-- 2. int_points_of_interest__publishable: the organization's own public flag
--    says internal (DEC's PUBLICUSE), or the source may not publish
--    (int_sources__publication);
-- 3. int_points_of_interest__in_corridor: an A.T.-family row outside the
--    corridor and its network ring, or another organization's amenity
--    outside the ring and every park boundary its layer names;
-- 4. int_points_of_interest__reached: an OSM water point a hiker could not
--    reach, with its verdict's reason, or with no verdict at all;
-- 5. int_points_of_interest__deduplicated: an OSM water point within 25 m
--    of an opentrail water point.
-- Stages 4 and 5 are read together, as the corridor's rows the dedupe does
-- not hold, told apart by the verdict: one parent fewer, under the project
-- evaluator's join threshold.
with classified as (
    select * from {{ ref('int_points_of_interest__classified') }}
),

publishable as (
    select
        poi_key,
        phone_files
    from {{ ref('int_points_of_interest__publishable') }}
),

in_corridor as (
    select poi_key from {{ ref('int_points_of_interest__in_corridor') }}
),

verdicts as (
    select
        poi_key,
        reachable,
        reason
    from {{ ref('int_points_of_interest__osm_water_verdicts') }}
),

deduplicated as (
    select poi_key from {{ ref('int_points_of_interest__deduplicated') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

refused_publication as (
    select
        classified.poi_key,
        case
            when not coalesce(publication.may_publish, false)
                then
                    'the source may not publish ('
                    || coalesce(
                        publication.publication_rule, 'no publication row'
                    )
                    || ')'
            else
                'not public: '
                || json_extract_string(
                    classified.registry_entry, '$.public_field'
                )
                || ' is not '
                || coalesce(
                    json_extract_string(
                        classified.registry_entry, '$.public_value'
                    ),
                    'Y'
                )
        end as drop_reason
    from classified
    left join publication on classified.source_key = publication.source_key
    where
        classified.drop_reason is null
        and classified.poi_key not in (
            select publishable.poi_key from publishable
        )
),

outside_corridor as (
    select
        publishable.poi_key,
        case
            when publishable.phone_files = 'poi_by_type'
                then
                    'outside the A.T. corridor and further than '
                    || '{{ var("poi_network_ring_feet") }} ft from a '
                    || 'published line'
            else
                'further than {{ var("poi_network_ring_feet") }} ft from a '
                || 'published line, and inside no park boundary its layer names'
        end as drop_reason
    from publishable
    where
        publishable.poi_key not in (
            select in_corridor.poi_key from in_corridor
        )
),

unreached as (
    -- Only OSM water drops past the corridor: a point the reach gate let
    -- through is a twin the dedupe dropped, and any other was not reachable.
    select
        in_corridor.poi_key,
        case
            when verdicts.reachable
                then
                    'an OSM twin of an opentrail water point, within '
                    || '{{ var("poi_water_dedup_radius_m") }} m'
            else
                'unreachable (#749): '
                || coalesce(verdicts.reason, 'no reachability verdict')
        end as drop_reason
    from in_corridor
    left join verdicts on in_corridor.poi_key = verdicts.poi_key
    where
        in_corridor.poi_key not in (
            select deduplicated.poi_key from deduplicated
        )
),

reasons as (
    select
        poi_key,
        drop_reason
    from classified
    where drop_reason is not null
    union all
    select * from refused_publication
    union all
    select * from outside_corridor
    union all
    select * from unreached
)

select
    classified.poi_key,
    classified.source_key,
    classified.source,
    classified.phone_files,
    classified.derived_id,
    classified.name,
    classified.poi_type,
    reasons.drop_reason,
    classified._loaded_at
from reasons
inner join classified on reasons.poi_key = classified.poi_key
