"""Georgia Appalachian Trail Club: warnings, published, and not landed (coverage audit 2026-10-01,
batch b4_oprhp_mohonk_gatc).

The canister requirement is a legal order, and a grep of `atc_updates.json` for "Jarrard" or
"canister" finds only the Pemi Wilderness one. The order is the Forest Service's
(`fs.usda.gov/…/Bear canister forest order CURRENT.pdf`), so USFS is the authoritative publisher and
GATC the republisher. …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://georgia-atclub.org/alerts/feed/` (a custom post type `alerts`, absent from "
        '`/wp-json/wp/v2/types`; 2 items). (1) "Seasonal Alert – Bear-Resistant Canisters Required: Jarrard Gap'
        ' to Neel Gap", published 2026-03-01 and modified 2026-03-06: the USFS order requires hard-sided '
        'canisters "From March 1 to June 1 each year" between "Jarrard Gap (mile 26.2) and Neel Gap (mile '
        '31.3)". (2) "2026 Thru-Hiker Planning – Hurricane Helene Updates", which points to ATC. The ATC path '
        "is LOADED: `atc_trail_updates` carries 3 Georgia bear-activity rows (Cooper Gap, Woods Hole Shelter, "
        "Swaim Gap).",
    ),
    where=(
        "https://georgia-atclub.org/alerts/feed/",
        "https://georgia-atclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
