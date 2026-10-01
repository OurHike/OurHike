"""Continental Divide Trail Coalition: warnings, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

A National Defense Area is military ground along the New Mexico border, and entering it is a federal
offence. The CDT's southern terminus is on that border. Whether this polygon touches the trail or
the Crazy Cook approach was not measured. It belongs in `cdtc/warnings.py` (or closures, if it …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same layers, rows with `Type=Alert` and `Active=Yes`. Example: "Black Fire… Stay alert for '
        "potentially dangerous conditions and slow travel due to standing dead trees, blowdown, and eroded "
        'trail." Also the static page `cdtcoalition.org/bears-and-the-cdt/`.',
        'Skeptic adds: `National_Defense_Area_NM/FeatureServer/0`: 1 polygon named "National Defense Area", '
        "last edit 2026-03-24, about 449 km² by `Shape__Area` (Measured). It is not one of the 149 + 76 alert "
        "features: a `LIKE '%efense%'` query on Alert Points returned 0 (Measured).",
    ),
    where=(
        "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/National_Defense_Area_NM/FeatureServer/0",
        "https://cdtcoalition.org/bears-and-the-cdt/",
        "https://services.wygisc.org/HostGIS/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
