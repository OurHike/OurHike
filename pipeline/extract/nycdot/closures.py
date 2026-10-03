"""NYC Department of Transportation: closures, published, and walled to our agent on 2026-10-03.

The find for NYC is DOT's Greenway Closures page, which names long-term closures of tread
`nyc_dot_greenways` draws today (East River Park the largest), 8 links, posted under Local Law 115 of
2022 (the coverage audit, 2026-10-01, which read it with a 200).

On 2026-10-03 decision 53's inventory (batch 1) got Akamai's 'Access Denied' (HTTP 403, a 423-byte page
with an errors.edgesuite.net reference) for both https://www.nyc.gov/robots.txt and the page, under our
agent, from the session's sandbox. A wall is not solved or worked round (decision 39), so nothing was
retried and no other agent was tried. Whether the edge refuses our agent, the sandbox's address or
neither for long is unknown: a read from a GitHub runner, under the same agent, would settle it, and a
registry row follows only a 200.

Before this, the file was the coverage audit's note (confirmed 2026-10-01, batch b5_nyc_nj_ct_ma_pa),
whose `checked` is kept below.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(decision 53 inventory, batch 1, 2026-10-03) https://www.nyc.gov/robots.txt and the Greenway Closures "
        "page both answered 403 'Access Denied' from Akamai (errors.edgesuite.net reference) to our agent. Not "
        "retried; no other agent tried.",
        "(coverage audit, 2026-10-01) Greenway Closures on the page (200 that day): 8 closures 'lasting more "
        "than three months', posted under Local Law 115 of 2022: Brooklyn 1 (Red Hook), Manhattan 6 (South "
        "Street Dover–Catherine Slip for the BMCR project; East River Park, Montgomery St to E 15th St, for "
        "ESCR; the Battery to the BPC esplanade; E 114th–117th St; the 79th Street Rotunda; the East River "
        "Esplanade at E 70th–75th St), and Staten Island 1 (the North Shore Esplanade). Each links to the "
        "managing agency's own notice.",
    ),
    where=(
        "https://www.nyc.gov/html/dot/html/bicyclists/greenways.shtml",
        "https://www.nyc.gov/robots.txt",
    ),
    reason=(
        "a wall: the host answered our agent with Akamai's 403 on 2026-10-03, robots.txt included; held until a "
        "read under the same agent answers 200"
    ),
)
