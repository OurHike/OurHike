"""Washington RCO — State Trails Database: photos, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Licence unstated, and the host `mapswa.com` is not RCO's domain, so who holds the rights is
@unvalidated. `may_publish` stays false until the maintainer rules on unstated-licence photos. Low
value either way: campground photos from a SCORP recreation inventory (the year was not checked).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Camping_scorp_view/0` has 152 `PhotoWeb` URLs on `mapswa.com`, with no licence stated.",
        "Skeptic re-counted: 152 rows with `PhotoWeb LIKE 'http%'` (974 are non-null, but most hold a single "
        "space), e.g. `https://mapswa.com/photos/1000352.jpg`. The item's `licenseInfo` is blank.",
    ),
    where=("https://mapswa.com/photos/1000352.jpg",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
