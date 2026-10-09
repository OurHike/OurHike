"""Nebraska Game and Parks Commission: warnings, held (decision 122; see closures.py beside this file).

The five hunting-unit layers the coverage audit named (2026-10-01), each the units for one species, statewide,
with no season dates:

- `ngpc_deer_management_units`: `Deer_Mangement_Units_2022/FeatureServer/0`, 18 units.
- `ngpc_elk_hunting_units`: `Elk_Hunting_Units_2022/FeatureServer/0`, 16 units.
- `ngpc_antelope_hunting_units`: `Antelope_Hunting_Units_2022/FeatureServer/0`, 21 units.
- `ngpc_mountain_lion_hunting_units`: `MT_Lion_Hunting_Units_2022/FeatureServer/0`, 3 units.
- `ngpc_bighorn_sheep_hunting_units`: `Bighorn_Hunting_Units_2022/FeatureServer/0`, 1 unit.

The services carry 2022 in their names, but deer and elk were edited in 2026 (editingInfo, read 2026-10-09). The
commission's organisation also holds 'Additional_Antlerless_Deer_2025', 'AOSC_Deer_Units',
'Additional_AOSC_Deer_Units' and 'Antelope_North_Sioux_Late' (its services list, 2026-10-09), which nobody has
read; they wait for the rest of the commission's layers.

On the hourly lane's notices job, as every closures and warnings source is (decision 61): a monthly notice source
would land where no build that reads it looks (review finding ARC-1, tests/test_generated_notice_models.py). Each
check is one conditional GET a run while nothing moves.
"""

from extract._kinds import arcgis_layer

TYPE = "warnings"
CLAIMS = (
    "ngpc_deer_management_units",
    "ngpc_elk_hunting_units",
    "ngpc_antelope_hunting_units",
    "ngpc_mountain_lion_hunting_units",
    "ngpc_bighorn_sheep_hunting_units",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
