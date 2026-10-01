"""Washington Trails Association: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c7_regional_4).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "22,454 features. WTA publishes no geometry of its own. The Mount Si page offers a map image "
        "(`/go-hiking/map-images/wta-mount-si-map/view`) and links to buy Green Trails maps.",
    ),
    where=("https://wta.org/",),
    reason="drawn from wa_rco/'s resources, extracted once there (decision 34); checked names the layer this org's "
    "data arrives in",
)
