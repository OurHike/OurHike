"""OuterSpatial: a platform land managers publish through, so nothing of its own to extract.

Its terms are per land manager, not per platform (trail_orgs.json's `why`), so
there is no single answer to record; a manager's data is that manager's to
publish, and lands in that manager's folder. not_available.toml [buckeye.trail_lines] lists the
Ohio DNR copy reachable this way among what it checked (ELT.md, "Decision 18
overrides round 5 for two refusals").
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "85,155 trail pages in `sitemaps/trails/trails-0/1.xml.gz`, from 204 organisations' trail sitemaps; pages "
        "and an app, with export on request (coverage audit, batch c12_umbrella_route_aggregator)",
    ),
    where=("https://www.outerspatial.com/",),
    terms="custom, per land manager",
)
