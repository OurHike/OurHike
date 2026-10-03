"""Tennessee Eastman Hiking & Canoeing Club: points of interest, published, and not landed (coverage
audit 2026-10-01, batch c3_at_clubs_south).

Steward-grade capacity and water prose, but stale. Shelter state is wrong in both directions: see
Overmountain (Defects 1), and Laurel Fork is closed per ATC while its wiki page says nothing.
(skeptic) `Shelter:Cherry Gap` (last revision 2014-09-26) still describes a standing shelter,
capacity 6 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "LOADED via `atc` (code 26): shelters 15, campsites 8, privies 1, parking 25, viewpoints 104, bridges "
        "38. Not loaded: 17 `Shelter:` pages, 16 of which carry `Template:Infobox Shelter` (Capacity, Privy, "
        "DistanceN, DistanceS, Elevation, Latitude, Longitude, nearest Medical) and a `== Water ==` prose "
        'section. Example: Laurel Fork, "A cascading stream is located 150 feet on blue-blazed trail behind the'
        ' shelter". Infobox revisions are old (Laurel Fork 2014-09-26, Roan High Knob 2018-12-21). '
        "`Template:Waterfall` appears on 3 pages.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://tehcc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
