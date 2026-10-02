{{ config(format='json', location='trail_miles_v2.json') }}
-- depends_on: {{ ref('pub_trails_geojson') }}
--
-- v2/trail_miles.json (decision 44's v2 of the trail_lines mart): the A.T.
-- mile of every centerline vertex of trails.geojson, as v1's trail_miles.json
-- carries it, with each chain's list delta-coded in whole thousandths of a
-- mile (pipeline/ELT.md, "Making the download smaller", tier (a)).
-- client/src/lib/trailMiles.ts's parseTrailMiles() decodes it back to v1's
-- numbers, and parity.py's trail_miles_v2 family holds the two files equal,
-- chain by chain.
--
-- THE FILE: v1's header, in v1's order, with `format` 2, then
-- `milli_mile_deltas` where v1 has `miles`: each chain's id to its vertex
-- miles in thousandths, the first as itself and every later one as its step
-- from the vertex before. A step can be negative: monotonic_breaks counts the
-- steps that run against the chain's direction, and the phone splits a piece
-- at each (client/src/lib/trailPosition.ts), so the coding keeps them.
--
-- trails_sha256 STAYS SECOND, the hash of the trails.geojson bytes
-- pub_trails_geojson wrote, as v1's writer reads it: trails.geojson has no
-- v2 (its 6 decimals are already v1's, decision 8), so both versions of
-- this file name the one line file a release carries.
-- client/src/lib/trailData.ts finds the hash with one regular expression in
-- the file's first 512 bytes, which is why it is not moved.
with chains as (
    select * from {{ ref('trail_lines', v=2) }}
    where line_kind = 'centerline' and vertex_milli_miles is not null
),

trails_file as (
    select content from read_blob('{{ var("processed_dir") }}/trails.geojson')
),

coded as (
    select
        trail_line_id,
        feature_order,
        len(vertex_milli_miles) as vertex_count,
        list_transform(
            range(1, len(vertex_milli_miles) + 1),
            lambda i: list_extract(vertex_milli_miles, i)
            - coalesce(list_extract(vertex_milli_miles, i - 1), 0)
        ) as deltas
    from chains
)

select packed.*  -- noqa: AM04
from (
    select
        {
            'format': 2,
            'trails_sha256': (
                select sha256(trails_file.content) from trails_file
            ),
            'axis': 'export_elevation.calibrated_trail_axis',
            'decimals': {{ var('trail_lines_mile_decimals') }},
            'feature_count': count(*),
            'vertex_count': cast(coalesce(sum(vertex_count), 0) as bigint),
            'milli_mile_deltas': coalesce(
                to_json(
                    map_from_entries(
                        list(
                            { 'k': trail_line_id, 'v': deltas }
                            order by feature_order
                        )
                    )
                ),
                json('{}')
            )
        } as packed
    from coded
) as wrapped
