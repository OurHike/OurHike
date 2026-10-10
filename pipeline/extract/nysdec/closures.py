"""DEC's closures: the weekly Adirondack backcountry information page, hourly, as facts and a link (decision 53
phase B and decision 55, 2026-10-03).

`nysdec_adk_backcountry` reads the page as one PageNotice (extract/_notices.py), read live under our agent
on 2026-10-03 after dec.ny.gov's robots.txt (Drupal internals only, no Crawl-delay). The row is the
page's title, its own weekly date, read from the header 'New this week (10/1/2026)' by the
`date_pattern` below, a hash of its <main> (10 regional sections of undated prose items, 49,851
characters that day) and the link. No item's wording lands.

WHY THIS IS NO LONGER A NOTE. This file said nothing could load until a person decided how a page under
DEC's Website Content Usage policy may be read: the NYS GIS Clearinghouse decision (decisions 20 and
22) covers DEC's datasets, not its web pages (ELT.md, "Who may publish", rule 6). Decision 55 (poll,
2026-10-03) is that decision, and names DEC: a notice whose site restricts copying but not reading
publishes as facts in OurHike's own words and a link, the terms quoted verbatim on its sources.json
row and its `licence_basis` the maintainer's.

NOT READ: DEC's GovDelivery bulletin (content.govdelivery.com/accounts/NYSDEC/bulletins/37eccff, 200 on
2026-10-03, 403 on 2026-08-27) is one bulletin per URL, not a channel, until the account's bulletin
index is found; and the NYS Mesonet fire-danger API (api.nysmesonet.org/data/firewx/GetFDRA/), whose
robots.txt disallows it, is never fetched.

Before decision 53 phase B this file was a note (confirmed 2026-10-01) whose `checked` read: "the
Adirondack backcountry information page, headed 'New this week (9/24/2026)', in 10 regional sections,
each item undated prose (Tirrell Pond lean-to closed Sept 25 to Oct 12, among others)"; "DEC's
GovDelivery bulletins: 200 on 2026-10-01, 403 on 2026-08-27"; "DEC's ArcGIS Online org and on-prem
server for a closure or status layer: none found".
"""

from extract._kinds import page_notice
from extract._notices import DATE

# The page's own weekly header, 'New this week (10/1/2026)' on 2026-10-03.
NEW_THIS_WEEK = r"New this week \(" + DATE + r"\)"

CLAIMS = ("nysdec_adk_backcountry",)
RESOURCES = [page_notice("nysdec_adk_backcountry", date_pattern=NEW_THIS_WEEK)]
