{{ config(materialized='table') }}
-- The typed rows that may ship, and the confidence each ships at: the one
-- home of the organizations' own public flags (PO27, PO28, PO29) and of
-- may_publish for every POI, before anything is deduplicated or merged, so
-- a row that may not ship can never win a merge and vanish, taking the
-- place with it (pipeline/ELT.md, "Publication filters run before dedup").
--
-- export_nearby_poi.py's public_verdict() and confidence_for(), rule by
-- rule. A layer with no `public_field` keeps every row at high confidence.
-- DEC's PUBLICUSE FILTERS: a row is kept only where the field, stripped and
-- upper-cased, is the entry's `public_value` ('Y' where none is written),
-- because DEC's 'N' side is internal assets, not weaker POIs. OPRHP's
-- ParksApp SETS CONFIDENCE instead (`public_flag_sets_confidence`): every
-- row is kept, high where flagged and low where not, because the flag says
-- what OPRHP's own visitor app shows, not what exists. Then the layer's
-- `confidence_floor`, which only ever lowers: NYC's drinking fountains read
-- `featuresta` Active on all 3,849 rows, so nothing says any one works, and
-- all ship low. A floor that is not 'low' fails the build at this model's
-- test, as confidence_for() raises, rather than shipping the layer high.
--
-- The A.T. family's confidence is the poi_type_mapping seed's, set in
-- int_points_of_interest__classified; export_poi.py reads no public flag.
--
-- Then int_sources__publication, the one home of may_publish (pipeline/
-- ELT.md, "Who may publish"): a row ships only where its source may. On
-- today's registry every POI source may (59 of 64 sources, and opentrail
-- through the unregistered_publishing_sources seed), so this drops nothing
-- today, and a source the registry holds back drops whole.
with classified as (
    select * from {{ ref('int_points_of_interest__classified') }}
    where drop_reason is null
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

judged as (
    select
        classified.*,
        json_extract_string(classified.registry_entry, '$.public_field')
            as public_field,
        {{ python_truthy(
            "json_extract(classified.registry_entry, "
            ~ "'$.public_flag_sets_confidence')"
        ) }} as public_flag_sets_confidence,
        json_extract_string(classified.registry_entry, '$.confidence_floor')
            as confidence_floor,
        upper({{ python_strip(
            "coalesce(json_extract_string(classified.properties, '$.' || "
            ~ poi_field_member("json_extract_string(classified.registry_entry, '$.public_field')")
            ~ "), '')"
        ) }})
        = upper(
            coalesce(
                json_extract_string(
                    classified.registry_entry, '$.public_value'
                ),
                'Y'
            )
        ) as flagged_public
    from classified
),

verdict as (
    select
        judged.*,
        judged.public_field is null
        or judged.public_flag_sets_confidence
        or judged.flagged_public as kept,
        case
            when
                judged.phone_files = 'poi_by_type'
                then judged.family_confidence
            when judged.confidence_floor = 'low' then 'low'
            when judged.public_field is null then 'high'
            when
                judged.public_flag_sets_confidence and not judged.flagged_public
                then 'low'
            else 'high'
        end as confidence
    from judged
)

select
    verdict.poi_key,
    verdict.source_key,
    verdict.file_order,
    verdict.source_row,
    verdict.club,
    verdict.source,
    verdict.phone_files,
    verdict.trail_id,
    verdict.source_feature_id,
    verdict.source_feature_id_json,
    verdict.derived_id,
    verdict.name,
    verdict.poi_type,
    verdict.confidence,
    verdict.confidence_floor,
    verdict.asset,
    verdict.facility,
    verdict.lon,
    verdict.lat,
    verdict.properties,
    verdict._loaded_at
from verdict
inner join publication on verdict.source_key = publication.source_key
where verdict.kept and publication.may_publish
