-- OurHike's visible field notes (extract/_shared/ourhike/field_notes.py,
-- export_conditions.py's PUBLIC_NOTES_SQL run whole), keyed (decision 40).
-- No mart reads them: conditions/notes.json stays export_conditions.py's to
-- write (WN11), and this model is what that file's exposure names, so its
-- lineage and cadence are checked like any other phone file's.
--
-- Key: the note's UUID primary key.
with source as (
    select * from {{ source('ourhike', 'raw_ourhike__notes') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'ourhike_notes'",
            'id',
        ]) }} as ourhike_note_key,
        id as note_uuid,
        poi_id,
        lat,
        lon,
        mile,
        observation,
        note,
        observed_at,
        reporter_type,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='ourhike_note_key', order_by='_dlt_id'
) }}
