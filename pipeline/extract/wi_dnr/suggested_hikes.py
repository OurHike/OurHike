"""Wisconsin DNR Open Data: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Format page. Like NC DPR's per-park trail tables, it sits closer to trail attributes than to
itineraries, but each entry is a described hike with a length. How many properties carry the page
was not counted. `findapark` is the index to walk.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No hike product in the services. The per-property hiking pages on `dnr.wisconsin.gov` were not opened."
        " Skeptic opened one (Measured): `dnr.wisconsin.gov/topic/parks/devilslake/recreation/hiking` (HTTP "
        '200) lists named trails with length and difficulty plus a sentence each, e.g. "East Bluff trail (1.7 '
        'miles) - Most difficult… passes by Elephant Rock", "Johnson Moraine trail (2.8 miles) - Easiest", '
        '"Parfrey\'s Glen trail (0.7 miles)… No food, drink or pets". A web search returned the same '
        "`/<property>/recreation/hiking` pattern for `bluemound`, `mirrorlake`, `ngwoods` and "
        "`StateForests/nhal` …",
    ),
    where=(
        "https://dnr.wisconsin.gov",
        "https://dnr.wisconsin.gov/topic/parks/devilslake/recreation/hiking",
        "https://data-wi-dnr.opendata.arcgis.com/",
        "https://dnrmaps.wi.gov/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
