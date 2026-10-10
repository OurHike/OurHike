"""MA DCR's Blue Hills Reservation parking and numbered trail intersections.

Read live 2026-10-03 for decision 54's wave 1, from DCR's own ArcGIS Online org; blue_hills/ draws from them.
NOT READ: DCR_Roads_and_Trails_Pts (20,786 points on the coverage audit's read, Shelter 59 and Road Ford 348
among them, from field work 'during the years 2005 to 2013' by its own description) on
arcgisserver.digital.mass.gov, whose robots.txt answered 502 twice on 2026-10-03. RFC 9309 reads a server
error as full disallow for now, so nothing on that host was fetched; the next run of this survey retries it.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "ma_dcr_blue_hills_parking",
    "ma_dcr_blue_hills_intersections",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
