{{ config(
    format='json',
    location='suggested_hikes_detail.json',
    meta={'when_empty': 'keep_last_file'}
) }}
-- Every shipped hike's detail, the fields the shelf leaves out, in the shape
-- export_suggested_hikes.py's split_record() makes each one: the page's own
-- prose and figures, the measurement beside them, and the hike's own `id`,
-- so a detail fetched alone can say which hike it is. FLAT, NOT NESTED:
-- lib/suggestedHikesData.ts's validDetail reads `url`, `publishedMiles` and
-- `description` off the top level of the record it is handed.
--
-- ONE FILE FOR ALL OF THEM, `{"details": [...]}` in shelf order, because a
-- phone_file writes exactly one document and dbt has no per-object fan-out
-- (pipeline/ELT.md, "Four kinds of phone file"). Each detail ships as its own
-- object, `suggested_hikes_detail_<number>.json`, the flat root key
-- write_details() names it under (DETAIL_KEY): cutting this file into those
-- objects is stage 4's, outside dbt, as the per-cell files are, and the key
-- is the number after the id's last colon, which the mart's test holds to
-- detailKeyFor's `<source>:<digits>`.
--
-- ABSENT, NEVER EMPTY: a page that names no author ships no `publication`
-- block (SH10), and a generated route no `trackReproduction`. Each sits in
-- the record with the rest, and json_merge_patch then removes the ones
-- absent, with a null patch; a block present is patched with `{}`, which
-- leaves it whole, its own nulls (`verifiedOn` on a page never revised)
-- included. A block put in through the patch would lose those nulls, which
-- is what RFC 7396 does with a null inside a patch (measured 2026-10-02,
-- DuckDB 1.5.5). Nothing is written when no hike ships, as for the shelf
-- (pub_suggested_hikes).
with hikes as (
    select * from {{ ref('suggested_hikes') }}
    where phone_file = 'suggested_hikes'
),

details as (
    select
        list_position,
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
                json_object('miles', measured_miles, 'note', measured_note),
                'publication',
                case
                    when publication_submitted_by is not null
                        then
                            json_object(
                                'submittedBy', publication_submitted_by,
                                'submittedOn', published_on,
                                'verifiedOn', updated_on
                            )
                end,
                'trackReproduction', track_reproduction,
                'id', hike_id
            ),
            json_object(
                'publication',
                case
                    when publication_submitted_by is not null then json('{}')
                end,
                'trackReproduction', track_reproduction
            )
        ) as detail
    from hikes
)

select list(detail order by list_position) as details
from details
having count(*) > 0
