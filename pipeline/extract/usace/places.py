"""US Army Corps of Engineers: places, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest; re-read for decision 54's wave 3 on 2026-10-04).

RIDB's `/recareas`, the Corps' recreation areas on Recreation.gov, is refused by
ridb.recreation.gov's robots.txt for every agent, ours included, before any key would matter. RIDB's
bulk export is allowed and answers, but it is Recreation.gov's national download for twelve agencies
(pipeline/SOURCE_SURVEY.md), not a Corps publication, so it would be a provider row of its own and is
the lead's to route; usace/points_of_interest.py records the same read.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "ridb.recreation.gov/robots.txt, read 2026-10-04T11:41:47Z under lib/user_agent.py's agent: `User-agent: *` / `Disallow: /api` / `Disallow: /api/*` / `Crawl-delay: 10`; `/api/v1/recareas` falls under it, so it was not requested.",
        "https://ridb.recreation.gov/downloads/RIDBFullExport_V1_CSV.zip, one HEAD on 2026-10-04 (robots allows /downloads/): 200, application/zip, 247,747,658 bytes, Last-Modified Sat, 03 Oct 2026 18:47:00 GMT. Not downloaded, so the Corps' share of it is unmeasured.",
    ),
    where=(
        "https://ridb.recreation.gov/robots.txt",
        "https://ridb.recreation.gov/downloads/RIDBFullExport_V1_CSV.zip",
        "https://usace.army.mil/",
    ),
    terms="ridb.recreation.gov/robots.txt (read 2026-10-04): `User-agent: *` / `Disallow: /api`",
    reason="refused for the API by robots.txt; the bulk export is Recreation.gov's, not the Corps', and the lead routes it",
)
