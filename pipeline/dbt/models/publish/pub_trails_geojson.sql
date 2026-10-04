{{ config(format='json', location='trails.geojson') }}
-- trails.geojson, the A.T.'s lines as the phone draws them (TL15's 1 m
-- pass, decision 8's 6 decimals), from the trail_lines
-- mart's A.T. rows: the centerline's chains, then the side trails and spurs,
-- in feature_order, as export_trails.py writes them. A FeatureCollection
-- named "trails", as GDAL's GeoJSON driver names it there, each feature's
-- properties `id`, `source`, `name` and `blaze_color`, and no feature-level
-- `id` member. The client reads the file only through MapLibre expressions
-- on `blaze_color` and `source`, and sniffs the `centerline:chain:` ids
-- (lib/trailShape.ts).
--
-- THE DELIBERATE DIFFERENCE, decision 8: the Python writes GDAL's digits;
-- this writes each coordinate cut to six decimals, as the mart holds it. The
-- bytes differ too, compact here and GDAL's spacing there, so
-- trail_miles.json's trails_sha256 names this file's bytes, never the
-- Python's.
with lines as (
    select * from {{ ref('trail_lines', v=1) }}
    where line_kind not in ('network', 'club')
)

-- The struct's fields as the file's top-level members: COPY's JSON format
-- writes a row's columns, so the writer selects them (ELT.md: the packed
-- writers select packed.*).
select collection.*  -- noqa: AM04
from (
    select
        {
            'type': 'FeatureCollection',
            'name': 'trails',
            -- An empty list is [], never null (pipeline/ELT.md's pitfall 2).
            'features': coalesce(
                list(
                    json_object(
                        'type', 'Feature',
                        'properties', json_object(
                            'id', trail_line_id,
                            'source', source_key,
                            'name', name,
                            'blaze_color', blaze_color
                        ),
                        'geometry', json(geom_geojson)
                    )
                    order by feature_order
                ),
                cast([] as json[])
            )
        } as collection
    from lines
) as wrapped
