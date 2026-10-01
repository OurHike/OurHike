"""NC Mountains-to-Sea Trail (state-published layer): closures, published, and not landed (coverage
audit 2026-10-01, batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Format page. Park pages carry an alert block (`block-nc-alert-block` in the HTML of "
        "`/state-parks/crowders-mountain-state-park/trails`). The sitemap (733 URLs) has closure news pages, "
        "e.g. `/state-parks/dismal-swamp-state-park/news/closure-bridge-repairs`. `rss.xml` returns 403.",
    ),
    where=("https://trails.nc.gov/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
