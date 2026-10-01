"""Connecticut Forest & Park Association: elevation, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

Skeptic: re-checked with a word-bounded `grep -rnw` for `Gains` and `Losses` over `pipeline/` (.py,
.sql, .json, excluding `data/`). The only hit is `reference/trail_orgs.json`'s own description, so
nothing reads the columns. A case-insensitive substring grep for "gains" would also have matched …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The CT DEEP layer that is already fetched has `Gains` and `Losses` columns. A grep of `pipeline/.py` "
        'and `pipeline/lib/.py` for "Gains" finds nothing, so nothing reads them. CFPA\'s own layers have `hasZ:'
        " false`.",
    ),
    where=(
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services",
        "https://ctwoodlands.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
