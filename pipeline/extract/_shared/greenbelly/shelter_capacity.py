"""Shelter capacities from the Greenbelly scrape: reference/shelter_capacity.json, reviewed in git, one row per shelter.

280 shelters, keyed by `poi_id` (ELT.md, "One key per table").
build_shelter_capacity.py produces the file and a person reviews it; the
reviewed file is what loads, and the scrape itself is not rebuilt here.
CLAUDE.md's rule for this file stands: a capacity nobody stands behind
exports none, so an absent capacity stays absent through every layer.
"""

from extract._kinds import reviewed_file

TYPE = "points_of_interest"
CLAIMS = ("reference/shelter_capacity.json",)
RESOURCES = [reviewed_file("reference/shelter_capacity.json", rows_key="shelters")]
