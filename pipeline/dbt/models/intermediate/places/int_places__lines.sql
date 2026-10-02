{{ config(materialized='table') }}
-- The lines places.json measures, one row per published line:
-- export_places.py's load_lines() in SQL (PL06), with the name each line is
-- summed under for the long trails (PL07).
--
-- PL06, ONLY LINES THAT SHIP, PLUS THE A.T. load_lines() keeps a line from
-- nearby_trails.geojson or trails.geojson only where its `source` is one of
-- shipped_line_source_keys() (a network line source whose reaches_hikers is
-- true) or `centerline`, so a park never prints miles of a line no phone
-- receives. Here the lines are the trail_lines mart's, the rows both files
-- are written from, and of those:
-- - every `network` line (nearby_trails.geojson's), kept where its source may
--   publish (int_sources__publication). The mart already holds a source that
--   may not publish out, so the join changes nothing today; it keeps PL06's
--   rule in this family, where its unit test is, should the mart ever carry
--   a held-back line for review. may_publish equals reaches_hikers on all 64
--   registered sources, measured 2026-10-02, and every network line comes
--   from a network line source;
-- - the A.T.'s own line, source `centerline`, from trails.geojson.
--
-- THE A.T.'S SIDE TRAILS MEASURE NOTHING, AS TODAY, and that is a finding
-- rather than a rule anyone wrote down. trails.geojson carries the side
-- trails and spurs under `source: side_trails`, which is not a network
-- source, so shipped_line_source_keys() never names it and load_lines()
-- counts every side trail as held back, and main() prints "measure nothing:
-- reaches_hikers is false" for a source whose reaches_hikers is true. The
-- module docstring says the figure is over "what this run publishes", and
-- the side trails are published. Ported as it is, because today's exporter is
-- the parity reference; whether side trails should count is the
-- maintainer's question (the places ledger rows in pipeline/ELT.md).
--
-- THE A.T. IS MEASURED AT SIX DECIMALS, the mart's geom_geojson, which is
-- the line trails.geojson draws once decision 8 cuts it, where
-- export_places.py measures today's full-precision file. parity.py feeds the
-- Python the cut file, as the trails family's parity does. Measured
-- 2026-10-02 on 1,546 real places: the cut moves one lot's trailMiles by a
-- tenth, 17.8 to 17.9, and nothing else.
--
-- PL07's NAME. load_named_trails() sums the centerline under the one route
-- name its source owns (`owns_route_names`, read through owned_route_names():
-- the later registry entry wins a name two claim, and the first such name in
-- the order the names were first claimed is the one used), because
-- export_trails.py names each chain by ATC's own segment name and the trail
-- summed segment by segment would be forty rows under the threshold rather
-- than one over it. Every other line is summed under its own name. With no
-- owned name, the centerline keeps its own, as the Python's `if owned`
-- leaves it.
with trail_lines as (
    select * from {{ ref('trail_lines') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

registry as (
    select * from {{ ref('stg_registry__sources') }}
),

claims as (
    select
        source_key,
        file_row,
        unnest(
            cast(json_extract(entry, '$.owns_route_names') as varchar[])
        ) as route_name,
        generate_subscripts(
            cast(json_extract(entry, '$.owns_route_names') as varchar[]), 1
        ) as route_position
    from registry
),

routes as (
    select
        route_name,
        arg_max(source_key, file_row * 100000 + route_position) as owner_key,
        min(file_row * 100000 + route_position) as first_claim
    from claims
    group by route_name
),

-- One row always (an aggregate with no group), its name null where the
-- centerline owns none.
centerline_route as (
    select arg_min(route_name, first_claim) as route_name
    from routes
    where owner_key = 'centerline'
),

measured as (
    select
        trail_lines.trail_line_id,
        trail_lines.club,
        trail_lines.source_key,
        trail_lines._loaded_at,
        trail_lines.line_kind,
        trail_lines.name,
        trail_lines.geom_geojson
    from trail_lines
    inner join publication
        on trail_lines.source_key = publication.source_key
    where
        publication.may_publish
        and (
            trail_lines.line_kind = 'network'
            or trail_lines.source_key = 'centerline'
        )
)

select
    measured.trail_line_id,
    measured.club,
    measured.source_key,
    measured._loaded_at,
    measured.line_kind,
    measured.name,
    case
        when measured.source_key = 'centerline'
            then coalesce(centerline_route.route_name, measured.name)
        else measured.name
    end as trail_name,
    measured.geom_geojson
from measured
cross join centerline_route
