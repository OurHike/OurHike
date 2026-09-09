"""Turning NYNJTC's WordPress payload into facts, and refusing a payload
whose shape has changed.

The cases below are the ones measured against their live API on 2026-08-27
rather than imagined - the same discipline `test_lib_atc_scrape.py` applies to
ATC's HTML. Two of them are real hygiene warts in NYNJTC's own taxonomies and
would look like bugs in this parser if they were not written down here:
`highlands-trail` is a term in BOTH the trail and park vocabularies, and a
title can arrive carrying an HTML entity.
"""

from __future__ import annotations

from lib.nynjtc_alerts import (
    PLACE_TAXONOMIES,
    Term,
    alert_problems,
    parse_alert,
    parse_terms,
)


def vocabularies() -> dict[str, dict[int, Term]]:
    """The four place taxonomies, cut down to the terms these tests use.

    Real ids and slugs, read off NYNJTC's API on 2026-08-27, so a test that
    passes here is a test about their data rather than about a fixture.
    """
    return {
        "trail": parse_terms(
            [
                {"id": 40, "name": "Appalachian Trail", "slug": "appalachian-trail"},
                {"id": 68, "name": "Ramapo-Dunderberg Trail", "slug": "ramapo-dunderberg-trail"},
                {"id": 31, "name": "Highlands Trail", "slug": "highlands-trail"},
            ]
        ),
        "park": parse_terms(
            [
                {"id": 213, "name": "Harriman-Bear Mountain State Parks", "slug": "harriman-bear-mountain-state-parks"},
                {"id": 405, "name": "Highlands Trail", "slug": "highlands-trail"},
            ]
        ),
        "region": parse_terms([{"id": 284, "name": "Harriman-Bear Mountain", "slug": "harriman-bear-mountain"}]),
        "state": parse_terms([{"id": 66, "name": "New York", "slug": "new-york"}]),
    }


def post(**overrides) -> dict:
    """NYNJTC's real A.T. detour alert, as their API returns it."""
    return {
        "slug": "a-t-detour-at-harriman-state-park",
        "title": {"rendered": "A.T. Detour at Harriman State Park"},
        "content": {"rendered": "<p>The Appalachian Trail follows the detour shown on the map.</p>"},
        "date": "2026-06-16T14:36:10",
        "modified": "2026-06-16T14:37:46",
        "link": "https://www.nynjtc.org/trail-alerts/a-t-detour-at-harriman-state-park/",
        "trail": [40, 68],
        "park": [213],
        "region": [284],
        "state": [66],
        **overrides,
    }


def test_a_real_alert_parses_into_facts_and_resolves_its_place_terms():
    alert = parse_alert(post(), vocabularies())

    assert alert is not None
    assert alert.slug == "a-t-detour-at-harriman-state-park"
    assert alert.title == "A.T. Detour at Harriman State Park"
    assert [term.name for term in alert.trails] == ["Appalachian Trail", "Ramapo-Dunderberg Trail"]
    assert [term.name for term in alert.parks] == ["Harriman-Bear Mountain State Parks"]
    assert alert.source_url.startswith("https://")


def test_modified_is_kept_apart_from_published_because_alerts_are_edited_in_place():
    """The field that says whether an alert is current is NOT the one that
    says when it first appeared. Measured 2026-08-27: NYNJTC's Bear Mountain
    advisories were published 2025-11-21 and last modified 2026-05-04, so
    reading age off `date` would age a live advisory by six months."""
    alert = parse_alert(post(date="2025-11-21T00:00:00", modified="2026-05-04T00:00:00"), vocabularies())

    assert alert.published_at == "2025-11-21T00:00:00"
    assert alert.modified_at == "2026-05-04T00:00:00"


def test_a_title_arrives_with_its_entities_unescaped():
    """WordPress renders entities INTO the JSON, so a title carried through
    verbatim would print a literal `&#8211;` in front of a hiker. Real title,
    read 2026-08-27."""
    alert = parse_alert(
        post(title={"rendered": "Highlands Trail Section Closed: Rt 605 &#8211; Lackawanna Drive"}),
        vocabularies(),
    )

    assert alert.title == "Highlands Trail Section Closed: Rt 605 – Lackawanna Drive"


def test_the_same_slug_in_two_taxonomies_stays_two_terms():
    """`highlands-trail` is a term in BOTH the trail and the park vocabulary
    on NYNJTC's site (measured 2026-08-27, ids 31 and 405). A join table keyed
    on the slug alone would collapse a line and an area into one place, so the
    parse keeps them in their own lists and features/ORG_NOTICES.md keys on
    `taxonomy:slug`."""
    alert = parse_alert(post(trail=[31], park=[405]), vocabularies())

    assert [term.slug for term in alert.trails] == ["highlands-trail"]
    assert [term.slug for term in alert.parks] == ["highlands-trail"]
    assert len(alert.place_terms) == 2


def test_place_terms_put_trails_before_parks():
    """A trail is the thing a hiker is standing on; a park is the ground
    around it. The order is the placement preference, not cosmetic."""
    alert = parse_alert(post(), vocabularies())

    assert [term.name for term in alert.place_terms][:2] == ["Appalachian Trail", "Ramapo-Dunderberg Trail"]


def test_an_unknown_term_id_is_dropped_rather_than_faked():
    """A post referring to a term this run did not read is a post whose
    placement is partly unknown. Absent means unknown - it must not become a
    term with an invented name."""
    alert = parse_alert(post(trail=[40, 99999]), vocabularies())

    assert [term.id for term in alert.trails] == [40]


def test_an_alert_with_no_place_tags_at_all_still_parses():
    """Being unplaced is a real state rather than a defect - ATC_TRAIL_UPDATES
    .md argues the same for a region-wide advisory - so the parse keeps it and
    `alert_problems` is what says so."""
    alert = parse_alert(post(trail=[], park=[], region=[], state=[]), vocabularies())

    assert alert is not None
    assert alert.place_terms == []
    assert any("no trail or park tag" in problem for problem in alert_problems(alert))


def test_a_park_only_alert_is_reported_as_placed_to_an_area():
    alert = parse_alert(post(trail=[]), vocabularies())

    problems = alert_problems(alert)
    assert len(problems) == 1
    assert "park only" in problems[0]
    assert "Harriman-Bear Mountain State Parks" in problems[0]


def test_an_alert_naming_a_trail_has_nothing_to_report():
    assert alert_problems(parse_alert(post(), vocabularies())) == []


def test_a_payload_missing_any_of_the_required_four_is_refused_whole():
    """None rather than a partial row: the caller's next move is deciding
    whether a hiker sees this, and half a parsed safety notice is the
    confident wrong answer this path is fenced against."""
    for missing in ("slug", "title", "modified", "link"):
        assert parse_alert(post(**{missing: None}), vocabularies()) is None, missing


def test_a_link_that_is_not_http_is_refused():
    """The scheme check `chrome/ClosureSheet.tsx` enforces on the way out,
    applied on the way in - a notice renders its source as a link a hiker
    taps."""
    assert parse_alert(post(link="javascript:alert(1)"), vocabularies()) is None


def test_a_malformed_term_costs_that_term_and_not_the_vocabulary():
    terms = parse_terms(
        [
            {"id": 40, "name": "Appalachian Trail", "slug": "appalachian-trail"},
            {"id": "forty-one", "name": "Broken", "slug": "broken"},
            None,
        ]
    )

    assert list(terms) == [40]


def test_the_place_taxonomies_are_the_four_the_api_publishes():
    """Named so a fifth taxonomy appearing upstream is a deliberate addition
    rather than something that quietly starts being read."""
    assert PLACE_TAXONOMIES == ("trail", "park", "region", "state")
