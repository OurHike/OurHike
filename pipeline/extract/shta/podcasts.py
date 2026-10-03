"""Superior Hiking Trail Association: podcasts, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

RSS. The SHTA's own. Skeptic: confirmed. `<itunes:author>` is "Superior Hiking Trail Association,
WTIP", and the description reads "a special-edition podcast created by WTIP and the Superior Hiking
Trail Association". The first `<item>`'s pubDate is 2026-08-14. (M)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Blazing Trail: 40 Years on the Superior Hiking Trail" (SHTA with WTIP), linked from '
        "`/40th-anniversary/`. RSS `https://feeds.transistor.fm/blazing-trails`, 12 episodes, latest "
        "2026-08-11.",
    ),
    where=("https://feeds.transistor.fm/blazing-trails",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
