-- A plain union all into common columns - no filter, no dedup, nothing
-- clever, which is what lets assert_int_pois_unioned_matches_staging_sum
-- prove no branch silently dropped rows (DBT.md's transformation-accuracy
-- ask). Cross-source deduplication is explicitly deferred out of Phase A and
-- Phase D did not force the question either.
--
-- THIRTEEN BRANCHES ACROSS THREE ORGANIZATIONS as of Phase D (#100): ATC's
-- six, opentrail's one, and DEC's six. This is the shape #100 was filed to
-- reach - a second organization's POIs arriving as six more branches of one
-- union rather than as a second pipeline - and adding them needed no change
-- to this model beyond the branches themselves.
--
-- POSITIONAL, so column order is a semantic contract shared by every model
-- above (which is why .sqlfluff turns ST06 off, with that reason). The
-- shape is: poi_key, source, source_id, name, poi_type, confidence,
-- public_use, longitude, latitude, loaded_at.
--
-- poi_key is each staging model's own key (decision 40 of #1793, pipeline/
-- ELT.md "One key per table"): dbt_utils.generate_surrogate_key over the
-- registry key and the columns measured unique for that layer. It is unique
-- across the union because the registry key is one of its inputs, which the
-- unique test on this model holds.
--
-- `public_use` is the column Phase D added, and it is CARRIED rather than
-- APPLIED - null where the publishing organization declares no
-- public/internal split, DEC's raw PUBLICUSE where it does.
-- stg_dec__lean_tos holds the argument for not filtering here.
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
union all
select * from {{ ref('stg_dec__lean_tos') }}
union all
select * from {{ ref('stg_dec__primitive_campsites') }}
union all
select * from {{ ref('stg_dec__scenic_vistas') }}
union all
select * from {{ ref('stg_dec__firetowers') }}
union all
select * from {{ ref('stg_dec__viewing_areas') }}
union all
select * from {{ ref('stg_dec__parking_areas') }}
