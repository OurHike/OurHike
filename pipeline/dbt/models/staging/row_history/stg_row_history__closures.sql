-- The closures mart's row history (snapshots/closures/, decision 57) as the
-- previous build saved it, read back for one rule: a feed's notice that
-- leaves the feed's window is not lifted (decision 53, phase C;
-- int_closures__window_carried). The columns are the club notices' own: a
-- carried row is only ever a generated club notice source's, whose rows
-- carry nothing else, so the history's other columns are not read.
--
-- `row_json` is the whole saved row, every column the mart had when it was
-- saved, for a second rule: a notice source int_closures__gate holds keeps
-- its last good rows (decision 53, phase D; int_closures__held_carried),
-- which need every column of an ATC or NYNJTC row, and which read a column
-- the saved history predates (a column a later build added) as null rather
-- than failing.
--
-- Read through notice_raw_table(): on a cold start, or a leg whose history
-- could not be restored (OURHIKE_ROW_HISTORY=off), the snapshot does not
-- exist yet and this is empty, so nothing is carried and nothing fails.
--
-- Key: dbt's dbt_scd_id, one per version of a row.
{%- set saved = source('row_history', 'int_closures__history') %}
with history as (
    select * from {{ notice_raw_table(saved, [
        'dbt_scd_id', 'closure_id', 'club', 'source_key', 'notice_kind',
        'obstructs_trail:boolean', 'review_state', 'title', 'category',
        'locality', 'source_edited_at:timestamptz', 'updated_at', 'source_url',
        'geom_geojson', 'source_row_key', 'dbt_valid_to:timestamp'
    ]) }}
),

source as (
    select
        dbt_scd_id,
        closure_id,
        club,
        source_key,
        notice_kind,
        cast(obstructs_trail as boolean) as obstructs_trail,
        review_state,
        title,
        category,
        locality,
        cast(source_edited_at as timestamptz) as source_edited_at,
        updated_at,
        source_url,
        geom_geojson,
        source_row_key,
        cast(_loaded_at as timestamptz) as _loaded_at,
        cast(dbt_valid_to as timestamp) as dbt_valid_to,
        to_json(history) as row_json
    from history
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'int_closures__history'",
            'dbt_scd_id',
        ]) }} as history_row_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='history_row_key', order_by='dbt_scd_id'
) }}
