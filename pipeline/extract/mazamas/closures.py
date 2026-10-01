"""Mazamas: closures, nothing published (coverage audit 2026-10-01, batch p04_persist).

Licence class (USFS layer): none_stated beyond a federal disclaimer; a federal work. "The USDA
Forest Service makes no warranty … These geospatial data and related maps or graphics are not legal
documents". The data belongs in `usfs`, not in a Mazamas folder (decision 18: Mazamas gets a …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Mazamas publishes none, and has no trail or area of its own for a land manager's closure to attach to "
        "(Reasoned, from the audit's UMBRELLA classification). Tried: (6) and (7): the sitemap has no "
        "conditions, alerts or feed URL, and `/feed/` is 404 (audit). (2) and (5) as above. (4) Land manager, "
        "for the record: on Mt. Hood NF, USFS `R06_FireClosureOrders_PublicView` holds 604 active closure "
        "lines. 600 of them are the Grasshopper order 06-06-01-26-06 on the Barlow RD, to 2026-12-31. Gifford "
        "Pinchot NF holds 84 active lines.",
    ),
    where=("https://mazamas.org/",),
)
