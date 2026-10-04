"""Upper Valley Trails Alliance: points of interest, refused: Trail Finder's terms forbid systematically
extracting its data (decision 55 lists Trail Finder among the refusals).

The alliance's GIS files are Trail Finder's per-trail KML and GPX downloads (www.trailfinder.info, which
UVTA administers for 973 partner managers' trails). Its robots.txt answered 200 and empty (read
2026-10-04), so robots does not refuse; its terms do, quoted in `terms` as decision 53's inventory read
them on 2026-10-03. A refusal is a dated note, never routed round (decision 39): the route forward is
Trail Finder's written consent, which the maintainer asks for. Before this the file was the coverage
audit's 'published, and not landed' note (2026-10-01), which said the same files need written consent.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(decision 54 wave 2, 2026-10-04) https://www.trailfinder.info/robots.txt: 200, empty body; the per-trail files (`kml/TrailPoints702.kml` and its GPX, labelled 'Download Points of Interest (points)' on the Mount Monadnock page, the coverage audit) were not requested, because the terms refuse.",
        "(decision 53 inventory, batch 3, 2026-10-03) https://www.trailfinder.info/terms, read whole: its 'you agree that you shall not' list forbids systematic extraction and redistribution (quoted in `terms`).",
        "(coverage audit, 2026-10-01) the /trails listing reads 'Showing 973 Trails'; ArcGIS Online search for 'Upper Valley Trails Alliance': 0 results.",
    ),
    where=(
        "https://www.trailfinder.info/terms",
        "https://www.trailfinder.info/robots.txt",
        "https://uvtrails.org/",
    ),
    terms='"Furthermore, you agree that you shall not: ... Collect information about other visitors to our website without their consent or otherwise systematically extract data or data fields, including without limitation any financial data or email addresses;" and "Redistribute any content, including data, provided by us in any manner whatsoever including by means of printed publication, fax broadcast, web pages, e-mail, web newsgroups or forums, or any other electronic or paper-based service or method;" (https://www.trailfinder.info/terms, read 2026-10-03 by decision 53\'s inventory, uvta/closures.py)',
    reason="refused: Trail Finder's terms forbid systematic extraction and redistribution; held until Trail Finder permits in writing",
)
