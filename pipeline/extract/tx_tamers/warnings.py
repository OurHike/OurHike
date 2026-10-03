"""Texas Trail Tamers: warnings, drawn from _shared/tpwd/'s two state-park alert pages (decision 53 phase B,
2026-10-03).

The burn bans at McKinney Falls and Davis Mountains are the warnings half of the TPWD alert pages that
land once in _shared/tpwd/park_alerts.py (decision 34); the warnings staging model reads those tables
too. closures.py says what else was looked at.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
p05_persist), whose `checked` is kept below.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via _shared/tpwd/park_alerts.py `tpwd_davis_mountains_alerts` and `tpwd_mckinney_falls_alerts` (decision "
        "53 phase B, 2026-10-03).",
        '(coverage audit, 2026-10-01) McKinney Falls: "Burn Ban Aug. 11, 2026 - The park is under a burn ban. Wood fires are not allowed." '
        'Davis Mountains: "Burn Ban Jan. 1, 2026 - No wood fires are allowed." Tried: as closures.',
    ),
    where=(
        "https://tpwd.texas.gov/state-parks/mckinney-falls/alert",
        "https://services1.arcgis.com/1mtXwieMId59thmg/arcgis/rest/services",
        "https://tpwd.texas.gov/arcgis/rest/services",
        "https://texastrailtamers.org/",
    ),
    reason="drawn from _shared/tpwd/'s resources, extracted once there (decision 34); checked names the pages this org's warnings arrive in",
)
