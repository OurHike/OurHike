-- Where each relayed NWS alert lands on the weather squares (WN03):
-- export_weather_alerts.py's bake() and lib/nbm_grid.py's overlapping(), in
-- SQL. One row per relayed alert, with the trail squares it reaches; one that
-- reaches none is kept here with `reaches_trail` false, and
-- pub_conditions_weather_alerts leaves it out, as bake() does.
--
-- BY ITS POLYGON, when NWS drew one (int_warnings__nws_alert_shapes): the
-- trail squares any part of which is inside the polygon. Touching along an
-- edge or at a corner does not count, since no ground is shared; that is
-- shapely's `intersects and not touches`, and ST_Intersects and ST_Touches
-- answer the same on lib/nbm_grid.py's test shapes. A polygon that reaches
-- no trail square places the alert nowhere: its zones are not read instead.
--
-- OTHERWISE BY ITS ZONES: every trail square any zone in `affectedZones`
-- overlaps (int_warnings__weather_zones), the zone read as "<kind>/<id>" from
-- the URL as zone_keys() reads it. A zone the pinned zone files never heard
-- of, in a state they cover, is listed in `unknown_zones`, so a stale pin
-- shows up; a marine zone (ANZ335, a stretch of sea) is in no state and is
-- not listed (unknown_zones()).
--
-- `squares` is [[row, col], ...] in (row, col) order, JSON text, as bake()
-- writes `sorted(squares)`.
with alert_areas as (
    select * from {{ ref('int_warnings__nws_alert_shapes') }}
),

trail_squares as (
    select * from {{ ref('int_warnings__weather_squares') }}
),

zones as (
    select * from {{ ref('int_warnings__weather_zones') }}
),

-- The polygon path.
drawn as (
    select
        notice_id,
        st_geomfromtext(grid_shape_wkt) as grid_shape
    from alert_areas
    where is_drawn
),

drawn_squares as (
    select
        drawn.notice_id,
        trail_squares.square_row,
        trail_squares.square_col
    from drawn
    inner join trail_squares
        on
            st_intersects(
                drawn.grid_shape,
                st_makeenvelope(
                    trail_squares.square_col, trail_squares.square_row,
                    trail_squares.square_col + 1, trail_squares.square_row + 1
                )
            )
            and not st_touches(
                drawn.grid_shape,
                st_makeenvelope(
                    trail_squares.square_col, trail_squares.square_row,
                    trail_squares.square_col + 1, trail_squares.square_row + 1
                )
            )
),

-- The zone path, for every alert NWS drew no polygon for.
zone_items as (
    select
        notice_id,
        unnest(cast(
            coalesce(affected_zones, cast('[]' as json)) as json[]
        )) as zone_item
    from alert_areas
    where not is_drawn
),

zone_urls as (
    select
        notice_id,
        json_extract_string(zone_item, '$') as zone_url
    from zone_items
),

alert_zones as (
    select distinct
        notice_id,
        regexp_extract(zone_url, '/zones/([a-z]+)/([A-Z0-9]+)$', 1)
        || '/'
        || regexp_extract(zone_url, '/zones/([a-z]+)/([A-Z0-9]+)$', 2)
            as zone_key
    from zone_urls
    where regexp_matches(zone_url, '/zones/([a-z]+)/([A-Z0-9]+)$')
),

zone_squares as (
    select
        alert_zones.notice_id,
        unnest(cast(zones.squares as json[])) as square
    from alert_zones
    inner join zones on alert_zones.zone_key = zones.zone_key
),

-- The states the pinned files cover: an id's first two letters.
states as (
    select distinct left(zone_id, 2) as state_code
    from zones
    where is_known
),

unknown as (
    select
        alert_zones.notice_id,
        alert_zones.zone_key
    from alert_zones
    left join zones
        on alert_zones.zone_key = zones.zone_key and zones.is_known
    where
        zones.zone_key is null
        and left(split_part(alert_zones.zone_key, '/', 2), 2) in (
            select states.state_code from states
        )
),

reached as (
    select
        notice_id,
        square_row,
        square_col
    from drawn_squares
    union distinct
    select
        notice_id,
        cast(json_extract_string(square, '$[0]') as integer) as square_row,
        cast(json_extract_string(square, '$[1]') as integer) as square_col
    from zone_squares
),

per_alert as (
    select
        notice_id,
        count(*) as square_count,
        to_json(
            list([square_row, square_col] order by square_row, square_col)
        ) as squares
    from reached
    group by notice_id
),

unknown_per_alert as (
    select
        notice_id,
        to_json(list(zone_key order by zone_key)) as unknown_zones
    from unknown
    group by notice_id
)

select
    alert_areas.notice_id,
    alert_areas.alert_id,
    case when alert_areas.is_drawn then 'polygon' else 'zones' end
        as placed_by,
    coalesce(per_alert.square_count, 0) as square_count,
    coalesce(per_alert.square_count, 0) > 0 as reaches_trail,
    cast(coalesce(per_alert.squares, cast('[]' as json)) as varchar)
        as squares,
    cast(
        coalesce(unknown_per_alert.unknown_zones, cast('[]' as json))
        as varchar
    ) as unknown_zones
from alert_areas
left join per_alert on alert_areas.notice_id = per_alert.notice_id
left join unknown_per_alert
    on alert_areas.notice_id = unknown_per_alert.notice_id
