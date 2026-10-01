"""DEC Lands: published on DEC's own server and listed in the clearinghouse, and not landed yet."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "dil/dil_land_activities/MapServer/0, 'DEC Lands': 3,234 polygons, all PUBLICUSE='Y', max(UPDATED) "
        "2026-09-14, with CATEGORY, CLASS, UNIT, FACILITY, UMP, URL and ACRES (re-read 2026-10-01)",
        "the same service's layer 1 (93 conservation easements) and layer 2 (132 Wildlife Management Areas)",
        "dil/dil_reference/MapServer/8 and /9: the Adirondack and Catskill Park boundaries, one polygon each",
    ),
    where=(
        "https://gisservices.dec.ny.gov/arcgis/rest/services/dil/dil_land_activities/MapServer/0",
        "https://gisservices.dec.ny.gov/arcgis/rest/services/dil/dil_reference/MapServer",
    ),
    reason="published, and not landed: the layer has no sources.json row, which a builder needs",
)
