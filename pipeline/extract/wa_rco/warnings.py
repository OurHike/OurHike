"""Washington RCO — State Trails Database: warnings, drawn from another folder's resource (decision 53
phase B, 2026-10-03).

This club's warnings arrive through _shared/wa_dnr/ `wa_dnr_wildfire_danger`, `wa_dnr_ifpl`, each
extracted once in its steward's folder (decision 34). Its portion is assigned in dbt.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://gis.dnr.wa.gov/site3/rest/services/Public_Wildfire/WADNR_PUBLIC_WD_WildfireDanger/MapServer/1,
WA DNR's Burn Bans layer, not re-read; layer 0, wired in _shared/wa_dnr/, carries BURN_BAN_LEVEL_NM
itself.

Before decision 53 phase B, 2026-10-03, this note read:

Washington RCO — State Trails Database: warnings, published, and not landed (coverage audit
2026-10-01, batch p10_persist).

WA DNR licenseInfo (on the sibling "Fire Shutdown Zones" item, the same publisher): "The Washington
State Department of Natural Resources (DNR) provides these geographic data 'as is.' DNR makes no
guarantee or warranty…": none_stated. WSPRC: "provides these geographic data 'as is'…": none_stated.
WDFW Safety Zones: empty, none_stated. People: the FDRA and IFPL layers carry regional-office phone,
address and email fields (`REGION_EMAIL_ADDR`, `RGN_EMAIL`), not copied.
`WA_Large_Fires_Current_Year`'s copyrightText names an individual's email, not copied, and the
layer's count query failed. Folders: `wa_dnr/`, `wa-state-parks/`, `wdfw/` (names Reasoned).

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via _shared/wa_dnr/ `wa_dnr_wildfire_danger`, `wa_dnr_ifpl` (decision 53 phase B, 2026-10-03): `wa_dnr_wildfire_danger` reads `Public_Wildfire/WADNR_PUBLIC_WD_WildfireDanger/MapServer/0`; `wa_dnr_ifpl` reads `Public_Wildfire/WADNR_PUBLIC_WD_IFPL/MapServer/0`",
        '`https://gis.dnr.wa.gov/site3/rest/services/Public_Wildfire/WADNR_PUBLIC_WD_WildfireDanger/MapServer`: `/0` Wildfire Danger holds 23 FDRA polygons, today Moderate 20 and Low 3. `/1` Burn Bans holds 23; `BURN_BAN_LEVEL_NM` reads "Rule Burns are banned" on 13, "Other combination described" on 8 and "No Burn Bans in effect" on 2. `…/WADNR_PUBLIC_WD_IFPL/MapServer/0` "Current Industrial Fire Precaution Levels" holds 37 zones, all at level 1, with `FIRE_PRECAUTION_EFFECTIVE_DT` up to 2026-09-30. `Public_Geology/Volcanic_Hazards/MapServer/0` holds 13 hazard polygons (standing, with `WHATTODO1..4` fields). From geo.wa.gov: WSPRC "PARKS - Winter Rec Temporary Closure" (`675652dc7a364c4686032d8d0a599c61`, 47 lines, 2025-12-03), which is a closure layer, and "WDFW Safety Zones" (`12a6b8e7e86146deac41dc15fcfd464a`, 67 polygons, 2026-06-25). WFIGS shows 24 current perimeters in a Washington bounding box today (the box also takes in parts of OR, ID and BC, so not all 24 are in the state), e.g. Little Giant 172,896 ac and Kaiser Canyon 138,293 ac. Tried: (1) WA DNR `site1/Wildfire` answers 499; `site3/Public_Wildfire` (11 services) and `site3/Wildfire` (3) list. (2) AGOL "Wildfire Danger Washington DNR" 2 (both relist the DNR service); `owner:OpenData_wadnr` wildfire 8. (3) geo.wa.gov "fire danger" 2, "closure" 14. (4) WA DNR, WSPRC, WDFW. (5) data.gov "Washington wildfire danger" 0; Socrata 0. (6) `rco.wa.gov` 0 (audit). (7) The DNR layers are live: the effective dates run to yesterday.',
    ),
    where=(
        "https://gis.dnr.wa.gov/site3/rest/services/Public_Wildfire/WADNR_PUBLIC_WD_WildfireDanger/MapServer/0",
        "https://gis.dnr.wa.gov/site3/rest/services/Public_Wildfire/WADNR_PUBLIC_WD_IFPL/MapServer/0",
        "https://gis.dnr.wa.gov/site3/rest/services/Public_Wildfire/WADNR_PUBLIC_WD_WildfireDanger/MapServer",
        "https://gis.dnr.wa.gov/site1/rest/services/Public_Geology/Volcanic_Hazards/MapServer/0",
        "https://geo.wa.gov",
        "https://data.gov",
        "https://rco.wa.gov",
        "https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services",
    ),
    reason="drawn from _shared/wa_dnr/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in",
)
