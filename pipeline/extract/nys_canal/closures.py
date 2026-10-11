"""New York State Canal Corporation: closures. The Canal Corporation's trail_orgs.json row, `nys-canal` (`load: ship`),
was approved on 2026-10-11 (decision 121, review page 02), so these files moved here from _shared/nys_canal/, where
decision 122 had loaded them held (the lead's call, 2026-10-09), and every raw table kept its name. The maintainer read
its website's copyright sentence as the website's own (P9 of the same poll): its GIS layers publish under decision 21a,
the sentence quoted in each layer row's `licence`, and this notice publishes as facts and a link under decision 55.

- `nys_canal_trail_alerts_page`: the Canalway Trail Alerts page, one PageNotice (its <main>, held to its title
  'Canalway Trail Alerts'). www.canals.ny.gov's robots.txt asks no Crawl-delay (2026-10-09).
"""

from extract._notices import page_notice

CLAIMS = ("nys_canal_trail_alerts_page",)
RESOURCES = [page_notice("nys_canal_trail_alerts_page", expect_title="Canalway Trail Alerts")]
