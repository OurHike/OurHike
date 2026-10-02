-- NYS OPRHP's park polygons (sources.json `oprhp_park_polygons`, the
-- NYS_Park_Polygons layer): every row, keyed and deduped (decision 40), with
-- nothing filtered and nothing joined. The one place this layer is staged,
-- for the places family: int_places__park_units groups these parcels into
-- the parks places.json lists (PL01-PL03), as export_places.py's load_parks()
-- does today.
--
-- ONE ROW PER PARCEL, NOT PER PARK, and nothing here groups them. Measured
-- 2026-10-02 against the live layer (858 polygons, last edited 2026-08-21):
-- 257 distinct Name, and 257 distinct MasterAreaID on 857 rows, with
-- Allegany's one parcel carrying none.
--
-- Key: GlobalID, unique on 858 of the 858 live rows and null on none
-- (measured 2026-10-02). It is ArcGIS's own row id, not a renumbering of the
-- fetch, so a reload keeps it.
--
-- EVERY COLUMN AS IT LANDED (`source.*`): which of them names the park, its
-- id and its unit is a fact on the layer's registry entry (`name_field`,
-- `id_field`, `unit_field`), and int_places__park_units reads each by the
-- name the entry gives it, as load_parks() does. A column renamed at OPRHP is
-- then a registry edit, never an edit here.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    --
    -- `rowid` is the row's place in the raw table, which extract/_warehouse.py
    -- fills in the order the layer's pages served the features: the order
    -- export_places.py's ST_Read reads the same file in (Reasoned, as
    -- stg_nynjtc__long_path has it). The park a point sits in, where two
    -- parks hold it, is the earlier one in that order.
    select
        rowid as source_row,
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('oprhp', 'raw_nysparks__oprhp_park_polygons') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'oprhp_park_polygons'",
            'globalid',
        ]) }} as park_polygon_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='park_polygon_key', order_by='source_row'
) }}
