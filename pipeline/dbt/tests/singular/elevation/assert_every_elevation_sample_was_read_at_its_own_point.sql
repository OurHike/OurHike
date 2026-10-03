-- Every point the DEM is asked about (int_elevation__dem_points: the A.T.'s
-- walk and every junction-graph edge's samples) was read by step_dem_sampling
-- at that point, once, and the step read no point that is not there. The DEM
-- step runs between two dbt invocations (pipeline/step_dem_sampling.py), so
-- its table can be missing rows if the step failed partway, or be a table an
-- earlier build left behind for a walk or a graph that has since moved;
-- either way a sample would have no elevation it should have, and with an
-- earlier build's rows it could be lent one from another place.
-- int_elevation__profile and int_elevation__edge_samples join on the point
-- itself so that never happens; this fails the build so that a profile with
-- holes the DEM did not make is never written.
with points as (
    select
        line_id,
        sample_index,
        lon,
        lat
    from {{ ref('int_elevation__dem_points') }}
),

dem as (
    select
        line_id,
        sample_index,
        lon,
        lat
    from {{ ref('stg_derived__dem_samples') }}
)

select
    points.line_id,
    points.sample_index,
    case
        when dem.sample_index is null then 'not read'
        else 'read at another point'
    end as problem
from points
left join dem
    on
        points.line_id = dem.line_id
        and points.sample_index = dem.sample_index
where
    dem.sample_index is null
    or dem.lon != points.lon
    or dem.lat != points.lat
union all
select
    dem.line_id,
    dem.sample_index,
    'read for no sample point' as problem
from dem
left join points
    on
        dem.line_id = points.line_id
        and dem.sample_index = points.sample_index
where points.sample_index is null
