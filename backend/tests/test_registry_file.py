"""An organization's registry as a file somebody can review line by line.

**WHY A FILE AT ALL.** The registry-approval decision of 2026-09-21: an
org's three codeowners approve its registry on GitHub with their own
accounts, and branch protection gates the merge on their review.
`.github/CODEOWNERS` maps PATHS to people, so the registry has to be at a
path - one per org, or every org's codeowners would own every org's file.

**WHY A DIRECTORY PER ORG.** That directory's stated exception is a join
encoding judgement somebody reviews row by row, which is exactly what a
sign-off is. The split into one file per park is measured rather than
tidy: a section serializes to 9 lines, so a single per-org file holds about
1,330 sections before passing `MAX_REFERENCE_LINES` - ample for a club on a
stretch of the AT and not ample for one maintaining a whole trail system,
which is the organization whose registry matters most.

**WHAT IS DELIBERATELY NOT IN IT** is the part worth reading twice. No row
ids, no timestamps, and no geometry. Ids and timestamps are database
bookkeeping that would churn the diff without telling a reviewer anything.
Geometry is the bigger one: a linestring per section would bury the names
and mileages a person is actually approving under megabytes they cannot
read, which defeats the review the file exists for - and it is derived data,
whose home is `pipeline/data/` and not a commit. The reviewed file is the
manifest; the shapes come from the organization's own GIS, which is
authoritative for them anyway.
"""

import json

from app.core.registry_file import INDEX_FILE, org_dir, registry_document, registry_files
from app.models.org_registry import OrgPark, OrgSection, OrgTrail
from tests.factories import make_org, make_section


def _registry(db_session, club):
    """Two parks, out of alphabetical order on purpose."""
    for park_name, trail_name, section_name in (
        ("Sterling Forest", "Sterling Ridge", "Sterling Ridge South"),
        ("Harriman", "Pine Meadow", "Pine Meadow North"),
        ("Harriman", "Pine Meadow", "Pine Meadow South"),
    ):
        park = db_session.query(OrgPark).filter(OrgPark.club_id == club.id, OrgPark.name == park_name).one_or_none()
        if park is None:
            park = OrgPark(club_id=club.id, name=park_name)
            db_session.add(park)
            db_session.flush()
        trail = db_session.query(OrgTrail).filter(OrgTrail.park_id == park.id, OrgTrail.name == trail_name).one_or_none()
        if trail is None:
            trail = OrgTrail(park_id=park.id, name=trail_name, blaze_value_raw="RED", blaze_mapped="red", miles=4.5)
            db_session.add(trail)
            db_session.flush()
        db_session.add(OrgSection(trail_id=trail.id, name=section_name, start_mile=0.0, end_mile=2.5, miles=2.5, region="North"))
    db_session.commit()


class TestWhereItGoes:
    def test_one_directory_per_org_slug(self):
        assert org_dir("ramapo-trail-conference") == "pipeline/reference/orgs/ramapo-trail-conference"

    def test_the_directory_is_under_the_reference_shelf(self):
        """Named rather than assumed: the CODEOWNERS entry and the branch
        protection rule are both written against this prefix, so a move
        that only edited one of them would silently un-gate the other."""
        assert org_dir("anything").startswith("pipeline/reference/orgs/")

    def test_every_file_an_org_writes_is_inside_its_own_directory(self, client, db_session):
        """The whole gate rests on this. A file written outside the
        organization's directory is a file its codeowners do not own, and a
        registry change nobody at that organization has to approve."""
        club = make_org(db_session)
        _registry(db_session, club)

        for path in registry_files(db_session, club):
            assert path.startswith(org_dir("ramapo-trail-conference") + "/")

    def test_a_park_gets_its_own_file_and_the_index_lists_it(self, client, db_session):
        club = make_org(db_session)
        _registry(db_session, club)

        files = registry_files(db_session, club)
        index = json.loads(files[f"{org_dir('ramapo-trail-conference')}/{INDEX_FILE}"])

        assert [park["file"] for park in index["parks"]] == ["harriman.json", "sterling-forest.json"]
        assert f"{org_dir('ramapo-trail-conference')}/harriman.json" in files

    def test_two_parks_that_slugify_alike_do_not_collide(self, client, db_session):
        """One park silently overwriting another is a registry missing a
        park, which is worth a suffix to avoid."""
        club = make_org(db_session)
        db_session.add(OrgPark(club_id=club.id, name="Bear Mountain"))
        db_session.add(OrgPark(club_id=club.id, name="Bear  Mountain!"))
        db_session.commit()

        files = registry_files(db_session, club)

        assert f"{org_dir('ramapo-trail-conference')}/bear-mountain.json" in files
        assert f"{org_dir('ramapo-trail-conference')}/bear-mountain-2.json" in files


class TestWhatItCarries:
    def test_the_three_tiers_come_out_nested(self, client, db_session):
        club = make_org(db_session)
        _registry(db_session, club)

        document = registry_document(db_session, club)

        parks = {park["name"] for park in document["parks"]}
        assert parks == {"Harriman", "Sterling Forest"}

    def test_a_trail_keeps_the_org_s_own_blaze_word(self, client, db_session):
        """`blaze_value_raw` is their GIS's spelling and is the whole reason
        the column exists - a reviewer checks the mapping against it."""
        club = make_org(db_session)
        _registry(db_session, club)

        document = registry_document(db_session, club)
        harriman = next(park for park in document["parks"] if park["name"] == "Harriman")

        assert harriman["trails"][0]["blaze_value_raw"] == "RED"
        assert harriman["trails"][0]["blaze_mapped"] == "red"

    def test_no_row_ids_and_no_timestamps_anywhere(self, client, db_session):
        """Database bookkeeping churns the diff and tells a reviewer nothing."""
        club = make_org(db_session)
        _registry(db_session, club)

        text = "".join(registry_files(db_session, club).values())

        assert '"id"' not in text
        assert "created_at" not in text

    def test_no_geometry(self, client, db_session):
        """The reason the file stays reviewable. A linestring per section
        would bury the names and mileages under what nobody reads."""
        club = make_org(db_session)
        section = make_section(db_session, club, name="With A Shape")
        section.geometry = "LINESTRING(-74.1 41.2, -74.2 41.3)"
        db_session.commit()

        text = "".join(registry_files(db_session, club).values())

        assert "LINESTRING" not in text
        assert "geometry" not in text


class TestThatADiffMeansSomething:
    def test_the_same_registry_serializes_identically_twice(self, client, db_session):
        """A review workflow where every regeneration reshuffles the file is
        a review workflow nobody can read."""
        club = make_org(db_session)
        _registry(db_session, club)

        assert registry_files(db_session, club) == registry_files(db_session, club)

    def test_everything_is_sorted_by_name(self, client, db_session):
        """Insertion order is whatever the GIS import happened to do, and
        would make the first diff look like a rewrite."""
        club = make_org(db_session)
        _registry(db_session, club)

        document = registry_document(db_session, club)

        assert [park["name"] for park in document["parks"]] == ["Harriman", "Sterling Forest"]
        harriman = document["parks"][0]
        assert [section["name"] for section in harriman["trails"][0]["sections"]] == [
            "Pine Meadow North",
            "Pine Meadow South",
        ]

    def test_a_mileage_does_not_serialize_as_binary_noise(self, client, db_session):
        """0.1 + 0.2 in a float column reaches JSON as 0.30000000000000004
        and makes a diff nobody changed."""
        club = make_org(db_session)
        section = make_section(db_session, club, name="Noisy", miles=0.1 + 0.2)
        db_session.commit()
        assert section.miles != 0.3

        document = registry_document(db_session, club)
        only = document["parks"][0]["trails"][0]["sections"][0]

        assert only["miles"] == 0.3

    def test_it_ends_with_a_newline(self, client, db_session):
        """A file committed without one makes every later diff touch the
        last line."""
        club = make_org(db_session)
        _registry(db_session, club)

        assert all(text.endswith("\n") for text in registry_files(db_session, club).values())


class TestTheCeilingTheSplitWasFor:
    def test_a_section_still_costs_about_nine_lines(self, client, db_session):
        """The measurement the directory-per-org split rests on, pinned.

        `MAX_REFERENCE_LINES` is 12,000 per file, and the split into one
        file per park was chosen because a section costs 9 lines - so a
        park holds roughly 1,300 of them. If a field is added here that
        cost grows, and the headroom shrinks without anybody noticing until
        a real organization's pull request is refused by a guard.
        """
        club = make_org(db_session)
        park = OrgPark(club_id=club.id, name="Harriman")
        db_session.add(park)
        db_session.flush()
        trail = OrgTrail(park_id=park.id, name="Pine Meadow")
        db_session.add(trail)
        db_session.flush()
        for index in range(40):
            db_session.add(OrgSection(trail_id=trail.id, name=f"Section {index:03d}", miles=1.0))
        db_session.commit()

        text = registry_files(db_session, club)[f"{org_dir('ramapo-trail-conference')}/harriman.json"]
        empty = registry_files(db_session, make_org(db_session, slug="empty-org"))[f"{org_dir('empty-org')}/{INDEX_FILE}"]
        per_section = (text.count("\n") - empty.count("\n")) / 40

        assert per_section <= 10, (
            f"A section now costs {per_section:.1f} lines, so a park file holds about "
            f"{int(12_000 / per_section):,} sections before MAX_REFERENCE_LINES refuses it. "
            "Either trim the shape or split further, and say which in review."
        )


class TestAnOrgWithNothingYet:
    def test_an_empty_registry_is_a_document_rather_than_a_crash(self, client, db_session):
        """Every org has one of these before it has any trails, and the PR
        that carries the first import diffs against it."""
        club = make_org(db_session)

        document = registry_document(db_session, club)

        assert document["parks"] == []
        files = registry_files(db_session, club)
        index = json.loads(files[f"{org_dir('ramapo-trail-conference')}/{INDEX_FILE}"])
        assert index["org"]["slug"] == "ramapo-trail-conference"
        assert index["parks"] == []
