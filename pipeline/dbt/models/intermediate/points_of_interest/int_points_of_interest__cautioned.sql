-- int_points_of_interest__described's rows, every one, with decision 65's
-- season caution applied (the maintainer's poll of 2026-10-04, from
-- decisions-64-67-mock.html section 2): a plumbed tap or fountain whose
-- layer records no shutoff season ships as UNCONFIRMED water, at low
-- confidence, which the phone draws as its hollow pin, and with
-- `water_caution` 'no_shutoff_season', which the waypoint card reads to say
-- the agency does not say when it is shut off and that taps like it are
-- often off out of season. Every other row passes through unchanged, with a
-- null `water_caution`.
--
-- WHICH POINTS: a water row of a layer whose layer_rules `plumbed_water` row
-- names the field and value it carries (BLM's FET_TYPE 6, NPS's four potable
-- POITYPEs, CPW's, NJDEP's, NCTA's, FLTC's and Tennessee's plumbed types,
-- IATA's pumps and fountains, and NY Parks' spigots and fountains). The
-- value is read from the row's own `properties`, by dlt's name, trimmed and
-- case-folded, as int_points_of_interest__club_points reads every rule.
-- A water row nobody marks plumbed is not cautioned: a spring or a stream is
-- not shut off for winter, and a caution on it would be a display outrunning
-- its source in the other direction.
--
-- A LAYER'S OWN SEASON FIELD WINS. Where an `open_in_winter` row matches
-- (CPW's d_WINTER_S 'Open', 1 of its 45 taps, read live 2026-10-04), the
-- layer says the tap is open in winter, so the row is still plumbed and
-- still low confidence but carries no caution. CPW's 'Closed' taps never
-- reach here: a not_water rule drops them in club_points.
--
-- Here and not in int_points_of_interest__classified, because the
-- classifier's unit test is held to export_nearby_poi.py's own answers
-- (tests/test_dbt_points_of_interest_parity.py), and this rule is the dbt
-- path's alone: today's exporter holds every plumbed tap back. A pass-through
-- rather than a table of the taps alone, because int_points_of_interest__final
-- would otherwise read described and that table both, which
-- dbt_project_evaluator fails as a rejoin and, at seven, as too many joins.
with described as (
    select * from {{ ref('int_points_of_interest__described') }}
),

rules as (
    select * from {{ ref('layer_rules') }}
    where rule in ('plumbed_water', 'open_in_winter')
),

matched as (
    select
        described.poi_id,
        rules.rule
    from described
    inner join rules
        on
            described.source_key = rules.source_key
            and lower(
                trim(
                    json_extract_string(
                        described.properties, '$.' || rules.field
                    )
                )
            )
            = lower(trim(rules.matches))
    where described.poi_type = 'water'
),

judged as (
    select
        poi_id,
        bool_or(rule = 'plumbed_water') as plumbed,
        bool_or(rule = 'open_in_winter') as open_in_winter
    from matched
    group by poi_id
),

joined as (
    select
        described.*,
        coalesce(judged.plumbed, false) as is_plumbed,
        coalesce(judged.open_in_winter, false) as is_open_in_winter
    from described
    left join judged on described.poi_id = judged.poi_id
)

select
    * exclude (confidence, is_plumbed, is_open_in_winter),
    -- Whatever its layer's own public flag rated it (NY Parks' ParksApp
    -- 'Y'): a plumbed tap is unconfirmed water.
    case when is_plumbed then 'low' else confidence end as confidence,
    case
        when is_plumbed and not is_open_in_winter then 'no_shutoff_season'
    end as water_caution
from joined
