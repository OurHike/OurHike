"""Tests for spike_flickr_group.py - the "is a Flickr group pool shippable"
measurement. All HTTP is mocked (TESTING.md: real network calls never fire in
tests) and no API key is ever needed, since the key is read from the
environment and the tests inject their own.

The load-bearing test here is the licence mapping: Flickr's licence *names*
carry no version ("Attribution-ShareAlike License" is 2.0), so a measurement
that read the name would count the entire CC 2.0 suite as shippable and report
a source that does not exist.
"""

from datetime import date

import pytest

import spike_flickr_group as spike

API_URL = spike.API_URL


def _licence(lic_id, name, url=""):
    return {"id": lic_id, "name": name, "url": url}


# The catalogue Flickr really returns, checked against the live API 2026-08-08.
REAL_CATALOGUE = [
    _licence(0, "All Rights Reserved"),
    _licence(1, "Attribution-NonCommercial-ShareAlike License", "https://creativecommons.org/licenses/by-nc-sa/2.0/"),
    _licence(2, "Attribution-NonCommercial License", "https://creativecommons.org/licenses/by-nc/2.0/"),
    _licence(3, "Attribution-NonCommercial-NoDerivs License", "https://creativecommons.org/licenses/by-nc-nd/2.0/"),
    _licence(4, "Attribution License", "https://creativecommons.org/licenses/by/2.0/"),
    _licence(5, "Attribution-ShareAlike License", "https://creativecommons.org/licenses/by-sa/2.0/"),
    _licence(6, "Attribution-NoDerivs License", "https://creativecommons.org/licenses/by-nd/2.0/"),
    _licence(7, "No known copyright restrictions", "https://www.flickr.com/commons/usage/"),
    _licence(8, "United States Government Work", "http://www.usa.gov/copyright.shtml"),
    _licence(9, "Public Domain Dedication (CC0)", "https://creativecommons.org/publicdomain/zero/1.0/"),
    _licence(10, "Public Domain Mark", "https://creativecommons.org/publicdomain/mark/1.0/"),
]


def _catalogue_response(licences=None):
    return {"stat": "ok", "licenses": {"license": licences if licences is not None else REAL_CATALOGUE}}


def _pool_response(photos, page=1, pages=1):
    return {"stat": "ok", "photos": {"page": page, "pages": pages, "photo": photos}}


def _photo(photo_id="1", title="Shelter", license_id="0", datetaken="2025-06-01 10:00:00", lat=None):
    p = {"id": photo_id, "title": title, "license": license_id, "datetaken": datetaken, "ownername": "A Hiker"}
    if lat is not None:
        p["latitude"] = lat
        p["longitude"] = "-71.0"
    return p


def _no_sleep(monkeypatch):
    monkeypatch.setattr(spike.time, "sleep", lambda _s: None)


# --- commons_style_license_id: the version is the whole point ---


@pytest.mark.parametrize(
    ("name", "url", "expected"),
    [
        ("Attribution License", "https://creativecommons.org/licenses/by/2.0/", "cc-by-2.0"),
        ("Attribution-ShareAlike License", "https://creativecommons.org/licenses/by-sa/2.0/", "cc-by-sa-2.0"),
        ("Attribution License", "https://creativecommons.org/licenses/by/4.0/", "cc-by-4.0"),
        ("Attribution-NonCommercial License", "https://creativecommons.org/licenses/by-nc/2.0/", "cc-by-nc-2.0"),
        ("Public Domain Dedication (CC0)", "https://creativecommons.org/publicdomain/zero/1.0/", "cc0"),
        ("Public Domain Mark", "https://creativecommons.org/publicdomain/mark/1.0/", "pd"),
        ("United States Government Work", "http://www.usa.gov/copyright.shtml", "pd-usgov"),
        ("All Rights Reserved", "", ""),
    ],
)
def test_commons_style_license_id_reads_the_version_off_the_deed_url(name, url, expected):
    assert spike.commons_style_license_id(name, url) == expected


def test_flickr_commons_no_known_restrictions_is_not_treated_as_a_licence():
    """ "No known copyright restrictions" is an absence of evidence, not a
    grant. Shipping on it would be exactly the unlicensed-source problem
    CONTRIBUTING.md's licence note exists to prevent."""
    assert spike.commons_style_license_id("No known copyright restrictions", "https://www.flickr.com/commons/usage/") == ""


def test_the_licence_name_alone_would_have_been_ambiguous():
    """Flickr calls both CC BY 2.0 and CC BY 4.0 "Attribution License". Same
    name, opposite verdicts - which is why the URL is what gets parsed."""
    assert spike.commons_style_license_id("Attribution License", "https://creativecommons.org/licenses/by/2.0/") == "cc-by-2.0"
    assert spike.commons_style_license_id("Attribution License", "https://creativecommons.org/licenses/by/4.0/") == "cc-by-4.0"


# --- licence_catalogue: the policy is imported, not restated ---


def test_the_catalogue_judges_by_the_same_policy_the_commons_fetch_uses(monkeypatch, requests_mock):
    """Every CC licence Flickr offers today is 2.0, which POI_PHOTOS.md
    rejects wholesale - so the whole CC block must come back unshippable, and
    only CC0/PD may pass. If this test ever starts failing because Flickr
    added a 4.0 option, that is a real finding, not a broken test."""
    _no_sleep(monkeypatch)
    requests_mock.get(API_URL, json=_catalogue_response())

    catalogue = spike.licence_catalogue(requests_mock_session(), "key")

    assert catalogue["4"]["allowed"] is False  # CC BY 2.0
    assert catalogue["5"]["allowed"] is False  # CC BY-SA 2.0
    assert catalogue["1"]["allowed"] is False  # NC
    assert catalogue["7"]["allowed"] is False  # "no known restrictions"
    assert catalogue["9"]["allowed"] is True  # CC0
    assert catalogue["10"]["allowed"] is True  # PD mark


def requests_mock_session():
    import requests

    return requests.Session()


# --- group_photos: pagination ---


def test_every_page_of_the_pool_is_collected(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(
        API_URL,
        [
            {"json": _pool_response([_photo("1"), _photo("2")], page=1, pages=3)},
            {"json": _pool_response([_photo("3")], page=2, pages=3)},
            {"json": _pool_response([_photo("4")], page=3, pages=3)},
        ],
    )

    photos = spike.group_photos(requests_mock_session(), "908185@N20", "key")

    assert [p["id"] for p in photos] == ["1", "2", "3", "4"]


def test_a_flickr_level_error_raises_rather_than_counting_as_an_empty_pool(monkeypatch, requests_mock):
    """stat != "ok" comes back with HTTP 200. Treating it as an empty pool
    would report "no shippable photos" for a bad API key - the wrong answer,
    delivered confidently."""
    _no_sleep(monkeypatch)
    requests_mock.get(API_URL, json={"stat": "fail", "code": 100, "message": "Invalid API Key"})

    with pytest.raises(RuntimeError, match="Invalid API Key"):
        spike.group_photos(requests_mock_session(), "908185@N20", "bad-key")


def test_a_transient_5xx_is_retried(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(API_URL, [{"status_code": 503}, {"json": _pool_response([_photo("1")])}])

    photos = spike.group_photos(requests_mock_session(), "908185@N20", "key")

    assert len(photos) == 1


# --- report: the counts ---


def test_only_open_licensed_and_fresh_photos_clear_both_bars(capsys):
    catalogue = {
        "0": {"name": "All Rights Reserved", "url": "", "commons_id": "", "allowed": False},
        "5": {"name": "Attribution-ShareAlike License", "url": "", "commons_id": "cc-by-sa-2.0", "allowed": False},
        "9": {"name": "Public Domain Dedication (CC0)", "url": "", "commons_id": "cc0", "allowed": True},
    }
    photos = [
        _photo("1", "Reserved shelter", license_id="0", datetaken="2025-06-01 10:00:00"),
        _photo("2", "CC 2.0 shelter", license_id="5", datetaken="2025-06-01 10:00:00"),
        _photo("3", "CC0 but ancient", license_id="9", datetaken="2009-06-01 10:00:00"),
        _photo("4", "CC0 and fresh", license_id="9", datetaken="2025-06-01 10:00:00", lat="44.2"),
    ]

    result = spike.report(photos, catalogue, cutoff=date(2022, 8, 8))

    assert result == {"pool": 4, "open_licensed": 2, "fresh_and_open": 1, "geotagged": 1}
    assert "CC0 and fresh" in capsys.readouterr().out


def test_a_pool_with_nothing_shippable_says_so_rather_than_printing_an_empty_list(capsys):
    catalogue = {"0": {"name": "All Rights Reserved", "url": "", "commons_id": "", "allowed": False}}

    result = spike.report([_photo("1", license_id="0")], catalogue, cutoff=date(2022, 8, 8))

    assert result["fresh_and_open"] == 0
    assert "Nothing in this pool clears both bars." in capsys.readouterr().out


# --- the key is read from the environment, never stored ---


def test_a_missing_api_key_exits_with_instructions_rather_than_calling_the_api(monkeypatch, capsys):
    monkeypatch.delenv(spike.API_KEY_ENV_VAR, raising=False)

    with pytest.raises(SystemExit) as excinfo:
        spike.main()

    assert excinfo.value.code == 2
    assert spike.API_KEY_ENV_VAR in capsys.readouterr().out


def test_an_unknown_flag_is_rejected_rather_than_silently_ignored(monkeypatch):
    monkeypatch.setenv(spike.API_KEY_ENV_VAR, "key")

    with pytest.raises(SystemExit) as excinfo:
        spike.run(["--gruop", "123"])

    assert excinfo.value.code == 2


def test_the_group_flag_is_passed_through(monkeypatch):
    seen = {}
    monkeypatch.setattr(spike, "main", lambda group_id: seen.setdefault("group", group_id))

    spike.run(["--group", "12345@N01"])

    assert seen["group"] == "12345@N01"


def test_the_key_is_read_at_call_time_rather_than_captured_at_import(monkeypatch, requests_mock):
    """The key is a credential the repository must never acquire: read from
    os.environ when main() runs, passed down as an argument, held nowhere.
    Same posture as check_r2_connection.py's R2 credentials."""
    _no_sleep(monkeypatch)
    monkeypatch.setenv(spike.API_KEY_ENV_VAR, "key-set-after-import")
    requests_mock.get(API_URL, [{"json": _catalogue_response()}, {"json": _pool_response([_photo("1")])}])

    spike.main()

    assert requests_mock.request_history[0].qs["api_key"] == ["key-set-after-import"]
