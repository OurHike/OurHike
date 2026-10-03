-- The points_of_interest mart's v2 (decision 44), for the eight
-- v2/poi_<type>.geojson files and v2/nearby_poi.geojson (stage 6 of #1793;
-- pipeline/ELT.md, "Making the download smaller", tier (a): "6 decimals" and
-- "one copy of each coordinate"). The same rows as v1, every column as v1
-- has it, except that a POI's position is held once, as `geom_geojson`, at 6
-- decimals; v1's `lat` and `lon` columns are gone.
--
-- WHICH NUMBER IS CUT. The one a v1 phone reads, which is the file's `lat`
-- and `lon` properties (client/src/lib/trailData.ts's readPois never reads
-- `geometry`): in poi_<type>.geojson that is GDAL's printing of the source's
-- double (macros/gdal_geojson.sql's gdal_geojson_double, which is not always
-- the double itself), and in nearby_poi.geojson and retired_poi.geojson the
-- double itself. Cutting the GDAL value rather than the source's own is what
-- makes a v2 coordinate exactly v1's at 6 decimals: the two differ by an ulp
-- or three, and where that straddles a half at the seventh decimal they
-- would round apart.
--
-- THE CUT IS PYTHON'S round(x, 6), as decision 8 cuts trails.geojson:
-- cast(printf('%.6f', x) as double), which matched Python's round() on every
-- one of 266,800 near-half doubles where DuckDB's round() missed 14,125
-- (.claude/skills/dbt/SKILL.md, "Contracts, and the traps in them"). A
-- point moves by at most 0.056 m per axis (half a millionth of a degree of
-- latitude; Reasoned). parity.py's poi_*_v2 families hold every v2 file's
-- coordinates to Python's round() of v1's properties.
--
-- Why a version: lat and lon are removed and geom_geojson's precision
-- changes, which decision 44 ships beside v1 (check_contract_versions.py).
-- v1 stays the latest version, so every unpinned ref still reads v1: the
-- places, suggested_hikes and spur-destination models among them.
with v1 as (
    select * from {{ ref('points_of_interest', v=1) }}
),

-- What the row's v1 file prints as its lat and lon properties.
printed as (
    select
        *,
        case
            when phone_files = 'poi_by_type'
                then {{ gdal_geojson_double('lon') }}
            else lon
        end as printed_lon,
        case
            when phone_files = 'poi_by_type'
                then {{ gdal_geojson_double('lat') }}
            else lat
        end as printed_lat
    from v1
)

select
    poi_id,
    poi_key,
    phone_files,
    poi_type,
    trail_id,
    source,
    source_feature_id,
    source_feature_id_json,
    name,
    cast(
        json_object(
            'type', 'Point',
            'coordinates',
            list_value(
                cast(printf('%.6f', printed_lon) as double),
                cast(printf('%.6f', printed_lat) as double)
            )
        ) as varchar
    ) as geom_geojson,
    mile,
    not_on_at,
    confidence,
    capacity,
    water_distance_ft,
    water_distance_source,
    description,
    nearby,
    -- PO36: the Long Path guide's own fields, on its waypoints, as v1's.
    lp_section,
    section_mile,
    placement,
    source_url,
    position_error_m,
    off_trail_miles,
    water_reliability,
    photo_key,
    photo_page_url,
    photo_author,
    photo_license,
    photo_taken,
    photos,
    site_id,
    site_role,
    site_name,
    trails_closed_within_m,
    retired,
    superseded_by,
    record_order,
    club,
    source_key,
    _loaded_at,
    -- v1's row dates (decision 57): v2's rows are v1's, printed for v2's
    -- files, so a change to a v1 column v2 drops moves them too.
    _first_seen_at,
    _changed_at
from printed
