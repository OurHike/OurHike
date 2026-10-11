"""Nebraska Game and Parks Commission: closures. The commission's trail_orgs.json row, `ngpc` (`load: ship`), was
approved on 2026-10-11 (decision 121, review page 01), so these files moved here from _shared/ngpc/, where decision 122
had loaded them held, and every raw table kept its name.

- `ngpc_cowboy_trail_improvements`: `Cowboy_Trail/FeatureServer/5`, the Cowboy Trail in 29 sections, each with
  a status and a condition (2 closed and impassable on 2026-10-09). One section reads 'Open' and 'Not Passable'
  at once, which its row says no rule may show as open.

This layer is the Cowboy Trail's line too, by the maintainer's choice on the row's review (P8): it covers only the
developed trail, so not_available.toml's [ngpc.trail_lines] shares it, and the commission's one-feature corridor line,
Cowboy_Trail_Complete (321.33 mi), must never draw as trail.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ngpc_cowboy_trail_improvements",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
