-- Whether each registered source may reach a hiker's phone, and the rule
-- that decided it (pipeline/ELT.md, "Who may publish"). One row per
-- sources.json entry. Every mart but `sources` keeps only the rows whose
-- source has `may_publish`; `sources` keeps every row and carries the flag.
--
-- RULE 1 DECIDES EVERY ROW TODAY. A builder takes a registry key, never a
-- URL (.claude/skills/dlt/SKILL.md), so every layer the extract lands has a
-- sources.json row, and a registered row publishes on its own
-- `reaches_hikers` and a basis the publishable_licence_bases seed lists.
-- Anything the rules do not make true is false: `unresolved` and a missing
-- basis say nobody has settled it, and an absent licence is not permission.
--
-- THE GUARDS, each of which can only take a row off a phone:
-- - `public_domain` publishes only for a federal organization, because only
--   a federal work is public domain by statute (17 U.S.C. 105). sources.json
--   records no organization type, so a registered row with that basis is
--   refused until one is recorded. No row has it today:
--   tests/test_organizations.py holds the registry to `stated_by_org`,
--   `maintainer_authorisation` and `unresolved`.
-- - `maintainer_clearinghouse` (decisions 20 and 22) covers NYS DEC and
--   OPRHP alone, so another steward's row with that basis is refused.
-- - `public_gis` (decision 21a) needs a GIS endpoint: an ArcGIS or Socrata
--   layer, or a source with no `kind`, which the fetcher reads as an ArcGIS
--   layer. A photo, audio or page source is refused (rule 6).
--
-- ONE ROW IS NOT IN THE REGISTRY. The unregistered_publishing_sources seed
-- lists the sources an exporter publishes today with no sources.json row,
-- each with the issue that keeps it open: opentrail_at, under #98's interim
-- position. They publish as they do today rather than drop off phones with
-- nobody having decided that, because what drops is water points (CLAUDE.md,
-- "Four ways this app can hurt somebody"). Removing a seed row is that
-- decision, made in review.
--
-- NOT HERE YET, and why. Rule 2 (trail_orgs.json's `load` for a layer with
-- no sources.json row) and rule 7 (the four `refuse` organizations) read
-- trail_orgs.json, which the extract does not land yet, and no layer either
-- rule would decide is extracted today. Rule 5 (restrictive text no decision
-- names, and decision 38's conditions) reads fields no sources.json row
-- carries yet. Each arrives with the rows it decides.
with sources as (
    select * from {{ ref('stg_registry__sources') }}
),

organizations as (
    select * from {{ ref('stg_registry__organizations') }}
),

registered as (
    select
        sources.source_key,
        sources.kind,
        sources.reaches_hikers,
        sources.licence_basis,
        organizations.steward_id
    from sources
    left join organizations on sources.provider = organizations.provider
),

bases as (
    select * from {{ ref('publishable_licence_bases') }}
),

unregistered as (
    select * from {{ ref('unregistered_publishing_sources') }}
),

decided as (
    select
        registered.source_key,
        registered.licence_basis,
        case
            when not registered.reaches_hikers
                then 'held_back_by_the_registry'
            when bases.licence_basis is null
                then 'basis_not_publishable'
            when bases.applies_to = 'federal'
                then 'public_domain_needs_a_federal_organization'
            when
                bases.applies_to = 'nys_clearinghouse'
                and coalesce(registered.steward_id, '')
                not in ('org:nysdec', 'org:nysoprhp')
                then 'clearinghouse_basis_outside_new_york'
            when
                bases.applies_to = 'gis'
                and coalesce(registered.kind, 'external_arcgis_layer')
                not in ('external_arcgis_layer', 'socrata_geojson_layer')
                then 'public_gis_needs_a_gis_endpoint'
            else 'registered_and_publishable'
        end as publication_rule
    from registered
    left join bases on registered.licence_basis = bases.licence_basis
)

select
    source_key,
    publication_rule = 'registered_and_publishable' as may_publish,
    publication_rule,
    licence_basis
from decided

union all

select
    source_key,
    true as may_publish,
    'publishing_before_registration' as publication_rule,
    cast(null as varchar) as licence_basis
from unregistered
