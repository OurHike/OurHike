"""Oregon Natural Desert Association: warnings, drawn from another folder's resource (decision 53 phase
B, 2026-10-03).

This club's warnings arrive through _shared/nifc/ `nifc_wfigs_current_perimeters`; _shared/odfw/
`odfw_orham_alert_areas`, each extracted once in its steward's folder (decision 34). Its portion is
assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://onda.org/ (html_page).

Before decision 53 phase B, 2026-10-03, this note read:

Oregon Natural Desert Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch p06_persist).

WFIGS licence: disclaimer only ("The National Interagency Fire Center shall not be held liable for
improper or incorrect use…"). It is a federal interagency product, so public domain (Reasoned).;
ODFW: the ORHAM MapServer copyrightText is empty (none_stated). The copyrightText on …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via _shared/nifc/ `nifc_wfigs_current_perimeters`; _shared/odfw/ `odfw_orham_alert_areas` (decision 53 phase B, 2026-10-03): `nifc_wfigs_current_perimeters` reads `WFIGS_Interagency_Perimeters_Current/FeatureServer/0`; `odfw_orham_alert_areas` reads `ORHAM/ORHAM/MapServer/6`",
        "NIFC WFIGS (new to the plan): `services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0` (item `d1c32af3212341869b3c810f1a215824`, owner `NIFC_Authoritative`). 127 current perimeters nationwide, 4 in an ODT box (-121.4,41.9 to -117.0,44.2) today.; ODFW: `nrimp.dfw.state.or.us/arcgis/rest/services/ORHAM/ORHAM/MapServer` has Alert Areas 289, Safety Areas (no hunting) 38 and Restricted Areas 28. WMU polygons are in `WMU_AandH_TMA_PubLand_view`. No layer carries hunting-season dates.; ONDA's own `slocum_creek(1)/FeatureServer/0` (item \"high …",
    ),
    where=(
        "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0",
        "https://nrimp.dfw.state.or.us/arcgis/rest/services/ORHAM/ORHAM/MapServer/6",
        "https://nrimp.dfw.state.or.us/arcgis/rest/services/ORHAM/ORHAM/MapServer",
    ),
    reason="drawn from _shared/nifc/'s and _shared/odfw/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
