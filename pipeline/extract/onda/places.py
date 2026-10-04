"""Oregon Natural Desert Association: places, published as a post and a town guide PDF with no coordinate, and
not landed (decision 54, waves 4 and 5, read 2026-10-04). The post '18 Trail Towns Along the Oregon Desert
Trail' describes each town and links ODT-Town-Guide-2024-spring_s.pdf; a town is never looked up from its
name. ONDA is a `refuse` row in trail_orgs.json, so whether anything of its own may publish is the
maintainer's open question (ELT.md, decision 39).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "onda.org/robots.txt (Yoast's, a `Crawl-delay: 10` above every group), then "
        "/18-trail-townsalong-the-oregon-desert-trail/, read 2026-10-04 under lib/user_agent.py's agent: 200, "
        "77,779 bytes, no coordinate in the page; it links "
        "/wp-content/uploads/2024/05/ODT-Town-Guide-2024-spring_s.pdf.",
        "the coverage audit (2026-10-01, batch c7_regional_4): six region pages (/regions/...) and /guides/.",
    ),
    where=("https://onda.org/18-trail-townsalong-the-oregon-desert-trail/",),
    reason="needs a per-site reader, not built in this pull request: trail towns described in prose with no coordinate",
)
