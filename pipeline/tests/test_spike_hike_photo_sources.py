"""Tests for spike_hike_photo_sources.py - the "can a geo-searchable photo
corpus illustrate the 385 NYNJTC hikes" measurement (#1450, strategy E).

All HTTP is mocked (TESTING.md: real network calls never fire in tests) and no
Mapillary token is ever needed, since the token is read from the environment
and these tests inject their own.

Two tests here are load-bearing, and both are about a count that reads like
coverage and is not:

  - `summarise` must count LOCATIONS, not images. Sterling Forest returns 73
    images from 9 spots on one day from one contributor. An image count says
    "good coverage"; the location count says "nine places", and only the
    second bears on whether 385 hikes can have pictures.
  - `_get` must never turn a failed request into an empty result. This spike
    exists to find out whether a corpus is empty, so a bug that reports a dead
    endpoint as "no images" would manufacture exactly the finding it is
    measuring - confidently, and with no way to tell from the output.
"""

import json

import pytest
import requests

import spike_hike_photo_sources as spike


def _no_sleep(monkeypatch):
    monkeypatch.setattr(spike.time, "sleep", lambda _s: None)


def _session():
    return requests.Session()


def _image(lat=41.2, lon=-74.1, licence="CC-BY-SA-4.0", image_id="1", producer="someone", measured=True):
    return spike.Image(
        source="panoramax",
        image_id=image_id,
        lat=lat,
        lon=lon,
        captured="2024-06-02T10:00:00+00:00",
        licence=licence,
        licence_measured=measured,
        producer=producer,
        thumbnail=None,
    )


# A Panoramax feature in the shape the live API really returns, read off
# api.panoramax.xyz on 2026-09-15. The coordinates are in `bbox` (a point's
# box is degenerate) rather than in `geometry`, which is the detail a parser
# written from the STAC spec alone would get wrong.
REAL_PANORAMAX_FEATURE = {
    "id": "e2c2edd1-e10b-489e-a265-11eadc289f7f",
    "bbox": [-74.1487, 41.31861, -74.1487, 41.31861],
    "type": "Feature",
    "properties": {
        "datetime": "2024-08-09T16:00:00+00:00",
        "license": "CC-BY-SA-4.0",
        "geovisio:producer": "p4n-pics",
        "geovisio:thumbnail": "https://example.test/thumb.jpg",
    },
}


# --- the licence gate is imported, not restated --------------------------------


@pytest.mark.parametrize(
    ("licence", "shippable"),
    [
        ("CC-BY-SA-4.0", True),  # what Panoramax returns, upper-cased
        ("cc-by-sa-4.0", True),
        ("CC-BY-4.0", True),
        ("cc0", True),
        ("cc-by-sa-2.0", False),  # POI_PHOTOS.md rejects the pre-4.0 suite
        ("", False),
    ],
)
def test_shippable_defers_to_the_policy_the_commons_fetch_uses(licence, shippable):
    """`lib.commons.license_allows_reuse` is the one copy of this policy. A
    second copy here would drift from it, and the drift would show up as a
    coverage number nobody could reproduce."""
    assert _image(licence=licence).shippable is shippable


def test_etalab_is_rejected_for_being_unknown_rather_than_for_being_closed():
    """France's Open Licence 2.0 is a genuinely open licence and Panoramax
    serves real images under it - two of the NYNJTC-area images measured
    2026-09-15 (Black Rock Forest, Storm King) carry it. The gate rejects it
    because it has never met the id, not because the terms fail.

    This test pins that as a known, deliberate gap rather than a silent one:
    if somebody teaches lib/commons.py the licence, this test fails and the
    coverage numbers in the module docstring move.
    """
    assert _image(licence="etalab-2.0").shippable is False


# --- summarise: locations are the number that matters --------------------------


def test_many_images_at_one_spot_count_as_one_place():
    """The Sterling Forest shape - consecutive frames of a short walk. 73
    images reads like coverage; 9 spots is what it is worth."""
    images = [_image(lat=41.19845, lon=-74.26156, image_id=str(n)) for n in range(73)]

    stats = spike.summarise(images)

    assert stats["images"] == 73
    assert stats["locations"] == 1


def test_locations_round_to_about_eleven_metres():
    """4dp is inside one stride, so two frames that round together were taken
    from the same spot by any reading a hiker would recognise."""
    together = spike.summarise([_image(lat=41.20000, lon=-74.10000), _image(lat=41.200004, lon=-74.100004)])
    apart = spike.summarise([_image(lat=41.20000, lon=-74.10000), _image(lat=41.20100, lon=-74.10100)])

    assert together["locations"] == 1
    assert apart["locations"] == 2


def test_shippable_locations_are_counted_separately_from_shippable_images():
    """A park can hold plenty of licensed images and still offer one place to
    photograph, which is the whole Sterling Forest lesson applied to the
    column a reader is most likely to quote."""
    images = [_image(lat=41.2, lon=-74.1, image_id=str(n)) for n in range(5)]
    images.append(_image(lat=41.9, lon=-74.4, image_id="x", licence="etalab-2.0"))

    stats = spike.summarise(images)

    assert stats["images"] == 6
    assert stats["locations"] == 2
    assert stats["shippable_images"] == 5
    assert stats["shippable_locations"] == 1


def test_contributors_are_counted_so_one_hobbyist_does_not_read_as_a_corpus():
    images = [_image(image_id=str(n), producer="Zirkon") for n in range(20)]

    assert spike.summarise(images)["producers"] == 1


def test_an_empty_area_summarises_to_zeroes_rather_than_failing():
    assert spike.summarise([]) == {
        "images": 0,
        "locations": 0,
        "shippable_images": 0,
        "shippable_locations": 0,
        "producers": 0,
        "subjects": 0,
        "licences": {},
    }


# --- parsing the two APIs ------------------------------------------------------


def test_panoramax_coordinates_are_read_from_the_bbox_the_api_really_sends(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(spike.PANORAMAX_API, json={"features": [REAL_PANORAMAX_FEATURE]})

    images = spike.panoramax_in_box(_session(), (-74.2, 41.15, -73.95, 41.35))

    assert len(images) == 1
    assert images[0].lat == pytest.approx(41.31861)
    assert images[0].lon == pytest.approx(-74.1487)
    assert images[0].licence == "CC-BY-SA-4.0"
    assert images[0].licence_measured is True
    assert images[0].producer == "p4n-pics"


def test_a_panoramax_feature_without_coordinates_is_dropped_rather_than_placed_at_null_island(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(spike.PANORAMAX_API, json={"features": [{"id": "x", "properties": {}, "bbox": []}]})

    assert spike.panoramax_in_box(_session(), (-74.2, 41.15, -73.95, 41.35)) == []


def test_mapillary_licence_is_flagged_as_asserted_rather_than_measured(monkeypatch, requests_mock):
    """The images endpoint serves no per-image licence, so the CC BY-SA 4.0
    comes from Mapillary's uploader terms. That is a weaker claim than
    Panoramax's per-image field and the record has to say which it is."""
    _no_sleep(monkeypatch)
    requests_mock.get(
        spike.MAPILLARY_API,
        json={"data": [{"id": "77", "computed_geometry": {"coordinates": [-74.1, 41.2]}, "captured_at": 1717000000}]},
    )

    images = spike.mapillary_in_box(_session(), (-74.2, 41.15, -73.95, 41.35), "token")

    assert len(images) == 1
    assert images[0].licence == spike.MAPILLARY_ASSUMED_LICENCE
    assert images[0].licence_measured is False


def test_the_mapillary_token_travels_as_a_header_rather_than_in_the_query(monkeypatch, requests_mock):
    """A token in the query string lands in every proxy and server log
    between here and Mapillary."""
    _no_sleep(monkeypatch)
    requests_mock.get(spike.MAPILLARY_API, json={"data": []})

    spike.mapillary_in_box(_session(), (-74.2, 41.15, -73.95, 41.35), "secret-token")

    request = requests_mock.request_history[0]
    assert request.headers["Authorization"] == "OAuth secret-token"
    assert "secret-token" not in request.url


# --- a failed request must never read as an empty corpus -----------------------


def test_a_transient_failure_is_retried(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(spike.PANORAMAX_API, [{"status_code": 503}, {"json": {"features": [REAL_PANORAMAX_FEATURE]}}])

    assert len(spike.panoramax_in_box(_session(), (-74.2, 41.15, -73.95, 41.35))) == 1


def test_a_dead_endpoint_raises_rather_than_reporting_no_images(monkeypatch, requests_mock):
    """THE test of this module. The spike's whole output is a count of how
    empty a corpus is, so a request failure that returned [] would be
    indistinguishable from the finding - and would always agree with it."""
    _no_sleep(monkeypatch)
    requests_mock.get(spike.PANORAMAX_API, status_code=404)

    with pytest.raises(requests.exceptions.HTTPError):
        spike.panoramax_in_box(_session(), (-74.2, 41.15, -73.95, 41.35))


def test_unparseable_json_raises_rather_than_reporting_no_images(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(spike.PANORAMAX_API, text="<html>a proxy error page</html>")

    with pytest.raises(json.JSONDecodeError):
        spike.panoramax_in_box(_session(), (-74.2, 41.15, -73.95, 41.35))


# --- geometry ------------------------------------------------------------------


def test_the_box_is_wider_in_longitude_than_latitude_at_these_latitudes():
    """A box built with the same degree delta on both axes would be ~25% short
    in longitude at 41 N, which would quietly shrink every search."""
    lon_min, lat_min, lon_max, lat_max = spike.box_around(41.2, -74.1, 250.0)

    assert (lon_max - lon_min) > (lat_max - lat_min)
    assert spike.metres_between((41.2, lon_min), (41.2, lon_max)) == pytest.approx(500, rel=0.02)
    assert spike.metres_between((lat_min, -74.1), (lat_max, -74.1)) == pytest.approx(500, rel=0.02)


class _Point:
    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon


def test_a_track_is_sampled_no_more_finely_than_asked():
    points = [_Point(41.0 + n * 0.0001, -74.0) for n in range(200)]  # ~11 m apart

    sampled = spike.sample_track(points, 400.0)

    assert len(sampled) < len(points)
    for a, b in zip(sampled, sampled[1:-1]):
        assert spike.metres_between(a, b) >= 399


def test_both_ends_of_a_track_are_always_asked_about():
    """A track shorter than one sample still has two ends, and a walk whose
    far end is the photogenic part is the common case."""
    points = [_Point(41.0, -74.0), _Point(41.0005, -74.0)]  # ~55 m, under one sample

    sampled = spike.sample_track(points, 400.0)

    assert sampled[0] == (41.0, -74.0)
    assert sampled[-1] == (41.0005, -74.0)


def test_an_empty_track_samples_to_nothing_rather_than_raising():
    assert spike.sample_track([], 400.0) == []


# --- the run ------------------------------------------------------------------


def test_a_missing_cache_points_at_the_mode_that_needs_no_cache(monkeypatch, tmp_path, capsys):
    """The export went behind a site password on 2026-09-15 (#1468), so "no
    cache" is the ordinary state in a sandbox rather than a broken checkout.
    Saying only "missing" would strand a reader who has a usable measurement
    available one flag away."""
    monkeypatch.setattr(spike, "CACHE_PATH", tmp_path / "hikefinder.json")

    assert spike.report_per_hike(_session(), None, None, None) == 1

    output = capsys.readouterr().out
    assert "--regional" in output
    assert "HIKEFINDER_PASSWORD" in output


def test_an_empty_cache_is_refused_rather_than_reported_as_zero_coverage(monkeypatch, tmp_path, capsys):
    cache = tmp_path / "hikefinder.json"
    cache.write_text(json.dumps({"hikes": {}}), encoding="utf-8")
    monkeypatch.setattr(spike, "CACHE_PATH", cache)

    assert spike.report_per_hike(_session(), None, None, None) == 1
    assert "no hikes" in capsys.readouterr().out


def test_an_unknown_flag_is_rejected_rather_than_silently_ignored():
    with pytest.raises(SystemExit) as excinfo:
        spike.run(["--regionl"])

    assert excinfo.value.code == 2


def test_an_absent_mapillary_token_is_announced_rather_than_looking_like_an_empty_source(monkeypatch, capsys):
    """Mapillary answers 500 without a token, so an unset variable and a dead
    endpoint produce the same silence. The run has to say which it had."""
    monkeypatch.delenv(spike.MAPILLARY_TOKEN_ENV, raising=False)
    monkeypatch.setattr(spike, "report_regional", lambda *_a, **_k: 0)

    spike.run(["--regional"])

    output = capsys.readouterr().out
    assert "PANORAMAX AND INATURALIST ONLY" in output
    assert spike.MAPILLARY_TOKEN_ENV in output


def test_a_present_mapillary_token_is_not_printed(monkeypatch, capsys):
    monkeypatch.setenv(spike.MAPILLARY_TOKEN_ENV, "secret-token")
    monkeypatch.setattr(spike, "report_regional", lambda *_a, **_k: 0)

    spike.run(["--regional"])

    assert "secret-token" not in capsys.readouterr().out


# --- iNaturalist: the source with all the coverage and the wrong subject -------


# An observation in the shape the live API really returns, read off
# api.inaturalist.org on 2026-09-15. Note `license_code` carries NO VERSION,
# which is the whole point of the tests below it, and that the coordinates live
# in `geojson` rather than in a `bbox` the way Panoramax's do.
REAL_INATURALIST_OBSERVATION = {
    "geojson": {"coordinates": [-74.05, 41.25], "type": "Point"},
    "observed_on": "2024-05-18",
    "quality_grade": "research",
    "user": {"login": "somebody"},
    "taxon": {"name": "Chimaphila maculata", "rank": "species"},
    "photos": [
        {
            "id": "723893498",
            "license_code": "cc-by",
            "attribution": "(c) Josh Ebbin, some rights reserved (CC BY)",
            "url": "https://inaturalist-open-data.s3.amazonaws.com/photos/723893498/square.jpg",
        }
    ],
}


def test_inaturalist_licences_arrive_without_a_version_and_are_therefore_rejected(monkeypatch, requests_mock):
    """THE licence finding, and the same trap spike_flickr_group.py documented
    for Flickr in a different field. iNaturalist's API says "cc-by" and its
    attribution string says "(CC BY)" - neither states 4.0, and lib/commons.py
    will not assume a version it cannot read.

    If iNaturalist ever starts serving a version, this test fails, and that is
    a real finding rather than a broken test: the source becomes shippable on
    licence grounds (though not, on this measurement, on subject grounds).
    """
    _no_sleep(monkeypatch)
    requests_mock.get(spike.INATURALIST_API, json={"results": [REAL_INATURALIST_OBSERVATION]})

    images = spike.inaturalist_in_box(_session(), (-74.2, 41.15, -73.95, 41.35))

    assert len(images) == 1
    assert images[0].licence == "cc-by"
    assert images[0].shippable is False


def test_the_versionless_licence_is_not_quietly_repaired_into_a_versioned_one(monkeypatch, requests_mock):
    """A one-line "cc-by means cc-by-4.0" mapping here would make the whole
    corpus pass, and would be an assertion about iNaturalist's terms wearing
    the costume of a measurement. The spike refuses to make it; a maintainer
    who wants to make it should make it somewhere a reader can see it."""
    _no_sleep(monkeypatch)
    requests_mock.get(spike.INATURALIST_API, json={"results": [REAL_INATURALIST_OBSERVATION]})

    image = spike.inaturalist_in_box(_session(), (-74.2, 41.15, -73.95, 41.35))[0]

    assert "4.0" not in image.licence
    assert image.licence_measured is True


def test_the_taxon_travels_as_the_subject_because_it_is_the_finding(monkeypatch, requests_mock):
    """No other source says what its photographs depict. iNaturalist does, and
    what it says is "this is a plant" - which is why the field exists."""
    _no_sleep(monkeypatch)
    requests_mock.get(spike.INATURALIST_API, json={"results": [REAL_INATURALIST_OBSERVATION]})

    assert spike.inaturalist_in_box(_session(), (-74.2, 41.15, -73.95, 41.35))[0].subject == "Chimaphila maculata"


def test_a_square_thumbnail_is_asked_for_at_a_size_a_person_can_judge(monkeypatch, requests_mock):
    """The API hands back a 75px `square` crop. Nobody can tell a trail from a
    leaf at 75px, and the adversarial look is the whole method here."""
    _no_sleep(monkeypatch)
    requests_mock.get(spike.INATURALIST_API, json={"results": [REAL_INATURALIST_OBSERVATION]})

    thumbnail = spike.inaturalist_in_box(_session(), (-74.2, 41.15, -73.95, 41.35))[0].thumbnail

    assert thumbnail.endswith("/medium.jpg")
    assert "/square." not in thumbnail


def test_an_observation_with_no_photo_is_skipped(monkeypatch, requests_mock):
    """Most of iNaturalist is observations; this spike is about photographs."""
    _no_sleep(monkeypatch)
    requests_mock.get(spike.INATURALIST_API, json={"results": [{**REAL_INATURALIST_OBSERVATION, "photos": []}]})

    assert spike.inaturalist_in_box(_session(), (-74.2, 41.15, -73.95, 41.35)) == []


def test_only_open_licences_are_asked_for(monkeypatch, requests_mock):
    """Fetching the all-rights-reserved majority to discard it locally would
    be a rude way to get the same number."""
    _no_sleep(monkeypatch)
    requests_mock.get(spike.INATURALIST_API, json={"results": []})

    spike.inaturalist_in_box(_session(), (-74.2, 41.15, -73.95, 41.35))

    asked = requests_mock.request_history[0].qs["photo_license"][0]
    assert set(asked.split(",")) == set(spike.INATURALIST_OPEN_LICENCES)


def test_counting_a_box_does_not_page_through_it(monkeypatch, requests_mock):
    """iNaturalist boxes here run to five figures. `per_page=0` answers the
    coverage question in one request and a few bytes."""
    _no_sleep(monkeypatch)
    requests_mock.get(spike.INATURALIST_API, json={"total_results": 4219, "results": []})

    assert spike.inaturalist_count(_session(), (-74.2, 41.15, -73.95, 41.35)) == 4219
    assert requests_mock.request_history[0].qs["per_page"] == ["0"]


def test_subjects_are_counted_so_a_park_full_of_taxa_reads_as_what_it_is():
    """A high distinct-taxa count is the signal that a box's coverage is
    species observations rather than places."""
    images = [
        spike.Image(
            source="inaturalist",
            image_id=str(n),
            lat=41.2,
            lon=-74.1,
            captured=None,
            licence="cc-by",
            licence_measured=True,
            producer="watcher",
            thumbnail=None,
            subject=f"Taxon {n}",
        )
        for n in range(7)
    ]

    assert spike.summarise(images)["subjects"] == 7


def test_a_source_that_dies_does_not_take_the_others_with_it(monkeypatch, requests_mock, capsys):
    """One dead endpoint must cost its own column, not the run - but it must
    say so, because a silent zero is indistinguishable from the finding."""
    _no_sleep(monkeypatch)
    requests_mock.get(spike.PANORAMAX_API, status_code=500)
    requests_mock.get(spike.INATURALIST_API, json={"results": [REAL_INATURALIST_OBSERVATION]})

    found = spike.gather(_session(), (-74.2, 41.15, -73.95, 41.35), None, 100)

    assert [image.source for image in found] == ["inaturalist"]
    assert "panoramax" in capsys.readouterr().err
