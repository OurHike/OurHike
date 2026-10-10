-- The Long Path guide's section pages, one row per section, as the
-- guide_pages kind lands them: lib/nynjtc_long_path_guide.py's
-- Section.to_dict() and the page's sha256. The three blocks' entries stay
-- JSON, because step_long_path_guide hands them back to that module's
-- Section.from_dict() and build_records(), which classify and place them
-- (pipeline/ELT.md's PO36). Nothing is read out of the prose here.
with source as (
    select * from {{ source('nynjtc', 'raw_nynjtc__nynjtc_long_path_guide') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nynjtc_long_path_guide'",
            'number',
        ]) }} as guide_section_key,
        cast(number as integer) as section_number,
        title,
        distance_miles,
        parks,
        url,
        cast(parking as json) as parking,
        cast(camping as json) as camping,
        cast(description as json) as entries,
        cast(notes as json) as notes,
        page_sha256,
        _loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='guide_section_key', order_by='section_number'
) }}
