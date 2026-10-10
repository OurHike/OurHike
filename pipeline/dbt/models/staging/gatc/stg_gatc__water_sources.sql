-- GATC's water list, one row per source it prints, renamed for
-- int_points_of_interest__gatc_water: the mile, the entry, which list it is
-- in, and the document's own dates out of its manifest. Nothing filtered and
-- nothing placed (decision 40; the review gate is the intermediate's).
--
-- `entry` is GATC's "Source Name" and "Distance Off AT" columns as the PDF's
-- text layer fuses them, kept whole: lib/club_pdfs.py measured that the
-- boundary between them is not in the file, and a guessed split would cut
-- Stover Creek's "Typically very low or dry" off its name.
--
-- `source_id` is the list and GATC's mile as GATC printed it ('at-20.7'),
-- which the published id is made of, so a hiker's report against a source
-- stays attached while GATC keeps the mile, and a renumbered list is a new
-- source rather than an old id pointing somewhere else.
select
    water_source_key,
    'gatc_water_sources' as source_key,
    'gatc' as club,
    trail,
    mile,
    cast(mile as varchar) as mile_text,
    entry,
    trail || '-' || cast(mile as varchar) as source_id,
    json_extract_string(_document, '$.url') as document_url,
    json_extract_string(_document, '$.last_modified') as document_last_modified,
    json_extract_string(_document, '$.title') as document_title,
    json_extract_string(_document, '$.created') as document_created,
    _loaded_at
from {{ ref('base_gatc__gatc_water_sources') }}
