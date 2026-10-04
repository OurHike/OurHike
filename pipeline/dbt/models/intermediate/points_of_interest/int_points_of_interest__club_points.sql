{{ config(materialized='table') }}
-- Every point of decision 54's wave 1 point layers
-- (int_points_of_interest__club_unioned) with its POI type and the rules
-- pipeline/ELT.md's "What wave 1's live reads found that phase C must
-- honour" gives points of interest, read from two seeds that quote the
-- evidence each row rests on: club_poi_types says what a layer's own field
-- values are, and layer_rules what holds a row back whatever it maps to.
-- One row per unioned row. int_points_of_interest__unioned reads it as a
-- branch of already-typed records, so the classifier, the public flags,
-- int_sources__publication's verdict, the corridor ring and the dedupe all
-- run over these rows as over every other organization's; a row this model
-- gives a `rule_drop_reason` never ships and says why in
-- int_points_of_interest__dropped.
--
-- A POI TYPE IS AN ALLOWLIST. A row is typed only by a club_poi_types row
-- naming the field and value it carries, or the layer's one row naming
-- neither; a value nobody mapped publishes nothing. Two rows typing it
-- differently drop it rather than pick one.
--
-- THE RULES, each a unit test in _points_of_interest__club_points.yml, and
-- each applied before the type map so no mapping can bring a row back:
-- - A WATER TYPE IS NOT WATER. A `not_water` rule (layer-wide, or where its
--   field equals its value) drops a row the map would type water: GNIS's
--   springs are names on a map, CDTC's caches can be empty, PA DCNR's
--   'Potable Water' buildings are plumbing, BLM's water-based sites hold
--   its firefighting 'Staging Area', and IATA's water is water only where
--   its Potability code says so (1 Potable, 2 Treatment required; never 0
--   No water, 5 Undrinkable or 9 Unknown). Plumbed water whose shutoff
--   season no layer records (fountains, pumps, BLM's, NPS's and CPW's
--   potable-water types) was held the same way until decision 65
--   (2026-10-04): club_poi_types now types it water, and its layer_rules
--   `plumbed_water` row gives it a season caution downstream
--   (int_points_of_interest__cautioned), which this model does not
--   read. A tap CPW marks closed in winter is still not_water. Every water
--   row that does map is low confidence: no wave 1 layer reports flow.
-- - PLANNED AND PROPOSED POINTS ARE NOT BUILT: `drop_where` on NPS's
--   POISTATUS 'Planned', Alaska Trails' Status 'Proposed', the Cumberland
--   Trail's 'Trailhead Proposed' and CFPA's future campsites, and
--   `drop_layer` on SBTS's planning layer.
-- - NOT PUBLIC IS NOT SHOWN: `keep_only_where` USFWS's Public_Use is
--   'Public Use' (non-public, limited and unknown rows are left out),
--   `drop_where` on its sewage and fuel sites and PA DCNR's staff
--   residences, and on each publisher's own withhold flag.
-- - NOTICES HIDE IN POI LAYERS: FLTC's hunting closures and high-water
--   advisories, the 2018 fire closure in PCTA's Halfmile water popups, and
--   the warning types of NCTA's and Tennessee State Parks' layers never
--   publish as POIs (decision 53's notices are their home).
-- - Closed sites in a layer's own words, and dispersed camping, which
--   usfs_dispersed_camping_holdback holds back, drop the same way.
-- - A POINT LISTED TWICE IS ONE POINT: of a layer's rows that share a name
--   and a fix, one ships (the `repeats` CTE says which, and why).
--
-- THE ID a row publishes under is `<source_key>:<source_id>`, the layer's
-- own id where its registry id_field is one, and the base model's key where
-- it is a server row id (make_dbt_staging.py's source_id).
--
-- GEOMETRY IS TEXT HERE (geom_wkt), as int_trail_lines__club_lines carries
-- it: dbt 2.0.6 cannot hold a GEOMETRY in a unit-tested model's output.
with unioned as (
    select * from {{ ref('int_points_of_interest__club_unioned') }}
),

rules as (
    select * from {{ ref('layer_rules') }}
    where
        rule in (
            'drop_where',
            'drop_where_contains',
            'keep_only_where',
            'drop_layer',
            'not_water'
        )
),

type_map as (
    select * from {{ ref('club_poi_types') }}
),

rule_reads as (
    -- Each row's value of each field a rule on its layer names, trimmed and
    -- folded; null for a layer-wide rule.
    select
        unioned.poi_key,
        rules.rule,
        rules.field,
        rules.matches,
        lower(rules.matches) as matches_folded,
        lower(
            trim(json_extract_string(unioned.properties, '$.' || rules.field))
        ) as value_folded
    from unioned
    inner join rules on unioned.source_key = rules.source_key
),

held as (
    select
        poi_key,
        'layer_rules drop_where: '
        || field
        || ' is '
        || matches as reason
    from rule_reads
    where rule = 'drop_where' and value_folded = matches_folded
    union all
    select
        poi_key,
        'layer_rules drop_where_contains: '
        || field
        || ' contains '
        || matches as reason
    from rule_reads
    where
        rule = 'drop_where_contains'
        and contains(value_folded, matches_folded)
    union all
    select
        poi_key,
        'layer_rules drop_layer: the whole layer is held back' as reason
    from rule_reads
    where rule = 'drop_layer'
    union all
    select
        poi_key,
        'layer_rules keep_only_where: '
        || field
        || ' is not '
        || string_agg(matches, ' or ' order by matches) as reason
    from rule_reads
    where rule = 'keep_only_where'
    group by poi_key, field
    having not coalesce(bool_or(value_folded = matches_folded), false)
),

first_held as (
    select
        poi_key,
        min(reason) as reason
    from held
    group by poi_key
),

repeats as (
    -- A POINT LISTED TWICE IS ONE POINT. A layer that lists the same point
    -- under two headings lands it once a heading: PATC's Tuscarora pages
    -- list a section's end under both sections it joins (20 fixes, its
    -- key_comment), and UGRC's trailheads carry two rows that share a name
    -- and a fix and differ only in TrailheadID. Rows of one layer whose
    -- name and point are the same are one pin; the first by poi_key that no
    -- rule holds back is kept, so a held listing never hides its twin. A
    -- point with no name is never folded: nothing says two are the same.
    select poi_key
    from (
        select
            unioned.poi_key,
            row_number() over (
                partition by
                    unioned.source_key,
                    lower(trim(unioned.name)),
                    st_astext(unioned.geom)
                order by first_held.reason is not null, unioned.poi_key
            ) as listing
        from unioned
        left join first_held on unioned.poi_key = first_held.poi_key
        where
            unioned.geom is not null
            and nullif(trim(unioned.name), '') is not null
    )
    where listing > 1
),

never_water as (
    select
        poi_key,
        min(
            'layer_rules not_water: '
            || coalesce(field || ' is ' || matches, 'the whole layer')
        ) as reason
    from rule_reads
    where
        rule = 'not_water'
        and (field is null or value_folded = matches_folded)
    group by poi_key
),

type_matches as (
    select
        unioned.poi_key,
        type_map.poi_type,
        type_map.confidence
    from unioned
    inner join type_map
        on
            unioned.source_key = type_map.source_key
            and (
                type_map.field is null
                or lower(
                    trim(
                        json_extract_string(
                            unioned.properties, '$.' || type_map.field
                        )
                    )
                )
                = lower(type_map.value)
            )
),

typed as (
    select
        poi_key,
        count(distinct poi_type) as type_count,
        min(poi_type) as poi_type,
        bool_or(confidence = 'low') as any_low
    from type_matches
    group by poi_key
)

select
    unioned.poi_key,
    unioned.source_key,
    unioned.club,
    nullif(trim(unioned.name), '') as name,
    unioned.source_id,
    unioned.source_key || ':' || unioned.source_id as derived_id,
    case when typed.type_count = 1 then typed.poi_type end as poi_type,
    case
        when typed.type_count = 1 and typed.any_low then 'low'
        when typed.type_count = 1 then 'high'
    end as confidence,
    case
        when first_held.reason is not null then first_held.reason
        when typed.type_count > 1
            then 'two club_poi_types rows type it differently'
        when repeats.poi_key is not null
            then 'a second listing of a point its layer already lists'
        when typed.poi_type = 'water' and never_water.reason is not null
            then never_water.reason
    end as rule_drop_reason,
    st_astext(unioned.geom) as geom_wkt,
    unioned.properties,
    unioned._loaded_at
from unioned
left join typed on unioned.poi_key = typed.poi_key
left join first_held on unioned.poi_key = first_held.poi_key
left join repeats on unioned.poi_key = repeats.poi_key
left join never_water on unioned.poi_key = never_water.poi_key
