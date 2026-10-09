-- Every unioned row either ships or says why it does not: the union's rows
-- are exactly the points_of_interest mart's rows that came from the union
-- plus int_points_of_interest__dropped's, each with a reason (pipeline/
-- ELT.md, the stage-3 successor of assert_points_of_interest_matches_
-- int_pois_unioned, which held the two 1:1 before any filter existed). The
-- mart's other rows are made rather than read: the synthesized CSI water
-- points (source atc_csi) and the tombstones. Fails by returning the
-- poi_keys that are in neither, or in both.
with unioned as (
    select poi_key from {{ ref('int_points_of_interest__unioned') }}
),

shipped as (
    select poi_key from {{ ref('points_of_interest', v=1) }}
    where
        phone_files in ('poi_by_type', 'nearby_poi')
        and source != 'atc_csi'
),

dropped as (
    select poi_key from {{ ref('int_points_of_interest__dropped') }}
),

accounted as (
    select
        poi_key,
        'shipped' as fate
    from shipped
    union all
    select
        poi_key,
        'dropped' as fate
    from dropped
)

select
    coalesce(unioned.poi_key, accounted.poi_key) as poi_key,
    count(accounted.fate) as fates,
    count(unioned.poi_key) as unioned_rows
from unioned
full outer join accounted on unioned.poi_key = accounted.poi_key
group by coalesce(unioned.poi_key, accounted.poi_key)
having count(accounted.fate) != 1 or count(unioned.poi_key) != 1
