"""Mountains to Sound Greenway Trust: points of interest, published, and not landed (coverage audit
2026-10-01, batch c6_regional_3).

Machine-readable. The categories overlap. Trailheads and campgrounds belong in POIs, and the rest in
places, split in dbt.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "WordPress REST "
        "`https://mtsgreenway.org/wp-json/wp/v2/cm-map-location?per_page=100&_fields=id,title,location,popup,cat,icon&_latlng=acf_loc_address`,"
        " which is the call the site's own map makes. `X-WP-Total` = 185, and 182 carry `location.lat`/`lng`. "
        'Categories: trails 88 (25 named "…Trailhead"), campgrounds 28, picnic or day-use areas 41, wildlife '
        "viewing 12.",
    ),
    where=(
        "https://mtsgreenway.org/wp-json/wp/v2/cm-map-location?per_page=100&_fields=id,title,location,popup,cat,icon&_latlng=acf_loc_address",
        "https://mtsgreenway.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
