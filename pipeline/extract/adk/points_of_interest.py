"""Adirondack Mountain Club: points of interest, drawn from another folder's resource (coverage audit
2026-10-01, batch c4_regional_1).

ADK's lodging is gated by its terms.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Via DEC: `dec_lean_tos`, `dec_primitive_campsites`, `dec_firetowers`, `dec_parking_areas`, "
        "`dec_scenic_vistas`. ADK's own lodging is AVAILABLE but not loaded: the WP `lodging` type has "
        "`x-wp-total: 11` (Johns Brook Lodge, Grace Camp, JBL lean-tos, Heart Lake cabins).",
    ),
    where=(
        "https://gisservices.dec.ny.gov/arcgis/rest/services",
        "https://adk.org/",
    ),
    reason="drawn from nysdec/'s resources, extracted once there (decision 34); checked names the layer this org's "
    "data arrives in",
)
