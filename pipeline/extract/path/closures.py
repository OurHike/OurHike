"""Piedmont Appalachian Trail Hikers: closures, drawn from another folder's resource (coverage audit
2026-10-01, batch p05_persist).

ATC: `maintainer_authorisation` (sources.json). GWJ: a federal page, public domain. Privacy: the
alert pages' contact blocks name individual staff with email addresses, so a scraper must drop the
contact fields. Folder `usfs/` for GWJ.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Loaded: ATC updates "Lick Creek: Bridge Washout" (Detour, mile 563.8, updated 2026-07-20). Not loaded:'
        " `https://www.fs.usda.gov/r08/gwj/alerts` has 30 alerts, 0 of them trail closures on PATH's miles "
        'today. "Mount Rogers National Recreation Area Current Road Conditions" (last updated 2026-07-30) says '
        '"Forest Service Road 86 Glade Mountain, and Forest Service Road 644 Overbay will be closed for '
        'reconstruction through the month of August." `EDW_RoadBasic_01` puts FSR 86 within 0.08 mi of A.T. '
        "mile 538.5 and FSR 644 within 0.08 mi of mile 542. Tried: 1 the PATH site is Wix, with no REST host. 2"
        " …",
    ),
    where=("https://www.fs.usda.gov/r08/gwj/alerts",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
