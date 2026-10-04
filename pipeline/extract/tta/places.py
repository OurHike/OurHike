"""Tennessee Trails Association: places, held for permission: its hike venues are a public REST list, and
its terms forbid copying the site's content without written permission (decision 54, wave 3, read
2026-10-04).

The Events Calendar's `/wp-json/tribe/events/v1/venues` lists 154 venues, 39 with geo_lat/geo_lng: where
the association's hikes meet (trailheads, parks, a brewery, 'Liberty Park Meeting Spot'). Some are a
person's: three venues named 'deb' or 'DEB', two with a telephone number. The site's terms of service
are a permission gate on copying (`terms`), so this is a dated note (the dlt skill: 'Note now, load on
permission'). If permission comes, the venues' `phone`, `address`, `zip`, `description` and `author`
never load (decision 59).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://tennesseetrails.org/wp-json/tribe/events/v1/venues, read 2026-10-04 under lib/user_agent.py's agent at the host's `Crawl-Delay: 60`: 4 pages of 50, `total` 154 (X-TEC-Total 154), 39 with a coordinate, 17 with a phone, 122 with an address; id unique on 154.",
        "https://tennesseetrails.org/robots.txt, read 2026-10-04: `User-agent: *` then `Crawl-Delay: 60` and Events Calendar URL-matrix disallows; the REST route is not disallowed.",
        "https://tennesseetrails.org/terms-of-service/, read 2026-10-04: quoted in `terms`; it also forbids 'the use of any device software and/or routine to bypass the robot exclusion headers'.",
    ),
    where=(
        "https://tennesseetrails.org/wp-json/tribe/events/v1/venues",
        "https://tennesseetrails.org/terms-of-service/",
    ),
    terms="You agree not to reproduce, duplicate, copy, sell, resell or exploit any portion of the Site, use of the Site, or access to the Site or any contact on the Site, without express written permission by us. You may not modify, publish, transmit, reverse engineer, participate in the transfer or sale, create derivative works, or in any way exploit any of the content, in whole or in part, found on the Site. (https://tennesseetrails.org/terms-of-service/, read 2026-10-04)",
    reason="held for permission: the site's terms forbid copying its content without express written permission",
)
