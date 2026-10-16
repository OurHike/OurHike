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
--   `maintainer_authorisation`, `public_gis`, `maintainer_clearinghouse`
--   and `unresolved`.
-- - `maintainer_clearinghouse` covers NYS DEC and
--   OPRHP alone, so another steward's row with that basis is refused. The
--   13 rows whose datasets the NYS GIS Clearinghouse lists carry it since
--   2026-10-15, each quoting its item's own words in `terms`, which the
--   basis answers (rule 5, below); tests/test_organizations.py holds it to
--   those two organizations' rows before this guard would see one.
-- - `public_gis` needs a GIS endpoint: an ArcGIS or Socrata
--   layer (`club_arcgis_layer` is a club's ArcGIS layer that only the
--   extract reads, lib/source_registry.py), a GIS file or an OGC API
--   Features collection (`gis_file`, `ogc_features`, the waves 2
--   and 3: a club's own KML, GPX or GeoJSON on a public URL is a GIS layer
--   it publishes, Reasoned), or a source with no `kind`, which the fetcher
--   reads as an ArcGIS layer. Decision 69 (the maintainer's poll,
--   2026-10-04) extends it to the points a club prints on its own public
--   web page or PDF, and to the route its own website's map reads them
--   from: `page_points`, `pdf_points` and `json_features`, published as
--   facts only (name, kind, the fix as the page states it, mile), credited
--   and linked, none of the page's prose. That these kinds carry a club's
--   own points and no prose is held in tests/test_organizations.py, since
--   no model here knows an organization's type. A photo, audio, hike-list,
--   notice or other page source is still refused (rule 6): the
--   presumption does not reach prose. A club's notice pages, feeds and
--   posts publish on another basis, the maintainer's facts and a link
--   (`maintainer_authorisation`; 131 of the 132 such
--   sources in seeds/notice_readers.csv on 2026-10-08, TATC's republished
--   ridgerunner reports `unresolved`), which decision 107 (the
--   maintainer's poll, 2026-10-08) confirmed for clubs' closure posts:
--   closed or open, the dates, the place and a link, never the post's
--   words.
-- - RULE 5: restrictive words that no decision answers. Read from the row's
--   own fields: the words it quotes (`terms`, and `terms_verbatim` where a
--   row carries the whole text), its `licence_basis`, and the decisions and
--   rulings its `licence` names. Two seeds hold the vocabulary, one row per
--   phrase, each with the row it was written from:
--     licence_restriction_phrases  which restriction a phrase is:
--                                  commercial, no_reuse, permission,
--                                  purpose_limited, condition, conduct
--                                  (a site's bar on disruptive or
--                                  malicious use),
--                                  cannot_be_met, ownership (an ownership
--                                  or copyright line: "property of",
--                                  "copyright", "all rights reserved"),
--                                  or not_a_restriction (a warranty,
--                                  liability, accuracy, reliance or credit
--                                  line, a grant, a link, or a scope note,
--                                  cut out first so its words never count:
--                                  decision 71 reads a hold-harmless or
--                                  indemnity clause as one, decision 72
--                                  "at your own risk" and "may be out of
--                                  date", decision 188 "should not be
--                                  considered authoritative", and decision
--                                  193 "illustrative, informational or
--                                  planning purposes" with the purposes
--                                  decisions 80 and 106 read);
--                                  and `unclassified`, the backstop
--     licence_restriction_answers  which decision answers a restriction on
--                                  which basis, and the words a row's
--                                  `licence` names it by
--   A restriction is answered when an answers row has its restriction and
--   the row's basis (or `any`), and the row's own `licence` names that
--   decision. DECISION 193 (the maintainer's poll, 2026-10-14) reads a
--   layer's own words by class, never row by row: each phrase reads a class
--   of wording, not one publisher's sentence, and its class answer, an
--   ownership or copyright line on a public GIS item (`public_gis`,
--   `stated_by_org`, `maintainer_clearinghouse`), names `.*`, which every
--   row's licence matches. `cannot_be_met` has no answers row on purpose:
--   decision 38 holds a layer whose condition a hiker's planning tool cannot
--   meet, and decision 193 keeps words forbidding a use the app makes as
--   that hold, however worded. The cannot_be_met row reads the wordings its
--   `why` names: "not to be used", "not intended" or "not intended to be
--   used" for navigation or planning, "not for navigation", "do not use ...
--   for navigation" and "not suitable for navigation".
--   A BASIS THAT IS A RULING ON THE DATASET ITSELF answers the dataset's
--   own words, whatever class they read as, except `cannot_be_met`
--   (the maintainer's poll of 2026-10-15: "Decisions 20
--   and 22 cover a clearinghouse dataset's own restrictive words, so quote
--   them in its `terms`"). The publishable_licence_bases seed says which
--   bases are such a ruling, in `covers_own_words_named_by`: the words a
--   row's `licence` must name the ruling by, as an answers row's
--   `named_by` does. Only `maintainer_clearinghouse` has one today
--   (decisions 20 and 22 rule on a DEC or OPRHP dataset by its listing in
--   the NYS GIS Clearinghouse, not on any wording of it), so DEC's "may NOT
--   be distributed outside DEC without permission" and OPRHP's "informational
--   and non-commercial purposes" are quoted on their rows and publish. Words
--   forbidding a use the app makes still hold such a row: decision 38 and
--   decision 193 hold them however worded, and no ruling on a dataset
--   makes a navigation line safe to navigate by.
--   THE BACKSTOP. Once every phrase is cut out of the words, any
--   restriction-shaped word left (may not, prohibited, only, distribute,
--   licence and the rest of the `unclassified` row's list) is
--   `unclassified`, and no answers row answers it; only a basis that is a
--   ruling on the dataset itself does, above. So a wording neither seed
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
--   Re-measured 2026-10-05 on the registry after decisions 69 to 75 and
--   section K's merge (43989398), 692 rows, with the seeds' patterns run in
--   DuckDB over sources.json as these CTEs run them (a reproduction, not a
--   dbt run): 446 quote words; 153 carry a restriction; 79 are unanswered,
--   every one held by its own `reaches_hikers`. Before the answers, on 670
--   rows at 3510e68e, 80 were. The answers took three off that list: OHTA's
--   copyright footer, FMST's "updated only when" (decision
--   72) and IN.gov's clause on bots. Decision 71 moved no
--   verdict: rule 5 already read a hold-harmless line as a liability line.
--   Re-measured 2026-10-08 the same way, on the registry after decision 106
--   (branch d106-107, from 4ad88f3b), 693 rows: 449 quote words; 153 carry
--   a restriction; 79 are unanswered, every one held by its own
--   `reaches_hikers`. The one new quote is pasda_explore_pa_trail_access's,
--   PA DCNR's Explore PA Trails terms, which carry no restriction once
--   the and the phrases are cut out; without decision
--   106's phrase the same words read purpose_limited, unanswered.
--   Re-measured 2026-10-14 the same way, on the registry after decision 193
--   (W11's build, from dd5f57f7), 782 rows: 384 publish and 398 are held by
--   their own `reaches_hikers`; 75 carry an unanswered restriction (90
--   before), and no shipping row does. Under the classes seven rows flipped
--   to publishing, each with its own rules in and tested: CPW's
--   trailheads, facilities and managed properties ("a product and property
--   of"), Blue Hills' parking and intersections, OTA's map and OHTA's track.
--   They also corrected two stated reasons (CFPA's two layers read
--   cannot_be_met, the class their typo "to be use" hid), and held one row a
--   live read found: in_dnr_open_trails' own description says "NOT INTENDED
--   TO BE USED FOR ON-THE-GROUND NAVIGATION".
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
-- rule would decide is extracted today. The conditions are read
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
        -- Rule 5's general answer: the row's basis is a maintainer's ruling
        -- on the dataset itself, and its licence names that ruling.
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
