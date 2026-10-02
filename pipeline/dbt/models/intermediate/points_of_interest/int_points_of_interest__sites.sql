{{ config(materialized='table') }}
-- Which site each POI belongs to, if any, and its role in it: a shelter with
-- its privy, campsites and water, modelled as one place with parts (#523,
-- features/POI_SITES.md), published as site_id, site_role and site_name. One
-- row per POI; the three are null on a POI in no site, which is most of them.
--
-- THE A.T. FAMILY: lib/poi_sites.py's group_sites() (PO18), the same two
-- passes in the same order. First every privy, campsite and water point
-- folds into its best SHELTER; then the campsites no shelter claimed anchor
-- the privies and water left over. A member's best anchor is one whose
-- base_name() it shares within var `poi_site_name_radius_m` (150 m) if any
-- is, preferring the anchor whose whole name the member's starts with, then
-- the nearest; else the nearest anchor within var
-- `poi_site_proximity_radius_m` (60 m); both radii are capped at
-- MAX_SITE_RADIUS_M, a mile. Ties go to the anchor the Python lists first,
-- its record order (the poi_sources seed's file_order, then the row's place
-- in its raw table), because sorted() is stable. Distances are
-- poi_distance_m(), lib/spurs.py's equirectangular formula, which the radii
-- were measured with. A site with no member is no site.
--
-- THE OTHER ORGANIZATIONS: lib/poi_sites.py's group_place_sites() (PO35),
-- for New York City's fountains and restrooms, where a park name says "same
-- property", not "same place". Waypoints of one type sharing a normalised
-- name fold single-link within var `poi_place_site_radius_m` (80 m), and the
-- pin is the member nearest the cluster's mean position, id breaking ties:
-- always a real fountain, never a centroid on a lawn. A waypoint with no
-- name keeps its own pin.
--
-- export_nearby_poi.py groups AFTER its network ring and closed-trailhead
-- pass, so that a site is composed of waypoints that ship, and so does this:
-- the ring is int_points_of_interest__in_corridor, upstream of this model,
-- and the closed-trailhead mark (int_points_of_interest__trailheads) removes
-- no waypoint, so the same waypoints are grouped.
{#- min(NAME_MATCH_RADIUS_M, MAX_SITE_RADIUS_M), and the proximity one, as
    _candidate_anchors() caps each gate; in SQL, so it is the same double. -#}
{%- set max_radius = var('poi_site_max_radius_m') -%}
{%- set name_radius =
    "least(" ~ var('poi_site_name_radius_m') ~ ", " ~ max_radius ~ ")" -%}
{%- set proximity_radius =
    "least(" ~ var('poi_site_proximity_radius_m') ~ ", " ~ max_radius ~ ")" -%}
{%- set lat_window =
    "((" ~ name_radius ~ " + 10) / " ~ var('poi_metres_per_degree') ~ ")" %}
with identified as (
    select * from {{ ref('int_points_of_interest__identified') }}
),

at_records as (
    select
        poi_id,
        poi_type,
        name,
        lat,
        lon,
        file_order,
        source_row,
        {{ poi_base_name('name') }} as base_name,
        {{ poi_normalise_name('name') }} as full_name
    from identified
    where phone_files = 'poi_by_type'
),

members as (
    select * from at_records
    where poi_type in ('privy', 'campsite', 'water')
),

first_pass_anchors as (
    select * from at_records
    where poi_type = 'shelter'
),

{%- macro candidates(members, anchors) %}
    select
        member.poi_id as member_id,
        anchor.poi_id as anchor_id,
        anchor.name as anchor_name,
        anchor.file_order as anchor_file_order,
        anchor.source_row as anchor_row,
        coalesce(anchor.base_name, '') != ''
        and anchor.base_name = member.base_name as same_base_name,
        coalesce(anchor.full_name, '') != ''
        and starts_with(coalesce(member.full_name, ''), anchor.full_name)
            as name_contained,
        {{ poi_distance_m(
            'member.lat', 'member.lon', 'anchor.lat', 'anchor.lon'
        ) }} as metres
    from {{ members }} as member
    inner join {{ anchors }} as anchor
        on
            member.poi_id != anchor.poi_id
            -- A latitude gap wider than the name radius plus 10 m is a
            -- distance wider than it, so no candidate is lost here.
            and abs(member.lat - anchor.lat) <= {{ lat_window }}
{%- endmacro %}

{%- macro best(candidates) %}
    select
        member_id,
        anchor_id,
        anchor_name
    from (
        select
            candidates.*,
            row_number() over (
                partition by member_id
                order by
                    case
                        when same_base_name and metres <= {{ name_radius }}
                            then 0
                        else 1
                    end,
                    case
                        when
                            same_base_name
                            and metres <= {{ name_radius }}
                            and name_contained
                            then 0
                        else 1
                    end,
                    metres,
                    anchor_file_order,
                    anchor_row
            ) as pick
        from {{ candidates }} as candidates
        where
            (same_base_name and metres <= {{ name_radius }})
            or metres <= {{ proximity_radius }}
    )
    where pick = 1
{%- endmacro %}

first_pass_candidates as (
    {{ candidates('members', 'first_pass_anchors') }}
),

first_pass as (
    {{ best('first_pass_candidates') }}
),

second_pass_anchors as (
    select * from at_records
    where
        poi_type = 'campsite'
        and poi_id not in (select first_pass.member_id from first_pass)
),

second_pass_members as (
    select * from members
    where
        poi_id not in (select first_pass.member_id from first_pass)
        and poi_id not in (
            select second_pass_anchors.poi_id from second_pass_anchors
        )
),

second_pass_candidates as (
    {{ candidates('second_pass_members', 'second_pass_anchors') }}
),

second_pass as (
    {{ best('second_pass_candidates') }}
),

folded as (
    select * from first_pass
    union all
    select * from second_pass
),

trail_sites as (
    select
        member_id as poi_id,
        anchor_id as site_id,
        'member' as site_role,
        anchor_name as site_name
    from folded
    union all
    select distinct
        anchor_id as poi_id,
        anchor_id as site_id,
        'anchor' as site_role,
        anchor_name as site_name
    from folded
),

place_records as (
    select
        poi_id,
        poi_type,
        name,
        lat,
        lon,
        {{ poi_normalise_name('name') }} as group_name
    from identified
    where
        phone_files = 'nearby_poi'
        and poi_type in ('water', 'privy')
        and coalesce(name, '') != ''
),

place_links as (
    select
        here.poi_id as from_id,
        there.poi_id as to_id
    from place_records as here
    inner join place_records as there
        on
            here.group_name = there.group_name
            and here.poi_type = there.poi_type
            and here.poi_id != there.poi_id
            and {{ poi_distance_m(
                'here.lat', 'here.lon', 'there.lat', 'there.lon'
            ) }} <= {{ var('poi_place_site_radius_m') }}
),

place_reach as (
    -- Single link: everything a waypoint reaches through links, itself
    -- included.
    with recursive reach as (
        select
            poi_id as start_id,
            poi_id as node_id
        from place_records
        union
        select
            reach.start_id,
            place_links.to_id
        from reach
        inner join place_links on reach.node_id = place_links.from_id
    )

    select
        start_id as poi_id,
        min(node_id) as cluster_id,
        count(*) as cluster_size
    from reach
    group by start_id
),

place_clusters as (
    select
        place_records.*,
        place_reach.cluster_id,
        avg(place_records.lat)
            over (partition by place_reach.cluster_id)
            as mid_lat,
        avg(place_records.lon)
            over (partition by place_reach.cluster_id)
            as mid_lon
    from place_records
    inner join place_reach on place_records.poi_id = place_reach.poi_id
    where place_reach.cluster_size >= 2
),

place_anchors as (
    select
        cluster_id,
        poi_id as anchor_id,
        name as anchor_name
    from (
        select
            place_clusters.*,
            row_number() over (
                partition by place_clusters.cluster_id
                order by
                    {{ poi_distance_m('lat', 'lon', 'mid_lat', 'mid_lon') }},
                    cast(place_clusters.poi_id as varchar)
            ) as pick
        from place_clusters
    )
    where pick = 1
),

place_sites as (
    select
        place_clusters.poi_id,
        place_anchors.anchor_id as site_id,
        case
            when
                place_clusters.poi_id = place_anchors.anchor_id
                then 'anchor'
            else 'member'
        end as site_role,
        place_anchors.anchor_name as site_name
    from place_clusters
    inner join
        place_anchors
        on place_clusters.cluster_id = place_anchors.cluster_id
),

sites as (
    select * from trail_sites
    union all
    select * from place_sites
)

select
    identified.*,
    sites.site_id,
    sites.site_role,
    sites.site_name
from identified
left join sites on identified.poi_id = sites.poi_id
