"""Tennessee Eastman Hiking & Canoeing Club: elevation, published as stated gains on wiki pages, not landed.

The club's trail pages carry `High Point`, `Low Point`, `Elevation Gain`,
`Elevation Loss` and `Elevation Change Direction` in a wiki template (coverage
audit 2026-10-01, batch c3_at_clubs_south). Web pages are decision 54's wave
5, a parser per site. One figure is already hand-copied as a comparison in
`reference/published_gain.json`; it is a steward-stated gain, a check on a
computed climb, not a DEM. Not re-read for decision 54.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Template:Trail` on 148 pages carries `High Point`, `Low Point`, `Elevation Gain`, `Elevation Loss` "
        'and `Elevation Change Direction`. Example: "Carver\'s Gap to US19E", 2,054 ft gain and 4,703 ft loss, '
        "South-to-North. 10 A.T. section pages use `Template:AT Segments`. GeoJSON Z is 0.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://tehcc.org/",
    ),
    reason="web pages, not landed: decision 54's wave 5 needs a parser for the site",
)
