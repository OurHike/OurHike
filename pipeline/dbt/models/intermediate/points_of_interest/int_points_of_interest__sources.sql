-- Every layer a POI file publishes from, one row each: the poi_sources
-- seed's (today's exporters' own layers, held to the Python by
-- tests/test_dbt_points_of_interest_parity.py), then each of decision 54's
-- wave 1 point layers int_points_of_interest__club_points carries, which no
-- exporter reads and so no seed transcribes. int_points_of_interest__classified
-- reads its layer facts from here.
--
-- A WAVE 1 LAYER is a `nearby_poi` layer, the file other organizations'
-- POIs ship in, whose rows arrive as records already typed (`unified`, as
-- the Long Path guide's do): int_points_of_interest__unioned writes each
-- row's poi_type, confidence, id and name into its properties, which the
-- classifier reads as they stand. Its file_order follows the seed's last,
-- in source_key order; no exporter's sort reads it. Its trail_id is the
-- club folder in capitals, the shape of export_nearby_poi.py's TRAIL_IDS
-- ('NYSDEC', 'USFS'). Reasoned: no phone code reads a nearby POI's
-- trail_id (client/src/lib/trailData.ts, read 2026-10-04).
with seeded as (
    select * from {{ ref('poi_sources') }}
),

club_layers as (
    select distinct
        source_key,
        club
    from {{ ref('int_points_of_interest__club_points') }}
),

last_order as (
    select max(file_order) as file_order from seeded
)

select
    source_key,
    file_order,
    club,
    source,
    phone_files,
    trail_id,
    id_field,
    name_field,
    type_field,
    poi_type,
    confidence,
    unified
from seeded
union all by name
select
    club_layers.source_key,
    cast(
        last_order.file_order
        + row_number() over (order by club_layers.source_key) as integer
    ) as file_order,
    club_layers.club,
    club_layers.source_key as source,
    'nearby_poi' as phone_files,
    upper(club_layers.club) as trail_id,
    'source_id' as id_field,
    'name' as name_field,
    cast(null as varchar) as type_field,
    cast(null as varchar) as poi_type,
    cast(null as varchar) as confidence,
    true as unified
from club_layers
cross join last_order
