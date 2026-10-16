{{ config(materialized='table') }}
-- The A.T. shelters and campsites whose water step_site_water asks about
-- every row of ATC's two layers that has a point, as
-- fetch_trail_water.py reads them through build_water_distance.py's
-- fetch_atc_features() today, which keeps a feature only where it carries a
-- geometry. One row per site. The step orders them as fetch_atc_features
-- does (by name, then GlobalID) and reads nothing else, so the key,
-- water_site_key (dbt_utils.generate_surrogate_key over layer and GlobalID),
-- stays in the warehouse.
with sites as (
    select
        'shelters' as layer,
        globalid as global_id,
        name,
        geom
    from {{ ref('stg_atc__shelters') }}
    union all
    select
        'campsites' as layer,
        globalid as global_id,
        name,
        geom
    from {{ ref('stg_atc__campsites') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['sites.layer', 'sites.global_id']) }}
        as water_site_key,
    sites.layer,
    sites.global_id,
    sites.name,
    st_y(sites.geom) as lat,
    st_x(sites.geom) as lon
from sites
where sites.geom is not null and not st_isempty(sites.geom)
