import pytest

from discover_sources import extract_item_id, slugify


@pytest.mark.parametrize("title, expected", [
    ("A.T. Trail Club Sections", "trail_club_sections"),
    ("A.T. Centerline", "centerline"),
    ("A.T. Half Mile Points From Springer", "half_mile_points_from_springer"),
    ("Bridges", "bridges"),
    ("", ""),
])
def test_slugify(title, expected):
    assert slugify(title) == expected


@pytest.mark.parametrize("url_or_id, expected", [
    ("c218db84e3ec430db52249797f4cff43", "c218db84e3ec430db52249797f4cff43"),
    (
        "https://experience.arcgis.com/experience/c218db84e3ec430db52249797f4cff43",
        "c218db84e3ec430db52249797f4cff43",
    ),
    (
        "https://experience.arcgis.com/experience/c218db84e3ec430db52249797f4cff43?org=ATConservancy",
        "c218db84e3ec430db52249797f4cff43",
    ),
])
def test_extract_item_id(url_or_id, expected):
    assert extract_item_id(url_or_id) == expected
