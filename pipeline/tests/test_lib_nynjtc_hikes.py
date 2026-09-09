"""Turning one of NYNJTC's Favorite Hikes into facts, and refusing a payload
whose shape has changed (#1290).

Synthetic posts throughout, in the real pages' skeleton (measured against
the live API on 2026-09-09: `_embed` terms and featured media, a Google Maps
embed whose marker is the trailhead, a `<details><summary>Detailed Hike
Description` block opening with a `Publication:` line) - so a change in
NYNJTC's theme fails here rather than emptying a build. The cases that
matter most are the ones that would put a WRONG fact in front of a hiker
rather than none: a viewport scale read as a latitude, a season's caption
read as prose, a credit lost so a photograph ships uncredited.
"""

from __future__ import annotations

from lib.nynjtc_hikes import (
    DIFFICULTY_LEVELS,
    START_MAP_CENTRE,
    START_MARKER,
    hike_problems,
    is_public,
    paragraphs,
    parse_hike,
    parse_publication,
    parse_start,
    photo_credit,
    rendition_url,
    strip_html,
)

MARKER_EMBED = (
    "https://www.google.com/maps/embed?pb=!1m21!1m12!1m3!1d96243.07!2d-74.2699!3d41.0778"
    "!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!4m6!3e6!4m0!4m3!3m2!1d41.077853!2d-74.187596"
    "!5e0!3m2!1sen!2sus!4v1746537411965!5m2!1sen!2sus"
)
PLACE_CARD_EMBED = (
    "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d17446.173480264977!2d-73.9277743905855"
    "!3d40.96321960135218!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2"
    "!1s0x89c2f21f961bd1a7%3A0x51d86911fefa2443!2sPalisades%20Interstate%20Park!5e1!3m2!1sen!2sus"
)


def body(
    *,
    embed: str | None = MARKER_EMBED,
    details: bool = True,
    publication: str = "<strong>Publication:</strong> Submitted by Daniel Chazin on 08/24/2016, updated/verified on 08/15/2021",
    caption_paragraph: str = "<p>View of the skyline from Cactus Ledge &#8211; Photo by Daniel Chazin</p>",
) -> str:
    """One page in the real skeleton: title, figure, caption line, tag table,
    overview, the map, the shop block, the description."""
    map_block = (
        f'<h2 class="wp-block-heading">How to Get There</h2><div class="map-responsive-short"><iframe src="{embed}"></iframe></div>'
        if embed
        else ""
    )
    description = (
        "<details open><summary>Detailed Hike Description</summary>"
        f"<p>{publication}</p>"
        "<p>This hike follows the <strong>yellow-blazed</strong> Vista Loop Trail.</p>"
        "<p>At the end of the pond, turn right onto the Pond Loop Trail.</p>"
        "</details>"
        if details
        else ""
    )
    return (
        "<h2>Hike: Vista Loop Trail</h2>"
        '<figure><img src="https://www.nynjtc.org/wp-content/uploads/2025/05/IMG_5127_e_0.jpg" '
        'alt="View of the skyline from Cactus Ledge - Photo by Daniel Chazin" /><span>Photo by Daniel Chazin</span></figure>'
        f"{caption_paragraph}"
        '<div><span>Region: </span><a href="/region/x/" rel="tag">Northern New Jersey Highlands</a></div>'
        '<div><span>Difficulty: </span><a href="/difficulty/moderate/" rel="tag">Moderate</a></div>'
        "<p>This <strong>3.8-mile</strong> loop offers <strong>scenic overlooks</strong>, <strong>rocky ascents</strong>, and water.</p>"
        "<p>The hike begins with a stroll around Scarlet Oak Pond.</p>"
        f"{map_block}"
        "<p>Don&#8217;t Leave Unprepared</p><script>var shop = 1;</script>"
        '<p>The digital version of this map is available exclusively at:</p><div><a href="https://www.avenzamaps.com/a/1uitbpd">Visit Avenza</a></div>'
        f"{description}"
        "<h3><strong>Support the trails you love</strong></h3><p>Your gift helps.</p>"
    )


def post(**overrides) -> dict:
    """NYNJTC's real Vista Loop post, cut down to what the parser reads."""
    base = {
        "id": 14496,
        "slug": "hike-vista-loop-trail",
        "type": "hike",
        "date": "2025-05-06T09:39:26",
        "date_gmt": "2025-05-06T13:39:26",
        "modified": "2025-05-27T10:27:17",
        "modified_gmt": "2025-05-27T14:27:17",
        "link": "https://www.nynjtc.org/hike/hike-vista-loop-trail/",
        "title": {"rendered": "Hike: Vista Loop Trail"},
        "content": {"rendered": body(), "protected": False},
        "_embedded": {
            "wp:featuredmedia": [
                {
                    "source_url": "https://www.nynjtc.org/wp-content/uploads/2025/05/IMG_5127_e_0.jpg",
                    "alt_text": "View of the skyline from Cactus Ledge - Photo by Daniel Chazin",
                    "caption": {"rendered": "<p>View of the skyline from Cactus Ledge</p>"},
                    "media_details": {
                        "width": 2000,
                        "height": 1031,
                        "sizes": {
                            "medium": {"width": 300, "source_url": "https://x/IMG-300x155.jpg"},
                            "large": {"width": 1024, "source_url": "https://x/IMG-1024x529.jpg"},
                            "1536x1536": {"width": 1536, "source_url": "https://x/IMG-1536x792.jpg"},
                            "full": {"width": 2000, "source_url": "https://x/IMG_5127_e_0.jpg"},
                        },
                    },
                }
            ],
            "wp:term": [
                [{"taxonomy": "difficulty", "slug": "moderate", "name": "Moderate"}],
                [{"taxonomy": "route-type", "slug": "loop", "name": "Loop"}],
                [
                    {"taxonomy": "park", "slug": "ramapo-valley-county-reservation", "name": "Ramapo Valley County Reservation"},
                ],
                [{"taxonomy": "region", "slug": "northern-new-jersey-highlands", "name": "Northern New Jersey Highlands"}],
                [{"taxonomy": "distance", "slug": "2-4-miles", "name": "2&#8211;4 miles"}],
                [{"taxonomy": "category", "slug": "hikes", "name": "Hikes"}],
            ],
        },
    }
    base.update(overrides)
    return base


class TestAWholePage:
    def test_a_real_page_parses_into_facts(self):
        hike = parse_hike(post())

        assert hike is not None
        assert hike.slug == "hike-vista-loop-trail"
        assert hike.name == "Vista Loop Trail"
        assert hike.title == "Hike: Vista Loop Trail"
        assert hike.source_url == "https://www.nynjtc.org/hike/hike-vista-loop-trail/"
        assert hike.difficulty == "moderate"
        assert [term.name for term in hike.terms["park"]] == ["Ramapo Valley County Reservation"]
        assert hike.stated_miles == 3.8
        assert hike.start == (41.077853, -74.187596)
        assert hike.start_basis == START_MARKER
        assert hike_problems(hike) == []

    def test_the_change_signal_is_modified_gmt_not_the_site_local_stamp(self):
        """lib/nynjtc_alerts.py records the bounded error of stamping the
        site-local `modified` as UTC; the GMT field is in the payload and is
        exact, so this reads it from the start."""
        hike = parse_hike(post())

        assert hike.modified_at == "2025-05-27T14:27:17"
        assert hike.published_at == "2025-05-06T13:39:26"

    def test_terms_are_only_the_taxonomies_a_hike_is_categorised_by(self):
        """WordPress's `category` rides the same `_embed` array. It says
        "Hikes" on every post and would be one more thing to ship."""
        hike = parse_hike(post())

        assert "category" not in hike.terms
        assert hike.terms["distance"][0].name == "2–4 miles"

    def test_every_difficulty_nynjtc_uses_is_one_the_app_will_carry(self):
        for level in ("easy", "easy-moderate", "moderate", "moderate-strenuous", "strenuous"):
            assert level in DIFFICULTY_LEVELS

    def test_a_difficulty_outside_the_five_is_no_difficulty(self):
        """Absent means unknown; a sixth word NYNJTC might add one day must
        not become a badge nobody designed."""
        embedded = post()["_embedded"]
        embedded["wp:term"][0] = [{"taxonomy": "difficulty", "slug": "expert", "name": "Expert"}]
        hike = parse_hike(post(_embedded=embedded))

        assert hike.difficulty is None
        assert any("no difficulty" in problem for problem in hike_problems(hike))


class TestTheProse:
    def test_the_overview_is_the_paragraphs_above_the_map_without_the_caption_line(self):
        """The caption under the figure is a `<p>` like the prose and sits
        first. It is the photo record's and must not open the description."""
        hike = parse_hike(post())

        assert hike.overview == [
            "This 3.8-mile loop offers scenic overlooks, rocky ascents, and water.",
            "The hike begins with a stroll around Scarlet Oak Pond.",
        ]

    def test_the_tag_table_never_reads_as_a_paragraph(self):
        """Region/Park/Difficulty sit in divs and spans, not paragraphs.
        Reading elements rather than splitting on `</p>` is what keeps
        "Region: Catskill Park: Catskill Park" out of every overview."""
        hike = parse_hike(post())

        assert not any("Region:" in text or "Difficulty:" in text for text in hike.overview)

    def test_inline_tags_do_not_break_words_from_their_punctuation(self):
        assert strip_html("<strong>rocky ascents</strong>, and <em>water</em>.") == "rocky ascents, and water."

    def test_block_tags_still_keep_words_apart(self):
        assert paragraphs("<p>one<br>two</p><li>three</li>") == ["one two", "three"]

    def test_the_description_is_the_details_block_minus_its_publication_line(self):
        hike = parse_hike(post())

        assert hike.description == [
            "This hike follows the yellow-blazed Vista Loop Trail.",
            "At the end of the pond, turn right onto the Pond Loop Trail.",
        ]
        assert hike.publication is not None
        assert hike.publication.submitted_by == "Daniel Chazin"
        assert hike.publication.submitted_on == "2016-08-24"
        assert hike.publication.verified_on == "2021-08-15"

    def test_a_page_never_reverified_carries_no_verified_date(self):
        """`hike-west-kill-mountain-from-spruceton-road`: submitted 2017,
        never since. The card must not print the submission date as a
        verification."""
        parsed = parse_publication("Publication: Submitted by Daniel Chazin on 11/12/2017")

        assert parsed is not None
        assert parsed.submitted_on == "2017-11-12"
        assert parsed.verified_on is None

    def test_the_publication_line_tolerates_the_missing_comma(self):
        """`hike-cranberry-lake-preserve-loop` writes it without the comma."""
        parsed = parse_publication("Publication: Submitted by Daniel Chazin on 02/25/2005 updated/verified on 06/29/2018")

        assert parsed.verified_on == "2018-06-29"

    def test_the_shop_block_and_the_avenza_link_never_reach_the_prose(self):
        hike = parse_hike(post())
        everything = " ".join(hike.overview + hike.description)

        assert "Avenza" not in everything
        assert "Unprepared" not in everything
        assert "Support the trails" not in everything

    def test_a_page_with_no_description_block_is_a_hike_with_problems_not_a_parse_failure(self):
        """catskill-fire-towers: five map PDFs, no route, no description. A
        reviewer sees it and holds it; None would have said NYNJTC's page
        changed shape."""
        hike = parse_hike(post(content={"rendered": body(embed=None, details=False), "protected": False}))

        assert hike is not None
        assert hike.description == []
        assert hike.publication is None
        assert hike.start is None
        problems = hike_problems(hike)
        assert any("nowhere to start" in p for p in problems)
        assert any("no Detailed Hike Description" in p for p in problems)


class TestTheStart:
    def test_the_marker_pair_is_the_start(self):
        assert parse_start(f'<iframe src="{MARKER_EMBED}">') == ((41.077853, -74.187596), START_MARKER)

    def test_the_viewport_scale_is_never_read_as_a_latitude(self):
        """The place-card embed's first `!1d` is 17,446 - a scale in metres.
        Taken blindly it is a trailhead at latitude 17,446°, which is what
        the first version of this parse did (measured on
        forest-view-closter-dock-trail-loop...)."""
        located = parse_start(f'<iframe src="{PLACE_CARD_EMBED}">')

        assert located is not None
        (lat, lon), basis = located
        assert basis == START_MAP_CENTRE
        assert abs(lat - 40.9632) < 0.001
        assert abs(lon - (-73.9278)) < 0.001

    def test_a_place_card_start_is_reported_as_the_weaker_reading(self):
        hike = parse_hike(post(content={"rendered": body(embed=PLACE_CARD_EMBED), "protected": False}))

        assert hike.start_basis == START_MAP_CENTRE
        assert any("place-card" in problem for problem in hike_problems(hike))

    def test_no_embed_is_no_start(self):
        assert parse_start("<p>no map here</p>") is None

    def test_a_marker_outside_the_region_is_refused(self):
        embed = "https://www.google.com/maps/embed?pb=!4m3!3m2!1d51.5!2d-0.12"
        assert parse_start(f'<iframe src="{embed}">') is None


class TestThePhotograph:
    def test_the_featured_media_is_the_photo_with_its_credit(self):
        hike = parse_hike(post())

        assert hike.photo is not None
        assert hike.photo.basis == "featured_media"
        assert hike.photo.credit == "Daniel Chazin"
        assert hike.photo.width == 2000

    def test_the_rendition_is_the_widest_no_wider_than_1024(self):
        assert rendition_url(post()) == "https://x/IMG-1024x529.jpg"

    def test_the_rendition_falls_back_to_the_original_when_nothing_fits(self):
        embedded = post()["_embedded"]
        embedded["wp:featuredmedia"][0]["media_details"]["sizes"] = {"huge": {"width": 4000, "source_url": "https://x/huge.jpg"}}
        assert rendition_url(post(_embedded=embedded)) == "https://www.nynjtc.org/wp-content/uploads/2025/05/IMG_5127_e_0.jpg"

    def test_the_three_credit_spellings_the_site_uses(self):
        assert photo_credit("Buttermilk Falls - Photo: Daniel Chazin") == "Daniel Chazin"
        assert photo_credit("View of Plattekill Falls - Photo credit: Daniela Wagstaff") == "Daniela Wagstaff"
        assert photo_credit("Cactus Ledge - Photo by Daniel Chazin") == "Daniel Chazin"
        assert photo_credit("The five Fire Towers of the Catskill Park") is None

    def test_a_credit_only_in_the_caption_paragraph_is_still_found(self):
        """Six of the twenty carry the photographer only in the paragraph
        under the figure, not in the media record."""
        embedded = post()["_embedded"]
        embedded["wp:featuredmedia"][0]["alt_text"] = "Cranberry Lake Preserve"
        embedded["wp:featuredmedia"][0]["caption"] = {"rendered": ""}
        markup = body(caption_paragraph="<p>Cranberry Lake Preserve &#8211; Photo: Jane Daniels</p>")
        hike = parse_hike(post(_embedded=embedded, content={"rendered": markup, "protected": False}))

        assert hike.photo.credit == "Jane Daniels"
        assert hike.photo.caption == "Cranberry Lake Preserve – Photo: Jane Daniels"
        assert "Jane Daniels" not in " ".join(hike.overview)

    def test_a_post_with_no_featured_media_takes_the_first_credited_figure(self):
        """hike-bear-mountain-summit-loop. The Avenza logo is a figure too,
        uncredited, and must not be chosen."""
        embedded = post()["_embedded"]
        embedded.pop("wp:featuredmedia")
        hike = parse_hike(post(_embedded=embedded))

        assert hike.photo is not None
        assert hike.photo.basis == "content_figure"
        assert hike.photo.source_url == "https://www.nynjtc.org/wp-content/uploads/2025/05/IMG_5127_e_0.jpg"
        assert hike.photo.credit == "Daniel Chazin"

    def test_a_caption_that_repeats_the_alt_text_is_not_prose(self):
        embedded = post()["_embedded"]
        embedded["wp:featuredmedia"][0]["alt_text"] = "The five Fire Towers of the Catskill Park"
        markup = body(caption_paragraph="<p>The five Fire Towers of the Catskill Park</p>")
        hike = parse_hike(post(_embedded=embedded, content={"rendered": markup, "protected": False}))

        assert "The five Fire Towers of the Catskill Park" not in hike.overview

    def test_an_uncredited_photo_is_a_named_problem(self):
        embedded = post()["_embedded"]
        embedded["wp:featuredmedia"][0]["alt_text"] = "A view"
        embedded["wp:featuredmedia"][0]["caption"] = {"rendered": ""}
        hike = parse_hike(post(_embedded=embedded, content={"rendered": body(caption_paragraph=""), "protected": False}))

        assert hike.photo.credit is None
        assert any("no 'Photo by' credit" in problem for problem in hike_problems(hike))


class TestRefusals:
    def test_a_password_protected_post_is_not_public(self):
        assert not is_public({"content": {"rendered": "", "protected": True}})
        assert is_public(post())

    def test_a_protected_post_never_parses_into_an_empty_hike(self):
        assert parse_hike(post(content={"rendered": "", "protected": True})) is None

    def test_the_required_five_each_refuse(self):
        assert parse_hike(post(id="14496")) is None
        assert parse_hike(post(slug="")) is None
        assert parse_hike(post(modified_gmt="", modified="")) is None
        assert parse_hike(post(link="/hike/vista/")) is None
        assert parse_hike(post(title={"rendered": ""})) is None
        assert parse_hike("not a post") is None

    def test_the_stated_miles_are_the_hyphenated_form_only(self):
        """ "3.4 miles from the trailhead" is a distance along the way and
        must not become the hike's length."""
        markup = body().replace(
            "This <strong>3.8-mile</strong> loop",
            "The summit is 3.4 miles from the lot on this <strong>6.8-mile</strong> out-and-back; a 2-mile spur",
        )
        hike = parse_hike(post(content={"rendered": markup, "protected": False}))

        assert hike.stated_miles == 6.8
        assert hike.stated_miles_mentioned == [6.8, 2.0]
