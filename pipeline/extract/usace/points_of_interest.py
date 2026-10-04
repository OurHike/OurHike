"""US Army Corps of Engineers: points of interest, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest; re-read for decision 54's wave 3 on 2026-10-04).

Two routes, neither wired here. RIDB's API, the Corps' share of Recreation.gov's facilities and
campsites, is refused by ridb.recreation.gov's robots.txt for every agent, ours included, before any
key would matter. RIDB's bulk export is allowed and answers, but it is Recreation.gov's national
download for twelve agencies (pipeline/SOURCE_SURVEY.md), not a Corps publication, so it would be a provider row of its own and
is the lead's to route. The Tulsa District points (trailheads, campgrounds, campsites, recreation
features) are ArcGIS layers on the service usace_tulsa_trails already reads for lines: wave 1's kind.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "ridb.recreation.gov/robots.txt, read 2026-10-04T11:41:47Z under lib/user_agent.py's agent: `User-agent: *` / `Disallow: /api` / `Disallow: /api/*` / `Crawl-delay: 10`; `/api/v1/facilities` and `/api/v1/campsites` fall under it, so neither was requested.",
        'https://ridb.recreation.gov/downloads/RIDBFullExport_V1_CSV.zip, one HEAD on 2026-10-04 (robots allows /downloads/): 200, application/zip, 247,747,658 bytes, ETag "a13b32915810006a08fe5da8f88716a8", Last-Modified Sat, 03 Oct 2026 18:47:00 GMT. Not downloaded, so the Corps\' share of it is unmeasured.',
        "Tulsa District recreation features (the coverage audit, 2026-10-01): Trailheads 100, Campgrounds 133, Campsites 6,013, Recreation Features 1,927, on services8.arcgis.com/GvI5dZtQIoT0Fznq's District_Recreation_Features_SWT FeatureServer, whose layer 13 usace_tulsa_trails registers.",
    ),
    where=(
        "https://ridb.recreation.gov/robots.txt",
        "https://ridb.recreation.gov/downloads/RIDBFullExport_V1_CSV.zip",
        "https://usace.army.mil/",
    ),
    terms="ridb.recreation.gov/robots.txt (read 2026-10-04): `User-agent: *` / `Disallow: /api`",
    reason="refused for the API by robots.txt; the bulk export is Recreation.gov's, not the Corps', and the Tulsa points are ArcGIS layers: both routed by the lead",
)
