"""PASDA / PA DCNR: closures, from Tioga State Forest's advisories page, hourly (decision 53 phase B,
2026-10-03).

`pa_dcnr_tioga_advisories` reads
https://www.pa.gov/agencies/dcnr/recreation/where-to-go/state-forests/find-a-forest/tioga/advisories as
one PageNotice (extract/_notices.py), read live under our agent on 2026-10-03 after www.pa.gov's
robots.txt (three disallowed paths, none of these; no Crawl-delay). Its <main> holds the advisories as
visible text: 'Pine Creek Rail Trail at the bridge over Asaph Run will be re-routed starting on Monday,
August 24th, 2026', a road closure and campground reservations. (The inventory found the text in the
page's meta description and in an escaped fragment; it is in the rendered body too, checked so that a
hash of <main> moves when an advisory does.) The row lands the title, a hash and the link; the page
states no date. Its weak ETag and Last-Modified are not trusted.

This page is read beside pasda/warnings.py's ParkAdvisory API because the API's answer for Tioga (id
8116) held two statewide items and not this re-route. The other 19 state-forest advisories pages and
129 state-park alerts pages in pa.gov's sitemap (the coverage audit) wait on a reviewed list of which
the build's trails cross; each is another registry row.

The inventory's other two are answered: DCNR's ParkAdvisory API for Tioga (id 8116) lands in
pasda/warnings.py as `pa_dcnr_park_advisories`, and the `laurel-ridge-state-park-alert-cf` fragment
is a standing pointer rather than a notice (not_available.toml [laurel.closures] says why it is not read).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://maps.dcnr.pa.gov/agsprod/rest/services/BOF/HuntStateForest/MapServer, 11 layers ('Roads
Opened for Deer Season', 'Elk Hunt Zones'); no layer was read, so none can be registered yet;
https://maps.dcnr.pa.gov/agsprod/rest/services/BOF/SpongyMothSprayBlocks/MapServer, one layer
'Spongy Moth Spray Blocks', not read;
https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR2/MapServer/9, 'Gated Roads Open
for Deer Season 202310', the 2023 season's roads; self-expiring and three seasons old.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
b5_nyc_nj_ct_ma_pa): "A live re-route on a trail this project draws, published only as a page", whose
`checked` named the pa.gov AEM alert fragments, the per-forest advisories pages and the ParkAdvisory
JSON.
"""

from extract._kinds import page_notice

CLAIMS = ("pa_dcnr_tioga_advisories",)
RESOURCES = [page_notice("pa_dcnr_tioga_advisories", expect_title="Advisories")]
