"""NC Mountains-to-Sea Trail (state-published layer): photos, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Published, but not openly licensed: the statement grants nothing. `may_publish` false. Some items
may be public domain by age, which is @unvalidated per item. The Flickr "NC State Parks Pool"
(`flickr.com/groups/ncfsp/`) is the Friends group's member photos, not DPR's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Photos_let/0` MAP_TOUR: 8 points with `pic_url` (2020). No licence.",
        'Skeptic correction (Measured): `Photos_let` is the item "Photos Tobacco Museums_let", owner a personal'
        ' ArcGIS account, licence "For Educational Purposes Only". It belongs to DNCR\'s historic-preservation '
        "side and says nothing about parks. DPR's photo collection is the North Carolina State Parks digital "
        "collection, `digital.ncdcr.gov/collections/north-carolina-state-parks` (format page; photographs, "
        "drawings and postcards from 1916 on, held jointly by the State Archives, State Library and DPR; "
        "per-item download). Its rights …",
    ),
    where=(
        "https://digital.ncdcr.gov/collections/north-carolina-state-parks",
        "https://flickr.com/groups/ncfsp/",
        "https://services7.arcgis.com/SEKZuPu27jfvDQ5b/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
