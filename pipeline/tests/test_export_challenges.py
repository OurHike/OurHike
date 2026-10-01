"""The challenge exporter.

#1780 - Let a club publish a challenge - places on its own trails that
hikers opt into and tag at camp - starting with the ATC's A.T. Summer
Bucket List.

lib/challenges.py holds the resolution and test_lib_challenges.py its
refusals. What is left here is the plumbing that has gone wrong in this
pipeline before - loaders reading the names export_poi.py really writes, a
module constant a test moves being actually followed, a curated list never
shrinking quietly - plus the one claim that matters most before a release:
the files somebody reviewed and committed publish whole once their anchors
exist.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

import export_challenges as exporter
from lib.challenges import unseal
from lib.poi_schema import poi_output_name

TODAY = date(2026, 9, 30)

ORGANIZATIONS = {
    "org:atc": {"provider": "ATC", "name": "Appalachian Trail Conservancy"},
    "org:nynjtc": {"provider": "NYNJTC", "name": "New York-New Jersey Trail Conference"},
}

PUBLISHERS = [{"org": "atc", "trails": ["AT"], "why": "The A.T.'s route owner.", "domain": "AppalachianTrail.org"}]

KNOB = {
    "id": "atc_viewpoints:knob",
    "trail_id": "AT",
    "poi_type": "viewpoint",
    "name": "McAfee Knob Summit",
    "mile": 714.92,
    "lat": 37.39,
    "lon": -80.03,
}
PRIEST = {
    "id": "atc_shelters:priest",
    "trail_id": "AT",
    "poi_type": "shelter",
    "name": "The Priest Shelter",
    "mile": 830.0,
    "lat": 37.82,
    "lon": -79.07,
}


def write_pois(poi_dir: Path, poi_type: str, records: list[dict]) -> None:
    poi_dir.mkdir(parents=True, exist_ok=True)
    (poi_dir / poi_output_name(poi_type)).write_text(
        json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": r} for r in records]})
    )


def line_feature(source: str, geometry: dict) -> dict:
    return {"type": "Feature", "properties": {"source": source}, "geometry": geometry}


def write_trails(path: Path, features: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def challenge(**overrides) -> dict:
    base = {
        "id": "summer-list",
        "org": "atc",
        "trail": "AT",
        "name": "Summer List",
        "status": "draft",
        "window": {"opens": "2027-05-15", "closes": "2027-09-01"},
        "finish": None,
        "reward": None,
        "sections": [{"id": "experience", "title": "Experience the A.T."}],
        "items": [
            {
                "id": "mcafee-knob",
                "section": "experience",
                "title": "Hike to McAfee Knob.",
                "match": {"kind": "place", "poi": KNOB["id"]},
            }
        ],
        "reviewed": "2026-09-30",
    }
    base.update(overrides)
    return base


def build(files, *, pois=(KNOB, PRIEST), centerline=None, publishers=PUBLISHERS, organizations=ORGANIZATIONS, today=TODAY):
    pois = list(pois)
    org_trails, _ = exporter.publisher_scope(publishers, organizations, pois)
    return exporter.build_output(
        files,
        org_trails=org_trails,
        organizations=organizations,
        pois=pois,
        centerline=centerline,
        today=today,
        org_domains=exporter.publisher_domains(publishers),
    )


# --- the loaders ----------------------------------------------------------------


class TestReadingThePublishedPois:
    def test_reads_every_type_under_the_names_export_poi_writes(self, tmp_path):
        # lib/poi_schema.poi_output_name's docstring has the incident:
        # export_poi.py ran green, and a reader asked for names it does not
        # write. An item can name any type the ATC carries.
        write_pois(tmp_path / "poi", "viewpoint", [KNOB])
        write_pois(tmp_path / "poi", "shelter", [PRIEST])

        assert {p["id"] for p in exporter.load_published_pois(tmp_path / "poi")} == {KNOB["id"], PRIEST["id"]}

    def test_an_absent_directory_yields_nothing_rather_than_raising(self, tmp_path):
        assert exporter.load_published_pois(tmp_path / "nope") == []

    def test_the_default_is_followed_when_the_module_constant_moves(self, tmp_path, monkeypatch):
        # A plain `=POI_DIR` default binds once at import - the trap
        # export_spurs.py's own loader documents.
        write_pois(tmp_path / "poi", "viewpoint", [KNOB])
        monkeypatch.setattr(exporter, "POI_DIR", tmp_path / "poi")

        assert [p["id"] for p in exporter.load_published_pois()] == [KNOB["id"]]


class TestReadingTheReviewedFiles:
    def test_reads_org_directories_in_path_order_and_never_publishers_json(self, tmp_path, monkeypatch):
        for relative in ("nynjtc/long-path-list.json", "atc/b-list.json", "atc/a-list.json"):
            (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / relative).write_text(json.dumps({"id": Path(relative).stem}))
        (tmp_path / "publishers.json").write_text(json.dumps({"publishers": []}))
        monkeypatch.setattr(exporter, "REFERENCE_DIR", tmp_path)

        files = exporter.load_challenge_files()

        assert [(path.parent.name, path.stem) for path, _ in files] == [
            ("atc", "a-list"),
            ("atc", "b-list"),
            ("nynjtc", "long-path-list"),
        ]

    def test_a_file_that_is_not_json_is_named_and_handed_on_rather_than_raised(self, tmp_path, capsys):
        # This runs in the job that publishes the trail; one broken file must
        # not hold that back, and must not vanish either.
        (tmp_path / "atc").mkdir()
        (tmp_path / "atc" / "broken.json").write_text("{ not json")

        files = exporter.load_challenge_files(tmp_path)

        assert [(path.stem, raw) for path, raw in files] == [("broken", None)]
        assert "broken.json is not valid JSON" in capsys.readouterr().err

    def test_an_absent_publishers_file_is_fatal(self, tmp_path):
        with pytest.raises(SystemExit):
            exporter.load_publishers(tmp_path / "gone.json")

    def test_the_publishers_default_follows_the_module_constant(self, tmp_path, monkeypatch):
        (tmp_path / "publishers.json").write_text(json.dumps({"publishers": PUBLISHERS}))
        monkeypatch.setattr(exporter, "PUBLISHERS_PATH", tmp_path / "publishers.json")

        assert exporter.load_publishers() == PUBLISHERS

    def test_the_organizations_default_follows_the_module_constant(self, tmp_path, monkeypatch):
        (tmp_path / "sources.json").write_text(json.dumps({"organizations": {"orgs": ORGANIZATIONS}}))
        monkeypatch.setattr(exporter, "SOURCES_PATH", tmp_path / "sources.json")

        assert exporter.load_organizations() == ORGANIZATIONS


class TestReadingTheCenterline:
    def test_reads_only_the_centerline_in_either_line_geometry(self, tmp_path):
        path = tmp_path / "trails.geojson"
        write_trails(
            path,
            [
                line_feature("centerline", {"type": "LineString", "coordinates": [[-80.0, 37.0], [-80.0, 37.1]]}),
                line_feature(
                    "centerline", {"type": "MultiLineString", "coordinates": [[[-79.0, 38.0, 1200.0]], [[-78.0, 39.0]]]}
                ),
                # Blue-blazed: a place beside a side trail is not on the A.T.
                line_feature("side_trails", {"type": "LineString", "coordinates": [[-70.0, 44.0], [-70.0, 44.1]]}),
            ],
        )

        assert exporter.load_centerline(path) == [
            [(-80.0, 37.0), (-80.0, 37.1)],
            [(-79.0, 38.0)],
            [(-78.0, 39.0)],
        ]

    def test_an_absent_file_is_none_not_an_empty_line(self, tmp_path):
        # None is "not measured"; an empty list would read as "measured, and
        # nothing is near the trail". The caller reports the first.
        assert exporter.load_centerline(tmp_path / "trails.geojson") is None

    def test_the_default_is_followed_when_the_module_constant_moves(self, tmp_path, monkeypatch):
        write_trails(
            tmp_path / "trails.geojson", [line_feature("centerline", {"type": "LineString", "coordinates": [[-80.0, 37.0]]})]
        )
        monkeypatch.setattr(exporter, "TRAILS_PATH", tmp_path / "trails.geojson")

        assert exporter.load_centerline() == [[(-80.0, 37.0)]]


# --- publishers.json ------------------------------------------------------------


class TestPublisherScope:
    def test_an_organization_sources_json_does_not_register_is_refused(self):
        scope, refused = exporter.publisher_scope([{"org": "nobody", "trails": ["AT"], "why": "x"}], ORGANIZATIONS, [KNOB])

        assert scope == {}
        assert refused == ["'nobody': not an organization in sources.json (looked for 'org:nobody')"]

    def test_a_trail_no_published_poi_carries_is_refused_and_the_org_keeps_an_empty_scope(self):
        # `at` for `AT` is exactly how this happens. The org stays, so its
        # challenges drop as "not a trail atc publishes" - which is then true.
        scope, refused = exporter.publisher_scope(
            [{"org": "atc", "trails": ["at"], "why": "x", "domain": "appalachiantrail.org"}], ORGANIZATIONS, [KNOB]
        )

        assert scope == {"atc": set()}
        assert refused == ["atc: trail 'at' is carried by no published POI"]

    def test_only_the_bad_trail_of_a_row_is_refused(self):
        scope, refused = exporter.publisher_scope(
            [{"org": "atc", "trails": ["AT", "LP"], "why": "x", "domain": "appalachiantrail.org"}], ORGANIZATIONS, [KNOB]
        )

        assert scope == {"atc": {"AT"}}
        assert len(refused) == 1

    def test_with_no_published_pois_every_trail_is_refused(self):
        scope, refused = exporter.publisher_scope(PUBLISHERS, ORGANIZATIONS, [])

        assert scope == {"atc": set()}
        assert refused == ["atc: trail 'AT' is carried by no published POI"]

    def test_a_row_that_gives_no_reason_is_refused(self):
        _, refused = exporter.publisher_scope([{"org": "atc", "trails": ["AT"]}], ORGANIZATIONS, [KNOB])

        assert refused == ["atc: the row gives no `why`"]

    def test_an_organization_with_no_name_or_provider_to_publish_is_refused(self):
        # The phone prints "ATC · until Sep 1" from these and has no other
        # source for them.
        organizations = {"org:atc": {"name": "Appalachian Trail Conservancy"}}
        scope, refused = exporter.publisher_scope(PUBLISHERS, organizations, [KNOB])

        assert scope == {}
        assert "no name or no provider" in refused[0]

    def test_a_second_row_for_the_same_organization_is_refused(self):
        rows = [*PUBLISHERS, {"org": "atc", "trails": ["LP"], "why": "again"}]
        scope, refused = exporter.publisher_scope(rows, ORGANIZATIONS, [KNOB])

        assert scope == {"atc": {"AT"}}
        assert refused == ["atc: listed twice - the first row stands"]

    def test_the_real_publishers_file_is_accepted_whole_against_the_real_registry(self):
        scope, refused = exporter.publisher_scope(exporter.load_publishers(), exporter.load_organizations(), [KNOB])

        assert refused == []
        assert scope == {"atc": {"AT"}}


# --- the artifact ---------------------------------------------------------------


class TestBuildingTheOutput:
    def test_names_the_directory_the_judgement_lives_in_and_carries_no_stamp(self):
        # No generated_at: it would move the sha256 every run, and a run that
        # changed no challenge would publish a new version anyway.
        output, _ = build([(Path("atc/summer-list.json"), challenge())])

        assert set(output) == {"source", "challenges"}
        assert output["source"] == "reference/challenges"

    def test_every_record_carries_the_registrys_name_and_short_name(self):
        output, _ = build([(Path("atc/summer-list.json"), challenge())])

        record = output["challenges"][0]
        assert record["org_name"] == "Appalachian Trail Conservancy"
        assert record["org_short"] == "ATC"

    def test_a_file_filed_under_another_organizations_directory_is_dropped(self):
        # A reviewer reading nynjtc/ in the diff would not check the org.
        output, resolution = build([(Path("nynjtc/summer-list.json"), challenge())])

        assert output["challenges"] == []
        assert resolution.dropped == [("summer-list", "file is under nynjtc/ but its org is 'atc'")]

    def test_a_challenge_it_cannot_place_is_reported_not_just_absent(self):
        output, resolution = build([(Path("atc/summer-list.json"), challenge(trail="LP"))])

        assert output["challenges"] == []
        assert resolution.dropped == [("summer-list", "trail 'LP' is not one 'atc' publishes")]

    def test_only_a_type_some_published_poi_carries_can_be_matched(self):
        # POI_TYPES declares `parking`; with no parking POI published, "tag
        # any parking area" could never be tagged.
        items = [
            {
                "id": "shelter",
                "section": "experience",
                "title": "Sleep in a shelter.",
                "match": {"kind": "poi_type", "type": "shelter"},
            },
            {"id": "parking", "section": "experience", "title": "Park.", "match": {"kind": "poi_type", "type": "parking"}},
        ]
        output, resolution = build([(Path("atc/summer-list.json"), challenge(items=items))])

        assert [i["id"] for i in output["challenges"][0]["items"]] == ["shelter"]
        assert resolution.dropped_items == [("summer-list", "parking", "poi type 'parking' is not a published type")]

    def test_a_place_the_published_centerline_does_not_pass_is_dropped(self):
        # The real index, not a stub: a line 1 km west of McAfee Knob.
        west = [[(KNOB["lon"] - 0.0112, KNOB["lat"] + i * 0.0001) for i in range(-20, 21)]]
        output, resolution = build([(Path("atc/summer-list.json"), challenge())], centerline=west)

        assert output["challenges"][0]["items"] == []
        assert "past its 150 m radius" in resolution.dropped_items[0][2]

    def test_a_place_the_published_centerline_passes_publishes(self):
        through = [[(KNOB["lon"] + 0.00002, KNOB["lat"])]]
        output, resolution = build([(Path("atc/summer-list.json"), challenge())], centerline=through)

        assert resolution.dropped_items == []
        assert output["challenges"][0]["items"][0]["match"]["places"][0]["poi"] == KNOB["id"]

    @pytest.mark.parametrize("centerline", [None, []])
    def test_no_centerline_means_no_distance_check(self, centerline):
        # main() is what announces this; build_output has no audience.
        output, resolution = build([(Path("atc/summer-list.json"), challenge())], centerline=centerline)

        assert resolution.dropped_items == []
        assert len(output["challenges"][0]["items"]) == 1


# --- main(), end to end over a sandbox --------------------------------------------


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    reference = tmp_path / "challenges"
    (reference / "atc").mkdir(parents=True)
    monkeypatch.setattr(exporter, "POI_DIR", processed / "poi")
    monkeypatch.setattr(exporter, "TRAILS_PATH", processed / "trails.geojson")
    monkeypatch.setattr(exporter, "OUT_PATH", processed / "challenges.json")
    monkeypatch.setattr(exporter, "MANIFEST_PATH", processed / "challenges_manifest.json")
    monkeypatch.setattr(exporter, "REFERENCE_DIR", reference)
    monkeypatch.setattr(exporter, "PUBLISHERS_PATH", reference / "publishers.json")
    monkeypatch.setattr(exporter, "SOURCES_PATH", tmp_path / "sources.json")

    (tmp_path / "sources.json").write_text(json.dumps({"organizations": {"orgs": ORGANIZATIONS}}))
    (reference / "publishers.json").write_text(json.dumps({"publishers": PUBLISHERS}))
    write_pois(processed / "poi", "viewpoint", [KNOB])
    write_trails(
        processed / "trails.geojson",
        [line_feature("centerline", {"type": "LineString", "coordinates": [[KNOB["lon"] + 0.00002, KNOB["lat"]]]})],
    )
    items = [
        {
            "id": "mcafee-knob",
            "section": "experience",
            # The ATC's own curly apostrophe, which must survive verbatim.
            "title": "Hike to the ATC’s favourite knob.",
            "match": {"kind": "place", "poi": KNOB["id"]},
        },
        {
            "id": "mystery-1",
            "section": "experience",
            "title": "Find the hidden spring.",
            "mystery": {"number": 1, "reveal_on": "2027-07-20"},
            "match": {"kind": "self_report"},
        },
    ]
    (reference / "atc" / "summer-list.json").write_text(json.dumps(challenge(items=items)))
    return processed


class TestMain:
    def test_writes_the_artifact_and_a_manifest_that_hashes_it(self, sandbox):
        manifest = exporter.main(today=TODAY)

        written = (sandbox / "challenges.json").read_bytes()
        assert manifest["sha256"] == hashlib.sha256(written).hexdigest()
        assert json.loads((sandbox / "challenges_manifest.json").read_text()) == manifest
        assert Path(manifest["path"]).name == "challenges.json"
        assert "Hike to the ATC’s favourite knob." in written.decode("utf-8")

    def test_a_second_run_over_the_same_inputs_writes_the_same_bytes(self, sandbox):
        # What makes publish.py's "unchanged uploads nothing" true here.
        first = exporter.main(today=TODAY)["sha256"]
        assert exporter.main(today=TODAY)["sha256"] == first

    def test_a_sealed_title_opens_on_the_first_run_after_its_date(self, sandbox):
        exporter.main(today=TODAY)
        before = json.loads((sandbox / "challenges.json").read_text())["challenges"][0]["items"][1]
        assert before["title"] is None
        assert unseal(before["sealed_title"]) == "Find the hidden spring."
        assert "Find the hidden spring" not in (sandbox / "challenges.json").read_text()

        # On the day itself it is still sealed - a UTC build day is the
        # evening before on the A.T. - and the phone opens it locally.
        exporter.main(today=date(2027, 7, 20))
        on_the_day = json.loads((sandbox / "challenges.json").read_text())["challenges"][0]["items"][1]
        assert on_the_day["title"] is None

        exporter.main(today=date(2027, 7, 21))
        after = json.loads((sandbox / "challenges.json").read_text())["challenges"][0]["items"][1]
        assert after["title"] == "Find the hidden spring."

    def test_a_missing_centerline_is_announced_as_a_skipped_check(self, sandbox, capsys):
        (sandbox / "trails.geojson").unlink()

        exporter.main(today=TODAY)

        out = capsys.readouterr().out
        assert "::warning::" in out
        assert "distance check was SKIPPED" in out

    def test_a_present_centerline_says_what_it_measured_against(self, sandbox, capsys):
        exporter.main(today=TODAY)
        assert "against 1 centerline vertices" in capsys.readouterr().out

    def test_drops_are_reported_and_do_not_fail_the_run(self, sandbox, capsys):
        # export_highlights.py's stance: this runs in the job that publishes
        # the trail, and a shrinking list is caught by the report.
        (sandbox / "poi" / poi_output_name("viewpoint")).unlink()

        exporter.main(today=TODAY)

        captured = capsys.readouterr()
        assert "atc: trail 'AT' is carried by no published POI" in captured.err
        assert "summer-list: trail 'AT' is not one 'atc' publishes" in captured.err
        assert "::warning::challenges: 1 challenge(s)" in captured.out
        assert json.loads((sandbox / "challenges.json").read_text())["challenges"] == []


# --- the files somebody reviewed --------------------------------------------------

#: What each of the ATC's layers publishes as, for stubbing its POIs. A new
#: layer named by a reviewed file fails loudly here rather than stubbing a
#: guess.
POI_TYPE_BY_LAYER = {
    "atc_viewpoints": "viewpoint",
    "atc_shelters": "shelter",
    "atc_communities": "resupply",
}

#: The layers whose points are towns rather than places on the footpath -
#: ATC's A.T. Communities, measured 236 m (Harpers Ferry) and 2,867 m (Monson)
#: from the centerline, 2026-09-30, release 2026-09-24-2.
TOWN_LAYERS = {"atc_communities"}


def committed() -> list[tuple[Path, object]]:
    files = exporter.load_challenge_files()
    assert files, "reference/challenges/ should carry at least the ATC's list"
    return files


def named_pois(raw: dict) -> list[str]:
    ids: list[str] = []
    for item in raw["items"]:
        match = item["match"]
        ids += [match[key] for key in ("poi", "from_poi", "to_poi") if key in match]
        ids += match.get("pois", [])
    return ids


class TestTheCommittedFiles:
    def test_every_file_is_named_for_its_id_and_filed_under_its_org(self):
        for path, raw in committed():
            assert raw is not None, f"{path} is not valid JSON"
            assert path.stem == raw["id"], f"{path} carries id {raw['id']}"
            assert path.parent.name == raw["org"], f"{path} carries org {raw['org']}"

    def test_every_item_has_a_title_unless_it_is_a_mystery(self):
        for path, raw in committed():
            untitled = [i["id"] for i in raw["items"] if not (i.get("title") or "").strip() and "mystery" not in i]
            assert untitled == [], f"{path.name}: {untitled}"

    def test_the_atc_list_is_a_draft(self):
        # The maintainer's poll, 2026-09-30: a draft publishes labelled and
        # takes no entries, until the ATC confirms the list and its terms.
        raw = json.loads((exporter.REFERENCE_DIR / "atc" / "atc-summer-bucket-list-2027.json").read_text(encoding="utf-8"))
        assert raw["status"] == "draft"

    def test_the_anchors_block_names_exactly_the_pois_the_items_use(self):
        # `anchors` is a reviewer aid the resolver ignores - so nothing but
        # this keeps the names a reviewer reads in step with the ids that
        # publish.
        for path, raw in committed():
            if "anchors" in raw:
                assert set(raw["anchors"]) == set(named_pois(raw)), path.name


def test_the_real_committed_files_publish_when_their_anchors_exist():
    """End to end against the committed files, with the POIs stubbed.

    The miles and coordinates are invented and the assertion is not about
    them. It is that every row somebody reviewed is well formed enough to
    reach the artifact once export_poi.py and export_trails.py have run -
    against the real publishers.json and the real sources.json. Measured
    against the live data by the design's author (2026-09-30, release
    2026-09-24-2): all 100 ATC items resolve with zero drops; this is the
    same claim, re-runnable without the bucket.
    """
    files = committed()
    raws = [raw for _, raw in files]
    ids = sorted({poi_id for raw in raws for poi_id in named_pois(raw)})
    wanted_types = sorted({i["match"]["type"] for raw in raws for i in raw["items"] if i["match"]["kind"] == "poi_type"})

    def stub(n: int, poi_id: str, poi_type: str) -> dict:
        # 0.1 degree apart, twice the distance index's grid cell, so a stub
        # with no vertex beside it reads as infinitely far from the trail.
        return {
            "id": poi_id,
            "trail_id": "AT",
            "poi_type": poi_type,
            "name": f"stub {n}",
            "mile": float(n * 10),
            "lat": 34.6 + n * 0.1,
            "lon": -84.2 + n * 0.1,
        }

    pois = []
    for poi_id in ids:
        layer = poi_id.split(":")[0]
        assert layer in POI_TYPE_BY_LAYER, f"{poi_id}: add its layer's poi_type to POI_TYPE_BY_LAYER"
        pois.append(stub(len(pois), poi_id, POI_TYPE_BY_LAYER[layer]))
    # Any type a poi_type item asks for gets one POI, so "a published type"
    # holds whichever types the reviewed files choose.
    for poi_type in wanted_types:
        if not any(p["poi_type"] == poi_type for p in pois):
            pois.append(stub(len(pois), f"stub:{poi_type}", poi_type))

    # A vertex ~2 m east of every stub EXCEPT the towns. The rule is the ATC
    # file's own README - "TOWNS ARE OFF THE TRAIL AND SAY SO" - and it comes
    # from outside the file on purpose: an item naming an ATC Community that
    # forgot `off_trail` finds no vertex within a grid cell and drops here.
    centerline = [[(p["lon"] + 0.00002, p["lat"]) for p in pois if p["id"].split(":")[0] not in TOWN_LAYERS]]

    org_trails, refused = exporter.publisher_scope(exporter.load_publishers(), exporter.load_organizations(), pois)
    output, resolution = exporter.build_output(
        files,
        org_domains=exporter.publisher_domains(exporter.load_publishers()),
        org_trails=org_trails,
        organizations=exporter.load_organizations(),
        pois=pois,
        centerline=centerline,
        today=TODAY,
    )

    assert refused == []
    assert resolution.dropped == []
    assert resolution.dropped_items == []
    assert len(output["challenges"]) == len(files)

    atc = next(c for c in output["challenges"] if c["id"] == "atc-summer-bucket-list-2027")
    assert len(atc["items"]) == 100
    assert atc["status"] == "draft"
    assert (atc["org_name"], atc["org_short"]) == ("Appalachian Trail Conservancy", "ATC")
    # The three mystery items carry no title in the file, so none ships.
    mysteries = [i for i in atc["items"] if "mystery" in i]
    assert len(mysteries) == 3
    assert all(i["title"] is None and "sealed_title" not in i for i in mysteries)
    # And it serializes the way main() writes it.
    json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False)


class TestPublisherDomain:
    def test_a_row_with_no_domain_is_refused(self):
        scope, refused = exporter.publisher_scope([{"org": "atc", "trails": ["AT"], "why": "x"}], ORGANIZATIONS, [KNOB])

        assert scope == {}
        assert refused == ["atc: the row gives no web `domain` (like appalachiantrail.org)"]

    def test_every_challenge_carries_its_publishers_domain_lower_cased(self):
        """What an entry carries back, and what the backend makes a club prove."""
        output, _ = build([(Path("atc/summer-list.json"), challenge())])

        assert {c["org_domain"] for c in output["challenges"]} == {"appalachiantrail.org"}

    def test_the_committed_publishers_file_names_a_domain_for_every_row(self):
        rows = exporter.load_publishers()
        assert all(exporter.publisher_domain(row) for row in rows)
