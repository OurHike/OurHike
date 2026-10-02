-- INTERFACE: replace with tl-at's model
--
-- The A.T.'s published lines, the half of the trail_lines mart that
-- trails.geojson carries (export_trails.py today), as places reads them.
-- tl-at builds that half on branch wk/tl-at as int_trail_lines__at_published,
-- unioned into the trail_lines mart; at integration int_places__lines
-- reads the mart's rows in place of this model and
-- int_trail_lines__network_published, and this model is deleted.
--
-- THE INTERFACE, one row per published A.T. line, in the mart's columns and
-- types (models/marts/trail_lines/_trail_lines__models.yml on wk/tl-at):
-- - trail_line_id: the published `id`, `centerline:chain:<n>` or
--   `side_trails:<feature id>`;
-- - club, source_key (`centerline` or `side_trails`), _loaded_at;
-- - line_kind: `centerline`, `side_trail` or `spur`;
-- - name: the line's name as trails.geojson publishes it (a centerline
--   chain's is null unless its segments agree);
-- - geom_geojson: the line a phone draws, as GeoJSON text in lon/lat.
--
-- No rows until then, so places.json measures no A.T. line here, which is
-- export_places.py's own answer when trails.geojson is absent. It reads
-- stg_atc__centerline_segments, the A.T. line today's export_trails.py
-- reads, only so that it is not a root model.
select
    cast(null as varchar) as trail_line_id,
    cast(null as varchar) as club,
    cast(null as varchar) as source_key,
    cast(null as timestamptz) as _loaded_at,
    cast(null as varchar) as line_kind,
    cast(null as varchar) as name,
    cast(null as varchar) as geom_geojson
from {{ ref('stg_atc__centerline_segments') }}
where false
