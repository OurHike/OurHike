"""New Mexico Volunteers for the Outdoors: closures, published, and not landed (coverage audit
2026-10-01, batch c6_regional_3).

Today the channel carries a single closure. The closure itself is the Cuba Ranger District's, so a
dbt test should check it against the USFS source.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same CalTopo map. One of 29 scouting reports carries a closure: Los Pinos Trail FT 46, scouted "
        '9/2/2026: "Because Cuba RD has closed the TH…"',
    ),
    where=(
        "https://coageo.cabq.gov/cabqgeo/rest/services",
        "https://nmvfo.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
