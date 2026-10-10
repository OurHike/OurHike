{{ config(materialized='table') }}
-- Every published POI with what export_poi.py attaches to it after the sites
-- and the water: its capacity and the nearby parts. One row per POI. The
-- sentence is int_points_of_interest__described's.
--
-- CAPACITY (PO13): how many a shelter sleeps, from
-- reference/shelter_capacity.json by published id, where the file states a
-- number (export_poi.py's load_capacities() and attach_capacity()). Absent
-- means nobody has said, never zero, and the points_of_interest mart refuses
-- a zero.
--
-- NEARBY (PO21, attach_nearby()): what a site's anchor publishes about the
-- parts around it, as JSON the phone writes the sentence from. Each member's
-- phrase (lib/poi_description.py's _privy_phrase() and _campsite_phrase(),
-- or "water"; the bare type with its article for any other) and its distance
-- from the anchor in feet, never below MIN_PART_FT and rounded to 0.1 ft as
-- Python rounds; a synthesized water member is skipped, because it sits on
-- the anchor. Then, for a shelter or campsite that is not a member and has
-- no real water part, ATC's own distance to water where it is no further
-- than the site radius, with its provenance as `source`, the one part whose
-- distance is a published figure rather than a measured position. Ordered
-- privy, water, campsite, then nearest first, then record order, as
-- nearby_parts()'s stable sort orders them.
{%- set m = 'member.properties' %}
with water as (
    select * from {{ ref('int_points_of_interest__water') }}
),

capacities as (
    select
        poi_id,
        capacity
    from {{ ref('base_greenbelly__shelter_capacity') }}
    where capacity is not null
),

privy_kinds as (
    select
        code,
        phrase
    from {{ ref('poi_description_terms') }}
    where vocabulary = 'privy_type'
),

member_parts as (
    select
        anchor.poi_id as anchor_id,
        member.poi_type,
        {{ poi_distance_m(
            'anchor.lat', 'anchor.lon', 'member.lat', 'member.lon'
        ) }} / {{ var('poi_metres_per_foot') }} as feet,
        case member.poi_type
            when 'privy'
                then
                    concat_ws(
                        ' ',
                        'a',
                        case
                            when {{ poi_coded(m, 'enclosure') }} = '2'
                                then 'multi-seat'
                        end,
                        privy_kind.phrase,
                        'privy',
                        case
                            when {{ poi_coded(m, 'enclosure') }} = '0'
                                then 'with no enclosure'
                        end
                    )
            when 'campsite'
                then
                    case
                        when
                            {{ poi_coded('member.properties', 'type') }} = '1'
                            then 'a group campsite' else
                            'a campsite'
                    end
            when 'water' then 'water'
            else
                case
                    when
                        left(member.poi_type, 1) in ('a', 'e', 'i', 'o', 'u')
                        then 'an '
                    else 'a '
                end
                || member.poi_type
        end as phrase,
        cast(null as varchar) as water_source,
        member.record_order as part_order
    from water as anchor
    inner join water as member
        on
            anchor.site_role = 'anchor'
            and member.site_role = 'member'
            and anchor.site_id = member.site_id
            and member.source != 'atc_csi'
    left join privy_kinds as privy_kind
        on
            member.poi_type = 'privy'
            and {{ poi_coded('member.properties', 'type') }} = privy_kind.code
    where anchor.phone_files = 'poi_by_type'
),

water_parts as (
    select
        water.poi_id as anchor_id,
        'water' as poi_type,
        cast(water.water_distance_ft as double) as feet,
        'water' as phrase,
        water.water_distance_source as water_source,
        9223372036854775807 as part_order
    from water
    where
        water.phone_files = 'poi_by_type'
        and water.poi_type in ('shelter', 'campsite')
        and coalesce(water.site_role, '') != 'member'
        and water.water_distance_ft is not null
        and water.water_distance_ft
        <= {{ var('poi_site_name_radius_m') }}
        / {{ var('poi_metres_per_foot') }}
        and not exists (
            select 1 from member_parts
            where
                member_parts.anchor_id = water.poi_id
                and member_parts.poi_type = 'water'
        )
),

parts as (
    select * from member_parts
    union all
    select * from water_parts
),

nearby as (
    select
        anchor_id,
        to_json(list(
            json_merge_patch(
                json_object(
                    'phrase', phrase,
                    'distance_ft',
                    {{ python_round(
                        'greatest(' ~ var('poi_nearby_min_part_ft') ~ ', feet)',
                        1
                    ) }}
                ),
                json_object('source', nullif(water_source, ''))
            )
            order by
                case poi_type
                    when 'privy' then 0
                    when 'water' then 1
                    when 'campsite' then 2
                    else 3
                end,
                feet,
                part_order
        )) as nearby
    from parts
    group by anchor_id
)

select
    water.*,
    capacities.capacity,
    nearby.nearby
from water
left join capacities
    on
        water.phone_files = 'poi_by_type'
        and water.poi_id = capacities.poi_id
left join nearby on water.poi_id = nearby.anchor_id
