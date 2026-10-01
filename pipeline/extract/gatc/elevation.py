"""Georgia Appalachian Trail Club: elevation, published, and not landed (coverage audit 2026-10-01,
batch b4_oprhp_mohonk_gatc).

Drawn profiles, not a DEM. They are useful only as a cross-check of published gain
(`reference/published_gain.json`'s kind of evidence). USGS 3DEP (`_shared/`) stays the source.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/for-hikers/maps/` links `wp-content/uploads/2024/11/GA-Profiles.pdf` (1,192,487 bytes, "
        "`Last-Modified` 2024-11-21) and `GA-AT-Brochure-Map-Profile-2024.pdf` (3,702,105 bytes, same date).",
    ),
    where=("https://georgia-atclub.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
