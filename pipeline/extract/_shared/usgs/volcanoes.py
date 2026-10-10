"""USGS's elevated volcanoes, as `raw_usgs__usgs_elevated_volcanoes`, on the hourly lane that builds `warnings`.

A national hazard service, so it sits in _shared/usgs/ beside 3DEP and NHD
rather than in a club folder; the decision 53 inventory found it through the
usgs-tnm row (batch 1, 2026-10-03). Public domain as a federal work. One row
per volcano USGS rates above normal, keyed by `vnum`; which drawn trails it
concerns (the Cascades, Hawaii, Alaska) is a join for dbt to make, and
nothing here filters by place.
"""

from extract._json_apis import usgs_elevated_volcanoes

TYPE = "warnings"
CLAIMS = ("usgs_elevated_volcanoes",)
RESOURCES = [usgs_elevated_volcanoes("usgs_elevated_volcanoes")]
