"""Potomac Appalachian Trail Club: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

I gave this row AVAILABLE rather than LOADED because about 950 of PATC's roughly 1,190 managed miles
(Tuscarora plus other trails) do not arrive through ATC (Reasoned from the club's stated mileage).
The layer's 381.6 A.T. miles exceed PATC's 240 because the `Maintainer` field also names NBATC …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "A.T. portion LOADED via atc. Own layer: "
        "`https://services7.arcgis.com/BbnVmymrKxjFL0SO/arcgis/rest/services/PATC_Trails_Master_view/FeatureServer/10`,"
        " 2,101 segments, 664 `TrailName` values, `SegmentLengthMiles` sum 2,198.3, `dataLastEditDate` "
        "2026-10-01, capabilities `Query`. Fields: TrailName, Maintainer, District, GuidebookSection, "
        "SurveyDate, MapMethod. Trails in it: Appalachian Trail 381.6 mi/197 seg; Tuscarora (all name variants)"
        " about 230 mi; Massanutten 408, 35.8; Catoctin 23.7; Bull Run Occoquan 15.5; 960 segs/495.1 mi have no"
        " TrailName. Older siblings: `PATC_Trails_2022/0` (2,001 …",
    ),
    where=("https://services7.arcgis.com/BbnVmymrKxjFL0SO/arcgis/rest/services/PATC_Trails_Master_view/FeatureServer/10",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
