-- Each relayed NWS alert's area, as int_warnings__nws_placed places it on
-- the weather squares (WN03): the polygon NWS drew, in NOAA's NBM grid units
-- (macro nbm_grid_units(), the transform lib/nbm_grid.py's overlapping()
-- applies), as WKT text, and the zones the alert names. x is a column and y
-- a row, so square (row, col) is the box (col, row) to (col + 1, row + 1).
--
-- A polygon NWS drew is the whole placement of its alert: storm and flood
-- warnings are drawn by the forecaster, and also list every county the
-- drawing touches for the systems that broadcast by county
-- (export_weather_alerts.py's docstring), so `is_drawn` decides which of
-- the two the placement reads. WKT, not a geometry column, because a dbt
-- 2.0.6 unit test cannot hold a geometry (the dbt skill, "Contracts, and
-- the traps in them"); DuckDB prints each coordinate at the shortest length
-- that reads back to the same double, so nothing is lost.
with relayed as (
    select * from {{ ref('int_warnings__nws_relayed') }}
)

select
    notice_id,
    alert_id,
    geom_geojson is not null as is_drawn,
    case
        when geom_geojson is not null
            then st_astext(
                {{ nbm_grid_units('st_geomfromgeojson(geom_geojson)') }}
            )
    end as grid_shape_wkt,
    affected_zones
from relayed
