-- int_challenges__final: the challenges mart's rows before their row dates,
-- every contracted column but _first_seen_at and _changed_at. This is what
-- models/marts/challenges/challenges.sql held until decision 57;
-- int_challenges__history snapshots it, and the mart reads that snapshot.
--
-- The challenges clubs put on their own trails (#1780 — Let a club publish a
-- challenge — places on its own trails that hikers opt into and tag at camp
-- — starting with the ATC's A.T. Summer Bucket List): one row per challenge
-- that resolved (int_challenges__resolved) and whose source may publish
-- (int_sources__publication, the one home of the rule). challenges.json is
-- written from it by pub_challenges.
--
-- THE GRAIN, chosen at the port (pipeline/ELT.md, "The eleven marts"): one
-- row per challenge, keyed by its id, because a challenge is what a hiker
-- joins and what the file lists; its sections and items stay the published
-- JSON they resolved to, each item's places carrying the published POI's
-- own mile, coordinate and name (CH01).
--
-- PUBLICATION. A challenge's source is the claim its club's folder was
-- landed under (`reference/challenges/<club>`). No sources.json row records
-- one. The ATC's, reference/challenges/atc, publishes through its row of
-- unregistered_publishing_sources: pipeline/ELT.md decision 47, the
-- maintainer's authorisation as an ATC volunteer (2026-10-02), which is not
-- a written grant from the ATC, and none is in this repository. PR #1798 —
-- Challenges: a club's list of places on its own trails, joined and tagged
-- at camp, starting with the ATC's Summer Bucket List asked for that
-- written permission; decision 47 is the maintainer's answer. Any other
-- club's folder, with no row, is held back under rule 6 of "Who may
-- publish" (page prose keeps its own licence row), and the warn test on
-- int_challenges__resolved names every challenge so held back.
with resolved as (
    select * from {{ ref('int_challenges__resolved') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
)

select
    resolved.challenge_id,
    resolved.club,
    resolved.source_key,
    resolved._loaded_at,
    resolved.org,
    resolved.org_name,
    resolved.org_short,
    resolved.org_domain,
    resolved.trail,
    resolved.name,
    resolved.status,
    resolved.challenge_summary,
    resolved.window_opens,
    resolved.window_closes,
    resolved.finish_count,
    resolved.finish_label,
    resolved.reward_kind,
    resolved.reward_rules_url,
    resolved.reward_art,
    resolved.takes_entries,
    resolved.photo,
    resolved.reviewed,
    cast(resolved.sections_published as json) as sections,
    cast(resolved.items_published as json) as items,
    resolved.item_count,
    resolved.sealed_item_count,
    resolved.list_position
from resolved
inner join publication on resolved.source_key = publication.source_key
where resolved.problem is null and publication.may_publish
