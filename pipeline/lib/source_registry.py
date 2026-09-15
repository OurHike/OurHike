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

# A PDF one of the thirty maintaining clubs publishes (#669) - GATC's water
# sources first. Fetched by fetch_club_pdfs.py into data/raw/club_pdfs/ and
# parsed where lib/club_pdfs.py has a parser for it, for review and
# cross-checks; nothing of this kind reaches a published artifact until the
# entry's `licence` says the club has answered (CONTRIBUTING.md, "A note on
# data and licences"). fetch_all.py skips it like everything not ArcGIS.
CLUB_PDF = "club_pdf"

# OSM data read from Geofabrik's daily state extracts (#529) - water point
# sources first, and the same extracts the basemap build already downloads.
# Fetched by fetch_osm_water.py (never fetch_all.py: multi-gigabyte
# downloads are a conditional workflow step, not a scheduled pull), and
# deliberately absent from check_freshness.py - Geofabrik republishes daily,
# so "changed" is always true and a marker would be noise, which is
# export_basemap.py's reasoning applied to a registry entry.
GEOFABRIK_EXTRACT = "geofabrik_extract"

# A source nothing here fetches, registered so that somebody is told when it
# becomes worth fetching. USGS's 3D Hydrography Program is the first: it is
# the successor to the retired NHD this pipeline's water derivation depends
# on, it is the product USGS actually maintains - and for the A.T. corridor
# it currently republishes NHD unchanged, so migrating today would cost the
# perennial/intermittent classification and buy nothing (WATER_SOURCES.md
# section 5). The registry entry exists to hold the watch, not a fetch:
# `fetch_all.py` skips it like everything not ArcGIS, and check_freshness.py
# reports on it so the day the answer changes is a day somebody hears about.
WATCHED_ONLY = "watched_only"

# An ArcGIS feature layer on another organization's own org, outside the
# A.T. build - NYS OPRHP's four Parks Explorer layers first (#769, the
# registration #768's program asked for). Its own kind rather than the
# default, for two reasons that are both about fetch_all.py's completeness
# gate. That gate is the A.T. release's ("every registered source produced a
# non-empty collection"), so folding another organization's layers into it
# couples the A.T. fetch to that org's uptime - and one of these layers is a
# TEMPORARY trail-closure layer whose honest feature count in a good week is
# zero, which that gate can only read as broken. fetch_external_layers.py
# fetches these instead, change-aware via the same editingInfo marker, into
# data/raw/external/ - for review and the #771 spike only, until each
# entry's licence records the org's answer (CONTRIBUTING.md, "A note on data
# and licences"). load_raw.py's kind filter keeps them out of the warehouse
# the same way, until #100's staging models take them deliberately.
EXTERNAL_ARCGIS_LAYER = "external_arcgis_layer"

# A dataset republished on a fixed weekly cadence, where the WEEK is part of
# the claim rather than metadata about it. The U.S. Drought Monitor is the
# first (#720): NDMC publishes a dated file every Thursday describing the
# Tuesday-to-Monday week, and `fetch_drought.py` takes the dated file
# specifically because the polygons carry no date inside them - so an
# artifact built from `usdm_current.json` could only be stamped with the
# bake's own clock, which is the failure export_atc_updates.py records at
# length for the ATC file.
#
# Its own kind rather than ARCGIS_FEATURE_LAYER (it is not one) or
# GEOFABRIK_EXTRACT (that kind's whole point is that "changed" is always true
# and freshness is therefore meaningless): a weekly source is exactly the
# case where freshness IS meaningful and checkable, because a release either
# landed this week or it did not. `fetch_all.py` skips it like everything
# not ArcGIS.
WEEKLY_POLYGONS = "weekly_polygons"

# A guide an organization publishes as web pages for people to read - NYNJTC's
# Long Path End-to-End Section Guide first, forty pages the registered
# `nynjtc_long_path` layer links to from its own `GuideURL` field. The only
# place NYNJTC publishes a waypoint (POI_COVERAGE_SURVEY.md section 6 found
# none on their ArcGIS org), and it publishes them as prose: "4.30  A sign
# marks the way to a spring, a dependable source of water". Fetched by
# fetch_nynjtc_long_path_guide.py into data/raw/nynjtc_long_path_guide/ and
# parsed by lib/nynjtc_long_path_guide.py into facts - a mile, a type, a
# position - which export_nearby_poi.py reads behind the entry's own
# `reaches_hikers` gate. Its own kind rather than PUBLISHED_NOTICES (those
# are reviewed by hand into a file in git and never fetched on a schedule)
# or CLUB_PDF (a document, with a PDF's text layer to parse): this is HTML on
# a schedule, and fetch_all.py skips it like everything not ArcGIS.
GUIDE_PAGES = "guide_pages"

# Day hikes an organization writes up for people to walk - NYNJTC's, through
# the Hike Finder export (#1427, and #1290 before it): a name, a summary, a
# turn-by-turn description, the publisher's own categorisation and tags, and
# the parking as a pin. Fetched by fetch_hikefinder.py into
# data/raw/hikefinder.json and parsed by lib/hikefinder.py into facts. THE
# ROUTE ARRIVES TWO WAYS and the difference is carried all the way to the
# card: 113 of the 385 publish a GPX track the writer DREW (#1451 - they
# are drawn in gpx.studio, not recorded on the ground), and 272
# publish no line at all, so route_hikefinder.py forms one from the
# description over the junction graph and grades it. export_suggested_hikes.py
# ships what passes, behind the entry's own `reaches_hikers` gate. Its own kind rather than GUIDE_PAGES because the
# thing a reader gets is a hike, not a waypoint, and the exporter that reads
# it is a different one; and rather than PUBLISHED_NOTICES because these are
# fetched on a schedule, not reviewed by hand into git. fetch_all.py skips it
# like everything not ArcGIS.
PUBLISHED_HIKES = "published_hikes"

# A dataset on a Socrata open-data portal, fetched as GeoJSON - New York
# City's own walking paths first (#1432): NYC Parks' trails across 73 parks,
# and the off-street greenway subset of NYC DOT's bike network.
#
# ITS OWN KIND BECAUSE THE TRANSPORT IS DIFFERENT, NOT BECAUSE THE DATA IS.
# These carry trail lines exactly as EXTERNAL_ARCGIS_LAYER's occupants do,
# and `network_line_sources()` picks both up off the same blaze marker. What
# differs is everything about getting the bytes: SoQL `$where` rather than an
# ArcGIS `where`, `$limit`/`$offset` rather than `resultOffset`, and
# `rowsUpdatedAt` in epoch SECONDS rather than `editingInfo.dataLastEditDate`
# in milliseconds. lib/socrata.py owns that half.
#
# WHY NOT JUST REGISTER NYC's ARCGIS MIRROR. Because it is dead. NYC DCP's
# copy of DOT's bike network reports dataLastEditDate 2017-03-08, carries
# 13,953 rows against the portal's 29,695, and has no `grnwy` column at all
# (all measured live 2026-09-15) - so the ArcGIS route cannot express the
# filter that keeps on-street bike lanes from being drawn as walking paths.
# NYC Parks has no ArcGIS org publishing trails at all. The portal is the
# publication of record, so the portal is what this fetches.
#
# fetch_external_layers.py fetches these alongside the ArcGIS ones - the same
# script, because the boundary that mattered for that script was "another
# organization's layer, outside the A.T. build", and that is what these are.
# fetch_all.py skips it like everything not ArcGIS.
SOCRATA_GEOJSON_LAYER = "socrata_geojson_layer"

KNOWN_KINDS = frozenset(
    {
        ARCGIS_FEATURE_LAYER,
        PUBLISHED_NOTICES,
        CLUB_PDF,
        GEOFABRIK_EXTRACT,
        WATCHED_ONLY,
        WEEKLY_POLYGONS,
        EXTERNAL_ARCGIS_LAYER,
        GUIDE_PAGES,
        PUBLISHED_HIKES,
        SOCRATA_GEOJSON_LAYER,
    }
)


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


def is_external_arcgis_layer(entry: dict) -> bool:
    """Whether this entry is another organization's layer, outside the A.T.
    build - the predicate `is_arcgis_feature_layer` has always had and this
    kind lacked. Added for export_trails.py, which needs to ask the negative
    of it: a source carrying blaze metadata belongs to the A.T. line export
    only if it is not one of these (see that module's load_line_sources)."""
    return source_kind(entry) == EXTERNAL_ARCGIS_LAYER


def arcgis_sources(registry: dict) -> list[dict]:
    """The entries `fetch_all.py` may fetch, in registry order."""
    return [entry for entry in registry.get("sources", []) if is_arcgis_feature_layer(entry)]


def club_pdf_sources(registry: dict) -> list[dict]:
    """The entries `fetch_club_pdfs.py` may fetch, in registry order."""
    return [entry for entry in registry.get("sources", []) if source_kind(entry) == CLUB_PDF]


def external_arcgis_sources(registry: dict) -> list[dict]:
    """The ArcGIS half of what `fetch_external_layers.py` fetches, in registry order."""
    return [entry for entry in registry.get("sources", []) if is_external_arcgis_layer(entry)]


def is_socrata_layer(entry: dict) -> bool:
    return source_kind(entry) == SOCRATA_GEOJSON_LAYER


def socrata_sources(registry: dict) -> list[dict]:
    """The Socrata half of what `fetch_external_layers.py` fetches, in registry order."""
    return [entry for entry in registry.get("sources", []) if is_socrata_layer(entry)]


def is_external_source(entry: dict) -> bool:
    """Whether this entry is another organization's layer, outside the A.T. build.

    THE NEGATIVE IS THE LOAD-BEARING USE (#1432). export_trails.py asks this
    to keep somebody else's layers OUT of the A.T. corridor export, and that
    question is about whose data it is, never about what it is served from -
    so a second external transport must answer it the same way the first
    does. Asked as `not is_external_arcgis_layer(...)`, the Socrata entries
    would have read as A.T. sources and been clipped into the corridor
    artifact, which is the silent-partial-keep failure export_trails.py's own
    docstring warns about, arriving through the door that docstring did not
    know existed yet.
    """
    return is_external_arcgis_layer(entry) or is_socrata_layer(entry)


def external_sources(registry: dict) -> list[dict]:
    """Every other organization's layer, whatever it is published on (#1432).

    ONE LIST, IN REGISTRY ORDER, because the thing these entries have in
    common is who they belong to and not how the bytes arrive: they are
    somebody else's data, outside the A.T. build, fetched by
    fetch_external_layers.py into data/raw/external/ and gated on their own
    `reaches_hikers`. Kind decides which fetcher gets called and nothing
    else, which is why this is the function the exports and the completeness
    gate ask - a third transport later should not have to be added to five
    call sites to be counted.
    """
    return [entry for entry in registry.get("sources", []) if is_external_source(entry)]


def guide_page_sources(registry: dict) -> list[dict]:
    """The entries `fetch_nynjtc_long_path_guide.py` may fetch, in registry order."""
    return [entry for entry in registry.get("sources", []) if source_kind(entry) == GUIDE_PAGES]


def find_source(registry: dict, key: str) -> dict | None:
    for entry in registry.get("sources", []):
        if entry.get("key") == key:
            return entry
    return None


# --- Which registered source a published POI came from (#876) -------------
#
# `lib/poi_schema.py` mints every POI id as `<source>:<source_feature_id>`,
# and `<source>` is `export_poi.py`'s name for the layer - `atc_shelters` -
# rather than the registry's key for it - `shelters`. The two spellings have
# never had to meet, because nothing downstream of the export needed to know
# which organization a waypoint came from.
#
# features/FIELD_NOTES.md §4 needs exactly that: a corroborated dispute is a
# correction that belongs upstream, in ATC's own data, and routing it there
# starts by asking whose data the disputed pin is. So the join gets written
# down once, here, in the module that already reads the registry.
#
# Spelled out rather than derived from `export_poi.py`'s `DIRECT_SOURCES`,
# for the reason that tuple gives for itself: a layer that turns out to
# differ should differ in a table, not somewhere clever. The drift risk that
# buys is real and is covered - `tests/test_lib_source_registry.py` asserts
# every source name the export mints appears either here or in the set below.
POI_SOURCE_KEYS = {
    "atc_shelters": "shelters",
    "atc_campsites": "campsites",
    "atc_viewpoints": "viewpoints",
    "atc_parking": "parking",
    "atc_privies": "privies",
    "atc_communities": "communities",
    "osm_water": "osm_water",
}

#: POI sources no registry entry covers, named rather than omitted.
#:
#: A dispute on one of these has nowhere to be filed, and that is worth
#: saying out loud each time rather than dropping the dispute quietly. Two
#: different reasons sit in this set:
#:
#:   - `opentrail_at` has no entry because its redistribution terms are the
#:     open question in #98, so it was never registered.
#:   - `atc_csi`, `nhd_crossing` and `nhd_stream` are DERIVED points rather
#:     than upstream features - a CSI distance turned into a place, and two
#:     geometry derivations - so there is no upstream row to correct even
#:     when a steward exists for the layer they were derived from. A hiker
#:     saying "there is no water here" about a derived crossing is telling
#:     this project its derivation is wrong, which is an issue here rather
#:     than an ask of USGS.
UNREGISTERED_POI_SOURCES = frozenset({"atc_csi", "opentrail_at", "nhd_crossing", "nhd_stream"})


def poi_source_entry(registry: dict, poi_source: str) -> dict | None:
    """The registry entry a published POI's id namespace came from.

    None for a source no entry covers - which is an answer rather than a
    failure, and the caller is expected to say so rather than skip it.
    """
    key = POI_SOURCE_KEYS.get(poi_source)
    return find_source(registry, key) if key else None


def poi_source_steward(registry: dict, poi_source: str) -> str | None:
    """Who to tell about that source, or None when nobody is named.

    Falls back to `provider` where `steward` is absent, because the twelve
    ATC entries still carry only the older field (SOURCE_REGISTRY.md's "Do
    this part first" is the change that ends that, and is not this one).
    Reading both means the routing works on the registry as it is rather
    than on the registry as that section wishes it were.
    """
    entry = poi_source_entry(registry, poi_source)
    if entry is None:
        return None
    return entry.get("steward") or entry.get("provider") or None
