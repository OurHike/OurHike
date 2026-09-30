"""A poll to the maintainer carries a picture, and the hook that says so when it did not (#1566).

WHY THIS SUITE. `.claude/hooks/visual_poll.py` is repository configuration in
the same sense `session-start.sh` is (test_session_start_hook.py says why that
one lives here): it decides what a session is told after every poll and at
every start, and no other tree owns it.

WHAT IS HELD. The maintainer chose, by poll on 2026-09-17, a hook that lets a
picture-less poll through and tells the session afterwards - over one that
refuses the poll. So the two properties worth a red test are the two a later
edit could quietly flip: what counts as a picture (an option `preview`, a named
side-panel file, or the `No visual: <why>` line - and a bare `No visual:` is
not one), and that the check never blocks or fails the poll, whatever it is
handed. The rest is wiring: settings.json runs the check after every
AskUserQuestion and the reminder at startup, resume and compaction, and the
paths the hook names exist.

Fixture-driven, like test_night_queue.py: the rule is a pure function of the
poll's input, and a test that needed a live session would never run in CI.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / ".claude" / "hooks" / "visual_poll.py"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
sys.path.insert(0, str(HOOK.parent))

import visual_poll  # noqa: E402


def poll(question="Badge or ring?", options=("A badge", "A ring"), previews=(), header="Water card"):
    """One poll in the shape AskUserQuestion is given: `previews` pairs with `options` by position."""
    return [
        {
            "question": question,
            "header": header,
            "multiSelect": False,
            "options": [
                {"label": label, "description": f"{label}, described", **({"preview": previews[i]} if i < len(previews) else {})}
                for i, label in enumerate(options)
            ],
        }
    ]


def run_check(event):
    stdin = event if isinstance(event, str) else json.dumps(event)
    return subprocess.run([sys.executable, str(HOOK), "check"], input=stdin, capture_output=True, text=True)


class TestWhatCountsAsAPicture:
    def test_a_poll_with_words_alone_is_the_case_the_hook_exists_for(self):
        ok, why = visual_poll.verdict(poll())

        assert ok is False
        assert "`preview`" in why and "side panel" in why and "`No visual: <why>`" in why

    def test_an_option_preview_counts(self):
        ok, why = visual_poll.verdict(poll(previews=("```\n[ badge ]\n```",)))

        assert ok is True
        assert why == "an option carries a preview"

    def test_a_blank_preview_does_not_count(self):
        ok, _ = visual_poll.verdict(poll(previews=("   ",)))

        assert ok is False

    def test_a_side_panel_file_named_in_the_question_counts(self):
        ok, why = visual_poll.verdict(poll(question="See water-card-mock.html: badge or ring?"))

        assert ok is True
        assert why == "the question names water-card-mock.html"

    def test_a_screenshot_named_in_an_option_description_counts_too(self):
        questions = poll()
        questions[0]["options"][1]["description"] = "the ring, as in legend.png"

        ok, why = visual_poll.verdict(questions)

        assert ok is True
        assert why == "the question names legend.png"

    def test_a_code_file_named_in_the_question_is_not_a_picture(self):
        ok, _ = visual_poll.verdict(poll(question="Should staleness.ts keep FRESH_MAX_DAYS at 14?"))

        assert ok is False

    def test_the_no_visual_line_with_a_reason_counts(self):
        ok, why = visual_poll.verdict(poll(question="Which branch name? No visual: this is a name, nothing renders."))

        assert ok is True
        assert why == "the question says `No visual:` and why"

    def test_the_no_visual_line_is_read_in_any_case(self):
        ok, _ = visual_poll.verdict(poll(question="no visual: the choice is a cron schedule"))

        assert ok is True

    def test_a_bare_no_visual_with_no_reason_does_not_count(self):
        """The reason is the answer. `No visual:` alone is the section left blank."""
        ok, _ = visual_poll.verdict(poll(question="Which branch name? No visual:"))

        assert ok is False

    def test_a_malformed_poll_is_read_as_wordy_rather_than_crashing(self):
        ok, _ = visual_poll.verdict([None, "text", {"options": [None, {"preview": 3}]}])

        assert ok is False


class TestTheCheckNeverBlocksThePoll:
    def test_a_wordy_poll_gets_one_paragraph_of_context_and_exit_0(self):
        result = run_check({"tool_name": "AskUserQuestion", "tool_input": {"questions": poll()}})

        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        context = out["hookSpecificOutput"]["additionalContext"]
        assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "#1566" in context and visual_poll.SKILL in context
        assert "No visual: <why>" in context
        assert "decision" not in out and "permissionDecision" not in result.stdout, "the maintainer chose let-it-through"

    def test_a_poll_with_a_picture_gets_silence(self):
        result = run_check({"tool_name": "AskUserQuestion", "tool_input": {"questions": poll(question="See mock.html")}})

        assert result.returncode == 0
        assert result.stdout == ""

    def test_another_tool_gets_silence(self):
        result = run_check({"tool_name": "Bash", "tool_input": {"command": "ls"}})

        assert (result.returncode, result.stdout) == (0, "")

    def test_unreadable_input_gets_silence_not_a_failure(self):
        """A hook that fails on a poll the maintainer already answered would be worse than no hook."""
        result = run_check("this is not json")

        assert (result.returncode, result.stdout) == (0, "")

    def test_an_unknown_mode_is_the_one_thing_that_exits_non_zero(self):
        result = subprocess.run([sys.executable, str(HOOK), "refuse"], capture_output=True, text=True)

        assert result.returncode == 2
        assert "usage" in result.stderr


class TestTheReminder:
    def test_remind_prints_one_line_naming_the_issue_the_skill_and_the_exemption(self):
        result = subprocess.run([sys.executable, str(HOOK), "remind"], capture_output=True, text=True)

        assert result.returncode == 0
        lines = result.stdout.strip().splitlines()
        assert len(lines) == 1, lines
        assert "#1566" in lines[0] and visual_poll.SKILL in lines[0]
        assert "night-shift" in lines[0]


def _commands(entry):
    return " ".join(hook["command"] for hook in entry["hooks"])


class TestTheWiring:
    def test_settings_run_the_check_after_every_poll(self):
        hooks = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]
        checks = [entry for entry in hooks["PostToolUse"] if 'visual_poll.py" check' in _commands(entry)]

        assert len(checks) == 1, hooks["PostToolUse"]
        assert re.fullmatch(checks[0]["matcher"], "AskUserQuestion")

    def test_settings_run_the_reminder_at_startup_resume_and_compaction(self):
        hooks = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]
        reminders = [entry for entry in hooks["SessionStart"] if 'visual_poll.py" remind' in _commands(entry)]

        assert len(reminders) == 1, hooks["SessionStart"]
        for kind in ("startup", "resume", "compact"):
            assert re.fullmatch(reminders[0]["matcher"], kind), f"the reminder must fire on {kind}"

    def test_the_provisioning_hook_is_still_registered(self):
        """Adding a second SessionStart entry must not displace the one that installs the suites (#822)."""
        hooks = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]

        assert any("session-start.sh" in _commands(entry) for entry in hooks["SessionStart"])

    def test_the_skill_the_hook_points_at_exists_and_is_named_from_claude_md(self):
        skill = REPO_ROOT / visual_poll.SKILL

        assert skill.is_file(), visual_poll.SKILL
        assert skill.read_text(encoding="utf-8").startswith("---\nname: visual-poll\n")
        claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        assert visual_poll.SKILL in claude_md
        assert ".claude/hooks/visual_poll.py" in claude_md
