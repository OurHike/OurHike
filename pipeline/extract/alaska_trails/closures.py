"""Alaska Trails: closures, published, and not landed (coverage audit 2026-10-01, batch p08_persist).

Licence: NPS and USFS are open_licence, federal. DPOR `copyrightText` reads "Alaska Department of
Natural Resources, Division of Parks & Outdoor Recreation". Class: attribution_only (a credit line;
no terms read). The ASP condition reports are PDFs on a web page, not GIS, so 21(a) does not reach
them; I did not read DNR's site terms. Its robots.txt allows `/parks` and disallows `/parks/guides/`
and query strings. Folders: `nps/closures.py`, `usfs/closures.py`, and a new `alaska-state-parks`
row for ASP. Do not read: `AKLT_Trail_Segments_(Internal)_view` answers 200 anonymously, but its
name says internal. I did not open it; ask Alaska Trails first.

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Managers, from `AKLT_Trail_Segments_Public.Segment_Management` (286 segments): AK DOT 60, Alaska State"
        " Parks 49, USFS 30, Anchorage Parks 23, Mat-Su 18, FNSB 15, NPS 8. (a) NPS alerts API, "
        '`parkCode=dena,kefj`: 5 alerts. DENA: "Teklanika Area Closures" (Park Closure, 2026-09-24) and "Road '
        'Open To: Mile 30 (Teklanika River)". KEFJ: "Hazardous Conditions at Terminus Of Aialik Glacier" '
        '(Danger, 2026-09-14), "Canyon from Toe of Exit Glacier to the Outwash Plain" (Danger) and "Use Caution'
        ' in and around Pedersen Lagoon" (Caution). (b) Chugach NF, `fs.usda.gov/r10/chugach/alerts`: 11 dated '
        'alerts, including "Wildfire reported in the area of mile marker 74 of Seward Highway" (caution, '
        '2026-09-14) and "Russian River Occupancy and Use Restrictions" (2026-06-01). b6 found the R10 polygon '
        "layer `CNF_ClosureAreaPolygons` stale. (c) Alaska State Parks: "
        '`dnr.alaska.gov/parks/asp/curevnts.htm`, "Park Condition Reports", "Last Update: September 30, 2026". '
        "It links per-park PDFs: `denalireport.pdf` (Sept 30), `cainesheadreport.pdf` (Sept 23), "
        '`hatcherreport.pdf` (Sept 24), `chugachreport.pdf` (April 22), plus `/parks/asp/open.htm` "Park Open '
        "Status\". DNR's ArcGIS `arcgis.dnr.alaska.gov/arcgis/rest/services/DPOR` holds `HP_MotorizedClosures` "
        "(Hatcher Pass zones closed to motorized use, not hiking closures) and `Park_Boundary_Facility` "
        "(facilities, trails, boundary, roads). The `OpenData` folder reset the connection. (d) Alaska Trails' "
        "own 36 services: no closure layer. `Segment_Condition` is work status (Construction 2, Reconstruct 2, "
        "Reroute 4), not closure. Tried: 1 (the Alaska Trails org; the DNR root, 15 folders). 2 (AGOL closure ×"
        " Anchorage, Chugach State Park, Kenai, Mat-Su: the CNF polygons and ADF&G areas, no municipal "
        "closures). 3 (Alaska open data via Hub: 12 hits, none closures). 4 (NPS, USFS, ASP). 5 (data.gov 0, "
        "Socrata 0). 7 (pages and API).",
    ),
    where=(
        "https://fs.usda.gov/r10/chugach/alerts",
        "https://dnr.alaska.gov/parks/asp/curevnts.htm",
        "https://arcgis.dnr.alaska.gov/arcgis/rest/services/DPOR",
        "https://data.gov",
        "https://alaska-trails.org/",
        "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
