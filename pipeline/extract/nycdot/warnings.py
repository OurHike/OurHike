"""NYC Department of Transportation: warnings, nothing published (coverage audit 2026-10-01, batch
q01_persist).

Cross-reference, not DOT's data: NWS `https://api.weather.gov/alerts?zone=NYZ072` (Manhattan) holds
a Coastal Flood Advisory and 4 Coastal Flood Statements sent 2026-09-27 and 2026-09-28. That is the
flood warning for the East River and Hudson River greenways, and it belongs in `_shared/nws/`. NYC
Parks' `DPR_ParkClosure_001.json` `Open`-type notices (`nyc_parks/`, b5) cover greenway segments
inside parks.

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Tried: (1) DOT's AGOL org: `orgid:wmZOI9vyUBq1zTZx` with "
        "detour/closure/advisory/flood/hazard/alert/condition/status/construction returns 46 items, none a "
        "warning. `Bike_Network_Bike_Lane_Condition_View` is facility-class history (b5 skeptic); "
        "`Street_Rating_View` is pavement rating; `Holiday_Embargo_*` are construction embargo blocks; "
        "`DDC_Active_Infrastructure_Projects` (2026-08-31) is a capital-project list; the bridge views carry no"
        " status field. The City's other ArcGIS roots: `gis.nyc.gov/arcgis/rest/services` and `maps.nyc.gov/…` "
        "301 to `www.nyc.gov/arcgis/rest/services`, which answers HTTP 490 (a block page; not routed around, so"
        ' UNKNOWN for that root); `nycdotgis.nyc.gov` proxy 502. (2) AGOL "NYC DOT greenway detour" 0, "NYC '
        'greenway closure" 1 (a Buffalo-region bike network). (3) NYS clearinghouse "closure" 0. (4) Not '
        "applicable (DOT is the manager). (5) Socrata, DOT attribution, re-listed: 240 datasets; hazard-shaped "
        "names are only `i6b5-j7bu`/`478a-yykk` street closures (the closures row), pothole work orders closed,"
        ' and parking-meter status. "NYC DOT advisory" 2 (LinkNYC), "greenway closure" 0, "Notify NYC" 0 '
        'matching. data.gov "NYC DOT advisory" 0. (6) DOT web pages are not GIS (b5). (7) No DOT warning feed '
        "found.",
    ),
    where=(
        "https://api.weather.gov/alerts?zone=NYZ072",
        "https://data.cityofnewyork.us/d/i6b5-j7bu",
        "https://data.cityofnewyork.us/d/478a-yykk",
        "https://gis.nyc.gov/arcgis/rest/services",
        "https://maps.nyc.gov/",
        "https://www.nyc.gov/arcgis/rest/services",
        "https://nycdotgis.nyc.gov",
        "https://data.gov",
    ),
)
