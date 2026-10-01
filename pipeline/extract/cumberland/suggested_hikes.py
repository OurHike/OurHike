"""Cumberland Trail / Tennessee State Parks: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Section-by-section descriptions, already numbered, are the most structured hike source in the batch.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'JSON:API `https://tnstateparks.com/jsonapi/node/trails` with a title filter on "Cumberland": 26 CT '
        "trail nodes, each with `field_trail_length`, `field_trail_difficulty`, `field_trails_status`, `body`, "
        '`field_trail_geometry`. Example: "(4) Cumberland Trail - North Cumberland WMA Section - Cove Lake '
        'Section", 47.30 mi, difficult. Pages: `/parks/cumberland-trail/hiking`, '
        "`/parks/activity-detail/cumberland-trail-hiking`.",
    ),
    where=(
        "https://tnstateparks.com/jsonapi/node/trails",
        "https://tnstateparks.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
