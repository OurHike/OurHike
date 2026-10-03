"""Utah UGRC — SGID Trails and Pathways: closures, read from trail_lines.py's resource (decision 53
phase B, 2026-10-03).

TrailsAndPathways/FeatureServer/0 is the registered utah_sgid_trails layer, which
utah_sgid/trail_lines.py already extracts whole: Status reads CLOSED on 122 of 48,132 trails
(EXISTING 45,796, PROPOSED 984, UNCERTAIN 829, UNOFFICIAL 341, Active 2, null 58), newest CLOSED
edit 2026-08-25 21:26 UTC (inventory batch 2, 2026-10-03). The closures are an attribute of that one
table, mapped in staging (Status = 'CLOSED'); a second read would be a copy. So they ride the
monthly lane with their table. The item now states CC BY 4.0 where utah_sgid_trails' row says public
domain by assume-open, which is worth reconciling.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/recreation_avalanche_center_forecast_zones/FeatureServer/0,
9 static zones linking to the Utah Avalanche Center's forecasts; the forecasts are UAC's, a _shared/
question;
https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/Utah_Fire_Restriction_Areas_Lookup/FeatureServer/0,
a 19-row lookup table last edited 2020-09-28, not restrictions; FFSL's live layer is
_shared/utah_ffsl/.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Utah UGRC — SGID Trails and Pathways: closures, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Map it in staging. No separate feed exists.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): An attribute in the loaded layer: `Status = CLOSED` on 122
segments. Nothing reads it (section B).

Its `where`: https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "trail_lines"
