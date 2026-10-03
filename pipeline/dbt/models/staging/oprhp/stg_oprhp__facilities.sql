-- NYS Parks' facility points as the extract lands them (extract/nysparks/
-- points_of_interest.py): 8,823 statewide, measured 2026-08-18, keyed and
-- deduplicated (decision 40), every column kept.
--
-- What publishes from this layer does so ROW BY ROW, and nothing here says
-- which rows. sources.json declares no layer-wide `poi_type`, because there
-- is none: 158 distinct `Sub_Asset` values, measured live 2026-08-27, of
-- which export_nearby_poi.py types thirteen through OPRHP_SUB_ASSET_TYPES
-- and ships the rest as nothing. That map is the poi_value_types seed now,
-- applied in int_points_of_interest__classified with the named exclusions
-- beside it.
--
-- THE EXCLUSIONS ARE THE PART THAT MATTERS. 136 'Water Spigot' and 15
-- 'Drinking Fountain' rows sit in that column, and both are held back as a
-- water holdback (sources.json's oprhp_water_holdback: no seasonal shutoff is
-- recorded anywhere). 'Mineral Spring', 'Water Tower' and 'Waterfall' are
-- also in the column and are not drinking water at all.
--
-- TWO PUBLIC FLAGS, AND THE OBVIOUS ONE IS THE WRONG ONE. `Public_` reads Y
-- on all 8,823 rows and discriminates nothing (measured 2026-08-27).
-- `ParksApp`, 5,822 Y / 3,000 N, is the entry's public_field, and it records
-- what OPRHP's own visitor app SHOWS rather than what exists on the ground,
-- so its N side ships at LOW confidence instead of being dropped (the
-- entry's public_flag_sets_confidence): filtering on it would discard every
-- one of OPRHP's 37 lean-tos, none of which are in that app.
--
-- `Name` is populated on 1,631 of 8,823 rows (18%) and the layer's own alias
-- flags it '(Legacy Field)'. `Facility` is populated on all 8,823 and is the
-- PARK's name, not the feature's.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        -- The row's place in the raw table, which extract/_warehouse.py fills
        -- in the order the upstream served it: the order a Python exporter
        -- reads the same file in, and so its tie-break (see the poi_sources
        -- seed's file_order).
        rowid as source_row,
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('oprhp', 'raw_nysparks__oprhp_facilities') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'oprhp_facilities'",
            'globalid',
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='objectid'
) }}
