-- The warnings mart's row history (snapshots/warnings/, decision 57) as the
-- previous build saved it, read back for one rule: a feed's notice that
-- leaves the feed's window is not lifted (decision 53, phase C;
-- int_closures__window_carried). The columns are the club notices' own: a
-- carried row is only ever a generated club notice source's, whose rows
-- carry nothing else, so the history's other columns are not read.
--
-- Read through notice_raw_table(): on a cold start, or a leg whose history
-- could not be restored (OURHIKE_ROW_HISTORY=off), the snapshot does not
-- exist yet and this is empty, so nothing is carried and nothing fails.
--
-- Key: dbt's dbt_scd_id, one per version of a row.
with source as (
    select
        dbt_scd_id,
        warning_id,
        warning_kind,
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
        cast(dbt_valid_to as timestamp) as dbt_valid_to
    from {{ notice_raw_table(source('row_history', 'int_warnings__history'), [
        'dbt_scd_id', 'warning_id', 'warning_kind', 'club', 'source_key', 'notice_kind',
        'obstructs_trail:boolean', 'review_state', 'title', 'category',
        'locality', 'source_edited_at:timestamptz', 'updated_at', 'source_url',
        'geom_geojson', 'source_row_key', 'dbt_valid_to:timestamp'
    ]) }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'int_warnings__history'",
            'dbt_scd_id',
        ]) }} as history_row_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='history_row_key', order_by='dbt_scd_id'
) }}
