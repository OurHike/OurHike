"""Wasatch Mountain Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
p08_persist).

Licence: UGRC is none_stated (a disclaimer); USFS is open_licence. avalanche.org is
explicit_restriction (quoted in the TYT warnings row). Folders: `_shared/utah_ugrc` (zone geometry),
`usfs/warnings.py`, and `_shared/avalanche_org` if permitted. Avalanche matters from November.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.fs.usda.gov/r04/uinta-wasatch-cache/alerts
(html_page); https://api.avalanche.org/v2/public/products/map-layer (json_api);
https://wasatchmountainclub.org/announcements (html_page).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "(a) Avalanche: UGRC `recreation_avalanche_center_forecast_zones/0` (9 polygons with `forecast_link`, "
        "b7) gives the geometry. The danger rating itself sits at "
        '`api.avalanche.org/v2/public/products/map-layer`: 9 UAC zones, "Salt Lake" among them; "no rating" '
        'today, because the season has not started. (b) Fire: the R04 orders for UWC include "Davis County Fire'
        ' Restrictions" (to 2026-10-31) and "Weber County Front Range Fire Restriction" (to 2026-11-15). '
        '"Camping Fire Restrictions Mill Creek, Little and Big Cottonwood Canyons" has been standing since '
        "1997, end date 2099-12-31. UGRC's …",
    ),
    where=(
        "https://api.avalanche.org/v2/public/products/map-layer",
        "https://avalanche.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
