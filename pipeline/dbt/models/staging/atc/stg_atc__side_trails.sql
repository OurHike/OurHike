-- The blue blazes' attribute record. export_spurs.py owns the published
-- artifact; this is where the raw Blaze vocabulary is staged for
-- features/TRAIL_BLAZE_COLORS.md's normalisation to build on - including
-- the real dirt that document names (24 features with no value, literal
-- "Unknown", "Gold"), which is exactly why the column carries no
-- accepted_values test yet: the domain is the finding, not a constraint.
with source as (
    select * from {{ source('atc', 'raw_atc__side_trails') }}
)

select
    cast(globalid as varchar) as source_id,
    name,
    status,
    type as trail_type,
    blaze,
    length_ft,
    _loaded_at as loaded_at
from source
