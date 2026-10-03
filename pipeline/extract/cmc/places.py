"""Carolina Mountain Club: places, drawn from another folder's resource (coverage audit 2026-10-01,
batch p01_persist).

Licence: ATC under the existing `atc` permission basis. USFS and NPS public domain. NC DPR:
"Acknowledgement of products derived from this data…" (audit b7), attribution_only. Folders: `atc/`
(loaded); `usfs/`, `nps/` and `nc-dpr/` for boundaries. A CMC trailhead directory still does not
exist.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "ATC `AT_Communities` "
        "`services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/AT_Communities/FeatureServer/0` "
        "(`sources.json` key `communities`, `reaches_hikers: true`): 59 points. North Carolina 2: Franklin "
        "(NHC's section) and Hot Springs (CMC's Davenport Gap–Spivey Gap section). An unnamed point also sits "
        "at Hot Springs (-82.872, 35.837).; Unit boundaries, available, not loaded:",
        "NC DPR `NC_State_Parks_System/0`: 346 polygons (audit b7).",
        "USFS `EDW_ForestSystemBoundaries_01` (in EDW, unregistered).",
        "NPS boundaries for GRSM and BLRI.; Tried: 1–7 above, plus a read of …",
    ),
    where=("https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/AT_Communities/FeatureServer/0",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
