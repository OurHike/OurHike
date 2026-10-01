"""AMC Connecticut Chapter: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c1_at_clubs_north).

"Some campsite water sources may dry up at certain times of year"
(`/trails/trails-hiking-on-the-at/`). It says which sources, not when.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://ct-amc.org/trails/trails-camping/` (WP page, modified 2022-04-04): a 12-site table, south to "
        "north, giving sleeping area, water source (brook/spring), bathroom (privy/chum) and bear box. "
        "Northwest Camp (chapter cabin, `/nwcamp/`). LOADED via atc (code 6): shelters 7, campsites 16, privies"
        " 19, parking 15, viewpoints 43, bridges 8.",
    ),
    where=(
        "https://ct-amc.org/trails/trails-camping/",
        "https://ct-amc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
