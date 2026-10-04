{{ config(materialized='table') }}
-- The shape of every state a state-wide notice names (decision 76, the
-- maintainer's poll of 2026-10-04): seeds/notice_states.csv's states, from
-- the Census Bureau's TIGER/Line file (stg_census__states), simplified for a
-- phone. pub_conditions_notice_states writes them to
-- conditions/notice_states.json, where client/src/lib/plannedNotices.ts asks
-- one question of each: is a planned route in this state? No map draws one.
--
-- WHY A MARGIN, AND NOT THE SHAPE ALONE. A simplified edge is not the state
-- line. The phone counts a route vertex as in a state only when it is inside
-- the shape and farther than `edge_margin_m` from its edge, so a vertex near
-- an edge counts for no state: the notice is missed, and never shown for the
-- state next door. Where a simplified shape and the state differ, the
-- difference lies within the simplification's offset of the simplified edge
-- (Reasoned: each dropped stretch of the edge stays inside a band about the
-- line that replaced it), so a vertex past the margin is in the state
-- whenever the margin is larger than the worst offset.
-- assert_notice_state_shapes_stay_inside_their_edge_margin measures that
-- offset on every build and fails above the margin.
--
-- THE NUMBERS. Douglas-Peucker at 250 m (`notice_state_simplify_tolerance_m`)
-- with topology preserved, then 4 decimal places (at most 7.9 m more).
-- Measured 2026-10-04 against tl_2025_us_state.zip on the 14 states the seed
-- names: 9,322 vertices kept of 208,929, 184,420 bytes of shapes, and the
-- worst original vertex 341 m from its simplified edge, in Colorado (GEOS
-- moves a ring's start vertex too, so the worst offset passes the tolerance;
-- the other 13 states were 215 to 316 m). The margin, 500 m
-- (`notice_state_edge_margin_m`), leaves 159 m for what that measurement
-- cannot see. @unvalidated as enough: TIGER's own lines against the ground
-- ("the positional accuracy of these coordinates is not as great as the six
-- decimal places suggest", the file's metadata), the route's own trail line
-- against where a hiker walks, and NAD83 read as WGS84 by the phone (about
-- a metre or two in the lower 48). What would settle it is the distance from
-- surveyed state-line monuments to TIGER's line, which nobody here has
-- measured. A larger margin misses more hikes that walk near a state line;
-- 500 m costs a hike only the stretch within half a kilometre of one.
-- 250 m rather than 100 m (worst 119 m, 304,680 bytes) or 500 m (worst
-- 780 m, 116,393 bytes): the lead's choice on the design, 2026-10-04.
--
-- THE FRAME. Each state is simplified in its own equirectangular projection
-- (`frame`), because a straight line there is a straight line in longitude
-- and latitude, which is how the phone draws an edge (lib/noticeGeometry.ts
-- casts its rays on lon/lat as a plane); in an Albers projection a long
-- edge along a parallel is a curve, and its straight chord on the phone
-- would sit kilometres off it. The frame's true scale is the state's
-- latitude nearest the equator, where a degree of longitude is longest, so
-- its metres overstate every east-west distance elsewhere in the state and a
-- tolerance in them is at most that many metres on the ground (Reasoned).
--
-- TIGER's states run out over their coastal water, so a beach trail is
-- deep inside its state's shape and the margin costs it nothing.
with named as (
    select distinct unnest(string_split(states, ' ')) as state
    from {{ ref('notice_states') }}
),

states as (
    select
        census.state,
        census.state_name,
        census.geom,
        census._loaded_at
    from {{ ref('stg_census__states') }} as census
    inner join named on census.state = named.state
),

framed as (
    select
        *,
        '+proj=eqc +lat_ts='
        || cast(
            round(
                case
                    when st_ymin(geom) > 0 then st_ymin(geom)
                    when st_ymax(geom) < 0 then st_ymax(geom)
                    else 0
                end,
                3
            ) as varchar
        )
        || ' +lon_0=' || cast(round(st_x(st_centroid(geom)), 3) as varchar)
        || ' +datum=NAD83 +units=m +no_defs' as frame
    from states
),

simplified as (
    select
        *,
        st_reduceprecision(
            st_transform(
                st_simplifypreservetopology(
                    st_transform(geom, 'EPSG:4269', frame, always_xy := true),
                    {{ var('notice_state_simplify_tolerance_m') }}
                ),
                frame,
                'EPSG:4269',
                always_xy := true
            ),
            0.0001
        ) as phone_geom
    from framed
)

-- RFC 7946's ring order, as pub_conditions_notices writes a notice's area:
-- ST_Normalize winds a shell clockwise and ST_Reverse turns it round. No
-- geometry column leaves the model: dbt 2.0.6's driver cannot read one back
-- ("BinaryView is not supported for DuckDB", measured 2026-10-04 in this
-- model's unit test), so the offset test reads the original shape from
-- stg_census__states.
select
    state,
    state_name,
    frame,
    cast(st_asgeojson(st_reverse(st_normalize(phone_geom))) as json)
        as phone_geometry,
    cast({{ var('notice_state_simplify_tolerance_m') }} as double)
        as simplify_tolerance_m,
    cast({{ var('notice_state_edge_margin_m') }} as double) as edge_margin_m,
    _loaded_at
from simplified
