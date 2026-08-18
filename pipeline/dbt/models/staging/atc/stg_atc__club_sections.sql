-- Which club maintains which stretch. Upstream spells the acronym column
-- ACROYNM; correcting a spelling at the rename is exactly what staging is
-- for. export_club_sections.py owns the published artifact.
with source as (
    select * from {{ source('atc', 'raw_atc__trail_club_sections') }}
)

select
    cast(globalid as varchar) as source_id,
    trail_club,
    acroynm as club_acronym,
    region,
    _loaded_at as loaded_at
from source
