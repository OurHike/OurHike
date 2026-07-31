"""Unit tests for lib/completeness.py's shared "did this run actually
produce complete output" gate - see that module's docstring for the
recurring bug pattern this guards against."""

import pytest

from lib.completeness import count_problems, fail_if_incomplete


def test_fail_if_incomplete_is_a_noop_when_problems_is_empty():
    # Should return normally (no exit, no output) rather than raising or
    # printing anything - callers run this unconditionally at the end of
    # main(), so a clean run must fall straight through.
    fail_if_incomplete([])


def test_fail_if_incomplete_prints_and_exits_when_problems_is_non_empty(capsys):
    with pytest.raises(SystemExit) as exc_info:
        fail_if_incomplete(["cell 3: no matching quads", "cell 7: empty/all-nodata merge result"])

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "Incomplete: 2 problem(s):" in out
    assert "  cell 3: no matching quads" in out
    assert "  cell 7: empty/all-nodata merge result" in out


def test_fail_if_incomplete_uses_custom_label(capsys):
    with pytest.raises(SystemExit):
        fail_if_incomplete(["shelter: 0, expected >= 1"], label="Incomplete export")

    out = capsys.readouterr().out
    assert "Incomplete export: 1 problem(s):" in out


def test_count_problems_flags_a_count_below_the_default_minimum():
    problems = count_problems({"shelter": 0, "campsite": 5})

    assert problems == ["shelter: 0, expected >= 1"]


def test_count_problems_respects_a_per_name_minimum_override():
    # crossing is deliberately allowed to be empty for the real AT corridor
    # data, so a per-name override of 0 should suppress the default-minimum
    # flag that would otherwise fire on a zero count.
    problems = count_problems({"crossing": 0, "shelter": 3}, minimums={"crossing": 0})

    assert problems == []


def test_count_problems_does_not_flag_a_count_that_exactly_meets_its_minimum():
    problems = count_problems({"crossing": 0, "shelter": 1}, minimums={"crossing": 0})

    assert problems == []
