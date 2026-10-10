-- int_places__final: the places mart's rows before their row dates, every
-- contracted column but _first_seen_at and _changed_at. This is what
-- models/marts/places/places.sql held until decision 57; int_places__history
-- snapshots it, and the mart reads that snapshot.
--
-- Every place a hiker can name before anything is downloaded, one row each:
-- the parks, towns, trailheads, parking areas and long trails places.json
-- lists (pipeline/ELT.md, "The eleven marts"), keyed by the id the file
-- publishes. int_places__resolved, typed: its JSON-text numbers cast back to
-- the doubles they are. pub_places writes places.json from it.
--
-- Only rows whose source may publish, from int_sources__publication, the one
-- home of may_publish. Each source was already held to it upstream (the park
-- layer in int_places__park_units, the lines in int_places__lines, the
-- waypoints by the points_of_interest mart); this join is the mart's own
-- statement of it.
--
-- THE SAFETY FIELDS, each a test in _places__models.yml:
-- - `state` is a postal code, and only where the source or its organization
--   states one (PL04): absent is unknown, never guessed;
-- - `trail_miles` is null exactly where nothing was measured (PL11), so an
--   unmeasured place never reads as a place with no trail.
with resolved as (
    select * from {{ ref('int_places__resolved') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
)

select
    resolved.place_id,
    resolved.place_order,
    resolved.kind,
    resolved.name,
    resolved.poi_id,
    resolved.category,
    resolved.state,
    resolved.within_park,
    cast(resolved.lon as double) as lon,
    cast(resolved.lat as double) as lat,
    cast(cast(resolved.bbox as json) as double[]) as bbox,
    cast(resolved.trail_miles as double) as trail_miles,
    resolved.trail_miles_measured,
    resolved.source,
    resolved.club,
    resolved.source_key,
    resolved._loaded_at
from resolved
inner join publication on resolved.source_key = publication.source_key
where
    publication.may_publish
    -- a place holding text DuckDB could not store (int_places__resolved's
    -- broken_text) is left out, never published with a column it lost
    and resolved.broken_text is null
