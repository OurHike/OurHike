{{ config(format='json_document', location='elevation_profile.json') }}
-- elevation_profile.json, the A.T. elevation profile the phone's ribbon draws
-- and counts climb over (client/src/lib/elevationProfile.ts), in the shape
-- export_elevation.py writes with json.dumps(records): a bare JSON array of
-- {"distance_mi", "elevation_ft"} records in mile order, `elevation_ft` null
-- where the DEM has no answer, and "part_start": true on the first sample of
-- each piece and on no other (#559). Python's separators too (", " and
-- ": "), so the file is today's byte for byte apart from one trailing
-- newline.
--
-- Measured 2026-10-02 through dbt 2.0.6, on ATC's live centerline and
-- half-mile markers of that day and a synthetic 3DEP-shaped DEM: 6,982,130
-- bytes against export_elevation.py's 6,982,129 from the same files, the
-- same bytes apart from the newline, 138,697 samples.
--
-- THE DOCUMENT IS ONE TEXT VALUE, written verbatim (phone_file's
-- `json_document` format: one row, one column under any name), because the
-- file is a top-level array, and COPY's JSON format writes every row as an
-- object of its columns, every column in every row: it can write neither a
-- bare array nor a record that leaves part_start out.
--
-- Each number is its decimal's text with the trailing zeros taken off and
-- one digit kept after the point: 12.340 -> 12.34, 2.000 -> 2.0. That is
-- what Python's repr() prints for the nearest double to a decimal of at most
-- 15 significant digits, which every value here is (at most 99999.999), and
-- none is small enough for repr's exponent form, which starts below 1e-4.
-- Empty, it writes [], as json.dumps([]) does: the aggregate below is one
-- row whatever the mart holds, so phone_file's when_empty never applies.
with profile as (
    select * from {{ ref('elevation') }}
    where line_id = 'AT'
),

records as (
    select
        seq,
        '{"distance_mi": '
        || regexp_replace(
            regexp_replace(cast(distance_mi as varchar), '0+$', ''), '\.$', '.0'
        )
        || ', "elevation_ft": '
        || coalesce(
            regexp_replace(
                regexp_replace(cast(elevation_ft as varchar), '0+$', ''),
                '\.$',
                '.0'
            ),
            'null'
        )
        || case when part_start then ', "part_start": true' else '' end
        || '}' as record
    from profile
)

select
    '[' || coalesce(string_agg(record, ', ' order by seq), '') || ']'
        as profile_json
from records
