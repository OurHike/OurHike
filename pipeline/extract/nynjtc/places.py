"""New York–New Jersey Trail Conference: places, published, and not landed (coverage audit 2026-10-01,
batch b2_nynjtc).

The `park` vocabulary is NYNJTC's own gazetteer for its alerts and hikes. It is useful as a join key
into DEC/OPRHP/NJDEP park polygons, not as a place source on its own (Reasoned).; The
acquisition-target parcels are do-not-ship. Publishing land a conservancy hopes to buy is a
land-relations …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "• `/highlands-trail-towns/` (modified 2026-09-03): the Highlands Trail Town program, which names 2 "
        "designated towns, Byram Township NJ and High Bridge NJ. Format: page.",
        "The WP taxonomies through `/wp-json/wp/v2/park`, `/region` and `/state`: 125, 13 and 3 terms, with "
        "name, slug, count and link. Names only, no geometry. Format: JSON.",
        "`/backpacking-the-long-path/`: the nearest lodging and campground per section. Format: page.",
        "`/ldt-at-shuttle-info/` (2026-07-20) lists shuttle providers. These are not places.",
        "The 2018 Shawangunk feature collections (`64dc6e61…`, `861a624c…` …",
    ),
    where=(
        "https://nynjtc.org/",
        "https://services7.arcgis.com/G1WTEJ6UVRUTvh9C/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
