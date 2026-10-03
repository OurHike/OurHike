"""Appalachian Mountain Club (A.T. sections): warnings, published, and not landed (coverage audit
2026-10-01, batch c1_at_clubs_north).

The Pemi rule is also LOADED via atc ("New Hampshire: Bear Can Requirement in the Pemi Wilderness",
not placed on the map). The daily note was 4 months stale when read, so freshness has to be checked
per field.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same conditions page. Its daily note for the Highland Center (dated 05/30/26 when read) gave "
        'temperature, "Wet trails, watch out for river crossings" and snow and ice above 3,000 ft. The '
        "`backcountry-campsites` record states the Pemigewasset bear-canister rule effective 2026-05-01. There "
        "is also a news post `/resources/amc-outdoors/news/bear-canisters-required-pemigewasett/`.",
    ),
    where=("https://outdoors.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
