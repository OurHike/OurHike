"""Benton MacKaye Trail Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Staleness risk: April restrictions are still listed in a September file, with no per-item end dates.
Whether they still hold is unverified, so these must not be shown as current without a USFS
cross-check. Skeptic, a second channel that contradicts the first: every `bmta.org` page carries a …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same PDF has 5 notices: fireworks always prohibited; Chattahoochee Stage II fire restriction "
        '"lifted 5/4/2026"; Cherokee NF Stage 1 fire restrictions "beginning April 24, 2026"; Nantahala '
        'campfire ban "April 15, 2026"; GSMNP parkwide fire ban cancelled. Also '
        "`bmtamail.org/docs/BeBearPreparedontheBMT.pdf` (static).",
    ),
    where=(
        "https://bmtamail.org/docs/BeBearPreparedontheBMT.pdf",
        "https://bmta.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
