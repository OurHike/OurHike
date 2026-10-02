-- Which of ATC's Trail Updates, as their website shows them now
-- (base_atc__atc_trail_updates_pages), may publish without a person:
-- lib/atc_updates.py's auto_publish_refusal() and auto_row(), as
-- export_atc_updates.py's automatic_rows() runs them over
-- fetch_atc_updates.py's scrape (CL07-CL10). One row per update the sitemap
-- lists, with `refusal`, the reason it may not publish, in the Python's
-- words, null where it may; and for those, the row as auto_row() writes it.
--
-- THE GATE, IN auto_publish_refusal()'S ORDER; the first that applies is
-- the reason:
--   a slug the reviewed file already has    a person's row always wins
--   no dateModified
--   not edited strictly after the review    the load-bearing rule: after a
--                                           review, everything unreviewed
--                                           is the reviewer's reject pile
--   no title, whitespace being none
--   a category this build does not know     var atc_update_categories (CL02)
--   no states
--   mile references that disagree (CL08)    none, or more than one
--                                           distinct (start, end)
--   the agreed span off the trail           vars atc_trail_mile_min/max (CL01)
--   the agreed span running backwards
-- An update's own words are never read: an all-clear publishes as one,
-- under ATC's own headline (lib/atc_updates.py, "WHY THERE IS NO ALL-CLEAR
-- REFUSAL"), and the extract does not land them.
--
-- THE ROW (CL09): `obstructs_trail` is FORCED FALSE and read from nothing,
-- so an update nobody here has read can put a dot and a banner on the map
-- and never a barrier across the trail, and it lands in the warnings mart
-- only (decision 7). The span is the first mile reference's, and a point's
-- end is its start. `updated_at` is dateModified in UTC to the second.
-- `review_state` is lib/atc_updates.py's UNREVIEWED in the phone file, and
-- `auto` in the marts (ELT.md, "The eleven marts").
--
-- CL10: an update ATC stops listing leaves the sitemap, and so this model,
-- and is not republished (extract/_kinds.py's AtcTrailUpdatePages).
--
-- THE REVIEW IS THE REVIEWED FILE'S: `reviewed_at` from base_atc__atc_updates
-- and the reviewed slugs from int_closures__atc_checked. export_atc_updates.py
-- runs this gate only for a file that passed is_reviewed() and
-- file_problems(); here it runs whatever the file holds, and
-- int_closures__gate holds back every ATC row, these included, when the file
-- fails either.
--
-- WHERE THIS IS STRICTER, deliberately (tests/test_dbt_conditions_parity.py
-- lists each): a dateModified or reviewed_at in a form Python's
-- fromisoformat() reads and the macros python_fromisoformat_utc() and
-- python_date_fromisoformat() do not, such as 20260819T162250Z, is refused
-- here as "not since the review", where the Python may publish it.
with pages as (
    select * from {{ ref('base_atc__atc_trail_updates_pages') }}
),

-- The file's review, as int_closures__gate reads it: one row however many
-- the base model has, so a file that did not land whole still has an answer.
review as (
    select
        max(
            case
                when
                    json_type(json_extract(document_json, '$.reviewed_at'))
                    = 'VARCHAR'
                    then json_extract_string(document_json, '$.reviewed_at')
            end
        ) as reviewed_at
    from {{ ref('base_atc__atc_updates') }}
),

reviewed as (
    select distinct atc_id
    from {{ ref('int_closures__atc_checked') }}
    where atc_id is not null
),

fields as (
    select
        pages.atc_trail_update_page_key,
        pages.slug,
        pages.sitemap_row,
        pages.title,
        pages.category,
        pages.states,
        pages.date_modified,
        pages.source_url,
        pages._loaded_at,
        review.reviewed_at,
        reviewed.atc_id is not null as already_reviewed,
        {{ python_fromisoformat_utc('pages.date_modified') }} as edited_at,
        {{ python_date_fromisoformat('left(review.reviewed_at, 10)') }}
            as reviewed_on,
        coalesce(cast(pages.miles as json[]), []) as mile_items,
        case
            when json_type(pages.states) = 'ARRAY'
                then json_array_length(pages.states)
            else 0
        end as state_count
    from pages
    cross join review
    left join reviewed on pages.slug = reviewed.atc_id
),

-- CL08's agreed_mile(): the first reference, when every reference names the
-- same (start, end). Python compares the numbers, so the key is each
-- number's shortest text, which is one text per double.
spans as (
    select
        *,
        len(mile_items) as mile_count,
        len(list_distinct(list_transform(
            mile_items,
            lambda m: coalesce(
                cast(
                    try_cast(json_extract_string(m, '$.start') as double)
                    as varchar
                ),
                'None'
            )
            || ' '
            || coalesce(
                cast(
                    try_cast(json_extract_string(m, '$.end') as double)
                    as varchar
                ),
                'None'
            )
        ))) as span_count,
        mile_items[1] as reference_mile
    from fields
),

reference as (
    select
        *,
        json_extract(reference_mile, '$.start') as start_json,
        json_extract(reference_mile, '$.end') as end_json,
        json_extract_string(reference_mile, '$.raw') as reference_raw,
        try_cast(json_extract_string(reference_mile, '$.start') as double)
            as reference_start,
        try_cast(json_extract_string(reference_mile, '$.end') as double)
            as reference_end
    from spans
),

judged as (
    select
        *,
        case
            when already_reviewed then 'already reviewed by a person'
            when coalesce(date_modified, '') = ''
                then 'no dateModified on the page'
            when
                not coalesce(
                    cast(timezone('UTC', edited_at) as date) > reviewed_on,
                    false
                )
                then
                    'last edited ' || left(date_modified, 10)
                    || ', not since the review on '
                    || coalesce(reviewed_at, 'None')
            when coalesce({{ python_strip('title') }}, '') = '' then 'no title'
            when
                not coalesce(
                    list_contains({{ var('atc_update_categories') }}, category),
                    false
                )
                then
                    'category ' || {{ python_repr('category') }}
                    || ' is not one this build knows'
            when state_count = 0 then 'no states on the page'
            when span_count != 1
                then
                    mile_count
                    || ' mile references that do not agree on one place'
            when
                reference_start is null
                or not reference_start
                between {{ var('atc_trail_mile_min') }}
                and {{ var('atc_trail_mile_max') }}
                or (
                    reference_end is not null
                    and not reference_end
                    between {{ var('atc_trail_mile_min') }}
                    and {{ var('atc_trail_mile_max') }}
                )
                then
                    {{ python_repr('reference_raw') }}
                    || ' is outside the trail''s own extent'
            when reference_end < reference_start
                then {{ python_repr('reference_raw') }} || ' runs backwards'
        end as refusal,
        -- A point's end is its start (auto_row()).
        case
            when json_type(end_json) in ('UBIGINT', 'BIGINT', 'DOUBLE')
                then end_json
            else start_json
        end as span_end_json,
        {{ python_strip('title') }} as stripped_title,
        strftime(timezone('UTC', edited_at), '%Y-%m-%dT%H:%M:%SZ')
            as edited_utc
    from reference
)

select
    atc_trail_update_page_key,
    slug,
    sitemap_row,
    refusal,
    refusal is null as publishes,
    -- CL12: the refusals a person can act on, the ones
    -- propose_atc_updates.py's _actionable() keeps: every reason except a
    -- reviewed slug and an update older than the review, which are refused
    -- on every run and are the steady state, not a finding.
    coalesce(
        not (
            starts_with(refusal, 'already reviewed')
            or starts_with(refusal, 'last edited')
        ),
        false
    ) as actionable,
    slug as atc_id,
    stripped_title as title,
    category,
    states,
    -- The span as the parse read it, text, as int_closures__atc_checked
    -- carries a reviewed mile, because a dbt 2.0.6 unit test compares a
    -- DOUBLE only to one decimal; int_closures__unioned casts it.
    case when refusal is null then cast(start_json as varchar) end
        as start_mile_text,
    case when refusal is null then cast(span_end_json as varchar) end
        as end_mile_text,
    false as obstructs_trail,
    case when refusal is null then edited_utc end as updated_at,
    source_url,
    -- The row as auto_row() writes it, for pub_conditions_atc_updates, each
    -- mile as the JSON number the parse read, so 1138.0 stays 1138.0.
    case
        when refusal is null
            then json_object(
                'atc_id', slug,
                'title', stripped_title,
                'category', category,
                'states', states,
                'start_mile_marker', start_json,
                'end_mile_marker', span_end_json,
                'obstructs_trail', false,
                'updated_at', edited_utc,
                'source_url', source_url,
                'source_key', 'atc_trail_updates',
                'review_state', 'unreviewed'
            )
    end as published_row,
    _loaded_at
from judged
