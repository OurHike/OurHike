"""Arizona Trail Association: elevation, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

It is derived from USGS, so it adds little over 3DEP. It is useful as a cross-check of the
pipeline's own profile. Skeptic spot-check: layer `/3` reports `hasZ: true`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Layer `/3` carries Z: passage 1 runs 5,505–9,095 (12,855 vertices). The unit is feet, judged from the "
        'Huachucas\' known crest (Reasoned). The item says the Z comes from a "10M USGS DEM". Layer `/1` has an '
        '`Elevation` field. The Web Experience "Arizona National Scenic Trail Elevation Profile" is '
        "`dd1becd86ed24b43b957532f8546b15d`.",
    ),
    where=(
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services",
        "https://aztrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
