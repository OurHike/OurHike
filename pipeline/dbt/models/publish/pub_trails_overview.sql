{{ config(format='json', location='trails_overview.geojson') }}
-- trails_overview.geojson, the corridor-view sketch of the centerline (PR
-- #872 — Publish a corridor-view centerline, and ask for it before the app
-- has booted), in the shape export_trails.write_overview() writes: one
-- Feature,
-- its properties the two the client's line styling reads (`source` and
-- `blaze_color`, literally "centerline" and "White" there), and one
-- MultiLineString of every line of int_trail_lines__at_overview in order.
--
-- IT READS AN INTERMEDIATE, NOT THE MART: the sketch is simplified from the
-- centerline's 1 m segments, which the mart, one row per published line,
-- holds only merged into chains (int_trail_lines__at_overview says why the
-- chains would give other vertices). That model keeps only a centerline that
-- may publish.
with lines as (
    select * from {{ ref('int_trail_lines__at_overview') }}
)

-- The struct's fields as the file's top-level members: COPY's JSON format
-- writes a row's columns, so the writer selects them (ELT.md: the packed
-- writers select packed.*).
select collection.*  -- noqa: AM04
from (
    select
        {
            'type': 'FeatureCollection',
            'features': [
                json_object(
                    'type', 'Feature',
                    'properties', json_object(
                        'source', 'centerline', 'blaze_color', 'White'
                    ),
                    'geometry', json_object(
                        'type', 'MultiLineString',
                        'coordinates', coalesce(
                            to_json(
                                list(
                                    json(coordinates_json) order by line_order
                                )
                            ),
                            json('[]')
                        )
                    )
                )
            ]
        } as collection
    from lines
) as wrapped
