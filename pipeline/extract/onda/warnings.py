"""Oregon Natural Desert Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch p06_persist).

WFIGS licence: disclaimer only ("The National Interagency Fire Center shall not be held liable for
improper or incorrect use…"). It is a federal interagency product, so public domain (Reasoned).;
ODFW: the ORHAM MapServer copyrightText is empty (none_stated). The copyrightText on …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "NIFC WFIGS (new to the plan): "
        "`services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0`"
        " (item `d1c32af3212341869b3c810f1a215824`, owner `NIFC_Authoritative`). 127 current perimeters "
        "nationwide, 4 in an ODT box (-121.4,41.9 to -117.0,44.2) today.; ODFW: "
        "`nrimp.dfw.state.or.us/arcgis/rest/services/ORHAM/ORHAM/MapServer` has Alert Areas 289, Safety Areas "
        "(no hunting) 38 and Restricted Areas 28. WMU polygons are in `WMU_AandH_TMA_PubLand_view`. No layer "
        "carries hunting-season dates.; ONDA's own `slocum_creek(1)/FeatureServer/0` (item \"high …",
    ),
    where=(
        "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0",
        "https://nrimp.dfw.state.or.us/arcgis/rest/services/ORHAM/ORHAM/MapServer",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
