{{ config(format='json', location='stewards.json') }}
-- stewards.json, "Where this map comes from" on the phone (#927), in the
-- shape export_sources.py's build_output() writes: one record per steward
-- whose data reaches a hiker, by provider. `layers` and `keys` are each
-- sorted on their own, so they are not index-aligned, as the Python warns.
with sources as (
    select * from {{ ref('sources') }}
),

stewards as (
    select
        provider,
        any_value(steward_name) as steward_name,
        any_value(steward_trust) as steward_trust,
        any_value(steward_licence) as steward_licence,
        any_value(steward_attribution) as steward_attribution,
        any_value(steward_terms) as steward_terms,
        any_value(steward_terms_source) as steward_terms_source,
        any_value(steward_support) as steward_support,
        any_value(steward_store) as steward_store,
        any_value(steward_id) as steward_id,
        list_sort(list(coalesce(title, source_key))) as layers,
        list_sort(list(source_key)) as source_keys
    from sources
    where reaches_hikers
    group by provider
)

select
    coalesce(list(
        json_object(
            'provider', provider,
            'name', steward_name,
            'trust', steward_trust,
            'licence', steward_licence,
            'attribution', steward_attribution,
            'terms', steward_terms,
            'terms_source', steward_terms_source,
            'layers', layers,
            'keys', source_keys,
            'support', steward_support,
            'store', steward_store,
            'steward_id', steward_id
        ) order by provider
    ), []) as stewards
from stewards
