"""New York State Canal Corporation: closures, held. A candidate steward with no trail_orgs.json row yet, so it
lives in _shared/ under the folder its row would name (decision 122). Its layers load held like every other
candidate's (the lead's call, 2026-10-09): a layer's terms decide its publication, never its extraction, and its
rows quote the website's reproduction clause and each layer's own disclaimer verbatim. Whether the website's words
reach the layers is settled when its trail_orgs.json row is reviewed (decision 121).

- `nys_canal_trail_alerts_page`: the Canalway Trail Alerts page, one PageNotice (its <main>, held to its title
  'Canalway Trail Alerts'). www.canals.ny.gov's robots.txt asks no Crawl-delay (2026-10-09).
"""

from extract._notices import page_notice

TYPE = "closures"
CLAIMS = ("nys_canal_trail_alerts_page",)
RESOURCES = [page_notice("nys_canal_trail_alerts_page", expect_title="Canalway Trail Alerts")]
