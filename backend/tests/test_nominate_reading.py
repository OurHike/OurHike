"""Turning a club's fetched pages into something a hiker can review.

`app/core/sitefetch.py` reads the pages. `app/core/assist.py` asks a model
about them. This is the seam between them, and the property it exists to
hold is one sentence:

**NOTHING REACHES THE HIKER THAT WAS NOT IN THE PAGES WE READ.**

A model asked "who should we contact at this club" will produce plausible
addresses whether or not the page had any, because plausible is what it is
for. `volunteers@carolinamountainclub.org` is exactly the shape of a thing
that gets invented, and a hiker looking at a screen headed "what we could
see on their site" has no way to tell an invention from a reading. Then we
would email it.

So every address and every URL the model proposes is checked back against
the literal text of the pages before it is shown, and anything absent is
dropped. That is not a tidy-up: it is the whole reason this file is separate
from the prompt, and CLAUDE.md's "never let a display outrun its source"
applied to the one path where the display is about a person.

The second property is the other half of the same rule: when the fetch got
nowhere, `read_at_all` is False and the screen says so, rather than showing
a model's recollection of a club it has heard of under a heading claiming we
read their site.
"""

import pytest

from app.core.nominate import ReadingFailed, grounded, reading_from
from app.core.sitefetch import Link, Page

HOME = Page(
    url="https://carolinamountainclub.org/",
    title="Carolina Mountain Club",
    text="Carolina Mountain Club, Asheville NC. Maintains part of the Appalachian Trail.",
    links=(Link(href="https://carolinamountainclub.org/maps", text="Trail maps"),),
    emails=(),
)
CONTACT = Page(
    url="https://carolinamountainclub.org/get-involved",
    title="Get Involved",
    text=(
        "Volunteer coordinator Dale Whitford - volunteers@carolinamountainclub.org. "
        "GIS and trail data: Priya Raghavan, maps@carolinamountainclub.org."
    ),
    links=(Link(href="mailto:volunteers@carolinamountainclub.org", text="Dale Whitford"),),
    emails=("volunteers@carolinamountainclub.org", "maps@carolinamountainclub.org"),
)
MAPS = Page(
    url="https://carolinamountainclub.org/maps",
    title="Trail maps",
    text="Our trails are published at services.arcgis.com/abc/CMC_Trails/FeatureServer/0.",
    links=(
        Link(
            href="https://services.arcgis.com/abc/CMC_Trails/FeatureServer/0",
            text="FeatureServer",
        ),
    ),
    emails=(),
)
PAGES = (HOME, CONTACT, MAPS)


def answering(payload: str):
    """A stand-in for the model that says exactly this."""

    def ask(prompt: str, system: str) -> tuple[str, int]:
        return payload, 42

    return ask


class TestGrounding:
    def test_an_address_on_the_page_is_kept(self):
        assert grounded("volunteers@carolinamountainclub.org", PAGES) is True

    def test_an_address_nobody_published_is_not(self):
        """The invention this whole module exists to catch."""
        assert grounded("president@carolinamountainclub.org", PAGES) is False

    def test_case_does_not_decide_it(self):
        assert grounded("Volunteers@CarolinaMountainClub.ORG", PAGES) is True

    def test_a_url_in_a_link_counts_as_seen(self):
        assert grounded("https://services.arcgis.com/abc/CMC_Trails/FeatureServer/0", PAGES) is True

    def test_a_plausible_neighbour_of_a_real_url_does_not(self):
        """One digit different is the failure mode, not a wholly invented host."""
        assert grounded("https://services.arcgis.com/abc/CMC_Trails/FeatureServer/9", PAGES) is False

    def test_nothing_is_grounded_in_no_pages(self):
        assert grounded("volunteers@carolinamountainclub.org", ()) is False


class TestBuildingTheReading:
    def test_a_well_formed_answer_comes_through(self):
        answer = """{
          "org_name": "Carolina Mountain Club",
          "summary": "Asheville, NC. Maintains part of the Appalachian Trail.",
          "sources": [{"label": "ArcGIS FeatureServer",
                       "url": "https://services.arcgis.com/abc/CMC_Trails/FeatureServer/0",
                       "verdict": "usable", "detail": "line features"}],
          "contacts": [{"name": "Dale Whitford", "role": "Volunteer coordinator",
                        "email": "volunteers@carolinamountainclub.org",
                        "source_page": "https://carolinamountainclub.org/get-involved"}]
        }"""
        reading = reading_from("https://carolinamountainclub.org/", PAGES, ask=answering(answer))
        assert reading.read_at_all is True
        assert reading.org_name == "Carolina Mountain Club"
        assert reading.pages_read == 3
        assert [source.url for source in reading.sources] == ["https://services.arcgis.com/abc/CMC_Trails/FeatureServer/0"]
        assert [contact.email for contact in reading.contacts] == ["volunteers@carolinamountainclub.org"]

    def test_an_invented_contact_is_dropped_and_the_rest_survives(self):
        """One invention must not discard a reading that was otherwise right."""
        answer = """{
          "org_name": "Carolina Mountain Club",
          "contacts": [
            {"name": "Dale Whitford", "email": "volunteers@carolinamountainclub.org",
             "source_page": "https://carolinamountainclub.org/get-involved"},
            {"name": "Board President", "email": "president@carolinamountainclub.org",
             "source_page": "https://carolinamountainclub.org/contact"}
          ]
        }"""
        reading = reading_from("https://carolinamountainclub.org/", PAGES, ask=answering(answer))
        assert [contact.email for contact in reading.contacts] == ["volunteers@carolinamountainclub.org"]

    def test_an_invented_source_is_dropped(self):
        answer = """{"sources": [
          {"label": "Real", "url": "https://services.arcgis.com/abc/CMC_Trails/FeatureServer/0",
           "verdict": "usable"},
          {"label": "Imagined", "url": "https://carolinamountainclub.org/secret-gis",
           "verdict": "usable"}
        ]}"""
        reading = reading_from("https://carolinamountainclub.org/", PAGES, ask=answering(answer))
        assert [source.label for source in reading.sources] == ["Real"]

    def test_a_source_page_the_reading_never_read_is_corrected_rather_than_trusted(self):
        """The citation has to point at a page we actually opened.

        A contact whose `source_page` names a URL we never fetched cannot
        answer "where did you get this", which is the one thing
        `nomination_contacts.source_page` is NOT NULL for.
        """
        answer = """{"contacts": [
          {"name": "Dale Whitford", "email": "volunteers@carolinamountainclub.org",
           "source_page": "https://carolinamountainclub.org/invented-page"}
        ]}"""
        reading = reading_from("https://carolinamountainclub.org/", PAGES, ask=answering(answer))
        assert reading.contacts[0].source_page == "https://carolinamountainclub.org/get-involved"

    def test_a_contact_whose_page_cannot_be_identified_at_all_is_dropped(self):
        pages = (HOME,)
        answer = """{"contacts": [
          {"name": "Somebody", "email": "nobody@carolinamountainclub.org",
           "source_page": "https://carolinamountainclub.org/"}
        ]}"""
        reading = reading_from("https://carolinamountainclub.org/", pages, ask=answering(answer))
        assert reading.contacts == []

    def test_the_money_pages_are_grounded_too(self):
        pages = PAGES + (
            Page(
                url="https://carolinamountainclub.org/join",
                title="Join",
                text="Membership is $30 a year. Give at https://carolinamountainclub.org/support.",
                links=(),
                emails=(),
            ),
        )
        answer = """{"membership_url": "https://carolinamountainclub.org/join",
                     "donation_url": "https://carolinamountainclub.org/not-real"}"""
        reading = reading_from("https://carolinamountainclub.org/", pages, ask=answering(answer))
        assert reading.membership_url == "https://carolinamountainclub.org/join"
        assert reading.donation_url is None

    def test_a_verdict_the_schema_does_not_know_drops_the_source(self):
        """A model inventing a category is a model we are not going to render."""
        answer = """{"sources": [
          {"label": "Something", "url": "https://carolinamountainclub.org/maps",
           "verdict": "brilliant"}
        ]}"""
        reading = reading_from("https://carolinamountainclub.org/", PAGES, ask=answering(answer))
        assert reading.sources == []

    def test_json_wrapped_in_prose_is_still_read(self):
        """Models preface. The alternative is discarding a good answer."""
        answer = 'Here is what I found:\n```json\n{"org_name": "Carolina Mountain Club"}\n```\nHope that helps.'
        reading = reading_from("https://carolinamountainclub.org/", PAGES, ask=answering(answer))
        assert reading.org_name == "Carolina Mountain Club"

    def test_an_answer_that_is_not_json_at_all_is_a_failure_rather_than_an_empty_reading(self):
        """An empty reading reads as "their site has nothing on it", which is a lie."""
        with pytest.raises(ReadingFailed):
            reading_from("https://carolinamountainclub.org/", PAGES, ask=answering("I could not tell."))

    def test_no_pages_means_read_at_all_is_false(self):
        """And the model is never asked, because there is nothing to ask about.

        This is the case that used to produce a confident paragraph about a
        club from the model's own memory, under a heading saying we had read
        their site.
        """
        asked: list[str] = []

        def ask(prompt: str, system: str):
            asked.append(prompt)
            return "{}", 0

        reading = reading_from("https://carolinamountainclub.org/", (), ask=ask)
        assert reading.read_at_all is False
        assert reading.pages_read == 0
        assert reading.sources == []
        assert reading.contacts == []
        assert asked == []

    def test_the_pages_are_what_the_model_is_given(self):
        """Not the URL. The whole point is that it reads ours rather than its own."""
        seen: list[str] = []

        def ask(prompt: str, system: str):
            seen.append(prompt)
            return '{"org_name": "Carolina Mountain Club"}', 1

        reading_from("https://carolinamountainclub.org/", PAGES, ask=ask)
        assert "Dale Whitford" in seen[0]
        assert "CMC_Trails/FeatureServer/0" in seen[0]

    def test_the_prompt_is_bounded_however_long_the_site_is(self):
        """A club with a 900kB page must not become a 900kB prompt."""
        huge = Page(
            url="https://carolinamountainclub.org/big",
            title="Big",
            text="trail " * 200_000,
            links=(),
            emails=(),
        )
        seen: list[str] = []

        def ask(prompt: str, system: str):
            seen.append(prompt)
            return "{}", 1

        reading_from("https://carolinamountainclub.org/", (huge,), ask=ask)
        assert len(seen[0]) < 60_000
