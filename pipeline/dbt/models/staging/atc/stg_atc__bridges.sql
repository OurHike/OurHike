-- Staged but NOT unioned into dim_pois: whether a bridge is a hiker-facing
-- POI type is a product call (#99), recorded as deliberately-unmapped in
-- the poi_type_mapping seed - the same greppable posture as opentrail's
-- 'c' and 't' codes - rather than decided in passing by a staging model.
with source as (
    select * from {{ source('atc', 'raw_atc__bridges') }}
)

select
    cast(globalid as varchar) as source_id,
    name,
    status,
    type as bridge_type,
    super_stru as superstructure,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
