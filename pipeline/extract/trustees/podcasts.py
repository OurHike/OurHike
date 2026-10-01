"""The Trustees of Reservations: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Coastal-programme content, not trail content, and two episodes, so `_shared/podcasts` material at
most. Licence unstated.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Trustees On The Coast", artist "The Trustees". Apple id 1485305394. RSS '
        '`https://anchor.fm/s/102fa3a7c/podcast/rss`: 2 items with enclosures, both dated 2025-03-27 ("A '
        'shorebird story: Piping Plovers on Trustees beaches", "Raise the Road! Protecting Argilla Road Access '
        'to Crane Beach"), with an empty `<copyright>`. Linked from `www.onthecoast.thetrustees.org/podcast`, '
        "which this sandbox's proxy refused (502), so it was not read. Separately, `/content/audio-tours/` "
        "offers deCordova sculpture audio tours through the OnCell app. Those are not trail content.",
    ),
    where=(
        "https://anchor.fm/s/102fa3a7c/podcast/rss",
        "https://www.onthecoast.thetrustees.org/podcast",
        "https://thetrustees.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
