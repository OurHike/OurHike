"""Tests for export_sources.py - publishing who the map's data belongs to.

Why this exists
---------------
Every failure this file guards is SILENT and prints a wrong sentence under an
organization's name on a hiker's phone. There is no crash to notice:

- A steward whose data does not ship, named anyway, with a licence beside it.
  Two of them are in the registry right now (GATC, NYS OPRHP), both fetched
  for review only pending a licence answer.
- A steward whose data DOES ship, omitted, when its licence obliges the
  attribution the omission removes.
- A tier or a licence inferred rather than recorded, which reads exactly like
  one somebody checked.

The registry these read from is hand-maintained prose plus a handful of flags,
so the cases below are written against a synthetic registry rather than the
real file - except where the point is what the real file currently says, which
is stated as such and dated.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import export_sources

ROOT = Path(__file__).resolve().parents[1]


def registry(*sources: dict, **blocks: dict) -> dict:
    return {"_comment": "synthetic", "sources": list(sources), **blocks}


def source(key: str, provider: str, reaches: bool, **fields) -> dict:
    return {"key": key, "provider": provider, "reaches_hikers": reaches, **fields}


class TestWhoGetsNamed:
    def test_names_a_steward_whose_data_reaches_hikers(self):
        out = export_sources.build_output(registry(source("a", "ATC", True, steward="Trail Org", attribution="© Trail Org")))

        assert [s["name"] for s in out["stewards"]] == ["Trail Org"]

    def test_omits_a_steward_registered_but_not_shipping(self):
        # The failure this whole flag exists to prevent: a licence printed
        # under the name of an organization whose data nobody publishes.
        out = export_sources.build_output(
            registry(
                source("a", "ATC", True, steward="Ships", attribution="© Ships"),
                source("b", "REVIEW", False, steward="Review Only", attribution="© Review"),
            )
        )

        assert [s["name"] for s in out["stewards"]] == ["Ships"]

    def test_omits_a_steward_whose_every_source_is_held_back(self):
        out = export_sources.build_output(
            registry(
                source("a", "HELD", False, steward="Held", attribution="© Held"),
                source("b", "HELD", False, steward="Held", attribution="© Held"),
            )
        )

        assert out["stewards"] == []

    def test_counts_only_the_shipping_layers_of_a_steward_that_ships_some(self):
        # A provider with one held-back layer still gets named - but the card
        # must not claim the held-back one, because "12 layers" beside a
        # licence is a claim about what a hiker holds.
        out = export_sources.build_output(
            registry(
                source("a", "ATC", True, steward="Org", title="Shipped"),
                source("b", "ATC", False, steward="Org", title="Held back"),
            )
        )

        assert out["stewards"][0]["layers"] == ["Shipped"]

    def test_refuses_to_run_when_a_source_is_unclassified(self):
        # A new registration must not default into a hiker's screen, in either
        # direction. Louder than a wrong answer, and the only failure here that
        # is not silent.
        unclassified = {"key": "brand_new", "provider": "X", "steward": "X"}

        with pytest.raises(SystemExit, match="brand_new"):
            export_sources.build_output(registry(unclassified))


class TestWhatItRefusesToGuess:
    def test_publishes_a_tier_only_when_every_shipping_source_agrees(self):
        out = export_sources.build_output(
            registry(
                source("a", "P", True, steward="Org", trust="authoritative"),
                source("b", "P", True, steward="Org", trust="authoritative"),
            )
        )

        assert out["stewards"][0]["trust"] == "authoritative"

    def test_publishes_no_tier_when_one_shipping_source_is_silent(self):
        # The strict half, and the one that bites the real registry: eleven of
        # ATC's shipping entries carry no `trust` and one carries
        # `authoritative`. Silence is not agreement.
        out = export_sources.build_output(
            registry(
                source("a", "P", True, steward="Org", trust="authoritative"),
                source("b", "P", True, steward="Org"),
            )
        )

        assert out["stewards"][0]["trust"] is None

    def test_publishes_no_tier_when_shipping_sources_disagree(self):
        out = export_sources.build_output(
            registry(
                source("a", "P", True, steward="Org", trust="authoritative"),
                source("b", "P", True, steward="Org", trust="community"),
            )
        )

        assert out["stewards"][0]["trust"] is None


class TestLicenceAndAttribution:
    def test_takes_the_licence_from_the_steward_s_own_block(self):
        out = export_sources.build_output(
            registry(
                source("a", "ATC", True, steward="Trail Org"),
                atc_licence={"author": "Trail Org", "license": "© Trail Org, with permission"},
            )
        )

        assert out["stewards"][0]["licence"] == "© Trail Org, with permission"

    def test_never_publishes_the_per_source_licence_prose(self):
        # The first draft did, and the output was maintainer notes rendered
        # under an organization's name - "See usdm_licence above - reproduction
        # of the map is explicitly permitted with NDMC's credit line...".
        # Right thing to have written down, wrong thing to put on a phone.
        prose = "See x_licence above - fetched under the maintainer's declaration of 2026-08-15"
        out = export_sources.build_output(registry(source("a", "P", True, steward="Org", licence=prose, attribution="© Org")))

        assert out["stewards"][0]["licence"] is None
        assert prose not in json.dumps(out)

    def test_publishes_attribution_verbatim_because_that_is_what_a_licence_obliges(self):
        obliged = "The U.S. Drought Monitor is jointly produced by the NDMC, USDA, NOAA and NASA."
        out = export_sources.build_output(registry(source("a", "P", True, steward="Org", attribution=obliged)))

        assert out["stewards"][0]["attribution"] == obliged

    def test_matches_a_licence_block_by_author_not_by_key_name(self):
        # `atc_licence` is keyed on a three-letter abbreviation while its
        # author is the organization's full name, so key-guessing would miss.
        out = export_sources.build_output(
            registry(
                source("a", "SHORT", True, steward="A Long Organization Name"),
                unrelated_licence={"author": "Somebody Else", "license": "wrong"},
                short_licence={"author": "A Long Organization Name", "license": "right"},
            )
        )

        assert out["stewards"][0]["licence"] == "right"

    def test_leaves_the_licence_null_when_no_block_matches(self):
        # Real today for OpenStreetMap (no block) and the U.S. Drought Monitor
        # (its block's `author` does not match its source's `steward`). Null is
        # an honest "no short terms recorded" - a registry gap for somebody to
        # fill, not a licence for this exporter to compose.
        out = export_sources.build_output(registry(source("a", "P", True, steward="Org", attribution="© Org")))

        assert out["stewards"][0]["licence"] is None
        assert out["stewards"][0]["attribution"] == "© Org"


class TestTheSupportLine:
    """`<x>_support` - how a hiker supports the organization (#932).

    Every case here is about the same thing: a fundraising ask is renderable on
    a screen a hiker opens when they are lost, so the schema has to be able to
    say WHERE it may appear, and has to refuse to publish an ask that does not.
    """

    def test_publishes_a_support_line_from_a_block_matched_by_author(self):
        out = export_sources.build_output(
            registry(
                source("a", "P", True, steward="Trail Org"),
                anything_support={
                    "author": "Trail Org",
                    "donate_url": "https://example.org/join",
                    "donate_cta": "Become a Member",
                    "donate_surfaces": ["sources_screen"],
                },
            )
        )

        assert out["stewards"][0]["support"] == {
            "donate_url": "https://example.org/join",
            "donate_cta": "Become a Member",
            "donate_surfaces": ["sources_screen"],
        }

    def test_a_steward_that_has_not_asked_for_support_publishes_null(self):
        """#932's first rule: absent means the organization has not asked, which
        is not the same as an organization that wants none. Null so the card
        renders exactly as it does today - no button, no empty section, no
        placeholder. The same rule the pipeline applies to shelter capacity."""
        out = export_sources.build_output(registry(source("a", "P", True, steward="Org")))

        assert out["stewards"][0]["support"] is None

    def test_refuses_a_support_block_with_no_surfaces(self):
        """The failure this whole field exists to prevent. A block with no
        `donate_surfaces` is not a block granting nothing - it is a block whose
        permissions nobody wrote down, and a renderer given the two cannot tell
        them apart. So it stops the publish rather than shipping."""
        with pytest.raises(SystemExit, match="donate_surfaces"):
            export_sources.build_output(
                registry(
                    source("a", "P", True, steward="Org"),
                    x_support={
                        "author": "Org",
                        "donate_url": "https://example.org/give",
                        "donate_cta": "Give",
                    },
                )
            )

    def test_refuses_a_surface_that_is_not_in_the_vocabulary(self):
        with pytest.raises(SystemExit, match="surfaces that do not exist"):
            export_sources.build_output(
                registry(
                    source("a", "P", True, steward="Org"),
                    x_support={
                        "author": "Org",
                        "donate_url": "https://example.org/give",
                        "donate_cta": "Give",
                        "donate_surfaces": ["sources_screen", "trailhead_kiosk"],
                    },
                )
            )

    def test_the_map_is_not_a_surface_an_org_can_grant(self):
        """ "On the map, never" - the v2 frames' one explicit refusal, enforced
        by the vocabulary having no member for it rather than by a check that
        rejects one. The distinction matters: a rejecting check can be relaxed
        in a one-line diff, while adding a member here means going back to every
        organization that has already answered."""
        assert "map" not in export_sources.DONATE_SURFACES
        assert not any("map" in s for s in export_sources.DONATE_SURFACES)

        with pytest.raises(SystemExit, match="surfaces that do not exist"):
            export_sources.build_output(
                registry(
                    source("a", "P", True, steward="Org"),
                    x_support={
                        "author": "Org",
                        "donate_url": "https://example.org/give",
                        "donate_cta": "Give",
                        "donate_surfaces": ["map"],
                    },
                )
            )

    def test_carries_a_recipient_when_the_money_goes_somewhere_else(self):
        """Real for NYS OPRHP: a state agency has no donation destination of its
        own, and parks.ny.gov's Donate link points at the Natural Heritage
        Trust, a separate 501(c)(3). Rendering "Support NYS OPRHP" over that URL
        would tell a hiker their money reaches the agency. It does not."""
        out = export_sources.build_output(
            registry(
                source("a", "P", True, steward="An Agency"),
                x_support={
                    "author": "An Agency",
                    "donate_url": "https://example.gov/trust",
                    "donate_cta": "Donate",
                    "donate_recipient": "A Separate Charity",
                    "donate_surfaces": ["sources_screen"],
                },
            )
        )

        assert out["stewards"][0]["support"]["donate_recipient"] == "A Separate Charity"

    def test_omits_the_blurb_key_entirely_when_no_org_has_sent_words(self):
        """`donate_blurb` is the org's own writing about what the money does,
        and no organization has sent any. Absent rather than empty-string, so a
        renderer cannot mistake "nobody asked" for "they said nothing"."""
        out = export_sources.build_output(
            registry(
                source("a", "P", True, steward="Org"),
                x_support={
                    "author": "Org",
                    "donate_url": "https://example.org/give",
                    "donate_cta": "Give",
                    "donate_surfaces": ["sources_screen"],
                },
            )
        )

        assert "donate_blurb" not in out["stewards"][0]["support"]


class TestAgainstTheRealRegistry:
    """What the checked-in `sources.json` currently produces.

    Dated assertions about real data, kept few and kept about the rule rather
    than the row count - a registration should not have to edit this file, but
    admitting a held-back steward to a hiker's screen should.
    """

    @staticmethod
    def real() -> dict:
        return export_sources.build_output(json.loads((ROOT / "sources.json").read_text()))

    def test_every_registered_source_is_classified(self):
        # The gate that keeps the exporter runnable at all. If this fails, a
        # source was registered without anybody saying whether it ships.
        self.real()

    def test_names_no_steward_that_is_fetch_and_review_only(self):
        # Measured 2026-08-23: GATC's own licence field says "Nothing from this
        # source reaches a published artifact until GATC answers a
        # redistribution ask".
        named = {s["name"] for s in self.real()["stewards"]}

        assert not any("Georgia" in n for n in named)

    def test_names_the_two_trail_stewards_now_that_their_lines_ship(self):
        """OPRHP and NYNJTC moved from held-back to shipped on 2026-08-24
        (#950), and this case is the inverse of the one above rather than an
        exception to it.

        It used to assert that neither was named. That was right while both
        were review-only, and became wrong the moment `reaches_hikers` flipped
        - at which point NOT naming them would have been the failure, because
        OPRHP's own terms require attribution on any map built from their data.
        So the assertion turns over rather than being deleted: a steward whose
        data is on a hiker's phone is named, and one whose data is not is not.
        """
        named = {s["name"] for s in self.real()["stewards"]}

        assert any("Parks" in n for n in named), "OPRHP's attribution is a licence condition"
        assert any("New York-New Jersey" in n for n in named)

    def test_names_mohonk_preserve_now_that_its_lines_ship(self):
        """Mohonk Preserve joined OPRHP and NYNJTC on 2026-08-25 (#992), on the
        maintainer's authorisation rather than stated terms - the same footing
        NYNJTC shipped on. Not a licence condition the way OPRHP's is, but the
        same "say what is drawn" rule this exporter exists to hold applies to a
        courtesy as much as to a condition."""
        named = {s["name"] for s in self.real()["stewards"]}

        assert any("Mohonk" in n for n in named)

    def test_still_omits_the_oprhp_layers_nothing_exports(self):
        """The distinction the licence flip had to keep, and it is not about
        licensing: a source is held back either because its terms are
        unresolved OR because nothing is wired to it, and `reaches_hikers`
        carries both meanings (see reaches_hikers_comment).

        The membership moves as exporters get written - `oprhp_trail_closures`
        left this group under #964, when export_nearby_trails.py started
        deriving its areas onto the trail lines, and `oprhp_facilities` left it
        under #1097, when export_nearby_poi.py started reading its lean-tos,
        vistas, privies, parking areas and trail bridges - so what is asserted
        is the DISTINCTION rather than a fixed list. Every held-back oprhp_*
        layer says in its own licence field that the reason is a missing
        exporter, because the alternative reading (a licence problem) is the
        one that would stop somebody wiring it up.

        Worth keeping straight about the #1097 move, since it is the one that
        most looks like a licence change and is not: OPRHP's terms did not
        change, `oprhp_licence` is untouched, and #769's open question - whether
        OurHike is non-commercial within those stated terms - is exactly as open
        as it was. What changed is that something now reads the layer. The one
        part of it still held back, the water, is held back inside the export
        rather than by this flag (`oprhp_water_holdback`), which is the right
        place for a refusal that a flag flip must not be able to undo.
        """
        registry = json.loads((ROOT / "sources.json").read_text())
        oprhp = {s["key"]: s for s in registry["sources"] if s["key"].startswith("oprhp")}

        shipped = {k for k, s in oprhp.items() if s["reaches_hikers"]}
        held = {k for k, s in oprhp.items() if not s["reaches_hikers"]}

        assert shipped == {"oprhp_trails", "oprhp_trail_closures", "oprhp_facilities"}
        assert held == {"oprhp_park_polygons"}
        for key in held:
            assert "nothing exports this layer" in oprhp[key]["licence"]

    def test_every_licence_and_support_block_joins_a_steward(self):
        """The check that would have caught a two-year-old silent bug in one run.

        `_block` matches a block's `author` against the entries' `steward`, and
        an author string that matches nothing is invisible: the block sits in
        the registry looking correct, the exporter emits null, the card renders
        attribution alone, and every test passes.

        That is not hypothetical. Until 2026-08-27 `usdm_licence`'s author read
        "National Drought Mitigation Center, USDA, NOAA and NASA" while its
        source's steward read "National Drought Mitigation Center, University of
        Nebraska-Lincoln", so the U.S. Drought Monitor's recorded terms - which
        exist specifically because NDMC's permission is conditional on a credit
        - never reached the sources screen. The gap was WRITTEN DOWN in three
        places (this module's docstring, the entry's own `licence` prose saying
        "See usdm_licence above", and a test asserting null was expected) and
        still shipped. A gap documented in three places and never fixed is not
        documented, it is decorated.

        Scoped to stewards that exist in the registry at all, not to stewards
        that ship: a licence block for a held-back source is legitimate, and a
        block whose author matches NO registered steward is a typo.
        """
        registry = json.loads((ROOT / "sources.json").read_text())
        stewards = {s["steward"] for s in registry["sources"] if s.get("steward")}

        orphaned = {
            key: block["author"]
            for key, block in registry.items()
            if isinstance(block, dict)
            and (key.endswith("_licence") or key.endswith("_support"))
            and block.get("author") not in stewards
        }

        assert orphaned == {}, (
            "these blocks name an author no registered source's `steward` matches, "
            f"so nothing they record reaches a hiker: {orphaned}"
        )

    def test_the_drought_monitors_terms_now_reach_the_screen(self):
        """The regression half of the case above, asserted on the real output
        rather than on the registry, because the registry looked fine
        throughout."""
        ndmc = next(s for s in self.real()["stewards"] if s["provider"].startswith("National Drought"))

        assert ndmc["licence"], "usdm_licence records conditional terms; a null here means unjoined"

    def test_the_three_orgs_that_have_a_support_line_and_the_five_that_do_not(self):
        """Measured 2026-08-27. Asserted as the SPLIT rather than as a list of
        three, because the failure worth catching is a fourth organization
        acquiring a support line without anybody deciding it should have one.

        The three are the orgs whose own public page states a destination and a
        button in their own words - read live, not composed here. The rest carry
        nothing, which is #932's first rule: absent means the organization has
        not asked, and it renders exactly as today.
        """
        support = {s["provider"]: s["support"] for s in self.real()["stewards"]}

        asking = {p for p, v in support.items() if v}
        assert asking == {"ATC", "NYNJTC", "NYS OPRHP"}

        assert support["ATC"]["donate_cta"] == "Become a Member"
        assert support["NYNJTC"]["donate_cta"] == "Donate Today"

        for provider in support.keys() - asking:
            assert support[provider] is None

    def test_oprhps_support_line_names_who_actually_receives_the_money(self):
        """The one entry where the destination is not the steward. NYS OPRHP is
        a state agency with no donation destination of its own; parks.ny.gov's
        Donate link resolves to the Natural Heritage Trust, a separate
        501(c)(3). A card rendering "Support NYS OPRHP" over that URL would make
        a claim about where a hiker's money goes that is not true, which is the
        never-let-a-display-outrun-its-source rule on a payment.

        Its surfaces are also the narrowest of the three, deliberately: the
        sources screen only, because a hiker on a trail card is looking at a
        trail rather than at where the map came from, and nobody at OPRHP has
        been asked.
        """
        oprhp = next(s for s in self.real()["stewards"] if s["provider"] == "NYS OPRHP")

        assert oprhp["support"]["donate_recipient"] == "Natural Heritage Trust"
        assert oprhp["support"]["donate_surfaces"] == ["sources_screen"]

    def test_no_organization_has_sent_words_about_what_the_money_does(self):
        """`donate_blurb` is absent everywhere, and this test is what keeps it
        that way until an org actually sends words. Lifting a paragraph off an
        organization's "why join" page and rendering it under their name in a
        hiker's app is the app speaking for an organization it does not
        represent - the same line #458 drew for ATC's notice text."""
        for steward in self.real()["stewards"]:
            if steward["support"]:
                assert "donate_blurb" not in steward["support"]

    def test_names_the_atc_with_its_recorded_licence(self):
        atc = next(s for s in self.real()["stewards"] if s["provider"] == "ATC")

        assert atc["licence"] == "© ATC, used with permission"
        # And no tier, because the registry does not record one for the eleven
        # A.T. feeds that ship - see the module docstring.
        assert atc["trust"] is None


def test_each_steward_lists_the_registry_keys_behind_its_layers():
    """The join a graph edge's `source` resolves through (#978): the phone has
    to turn `oprhp_trails` into an organization's name, and the KEY only
    survived into this artifact where a title was missing. Not index-aligned
    with `layers` - both are sorted independently, in different vocabularies -
    which the field's comment states so nobody joins them positionally."""
    registry = {
        "sources": [
            {
                "key": "oprhp_trails",
                "title": "NYS Parks Trails",
                "kind": "external_arcgis_layer",
                "provider": "NYS OPRHP",
                "steward": "New York State Office of Parks",
                "reaches_hikers": True,
            },
            {
                "key": "oprhp_closures",
                "title": "NYS Parks Closures",
                "kind": "external_arcgis_layer",
                "provider": "NYS OPRHP",
                "steward": "New York State Office of Parks",
                "reaches_hikers": True,
            },
        ]
    }

    output = export_sources.build_output(registry)

    (steward,) = output["stewards"]
    assert steward["keys"] == ["oprhp_closures", "oprhp_trails"]


class TestTheRegistryTheConsoleReads:
    """`build_registry` - every registered source, shipping or not (#929).

    Its sibling `build_output` may only name what actually ships. This one
    exists BECAUSE of that rule rather than in spite of it: the org console
    asks "what is registered", which is an admin question, and answering it
    from the hiker-facing artifact would have put a held-back steward on a
    sources card the day somebody wanted to count registrations.
    """

    @staticmethod
    def real() -> dict:
        return export_sources.build_registry(json.loads((ROOT / "sources.json").read_text()))

    def test_names_the_sources_that_reach_no_hiker(self):
        """The whole reason for a second artifact. GATC and the held-back
        OPRHP layer are registrations somebody has to be able to see."""
        keys = {row["key"] for row in self.real()["sources"]}

        assert "gatc_water_sources" in keys
        assert "oprhp_park_polygons" in keys

    def test_carries_the_flag_rather_than_filtering_on_it(self):
        rows = {row["key"]: row for row in self.real()["sources"]}

        assert rows["gatc_water_sources"]["reaches_hikers"] is False
        assert rows["nynjtc_trail_alerts"]["reaches_hikers"] is True

    def test_every_row_carries_the_stable_id_of_its_organization(self):
        missing = [row["key"] for row in self.real()["sources"] if not row["steward_id"]]

        assert missing == [], f"rows with no steward_id: {missing}"

    def test_leaves_an_undeclared_kind_null_rather_than_defaulting_it(self):
        """Twelve ATC entries declare no `kind`, and `lib/source_registry.py`
        reads an absent one as an ArcGIS feature layer. That default is a fact
        about the FETCHER, not about the registration - a console that filled
        it in would hide the twelve registrations a probe cannot describe."""
        rows = {row["key"]: row for row in self.real()["sources"]}

        assert rows["centerline"]["kind"] is None
        assert rows["nynjtc_trail_alerts"]["kind"] == "published_notices"

    def test_says_which_organizations_have_asked_for_support(self):
        rows = {row["key"]: row for row in self.real()["sources"]}

        assert rows["nynjtc_trail_alerts"]["supports_donation"] is True
        assert rows["dec_hiking_trails"]["supports_donation"] is False

    def test_a_source_inheriting_its_stewards_name_still_finds_the_support_block(self):
        """The twelve ATC entries, which is where this got it wrong.

        None of them declares its own `steward` - they inherit the
        organization's name, and `atc_support`'s `author` is that name. Joining
        the block on the raw field therefore matched nothing and every ATC row
        read `supports_donation: false`, while the organization record below
        read true from the same block, because it joins over all of a
        provider's entries at once. Two halves of one console disagreeing, and
        neither looked wrong on its own.

        Asserted as agreement rather than as a literal true, so the day ATC
        withdraw their support block this fails on the row that stops matching
        rather than on a hard-coded expectation of what they want.
        """
        registry = json.loads((ROOT / "sources.json").read_text())
        rows = [row for row in export_sources.build_registry(registry)["sources"] if row["provider"] == "ATC"]
        atc = next(steward for steward in export_sources.build_output(registry)["stewards"] if steward["provider"] == "ATC")

        assert len(rows) >= 12
        assert all(row["steward"] == "Appalachian Trail Conservancy" for row in rows)
        assert {row["supports_donation"] for row in rows} == {atc["support"] is not None}

    def test_says_no_organization_has_licensed_a_mark(self):
        states = {row["mark_state"] for row in self.real()["sources"]}

        assert states == {"not_asked"}

    def test_lists_every_organization_once_with_its_id(self):
        orgs = self.real()["organizations"]

        assert len(orgs) == 9
        assert {org["steward_id"] for org in orgs} == {
            "org:atc",
            "org:gatc",
            "org:mohonk",
            "org:ndmc",
            "org:nynjtc",
            "org:nysdec",
            "org:nysoprhp",
            "org:osm",
            "org:usgs",
        }

    def test_composes_nothing_a_reviewer_would_have_to_check(self):
        """Every field is one the registry already carries, copied. A console
        showing a number this file worked out - "seems well licensed",
        "probably fresh" - would be an opinion wearing the registry's
        authority, which is the failure the whole evidence standard exists to
        prevent."""
        registry = json.loads((ROOT / "sources.json").read_text())
        by_key = {s["key"]: s for s in registry["sources"]}

        for row in self.real()["sources"]:
            source = by_key[row["key"]]
            assert row["trust"] == source.get("trust")
            assert row["licence_basis"] == source.get("licence_basis")
            assert row["reaches_hikers"] == source["reaches_hikers"]

    def test_survives_a_registry_with_no_organizations_block(self):
        """Every synthetic fixture in this suite predates it, and so does every
        release exported before #929. Null rather than an error, because the id
        is additive and its absence is a state rather than a fault."""
        out = export_sources.build_registry(registry(source("a", "P", True, steward="Org")))

        assert out["sources"][0]["steward_id"] is None
        assert out["organizations"] == []
