"""Arizona Trail Association: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

USFS EDW holds about 276 mi under AZT-like names ("ARIZONA" 142.8, "ARIZONA TRAIL" 99.4, "ARIZONA
TRAIL CANELO HILLS" 30.2). That those are the AZT is Reasoned, not checked. A hiker today gets the
connectors and not the trail they connect to. Skeptic: spot-checked `/3` = 44 (hasZ, last edit …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The trail itself is not loaded. `azgeo_arizona_trail` is "
        "`…/Arizona_National_Scenic_Trail_Feature_Layers_view/FeatureServer/5` = Arizona Trail Association "
        'Connector Trails (145 features, 228.9 mi; names like "Phantom Ranch Alternate Trail"). The AZT is '
        "layer `/3`, Arizona National Scenic Trail Polyline: 44 passages, 831.6 mi, `hasZ: true`, last edit "
        "2026-09-04, on `services3.arcgis.com/IKBBLZOXy58PXgpl` (ATA's own org). Also `/4` mountain-bike "
        "passages (50) and per-passage GPX, e.g. "
        "`https://aztrailmedia.s3.us-west-1.amazonaws.com/wp-content/uploads/2025/03/pass-01.gpx` (plus "
        "`-gps-1.gpx` …",
    ),
    where=(
        "https://aztrailmedia.s3.us-west-1.amazonaws.com/wp-content/uploads/2025/03/pass-01.gpx",
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
