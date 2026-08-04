"""A raw ArcGIS feature's stable identity, shared by every exporter.

One implementation on purpose. trails.geojson and spurs.json only join
because both sides build `{key}:{id}` from the same fallback chain - two
copies of "the same" chain drifted within a day of each other (one checked
truthiness instead of `is None` and fell back to OBJECTID instead of the
feature's own id), and the result was a valid-looking spurs.json in which
any feature off the happy path silently never joined. An id rule that two
artifacts must agree on gets one home.
"""

from __future__ import annotations


def resolve_feature_id(key: str, feature: dict, properties: dict, index: int) -> str | int:
    """A feature's stable identity - used for record ids in every published
    artifact and for any warning that names a feature.

    Checks the RESULTING VALUE at each fallback step, not just key
    presence: dict.get(key, default) only falls back when the key is
    ABSENT, so a raw feature carrying an explicit `"GlobalID": null` (a real
    shape some ArcGIS exports use) would return None directly instead of
    falling back to the feature's own id - and two such features would then
    collide on the literal id f"{key}:None". This mirrors lib/poi_schema.py's
    unify_poi(), which gets this right the same way for POI sources.

    If GlobalID and the feature's own top-level id are BOTH really absent,
    substitutes a synthetic id built from `index` (the feature's position in
    its source's feature list, so it's unique within that source) and warns
    loudly - the exporters' convention is a loud warning and carrying on,
    never raising and killing the whole batch over one bad feature (see
    export_trails.py's module docstring)."""
    feature_id = properties.get("GlobalID")
    if feature_id is None:
        feature_id = feature.get("id")
    if feature_id is None:
        feature_id = f"generated-{index}"
        print(
            f"WARNING: {key} feature at position {index} has no GlobalID and no top-level id - "
            f"substituting synthetic id {feature_id!r}"
        )
    return feature_id
