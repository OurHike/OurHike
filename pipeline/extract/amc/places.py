"""Appalachian Mountain Club: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `amc_properties_and_landscapes`: AMC Properties and Landscapes, 9 polygon features; places kind
  `park`.
- `amc_chapter_boundaries`: AMC Chapter Boundaries, 11 polygon features; no places kind.

AMC's organization holds about 700 services, many of them copies of other publishers' data (PAD-US
extracts, state trails); only its own two place layers are registered.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("amc_properties_and_landscapes", "amc_chapter_boundaries")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
