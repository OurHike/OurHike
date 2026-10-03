{{ config(materialized='table') }}
-- Each POI's card photo and gallery (PO24, PO38): export_poi.py's main()
-- from load_photo_records() to attach_photos(), one row per POI with a photo
-- to show.
--
-- THE FACE GATE (PO38, lib/photo_screen.py's gate_photos(), #836 — Run a
-- face-and-nudity check over the Commons fetch, where a stranger's
-- self-portrait can become a town's illustration) covers the Commons photos
-- and not ATC's own inventory shoot, as export_poi.py applies it. A photo a
-- person refused never ships, whatever the screen said; a photo the screen
-- flagged ships only once a person has cleared it, and is held until then;
-- every other photo ships. Unscreened ships, as the Python ships it, because
-- unscreened is a fact about when the photo was fetched rather than about
-- what is in it (gate_photos()' own words), and the step counts them. The
-- decision is read by the photo's digest, as the ledger keys it.
--
-- ATC WINS AN OVERLAP, WHOLE: the merge is `{**commons, **atc}` by POI, so
-- a POI with any ATC photo record shows ATC's list and none of Commons',
-- even where none of ATC's has a digest to show. A POI whose every Commons
-- photo the gate held has no Commons entry left to merge.
--
-- WHAT A CARD SHOWS (attach_photos()): only a photo with a digest, because
-- the digest is the only thing that names it in our bucket; the first is the
-- card photo, its credit in the flat photo_* columns, and `photos` is every
-- one in list order as JSON, the key first, then the four credit fields.
-- photo_key() raises on a digest that is not a sha256 hex string, and this
-- model's `error` test fails the build on one.
with photos as (
    select * from {{ ref('stg_derived__poi_photos') }}
),

gated as (
    -- gate_photos() on the Commons file; ATC's is not gated.
    select photos.*
    from photos
    where
        photos.source = 'atc'
        or (
            coalesce(photos.decision, '') != 'refused'
            and (not photos.flagged or photos.decision = 'cleared')
        )
),

winner as (
    -- {**commons, **atc}: ATC's list where the POI has one.
    select
        poi_id,
        case when bool_or(source = 'atc') then 'atc' else 'commons' end
            as source
    from gated
    group by poi_id
),

usable as (
    select
        gated.poi_id,
        gated.photo_index,
        gated.digest,
        gated.page_url,
        gated.author,
        gated.license,
        gated.taken,
        'photos/' || gated.digest || '.jpg' as photo_key
    from gated
    inner join winner
        on
            gated.poi_id = winner.poi_id
            and gated.source = winner.source
    where coalesce(gated.digest, '') != ''
)

select
    poi_id,
    -- The card photo: the first usable photo, nulls kept as the Python
    -- copies them (`first.get(field)`).
    list_extract(list(photo_key order by photo_index), 1) as photo_key,
    list_extract(list(page_url order by photo_index), 1) as photo_page_url,
    list_extract(list(author order by photo_index), 1) as photo_author,
    list_extract(list(license order by photo_index), 1) as photo_license,
    list_extract(list(taken order by photo_index), 1) as photo_taken,
    to_json(
        list(
            json_object(
                'key', photo_key,
                'page_url', page_url,
                'author', author,
                'license', license,
                'taken', taken
            )
            order by photo_index
        )
    ) as photos
from usable
group by poi_id
