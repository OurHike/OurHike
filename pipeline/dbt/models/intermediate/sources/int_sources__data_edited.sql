-- Each source's data edit day: the UTC day its upstream says its data was
-- last edited, as YYYY-MM-DD, one row per source key that has a usable one.
-- pub_club_sections reads it for club_sections.json's `source_edited`,
-- where export_club_sections.py reads fetch_all.py's manifest
-- (`data_last_edit_date`, ArcGIS's editingInfo.dataLastEditDate).
--
-- WHERE THE DATE COMES FROM: the extract logs each ArcGIS layer's
-- editingInfo.dataLastEditDate on its run log row, from the metadata it
-- reads before the pages, and never lastEditDate (extract/_run.py's
-- RUNS_COLUMNS comment says why there, and extract/_kinds.py's
-- data_last_edit_date() what is read).
--
-- WHICH ROW DATES A TABLE: a build reads a table's rows from its newest
-- `loaded` run (extract/_warehouse.py's committed_tables()), and a
-- `skipped` run after it found those rows unchanged. So a table is dated by
-- the newest date logged on that load or on a skip after it: a FRESH skip
-- reads no metadata body (a 304), so its row carries none unless the
-- monthly lane read one for it (extract/_run.py's fresh_edit_date(), which
-- extract/_run.py's dated_tables() decides by this same rule). An older
-- load's date is never used, because it dated rows since replaced: a load
-- whose layer stated no date leaves its table undated, not guessed. A
-- refused or incomplete read logs no date, so a date newer than the rows a
-- build serves never reaches a file.
--
-- WHICH DAYS ARE USABLE: export_club_sections.py's edited_day()'s, UTC and
-- only for an epoch after 1970-01-01T00:00:00Z and before the year 10000,
-- the range Python's datetime prints: zero, a negative and anything later
-- are no day, and the key is left out, never null and never "1969-12-31".
-- epoch_ms() gives a naive UTC timestamp, so the session's zone moves no
-- day, and the CASE keeps it off a value it cannot convert, which errors.
--
-- THE SOURCE KEY is the `<key>` of the table's `raw_<club>__<key>` name
-- (extract/_contract.py's raw_table()), read with the run log's own `club`.
-- That is the sources.json key itself for any key without a `-`, which
-- raw_table() writes as `_`: none of the 782 keys has one (sources.json,
-- read 2026-10-15).
with runs as (
    select
        club,
        table_name,
        run_id,
        outcome,
        data_last_edit_date
    from {{ ref('base_extract__runs_monthly') }}
    where outcome in ('loaded', 'skipped')
),

-- The run whose rows a build reads of each table. run_id is a UTC stamp
-- that sorts in time order.
served as (
    select
        table_name,
        max(run_id) as loaded_run_id
    from runs
    where outcome = 'loaded'
    group by table_name
),

dated as (
    select
        runs.table_name,
        any_value(runs.club) as club,
        arg_max(runs.data_last_edit_date, runs.run_id) as data_last_edit_date
    from runs
    inner join served
        on
            runs.table_name = served.table_name
            and runs.run_id >= served.loaded_run_id
    where runs.data_last_edit_date is not null
    group by runs.table_name
),

days as (
    select
        substr(table_name, length('raw_' || club || '__') + 1) as source_key,
        data_last_edit_date,
        case
            -- 253402300800000 is 10000-01-01T00:00:00Z in epoch milliseconds.
            when
                data_last_edit_date > 0
                and data_last_edit_date < 253402300800000
                then strftime(epoch_ms(data_last_edit_date), '%Y-%m-%d')
        end as data_edited_on
    from dated
)

select
    source_key,
    data_last_edit_date,
    data_edited_on
from days
where data_edited_on is not null
