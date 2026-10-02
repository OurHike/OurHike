{{ config(materialized='table') }}
-- A table: the mart, the refusals and their tests all read it.
-- Every challenge file, resolved to the end (CH08, CH09, CH10, CH11): the
-- checks lib/challenges.py's resolve_challenge() makes after its items, then
-- resolve()'s two, then build_output()'s, with the first refusal in
-- `problem` and, where there is none, the challenge as it publishes. One row
-- per file, in the order today's exporter reads them.
--
-- THE REFUSALS, IN THE PYTHON'S ORDER:
--   int_challenges__files' (the file's folder and saving domain, then
--   everything before the items);
--   a finish that is an object, with a whole count from 1 that the items
--   that resolved can reach (CH08: a "25 for the drawing" that can only ever
--   be 24 is a promise nobody can keep, so the whole challenge drops);
--   a reward of a kind the app knows, with a finish line to claim it at, its
--   rules and art https or nothing (CH09);
--   takes_entries true or false (CH09), and true only for a published
--   challenge with a reward;
--   a photo that is https or nothing; a reviewed date (CH11);
--   the file named for its id (CH10), and no earlier file with the same id
--   (CH10: the first in path order keeps it);
--   build_output()'s last two, a name and a provider for the org and a
--   domain for it, which the scope already guarantees (the Python's own
--   comments say both are reached only by a caller that built its scope
--   another way), so neither can fire here.
--
-- Item drops are counted for every file that reached its items, whether or
-- not the challenge itself then dropped, as resolve_challenge() returns them
-- either way; a file refused before its items reports none.
with files as (
    select * from {{ ref('int_challenges__files') }}
),

items as (
    select * from {{ ref('int_challenges__items') }}
),

publishers as (
    select * from {{ ref('int_challenges__publishers') }}
    where accepted
),

item_summary as (
    select
        challenge_file_key,
        count(*) filter (where problem is null) as resolved_items,
        count(*) filter (where problem is not null) as dropped_items,
        count(*) filter (where problem is null and sealed) as sealed_items,
        cast(to_json(coalesce(
            list(published_item order by item_position) filter (where problem is null),
            cast([] as json[])
        )) as varchar) as items_published
    from items
    group by challenge_file_key
),

fields as (
    select
        files.*,
        cast(files.file_json_text as json) as file_json,
        coalesce(item_summary.resolved_items, 0) as resolved_items,
        coalesce(item_summary.dropped_items, 0) as dropped_items,
        coalesce(item_summary.sealed_items, 0) as sealed_items,
        coalesce(item_summary.items_published, '[]') as items_published
    from files
    left join item_summary on files.challenge_file_key = item_summary.challenge_file_key
),

parts as (
    select
        *,
        json_extract(file_json, '$.finish') as finish_json,
        coalesce(json_type(json_extract(file_json, '$.finish')), 'NULL') as finish_type,
        json_extract(file_json, '$.finish.count') as finish_count_json,
        json_extract(file_json, '$.reward') as reward_json,
        coalesce(json_type(json_extract(file_json, '$.reward')), 'NULL') as reward_type,
        json_extract(file_json, '$.reward.kind') as reward_kind_json,
        json_extract(file_json, '$.takes_entries') as takes_entries_json,
        json_extract(file_json, '$.photo') as photo_json,
        json_extract(file_json, '$.reviewed') as reviewed_json
    from fields
),

checked as (
    select
        *,
        case
            when misplaced_problem is not null then misplaced_problem
            when challenge_problem is not null then challenge_problem
            when finish_type != 'NULL' and finish_type != 'OBJECT' then 'finish is not an object'
            when
                finish_type = 'OBJECT'
                and (
                    coalesce(json_type(finish_count_json), 'NULL') not in ('BIGINT', 'UBIGINT')
                    or try_cast(finish_count_json as hugeint) < 1
                )
                then 'finish count must be a whole number from 1'
            when finish_type = 'OBJECT' and try_cast(finish_count_json as hugeint) > resolved_items
                then
                    'finish needs ' || cast(try_cast(finish_count_json as hugeint) as varchar)
                    || ' items and only ' || cast(resolved_items as varchar) || ' resolved'
            when
                reward_type != 'NULL'
                and not coalesce(
                    reward_type = 'OBJECT'
                    and json_type(reward_kind_json) = 'VARCHAR'
                    and list_contains({{ var('challenges_reward_kinds') }}, json_extract_string(reward_kind_json, '$')),
                    false
                )
                then
                    'reward kind must be one of '
                    || array_to_string({{ var('challenges_reward_kinds') }}, ', ')
            when reward_type != 'NULL' and finish_type = 'NULL'
                then 'a reward needs a finish line to be claimed at'
            when
                reward_type != 'NULL'
                and {{ challenges_text("json_extract(reward_json, '$.rules_url')") }} != ''
                and not starts_with({{ challenges_text("json_extract(reward_json, '$.rules_url')") }}, 'https://')
                then 'reward rules_url must be https'
            when reward_type != 'NULL' and not {{ challenges_https_ok("json_extract(reward_json, '$.art')") }}
                then 'reward art must be an https URL'
            when takes_entries_json is not null and coalesce(json_type(takes_entries_json), 'NULL') != 'BOOLEAN'
                then 'takes_entries must be true or false'
            when not {{ challenges_https_ok('photo_json') }} then 'photo must be an https URL'
            when not {{ challenges_date_ok('reviewed_json') }} then 'reviewed must be a YYYY-MM-DD date'
        end as challenge_problem_through_reviewed
    from parts
),

-- resolve()'s two: the file named for its id, then the first of an id keeps it.
named as (
    select
        *,
        case
            when challenge_problem_through_reviewed is not null then challenge_problem_through_reviewed
            when challenge_id != file_stem
                then 'file is named ' || file_stem || '.json but its id is ' || challenge_id
        end as problem_before_repeat
    from checked
),

repeats as (
    select
        challenge_file_key,
        row_number() over (partition by challenge_id order by list_position) > 1 as is_repeat
    from named
    where problem_before_repeat is null
),

decided as (
    select
        named.*,
        publishers.org_name,
        publishers.org_short,
        publishers.org_domain,
        case
            when named.problem_before_repeat is not null then named.problem_before_repeat
            when repeats.is_repeat then 'duplicate challenge id'
            when coalesce(publishers.org_name, '') = '' or coalesce(publishers.org_short, '') = ''
                then 'sources.json ''org:' || named.org || ''' has no name or no provider'
            when publishers.org_domain is null
                then 'publishers.json gives ''org:' || named.org || ''' no domain'
        end as problem
    from named
    left join repeats on named.challenge_file_key = repeats.challenge_file_key
    left join publishers on named.org = publishers.org
)

select
    challenge_file_key,
    club,
    source_key,
    list_position,
    -- How the exporter names a dropped file: by its id once it resolved to a
    -- record (the stem, repeat and organization checks drop a record), else
    -- by int_challenges__files' label.
    case when challenge_problem_through_reviewed is null then challenge_id else report_label end as report_label,
    problem,
    -- Which of the exporter's three steps dropped the file, which is the
    -- order its report lists them in: build_output()'s placing checks, the
    -- resolver, then build_output()'s organization checks.
    case
        when misplaced_problem is not null then 1
        when problem_before_repeat is not null or problem = 'duplicate challenge id' then 2
        when problem is not null then 3
    end as drop_step,
    -- Item drops are reported for a file that reached its items.
    misplaced_problem is null and challenge_problem is null as reached_items,
    dropped_items,
    challenge_id,
    -- The challenge as it publishes, for a file that resolved; a dropped one
    -- publishes nothing, so its fields are null rather than half-read.
    case when problem is null then org end as org,
    case when problem is null then org_name end as org_name,
    case when problem is null then org_short end as org_short,
    case when problem is null then org_domain end as org_domain,
    case when problem is null then trail end as trail,
    case when problem is null then name end as name,
    case when problem is null then status end as status,
    case when problem is null then challenge_summary end as challenge_summary,
    case when problem is null then window_opens end as window_opens,
    case when problem is null then window_closes end as window_closes,
    case
        when problem is null and finish_type = 'OBJECT'
            then try_cast(finish_count_json as integer)
    end as finish_count,
    case
        when problem is null and finish_type = 'OBJECT'
            then nullif({{ challenges_text("json_extract(finish_json, '$.label')") }}, '')
    end as finish_label,
    case
        when problem is null and reward_type = 'OBJECT'
            then json_extract_string(reward_kind_json, '$')
    end as reward_kind,
    case
        when problem is null and reward_type = 'OBJECT'
            then nullif({{ challenges_text("json_extract(reward_json, '$.rules_url')") }}, '')
    end as reward_rules_url,
    case
        when problem is null and reward_type = 'OBJECT'
            then {{ challenges_https("json_extract(reward_json, '$.art')") }}
    end as reward_art,
    -- True only for a published challenge with a reward (CH09).
    case
        when problem is null
            then coalesce(
                json_type(takes_entries_json) = 'BOOLEAN'
                and json_extract_string(takes_entries_json, '$') = 'true'
                and status = 'published'
                and reward_type != 'NULL',
                false
            )
    end as takes_entries,
    case when problem is null then {{ challenges_https('photo_json') }} end as photo,
    case when problem is null then json_extract_string(reviewed_json, '$') end as reviewed,
    case when problem is null then sections_published end as sections_published,
    case when problem is null then items_published end as items_published,
    case when problem is null then resolved_items end as item_count,
    case when problem is null then sealed_items end as sealed_item_count,
    _loaded_at
from decided
