{{ config(format='json', location='trail_miles.json') }}
-- depends_on: {{ ref('pub_trails_geojson') }}
--
-- trail_miles.json, the A.T. mile of every centerline vertex of
-- trails.geojson (#1192 — A returning hiker's launch freezes for ten
-- seconds while every waypoint is placed on the trail, on the main
-- thread), from the trail_lines mart's chains, in the shape
-- export_trails.write_trail_miles() writes: `format`, then `trails_sha256`
-- second, because client/src/lib/trailData.ts finds it with one regular
-- expression in the file's first 512 bytes; then `axis`, `decimals`,
-- `feature_count`, `vertex_count`, and `miles`, each chain's id to its
-- vertex miles, in the chains' order.
--
-- trails_sha256 IS THE HASH OF THE BYTES pub_trails_geojson WROTE, read back
-- from the file, so the pair cannot disagree: the phone stores the miles only
-- when it equals the published hash of the trails.geojson it verified, and
-- measures the line itself otherwise (trailData.ts's fetchTrailMiles). The
-- depends_on line above runs this writer after that one. It never equals
-- export_trails.py's, whose trails.geojson has other bytes (decision 8).
--
-- `axis` keeps export_trails.py's literal: int_trail_lines__mile_axis is
-- export_elevation.calibrated_trail_axis in SQL, equal on ATC's 562 live
-- pieces (its models' headers have the run), and nothing on the phone reads
-- the field.
with chains as (
    select * from {{ ref('trail_lines') }}
    where line_kind = 'centerline' and vertex_miles is not null
)

select packed.*
from (
    select
        {
            'format': 1,
            'trails_sha256': (
                select sha256(content)
                from read_blob('{{ var("processed_dir") }}/trails.geojson')
            ),
            'axis': 'export_elevation.calibrated_trail_axis',
            'decimals': {{ var('trail_lines_mile_decimals') }},
            'feature_count': count(*),
            'vertex_count': cast(coalesce(sum(len(vertex_miles)), 0) as bigint),
            'miles': coalesce(
                to_json(
                    map_from_entries(
                        list(
                            { 'k': trail_line_id, 'v': vertex_miles }
                            order by feature_order
                        )
                    )
                ),
                json('{}')
            )
        } as packed
    from chains
) as wrapped
