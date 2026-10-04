{{ config(format='json', location='nearby_trails.geojson') }}
-- nearby_trails.geojson, every other organization's trail lines, in the
-- shape export_nearby_trails.py's records_to_geojson() writes (decision 44's
-- v1): one Feature per line, its properties in that function's order, then
-- the geometry. No phone reads this file since #1257
-- (client/src/lib/config.ts's NEARBY_TRAILS_TILES_KEY says why); it is what
-- nearby_trails.pmtiles is cut from, and build_trail_graph.py,
-- fetch_trail_water.py and the other readers export_nearby_trails.py's
-- docstring counts read it as the network's topology.
--
-- Reads the trail_lines mart's network rows (`line_kind = 'network'`),
-- which int_trail_lines__network_published gives it, then its club rows
-- (`line_kind = 'club'`, decision 64: int_trail_lines__club_published).
--
-- THE PROPERTIES, records_to_geojson()'s:
-- - `id`, `source`, `name` (null where nothing names the line, never left
--   out), `blaze_color`, `trail_status`;
-- - `length_miles`, the 1 m line's own length in EPSG:5070 miles
--   (`published_length_m`), rounded to 2 decimals as Python's round() does
--   (the printf cast, which the published model's header measures);
-- - `closure_kind` only on a closed line; `closure_reason` and
--   `closure_source` only on a section inside one of NYS Parks' closed areas
--   (int_trail_lines__network_area_closures: the area's reason verbatim, and
--   the closure layer's registry key, #1142), the reason only where the
--   steward wrote one; and `duplicate_of` only on a line that swallowed
--   another source's copy. Each is left out rather than null;
-- - `line_kind` 'club' on a club line only, the mark that it is drawn and
--   never routed: build_trail_graph.py refuses a feature carrying it, and
--   the phone's line sheet says so. A network line carries no `line_kind`,
--   so every record today's exporter writes is unchanged.
-- The shared-ground pairs' `concurrent_*` were never in this file.
--
-- THE ORDER is `feature_order`. map/style.ts draws by `line-sort-key`, not
-- by feature order, so a different order draws the same map (Reasoned from
-- its TRAIL_SORT_KEY_EXPRESSION comment).
with published as (
    select * from {{ ref('trail_lines', v=1) }}
    where line_kind in ('network', 'club')
),

features as (
    select
        feature_order,
        json_object(
            'type', 'Feature',
            'properties', json_merge_patch(
                json_object(
                    'id', trail_line_id,
                    'source', source_key,
                    'name', name,
                    'blaze_color', blaze_color,
                    'length_miles', cast(
                        printf('%.2f', published_length_m / 1609.344)
                        as double
                    ),
                    'trail_status', trail_status
                ),
                -- json_merge_patch() drops a member the patch sets to null,
                -- which is how an absent key stays absent.
                json_object(
                    'closure_kind', nullif(closure_kind, ''),
                    'closure_reason', nullif(closure_reason, ''),
                    'closure_source', nullif(closure_source, ''),
                    'duplicate_of', nullif(duplicate_of, ''),
                    'line_kind',
                    case when line_kind = 'club' then line_kind end
                )
            ),
            'geometry', cast(geom_geojson as json)
        ) as feature
    from published
)

select
    -- Quoted because `type` is a keyword to SQLFluff's RF04, and GeoJSON names
    -- the member so; quoting it is what RF06 calls unnecessary.
    'FeatureCollection' as "type",  -- noqa: RF06
    -- An empty network is [], never null (pipeline/ELT.md's pitfall 2).
    coalesce(list(feature order by feature_order), []) as features
from features
