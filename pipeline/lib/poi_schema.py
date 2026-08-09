"""Unified POI schema (ROADMAP.md Phase 1 "Unified POI schema"): one shape
for every point-of-interest source instead of source-specific ones - ATC
shelters/campsites, ATC Communities (a resupply proxy), opentrail.org's
water/resupply tags, and eventually NHD stream crossings (see ROADMAP.md's
still-exploratory NHD investigation).

Pure module - no I/O, no DuckDB, no network. export_poi.py is what wires
this up against real raw GeoJSON and the corridor clip.
"""

POI_TYPES = ("shelter", "campsite", "water", "resupply", "crossing")

# Two tiers is enough for the one real distinction this schema needs to make
# today: ATC's Communities layer (a town being an "official A.T. Community"
# is a proxy for resupply, not verified resupply-point data) vs. sources that
# directly tag the point itself (opentrail.org's resupply/water tags, ATC's
# own shelter/campsite facility data). CONFIDENCE_RANK gives callers/tests an
# explicit ordering rather than relying on string comparison.
CONFIDENCE_HIGH = "high"
CONFIDENCE_LOW = "low"
CONFIDENCE_RANK = {CONFIDENCE_LOW: 1, CONFIDENCE_HIGH: 2}

# The two files export_poi.py writes per poi_type.
POI_OUTPUT_KINDS = ("geojson", "fgb")


def poi_output_name(poi_type: str, kind: str = "geojson") -> str:
    """What one poi_type's export is called on disk.

    A naming convention rather than I/O, so it belongs in the pure module -
    and it needs a single home because the two ends spelled it separately
    once and disagreed. export_poi.py wrote `shelter.geojson`; export_spurs.py
    read `poi_shelter.geojson`, which is the *R2 key* publish.py builds when
    it flattens this directory into a bucket namespace. Both spellings are
    correct in their own place, which is exactly why neither end looked wrong.

    A missing POI file is a legal empty result (a partial export is a state
    this pipeline supports), so the disagreement raised nothing: 784 spurs
    published with a null destination and the run went green (#469). Reading
    the name from here means the next divergence is a failed import rather
    than a quiet zero.
    """
    if poi_type not in POI_TYPES:
        raise ValueError(f"Unknown poi_type {poi_type!r} - expected one of {POI_TYPES}")
    if kind not in POI_OUTPUT_KINDS:
        raise ValueError(f"Unknown output kind {kind!r} - expected one of {POI_OUTPUT_KINDS}")
    return f"{poi_type}.{kind}"


def unify_poi(feature: dict, poi_type: str, source: str, trail_id: str, field_map: dict) -> dict:
    """Map one raw GeoJSON Feature (from any source) into the unified POI
    dict export_poi.py writes out per poi_type.

    `field_map` carries everything source-specific - this function has no
    per-source branching (no "if source == 'atc_shelters'" inside it), so a
    new source or club only ever needs a new field_map plus a caller-side
    loop, never a change here. Keys:
      - "id_field" (required): key into feature["properties"] holding the
        source's own stable feature id (e.g. ATC's "GlobalID", opentrail.org's
        "dbid"). Falls back to the GeoJSON Feature's own top-level "id" if
        the property is missing there but present on the feature itself.
      - "name_field" (optional): key into feature["properties"] holding the
        display name. Omitted/absent -> name is None.
      - "confidence" (optional): either a literal CONFIDENCE_HIGH/
        CONFIDENCE_LOW value applied to every feature this call processes,
        or a callable `(properties: dict) -> str` for sources where
        confidence varies per feature. Defaults to CONFIDENCE_HIGH.

    id is deterministic: f"{source}:{source_feature_id}" - never a randomly
    generated UUID, since a future Report/Closure references this id and it
    has to stay stable across repeated pipeline runs on unchanged input.

    trail_id is entirely caller-supplied, never hardcoded to "AT" here -
    this project starts AT-only but the schema itself must not assume a
    single trail (value #7: inheritable to a future trail/club).
    """
    if poi_type not in POI_TYPES:
        raise ValueError(f"Unknown poi_type {poi_type!r} - expected one of {POI_TYPES}")

    geometry = feature.get("geometry") or {}
    if geometry.get("type") != "Point":
        raise ValueError(f"unify_poi only supports Point geometries, got {geometry.get('type')!r}")
    lon, lat = geometry["coordinates"][0], geometry["coordinates"][1]

    properties = feature.get("properties") or {}

    id_field = field_map["id_field"]
    source_feature_id = properties.get(id_field)
    if source_feature_id is None:
        source_feature_id = feature.get("id")
    if source_feature_id is None:
        raise ValueError(
            f"Feature has no usable id: field_map['id_field']={id_field!r} isn't in properties "
            f"and the feature has no top-level 'id' either - check the field_map for source {source!r}"
        )

    name_field = field_map.get("name_field")
    name = properties.get(name_field) if name_field else None

    confidence = field_map.get("confidence", CONFIDENCE_HIGH)
    if callable(confidence):
        confidence = confidence(properties)

    return {
        "id": f"{source}:{source_feature_id}",
        "poi_type": poi_type,
        "trail_id": trail_id,
        "source": source,
        "source_feature_id": source_feature_id,
        "name": name,
        "lat": lat,
        "lon": lon,
        "confidence": confidence,
    }
