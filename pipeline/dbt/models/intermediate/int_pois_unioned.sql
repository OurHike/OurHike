-- A plain union all into common columns - no filter, no dedup, nothing
-- clever, which is what lets assert_int_pois_unioned_matches_staging_sum
-- prove no branch silently dropped rows (DBT.md's transformation-accuracy
-- ask). Cross-source deduplication is explicitly deferred out of Phase A.
select * from {{ ref('stg_atc__shelters') }}
union all
select * from {{ ref('stg_atc__campsites') }}
union all
select * from {{ ref('stg_atc__viewpoints') }}
union all
select * from {{ ref('stg_atc__parking') }}
union all
select * from {{ ref('stg_atc__privies') }}
union all
select * from {{ ref('stg_atc__communities') }}
union all
select * from {{ ref('stg_opentrail__waypoints') }}
