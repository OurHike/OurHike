"""Texas Trail Tamers: closures, published, and not landed (coverage audit 2026-10-01, batch
p05_persist).

A page, not GIS, so decision 21(a) does not reach it (Reasoned). TPWD's website terms were not read
(@unvalidated). Folder `tpwd/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://tpwd.texas.gov/state-parks/davis-mountains/alert` (HTML, rendered on the server): "Primitive '
        "Area Closures. The primitive camping area will be closed on the following dates: 6 a.m. on Oct. 2 to 8"
        " a.m. on Oct. 10; 6 a.m. on Nov. 6 to 8 a.m. on Nov. 11; 6 a.m. on Feb. 19 to 8 a.m. on Feb. 24. Only "
        'permitted hunters will be allowed on these dates." `/state-parks/mckinney-falls/alert` has no closure '
        "today. Guadalupe Mountains is covered by the NPS Alerts API (b6_federal.md: 617 alerts nationwide; it "
        "needs a key, which I did not use). Tried: 1–3 no closure layer in TPWD's REST folders or …",
    ),
    where=(
        "https://tpwd.texas.gov/state-parks/davis-mountains/alert",
        "https://texastrailtamers.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
