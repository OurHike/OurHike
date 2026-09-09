"""plan_release.py - whether this week's data is worth a release (#1314).

The job this drives holds no R2 credentials, so nothing here can change what
a hiker downloads. What it can do is decide not to build when it should have,
which is the failure these tests are mostly about: `lib/freshness_state.py`'s
"the failure that matters is a false FRESH", one job further along.

No real network - requests_mock raises on any unmocked request, and
tests/conftest.py's socket guard raises under that (TESTING.md).
"""

from __future__ import annotations

import json
from datetime import date

import pytest

import plan_release

INDEX_URL = "https://data.ourhike.org/releases/index.json"


def verdict(*sources, checked_at="2026-09-09", age=2):
    """A check_freshness.py --json document with the given (name, freshness)."""
    return {
        "checked_at": checked_at,
        "state_age_days": age,
        "sources": [{"source": name, "freshness": freshness, "detail": f"{name} detail"} for name, freshness in sources],
        "needs_refetch": [name for name, freshness in sources if freshness == "stale"],
        "unknown": [name for name, freshness in sources if freshness == "unknown"],
    }


def index(*release_ids):
    return {"releases": [{"id": rid, "created_at": "x", "version": "v"} for rid in release_ids]}


class TestWhenToBuild:
    def test_everything_fresh_stages_nothing(self):
        document = plan_release.plan(verdict(("atc", "fresh"), ("opentrail", "fresh")), index("2026-09-01"))

        assert document["rebuild"] is False
        assert document["reasons"] == []
        assert document["previous_release"] == "2026-09-01"

    def test_a_stale_source_builds_and_says_which(self):
        document = plan_release.plan(verdict(("atc", "stale"), ("opentrail", "fresh")), index("2026-09-01"))

        assert document["rebuild"] is True
        assert document["reasons"] == ["atc is stale: atc detail"]

    def test_an_unknown_source_builds_too(self):
        """The asymmetry, and the one decision in this file worth arguing with.

        UNKNOWN could reasonably read as "no evidence of change, carry on".
        It does not, because an upstream nobody could reach is not an upstream
        that did not move, and the costs are not symmetric: a needless build
        spends runner minutes, a skipped one ships a map that quietly stopped
        tracking the trail.
        """
        document = plan_release.plan(verdict(("topo_quads", "unknown"), ("atc", "fresh")), index("2026-09-01"))

        assert document["rebuild"] is True
        assert document["reasons"] == ["topo_quads is unknown: topo_quads detail"]

    def test_an_empty_index_always_builds(self):
        """Nothing has ever been staged, so there is no previous release the
        freshness state could have described. Building is the only thing that
        can be true here, whatever the verdict says."""
        document = plan_release.plan(verdict(("atc", "fresh")), None)

        assert document["rebuild"] is True
        assert document["reasons"] == ["no release has been staged yet"]
        assert document["previous_release"] is None

    def test_force_builds_against_a_wholly_fresh_verdict(self):
        document = plan_release.plan(verdict(("atc", "fresh")), index("2026-09-01"), force=True)

        assert document["rebuild"] is True
        assert document["reasons"] == ["force_full_rebuild was requested"]

    def test_the_rebuild_verdicts_are_pinned(self):
        """Spelled as a set rather than `!= fresh`, so a fourth verdict added
        to Freshness later fails here rather than being swept silently into
        one side."""
        assert plan_release.REBUILD_ON == {"stale", "unknown"}


class TestTheReleaseId:
    def test_it_avoids_ids_the_index_already_lists(self):
        document = plan_release.plan(verdict(("atc", "stale")), index("2026-09-09"), today=date(2026, 9, 9))

        assert document["release_id"] == "2026-09-09-2"

    def test_a_fresh_day_takes_the_unsuffixed_id(self):
        document = plan_release.plan(verdict(("atc", "stale")), index("2026-09-08"), today=date(2026, 9, 9))

        assert document["release_id"] == "2026-09-09"


class TestReadingTheIndex:
    def test_a_missing_index_plans_as_a_first_run(self, requests_mock, capsys):
        requests_mock.get(INDEX_URL, status_code=404)

        assert plan_release.load_index(INDEX_URL) is None
        assert "No release index read" in capsys.readouterr().err

    def test_a_host_outside_the_allowlist_is_refused_not_fetched(self, capsys):
        """#173's wall. A dispatch input naming another host must not turn the
        runner into a GET proxy for it - and because requests_mock is not
        primed here, a fetch that got through would raise instead."""
        assert plan_release.load_index("https://example.test/releases/index.json") is None
        assert "not a place a published state lives" in capsys.readouterr().err

    def test_plain_http_is_refused(self, capsys):
        assert plan_release.load_index("http://data.ourhike.org/releases/index.json") is None
        assert "must be https" in capsys.readouterr().err

    def test_no_url_at_all_reads_as_no_index(self):
        assert plan_release.load_index(None) is None

    def test_a_real_index_is_read(self, requests_mock):
        requests_mock.get(INDEX_URL, json=index("2026-09-01", "2026-09-08"))

        assert plan_release.load_index(INDEX_URL) == index("2026-09-01", "2026-09-08")


class TestTheCommandLine:
    def test_it_writes_the_plan_and_the_step_outputs(self, tmp_path, monkeypatch, requests_mock):
        requests_mock.get(INDEX_URL, json=index("2026-09-01"))
        verdict_path = tmp_path / "freshness.json"
        verdict_path.write_text(json.dumps(verdict(("atc", "stale"))))
        plan_path = tmp_path / "out" / "plan.json"
        outputs = tmp_path / "gh_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))

        code = plan_release.main(["--verdict", str(verdict_path), "--index-url", INDEX_URL, "--json", str(plan_path)])

        assert code == 0
        written = json.loads(plan_path.read_text())
        assert written["rebuild"] is True
        assert written["state_age_days"] == 2
        assert "rebuild=true" in outputs.read_text()
        assert f"release_id={written['release_id']}" in outputs.read_text()

    def test_an_unreadable_verdict_is_fatal_rather_than_a_quiet_skip(self, tmp_path, capsys):
        """Unlike a missing index. The verdict is this run's own output from a
        step that just succeeded, so an unreadable one means the run is
        confused about itself - and planning "nothing changed" from it is
        exactly the false FRESH the design exists to prevent."""
        code = plan_release.main(["--verdict", str(tmp_path / "nope.json")])

        assert code == 1
        assert "Could not read the freshness verdict" in capsys.readouterr().err

    def test_a_skip_says_what_it_compared_against(self, tmp_path, requests_mock, capsys):
        requests_mock.get(INDEX_URL, json=index("2026-09-01"))
        verdict_path = tmp_path / "freshness.json"
        verdict_path.write_text(json.dumps(verdict(("atc", "fresh"))))

        assert plan_release.main(["--verdict", str(verdict_path), "--index-url", INDEX_URL]) == 0
        assert "no release to stage" in capsys.readouterr().out


@pytest.mark.parametrize("freshness", ["stale", "unknown"])
def test_every_rebuild_reason_names_its_source_and_its_detail(freshness):
    """The workflow prints these into its job summary, and "rebuild: true"
    with nothing beside it is output people stop reading by the third week."""
    [reason] = plan_release.rebuild_reasons(verdict(("elevation", freshness)))

    assert "elevation" in reason
    assert freshness in reason
    assert "elevation detail" in reason
