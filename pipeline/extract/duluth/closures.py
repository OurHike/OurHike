"""City of Duluth Open Data: closures, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

No feed was found. The city's `RoadClosures/` services are for streets.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Format page: the `duluthmn.gov/parks/` news list carries trail closures, e.g. "Portion of Chester Park'
        ' Trail Closed Due to Washout" (2017-08-29); "Closed" appears 46 times on the page. '
        "`/parks/cancellations/` lists programme cancellations.",
    ),
    where=(
        "https://duluthmn.gov/parks/",
        "https://data-duluthmn.opendata.arcgis.com/",
        "https://utility.arcgis.com/usrsvcs/servers/085f4309eec943a8998e801f7849b1b8/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
