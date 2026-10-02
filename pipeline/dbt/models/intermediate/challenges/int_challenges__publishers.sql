-- reference/challenges/publishers.json, row by row, through
-- export_challenges.py's publisher_scope() (CH02): which organizations may
-- put a challenge on which trails, and why each row that may not was
-- refused. One row per row of the file, in its order. A row that is
-- `accepted` is the organization's scope; its trails are checked one by one
-- in int_challenges__publisher_trails.
--
-- THE CHECKS, IN publisher_scope()'S ORDER, because a row reports its first:
--   1. an object;
--   2. its `org` is an organization sources.json registers as `org:<org>`;
--   3. that organization has a name and a provider to print beside it;
--   4. no earlier row of the same organization was accepted ("listed twice
--      - the first row stands");
--   5. a `why`, 6. a web `domain` _DOMAIN accepts, 7. `trails` is a list.
-- Checks 2 and 3 are the organization's, so every row of one organization
-- passes or fails them alike, and the row accepted is the first of that
-- organization to pass 5 to 7. Every later row of it fails at 4, whatever
-- else it holds.
--
-- THE DOMAIN is the accepted row's own, lower-cased: publisher_domains()
-- takes the first row that has a `why`, a list of trails and a domain
-- _DOMAIN accepts, among the organizations publisher_scope() accepted, which
-- is that same row. A refused row never supplies it (the second security
-- review, 2026-10-01).
--
-- load_publishers() reads the file's `publishers` and treats anything but a
-- list as no rows, so no organization may publish. The file being absent is
-- fatal there; here the extract cannot load it at all (reviewed_file()
-- raises on a missing file, and the layout test imports it).
with documents as (
    select * from {{ ref('base_ourhike__challenges_publishers') }}
),

organizations as (
    select * from {{ ref('stg_registry__organizations') }}
),

listed as (
    select
        _loaded_at,
        case
            when json_type(json_extract(file_json, '$.publishers')) = 'ARRAY'
                then cast(json_extract(file_json, '$.publishers') as json[])
            else []
        end as publisher_rows
    from documents
),

publisher_rows as (
    select
        _loaded_at,
        unnest(publisher_rows) as row_json,
        generate_subscripts(publisher_rows, 1) as publisher_position
    from listed
),

fields as (
    select
        publisher_position,
        row_json,
        _loaded_at,
        coalesce(json_type(row_json), 'NULL') as row_type,
        json_extract(row_json, '$.org') as org_json,
        -- Each value a message quotes, as Python's repr() prints it, once.
        {{ python_repr('row_json') }} as row_repr,
        {{ python_repr("json_extract(row_json, '$.org')") }} as org_repr,
        case
            when json_type(json_extract(row_json, '$.org')) = 'VARCHAR'
                then json_extract_string(row_json, '$.org')
        end as org,
        {{ challenges_text("json_extract(row_json, '$.why')") }} as why,
        lower(
            {{ challenges_text("json_extract(row_json, '$.domain')") }}
        ) as domain_text,
        json_extract(row_json, '$.trails') as trails_json
    from publisher_rows
),

registered as (
    select
        fields.*,
        organizations.steward_id,
        {{ python_strip("coalesce(organizations.org_name, '')") }} as org_name,
        {{ python_strip("coalesce(organizations.provider, '')") }} as org_short
    from fields
    left join organizations
        on
            fields.org is not null
            and organizations.steward_id = 'org:' || fields.org
),

checked as (
    select
        *,
        -- Checks 1 to 3, the row's and its organization's.
        case
            when row_type != 'OBJECT'
                then 'a row is not an object: ' || row_repr
            when steward_id is null
                then
                    org_repr
                    || ': not an organization in sources.json '
                    || '(looked for ''org:'
                    || {{ python_str('org_json', 'org_repr') }} || ''')'
            when org_name = '' or org_short = ''
                then
                    org || ': sources.json ''org:' || org
                    || ''' has no name or no provider to publish beside its '
                    || 'challenges'
        end as organization_problem,
        -- Checks 5 to 7, the row's own.
        case
            when why = '' then org || ': the row gives no `why`'
            when
                not coalesce(regexp_full_match(
                    domain_text, '{{ var("challenges_domain_pattern") }}'
                ), false)
                then
                    org || ': the row gives no web `domain` '
                    || '(like appalachiantrail.org)'
            when coalesce(json_type(trails_json), 'NULL') != 'ARRAY'
                then org || ': `trails` is not a list'
        end as row_problem
    from registered
),

first_accepted as (
    select
        org,
        min(publisher_position) as accepted_position
    from checked
    where organization_problem is null and row_problem is null
    group by org
),

decided as (
    select
        checked.*,
        case
            when checked.organization_problem is not null
                then checked.organization_problem
            when first_accepted.accepted_position < checked.publisher_position
                then checked.org || ': listed twice - the first row stands'
            else checked.row_problem
        end as problem
    from checked
    left join first_accepted on checked.org = first_accepted.org
)

select
    publisher_position,
    org,
    problem is null as accepted,
    problem,
    case when problem is null then domain_text end as org_domain,
    case when problem is null then org_name end as org_name,
    case when problem is null then org_short end as org_short,
    case
        when problem is null then cast(trails_json as varchar)
    end as trails_json,
    _loaded_at
from decided
