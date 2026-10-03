"""NH GRANIT (University of New Hampshire): warnings, nothing published (coverage audit 2026-10-01,
batch p07_persist).

The NH Fish and Game layers' licence reads "Please refer to the current New Hampshire Hunting
Digest. Digital data represent the efforts of the NH Fish and Game Department… Not intended for
legal use." That is a disclaimer, so none_stated. They belong in a new NH Fish and Game folder, and
they …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Same scan. GRANIT hosts no hunting-season, fire-danger or wildlife-activity layer. Its flood layers "
        "(`Topical/CV_InlandWaterResources` Flood Hazard Areas, `CV_SLR_classes`) are regulatory flood zones "
        "and sea-level scenarios, not trail warnings. Not GRANIT's, found on the way: NH Fish and Game's own "
        "AGOL org (`services8.arcgis.com/hg1B9Egwk1I5p300`):",
        "`WMU/FeatureServer`: 24 units plus 7 deer, moose, turkey and bear sublayers, edited 2026-08-26, "
        'copyright "NH Fish and Game Department, Dec. 18, 2025".',
        "`Rifles_Prohibited_Deer_Hunting/0`: 56 polygons.",
        "`WaterfowlClosedAreas/0`: 26 …",
    ),
    where=("https://services8.arcgis.com/hg1B9Egwk1I5p300/arcgis/rest/services",),
)
