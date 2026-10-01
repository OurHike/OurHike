-- Every registered source, shipping or not, with what the org console's
-- registry.json says about it (#929, SR07). Nothing is composed: each field
-- is one the registry carries, copied, and null where it carries none,
-- because a console filling a gap would hide the registration a probe
-- cannot describe (export_sources.py's build_registry()).
--
-- `steward` is the one the row reports: the source's own, else its
-- organization's name. That is the name its support block is joined on, and
-- the difference is measured: joined on the source's field alone, all twelve
-- ATC entries read `supports_donation: false` (export_sources.py, 2026-08-28).
with sources as (
    select * from {{ ref('stg_registry__sources') }}
),

organizations as (
    select * from {{ ref('stg_registry__organizations') }}
),

marks as (
    select * from {{ ref('stg_registry__org_marks') }}
),

-- Every name a support block is about: its author and its also_covers.
supported as (
    select distinct unnest(list_append(also_covers, author)) as steward
    from {{ ref('stg_registry__top_level') }}
    where block_kind = 'support'
),

reported as (
    select
        sources.*,
        organizations.steward_id,
        organizations.org_name,
        organizations.org_note,
        coalesce(
            nullif(sources.steward, ''), organizations.org_name
        ) as reported_steward
    from sources
    left join organizations on sources.provider = organizations.provider
)

select
    reported.source_key,
    reported.file_row,
    reported.title,
    reported.provider,
    reported.steward_id,
    reported.reported_steward as steward,
    reported.kind,
    reported.trust,
    reported.reaches_hikers,
    reported.licence_basis,
    reported.freshness_kind,
    reported.attribution,
    reported.org_name,
    reported.org_note,
    supported.steward is not null as supports_donation,
    marks.mark_state
from reported
left join marks on reported.provider = marks.provider
left join supported
    on
        reported.reported_steward = supported.steward
        and reported.reported_steward != ''
