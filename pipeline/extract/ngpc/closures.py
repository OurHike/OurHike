"""Nebraska Game and Parks Commission: closures. The commission's trail_orgs.json row, `ngpc` (`load: ship`), was
approved on 2026-10-11 (decision 121, review page 01), so these files moved here from _shared/ngpc/, where decision 122
had loaded them held, and every raw table kept its name.

- `ngpc_cowboy_trail_improvements`: `Cowboy_Trail/FeatureServer/5`, the Cowboy Trail in 29 sections, each with
  a status and a condition (2 closed and impassable on 2026-10-09). One section reads 'Open' and 'Not Passable'
  at once, which its row says no rule may show as open.

This layer is the Cowboy Trail's line too, by the maintainer's choice on the row's review (P8): it covers only the
developed trail, so not_available.toml's [ngpc.trail_lines] shares it, and the commission's one-feature corridor line,
Cowboy_Trail_Complete (321.33 mi), must never draw as trail: no sources.json row registers it, so no file can read it.

ONE EXTRACTION, TWO LANES. This resource is a closure's, so it rides the hourly lane (the notices job), and
generate_notice_models.py stages that copy for the closures. The trail_lines nodes that draw the line are the
monthly lane's, whose warehouse holds only what that lane lands, so the monthly lane lands its own copy of this
table as well (extract/_run.py's ALSO_READS, with --cross-lane-inputs): the same resource and the same raw table
name, read again at the monthly build's own time and pinned with its raw_run. make_dbt_staging.py stages that copy
for the line under a source table and a base model of its own (its docstring, "A LANE COPY").

The line's rules are rows of dbt/seeds/layer_rules.csv, which int_trail_lines__club_lines reads: only a section
whose Road_Status is 'Open' or 'Closed' draws (the two 'Alt Route' sections are the HWY 275 detour beside the closed
Elkhorn bridges, never trail), and a section whose Road_Status is 'Closed' or whose Condition is 'Impassable' or
'Not Passable' draws closed, the same values the closures read as closing the trail
(seeds/notice_status_values.csv and seeds/notice_category_values.csv, which tests/test_ngpc_cowboy_trail.py holds
them to).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ngpc_cowboy_trail_improvements",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
