"""River to River Trail Society: closures. The society's trail_orgs.json row, `r2r` (`load: via`, its line the Forest
Service's), was approved on 2026-10-11 (decision 121, review page 01), so this file moved here from _shared/r2r/, where
decision 122 had loaded it held, and its raw table kept its name.

- `r2r_trail_conditions`: the 'Trail Conditions' category's posts (36 on 2026-10-09), reroutes, detours lifted,
  storm damage and volunteer news among them; no post carries a status. rivertorivertrail.net's robots.txt asks
  no Crawl-delay and allows the REST route (2026-10-09).
"""

from extract._kinds import wordpress_posts

CLAIMS = ("r2r_trail_conditions",)
RESOURCES = [wordpress_posts("r2r_trail_conditions")]
