"""What kind of thing each entry in sources.json is, and who may fetch it.

For twelve entries this question had one answer, so nothing had to ask it:
every source was an ArcGIS feature layer, and `fetch_all.py` could hand
`src["url"]` straight to `fetch_layer_to_file` without looking. ATC's Trail
Updates are the thirteenth and the first that is not
(features/ATC_TRAIL_UPDATES.md, #459) - a WordPress site read for its
published safety notices, which answers an ArcGIS query with a 403 and an
HTML error page rather than with features.

So `kind` becomes the discriminator, and this module is the one place that
reads it.

WHY THE FIELD IS OPTIONAL, and defaults to the ArcGIS spelling rather than
being required on every entry: `discover_sources.py` rebuilds each entry it
rediscovers from the layer metadata, so a field it does not know to carry
forward is dropped the next time discovery runs. Requiring `kind` on all
thirteen would mean twelve values that vanish on a re-run and one that
survives - a schema that looks enforced and is not. The default is where the
twelve actually live, and `is_arcgis_feature_layer` is true for them without
anything being written down that discovery can lose.

That is a limitation of discovery rather than a preference, and it is fixed
in the same change: `discover_sources.py` now carries unknown fields through.
The default stays anyway, because it is what makes a registry written before
this module still readable by it.
"""

from __future__ import annotations

import json
from pathlib import Path

# The kind twelve of the thirteen entries are, and the one `fetch_all.py`
# knows how to fetch. Spelled once here rather than at each comparison.
ARCGIS_FEATURE_LAYER = "arcgis_feature_layer"

# A source published as prose on a website rather than as a data layer. Read
# by a human, reviewed into a file in git, and baked from there - never
# fetched into `data/raw/` on a schedule, which is why `fetch_all.py` skips
# it rather than growing a second fetcher (features/ATC_TRAIL_UPDATES.md's
# "the parse proposes; a human publishes").
PUBLISHED_NOTICES = "published_notices"

KNOWN_KINDS = frozenset({ARCGIS_FEATURE_LAYER, PUBLISHED_NOTICES})


def load_registry(path: Path) -> dict:
    """sources.json, whole - the `photo_licence` block included.

    Returns the document rather than just its `sources` list, because the
    top-level keys are part of the registry too: `photo_licence` records the
    basis on which ATC's photos may be served, and a reader that returned
    only the list would invite a caller to rewrite the file without it.
    """
    return json.loads(path.read_text())


def source_kind(entry: dict) -> str:
    """One entry's kind, defaulted. See this module's docstring for why."""
    return entry.get("kind", ARCGIS_FEATURE_LAYER)


def is_arcgis_feature_layer(entry: dict) -> bool:
    return source_kind(entry) == ARCGIS_FEATURE_LAYER


def arcgis_sources(registry: dict) -> list[dict]:
    """The entries `fetch_all.py` may fetch, in registry order."""
    return [entry for entry in registry.get("sources", []) if is_arcgis_feature_layer(entry)]


def find_source(registry: dict, key: str) -> dict | None:
    for entry in registry.get("sources", []):
        if entry.get("key") == key:
            return entry
    return None
