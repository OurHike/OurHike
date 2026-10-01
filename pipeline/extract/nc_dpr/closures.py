"""NC Division of Parks & Recreation — NC Trails: closures, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Page, one per park (about 41 units). No feed or JSON found. Skeptic checked `/jsonapi`, `/alerts`
and `/park-alerts` (all 404) and `/rss.xml` (403). `sitemap.xml` (733 URLs) lists 31 per-park news
posts at `/state-parks/<park>/news/<slug>`, some of them closure notices (e.g. …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Per-park `role="alert"` banners on ncparks.gov (Drupal 10). Example, '
        '`https://www.ncparks.gov/state-parks/mount-mitchell-state-park`: "North of the park, the Parkway is '
        'closed."',
    ),
    where=(
        "https://www.ncparks.gov/state-parks/mount-mitchell-state-park",
        "https://ncparks.gov",
        "https://trails.nc.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
