-- The hikes a phone is offered, one row each, keyed by the id it publishes
-- under (`hike_id`): two kinds, told apart by the phone file each goes to.
--
-- `phone_file` 'suggested_hikes': a hike somebody wrote up, today NYNJTC's
-- Hike Finder export, whose route ships (int_suggested_hikes__routed: graded,
-- not rejected, and a published track re-walked within its tolerance), in
-- hike-number order, with every field export_suggested_hikes.py's record_for()
-- gives it. pub_suggested_hikes writes the shelf from these and
-- pub_suggested_hikes_detail each hike's detail.
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
with hikes as (
    select * from {{ ref('int_suggested_hikes__hike_finder') }}
),

routed as (
    select * from {{ ref('int_suggested_hikes__routed') }}
),

photos as (
    select * from {{ ref('int_suggested_hikes__photos') }}
),

highlights as (
    select * from {{ ref('int_suggested_hikes__highlights') }}
    where problem is null
),

registry as (
    select
        source_key,
        -- source.get("steward") or source.get("attribution")
        coalesce(nullif(steward, ''), nullif(attribution, '')) as steward
    from {{ ref('stg_registry__sources') }}
),

publication as (
    select source_key from {{ ref('int_sources__publication') }}
    where may_publish
),

hike_rows as (
    select
        hikes.*,
        '{{ var("suggested_hikes_source_key") }}' as source_key
    from hikes
),

written_up as (
    select
        hike_rows.hike_id,
        'suggested_hikes' as phone_file,
        hike_rows.hike_number as list_position,
        'nynjtc' as club,
        hike_rows.source_key,
        hike_rows._loaded_at,
        hike_rows.name,
        hike_rows.hike_number,
        cast(routed.miles_json as double) as miles,
        routed.climb_gain_ft,
        routed.climb_loss_ft,
        hike_rows.difficulty_slug as difficulty,
        hike_rows.difficulty as published_difficulty,
        '{{ var("suggested_hikes_author_kind") }}' as author_kind,
        registry.steward as author_name,
        photos.photo_url,
        photos.photo_credit,
        photos.photo_licence,
        cast(routed.segments_json as json) as segments,
        routed.provenance as route_provenance,
        routed.grade as route_grade,
        cast(routed.route_notes_json as json) as route_notes,
        hike_rows.features_json as features,
        hike_rows.region,
        hike_rows.park,
        hike_rows.estimated_hours,
        hike_rows.dogs,
        hike_rows.route_type,
        routed.route_closed as closed,
        hike_rows.source_url,
        hike_rows.stated_miles as published_miles,
        -- [summary] if summary else []
        case
            when coalesce(hike_rows.summary, '') != ''
                then json_array(hike_rows.summary)
            else json('[]')
        end as overview,
        hike_rows.description_json as description,
        cast(routed.trails_json as json) as trails,
        hike_rows.has_start,
        hike_rows.start_lat,
        hike_rows.start_lon,
        hike_rows.start_label as start_basis,
        hike_rows.published_on,
        hike_rows.updated_on,
        hike_rows.directions_json as directions,
        hike_rows.public_transport_json as public_transport,
        '{{ var("suggested_hikes_content_licence") }}' as content_licence,
        cast(routed.miles_json as double) as measured_miles,
        -- The note holds apostrophes, doubled for the SQL literal.
        '{{ var("suggested_hikes_same_tread_note") | replace("'", "''") }}'
            as measured_note,
        -- A page that names nobody ships no publication block, never an
        -- empty one.
        case
            when coalesce(hike_rows.author, '') != '' then hike_rows.author
        end as publication_submitted_by,
        routed.track_reproduction,
        cast(null as varchar) as highlight_note,
        cast(null as varchar) as highlight_reviewed,
        cast(null as json) as highlight_legs,
        cast(null as varchar) as section_club
    from hike_rows
    inner join routed on hike_rows.hike_number = routed.hike_number
    inner join registry on hike_rows.source_key = registry.source_key
    inner join publication on hike_rows.source_key = publication.source_key
    -- photo_for(): the number after the record id's last colon.
    left join photos
        on cast(hike_rows.hike_number as varchar) = photos.hike_key
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
        highlight_rows.club as section_club
    from highlight_rows
    inner join publication on highlight_rows.source_key = publication.source_key
)

select * from written_up
union all by name
select * from curated
