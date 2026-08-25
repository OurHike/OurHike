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
        # redistribution ask". mohonk_trails (#992) joined this group
        # 2026-08-25 on the same footing - registered, fetched, and not named
        # until its licence is resolved.
        named = {s["name"] for s in self.real()["stewards"]}

        assert not any("Georgia" in n for n in named)
        assert not any("Mohonk" in n for n in named)

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

    def test_still_omits_the_oprhp_layers_nothing_exports(self):
        """The distinction the licence flip had to keep, and it is not about
        licensing: a source is held back either because its terms are
        unresolved OR because nothing is wired to it, and `reaches_hikers`
        carries both meanings (see reaches_hikers_comment).

        The membership moves as exporters get written - `oprhp_trail_closures`
        left this group under #964, when export_nearby_trails.py started
        deriving its areas onto the trail lines - so what is asserted is the
        DISTINCTION rather than a fixed list. Every held-back oprhp_* layer
        says in its own licence field that the reason is a missing exporter,
        because the alternative reading (a licence problem) is the one that
        would stop somebody wiring it up.
        """
        registry = json.loads((ROOT / "sources.json").read_text())
        oprhp = {s["key"]: s for s in registry["sources"] if s["key"].startswith("oprhp")}

        shipped = {k for k, s in oprhp.items() if s["reaches_hikers"]}
        held = {k for k, s in oprhp.items() if not s["reaches_hikers"]}

        assert shipped == {"oprhp_trails", "oprhp_trail_closures"}
        assert held == {"oprhp_facilities", "oprhp_park_polygons"}
        for key in held:
            assert "nothing exports this layer" in oprhp[key]["licence"]

    def test_names_the_atc_with_its_recorded_licence(self):
        atc = next(s for s in self.real()["stewards"] if s["provider"] == "ATC")

        assert atc["licence"] == "© ATC, used with permission"
        # And no tier, because the registry does not record one for the eleven
        # A.T. feeds that ship - see the module docstring.
        assert atc["trust"] is None
