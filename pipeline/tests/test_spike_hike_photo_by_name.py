"""Tests for spike_hike_photo_by_name.py - strategies A and B of #1450, "can a
hike be illustrated by looking its place up by name".

All HTTP is mocked (TESTING.md: real network calls never fire in tests).

Two groups here are load-bearing, and both pin a mistake #1450's own probe made
rather than a hypothetical one:

  - **Resolution is not a string search.** "Sterling Forest" resolves first to
    a hamlet, not to the state park the hikes are in. A spike that took hit one
    would score a village's photograph as the park's and report it as coverage.
    The coordinate check is what stops that, and `test_a_same_named_place_...`
    is the case that motivated the whole function.
  - **A rate limiter is not a finding.** Wikidata answers 429 under a loop and
    #1450 lost 14 of 18 requests to it. A run that counted a 429 as "this park
    has no photograph" would report the rate limiter's opinion as a fact about
    the world, and would do it silently.
"""

from datetime import date

import pytest
import requests

import spike_hike_photo_by_name as spike


def _no_sleep(monkeypatch):
    monkeypatch.setattr(spike.time, "sleep", lambda _s: None)


def _session():
    return requests.Session()


def _search(*qids):
    return {"search": [{"id": qid} for qid in qids]}


def _entity(qid, label, description="", lat=None, lon=None, image=None):
    claims = {}
    if lat is not None:
        claims["P625"] = [{"mainsnak": {"datavalue": {"value": {"latitude": lat, "longitude": lon}}}}]
    if image is not None:
        claims["P18"] = [{"mainsnak": {"datavalue": {"value": image}}}]
    return {
        "id": qid,
        "labels": {"en": {"value": label}},
        "descriptions": {"en": {"value": description}},
        "claims": claims,
    }


def _entities(*items):
    return {"entities": {item["id"]: item for item in items}}


def _imageinfo(licence="cc-by-sa-4.0", artist="A Photographer", taken="2025-06-01 10:00:00", thumb=True):
    extmetadata = {
        "License": {"value": licence},
        "LicenseShortName": {"value": licence.upper()},
        "Artist": {"value": artist},
        "DateTimeOriginal": {"value": taken},
    }
    info = {"mime": "image/jpeg", "extmetadata": extmetadata, "descriptionurl": "https://commons.example/File:X"}
    if thumb:
        info["thumburl"] = "https://upload.example/thumb/X.jpg"
    return {"query": {"pages": {"1": {"title": "File:X.jpg", "imageinfo": [info]}}}}


# --- the coordinate check, which is the whole point of resolve() ---------------


def test_a_same_named_place_next_door_is_refused(monkeypatch, requests_mock):
    """THE case. "Sterling Forest" really does resolve first to Q7611404, "human
    settlement in New York", rather than to the state park the hikes are in
    (checked against the live API 2026-09-15). Taking the top hit would have
    scored a hamlet's photograph as a park's."""
    _no_sleep(monkeypatch)
    requests_mock.get(
        spike.WIKIDATA_API,
        [
            {"json": _search("Q7611404")},
            {"json": _entities(_entity("Q7611404", "Sterling Forest", "human settlement", 43.9, -75.4))},
        ],
    )

    entity = spike.resolve(_session(), "Sterling Forest", 41.20, -74.29)

    assert entity.qid == "Q7611404"
    assert entity.accepted is False
    assert "km away" in entity.rejected_because


def test_a_nearby_entity_is_accepted_and_carries_its_drift(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(
        spike.WIKIDATA_API,
        [
            {"json": _search("Q3364063")},
            {"json": _entities(_entity("Q3364063", "Harriman State Park", "state park", 41.25, -74.08))},
        ],
    )

    entity = spike.resolve(_session(), "Harriman State Park", 41.25, -74.08)

    assert entity.accepted is True
    assert entity.drift_km == pytest.approx(0, abs=0.5)


def test_a_later_hit_wins_when_the_first_is_the_wrong_place(monkeypatch, requests_mock):
    """Relevance order is kept, but relevance is not correctness: the first
    candidate that proves itself on the coordinate is the answer, even when it
    is not the first the search returned."""
    _no_sleep(monkeypatch)
    requests_mock.get(
        spike.WIKIDATA_API,
        [
            {"json": _search("Q_village", "Q_park")},
            {
                "json": _entities(
                    _entity("Q_village", "Sterling Forest", "human settlement", 43.9, -75.4),
                    _entity("Q_park", "Sterling Forest State Park", "state park", 41.20, -74.29),
                )
            },
        ],
    )

    entity = spike.resolve(_session(), "Sterling Forest", 41.20, -74.29)

    assert entity.qid == "Q_park"
    assert entity.accepted is True


def test_no_search_result_is_a_different_answer_from_a_refused_one(monkeypatch, requests_mock):
    """ "No such item" and "an item we did not believe" want different fixes -
    a spelling and a disambiguation - so the report must tell them apart."""
    _no_sleep(monkeypatch)
    requests_mock.get(spike.WIKIDATA_API, json={"search": []})

    assert spike.resolve(_session(), "Nowhere In Particular", 41.0, -74.0) is None


def test_an_entity_with_no_coordinate_is_not_silently_believed(monkeypatch, requests_mock):
    """A missing P625 is not evidence that the entity is the right one. It
    comes back refused, with the reason said out loud."""
    _no_sleep(monkeypatch)
    requests_mock.get(
        spike.WIKIDATA_API,
        [
            {"json": _search("Q_nocoord")},
            {"json": _entities(_entity("Q_nocoord", "Somewhere", "a concept"))},
        ],
    )

    entity = spike.resolve(_session(), "Somewhere", 41.0, -74.0)

    assert entity.accepted is False
    assert entity.rejected_because == "no coordinate to check"


def test_the_drift_bar_sits_above_a_park_radius_and_below_another_state():
    """The constant has to separate exactly two confusions. This pins that it
    still does, so a later tightening cannot quietly start refusing the right
    entity for being measured from a park's far corner."""
    across_a_big_park = spike.kilometres_between((41.25, -74.08), (41.35, -74.20))
    another_state = spike.kilometres_between((41.25, -74.08), (43.90, -75.40))

    assert across_a_big_park < spike.MAX_ENTITY_DRIFT_KM
    assert another_state > spike.MAX_ENTITY_DRIFT_KM


# --- the lead image ------------------------------------------------------------


def test_a_p18_is_read_with_its_licence_author_and_capture_date(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    entity = spike.Entity("Q1", "Harriman State Park", "state park", 41.25, -74.08, 0.0, True, None)
    requests_mock.get(spike.WIKIDATA_API, json=_entities(_entity("Q1", "Harriman", image="Island Pond.jpg")))
    requests_mock.get(spike.COMMONS_API, json=_imageinfo())

    image = spike.lead_image(_session(), entity)

    assert image.filename == "Island Pond.jpg"
    assert image.licence == "cc-by-sa-4.0"
    assert image.author == "A Photographer"
    assert image.taken == date(2025, 6, 1)
    assert image.licence_ok is True


def test_an_entity_without_a_p18_returns_nothing_rather_than_an_empty_record(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    entity = spike.Entity("Q2", "Sterling Forest", "state park", 41.2, -74.29, 0.0, True, None)
    requests_mock.get(spike.WIKIDATA_API, json=_entities(_entity("Q2", "Sterling Forest")))

    assert spike.lead_image(_session(), entity) is None


def test_a_cc_by_image_with_nobody_to_credit_is_not_shippable(monkeypatch, requests_mock):
    """#1450: "the credit line is the licence's condition, not a courtesy".
    lib/commons.eligible_photo enforces this for geosearch hits; a P18 arrives
    by a different road and needs the same bar."""
    _no_sleep(monkeypatch)
    entity = spike.Entity("Q3", "A Park", "state park", 41.0, -74.0, 0.0, True, None)
    requests_mock.get(spike.WIKIDATA_API, json=_entities(_entity("Q3", "A Park", image="X.jpg")))
    requests_mock.get(spike.COMMONS_API, json=_imageinfo(licence="cc-by-4.0", artist=""))

    image = spike.lead_image(_session(), entity)

    assert image.licence_ok is True
    assert image.creditable is False


def test_a_public_domain_image_needs_no_author(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    entity = spike.Entity("Q4", "A Park", "state park", 41.0, -74.0, 0.0, True, None)
    requests_mock.get(spike.WIKIDATA_API, json=_entities(_entity("Q4", "A Park", image="X.jpg")))
    requests_mock.get(spike.COMMONS_API, json=_imageinfo(licence="pd", artist=""))

    assert spike.lead_image(_session(), entity).creditable is True


def test_a_pre_four_point_zero_licence_is_refused(monkeypatch, requests_mock):
    """POI_PHOTOS.md rejects the pre-4.0 CC suite wholesale, and a P18 is not
    exempt from it for having been curated."""
    _no_sleep(monkeypatch)
    entity = spike.Entity("Q5", "A Park", "state park", 41.0, -74.0, 0.0, True, None)
    requests_mock.get(spike.WIKIDATA_API, json=_entities(_entity("Q5", "A Park", image="X.jpg")))
    requests_mock.get(spike.COMMONS_API, json=_imageinfo(licence="cc-by-sa-2.0"))

    assert spike.lead_image(_session(), entity).licence_ok is False


# --- freshness, which is what this spike found the wall at ---------------------


def _image(taken):
    entity = spike.Entity("Q9", "A Park", "", 41.0, -74.0, 0.0, True, None)
    return spike.LeadImage(entity, "X.jpg", "u", "p", "cc-by-sa-4.0", "Someone", taken)


def test_an_image_with_no_capture_date_is_not_fresh():
    """An age that cannot be established cannot pass an age requirement -
    lib/commons.parse_date_taken's rule, and absence is a verdict not a gap."""
    assert _image(None).fresh(date(2022, 9, 15)) is False


def test_freshness_is_inclusive_at_the_cutoff():
    assert _image(date(2022, 9, 15)).fresh(date(2022, 9, 15)) is True
    assert _image(date(2022, 9, 14)).fresh(date(2022, 9, 15)) is False


# --- a rate limiter is not a finding -------------------------------------------


def test_a_429_is_retried_rather_than_counted_as_an_absent_photograph(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(spike.WIKIDATA_API, [{"status_code": 429}, {"json": {"search": []}}])

    assert spike.api_get(_session(), spike.WIKIDATA_API, {"action": "wbsearchentities"}) == {"search": []}


def test_retry_after_is_honoured_when_the_server_sends_one(monkeypatch, requests_mock):
    """Wikimedia's API etiquette asks callers to back off by the header rather
    than by their own guess, and this spike exists partly because #1450's probe
    did not."""
    waits = []
    monkeypatch.setattr(spike.time, "sleep", lambda s: waits.append(s))
    requests_mock.get(
        spike.WIKIDATA_API,
        [{"status_code": 429, "headers": {"Retry-After": "42"}}, {"json": {"search": []}}],
    )

    spike.api_get(_session(), spike.WIKIDATA_API, {"action": "wbsearchentities"})

    assert 42 in waits


def test_a_hard_failure_raises_rather_than_reporting_no_photograph(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(spike.WIKIDATA_API, status_code=404)

    with pytest.raises(requests.exceptions.HTTPError):
        spike.api_get(_session(), spike.WIKIDATA_API, {"action": "wbsearchentities"})


# --- the report ----------------------------------------------------------------


def test_the_funnel_separates_what_the_freshness_bar_costs(monkeypatch, requests_mock, capsys):
    """The number this spike exists to show. A report that printed only the
    post-filter count would hide the decision behind a low percentage."""
    _no_sleep(monkeypatch)
    monkeypatch.setattr(spike, "PARKS", (("A Park", 41.0, -74.0, "A Park"),))
    requests_mock.get(
        spike.WIKIDATA_API,
        [
            {"json": _search("Q1")},
            {"json": _entities(_entity("Q1", "A Park", "state park", 41.0, -74.0))},
            {"json": _entities(_entity("Q1", "A Park", image="Old.jpg"))},
        ],
    )
    requests_mock.get(spike.COMMONS_API, json=_imageinfo(taken="2015-06-01 10:00:00"))

    spike.report(_session(), None, today=date(2026, 9, 15))

    output = capsys.readouterr().out
    assert "shippable ignoring freshness        1" in output
    assert "shippable as the bar stands today   0" in output


def test_an_unknown_flag_is_rejected_rather_than_silently_ignored():
    with pytest.raises(SystemExit) as excinfo:
        spike.run(["--shotz"])  # not "--shot": that is a prefix of --shots

    assert excinfo.value.code == 2
