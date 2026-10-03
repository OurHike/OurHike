"""Friends of the Mountains-to-Sea Trail: trail lines, drawn from another folder's resource (coverage
audit 2026-10-01, batch c7_regional_4).

The 2020 layer predates the Helene reroutes. Per #1709 — Register the steward and the redistributor
both, and declare which one wins where they overlap, the steward's own route should outrank it once
found. ArcGIS: no FMST-owned items.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "328 features, last edited 2020-10-19. The Friends' own geometry:",
        'The "MST-Hurricane Helene Recovery Status" Google My Map, as KML: '
        "`https://www.google.com/maps/d/kml?mid=1oSH-JQQpOan3r5Km7lJSVDDopenkW6k&forcekml=1`. 12 LineStrings, "
        "Segments 1–5 (the mountains).",
        'An "Interactive Google Map" at `/the-trail/map/`, whose `mid` I could not read.',
        "FarOut (paid).",
        'A state copy, "created by Friends of the MST. Used with permission." (correction 3).',
    ),
    where=(
        "https://www.google.com/maps/d/kml?mid=1oSH-JQQpOan3r5Km7lJSVDDopenkW6k&forcekml=1",
        "https://mountainstoseatrail.org/",
    ),
    reason="drawn from nc_mst/'s resources, extracted once there (decision 34); checked names the layer this org's "
    "data arrives in",
)
