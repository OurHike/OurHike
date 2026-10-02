-- reference/challenges/atc/ (extract/atc/challenges.py): every challenge file
-- of the ATC's folder, keyed (decision 40), with nothing filtered and nothing
-- joined. Each file is still the JSON its reviewer wrote, `_README` aside:
-- reading its fields is the gate's work (int_challenges__files), because a
-- field's JSON type is one of the things the gate checks.
--
-- A file that is not valid JSON has a null `file_json` and the parser's
-- complaint in `parse_error`; so does one json.dumps wrote and DuckDB cannot
-- read (a NaN or an Infinity), whose `file_json_text` is then not null.
--
-- Key: the folder and the file's path in it, unique by construction.
with source as (
    select * from {{ source('atc', 'raw_atc__challenges_atc') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/challenges/atc'",
            '_path',
        ]) }} as challenge_file_key,
        _path as file_path,
        try_cast(row_json as json) as file_json,
        row_json as file_json_text,
        _parse_error as parse_error,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='challenge_file_key', order_by='_dlt_id'
) }}
