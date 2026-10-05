-- Decision 77's one promise about an area in conditions/notices.json: the
-- published area covers the source's, every vertex and every edge, as the
-- phone reads it (the GeoJSON text the writer prints, edges straight in
-- longitude and latitude), so a route that met the source's area meets the
-- published one and the notice is shown rather than missed.
-- macros/notice_phone_geometry.sql is the writer's own shaping, run here on
-- made-up shapes rather than a build's rows, so the test fails only when the
-- SQL breaks the promise, never on one club's data in an hourly run.
--
-- The first shape is the one that bites: grown 100 m and simplified at
-- 100 m, GEOS's simplifier cuts back past its vertex at -96.993004
-- 38.007004, which is off the 5-decimal grid. Shown 2026-10-05 on dbt
-- 2.0.6: with the macro's join taken out, and again with
-- `notice_area_snap_allowance_m` set to 0, this test returned that vertex
-- and the pentagon's area; as committed it returns nothing. The others are
-- the shapes growing changes most: two parts that merge, a hole that closes,
-- a strip along a parallel 3 degrees long, and the parcel from
-- pub_conditions_notices' unit test. Returns one row per vertex outside its
-- published area, and one per shape whose area is not covered whole.
with sources as (
    select
        shapes.shape,
        st_makevalid(st_geomfromtext(shapes.wkt)) as geom
    from (
        values
        (
            'a pentagon the simplifier cuts past',
            'POLYGON ((-97 38.007, -96.999 38, -96.991 38, -96.991 38.006, '
            || '-96.993004 38.007004, -97 38.007))'
        ),
        (
            'two parcels 160 m apart',
            'MULTIPOLYGON (((-89.5 44.5, -89.49 44.5, -89.49 44.505, '
            || '-89.5 44.505, -89.5 44.5)), ((-89.488 44.5, -89.48 44.5, '
            || '-89.48 44.505, -89.488 44.505, -89.488 44.5)))'
        ),
        (
            'a ring with a hole 170 m across',
            'POLYGON ((-110 40, -109.98 40, -109.98 40.02, -110 40.02, '
            || '-110 40), (-109.991 40.009, -109.989 40.009, '
            || '-109.989 40.0105, -109.991 40.0105, -109.991 40.009))'
        ),
        (
            'a strip along a parallel',
            'POLYGON ((-100 45, -98.5 45, -97 45, -97 45.002, -98.5 45.002, '
            || '-100 45.002, -100 45))'
        ),
        (
            'the hunting parcel',
            'POLYGON ((-89.5 44.5, -89.4875 44.5, -89.475 44.500027, '
            || '-89.4625 44.5, -89.45 44.5, -89.45 44.51, -89.5 44.51, '
            || '-89.5 44.5))'
        )
    ) as shapes (shape, wkt)
),

published as (
    select
        shape,
        geom,
        st_geomfromgeojson(
            st_asgeojson(
                st_reverse(st_normalize({{ notice_phone_geometry('geom') }}))
            )
        ) as phone_geom
    from sources
),

vertices as (
    select
        published.shape,
        published.phone_geom,
        unnest(st_dump(st_points(published.geom))).geom as vertex
    from published
)

select
    shape,
    'vertex ' || st_astext(vertex) as outside
from vertices
where not st_covers(phone_geom, vertex)
union all
select
    shape,
    'area' as outside
from published
where not st_covers(phone_geom, geom)
