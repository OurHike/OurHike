{{ config(format='json', location='retired_poi.geojson') }}
-- retired_poi.geojson: the tombstone of every POI id the identity ledger has
-- retired (#673 — Tombstones and superseded_by: an upstream removal never
-- deletes a hiker's content), in the shape export_retired_poi.py's
-- tombstone() and build() write: a point where the place was, its id, type,
-- source and retirement, its name and successor only where it has one (a
-- name or successor that is absent is left out, never null), sorted by id.
with tombstones as (
    select * from {{ ref('points_of_interest') }}
    where phone_files = 'retired_poi'
)

select
    'FeatureCollection' as type,
    coalesce(
        list(
            json_object(
                'type', 'Feature',
                'geometry', cast(geom_geojson as json),
                -- A merge patch drops every member whose value is null.
                'properties', json_merge_patch(
                    '{}',
                    json_object(
                        'id', poi_id,
                        'poi_type', poi_type,
                        'source', source,
                        'retired', retired,
                        'name', nullif(name, ''),
                        'superseded_by', nullif(superseded_by, '')
                    )
                )
            )
            order by poi_id
        ),
        []
    ) as features
from tombstones
