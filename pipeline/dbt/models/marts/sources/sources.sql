-- Every registered source (one row per layer or feed in sources.json), with
-- the record of the steward it is credited to on a hiker's phone. The
-- steward's columns are null for a source whose provider ships nothing,
-- which today is GATC's and OPRHP's. stewards.json and registry.json are
-- both written from this (pub_stewards, pub_registry).
--
-- `may_publish` (pipeline/ELT.md, "Who may publish") is not here yet: it
-- needs every club's org row, which int_sources__publication reads, and
-- arrives with it. Until then `reaches_hikers` is the registry's answer, as
-- it is export_sources.py's.
with registered as (
    select * from {{ ref('int_sources__registered') }}
),

stewards as (
    select * from {{ ref('int_sources__stewards') }}
)

select
    registered.source_key,
    registered.title,
    registered.provider,
    registered.steward_id,
    registered.steward,
    registered.kind,
    registered.trust,
    registered.reaches_hikers,
    registered.licence_basis,
    registered.freshness_kind,
    registered.supports_donation,
    registered.mark_state,
    registered.org_name,
    registered.org_note,
    stewards.steward_name,
    stewards.steward_trust,
    stewards.licence as steward_licence,
    stewards.attribution as steward_attribution,
    stewards.terms as steward_terms,
    stewards.terms_source as steward_terms_source,
    stewards.support_record as steward_support,
    stewards.store_record as steward_store,
    registered.file_row as list_position
from registered
left join stewards on registered.provider = stewards.provider
