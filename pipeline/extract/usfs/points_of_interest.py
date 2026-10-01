"""The Forest Service's recreation sites, `EDW_RecInfraRecreationSites_02/MapServer/0`.

31,415 points on 2026-10-01 against 31,405 on 2026-09-02 (coverage audit,
batch b6_federal). Its `seasonal_operational_status` reads CLOSED on 757
sites nationwide and nothing reads it yet: #1803 — 339 USFS campgrounds,
trailheads and viewpoints the Forest Service marks CLOSED ship as ordinary
pins, because nothing reads seasonal_operational_status. Not landed:
`EDW_RecreationOpportunities_01/MapServer/0` (14,211 points, with
`openstatus`) and `EDW_FSOfficeLocations_01/MapServer/0` (1,949 offices, which
include IT sites and need a filter before they mean "ranger station").
"""

from extract._kinds import arcgis_layer

CLAIMS = ("usfs_rec_sites",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
