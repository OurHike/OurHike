"""Whether an organization's mark may ship, and the check that no mark ships without one (#933).

Why this exists
---------------
OurHike is offline-first. An organization's logo is not fetched when a card
renders - it is copied into the download and carried on a hiker's phone,
potentially for months, inside an application distributed under AGPL-3.0. That
is redistribution, and it needs permission in writing the same way the trail
geometry does. A logo is usually held MORE tightly than the data: trademark
rather than copyright, with organizations that care a great deal about how
their mark is used.

So the failure this file guards is not a crash and not a wrong pixel. It is a
third-party trademark entering a public repository permanently, with nobody
having asked, because the file looked like an ordinary asset on the day it was
committed and the licensing question had no home.

THIS REPOSITORY HAS ALREADY DONE THAT ONCE. `client/src/design-system/assets/
trails/at-logo.png` is the official Appalachian Trail / National Scenic Trail
marker; it carries its own TM; it is in the bundle today; and its entire
permission record is a comment at the top of `client/src/lib/trails.ts`. That
is the maintainer's own decision and a legitimate basis - it is the same
footing `atc_licence` and `photo_licence` stand on - but a permission recorded
only in a source comment is a permission the next person will not find. The
registry now records it, and these tests are what keep the next one from
repeating the pattern.

Nothing here can make an organization answer. What it can do is make the answer
a precondition rather than an afterthought, which is the whole argument of
features/SOURCE_REGISTRY.md's "required at submission: licence and attribution"
applied one asset class over.

WHAT IS GREEN TODAY, AND WHY THAT IS NOT VACUOUS
No organization has granted anything, and no org mark is in the tree, so the
teeth below bite on an empty set. That is a real state rather than an absent
one: it is the difference between "we checked and nothing ships" and "nobody
looked". The tests earn their keep on the day somebody drops the first file in.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
REGISTRY = json.loads((ROOT / "sources.json").read_text())
MARKS = REGISTRY["org_marks"]

# The one place an organization's mark may live. Named here rather than
# discovered, so that putting one somewhere else is a change somebody makes
# deliberately - and so this test has a directory to police at all.
ORG_MARK_DIR = REPO / "client" / "src" / "design-system" / "assets" / "orgs"

# Everything that is a picture. Deliberately wider than the set the client
# imports today: the check is "did an image of somebody's brand get committed",
# and a `.webp` nobody has used yet is exactly as much of a trademark as a
# `.svg` somebody has.
IMAGE_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".ico"}


def providers() -> set[str]:
    return {s["provider"] for s in REGISTRY["sources"]}


class TestTheRecordCoversEveryOrganization:
    """Derived from the registry rather than listed, for the reason
    tests/test_poi_coverage.py gives about its own org set: a new registration
    must not be able to slip past by not being added to a second place."""

    def test_every_registered_provider_has_a_mark_answer(self):
        missing = providers() - set(MARKS["orgs"])

        assert missing == set(), (
            "these organizations publish data this build ships and nobody has said "
            f"whether their mark may ship too: {sorted(missing)}. `not_asked` is a "
            "complete answer - an absent row is not."
        )

    def test_no_mark_answer_for_an_organization_that_is_not_registered(self):
        """The reverse, and it catches the likelier drift: a provider renamed in
        `sources` while its mark row keeps the old spelling, leaving a record
        that reads as current and joins nothing."""
        extra = set(MARKS["orgs"]) - providers()

        assert extra == set(), f"mark rows for unregistered organizations: {sorted(extra)}"

    def test_every_state_is_one_of_the_four_declared_words(self):
        vocabulary = set(MARKS["state_vocabulary"])

        for org, row in MARKS["orgs"].items():
            assert row["state"] in vocabulary, f"{org}: {row['state']!r} is not one of {sorted(vocabulary)}"

    def test_a_state_that_is_not_a_grant_still_says_something(self):
        """A row reading `not_asked` with no note is indistinguishable from a
        row somebody forgot. The note is where "the ask rides along with #768"
        lives, which is the thing a reader actually needs."""
        for org, row in MARKS["orgs"].items():
            if row["state"] != "granted":
                assert row.get("note", "").strip(), f"{org}: a state with no note rests on nothing"


class TestAGrantHasToBeComplete:
    """The four permissions are not decoration. Each is a different thing an
    organization can say no to, and a grant recorded without one of them is a
    permission somebody assumed."""

    def test_a_granted_row_carries_all_four_permissions(self):
        for org, row in MARKS["orgs"].items():
            if row["state"] != "granted":
                continue
            for permission in MARKS["required_on_grant"]:
                assert permission in row.get("permissions", {}), (
                    f"{org} is recorded as granting its mark, but says nothing about "
                    f"{permission!r}. See org_marks.permission_meanings."
                )

    def test_a_granted_row_says_who_granted_it_and_when(self):
        for org, row in MARKS["orgs"].items():
            if row["state"] != "granted":
                continue
            assert row.get("recorded_date"), f"{org}: a grant with no date cannot be aged or re-checked"
            assert row.get("terms_source", "").strip(), (
                f"{org}: a grant needs to name where it came from - an email, a brand-kit "
                "page with its read date, a person at the org. 'Somebody said yes' is not a record."
            )

    def test_the_brand_colour_permission_is_chip_only_wherever_it_is_granted(self):
        """The one permission that constrains OurHike rather than the org, and
        the one an implementer is most likely to breach by accident.

        The map's hue channel means WHICH BLAZE A HIKER FOLLOWS. An
        organization's brand colour reaching a trail line would make the map say
        something false about paint on a tree - the same class of claim
        `nynjtc_highlands_trail`'s `blaze_default: "Unknown"` already refuses to
        make, and one of CLAUDE.md's four ways this app can hurt somebody
        (lost).
        """
        assert "brand_colour_chip_only" in MARKS["required_on_grant"]

        for org, row in MARKS["orgs"].items():
            colour = row.get("brand_colour")
            if not colour:
                continue
            assert row["state"] == "granted", f"{org}: a brand colour recorded without a grant"
            assert row["permissions"]["brand_colour_chip_only"] is True, (
                f"{org}: a brand colour is recorded and the chip-only constraint is not affirmed"
            )


class TestNoMarkShipsWithoutOne:
    """The teeth. Everything above is bookkeeping if a file can appear in the
    bundle regardless."""

    @staticmethod
    def committed_marks() -> list[Path]:
        if not ORG_MARK_DIR.exists():
            return []
        return sorted(p for p in ORG_MARK_DIR.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)

    def test_no_org_mark_file_exists_without_a_recorded_grant(self):
        """Reads the tree, not the registry, because the registry is the thing
        somebody forgets to update.

        `.github/tests/test_no_committed_data.py` is the sibling check and it
        cannot cover this: its `DATA_SUFFIXES` are geospatial formats, and it
        allowlists `client/public/` wholesale. An `.svg` trips nothing there.
        """
        granted = {row.get("asset") for row in MARKS["orgs"].values() if row["state"] == "granted" and row.get("asset")}

        unlicensed = [str(p.relative_to(REPO)) for p in self.committed_marks() if str(p.relative_to(REPO)) not in granted]

        assert unlicensed == [], (
            "these images sit where an organization's mark goes and no row in "
            f"org_marks records a grant covering them: {unlicensed}. A mark ships inside "
            "an offline bundle on a hiker's phone under AGPL-3.0; that is redistribution "
            "of somebody's trademark. Record the permission or remove the file."
        )

    def test_todays_answer_is_that_no_org_mark_ships_at_all(self):
        """Dated 2026-08-27, and stated as a fact rather than left implicit.

        This is the assertion that turns the empty green above into a claim: not
        "the check found nothing to complain about" but "no organization's mark
        is in this bundle". When the first grant lands, this test is the one
        that has to be deliberately edited - which is the point.
        """
        assert self.committed_marks() == []
        assert not any(row["state"] == "granted" for row in MARKS["orgs"].values())


class TestTheTrailMarkThatIsAlreadyHere:
    """A.T.-marker-shaped, and the reason the record had to exist before any org
    replied. Not an org mark, so it does not live under ORG_MARK_DIR and the
    check above does not police it - but it IS a third-party trademark in a
    public AGPL tree, and #933's item 3 says the answer is recorded per source.
    """

    ATC_ROW = MARKS["orgs"]["ATC"]
    LOGO = REPO / "client" / "src" / "design-system" / "assets" / "trails" / "at-logo.png"

    def test_the_at_marker_is_in_the_tree_and_the_registry_says_so(self):
        assert self.LOGO.exists(), (
            "if this file moved, the record in org_marks.orgs.ATC.trail_mark_in_tree moved with it or stopped being true"
        )

        record = self.ATC_ROW["trail_mark_in_tree"]
        assert record["asset"] == str(self.LOGO.relative_to(REPO))
        assert record["basis"].strip()
        assert record["scope"].strip()

    def test_the_trail_mark_record_is_not_read_as_an_org_grant(self):
        """The distinction that has to survive somebody skim-reading the row.
        ATC's state is `not_asked` for an ORG mark; a trail marker the
        maintainer supplied is a different permission about a different asset on
        a different surface, and letting it read as the first would put ATC's
        logo on a steward card on nobody's authority."""
        assert self.ATC_ROW["state"] == "not_asked"
        assert "not a grant from ATC" in self.ATC_ROW["note"].lower().replace("  ", " ") or (
            "NOT a grant from ATC" in self.ATC_ROW["note"]
        )


def test_the_permission_vocabulary_and_the_required_set_agree():
    """The two lists are written separately and mean the same thing, which is
    the shape that goes stale. `tests/test_poi_coverage.py` pins its own
    vocabulary against the enforcing test for the same reason."""
    assert set(MARKS["required_on_grant"]) == set(MARKS["permission_meanings"])


@pytest.mark.parametrize("permission", sorted(MARKS["permission_meanings"]))
def test_every_permission_says_what_it_means(permission: str):
    """A four-word key with no gloss is a permission an organization would be
    asked to grant without being told what it covers."""
    assert len(MARKS["permission_meanings"][permission]) > 80
