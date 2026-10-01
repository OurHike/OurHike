"""Potomac Appalachian Trail Club: elevation, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

Recommend not loading (Reasoned). USGS 3DEP is the elevation source, and contours would add bytes
without adding information. The contours' own source is not stated (Unvalidated).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Contours_5ft_2ft_AT/0`: 13,762 two-foot contour polylines (layer 1 holds the five-foot set), "
        "2022-05-09. The hikethetuscarora.org section guides give max/min elevation per section (page)",
    ),
    where=("https://hikethetuscarora.org",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
