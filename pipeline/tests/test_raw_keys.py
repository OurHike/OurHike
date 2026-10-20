"""lib/raw_keys.py: the private raw store's own key rule (INCREMENTAL.md, "The private bucket needs its own key validator").

The rule is the opposite trade to lib/r2_keys.py's: a raw key is not a URL
anybody fetches, so `latest`, upper case, deep paths and any extension pass,
and what is refused is a key that could escape its prefix or be read as
another key.
"""

import pytest

from lib import r2_keys
from lib.raw_keys import MAX_KEY_BYTES, raw_key_problems, validate_raw_key


@pytest.mark.parametrize(
    "key",
    ["osm/georgia-latest.osm.pbf", "nhd_tmp/NHD_H_0204_HU4_GPKG.zip", "a/b/c/d/e/f/g.parquet", "index.json"],
)
def test_names_the_public_bucket_refuses_are_legal_raw_keys(key):
    assert raw_key_problems(key) == []


def test_geofabriks_own_file_name_is_a_raw_key_and_never_a_public_one():
    """`latest` is banned in the public bucket because a permanent URL must not call itself current; current/ is for that."""
    assert validate_raw_key("osm/maine-latest.osm.pbf") == "osm/maine-latest.osm.pbf"
    assert r2_keys.validate_key("osm/maine-latest.osm.pbf") is not None


@pytest.mark.parametrize(
    "key",
    [
        "",
        "/osm/a.pbf",
        "osm/",
        "osm//a.pbf",
        "../a.pbf",
        "osm/./a.pbf",
        "osm/a b.pbf",
        "osm\\a.pbf",
        "osm/a?.pbf",
        "x" * (MAX_KEY_BYTES + 1),
    ],
)
def test_a_key_that_could_leave_its_prefix_or_read_as_another_is_refused(key):
    assert raw_key_problems(key)
    with pytest.raises(ValueError, match="not a raw-store key"):
        validate_raw_key(key)
