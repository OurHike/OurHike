-- Every line a phone draws from a trail file, one row per published line
-- (pipeline/ELT.md, "The eleven marts"): the A.T.'s centerline chains, side
-- trails and spurs, which trails.geojson carries (export_trails.py today),
-- and every other organization's lines, which nearby_trails.geojson carries
-- (export_nearby_trails.py today). Keyed by the `id` both files publish.
--
-- Two halves, each already in the mart's columns:
-- int_trail_lines__at_published (the A.T.'s, tl-at) and
-- int_trail_lines__network_published (the network's, tl-net). Each branch
-- names every column, in the mart's order, so a half that drops or renames a
-- column fails here rather than reaching the union as a null, which
-- `union all by name` would make of it.
--
-- PUBLICATION: a row whose source may not publish never reaches the mart
-- (int_sources__publication, the one home of the rule). Today the A.T.'s
-- files ship with no licence gate at all, and publish.py holds
-- nearby_trails.geojson back whole when any of its sources carries
-- reaches_hikers: false (its "ONLY ARTIFACT ... WITH A LICENCE GATE"
-- comment); here a held-back source's lines are simply absent.
with lines as (
    select
        trail_line_id,
        club,
        source_key,
        _loaded_at,
        line_kind,
        feature_order,
        name,
        blaze_color,
        trail_status,
        trail_status_basis,
        closure_kind,
        closure_reason,
        closure_source,
        duplicate_of,
        geom_geojson,
        length_m,
        published_length_m,
        vertex_miles,
        monotonic_breaks,
        spur_length_ft,
        spur_destination_poi_id,
        spur_destination_distance_m,
        spur_junction_mile
    from {{ ref('int_trail_lines__at_published') }}
    union all
    select
        trail_line_id,
        club,
        source_key,
        _loaded_at,
        line_kind,
        feature_order,
        name,
        blaze_color,
        trail_status,
        trail_status_basis,
        closure_kind,
        closure_reason,
        closure_source,
        duplicate_of,
        geom_geojson,
        length_m,
        published_length_m,
        vertex_miles,
        monotonic_breaks,
        spur_length_ft,
        spur_destination_poi_id,
        spur_destination_distance_m,
        spur_junction_mile
    from {{ ref('int_trail_lines__network_published') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
)

select lines.*
from lines
inner join publication on lines.source_key = publication.source_key
where publication.may_publish
