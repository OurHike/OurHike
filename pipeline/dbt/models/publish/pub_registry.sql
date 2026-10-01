{{ config(format='json', location='registry.json') }}
-- registry.json, the org console's list of every registered source (#929),
-- in the shape export_sources.py's build_registry() writes: one row per
-- source by provider and key, then the organizations by provider.
with sources as (
    select * from {{ ref('sources') }}
),

registered as (
    select
        coalesce(list(
            json_object(
                'key', source_key,
                'title', title,
                'provider', provider,
                'steward_id', steward_id,
                'steward', steward,
                'kind', kind,
                'trust', trust,
                'reaches_hikers', reaches_hikers,
                'licence_basis', licence_basis,
                'freshness_kind', freshness_kind,
                'supports_donation', supports_donation,
                'mark_state', mark_state
            ) order by provider, source_key
        ), []) as registered_sources
    from sources
),

organizations as (
    select distinct
        steward_id,
        provider,
        org_name,
        org_note
    from sources
    where steward_id is not null
),

listed as (
    select
        coalesce(list(
            json_object(
                'steward_id', steward_id,
                'provider', provider,
                'name', org_name,
                'note', org_note
            ) order by provider
        ), []) as listed_organizations
    from organizations
)

select
    registered.registered_sources as sources,
    listed.listed_organizations as organizations
from registered
cross join listed
