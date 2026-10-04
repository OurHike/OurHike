{{ config(materialized='table') }}
-- The clubs' lines in network_overview.geojson's sketch (decision 64), one
-- row per club line the sketch keeps, in int_trail_lines__network_overview_
-- seam's columns, which int_trail_lines__network_overview_features groups
-- after the network's own.
--
-- THE SAME THREE PASSES as the network's sketch, on the club line's 1 m line
-- at full precision (int_trail_lines__club_published's navigation_wkt):
-- the coarse line at var trail_lines_network_overview_simplify_tolerance_m
-- (100 m) in EPSG:5070; the floor, which drops a coarse line whose bounding
-- box's diagonal is under var trail_lines_network_overview_min_feature_m
-- (one z5 pixel); and the seam's pass at
-- var trail_lines_network_overview_seam_tolerance_m. Each pass keeps the
-- line it was handed where it would leave a part with fewer than two
-- distinct vertices. Both constants are @unvalidated in their own comments
-- (export_nearby_trails.py's OVERVIEW_MIN_FEATURE_M and
-- NAMED_TRAIL_THRESHOLD_MILES).
--
-- NEVER A THROUGH ROUTE. A club line is haze in the sketch, whatever its
-- length: `through_route` is null on every row, so it never takes the
-- heavier far weight a through route draws at (map/style.ts's
-- NETWORK_OVERVIEW_FAR_WIDTH_EXPRESSION) and never counts toward one. Its
-- lines are not deduplicated against the network's, so summing them would
-- count one trail twice.
--
-- Only a line whose source may publish, as the trail_lines mart keeps it.
with club as (
    select * from {{ ref('int_trail_lines__club_published') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

published as (
    select
        club.*,
        st_geomfromtext(club.navigation_wkt) as navigation_line
    from club
    inner join publication on club.source_key = publication.source_key
    where publication.may_publish
),

reduced as (
    select
        *,
        st_transform(
            st_simplify(
                st_transform(
                    navigation_line, 'EPSG:4326', 'EPSG:5070', always_xy := true
                ),
                {{ var('trail_lines_network_overview_simplify_tolerance_m') }}
            ),
            'EPSG:5070',
            'EPSG:4326',
            always_xy := true
        ) as reduced
    from published
),

coarse as (
    select
        *,
        case
            when
                coalesce(
                    not st_isempty(reduced)
                    and list_bool_and(
                        list_transform(
                            st_dump(reduced),
                            lambda part: (
                                st_xmin(struct_extract(part, 'geom'))
                                < st_xmax(struct_extract(part, 'geom'))
                            )
                            or (
                                st_ymin(struct_extract(part, 'geom'))
                                < st_ymax(struct_extract(part, 'geom'))
                            )
                        )
                    ),
                    false
                )
                then reduced
            else navigation_line
        end as coarse_line
    from reduced
),

measured as (
    select
        *,
        st_transform(
            coarse_line, 'EPSG:4326', 'EPSG:5070', always_xy := true
        ) as coarse_m
    from coarse
),

kept as (
    select *
    from measured
    where
        sqrt(
            (st_xmax(coarse_m) - st_xmin(coarse_m))
            * (st_xmax(coarse_m) - st_xmin(coarse_m))
            + (st_ymax(coarse_m) - st_ymin(coarse_m))
            * (st_ymax(coarse_m) - st_ymin(coarse_m))
        )
        >= {{ var('trail_lines_network_overview_min_feature_m') }}
),

seam as (
    select
        *,
        st_transform(
            st_simplify(
                coarse_m,
                {{ var('trail_lines_network_overview_seam_tolerance_m') }}
            ),
            'EPSG:5070',
            'EPSG:4326',
            always_xy := true
        ) as seam_line
    from kept
)

select
    trail_line_id,
    source_key,
    blaze_color,
    trail_status,
    cast(null as varchar) as through_route,
    st_astext(
        case
            when
                coalesce(
                    not st_isempty(seam_line)
                    and list_bool_and(
                        list_transform(
                            st_dump(seam_line),
                            lambda part: (
                                st_xmin(struct_extract(part, 'geom'))
                                < st_xmax(struct_extract(part, 'geom'))
                            )
                            or (
                                st_ymin(struct_extract(part, 'geom'))
                                < st_ymax(struct_extract(part, 'geom'))
                            )
                        )
                    ),
                    false
                )
                then seam_line
            else coarse_line
        end
    ) as seam_wkt
from seam
