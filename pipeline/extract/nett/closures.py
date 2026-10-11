"""NorthEast Texas Trail Coalition: closures. The coalition's trail_orgs.json row, `nett` (`load: ship`), was approved
on 2026-10-11 (decision 121, review page 02), so these files moved here from _shared/nett/, where decision 122 had
loaded them held, and every raw table kept its name.

- `nett_damaged_bridges`: `NET_KML_Damaged_Bridges/FeatureServer/0`, 3 bridges collapsed or burned (2026-10-09),
  each dated only in its popup's prose (2014 to 2017), and last edited 2018. Nothing on the layer says any of the
  three is current. The maintainer chose how they show (the poll of 2026-10-11, review page 02, P11): each drawn
  closed with its note's date, "Their note is from 2017. OurHike has not checked it since."
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nett_damaged_bridges",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
