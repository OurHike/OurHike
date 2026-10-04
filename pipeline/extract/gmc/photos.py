"""Green Mountain Club: photos, arriving on the overnight-sites layer, which points_of_interest.py's
`gmc_overnight_sites` lands (decision 54 wave 3, section C, 2026-10-04).

OS_MASTER's `Photo1` holds a photo URL on 59 of 72 sites (the coverage audit), hosted in the S3
bucket gmc-public-web-map, so the manifest rows arrive with that layer and this type shares it. The
layer states no licence for the photos, so none publishes on its own word; ATC's layers already
carry 27 of these under ATC's photo licence (atc/photos.py).

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Green Mountain Club: photos, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Not openly licensed. Publishing these needs a basis the maintainer records, the same way
`photo_licence` does for ATC's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `OS_MASTER.Photo1` holds URLs on 59 of 72 sites, hosted in the
S3 bucket `gmc-public-web-map`. No licence is stated. LOADED via atc: `Photo1` on 27 of 27 GMC
shelters.

Its `where`: https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services
https://services8.arcgis.com/kClE0vHJkIEmhQ53/arcgis/rest/services
https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services https://greenmountainclub.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "points_of_interest"
