-- Every challenge file, read and checked as far as lib/challenges.py's
-- resolve_challenge() goes before it reads the items (CH02, CH03, CH10,
-- CH11, CH12), with export_challenges.build_output()'s two checks on where
-- the file was filed first. One row per file, in the order today's exporter
-- reads them: sorted(reference/challenges/*/*.json), pathlib's order, folder
-- by folder and then by file name (load_challenge_files()).
--
-- `misplaced_problem` is build_output()'s: the file's folder must be its
-- `org`, and a file the console's pull request saved (`published_by_domain`)
-- must name the domain publishers.json gives that org. A misplaced file is
-- never resolved, so nothing else is reported for it.
--
-- `challenge_problem` is resolve_challenge()'s first refusal before the
-- items, in its order:
--   an object; an id (CH10); an org publishers.json accepts; a trail that org
--   publishes (CH03); a name; a status (CH12); a window that is an object,
--   with each end YYYY-MM-DD or null and closing on or after opening (CH11);
--   sections, each with a usable id and a title, no two sharing an id
--   (CH11); items.
-- A file refused here reports no item drops, as resolve_challenge() returns
-- none for it. Everything after the items (finish, reward, takes_entries,
-- photo, reviewed) is int_challenges__resolved's, because the finish line is
-- read against how many items resolved.
--
-- `report_label` is how resolve() names a file it drops: its `id` if that is
-- truthy, else its stem. A misplaced file is named by its stem.
with files as (
    select * from {{ ref('int_challenges__unioned') }}
),

publishers as (
    select * from {{ ref('int_challenges__publishers') }}
    where accepted
),

scope_trails as (
    select distinct
        org,
        trail
    from {{ ref('int_challenges__publisher_trails') }}
    where in_scope
),

fields as (
    select
        challenge_file_key,
        club,
        source_key,
        file_path,
        file_folder,
        file_name,
        file_stem,
        file_json,
        parse_error,
        _loaded_at,
        -- load_challenge_files(): sorted(glob('*/*.json')), compared part
        -- by part.
        row_number() over (order by file_folder, file_name) as list_position,
        coalesce(json_type(file_json), 'NULL') as document_type,
        json_extract(file_json, '$.id') as id_json,
        json_extract(file_json, '$.org') as org_json,
        json_extract(file_json, '$.trail') as trail_json,
        json_extract(file_json, '$.name') as name_json,
        json_extract(file_json, '$.status') as status_json,
        json_extract(file_json, '$.summary') as summary_json,
        json_extract(file_json, '$.window') as window_json,
        json_extract(file_json, '$.window.opens') as opens_json,
        json_extract(file_json, '$.window.closes') as closes_json,
        json_extract(file_json, '$.sections') as sections_json,
        json_extract(file_json, '$.items') as items_json,
        json_extract(file_json, '$.published_by_domain') as saved_by_json
    from files
),

typed as (
    select
        *,
        case
            when json_type(org_json) = 'VARCHAR'
                then json_extract_string(org_json, '$')
        end as org,
        case
            when json_type(trail_json) = 'VARCHAR'
                then json_extract_string(trail_json, '$')
        end as trail,
        case
            when json_type(status_json) = 'VARCHAR'
                then json_extract_string(status_json, '$')
        end as status_text,
        -- An end is given when it is present and not null: window.get() reads
        -- both as None.
        coalesce(json_type(opens_json), 'NULL') != 'NULL' as opens_given,
        coalesce(json_type(closes_json), 'NULL') != 'NULL' as closes_given,
        coalesce(json_type(saved_by_json), 'NULL') != 'NULL' as saved_by_given,
        coalesce(json_type(window_json), 'NULL') = 'OBJECT' as window_is_object,
        coalesce(json_type(sections_json), 'NULL') = 'ARRAY'
        and json_array_length(sections_json) > 0 as has_sections,
        coalesce(json_type(items_json), 'NULL') = 'ARRAY'
        and json_array_length(items_json) > 0 as has_items,
        {{ challenges_date_ok('opens_json') }} as opens_ok,
        {{ challenges_date_ok('closes_json') }} as closes_ok,
        {{ challenges_id_ok('id_json') }} as id_ok,
        {{ challenges_text('name_json') }} as name_text,
        {{ challenges_text('summary_json') }} as summary_text,
        -- Each value a message quotes, as Python's repr() prints it, once.
        {{ python_repr('id_json') }} as id_repr,
        {{ python_repr('org_json') }} as org_repr,
        {{ python_repr('trail_json') }} as trail_repr,
        {{ python_repr('saved_by_json') }} as saved_by_repr
    from fields
),

-- str(org) and str(saved_by).strip().lower(), as build_output() compares
-- them: a string as itself, anything else as its repr.
spelled as (
    select
        *,
        {{ python_str('org_json', 'org_repr') }} as org_str,
        lower(
            {{ python_strip(python_str('saved_by_json', 'saved_by_repr')) }}
        ) as saved_by_domain
    from typed
),

-- build_output()'s two checks, before the resolver sees the file.
placed as (
    select
        spelled.*,
        case
            when
                spelled.document_type = 'OBJECT'
                and spelled.org is not null
                and spelled.org != spelled.file_folder
                then
                    'file is under ' || spelled.file_folder
                    || '/ but its org is ' || spelled.org_repr
            when
                spelled.document_type = 'OBJECT'
                and spelled.saved_by_given
                and not coalesce(
                    saving.org_domain = spelled.saved_by_domain, false
                )
                then
                    'saved by ' || spelled.saved_by_repr
                    || ', which is not the domain publishers.json names for '
                    || spelled.org_repr
        end as misplaced_problem
    from spelled
    -- org_domains.get(str(org)): the accepted publisher named by the org's
    -- str().
    left join publishers as saving
        on
            spelled.document_type = 'OBJECT'
            and spelled.org_str = saving.org
),

sections as (
    select
        challenge_file_key,
        unnest(cast(sections_json as json[])) as section_json,
        generate_subscripts(cast(sections_json as json[]), 1)
            as section_position
    from typed
    where json_type(sections_json) = 'ARRAY'
),

section_fields as (
    select
        challenge_file_key,
        section_position,
        coalesce(json_type(section_json), 'NULL') = 'OBJECT' as is_object,
        json_extract(section_json, '$.id') as id_json,
        json_extract_string(section_json, '$.id') as section_id,
        {{ challenges_text("json_extract(section_json, '$.title')") }}
            as title_text,
        {{ challenges_text("json_extract(section_json, '$.short')") }}
            as short_text
    from sections
),

section_checks as (
    select
        challenge_file_key,
        section_position,
        section_id,
        case
            when not is_object or not {{ challenges_id_ok('id_json') }}
                then 'a section has no usable id'
            -- The id passed _id_ok() here, so it is a string, printed as
            -- itself.
            when title_text = ''
                then 'section ' || section_id || ' has no title'
        end as section_problem,
        -- What a section publishes as: its id, its title stripped, and its
        -- short name stripped or else its title.
        json_object(
            'id', section_id,
            'title', title_text,
            'short', coalesce(nullif(short_text, ''), title_text)
        ) as published_section
    from section_fields
),

section_summary as (
    select
        challenge_file_key,
        arg_min(section_problem, section_position)
        filter (where section_problem is not null) as section_problem,
        count(*) as section_count,
        count(distinct section_id) as distinct_section_ids,
        cast(
            to_json(list(published_section order by section_position))
            as varchar
        ) as sections_published,
        cast(to_json(list(section_id order by section_position)) as varchar)
            as section_ids
    from section_checks
    group by challenge_file_key
),

checked as (
    select
        placed.*,
        section_summary.sections_published,
        section_summary.section_ids,
        case
            when placed.document_type != 'OBJECT' then 'file is not an object'
            when not placed.id_ok
                then
                    'id must be lowercase words joined by hyphens, at most '
                    || '{{ var("challenges_id_max_chars") }} characters'
            when known.org is null
                then 'org ' || placed.org_repr || ' is not a known organization'
            when scope_trails.trail is null
                then
                    'trail ' || placed.trail_repr || ' is not one '
                    || placed.org_repr || ' publishes'
            when placed.name_text = '' then 'challenge has no name'
            when
                not coalesce(
                    list_contains(
                        {{ var('challenges_statuses') }}, placed.status_text
                    ),
                    false
                )
                then
                    'status must be one of '
                    || array_to_string({{ var('challenges_statuses') }}, ', ')
            when not placed.window_is_object then 'window is not an object'
            when
                (placed.opens_given and not placed.opens_ok)
                or (placed.closes_given and not placed.closes_ok)
                then 'window dates must be YYYY-MM-DD or null'
            when
                placed.opens_given
                and placed.closes_given
                and json_extract_string(placed.closes_json, '$')
                < json_extract_string(placed.opens_json, '$')
                then 'window closes before it opens'
            when not placed.has_sections then 'challenge declares no sections'
            when section_summary.section_problem is not null
                then section_summary.section_problem
            when
                section_summary.distinct_section_ids
                != section_summary.section_count
                then 'two sections share an id'
            when not placed.has_items then 'challenge has no items'
        end as challenge_problem
    from placed
    left join publishers as known on placed.org = known.org
    left join scope_trails
        on placed.org = scope_trails.org and placed.trail = scope_trails.trail
    left join section_summary
        on placed.challenge_file_key = section_summary.challenge_file_key
),

-- Whether the file reached its items: placed where it says, and passed
-- every check above.
reached as (
    select
        *,
        misplaced_problem is null and challenge_problem is null as passed
    from checked
)

select
    challenge_file_key,
    club,
    source_key,
    file_path,
    file_folder,
    file_stem,
    list_position,
    parse_error,
    misplaced_problem,
    case
        when misplaced_problem is null then challenge_problem
    end as challenge_problem,
    case
        when misplaced_problem is not null then file_stem
        when {{ python_truthy('id_json') }}
            then {{ python_str('id_json', 'id_repr') }}
        else file_stem
    end as report_label,
    case when id_ok then json_extract_string(id_json, '$') end as challenge_id,
    org,
    trail,
    name_text as name,
    status_text as status,
    nullif(summary_text, '') as challenge_summary,
    -- What the later models read, for a file that reached its items.
    case
        when passed and opens_given then json_extract_string(opens_json, '$')
    end as window_opens,
    case
        when passed and closes_given
            then json_extract_string(closes_json, '$')
    end as window_closes,
    case when passed then sections_published end as sections_published,
    case when passed then section_ids end as section_ids,
    cast(items_json as varchar) as items_json,
    cast(file_json as varchar) as file_json_text,
    _loaded_at
from reached
