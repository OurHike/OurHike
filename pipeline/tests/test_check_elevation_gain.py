"""Tests for check_elevation_gain.py - does the chosen dead band actually
agree with figures somebody else published?

Why this exists
---------------
The threshold in lib/elevation_gain.py is derived from the DEM's error, not
fitted to the answer, and that distinction is only worth anything if something
checks it. The trap this harness has to avoid is the one the issue names:
tuning until the end-to-end total reads 510,000 produces a number that agrees
with the consensus by construction and means nothing.

So the tests below are mostly about the harness's honesty rather than its
arithmetic - that an empty reference table fails rather than passes, that a
single whole-trail figure never gates, and that a section outside tolerance is
reported as a failure rather than averaged away against the ones that passed.
"""

import json

import pytest

import check_elevation_gain


@pytest.fixture
def profile(tmp_path):
    """A synthetic profile with a known answer: three 1,000 ft climbs, and
    jitter far too small to confirm a turning point."""
    records = []
    mile = 0.0
    elevation = 1000.0
    for _ in range(3):
        for step in range(101):
            records.append({"distance_mi": round(mile, 4), "elevation_ft": elevation + step * 10})
            mile += 0.01
        for step in range(101):
            records.append({"distance_mi": round(mile, 4), "elevation_ft": elevation + 1000 - step * 10})
            mile += 0.01
    path = tmp_path / "elevation_profile.json"
    path.write_text(json.dumps(records))
    return path


@pytest.fixture
def reference(tmp_path):
    def write(payload):
        path = tmp_path / "published_gain.json"
        path.write_text(json.dumps(payload))
        return path

    return write


def test_an_empty_reference_table_fails_rather_than_passes(profile, reference, capsys):
    """The load-bearing one. A harness that reported success with nothing to
    compare against would make an underived threshold look validated, which is
    worse than having no harness - the whole point is that a gain figure can
    agree with a consensus by construction."""
    path = reference({"whole_trail": None, "sections": []})

    assert check_elevation_gain.main(["--profile", str(profile), "--reference", str(path)]) == 1
    assert "derived, not validated" in capsys.readouterr().out


def test_the_whole_trail_figure_alone_never_gates(profile, reference, capsys):
    """One scalar against one free parameter is not a test: some threshold
    always hits it. It is reported, and it does not decide anything."""
    path = reference(
        {
            "whole_trail": {"published_gain_ft": 1, "source": "deliberately absurd"},
            "sections": [],
        }
    )

    result = check_elevation_gain.main(["--profile", str(profile), "--reference", str(path)])

    # Wildly wrong on the whole-trail figure, and the failure is still the
    # missing sections rather than that comparison.
    assert result == 1
    assert "No published section figures" in capsys.readouterr().out


def test_sections_that_agree_pass(profile, reference):
    path = reference(
        {
            "sections": [
                {
                    "name": "first climb",
                    "start_mi": 0.0,
                    "end_mi": 1.0,
                    "published_gain_ft": 1000,
                    "source": "synthetic",
                }
            ]
        }
    )

    assert check_elevation_gain.main(["--profile", str(profile), "--reference", str(path)]) == 0


def test_a_section_outside_tolerance_fails_and_is_named(profile, reference, capsys):
    """Named, not just counted. "One section is off" and "the Whites are off"
    are different amounts of help."""
    path = reference(
        {
            "sections": [
                {
                    "name": "the Whites",
                    "start_mi": 0.0,
                    "end_mi": 1.0,
                    "published_gain_ft": 5000,
                    "source": "synthetic",
                }
            ]
        }
    )

    assert check_elevation_gain.main(["--profile", str(profile), "--reference", str(path)]) == 1
    assert "the Whites" in capsys.readouterr().out


def test_one_bad_section_is_not_averaged_away_by_good_ones(profile, reference):
    """Every section has to agree at the same threshold. Rolling them into a
    mean would let a threshold that is badly wrong somewhere pass by being
    right elsewhere - which is precisely the failure per-section checking
    exists to catch."""
    path = reference(
        {
            "sections": [
                {"name": "good", "start_mi": 0.0, "end_mi": 1.0, "published_gain_ft": 1000, "source": "s"},
                {"name": "bad", "start_mi": 2.0, "end_mi": 3.0, "published_gain_ft": 100, "source": "s"},
            ]
        }
    )

    assert check_elevation_gain.main(["--profile", str(profile), "--reference", str(path)]) == 1


def test_a_missing_profile_is_its_own_exit_code(tmp_path, reference):
    """Distinct from "the threshold is wrong": nothing has been measured at
    all, and a caller that conflated the two would report a data problem when
    export_elevation.py simply has not been run."""
    path = reference({"sections": []})

    assert check_elevation_gain.main(["--profile", str(tmp_path / "absent.json"), "--reference", str(path)]) == 2


def test_the_sweep_shows_the_raw_sum_and_the_chosen_one(profile, reference, capsys):
    """The comparison is the argument. A run that printed only the corrected
    figure would be asking to be trusted rather than showing its working."""
    path = reference({"sections": []})

    check_elevation_gain.main(["--profile", str(profile), "--reference", str(path)])

    out = capsys.readouterr().out
    assert "raw (every rise summed)" in out
    assert "threshold sweep" in out
    assert "<- chosen" in out


def test_a_missing_reference_file_is_treated_as_an_empty_one(profile, tmp_path, capsys):
    """A fresh checkout that has not created the table yet gets the same
    honest "not validated" answer as one holding an empty table, rather than a
    traceback."""
    assert check_elevation_gain.main(["--profile", str(profile), "--reference", str(tmp_path / "none.json")]) == 1
    assert "derived, not validated" in capsys.readouterr().out


def test_the_committed_reference_file_parses_and_declares_no_sections():
    """The shipped table is empty on purpose, and this pins that it is empty
    *deliberately* rather than by a typo that would silently skip the check.
    Delete this test when real sections are added."""
    reference = json.loads(check_elevation_gain.REFERENCE_PATH.read_text())

    assert reference["sections"] == []
    assert reference["whole_trail"]["published_gain_ft"] == 510000


def test_an_unreadable_profile_reports_rather_than_tracebacks(tmp_path, reference):
    """A truncated write is a plausible way for this to be reached, and a
    JSONDecodeError from inside the json module tells a reader nothing about
    which file was bad or what to do about it."""
    broken = tmp_path / "elevation_profile.json"
    broken.write_text("{ not json")
    path = reference({"sections": []})

    assert check_elevation_gain.main(["--profile", str(broken), "--reference", str(path)]) == 2


def test_an_empty_profile_is_read_as_nothing_measured(tmp_path, reference):
    empty = tmp_path / "elevation_profile.json"
    empty.write_text("[]")
    path = reference({"sections": []})

    assert check_elevation_gain.main(["--profile", str(empty), "--reference", str(path)]) == 2


def test_a_stubbed_section_with_no_published_figure_prints_a_dash_and_does_not_gate(profile, reference, capsys):
    """A null published_gain_ft is a stub awaiting its citation. It must
    neither crash the summary (None has no float format) nor be counted as a
    failed comparison - "not validated" and "validated and wrong" are the two
    states this file exists to keep apart."""
    path = reference(
        {
            "sections": [
                {
                    "name": "first climb",
                    "start_mi": 0.0,
                    "end_mi": 1.0,
                    "published_gain_ft": 1000,
                    "source": "synthetic",
                },
                {
                    "name": "stubbed section",
                    "start_mi": 1.0,
                    "end_mi": 2.0,
                    "published_gain_ft": None,
                    "source": "tbd",
                },
            ]
        }
    )

    assert check_elevation_gain.main(["--profile", str(profile), "--reference", str(path)]) == 0
    out = capsys.readouterr().out
    assert "stubbed section" in out
    assert "no published figure yet" in out


def test_a_reference_of_nothing_but_stubs_is_not_a_pass(profile, reference, capsys):
    """All-stubs is the empty table wearing a different shape: nothing has
    been validated, and reporting success would make it look validated."""
    path = reference(
        {
            "sections": [
                {
                    "name": "stubbed section",
                    "start_mi": 0.0,
                    "end_mi": 1.0,
                    "published_gain_ft": None,
                    "source": "tbd",
                }
            ]
        }
    )

    assert check_elevation_gain.main(["--profile", str(profile), "--reference", str(path)]) == 1


def test_an_unreadable_reference_reports_rather_than_tracebacks(profile, tmp_path):
    """The reference gets the same discipline as the profile: a truncated
    write to published_gain.json is a named exit-2, not an anonymous
    JSONDecodeError from inside the json module."""
    broken = tmp_path / "published_gain.json"
    broken.write_text("{ not json")

    assert check_elevation_gain.main(["--profile", str(profile), "--reference", str(broken)]) == 2


# --- step plausibility, and what it does to a section's verdict (#663) -------


@pytest.fixture
def profile_with_a_phantom_climb(tmp_path):
    """The `profile` fixture with one impossible sample spliced into the
    second climb: +2,000 ft between neighbouring samples 0.01 mi (53 ft)
    apart.

    That is the shape #559 measures on real data - all 94 of its too-steep
    steps sit on a centerline part boundary, the largest +2,588 ft across
    25 m - reproduced small enough to reason about.

    Note it yields **two** impossible steps, not one: a single spliced sample
    is a spike, so the profile jumps up and straight back down. Both are
    equally impossible and both are reported; only the rise inflates a gain
    figure, which is what `ascending_total` is for.
    """
    records = []
    mile = 0.0
    elevation = 1000.0
    for climb in range(3):
        for step in range(101):
            records.append({"distance_mi": round(mile, 4), "elevation_ft": elevation + step * 10})
            mile += 0.01
        if climb == 1:
            records.append({"distance_mi": round(mile, 4), "elevation_ft": elevation + 1000 + 2000})
            mile += 0.01
        for step in range(101):
            records.append({"distance_mi": round(mile, 4), "elevation_ft": elevation + 1000 - step * 10})
            mile += 0.01
    path = tmp_path / "elevation_profile.json"
    path.write_text(json.dumps(records))
    return path


def test_a_clean_profile_reports_no_implausible_steps(profile, reference, capsys):
    check_elevation_gain.main(["--profile", str(profile), "--reference", str(reference({}))])

    assert "no step exceeds a 100% grade" in capsys.readouterr().out


def test_the_spacing_is_read_off_the_profile_rather_than_assumed(profile):
    """The ceiling is only meaningful against the spacing the file it is
    measuring actually used - this script is handed profiles it did not
    build, possibly from a run whose interval differed."""
    records = json.loads(profile.read_text())

    # The fixture steps 0.01 mi, which is 52.8 ft.
    assert check_elevation_gain.sample_spacing_ft(records) == pytest.approx(52.8)


def test_a_step_too_steep_to_be_trail_is_reported_with_its_size(profile_with_a_phantom_climb, reference, capsys):
    check_elevation_gain.main(["--profile", str(profile_with_a_phantom_climb), "--reference", str(reference({}))])
    out = capsys.readouterr().out

    # Two: up and straight back down - see the fixture. Only the rise is
    # counted as the over-count.
    assert "2 step(s) too steep to be trail" in out
    assert "2,000 ft of it ascending" in out
    assert "+2,000 ft" in out
    assert "#559" in out


def test_only_the_climbing_half_of_an_impossible_step_counts(profile, reference):
    """Both halves are equally impossible; only the rise inflates a gain
    figure, so only the rise is the over-count."""
    steps = [{"from_mi": 0.0, "to_mi": 0.1, "delta_ft": 900}, {"from_mi": 1.0, "to_mi": 1.1, "delta_ft": -900}]

    assert check_elevation_gain.ascending_total(steps) == 900


def test_a_section_containing_an_impossible_step_is_not_validated(profile_with_a_phantom_climb, reference, capsys):
    """The failure this exists for. The section's measured gain is inflated
    by a geometry fault, so a pass would record the threshold as validated by
    a phantom climb - the exact "agrees by construction" failure
    published_gain.json's README is guarding against."""
    path = reference(
        {
            "sections": [
                {
                    "name": "contaminated",
                    "start_mi": 2.0,
                    "end_mi": 4.1,
                    "published_gain_ft": 3000,
                    "source": "synthetic",
                }
            ]
        }
    )

    exit_code = check_elevation_gain.main(["--profile", str(profile_with_a_phantom_climb), "--reference", str(path)])
    out = capsys.readouterr().out

    # Not a pass, and not a failure either - the third state.
    assert exit_code == 1
    assert "step too steep to be trail" in out
    assert "impossible" in out
    assert "Fix #559" in out


def test_a_contaminated_section_is_not_reported_as_outside_tolerance(profile_with_a_phantom_climb, reference, capsys):
    """Failing it would be as wrong as passing it: somebody would go and tune
    a dead band that is not the problem."""
    path = reference(
        {
            "sections": [
                {
                    "name": "contaminated",
                    "start_mi": 2.0,
                    "end_mi": 4.1,
                    "published_gain_ft": 3000,
                    "source": "synthetic",
                }
            ]
        }
    )

    check_elevation_gain.main(["--profile", str(profile_with_a_phantom_climb), "--reference", str(path)])
    out = capsys.readouterr().out

    assert "outside" not in out
    assert "OFF" not in out


def test_a_clean_section_beside_a_contaminated_one_still_gets_its_verdict(profile_with_a_phantom_climb, reference, capsys):
    """Contamination is scoped to the window that contains the step, not to
    the whole run - otherwise one bad boundary would silence every section."""
    path = reference(
        {
            "sections": [
                {"name": "clean first climb", "start_mi": 0.0, "end_mi": 1.0, "published_gain_ft": 1000, "source": "s"},
                {"name": "contaminated", "start_mi": 2.0, "end_mi": 4.1, "published_gain_ft": 3000, "source": "s"},
            ]
        }
    )

    check_elevation_gain.main(["--profile", str(profile_with_a_phantom_climb), "--reference", str(path)])
    out = capsys.readouterr().out

    assert "ok  clean first climb" in out
    assert "?  contaminated" in out


def test_the_implausible_step_finder_ignores_nulls_rather_than_crashing(tmp_path):
    """A DEM coverage gap is a None, and the step either side of it is not a
    step at all - lib/elevation_gain.py already breaks its runs there."""
    records = [
        {"distance_mi": 0.0, "elevation_ft": 1000.0},
        {"distance_mi": 0.01, "elevation_ft": None},
        {"distance_mi": 0.02, "elevation_ft": 5000.0},
    ]

    assert check_elevation_gain.implausible_steps(records) == []
