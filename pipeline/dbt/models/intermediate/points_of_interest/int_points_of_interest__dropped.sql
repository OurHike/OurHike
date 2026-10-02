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
--    outside the ring and every park boundary its layer names.
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
