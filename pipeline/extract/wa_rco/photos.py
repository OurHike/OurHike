"""Washington RCO: photos, as manifest rows read from RCO's camping inventory layer, never their pixels.

Section K of decision 54 handed this back as an ArcGIS photo field; read live on 2026-10-10 (robots.txt first,
lib/user_agent.py's agent, 2 s or more between requests to one host) and registered in sources.json, where its row
carries the counts, the measured key, the fields it never asks for, and the terms, which state nothing.

- `wa_rco_camping_photos`: Camping_scorp_view's layer 0 ("RCO Web Points"), a campground inventory from
  Washington's outdoor recreation plan. 152 of its 974 campgrounds carry a photograph's URL in `PhotoWeb`, on
  mapswa.com, and the row's `where` keeps those. Keyed on `LocLink`, the inventory's own id.

Neither the layer nor mapswa.com states a licence for the photographs, and mapswa.com is not RCO's domain, so the
row reaches no hiker (reaches_hikers false) until the maintainer rules on photographs with no stated licence. The
campgrounds themselves are not landed here: they are not_available.toml [wa_rco.points_of_interest]'s cell.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("wa_rco_camping_photos",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
