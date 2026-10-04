"""Iditarod Historic Trail Alliance: podcasts, none of its own: the oral histories are UAF's (decision 54 wave
5, section K, 2026-10-04).

The site's 'Project Jukebox Oral History' menu item links the University of Alaska Fairbanks's Project Jukebox,
whose audio is UAF's, on UAF's host; iditarod100.org publishes no feed or episode list of its own.

The note this replaces read, whole:

Iditarod Historic Trail Alliance: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Not opened. Licence unknown

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Nav item "Project Jukebox Oral History" (UAF Project Jukebox
audio, third-party host)

Its `where`: https://gis.blm.gov/arcgis/rest/services
https://services2.arcgis.com/Ce3DhLRthdwbHlfF/arcgis/rest/services https://iditarod100.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.iditarod100.org/passport-stamp-program.html (HTTP 200, 2026-10-04): the menu's 'Project Jukebox Oral History' item",
        "(the coverage audit, 2026-10-01) Project Jukebox, UAF's, a third-party host",
    ),
    where=("https://www.iditarod100.org/",),
    reason="not this club's: the oral histories are UAF's Project Jukebox, on its host",
)
