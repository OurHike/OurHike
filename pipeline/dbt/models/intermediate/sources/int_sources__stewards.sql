-- One record per steward whose data reaches a hiker (#927): what
-- stewards.json says about it, and the first problem export_sources.py's
-- build_output() would refuse the whole file for. The test on this model
-- fails the build on any problem, as the Python's SystemExit does.
--
-- WHO IS A STEWARD: a `provider` with at least one source whose
-- `reaches_hikers` is true (SR01). A provider with none is not published at
-- all, which today is GATC and OPRHP.
--
-- HOW A BLOCK JOINS ITS STEWARD (SR02, SR03): a `<x>_licence`, `_support` or
-- `_store` block belongs to the provider when its `author`, or one of its
-- `also_covers`, is the `steward` one of the provider's shipping sources
-- names. The first such block in the file wins, as in `_block`, so
-- photo_licence, which comes first, is ATC's licence block.
--
-- WHAT IS UNANIMOUS (SR06): `steward`, `trust` and `attribution` are taken
-- from the sources only when every shipping source gives the same one; a
-- source that gives none breaks the agreement, as `_unanimous` has it.
--
-- WHAT FAILS (SR04, SR05): a support or store block missing a required
-- field, with surfaces that are not a list or name a surface the seed does
-- not hold, a referral that is not a string, a store whose paper-map table
-- no resource lands, or a table int_sources__paper_maps refuses. Messages
-- are `_support_record`'s and `_store_record`'s, except the table that is
-- not landed: SQL sees the warehouse, not the checkout, so it says which
-- folder would land it.
with shipping as (
    select * from {{ ref('stg_registry__sources') }}
    where reaches_hikers
),

blocks as (
    select * from {{ ref('stg_registry__top_level') }}
    where block_kind is not null
),

organizations as (
    select * from {{ ref('stg_registry__organizations') }}
),

surfaces as (
    select
        block_kind,
        list(surface order by surface) as allowed
    from {{ ref('registry_surfaces') }}
    group by block_kind
),

paper_maps as (
    select * from {{ ref('int_sources__paper_maps') }}
),

providers as (
    select
        provider,
        case
            when count(*) = count(steward) and count(distinct steward) = 1
                then any_value(steward)
        end as unanimous_steward,
        case
            when count(*) = count(trust) and count(distinct trust) = 1
                then any_value(trust)
        end as unanimous_trust,
        case
            when
                count(*) = count(attribution)
                and count(distinct attribution) = 1
                then any_value(attribution)
        end as unanimous_attribution,
        list_distinct(
            list(steward) filter (where coalesce(steward, '') != '')
        ) as steward_names
    from shipping
    group by provider
),

matched as (
    select
        providers.provider,
        blocks.block_kind,
        arg_min(blocks.entry_value, blocks.entry_position) as block
    from providers
    inner join blocks
        on list_has_any(
            providers.steward_names,
            list_append(blocks.also_covers, blocks.author)
        )
    group by providers.provider, blocks.block_kind
),

joined as (
    select
        providers.*,
        licences.block as licence_block,
        supports.block as support_block,
        stores.block as store_block
    from providers
    left join matched as licences
        on
            providers.provider = licences.provider
            and licences.block_kind = 'licence'
    left join matched as supports
        on
            providers.provider = supports.provider
            and supports.block_kind = 'support'
    left join matched as stores
        on
            providers.provider = stores.provider
            and stores.block_kind = 'store'
),

-- Each block's fields, read once.
fields as (
    select
        *,
        json_extract_string(support_block, '$.author') as support_author,
        json_extract(support_block, '$.donate_surfaces') as donate_surfaces,
        json_extract_string(store_block, '$.author') as store_author,
        json_extract(store_block, '$.store_surfaces') as store_surfaces,
        json_extract(store_block, '$.referral') as referral_json,
        json_extract_string(store_block, '$.referral') as referral,
        json_extract_string(store_block, '$.paper_maps') as paper_maps_path,
        list_filter(
            ['author', 'donate_url', 'donate_cta', 'donate_surfaces'],
            lambda field: not {{ python_truthy(
                "json_extract(support_block, '$.' || field)"
            ) }}
        ) as support_missing,
        list_filter(
            [
                'author', 'store_url', 'store_cta', 'store_surfaces',
                'paper_maps'
            ],
            lambda field: not {{ python_truthy(
                "json_extract(store_block, '$.' || field)"
            ) }}
        ) as store_missing
    from joined
),

allowed as (
    select
        any_value(allowed) filter (
            where block_kind = 'support'
        ) as donate_allowed,
        any_value(allowed) filter (where block_kind = 'store') as store_allowed
    from surfaces
),

with_tables as (
    select
        fields.*,
        paper_maps.products,
        allowed.donate_allowed,
        allowed.store_allowed,
        paper_maps.file_path is not null as paper_maps_landed,
        paper_maps.problem as paper_maps_problem
    from fields
    left join paper_maps on fields.paper_maps_path = paper_maps.file_path
    cross join allowed
),

checked as (
    select
        *,
        case
            when json_type(donate_surfaces) = 'ARRAY'
                then list_sort(list_filter(
                    list_distinct(cast(donate_surfaces as varchar[])),
                    lambda surface: not list_contains(donate_allowed, surface)
                ))
        end as unknown_donate_surfaces,
        case
            when json_type(store_surfaces) = 'ARRAY'
                then list_sort(list_filter(
                    list_distinct(cast(store_surfaces as varchar[])),
                    lambda surface: not list_contains(store_allowed, surface)
                ))
        end as unknown_store_surfaces
    from with_tables
),

records as (
    select
        provider,
        coalesce(
            nullif(unanimous_steward, ''),
            nullif(json_extract_string(licence_block, '$.author'), ''),
            provider
        ) as steward_name,
        unanimous_trust as steward_trust,
        json_extract_string(licence_block, '$.license') as licence,
        coalesce(
            nullif(unanimous_attribution, ''),
            json_extract_string(licence_block, '$.attribution')
        ) as attribution,
        json_extract_string(licence_block, '$.terms_verbatim') as terms,
        json_extract_string(licence_block, '$.terms_source') as terms_source,
        -- The donate line, or null where the organization has not asked
        -- (#932). `donate_recipient` and `donate_blurb` only where set:
        -- json_merge_patch drops a member a patch sets to null.
        case
            when support_block is not null
                then json_merge_patch(
                    json_object(
                        'donate_url',
                        json_extract_string(support_block, '$.donate_url'),
                        'donate_cta',
                        json_extract_string(support_block, '$.donate_cta'),
                        'donate_surfaces',
                        list_sort(list_distinct(
                            try_cast(donate_surfaces as varchar[])
                        ))
                    ),
                    json_object(
                        'donate_recipient',
                        nullif(json_extract_string(
                            support_block, '$.donate_recipient'
                        ), ''),
                        'donate_blurb',
                        nullif(json_extract_string(
                            support_block, '$.donate_blurb'
                        ), '')
                    )
                )
        end as support_record,
        -- The paper-map store, or null where none is recorded (#1574), every
        -- link carrying the organization's referral query.
        case
            when store_block is not null
                then json_object(
                    'store_url',
                    {{ with_referral(
                        "json_extract_string(store_block, '$.store_url')",
                        "referral"
                    ) }},
                    'store_cta',
                    json_extract_string(store_block, '$.store_cta'),
                    'store_surfaces',
                    list_sort(list_distinct(
                        try_cast(store_surfaces as varchar[])
                    )),
                    'paper_maps',
                    list_transform(
                        products,
                        lambda product: json_merge_patch(product, json_object(
                            'url',
                            {{ with_referral(
                                "json_extract_string(product, '$.url')",
                                "referral"
                            ) }}
                        ))
                    )
                )
        end as store_record,
        case
            when support_block is null then null
            when len(support_missing) > 0
                then
                    'support block for '
                    || coalesce(nullif(support_author, ''), '(no author)')
                    || ' is missing: ' || array_to_string(support_missing, ', ')
            when json_type(donate_surfaces) != 'ARRAY'
                then
                    'donate_surfaces for ' || support_author
                    || ' must be a list, got '
                    || {{ python_type_name('donate_surfaces') }}
            when len(unknown_donate_surfaces) > 0
                then
                    'donate_surfaces for ' || support_author
                    || ' names surfaces that do not exist: '
                    || array_to_string(unknown_donate_surfaces, ', ')
        end as support_problem,
        case
            when store_block is null then null
            when len(store_missing) > 0
                then
                    'store block for '
                    || coalesce(nullif(store_author, ''), '(no author)')
                    || ' is missing: ' || array_to_string(store_missing, ', ')
            when json_type(store_surfaces) != 'ARRAY'
                then
                    'store_surfaces for ' || store_author
                    || ' must be a list, got '
                    || {{ python_type_name('store_surfaces') }}
            when len(unknown_store_surfaces) > 0
                then
                    'store_surfaces for ' || store_author
                    || ' names surfaces that do not exist: '
                    || array_to_string(unknown_store_surfaces, ', ')
            when not paper_maps_landed
                then
                    'store block for ' || store_author || ' names '
                    || paper_maps_path || ', and no resource in '
                    || 'extract/_shared/registry/ lands it'
            when
                coalesce(json_type(referral_json), 'NULL') not in (
                    'NULL', 'VARCHAR'
                )
                then
                    'referral for ' || store_author
                    || ' must be a query string, got '
                    || {{ python_type_name('referral_json') }}
            else paper_maps_problem
        end as store_problem
    from checked
)

select
    records.provider,
    records.steward_name,
    records.steward_trust,
    records.licence,
    records.attribution,
    records.terms,
    records.terms_source,
    records.support_record,
    records.store_record,
    organizations.steward_id,
    coalesce(records.support_problem, records.store_problem) as problem
from records
left join organizations on records.provider = organizations.provider
