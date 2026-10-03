"""Mohonk Preserve: closures, 2 notice sources read here (decision 53 phase B, 2026-10-03).

- `mohonk_alerts`: Mohonk Preserve Alerts, one notice, WordPress page 13789 through its REST route
  (PageNotice). The preserve's Alerts page, with a Closures and an Alerts section, read through
  WordPress page 13789. On 2026-10-03 its Closures section held 'Trailhead Alert: Pine Road Closure
  – October 6–9'. mohonkpreserve.org asks `Crawl-delay: 10`.

- `mohonk_peregrine_updates`: Mohonk Preserve Peregrine Watch updates, one notice, WordPress page
  1502 through its REST route (PageNotice). Seasonal cliff closures for nesting peregrines, read
  through WordPress page 1502 (lifted for 2026 on May 13).

Not read: the site's notification bar (https://mohonkpreserve.org/wp-json/wp/v2/wphash_ntf_bar, one
bar titled 'Weather Alert' carrying a membership promotion on 2026-10-03), watched by the inventory
and not a notice today.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Mohonk Preserve: closures, published, and not landed (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

The alerts page has a real change signal (`modified`), as ALERTS_NOTICES_SURVEY.md §6 found. The
peregrine closures are cliff areas with no published geometry. They would be `place_text` only.
Skeptic additions (Measured 2026-10-01): the page still reads "There are currently not closures" …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `wp-json/wp/v2/pages/13789` (`/visit/alerts/`), `modified`
2026-09-28. It has a "Closures" section, which today reads "There are currently not closures".
`/what-we-do/conservation-programs/conservation-science/peregrine-watch-updates/` (`modified`
2026-05-12) posts dated temporary climbing and bouldering closures, e.g. "4.2.26 … a reduced,
temporary closure will be in place starting Friday, April 3rd" and adjusted boundaries "effective
Wednesday, April 15th".

Its `where`: https://mohonkpreserve.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import page_notice

CLAIMS = ("mohonk_alerts", "mohonk_peregrine_updates")
RESOURCES = [
    page_notice("mohonk_alerts", wp_page=13789, crawl_delay=10.0),
    page_notice("mohonk_peregrine_updates", wp_page=1502, crawl_delay=10.0),
]
