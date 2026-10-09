"""River to River Trail Society: closures, held. A candidate steward with no trail_orgs.json row yet, so it lives in
_shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type,
held"). Held until the maintainer approves the society's trail_orgs.json row in chat (decision 121); then this
file moves to the club folder of the same name.

- `r2r_trail_conditions`: the 'Trail Conditions' category's posts (36 on 2026-10-09), reroutes, detours lifted,
  storm damage and volunteer news among them; no post carries a status. rivertorivertrail.net's robots.txt asks
  no Crawl-delay and allows the REST route (2026-10-09).
"""

from extract._kinds import wordpress_posts

TYPE = "closures"
CLAIMS = ("r2r_trail_conditions",)
RESOURCES = [wordpress_posts("r2r_trail_conditions")]
