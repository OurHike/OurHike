"""Central Iowa Trail Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

Under poll 7, a muddy-but-open area is a warning, not a closure. (Skeptic: the JSON API adds two
warning fields the index page hides. Free-text `comments` holds hazards such as "Tree down on trail
3", and `trail.alertNote` / `hasAlertNote` is a per-area "Trail Alert" banner, null on EWG today. …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same status page gives a condition (Muddy / Tacky / Wet / Normal) for open areas. `/winter-trail-use` (page).",
    ),
    where=(
        "https://services.arcgis.com/HT7H9QGiZQoRJDpJ/arcgis/rest/services",
        "https://bikecita.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
