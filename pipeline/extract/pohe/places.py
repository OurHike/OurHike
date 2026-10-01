"""Potomac Heritage Trail Association: places, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Belongs in the `nps` folder. Deduplicate across parks: the same place arrives under `choh`, `gwmp`
and the rest.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "NPS API `/places?parkCode=pohe`: 156. `/visitorcenters`: 2.",
        "Skeptic: not reproduced. The API's `total` reads 332 today, and every one of the 332 also lists "
        "another park in `relatedParks`: CHOH 136, CWDW+ROCR 42, FOWA+NACE 35, GWMP 23, and so on. NPS "
        "`POHE_GIS` also publishes `POHE_Trail_Regions_View/4`, 9 management-region polygons with `NPSgov_URL` "
        "and StoryMap links (last edit 2026-07-10).",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/pohe/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
