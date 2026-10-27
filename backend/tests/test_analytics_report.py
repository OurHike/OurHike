"""The usage report's mask (#1902, app/core/analytics_report.py).

"A mask at runtime though. Dont mess with the data" (the maintainer, poll
2026-10-27): the stored figures stay exact, and every report masks the same
way when it is built. The test that matters most is the last one here - a
masked figure is not merely hidden by the page, it is not in the file at all.
"""

import importlib.util
from datetime import date
from pathlib import Path

import pytest

from app.core.analytics_report import K_FLOOR, build_report_data, mask_cells
from app.models.analytics import AnalyticsMonth, AnalyticsMonthly, AnalyticsUser, MonthStatus

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "usage_report.py"
OCTOBER = date(2026, 10, 1)


@pytest.fixture(scope="module")
def report_script():
    spec = importlib.util.spec_from_file_location("usage_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_cell_describing_fewer_than_the_floor_is_masked_whole():
    masked, whole = mask_cells({"2026-10|GMC|*": {"devices_active": K_FLOOR - 1, "plans_made": 3.5, "map_views": 40}})

    assert masked["2026-10|GMC|*"] == {"devices_active": None, "plans_made": None, "map_views": None}
    assert whole == {"2026-10|GMC|*"}


def test_a_cell_at_the_floor_is_shown():
    masked, whole = mask_cells({"2026-10|*|*": {"devices_active": K_FLOOR, "plans_made": 4}})

    assert masked["2026-10|*|*"]["plans_made"] == 4 and not whole


def test_a_small_count_of_hikers_who_said_yes_is_masked_inside_a_shown_cell():
    masked, _ = mask_cells({"2026-10|*|*": {"devices_active": 900, "hikers_active": 12, "map_views": 3000}})

    assert masked["2026-10|*|*"]["hikers_active"] is None
    assert masked["2026-10|*|*"]["map_views"] == 3000


def test_a_count_of_nobody_stays_zero():
    masked, _ = mask_cells({"2026-10|*|*": {"devices_active": 900, "plan_hikers": 0}})

    assert masked["2026-10|*|*"]["plan_hikers"] == 0


def test_one_hidden_club_takes_the_next_smallest_with_it():
    """Otherwise the hidden club could be had by subtracting the others from the total."""
    cells = {
        "2026-10|*|*": {"devices_active": 500},
        "2026-10|NYNJTC|*": {"devices_active": 300},
        "2026-10|PATC|*": {"devices_active": 60},
        "2026-10|GMC|*": {"devices_active": 9},
    }

    _, whole = mask_cells(cells)

    assert whole == {"2026-10|GMC|*", "2026-10|PATC|*"}


def test_two_hidden_clubs_need_no_third():
    cells = {
        "2026-10|*|*": {"devices_active": 500},
        "2026-10|NYNJTC|*": {"devices_active": 300},
        "2026-10|GMC|*": {"devices_active": 9},
        "2026-10|RATC|*": {"devices_active": 4},
    }

    _, whole = mask_cells(cells)

    assert whole == {"2026-10|GMC|*", "2026-10|RATC|*"}


def test_one_hidden_platform_takes_the_next_smallest_with_it():
    cells = {
        "2026-10|*|*": {"devices_active": 300},
        "2026-10|*|ios": {"devices_active": 200},
        "2026-10|*|android": {"devices_active": 90},
        "2026-10|*|web": {"devices_active": 10},
    }

    _, whole = mask_cells(cells)

    assert whole == {"2026-10|*|web", "2026-10|*|android"}


def _month_with_a_small_club(db_session):
    db_session.add(AnalyticsMonth(month=OCTOBER, status=MonthStatus.provisional, definition_version=1))
    for club, devices, miles in (("*", 400, 5000.0), ("NYNJTC", 300, 4300.0), ("PATC", 80, 650.5), ("GMC", 9, 271.75)):
        db_session.add(AnalyticsMonthly(month=OCTOBER, metric="devices_active", club=club, platform="*", value=devices))
        db_session.add(AnalyticsMonthly(month=OCTOBER, metric="plan_miles", club=club, platform="*", value=miles))
    db_session.commit()


def test_the_report_data_carries_no_figure_for_a_masked_cell(db_session):
    _month_with_a_small_club(db_session)

    data = build_report_data(db_session, environment="Test")

    assert data["cells"]["2026-10|GMC|*"] == {"devices_active": None, "plan_miles": None}
    assert data["cells"]["2026-10|*|*"]["plan_miles"] == 5000.0


def test_a_masked_figure_is_not_anywhere_in_the_written_file(db_session, report_script):
    """Not hidden by the page's script: absent. A copy forwarded to a club
    cannot be read past the mask with view-source."""
    _month_with_a_small_club(db_session)

    html = report_script.render(build_report_data(db_session, environment="Test"))

    assert "271.75" not in html
    assert "650.5" not in html, "PATC is hidden with GMC, or GMC is total minus the others"
    assert "4300" in html, "the shown figures are in the file, which is what makes the test above mean something"


def test_cohorts_hide_a_cohort_smaller_than_the_floor(db_session):
    db_session.add(AnalyticsMonth(month=OCTOBER, status=MonthStatus.provisional, definition_version=1))
    for index in range(3):
        db_session.add(
            AnalyticsUser(
                user_key=f"{index:032d}",
                first_seen_on=date(2026, 9, 2),
                last_seen_on=date(2026, 10, 2),
                first_platform="ios",
                last_platform="ios",
                active_months=[202609, 202610],
            )
        )
    db_session.commit()

    data = build_report_data(db_session, environment="Test")

    september = next(row for row in data["cohorts"] if row["cohort"] == "2026-09")
    assert september["size"] is None and september["retained"] == [None]
    assert data["users"]["hikers"] is None


def test_an_empty_database_builds_an_empty_report(db_session, report_script):
    html = report_script.render(build_report_data(db_session, environment="Test"))

    assert '"months":[]' in html


def test_the_page_template_holds_its_data_slot_exactly_once(report_script):
    assert report_script.TEMPLATE.read_text(encoding="utf-8").count(report_script.PLACEHOLDER) == 1


def test_no_value_can_close_the_data_block_early(report_script):
    html = report_script.render({"months": [], "note": "</script><script>alert(1)</script>"})

    assert "</script><script>alert" not in html


def test_the_report_refuses_to_be_written_into_the_repository(report_script, tmp_path):
    inside = Path(__file__).resolve().parents[2] / "usage-report.html"

    assert report_script.main(["--out", str(inside)]) == 2
    assert not inside.exists()
