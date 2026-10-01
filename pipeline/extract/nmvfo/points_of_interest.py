"""New Mexico Volunteers for the Outdoors: points of interest, drawn from another folder's resource
(coverage audit 2026-10-01, batch p05_persist).

USFS: public domain. Folder `usfs/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Loaded `EDW_RecInfraRecreationSites_02`:",
        "Cibola (0303): TRAILHEAD 67, CAMPGROUND 28, PICNIC SITE 26.",
        "Santa Fe (0310): TRAILHEAD 37, CAMPGROUND 21.",
        "Lincoln (0308): TRAILHEAD 18, CAMPGROUND 16, OBSERVATION SITE 9.; NMVFO's own: "
        "`wp/v2/media?media_type=application` reports X-WP-Total 79, of which 62 are readable over 2 pages: 59 "
        "PDF, 3 docx, and 0 GPX/KML/KMZ/GeoJSON. One is a 2018 project map PDF (Piedra Lisa). `tribe_venue` has"
        " 8 rows: Los Luceros Historic Site, Tijeras BioZone Education Center, REI Albuquerque, Sevilleta NWR, "
        "Canteen Brewhouse, Heron Lake State Park, Agua Piedra …",
    ),
    where=(
        "https://coageo.cabq.gov/cabqgeo/rest/services",
        "https://nmvfo.org/",
    ),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
