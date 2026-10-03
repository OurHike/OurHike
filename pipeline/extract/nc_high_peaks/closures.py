"""NC High Peaks Trail Association: closures, drawn from usfs/closures.py's National Forests in North Carolina
alerts page (decision 53 phase B, 2026-10-03).

The club's own page is a list of trails open, never of trails closed, so it lands in warnings.py and
not here. The closures on its trails are the land managers': the National Forests in North Carolina's
alerts page, which lands once in usfs/closures.py as `usfs_r08_northcarolina_alerts` (decision 34), and
NPS's Blue Ridge Parkway alerts in nps/warnings.py.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c7_regional_4): "Page. 14 months stale, and an inverse list (open, not closed). Low value as a closure
source."
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "usfs/closures.py `usfs_r08_northcarolina_alerts` reads https://www.fs.usda.gov/r08/northcarolina/alerts "
        "(decision 53 phase B, 2026-10-03): 59 alert cards; 'Black Mountain' appears in none of their slugs "
        "(decision 53 inventory, batch 2).",
        "https://nchighpeaks.org/2024Hikes, 'Hiking Trails Currently Open in Our Area', 'Update 7/30/2025': an "
        "inverse list, landed by warnings.py as nchpta_open_trails.",
    ),
    where=(
        "https://www.fs.usda.gov/r08/northcarolina/alerts",
        "https://nchighpeaks.org/2024Hikes",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the page this org's closures arrive in",
)
