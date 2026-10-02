-- Each shipped Hike Finder hike as the phone reads it: every field
-- export_suggested_hikes.py's record_for() gives it, as a typed column the
-- mart carries, and the record itself, split by split_record() into its
-- shelf record and its detail (SH10, SH11), as JSON text. The mart takes the
-- columns and pub_suggested_hikes and pub_suggested_hikes_detail only gather
-- the records, so the shape a phone reads is unit-tested here, record by
-- record.
--
-- THE SHELF is SHELF_FIELDS (#1473 — The hike shelf is 85% of the cache
-- ceiling, and crossing it deletes the shelf rather than trimming it): what
-- lib/suggestedHikesData.ts reads off a shelf record, where the drawn line
-- came from (routeProvenance, routeGrade and routeNotes ride on the shelf so
-- a generated line is never drawn with its provenance still in flight), and
-- what a finder filters on. THE DETAIL is everything else, FLAT, never
-- nested: validDetail reads `url`, `publishedMiles` and `description` off
-- the top level of the record it is handed. The detail carries the hike's
-- own `id`, so one fetched alone can say which hike it is. Both keep
-- split_record()'s key order.
--
-- ABSENT, NEVER EMPTY. A hike with no confirmed photograph has no `photo`,
-- one whose walk was never priced no `climb` (SH08), one whose page names no
-- author no `publication` (SH10: validPublication refuses a block with no
-- submittedBy), and a generated route no `trackReproduction`. Each is built
-- in its place, and an absent one is removed by a json_merge_patch whose
-- patch names only that key, as null: a patch of `{}` leaves the record
-- whole, nulls and key order included, and a null-valued patch member
-- removes its key and touches no other (measured 2026-10-02, DuckDB 1.5.5).
-- A field the publisher left blank stays, as null, as record_for() writes
-- it. There is no `hikerNote`: that field's contract is that a person
-- checked the hike, and nobody has checked these.
--
-- `author` is the steward the registry names (`steward`, else
-- `attribution`), never the page's Author, who is the publication's
-- submittedBy: two authors, kept apart.
with hikes as (
    select * from {{ ref('int_suggested_hikes__hike_finder') }}
),

routed as (
    select * from {{ ref('int_suggested_hikes__routed') }}
),

photos as (
    select * from {{ ref('int_suggested_hikes__photos') }}
),

registry as (
    select
        source_key,
        -- source.get("steward") or source.get("attribution")
        coalesce(nullif(steward, ''), nullif(attribution, '')) as steward
    from {{ ref('stg_registry__sources') }}
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
        hike_rows.hike_number,
        hike_rows.source_key,
        hike_rows._loaded_at,
        hike_rows.name,
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
        -- `if author:`. A page that names nobody ships no publication block,
        -- never an empty one.
        case
            when coalesce(hike_rows.author, '') != '' then hike_rows.author
        end as publication_submitted_by,
        routed.track_reproduction
    from hike_rows
    inner join routed on hike_rows.hike_number = routed.hike_number
    inner join registry on hike_rows.source_key = registry.source_key
    -- photo_for(): the number after the record id's last colon.
    left join photos
        on cast(hike_rows.hike_number as varchar) = photos.hike_key
),

records as (
    select
        *,
        -- SHELF_FIELDS, in its order, as JSON text, which a unit test
        -- compares exactly.
        cast(
            json_merge_patch(
                json_merge_patch(
                    json_object(
                        'id', hike_id,
                        'name', name,
                        'miles', miles,
                        'climb',
                        json_object(
                            'gainFt', climb_gain_ft,
                            'lossFt', climb_loss_ft
                        ),
                        'difficulty', difficulty,
                        'author',
                        json_object('kind', author_kind, 'name', author_name),
                        'photo',
                        json_object(
                            'url', photo_url,
                            'credit', photo_credit,
                            'licence', photo_licence
                        ),
                        'segments', segments,
                        'routeProvenance', route_provenance,
                        'routeGrade', route_grade,
                        'routeNotes', route_notes,
                        'features', features,
                        'region', region,
                        'park', park,
                        'publishedDifficulty', published_difficulty,
                        'estimatedHours', estimated_hours,
                        'dogs', dogs,
                        'routeType', route_type,
                        'closed', closed
                    ),
                    case
                        when climb_gain_ft is null
                            then json('{"climb": null}')
                        else json('{}')
                    end
                ),
                case
                    when photo_url is null then json('{"photo": null}')
                    else json('{}')
                end
            ) as varchar
        ) as shelf_json,
        -- Everything else, in record_for()'s order, then the id.
        cast(
            json_merge_patch(
                json_merge_patch(
                    json_object(
                        'url', source_url,
                        'publishedMiles', published_miles,
                        'overview', overview,
                        'description', description,
                        'trails', trails,
                        'start',
                        case
                            when has_start
                                then
                                    json_object(
                                        'lat', start_lat,
                                        'lon', start_lon,
                                        'basis', start_basis
                                    )
                        end,
                        'publishedOn', published_on,
                        'updatedOn', updated_on,
                        'directions', directions,
                        'publicTransport', public_transport,
                        'licence', content_licence,
                        'measured',
                        json_object(
                            'miles', measured_miles,
                            'note', measured_note
                        ),
                        'publication',
                        json_object(
                            'submittedBy', publication_submitted_by,
                            'submittedOn', published_on,
                            'verifiedOn', updated_on
                        ),
                        'trackReproduction', track_reproduction,
                        'id', hike_id
                    ),
                    case
                        when publication_submitted_by is null
                            then json('{"publication": null}')
                        else json('{}')
                    end
                ),
                case
                    when track_reproduction is null
                        then json('{"trackReproduction": null}')
                    else json('{}')
                end
            ) as varchar
        ) as detail_json
    from written_up
)

select * from records
