-- GATC's water-sources PDF (sources.json `gatc_water_sources`, landed by
-- extract/gatc/points_of_interest.py's ClubPdf): every row, keyed and deduped
-- (decision 40), with nothing filtered and nothing joined. A base model, the
-- one place this dataset is staged (decision 34).
--
-- Key: (`trail`, `mile`): unique on 65 of 65 (measured 2026-10-04 on the
-- live PDF, parsed as lib/club_pdfs.py parses it). `mile` alone is 65 of 65
-- today; `trail` is kept beside it because the approach trail's miles and
-- the A.T.'s are two lists that count from different places, and a later
-- file could repeat a figure across them. `entry` alone is 57 of 65.
--
-- The rows carry no geometry: the PDF states none, so a source is a GATC
-- mile and nothing else until int_points_of_interest__gatc_water places it.
-- Its table lands only where pypdf is installed, which is the extract job's
-- venv and not fixture mode's Python, so in the fixture build this reads no
-- rows through raw_or_empty().
with source as (
    select *
    from {{ raw_or_empty(
        source('gatc', 'raw_gatc__gatc_water_sources'),
        ['trail', 'mile:double', 'entry', '_document']
    ) }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'gatc_water_sources'",
            'trail',
            'mile',
        ]) }} as water_source_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='water_source_key', order_by='_dlt_id'
) }}
