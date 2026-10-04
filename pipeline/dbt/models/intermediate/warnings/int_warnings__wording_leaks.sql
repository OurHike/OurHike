{{ config(materialized='table') }}
-- NO PROSE IS PUBLISHED (decision 55; pipeline/ELT.md, phase C). One row per
-- text value of a closures or warnings row that holds a club notice
-- source's own wording: a value int_warnings__notice_wording_unioned
-- collected from that source's base model, which its staging model does not
-- carry. Its test fails the build on any row, so a column that starts
-- carrying a source's paragraphs, by a rule change or a staging edit, stops
-- the build before a writer can publish it.
--
-- WHAT IT COMPARES. Each value of a final row is read as words
-- (notice_wording_text(): tags cut, whitespace folded), and it leaks when it
-- contains a whole wording value of its own source. The finals are the marts
-- less their two dates, and every pub_conditions_* writer reads a club
-- notice only through the marts (tests/test_generated_notice_models.py holds
-- that no writer reads a club notice model), so this covers the files too.
-- Only rows of the club notice sources are read: no other branch reads their
-- base models, so no other row can hold their words.
--
-- WHAT IT MISSES, said so: a part of a paragraph shorter than the whole
-- value, and a value shorter than notice_is_wording()'s threshold
-- (@unvalidated). A value that a source repeats in a fact column, such as a
-- description identical to the title, is not wording (the union leaves it
-- out), so a title can never fail this.
with wording as (
    select distinct
        source_key,
        wording
    from {{ ref('int_warnings__notice_wording_unioned') }}
),

-- Unqualified, from a subquery: `to_json(final_row)` names the row, which
-- dbt lint's RF03 and AL05 read as an unqualified reference and an unused
-- alias unless every reference beside it is unqualified too.
published as (
    select
        'closures' as mart,
        closure_id as row_id,
        source_key,
        to_json(final_row) as row_json
    from (select * from {{ ref('int_closures__final') }}) as final_row
    where starts_with(notice_kind, 'club_')
    union all
    select
        'warnings' as mart,
        warning_id as row_id,
        source_key,
        to_json(final_row) as row_json
    from (select * from {{ ref('int_warnings__final') }}) as final_row
    where starts_with(notice_kind, 'club_')
),

published_values as (
    select
        published.mart,
        published.row_id,
        published.source_key,
        entry.key as column_name,
        {{ notice_wording_text("json_extract_string(entry.value, '$')") }}
            as published_text
    from published
    cross join json_each(published.row_json) as entry
    where json_type(entry.value) = 'VARCHAR'
)

select
    {{ dbt_utils.generate_surrogate_key([
        'published_values.mart',
        'published_values.row_id',
        'published_values.column_name',
        'wording.wording',
    ]) }} as leak_key,
    published_values.mart,
    published_values.row_id,
    published_values.column_name,
    published_values.source_key,
    wording.wording
from published_values
inner join wording
    on
        published_values.source_key = wording.source_key
        and contains(published_values.published_text, wording.wording)
