"""Finger Lakes Trail Conference: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

Partly loaded already: `dec_hiking_trails` has 127 FLT-named segments and `ncta_trail` 449. NCTA's
`nctgis` item `agol_flt` (417 segments, ~382 mi, "NCT Segments of the FLT") is a subset of the NCT.
Overlap with `ncta_trail` needs a #1709 measurement.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "FLTC's own ArcGIS org (from Experience Builder app `3d03f176ff21463ea6066e2b832643b7`, which "
        '`fingerlakestrail.org/map/` embeds; web map "FLT System Master" `9794ff6ba02d4c25b809d1a73c388fc3`, '
        "public): `https://services7.arcgis.com/GwV4OWqOyYWWUpBK/arcgis/rest/services/FLTmain/FeatureServer/1`,"
        ' "FLT thru trails, loops, and spurs". 225 polylines, Σ`Len_Miles` = 1,023.6 mi, lastEdit 2026-07-20, '
        "maxRecordCount 2000. Also `NonFLTTrails_/FeatureServer/4` (215 lines).",
    ),
    where=(
        "https://services7.arcgis.com/GwV4OWqOyYWWUpBK/arcgis/rest/services/FLTmain/FeatureServer/1",
        "https://services7.arcgis.com/GwV4OWqOyYWWUpBK/arcgis/rest/services/NonFLTTrails_/FeatureServer/4",
        "https://fingerlakestrail.org/map/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
