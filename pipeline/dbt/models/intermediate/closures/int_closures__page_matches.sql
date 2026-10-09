{{ config(materialized='table') }}
-- DECISION 128 (the maintainer's poll of 2026-10-09, shown
-- w6-ptny-closures.html, frame A): a section of Parks & Trails New York's
-- closures layer (ptny_est_closures), which states 'Closed' on all nine of
-- its lines and no date, reason or link, draws as closed only once a person
-- has matched it to an item on the trail's dated closures page
-- (oprhp_est_trail_closures_page), and its card then carries that page's
-- date and a link to it. An unmatched section stays held. One row per match
-- in seeds/notice_page_matches.csv, with whether it stands this build and,
-- where it does not, why.
--
-- A MATCH STANDS while all of these hold, each read this build:
--   1. its source and its page are a pair seeds/notice_confirming_pages.csv
--      names;
--   2. the page may publish (int_sources__publication);
--   3. this warehouse holds a read of the page, and that read states the
--      page's own date, which the card prints;
--   4. that read still carries the item: the item's sha256, as the match
--      recorded it, is among the read's `item_sha256s`
--      (extract/_notices.py's PageNotice, ITEMS);
--   5. the source's rows in this warehouse still serve the line as it was
--      matched: its notice id, with the raw row key the match names. A
--      layer reload mints new OBJECTIDs (decision 40) and a redrawn line
--      hashes to a new key, and either way the match is for a line PTNY no
--      longer serves. Not judged where this warehouse holds no row of the
--      source at all (its table absent, decision 61), so the section can
--      still be carried while its page carries the item.
-- int_closures__club_notices holds every row of a confirming source whose
-- match does not stand (its rule 7), int_closures__held_carried carries none
-- of them, and pub_conditions_notices puts the page's date and link on each
-- one that does.
--
-- WHICH WAY THAT ROUNDS, AND WHY: toward held. PTNY's layer dates nothing,
-- so it can say 'Closed' long after a closure has lifted, and the page is
-- the authority decision 128 chose. So a section whose item has left the
-- page, or whose item the page has reworded in any word, or whose page
-- this warehouse holds no read of, or whose line PTNY no longer serves as
-- it was matched, is neither drawn nor carried: a closure drawn on an item
-- nobody can find any more is a confident answer nobody stands behind,
-- which CLAUDE.md ranks below an honest unknown. The cost is the other
-- harm, and it is real: a section that is still closed stops drawing when
-- the page rewords its item, or when PTNY reloads or redraws its line,
-- until a person matches it again. The warn test on this model names each
-- such match in the build log so that somebody does. "Latest read" means
-- the latest that landed: a read the extract refuses leaves the one before
-- it standing (extract/_notices.py), so a page that cannot be read keeps
-- its matches, and dbt's source freshness turns that page red after 24
-- hours (decision 100).
--
-- A MATCH IS A PERSON'S JUDGEMENT, approved by the maintainer in chat before
-- it is written (decision 121's rule for trail_orgs.json rows, which
-- decision 128 follows), so the seed ships empty and nothing draws.
--
-- ONE PAGE IS READ HERE, the Empire State Trail's, through its own base
-- model: it is the only page the extract reads with `items`, and both seeds'
-- accepted_values tests hold every row to it, so a row naming another page
-- fails a test rather than silently never standing. The read is taken out of
-- the row as JSON, because a page table this warehouse does not hold reads
-- as its key columns alone (macros/notices.sql's notice_raw_table), and a
-- missing column must read as no date and no items, not stop the build.
with matches as (
    select * from {{ ref('notice_page_matches') }}
),

confirming as (
    select * from {{ ref('notice_confirming_pages') }}
),

page_reads as (
    select
        'oprhp_est_trail_closures_page' as page_source_key,
        page.url as page_url,
        try_cast(
            json_extract_string(to_json(page), '$.date') as date
        ) as page_updated_on,
        try_cast(
            json_extract_string(to_json(page), '$.item_sha256s') as json
        ) as item_sha256s
    from {{ ref('base_nysparks__oprhp_est_trail_closures_page') }} as page
),

publication as (
    select
        source_key,
        may_publish
    from {{ ref('int_sources__publication') }}
),

-- Condition 5: each confirming source's rows in this warehouse, keyed as
-- int_closures__club_notices keys them, and which sources have any.
served as (
    select
        notices.source_key,
        notices.source_key || ':'
        || coalesce(notices.source_id, 'key-' || notices.notice_key)
            as notice_id,
        notices.notice_key
    from {{ ref('int_closures__club_notices_unioned') }} as notices
    inner join confirming on notices.source_key = confirming.source_key
),

served_ids as (
    select distinct notice_id from served
),

served_sources as (
    select distinct source_key from served
),

judged as (
    select
        matches.notice_id,
        matches.source_row_key,
        split_part(matches.notice_id, ':', 1) as source_key,
        matches.page_source_key,
        matches.matched_on,
        page_reads.page_url,
        page_reads.page_updated_on,
        confirming.source_key is not null as pair_named,
        coalesce(publication.may_publish, false) as page_may_publish,
        page_reads.page_url is not null as page_read,
        coalesce(
            list_contains(
                cast(page_reads.item_sha256s as varchar[]),
                matches.page_item_sha256
            ),
            false
        ) as item_on_page,
        served_sources.source_key is not null as source_read,
        served_ids.notice_id is not null as row_id_served,
        served_row.notice_id is not null as row_key_served
    from matches
    left join confirming
        on
            split_part(matches.notice_id, ':', 1) = confirming.source_key
            and matches.page_source_key = confirming.page_source_key
    left join page_reads
        on matches.page_source_key = page_reads.page_source_key
    left join publication
        on matches.page_source_key = publication.source_key
    left join served_sources
        on split_part(matches.notice_id, ':', 1) = served_sources.source_key
    left join served_ids
        on matches.notice_id = served_ids.notice_id
    left join served as served_row
        on
            matches.notice_id = served_row.notice_id
            and matches.source_row_key = served_row.notice_key
)

select
    notice_id,
    source_row_key,
    source_key,
    page_source_key,
    page_url,
    page_updated_on,
    matched_on,
    page_read,
    item_on_page,
    case when source_read then row_key_served end as row_served,
    case
        when not pair_named
            then
                'seeds/notice_confirming_pages.csv does not name '
                || page_source_key || ' as the page of ' || source_key
        when not page_may_publish
            then
                'its page, ' || page_source_key || ', may not publish '
                || '(int_sources__publication)'
        when not page_read
            then
                'no read of its page, ' || page_source_key || ', is in this '
                || 'warehouse, so nothing says its item is still on it'
        when page_updated_on is null
            then
                'the latest read of its page, ' || page_source_key
                || ', states no date of its own, so the card could not '
                || 'carry one'
        when not item_on_page
            then
                'the latest read of its page, ' || page_source_key
                || ' (updated ' || strftime(page_updated_on, '%Y-%m-%d')
                || '), no longer carries the item it was matched to on '
                || strftime(matched_on, '%Y-%m-%d')
                || ': gone, or reworded'
        when source_read and not row_id_served
            then
                'the latest read of ' || source_key || ' serves no row '
                || notice_id || ', so its line was removed or renumbered '
                || 'after it was matched on '
                || strftime(matched_on, '%Y-%m-%d')
        when source_read and not row_key_served
            then
                'the latest read of ' || source_key || ' draws ' || notice_id
                || ' differently from the line matched on '
                || strftime(matched_on, '%Y-%m-%d')
                || ' (its raw row key changed)'
    end as held_because
from judged
