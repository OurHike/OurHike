"""Appalachian Mountain Club (A.T. sections): trail lines, drawn from another folder's resource
(coverage audit 2026-10-01, batch c1_at_clubs_north).

The A.T. layers in AMC's account are a copy of ATC's, not AMC's own. Nobody has checked where "New
Hampshire Trails" and "Maine Trails" come from (@unvalidated; likely state copies). No White
Mountain trail inventory was found, so `amc`'s hold reason still stands.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`centerline`; club polygon "Appalachian Mountain Club". AMC\'s ArcGIS account a personal ArcGIS account'
        ' (accepted owner) holds "Appalachian Trail from ATC", whose own snippet says "data obtained from the '
        'Appalachian Trail Conservancy … 4,809 segments". It also holds "New Hampshire Trails" and "Maine '
        'Trails" feature services with no stated provenance, plus Highlands and PA Highlands layers.',
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://services9.arcgis.com/mxpFc8oFRyNIV03y/arcgis/rest/services",
        "https://outdoors.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
