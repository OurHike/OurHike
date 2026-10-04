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
--   `maintainer_authorisation`, `public_gis` and `unresolved`.
-- - `maintainer_clearinghouse` (decisions 20 and 22) covers NYS DEC and
--   OPRHP alone, so another steward's row with that basis is refused.
-- - `public_gis` (decision 21a) needs a GIS endpoint: an ArcGIS or Socrata
--   layer (`club_arcgis_layer` is a club's ArcGIS layer that only the
--   extract reads, lib/source_registry.py), a GIS file or an OGC API
--   Features collection (`gis_file`, `ogc_features`, decision 54's waves 2
--   and 3: a club's own KML, GPX or GeoJSON on a public URL is a GIS layer
--   it publishes, Reasoned), or a source with no `kind`, which the fetcher
--   reads as an ArcGIS layer. A JSON API's items (`json_features`), a
--   photo, audio or page source is refused (rule 6): whether a website's
--   own map route is a GIS endpoint is the maintainer's to say.
-- - RULE 5: restrictive words that no decision answers. Read from the row's
--   own fields: the words it quotes (`terms`, and `terms_verbatim` where a
--   row carries the whole text), its `licence_basis`, and the decisions and
--   rulings its `licence` names. Two seeds hold the vocabulary, one row per
--   phrase, each with the row it was written from:
--     licence_restriction_phrases  which restriction a phrase is:
--                                  commercial, no_reuse, permission,
--                                  purpose_limited, condition,
--                                  cannot_be_met, or not_a_restriction (a
--                                  warranty, liability, accuracy or credit
--                                  line, cut out first so its words never
--                                  count); and `unclassified`, the backstop
--     licence_restriction_answers  which decision answers a restriction on
--                                  which basis, and the words a row's
--                                  `licence` names it by
--   A restriction is answered when an answers row has its restriction and
--   the row's basis (or `any`), and the row's own `licence` names that
--   decision. `cannot_be_met` has no answers row on purpose: decision 38
--   holds a layer whose condition a hiker's planning tool cannot meet.
--   THE BACKSTOP. Once every phrase is cut out of the words, any
--   restriction-shaped word left (may not, prohibited, only, distribute,
--   licence and the rest of the `unclassified` row's list) is
--   `unclassified`, and no decision answers it. So a wording neither seed
--   has met holds its row until a person adds the phrase that explains it,
--   rather than publishing by default.
--   The rule comes after every other, so it changes no `publication_rule`
--   a row has today: every row whose words it holds is also held by its own
--   `reaches_hikers` (counted below). `unanswered_restrictions` carries its
--   verdict on every row anyway, so a later flip of `reaches_hikers` meets
--   it, and assert_every_source_the_registry_ships_may_publish stops that
--   build rather than publish words nobody answered.
--   Measured 2026-10-03 on the registry at 52835a44, 236 rows: 95 quote
--   words; 20 of them carry a restriction; 3 are unanswered, all held by
--   the registry already: cpw_managed_properties and cpw_property_centroids
--   ("a product and property of Colorado Parks and Wildlife", whose
--   licence names decision 21(a) and not 37, where cpw_bear_conflict_areas'
--   names 37 over the same words), and ttc_management_areas ("for the sole
--   purpose of geographic reference"). @unvalidated: the phrase list is
--   what those 95 texts needed, and its coverage of a wording nobody has
--   read is what the backstop is for; what would show it too loose is a
--   restriction a person finds in a row this rule passed.
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
-- rule would decide is extracted today. Decision 38's conditions are read
-- here only as far as whether a decision answers them; carrying each one
-- with its layer into the sources mart arrives with the rows it decides.
with sources as (
    select * from {{ ref('stg_registry__sources') }}
),

organizations as (
    select * from {{ ref('stg_registry__organizations') }}
),

phrases as (
    select * from {{ ref('licence_restriction_phrases') }}
),

answers as (
    select * from {{ ref('licence_restriction_answers') }}
),

registered as (
    select
        sources.source_key,
        sources.kind,
        sources.reaches_hikers,
        sources.licence_basis,
        organizations.steward_id,
        nullif(
            trim(
                concat_ws(
                    ' ',
                    json_extract_string(sources.entry, '$.terms'),
                    json_extract_string(sources.entry, '$.terms_verbatim')
                )
            ),
            ''
        ) as terms_text,
        coalesce(
            json_extract_string(sources.entry, '$.licence'), ''
        ) as licence_text
    from sources
    left join organizations on sources.provider = organizations.provider
),

-- Each class's phrases as one alternation, for regexp_replace to cut out.
alternations as (
    select
        string_agg('(?:' || pattern || ')', '|') filter (
            where restriction = 'not_a_restriction'
        ) as not_restrictions,
        string_agg('(?:' || pattern || ')', '|') filter (
            where restriction not in ('not_a_restriction', 'unclassified')
        ) as restrictions
    from phrases
),

-- The quoted words with every disclaimer, credit and label cut out first,
-- so a warranty's "shall not" never reads as a restriction.
read_words as (
    select
        registered.source_key,
        regexp_replace(
            registered.terms_text, alternations.not_restrictions, ' ', 'gi'
        ) as words
    from registered
    cross join alternations
    where registered.terms_text is not null
),

found as (
    select distinct
        read_words.source_key,
        phrases.restriction
    from read_words
    inner join phrases
        on regexp_matches(read_words.words, phrases.pattern, 'i')
    where phrases.restriction not in ('not_a_restriction', 'unclassified')
),

-- What no phrase explains: the backstop reads it.
leftover as (
    select
        read_words.source_key,
        regexp_replace(
            read_words.words, alternations.restrictions, ' ', 'gi'
        ) as words
    from read_words
    cross join alternations
),

unclassified as (
    select distinct
        leftover.source_key,
        phrases.restriction
    from leftover
    inner join phrases
        on
            phrases.restriction = 'unclassified'
            and regexp_matches(leftover.words, phrases.pattern, 'i')
),

restricted as (
    select
        source_key,
        restriction
    from found
    union distinct
    select
        source_key,
        restriction
    from unclassified
),

judged as (
    select
        restricted.source_key,
        restricted.restriction,
        coalesce(bool_or(answers.restriction is not null), false)
            as is_answered
    from restricted
    inner join registered on restricted.source_key = registered.source_key
    left join answers
        on
            restricted.restriction = answers.restriction
            and answers.licence_basis in (registered.licence_basis, 'any')
            and regexp_matches(registered.licence_text, answers.named_by, 'i')
    group by restricted.source_key, restricted.restriction
),

rule_five as (
    select
        source_key,
        string_agg(restriction, ', ' order by restriction)
            as terms_restrictions,
        string_agg(restriction, ', ' order by restriction) filter (
            where not is_answered
        ) as unanswered_restrictions
    from judged
    group by source_key
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
        rule_five.terms_restrictions,
        rule_five.unanswered_restrictions,
        case
            -- A null verdict holds the row back: nobody said it ships.
            when not coalesce(registered.reaches_hikers, false)
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
                not in (
                    'external_arcgis_layer',
                    'club_arcgis_layer',
                    'socrata_geojson_layer',
                    'gis_file',
                    'ogc_features'
                )
                then 'public_gis_needs_a_gis_endpoint'
            when rule_five.unanswered_restrictions is not null
                then 'restrictive_terms_no_decision_answers'
            else 'registered_and_publishable'
        end as publication_rule
    from registered
    left join bases on registered.licence_basis = bases.licence_basis
    left join rule_five on registered.source_key = rule_five.source_key
)

select
    source_key,
    publication_rule = 'registered_and_publishable' as may_publish,
    publication_rule,
    licence_basis,
    terms_restrictions,
    unanswered_restrictions
from decided

union all

select
    source_key,
    true as may_publish,
    'publishing_before_registration' as publication_rule,
    cast(null as varchar) as licence_basis,
    cast(null as varchar) as terms_restrictions,
    cast(null as varchar) as unanswered_restrictions
from unregistered
