-- Whether each registered source may reach a hiker's phone, and the rule
-- that decided it (pipeline/ELT.md, "Who may publish"). One row per
-- sources.json entry. Every mart but `sources` keeps only the rows whose
-- source has `may_publish`; `sources` keeps every row and carries the flag.
--
-- A REGISTERED ROW PUBLISHES on its own `reaches_hikers` and a basis the
-- publishable_licence_bases seed lists. Every layer the extract lands has a
-- sources.json row, because a builder takes a registry key, never a URL.
-- Anything these rules do not make true is false: `unresolved` and a
-- missing basis say nobody has settled it, and an absent licence is not
-- permission.
--
-- THE GUARDS, each of which can only take a row off a phone:
-- - `public_domain` publishes only for a federal organization, because only
--   a federal work is public domain by statute (17 U.S.C. 105). sources.json
--   records no organization type, so a row with that basis is refused until
--   one is recorded. No row has it today (tests/test_organizations.py).
-- - `maintainer_clearinghouse` covers NYS DEC and OPRHP alone; another
--   steward's row with that basis is refused. Its rows quote their item's
--   own words in `terms`, which the basis answers (below).
-- - `public_gis` needs a GIS endpoint: an ArcGIS or Socrata layer
--   (`club_arcgis_layer` is a club's ArcGIS layer only the extract reads), a
--   GIS file or an OGC API Features collection (`gis_file`,
--   `ogc_features`), or a source with no `kind`, which the fetcher reads as
--   an ArcGIS layer. It also covers the points a club prints on its own
--   public page or PDF, and the route its own website's map reads them from
--   (`page_points`, `pdf_points`, `json_features`), published as facts only:
--   name, kind, the fix as stated, mile, credited and linked, none of the
--   page's prose (the maintainer's poll, 2026-10-04). A photo, audio,
--   hike-list, notice or other page source is refused: the presumption does
--   not reach prose. A club's notice pages, feeds and posts publish on
--   `maintainer_authorisation` instead: closed or open, the dates, the place
--   and a link, never the post's words (the maintainer's poll, 2026-10-08).
--
-- RESTRICTIVE WORDS NO RULING ANSWERS HOLD A ROW. Read from the row's own
-- fields: the words it quotes (`terms`, and `terms_verbatim` where a row
-- carries the whole text), its `licence_basis`, and the rulings its
-- `licence` names. Two seeds hold the vocabulary, one row per phrase, each
-- with the row it was written from:
--   licence_restriction_phrases  which restriction a phrase is: commercial,
--                                no_reuse, permission, purpose_limited,
--                                condition, conduct (a bar on disruptive
--                                or malicious use), cannot_be_met,
--                                ownership ("property of", "copyright",
--                                "all rights reserved"), or
--                                not_a_restriction (a warranty, liability,
--                                accuracy, reliance or credit line, a
--                                grant, a link or a scope note, cut out
--                                first so its words never count), and
--                                `unclassified`, the backstop
--   licence_restriction_answers  which ruling answers a restriction on
--                                which basis, and the words a row's
--                                `licence` names that ruling by
-- A restriction is answered when an answers row has its restriction and the
-- row's basis (or `any`), and the row's own `licence` names that ruling.
-- Words are read by class, never row by row (the maintainer's poll,
-- 2026-10-14): each phrase reads a class of wording, and an ownership or
-- copyright line on a public GIS item is answered for every row of its
-- basis. `cannot_be_met` has no answers row on purpose: words forbidding a
-- use the app makes ("not to be used for navigation", "not intended for
-- planning", "not suitable for navigation") hold the row however worded.
-- A BASIS THAT IS A RULING ON THE DATASET ITSELF answers the dataset's own
-- words, whatever class they read as, except `cannot_be_met` (the
-- maintainer's poll, 2026-10-15). publishable_licence_bases says which
-- bases are such a ruling, in `covers_own_words_named_by`. Only
-- `maintainer_clearinghouse` has one today, so DEC's "may NOT be
-- distributed outside DEC without permission" and OPRHP's "informational
-- and non-commercial purposes" are quoted on their rows and publish.
-- THE BACKSTOP: once every phrase is cut out, any restriction-shaped word
-- left (may not, prohibited, only, distribute, licence and the rest of the
-- `unclassified` row's list) is `unclassified`, and only a ruling on the
-- dataset itself answers it. A wording neither seed has met holds its row
-- until a person adds the phrase that explains it.
-- This comes after every other rule and changes no `publication_rule` today:
-- every row whose words it holds is also held by its own `reaches_hikers`.
-- `unanswered_restrictions` carries the verdict on every row anyway, so a
-- later flip of `reaches_hikers` meets it, and
-- assert_every_source_the_registry_ships_may_publish stops that build.
-- Measured 2026-10-14 on the registry at dd5f57f7, 782 rows: 384 publish,
-- 398 are held by their own `reaches_hikers`, 75 carry an unanswered
-- restriction, and no shipping row does. @unvalidated: the phrase list is
-- what the registry's texts needed; what would show it too loose is a
-- restriction a person finds in a row this rule passed.
--
-- ONE SOURCE IS NOT IN THE REGISTRY. The unregistered_publishing_sources
-- seed lists the sources an exporter publishes today with no sources.json
-- row, each with the issue that keeps it open: opentrail_at, under #98's
-- interim position. They publish as they do today rather than drop off
-- phones with nobody having decided that, because what drops is water
-- points. Removing a seed row is that decision, made in review.
--
-- NOT HERE YET: trail_orgs.json's `load` for a layer with no sources.json
-- row, and the four `refuse` organizations, read trail_orgs.json, which the
-- extract does not land yet, and no layer either would decide is extracted
-- today. Conditions are read here only as far as whether a ruling answers
-- them.
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

bases as (
    select * from {{ ref('publishable_licence_bases') }}
),

registered as (
    select
        sources.source_key,
        sources.kind,
        sources.reaches_hikers,
        sources.licence_basis,
        organizations.steward_id,
        -- A basis that is a maintainer's ruling on the dataset itself, named
        -- by the row's licence, answers its own words.
        coalesce(
            regexp_matches(
                coalesce(json_extract_string(sources.entry, '$.licence'), ''),
                bases.covers_own_words_named_by,
                'i'
            ),
            false
        ) as basis_covers_own_words,
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
    left join bases on sources.licence_basis = bases.licence_basis
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
        or (
            registered.basis_covers_own_words
            and restricted.restriction != 'cannot_be_met'
        ) as is_answered
    from restricted
    inner join registered on restricted.source_key = registered.source_key
    left join answers
        on
            restricted.restriction = answers.restriction
            and answers.licence_basis in (registered.licence_basis, 'any')
            and regexp_matches(registered.licence_text, answers.named_by, 'i')
    group by
        restricted.source_key,
        restricted.restriction,
        registered.basis_covers_own_words
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
                    'ogc_features',
                    -- A club's own page, PDF or map route.
                    'page_points',
                    'pdf_points',
                    'json_features'
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
