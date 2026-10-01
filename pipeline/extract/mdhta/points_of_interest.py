"""Maah Daah Hey Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c8_regional_5).

Machine-parseable HTML. The waterboxes are water caches, and USFS rec sites publish no water at all
(`usfs_rec_sites` notes). That makes them this batch's clearest safety gap.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/trail-guide/` carries 50 located points as HTML `data-lat`/`data-long` attributes: 19 trailheads, 11"
        " campgrounds, 8 waterboxes (Plumely Draw, Long X, Magpie Road, Third Creek, Tom's Wash, Bear Creek, "
        "Roosevelt, Beicegel Creek Road), 6 river crossings and 6 points of interest. Each also has its own "
        'page, e.g. `/waterboxes/bear-creek/`, "GPS coordinates 46.72897, -103.52134". FAQ: "Each campground on'
        ' the trail has hand pumped potable water … Pump handles are removed about November 10 through April."',
    ),
    where=("https://mdhta.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
