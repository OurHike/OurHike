{{ config(materialized='table') }}
{%- set decimals = var('trail_lines_network_coordinate_decimals') %}
-- The clubs' own trail lines as the trail_lines mart draws them, one row per
-- line that may draw, in the mart's 23 columns, with `line_kind` 'club'
-- (decision 64, the maintainer's poll of 2026-10-04: "draw now, route
-- later"). int_trail_lines__final unions it with the A.T.'s half and the
-- network's, and its publication join keeps only a line whose source may
-- publish.
--
-- DRAWN, NEVER ROUTED. A club line joins no routable network: the junction
-- graph reads the mart's `network` rows and the A.T.'s
-- (int_trail_network__routable), so no route, route distance, trail mile or
-- trail_graph*.json edge is made of one. It joins routing only after a
-- dedupe step has checked it against the lines already drawn, which is not
-- built: many club lines repeat a line already on the map (FLTC's and NCTA's
-- shared stretch, three copies of the Superior Hiking Trail), and a route
-- could jump between two copies. `line_kind` 'club' is the mark the phone
-- reads (nearby_trails.geojson's `line_kind`): the line sheet says the line
-- is a club's, drawn and not routed, and offers no day-hike point on it.
--
-- WHAT NEVER DRAWS, from int_trail_lines__club_lines' rules: a historic
-- alignment (`draws_as_trail` false), and a seasonal line (`season` set:
-- BLM's Iditarod, "primarily a winter trail"), which waits until a drawing
-- can say its season. A row with no geometry, or one that is not a line,
-- has nothing to draw.
--
-- THE GEOMETRY, as the network's: Douglas-Peucker at 1 m in EPSG:5070
-- (var trail_lines_network_navigation_tolerance_m, TL15), keeping the line
-- whole where the pass would leave a part with fewer than two distinct
-- vertices (simplify_records()' never-drop rule), then every vertex cut to
-- six decimals as Python's round() cuts it, keeping full precision where
-- the cut would leave a part degenerate. Both rules and their measurements
-- are int_trail_lines__network_navigation's and
-- int_trail_lines__network_published's headers; this repeats their SQL
-- rather than sharing it, so the network's parity-held models stay as they
-- are.
--
-- WHAT A CLUB LINE DOES NOT CARRY: a status (null, which is unknown, never
-- open: no club layer's status field is read here, and a layer with one is
-- held by its sources.json row until it is), a closure, a decoded blaze
-- ('Unknown', which the map draws in its neutral colour when blaze colours
-- are on), and every A.T. column. `feature_order` follows the network's
-- lines, so nearby_trails.geojson writes the network first, in its own
-- order, then the club lines by source and id.
--
-- BOTH LENGTHS ARE ON THE WGS84 ELLIPSOID, as the network's are
-- (int_trail_lines__network_published's header; decision 97, the
-- maintainer's poll of 2026-10-06): `length_m` of the line before the pass
-- and `published_length_m` of the 1 m line, which nearby_trails.geojson's
-- `length_miles` is rounded from, each by macros/geodesic_length_m.sql.
--
-- `navigation_wkt` is the 1 m line at full precision, which the overview
-- sketch is simplified from (int_trail_lines__club_overview), as the
-- network's sketch is from int_trail_lines__network_navigation.
with club_lines as (
    select * from {{ ref('int_trail_lines__club_lines') }}
    where draws_as_trail and season is null and geom_wkt is not null
),

network as (
    select count(*) as network_lines
    from {{ ref('int_trail_lines__network_published') }}
),

lines as (
    select
        *,
        st_geomfromtext(geom_wkt) as geom
    from club_lines
    where
        st_geometrytype(st_geomfromtext(geom_wkt))
        in ('LINESTRING', 'MULTILINESTRING')
        and not st_isempty(st_geomfromtext(geom_wkt))
),

reduced as (
    select
        *,
        st_transform(
            st_simplify(
                st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true),
                {{ var('trail_lines_network_navigation_tolerance_m') }}
            ),
            'EPSG:5070',
            'EPSG:4326',
            always_xy := true
        ) as reduced
    from lines
),

navigation as (
    select
        *,
        case
            when
                coalesce(
                    not st_isempty(reduced)
                    and list_bool_and(
                        list_transform(
                            st_dump(reduced),
                            lambda part: (
                                st_xmin(struct_extract(part, 'geom'))
                                < st_xmax(struct_extract(part, 'geom'))
                            )
                            or (
                                st_ymin(struct_extract(part, 'geom'))
                                < st_ymax(struct_extract(part, 'geom'))
                            )
                        )
                    ),
                    false
                )
                then reduced
            else geom
        end as navigation_line
    from reduced
),

-- try_cast in both branches. A plain cast failed this model's unit test on
-- dbt 2.0.6 (2026-10-04: "Conversion Error: Expected ARRAY, but got
-- DOUBLE: -72.9"), a LineString's coordinates cast to three levels of list
-- in the branch its row never takes, where int_trail_lines__network_published's
-- plain cast passes its own. Why is not settled; DuckDB folding a CASE over
-- the unit test's literal rows branch by branch is a guess. try_cast gives
-- null in the branch not taken, and the taken branch is the same cast.
parts as (
    select
        *,
        st_geometrytype(navigation_line) = 'MULTILINESTRING' as is_multi,
        case
            when st_geometrytype(navigation_line) = 'MULTILINESTRING'
                then try_cast(
                    json_extract(st_asgeojson(navigation_line), '$.coordinates')
                    as double[][][]
                )
            else [
                try_cast(
                    json_extract(st_asgeojson(navigation_line), '$.coordinates')
                    as double[][]
                )
            ]
        end as full_parts
    from navigation
),

rounded as (
    select
        *,
        list_transform(
            full_parts,
            lambda part: list_transform(
                part,
                lambda point: list_transform(
                    point,
                    lambda coordinate: cast(
                        printf('%.{{ decimals }}f', coordinate) as double
                    )
                )
            )
        ) as cut_parts
    from parts
),

chosen as (
    select
        *,
        case
            when
                list_bool_and(
                    list_transform(
                        cut_parts, lambda part: len(list_distinct(part)) >= 2
                    )
                )
                then cut_parts
            else full_parts
        end as chosen_parts
    from rounded
)

select
    chosen.source_key || ':' || chosen.trail_segment_key as trail_line_id,
    chosen.club,
    chosen.source_key,
    chosen._loaded_at,
    'club' as line_kind,
    network.network_lines - 1
    + row_number()
        over (order by chosen.source_key, chosen.trail_segment_key)
        as feature_order,
    nullif(trim(chosen.name), '') as name,
    'Unknown' as blaze_color,
    cast(null as varchar) as trail_status,
    cast(null as varchar) as trail_status_basis,
    cast(null as varchar) as closure_kind,
    cast(null as varchar) as closure_reason,
    cast(null as varchar) as closure_source,
    cast(null as varchar) as duplicate_of,
    cast(
        json_object(
            'type',
            case
                when chosen.is_multi then 'MultiLineString' else 'LineString'
            end,
            'coordinates',
            case
                when chosen.is_multi then to_json(chosen.chosen_parts)
                else to_json(list_extract(chosen.chosen_parts, 1))
            end
        ) as varchar
    ) as geom_geojson,
    {{ geodesic_length_m(
        "st_transform(chosen.geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)"
    ) }} as length_m,
    {{ geodesic_length_m(
        "st_transform(chosen.navigation_line, 'EPSG:4326', 'EPSG:5070', always_xy := true)"
    ) }} as published_length_m,
    cast(null as double[]) as vertex_miles,
    cast(null as integer) as monotonic_breaks,
    cast(null as double) as spur_length_ft,
    cast(null as varchar) as spur_destination_poi_id,
    cast(null as integer) as spur_destination_distance_m,
    cast(null as double) as spur_junction_mile,
    st_astext(chosen.navigation_line) as navigation_wkt
from chosen
cross join network
