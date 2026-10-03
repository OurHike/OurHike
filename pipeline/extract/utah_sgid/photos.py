"""Utah UGRC — SGID Trails and Pathways: photos, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

The photos are Utah State Parks' website thumbnails, not UGRC's, and a staging host can vanish
without notice. Owner of the rights: Utah State Parks (Reasoned from the host). `may_publish` false
until settled. Worth little.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`state_park_points_for_website.thumbnail_url` points at `stateparks.utah.gov/wp-content/uploads/…`, "
        "website images with no licence stated.",
        "Skeptic re-checked: 54 of 54 rows carry a URL. The one sampled is a 300×169 `.webp` on "
        "`stateparks.stage.utah.gov`, a staging host. Also present: `Utah_Alluvial_Fans_Field_Photos`, which "
        "are geology field photos, not hiker features.",
    ),
    where=(
        "https://stateparks.utah.gov/wp-content/uploads/",
        "https://stateparks.stage.utah.gov",
        "https://gis.utah.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
