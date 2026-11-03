{{ config(materialized='table') }}
-- The side trails trails.geojson publishes, after the clip and the 1 m pass,
-- each with what int_trail_lines__spurs says of it: a spur is a side trail
-- whose Type decodes to 3, and carries spurs.json's fields. Side trails are
-- never merged (export_trails.merge_chain_records): each is its own
-- destination and its own line-detail sheet (#134 — The line-detail sheet
-- that shows a spur's destination).
--
-- spurs.json is written from these rows, so it holds the spurs trails.geojson
-- draws. export_spurs.py also writes a spur with no line, or one past the
-- corridor, which no phone can reach: client/src/lib/lineDetail.ts reads
-- `spurs[line.id]` for a line the map drew. None does today (no live spur
-- lacks a line or lies past the corridor, 2026-10-02).
with simplified as (
    select * from {{ ref('int_trail_lines__at_simplified') }}
    where source_key not in ('centerline')
),

spurs as (
    select * from {{ ref('int_trail_lines__spurs') }}
)

select
    simplified.*,
    coalesce(spurs.is_spur, false) as is_spur,
    case when spurs.is_spur then spurs.length_ft end as spur_length_ft,
    spurs.destination_poi_id as spur_destination_poi_id,
    spurs.destination_distance_m as spur_destination_distance_m,
    spurs.junction_mile as spur_junction_mile,
    spurs.spur_record_json
from simplified
left join spurs on simplified.trail_segment_key = spurs.trail_segment_key
