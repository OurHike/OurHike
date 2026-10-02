-- reference/work_projects.json's rows, each with what lib/work_projects.py's
-- file_problems() says is wrong with it (CL17), and the row as
-- published_rows() writes it. One row per row of `rows`, in the file's order,
-- plus one row for the file itself, with no position: its review as
-- is_reviewed() reads it, and its own problems (`rows` not a list, the
-- retired `ua_sample_rows`).
-- pub_conditions_work_projects writes conditions/work_projects.json from
-- here, and nothing at all when any row has a problem: one bad row fails the
-- whole file, lib/work_projects.py's stance, "a partial set is worse than
-- none because the gap is invisible".
--
-- THE PROBLEMS, in file_problems()'s order and words: the file's own, then
-- each repeated string `id` ("duplicate id"), then row_problems() for each
-- row: a required field missing, null or "", a date that is not one, ends_on
-- before starts_on (only for a row with no problem so far), a status or
-- signup_mode outside its list, a contact-mode row without a mailto:, tel: or
-- https: signup_contact, no place (lat and lon, or a mile), a mile off the
-- trail, a capacity that is not a positive whole number.
--
-- WHERE THIS REFUSES AND THE PYTHON DOES NOT, each on purpose, and each the
-- direction a gate on what sends a hiker to a trailhead may err in
-- (tests/test_dbt_conditions_parity.py's DELIBERATE_WORK_PROJECT_ROWS):
--   - a JSON true or false counts as no number here, where Python's
--     isinstance(True, int) is true: a lat, lon or mile of `true` is no place,
--     and a capacity of `true` is refused, where Python publishes them;
--   - a date written as an ISO week (2026-W37-6), which Python 3.11 and later
--     read and macro python_date_fromisoformat() does not;
--   - a signup_contact with spaces or control characters before its scheme,
--     which urlsplit() strips before reading the scheme, as
--     int_closures__atc_checked reads a link's scheme as written.
-- And where the Python stops with a traceback, so publishes nothing either: a
-- row that is not an object, a date that is not a string, and a contact whose
-- host has an unmatched bracket (urlsplit()'s "Invalid IPv6 URL"). Each is a
-- problem here, in words of its own.
with documents as (
    select * from {{ ref('base_ourhike__work_projects') }}
),

rows_listed as (
    select
        work_projects_document_key,
        document_json,
        case
            when json_type(document_json, '$.rows') = 'ARRAY'
                then cast(json_extract(document_json, '$.rows') as json[])
        end as row_list
    from documents
),

-- The file's review and its own problems, file_problems()'s first two.
file_level as (
    select
        work_projects_document_key,
        case
            when json_type(document_json, '$.reviewed_at') = 'VARCHAR'
                then json_extract_string(document_json, '$.reviewed_at')
        end as reviewed_at,
        list_value(
            case
                when row_list is null
                    then
                        'rows must be a list (empty is fine - that is the '
                        || 'file''s honest state today)'
            end,
            case
                when json_exists(document_json, '$.ua_sample_rows')
                    then
                        'ua_sample_rows is retired (maintainer decision '
                        || '2026-09-09): no invented workday may reach a '
                        || 'hiker in ANY environment, so `rows` is the only '
                        || 'list. Move a real club''s row into `rows`, or '
                        || 'delete the key'
            end
        ) as listed_problems
    from rows_listed
),

work_rows as (
    select
        work_projects_document_key,
        unnest(row_list) as row_value,
        unnest(range(len(row_list))) as row_position
    from rows_listed
    where row_list is not null
),

-- Each field a check reads, with its JSON type: null where the key is absent,
-- 'NULL' where it is JSON null.
fields as (
    select
        work_projects_document_key,
        row_position,
        row_value,
        json_type(row_value) = 'OBJECT' as is_object,
        json_type(row_value, '$.id') as id_type,
        json_type(row_value, '$.club_name') as club_name_type,
        json_type(row_value, '$.title') as title_type,
        json_type(row_value, '$.description') as description_type,
        json_type(row_value, '$.starts_on') as starts_type,
        json_type(row_value, '$.ends_on') as ends_type,
        json_type(row_value, '$.status') as status_type,
        json_type(row_value, '$.signup_mode') as mode_type,
        json_type(row_value, '$.signup_contact') as contact_type,
        json_type(row_value, '$.lat') as lat_type,
        json_type(row_value, '$.lon') as lon_type,
        json_type(row_value, '$.mile') as mile_type,
        json_type(row_value, '$.capacity') as capacity_type,
        json_extract_string(row_value, '$.id') as id_text,
        json_extract_string(row_value, '$.club_name') as club_name_text,
        json_extract_string(row_value, '$.title') as title_text,
        json_extract_string(row_value, '$.starts_on') as starts_text,
        json_extract_string(row_value, '$.ends_on') as ends_text,
        json_extract_string(row_value, '$.status') as status_text,
        json_extract_string(row_value, '$.signup_mode') as mode_text,
        json_extract_string(row_value, '$.signup_contact') as contact_text,
        cast(json_extract(row_value, '$.mile') as varchar) as mile_json,
        try_cast(json_extract_string(row_value, '$.mile') as double) as mile,
        try_cast(json_extract_string(row_value, '$.capacity') as hugeint)
            as capacity
    from work_rows
),

-- How a message names its row: f"{row_id}" of row.get("id", "<no id>").
labelled as (
    select
        *,
        case
            when id_type is null then '<no id>'
            when id_type = 'NULL' then 'None'
            when id_type = 'BOOLEAN'
                then case when id_text = 'true' then 'True' else 'False' end
            when id_type = 'VARCHAR' then id_text
            else cast(json_extract(row_value, '$.id') as varchar)
        end as row_label,
        coalesce(
            mile_type in ('BIGINT', 'UBIGINT', 'DOUBLE'), false
        ) as has_mile,
        coalesce(
            lat_type in ('BIGINT', 'UBIGINT', 'DOUBLE')
            and lon_type in ('BIGINT', 'UBIGINT', 'DOUBLE'),
            false
        ) as has_coords,
        -- REQUIRED_FIELDS: missing, JSON null, or "" (`in ("", None)`).
        {{ work_project_missing('id') }} as missing_id,
        {{ work_project_missing('club_name') }} as missing_club_name,
        {{ work_project_missing('title') }} as missing_title,
        {{ work_project_missing('starts') }} as missing_starts_on,
        {{ work_project_missing('ends') }} as missing_ends_on,
        {{ work_project_missing('mode') }} as missing_signup_mode,
        {{ python_date_fromisoformat('starts_text') }} as starts_on,
        {{ python_date_fromisoformat('ends_text') }} as ends_on,
        -- urlsplit()'s scheme: the letters, digits, +, - and . before the
        -- first colon, the first of them a letter, read as written.
        lower(
            regexp_extract(contact_text, '^([A-Za-z][A-Za-z0-9+.-]*):', 1)
        ) as contact_scheme,
        -- urlsplit()'s netloc, when // follows the scheme.
        regexp_extract(
            contact_text, '^[A-Za-z][A-Za-z0-9+.-]*://([^/?#]*)', 1
        ) as contact_netloc
    from fields
),

-- row_problems()'s checks before the date order, which runs only when these
-- found nothing: a row that is not an object, each required field, then
-- each date that is not one.
first_checks as (
    select
        *,
        list_filter(
            [
                case
                    when not is_object
                        then
                            'row ' || row_position
                            || ' is not an object, so none of its fields '
                            || 'can be read'
                end,
                case
                    when is_object and missing_id
                        then row_label || ': id is required'
                end,
                case
                    when is_object and missing_club_name
                        then row_label || ': club_name is required'
                end,
                case
                    when is_object and missing_title
                        then row_label || ': title is required'
                end,
                case
                    when is_object and missing_starts_on
                        then row_label || ': starts_on is required'
                end,
                case
                    when is_object and missing_ends_on
                        then row_label || ': ends_on is required'
                end,
                case
                    when is_object and missing_signup_mode
                        then row_label || ': signup_mode is required'
                end,
                -- Python's date.fromisoformat() of a number raises
                -- TypeError: a traceback there, a problem here.
                case
                    when starts_type = 'VARCHAR' and starts_on is null
                        then
                            row_label || ': starts_on is not a date: '
                            || {{ python_repr('starts_text') }}
                    when starts_type not in ('VARCHAR', 'NULL')
                        then
                            row_label
                            || ': starts_on must be a YYYY-MM-DD string'
                end,
                case
                    when ends_type = 'VARCHAR' and ends_on is null
                        then
                            row_label || ': ends_on is not a date: '
                            || {{ python_repr('ends_text') }}
                    when ends_type not in ('VARCHAR', 'NULL')
                        then
                            row_label
                            || ': ends_on must be a YYYY-MM-DD string'
                end
            ],
            lambda problem: problem is not null
        ) as early_problems
    from labelled
),

checked as (
    select
        *,
        list_concat(
            early_problems,
            list_filter(
                [
                    case
                        when len(early_problems) = 0 and ends_on < starts_on
                            then row_label || ': ends_on is before starts_on'
                    end,
                    case
                        when
                            is_object
                            and status_type is not null
                            and (
                                status_type != 'VARCHAR'
                                or status_text not in (
                                    'upcoming', 'completed', 'cancelled'
                                )
                            )
                            then
                                row_label || ': status must be one of '
                                || '(''upcoming'', ''completed'', '
                                || '''cancelled'')'
                    end,
                    case
                        when
                            is_object
                            and (
                                mode_type is distinct from 'VARCHAR'
                                or mode_text not in ('contact', 'in_app')
                            )
                            then
                                row_label || ': signup_mode must be one of '
                                || '(''contact'', ''in_app'') - `in_app` '
                                || 'arrives with the signup backend (#762)'
                    end,
                    case
                        when
                            mode_type = 'VARCHAR'
                            and mode_text = 'contact'
                            and (
                                contact_type is distinct from 'VARCHAR'
                                or coalesce(contact_scheme, '') not in (
                                    'mailto', 'tel', 'https'
                                )
                            )
                            then
                                row_label || ': a contact-mode row needs '
                                || 'signup_contact (a mailto: or tel: or '
                                || 'https: string)'
                        when
                            mode_type = 'VARCHAR'
                            and mode_text = 'contact'
                            and (
                                contains(contact_netloc, '[')
                                or contains(contact_netloc, ']')
                            )
                            then
                                row_label || ': signup_contact has a '
                                || 'bracket in its host, which urlsplit() '
                                || 'cannot read'
                    end,
                    case
                        when is_object and not has_coords and not has_mile
                            then
                                row_label || ': a row needs lat+lon, or a '
                                || 'mile, or both - a workday with no place '
                                || 'sends nobody anywhere'
                    end,
                    case
                        when
                            has_mile
                            and not mile between
                            {{ var('work_project_mile_min') }}
                            and {{ var('work_project_mile_max') }}
                            then
                                row_label || ': mile ' || mile_json
                                || ' is off the trail''s own extent ('
                                || '{{ var("work_project_mile_min") }}-'
                                || '{{ var("work_project_mile_max") }})'
                    end,
                    case
                        when
                            is_object
                            and capacity_type is not null
                            and capacity_type != 'NULL'
                            and (
                                capacity_type not in ('BIGINT', 'UBIGINT')
                                or capacity < 1
                            )
                            then
                                row_label || ': capacity is a positive '
                                || 'whole number of people, or absent for '
                                || '''no cap stated'''
                    end
                ],
                lambda problem: problem is not null
            )
        ) as row_problems
    from first_checks
),

-- file_problems()'s duplicate check: each string id after its first.
duplicates as (
    select
        *,
        case
            when
                id_type = 'VARCHAR'
                and row_number() over (
                    partition by work_projects_document_key, id_type, id_text
                    order by row_position
                ) > 1
                then [
                    id_text
                    || ': duplicate id - the client keys and dedupes on it'
                ]
            else []
        end as duplicate_problems
    from checked
),

-- published_rows(): the row as written, then each of status, capacity,
-- description, lat, lon and mile it lacks, in that order, as setdefault()
-- adds them. A row with no problem is an object with at least six keys, so
-- its text ends in the brace the defaults go before.
published as (
    select
        *,
        case
            when len(row_problems) = 0 and len(duplicate_problems) = 0
                then cast(
                    left(cast(row_value as varchar), -1)
                    || case
                        when status_type is null
                            then ',"status":"upcoming"'
                        else ''
                    end
                    || case
                        when capacity_type is null then ',"capacity":null'
                        else ''
                    end
                    || case
                        when description_type is null
                            then ',"description":null'
                        else ''
                    end
                    || case
                        when lat_type is null then ',"lat":null' else ''
                    end
                    || case
                        when lon_type is null then ',"lon":null' else ''
                    end
                    || case
                        when mile_type is null then ',"mile":null' else ''
                    end
                    || '}' as json
                )
        end as published_row
    from duplicates
)

select
    {{ dbt_utils.generate_surrogate_key([
        'work_projects_document_key', 'row_position',
    ]) }} as work_project_row_key,
    work_projects_document_key,
    row_position,
    case when id_type = 'VARCHAR' then id_text end as work_project_id,
    row_label,
    duplicate_problems,
    row_problems,
    -- The row's share of file_problems(), one line, for `dbt show` and the
    -- unit tests, which cannot compare a list.
    nullif(
        array_to_string(list_concat(duplicate_problems, row_problems), ' | '),
        ''
    ) as problem,
    published_row,
    cast(null as varchar) as reviewed_at,
    cast(null as boolean) as is_reviewed
from published
union all
select
    {{ dbt_utils.generate_surrogate_key([
        'work_projects_document_key', "'file'",
    ]) }} as work_project_row_key,
    work_projects_document_key,
    null as row_position,
    null as work_project_id,
    null as row_label,
    [] as duplicate_problems,
    list_filter(listed_problems, lambda problem: problem is not null)
        as row_problems,
    nullif(
        array_to_string(
            list_filter(listed_problems, lambda problem: problem is not null),
            ' | '
        ),
        ''
    ) as problem,
    null as published_row,
    reviewed_at,
    -- lib/work_projects.py's is_reviewed(): a string, not blank once
    -- stripped, whose first ten characters date.fromisoformat() reads.
    coalesce(
        {{ python_strip('reviewed_at') }} != ''
        and {{ python_date_fromisoformat('left(reviewed_at, 10)') }}
        is not null,
        false
    ) as is_reviewed
from file_level
