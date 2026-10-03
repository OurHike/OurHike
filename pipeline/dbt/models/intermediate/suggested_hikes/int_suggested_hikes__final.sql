-- int_suggested_hikes__final: the suggested hikes mart's rows before their row
-- dates, every contracted column but _first_seen_at and _changed_at. This is
-- what models/marts/suggested_hikes/suggested_hikes.sql held until decision 57;
-- int_suggested_hikes__history snapshots it, and the mart reads that snapshot.
--
-- The hikes a phone is offered, one row each, keyed by the id it publishes
-- under (`hike_id`): two kinds, told apart by the phone file each goes to.
--
-- `phone_file` 'suggested_hikes': a hike somebody wrote up, today NYNJTC's
-- Hike Finder export, whose route ships (int_suggested_hikes__routed: graded,
-- not rejected, and a published track re-walked within its tolerance), in
-- hike-number order, with every field export_suggested_hikes.py's record_for()
-- gives it and the shelf record and detail it splits into
-- (int_suggested_hikes__records). pub_suggested_hikes writes the shelf from
-- these and pub_suggested_hikes_detail each hike's detail.
--
-- `phone_file` 'highlights': a stretch of the A.T. somebody says is worth
-- going to, from OurHike's curated reference/highlights.json, every row that
-- resolved against the published POIs (int_suggested_hikes__highlights), in
-- the file's order. pub_highlights writes highlights.json from these.
--
-- Only rows whose source may publish (int_sources__publication, the one home
-- of may_publish): `nynjtc_hike_finder` publishes on the registry's
-- reaches_hikers, as export_suggested_hikes.py's own check does, and
-- `ourhike_highlights` on its row of unregistered_publishing_sources, as
-- export_highlights.py publishes today.
--
-- THE SAFETY FIELDS (_suggested_hikes__models.yml has each test):
-- - SH08, the climb: `climb_gain_ft` and `climb_loss_ft` are both null where
--   the walk was never priced, never 0, and Naismith reads them with no
--   descent credit (client/src/lib/naismith.ts), left so;
-- - SH09, the photograph: only from the person-confirmed join, all three of
--   its url, credit and licence or none, the url a sha256 bucket key;
-- - SH10, the publication: only with a named author, and no `hikerNote`
--   column at all, because that field's contract is that a person checked
--   the hike, and nobody has checked these; `author_name`, the steward the
--   card credits, on every hike;
-- - the route's provenance and grade on every hike, so a generated line is
--   never drawn with its provenance still in flight.
-- Highlights store nothing derived (SH14): no length, ascent or time.
with records as (
    select * from {{ ref('int_suggested_hikes__records') }}
),

highlights as (
    select * from {{ ref('int_suggested_hikes__highlights') }}
    where problem is null
),

publication as (
    select source_key from {{ ref('int_sources__publication') }}
    where may_publish
),

written_up as (
    select
        records.hike_id,
        'suggested_hikes' as phone_file,
        records.hike_number as list_position,
        'nynjtc' as club,
        records.source_key,
        records._loaded_at,
        records.name,
        records.hike_number,
        records.miles,
        records.climb_gain_ft,
        records.climb_loss_ft,
        records.difficulty,
        records.published_difficulty,
        records.author_kind,
        records.author_name,
        records.photo_url,
        records.photo_credit,
        records.photo_licence,
        records.segments,
        records.route_provenance,
        records.route_grade,
        records.route_notes,
        records.features,
        records.region,
        records.park,
        records.estimated_hours,
        records.dogs,
        records.route_type,
        records.closed,
        records.source_url,
        records.published_miles,
        records.overview,
        records.description,
        records.trails,
        records.has_start,
        records.start_lat,
        records.start_lon,
        records.start_basis,
        records.published_on,
        records.updated_on,
        records.directions,
        records.public_transport,
        records.content_licence,
        records.measured_miles,
        records.measured_note,
        records.publication_submitted_by,
        records.track_reproduction,
        cast(null as varchar) as highlight_note,
        cast(null as varchar) as highlight_reviewed,
        cast(null as json) as highlight_legs,
        cast(null as varchar) as section_club,
        cast(records.shelf_json as json) as shelf_record,
        cast(records.detail_json as json) as detail_record,
        cast(null as json) as highlight_record
    from records
    inner join publication on records.source_key = publication.source_key
),

highlight_rows as (
    select
        highlights.*,
        'ourhike_highlights' as source_key
    from highlights
),

curated as (
    select
        highlight_rows.highlight_id as hike_id,
        'highlights' as phone_file,
        highlight_rows.file_row as list_position,
        'ourhike' as club,
        highlight_rows.source_key,
        highlight_rows._loaded_at,
        highlight_rows.highlight_name as name,
        cast(null as bigint) as hike_number,
        cast(null as double) as miles,
        cast(null as integer) as climb_gain_ft,
        cast(null as integer) as climb_loss_ft,
        cast(null as varchar) as difficulty,
        cast(null as varchar) as published_difficulty,
        cast(null as varchar) as author_kind,
        cast(null as varchar) as author_name,
        cast(null as varchar) as photo_url,
        cast(null as varchar) as photo_credit,
        cast(null as varchar) as photo_licence,
        cast(null as json) as segments,
        cast(null as varchar) as route_provenance,
        cast(null as varchar) as route_grade,
        cast(null as json) as route_notes,
        cast(null as json) as features,
        cast(null as varchar) as region,
        cast(null as varchar) as park,
        cast(null as double) as estimated_hours,
        cast(null as varchar) as dogs,
        cast(null as varchar) as route_type,
        cast(null as boolean) as closed,
        cast(null as varchar) as source_url,
        cast(null as double) as published_miles,
        cast(null as json) as overview,
        cast(null as json) as description,
        cast(null as json) as trails,
        cast(null as boolean) as has_start,
        cast(null as double) as start_lat,
        cast(null as double) as start_lon,
        cast(null as varchar) as start_basis,
        cast(null as varchar) as published_on,
        cast(null as varchar) as updated_on,
        cast(null as json) as directions,
        cast(null as json) as public_transport,
        cast(null as varchar) as content_licence,
        cast(null as double) as measured_miles,
        cast(null as varchar) as measured_note,
        cast(null as varchar) as publication_submitted_by,
        cast(null as varchar) as track_reproduction,
        highlight_rows.note as highlight_note,
        highlight_rows.reviewed as highlight_reviewed,
        cast(highlight_rows.legs_json as json) as highlight_legs,
        highlight_rows.club as section_club,
        cast(null as json) as shelf_record,
        cast(null as json) as detail_record,
        cast(highlight_rows.record_json as json) as highlight_record
    from highlight_rows
    inner join publication on highlight_rows.source_key = publication.source_key
)

select * from written_up
union all by name
select * from curated
