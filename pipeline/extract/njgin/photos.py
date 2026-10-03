"""NJDEP / NJGIN — Statewide Trails: photos, could not be told (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

Skeptic, 2026-10-01: UNKNOWN kept. A search of the NJDEP AGOL org (`orgid:QWdNfRs7lkPq4g4Q`) for
"photo" returns 30 items, all habitat, solar, shoreline or land-use layers, none a feature-photo
layer. Flickr aliases `njdep`, `njstateparks` and `newjerseystateparks` do not exist (404). NJ State
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Land/62` `PHOTO`: 20 rows carry `http://www.njparksandforests.org/interactive_map/.jpg`, a host that "
        "now answers 301. No licence covers image bytes.",
    ),
    where=(
        "https://mapsdep.nj.gov/arcgis/rest/services",
        "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
