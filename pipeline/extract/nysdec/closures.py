"""DEC's closures are a weekly web page, which DEC's Website Content Usage policy governs, and no layer.

The NYS GIS Clearinghouse decision (decisions 20 and 22) covers DEC's
datasets, not its web pages (ELT.md, "Who may publish", rule 6), and the
page's items are undated prose. So nothing loads for closures until a person
decides how the page may be read.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://dec.ny.gov/things-to-do/hiking/adirondack-backcountry/backcountry-information-for-adirondack-park
(html_page); https://content.govdelivery.com/accounts/NYSDEC/bulletins/37eccff (html_page);
https://api.nysmesonet.org/data/firewx/GetFDRA/ (json_api - robots.txt disallows it, so not to be
fetched).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "the Adirondack backcountry information page, headed 'New this week (9/24/2026)', in 10 regional "
        "sections, each item undated prose (Tirrell Pond lean-to closed Sept 25 to Oct 12, among others)",
        "DEC's GovDelivery bulletins: 200 on 2026-10-01, 403 on 2026-08-27",
        "DEC's ArcGIS Online org and on-prem server for a closure or status layer: none found",
    ),
    where=(
        "https://dec.ny.gov/things-to-do/hiking/adirondack-backcountry/backcountry-information-for-adirondack-park",
        "https://content.govdelivery.com/accounts/NYSDEC/bulletins/37eccff",
    ),
    reason="a web page under DEC's Website Content Usage policy, outside the clearinghouse decision",
)
