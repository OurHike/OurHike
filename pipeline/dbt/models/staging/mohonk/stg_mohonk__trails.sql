-- Mohonk Preserve's trails and carriage roads, attributes only - same scope
-- line as stg_nynjtc__long_path, and no id column for the same reason (no
-- `id_field` recorded, and OGC_FID is GDAL's row number rather than
-- Mohonk's identity).
--
-- 304 polyline segments, measured live 2026-08-25 via returnCountOnly. The
-- measured field list is Name/General_Classification/Classification/Use_/
-- Blaze/Mileage/Surface/Owner/Manager, whole.
--
-- `blaze` HERE IS A GENUINE CODED FIELD, unlike the Long Path's plain string
-- and unlike the Highlands Trail's absent one - three organizations, three
-- different answers to the same question, which is the variety Phase D was
-- meant to surface. Still no accepted_values test: the values actually
-- present on the fetched 304 rows (not the domain's declared possibilities)
-- are N/A 124, Blue 61, Red 49, Other 33, Yellow 30, plus 7 rows with no
-- Blaze value at all. The literal string 'N/A' on 41% of rows is exactly the
-- dirt an accepted_values test would either bless or break on.
--
-- WHAT THIS LAYER IS NOT: it is already a filtered VIEW. Its own
-- definitionQuery keeps only General_Classification 'Carriage Road' or
-- 'Trail' AND Manager 'Mohonk Preserve', so this is Mohonk's curated public
-- extract rather than their internal dataset. `owner` and `manager` are
-- staged because they differ - 298 of 304 rows read Owner 'Mohonk Preserve'
-- and 6 read 'NYS OPRHP/PIPC' with Manager still Mohonk.
with source as (
    select * from {{ source('mohonk', 'raw_mohonk__mohonk_trails') }}
)

select
    name,
    general_classification,
    classification,
    use_ as permitted_use,
    blaze,
    mileage,
    surface,
    owner,
    manager,
    _loaded_at as loaded_at
from source
