"""publish-conditions.yml runs its production leg only from main, whatever a dispatch asks for.

The production leg writes `conditions/` under production's prefix, which every
hiker's phone reads within the hour with no release or review between
(pipeline/ELT.md, "Why a scheduled run cannot reach production", where this
bake is the one exemption). A schedule fires from main alone, but
`workflow_dispatch` runs any ref, with that ref's copy of the workflow, and
#1793 — Rebuild the data platform as dlt → dbt: seven contracted marts, a
monthly refresh, published docs, and lighter phone downloads soaks its new
path by dispatching this workflow from its pull request's branch, hourly, for
seven days (decision 30). Before this guard, that dispatch ran the matrix
`[production, ua]` and published unmerged code to production.

TWO LOCKS, AND THIS FILE HOLDS BOTH.

1. The matrix leaves the production leg out unless `github.ref` is
   `refs/heads/main` and the dispatch did not ask for `ua` alone. That is a
   GitHub expression, so it is checked here by evaluating it, for every
   trigger, ref and input below, with a small evaluator of the expression
   language (`_evaluate`): what the matrix becomes is the claim, not what its
   text looks like.
2. The job's first step refuses a production leg from any other ref, with
   bash's case-sensitive `=`. GitHub's `==` compares strings ignoring case
   (docs.github.com, "Expressions", operators: "GitHub ignores case when
   comparing strings"), so lock 1 alone would let a branch named `Main`
   through. The step's own script is run here under bash for that case.

WHAT THIS DOES NOT COVER. A dispatch runs the named ref's copy of the
workflow, so these locks bind only refs that carry them: a branch cut before
this change still runs both legs if dispatched. Keeping production's keys out
of every branch's reach is a repository setting (an environment whose
deployment-branch rule is main, holding the production secrets), which no
file here can make.
"""

from __future__ import annotations

import json
import re
import subprocess
from itertools import product
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "publish-conditions.yml"
JOB = "publish"
GUARD_STEP = "Refuse a production leg from any ref but main"

MAIN = "refs/heads/main"
# Refs a dispatch can name: a pull request's branch (the soak's own), a tag,
# a branch whose name differs from main's only in case, and one that merely
# starts with main's.
OTHER_REFS = ("refs/heads/claude/intelligent-feynman-sw3ewm", "refs/tags/v1.0.0", "refs/heads/Main", "refs/heads/main-old")
# What `inputs.data_environment` holds: each choice, and None on a schedule,
# which carries no inputs.
INPUTS = ("both", "ua", None)


# --- a small evaluator of GitHub's expression language -----------------------
#
# Enough of docs.github.com's "Evaluate expressions in workflows and actions"
# for the expressions this workflow's matrix uses: string, number, boolean and
# null literals; context lookups (`github.ref`, `inputs.data_environment`);
# `!`, `==`, `!=`, `&&`, `||` and parentheses; and `fromJSON()`. `&&` and `||`
# return one of their operands, as in JavaScript; `==` ignores case between
# two strings, and otherwise coerces both sides to numbers, as the docs'
# coercion table says. Anything else raises, so an expression this cannot read
# fails the test rather than passing it.

TOKEN = re.compile(
    r"\s*(?:(?P<string>'(?:[^']|'')*')|(?P<number>-?\d+(?:\.\d+)?)|(?P<op>==|!=|&&|\|\||[!()])|(?P<name>[A-Za-z_][A-Za-z0-9_.-]*))"
)


def _tokens(text: str) -> list[tuple[str, str]]:
    tokens, position = [], 0
    text = text.strip()
    while position < len(text):
        match = TOKEN.match(text, position)
        if match is None or match.end() == position:
            raise ValueError(f"cannot read {text[position:]!r} in {text!r}")
        kind = match.lastgroup
        tokens.append((kind, match.group(kind)))
        position = match.end()
    return tokens


def _truthy(value) -> bool:
    return value not in (None, False, 0, "") and value == value  # NaN is falsy


def _number(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value) if value.strip() else 0.0
    except ValueError:
        return float("nan")


def _equal(left, right) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    if type(left) is type(right) and not isinstance(left, str):
        return left == right
    return _number(left) == _number(right)


def _evaluate(text: str, context: dict):
    tokens = _tokens(text)
    position = 0

    def peek():
        return tokens[position] if position < len(tokens) else (None, None)

    def take(value=None):
        nonlocal position
        token = peek()
        if value is not None and token[1] != value:
            raise ValueError(f"expected {value!r}, found {token[1]!r} in {text!r}")
        position += 1
        return token

    def primary():
        kind, value = take()
        if value == "(":
            result = either()
            take(")")
            return result
        if value == "!":
            return not _truthy(primary())
        if kind == "string":
            return value[1:-1].replace("''", "'")
        if kind == "number":
            return float(value)
        if kind == "name":
            if value in ("true", "false"):
                return value == "true"
            if value == "null":
                return None
            if peek()[1] == "(":
                take("(")
                argument = either()
                take(")")
                if value.casefold() != "fromjson":
                    raise ValueError(f"no function {value} in this evaluator")
                return json.loads(argument)
            found = context
            for part in value.split("."):
                found = found.get(part) if isinstance(found, dict) else None
            return found
        raise ValueError(f"unexpected {value!r} in {text!r}")

    def comparison():
        left = primary()
        while peek()[1] in ("==", "!="):
            operator = take()[1]
            right = primary()
            left = _equal(left, right) if operator == "==" else not _equal(left, right)
        return left

    def both():
        left = comparison()
        while peek()[1] == "&&":
            take()
            right = comparison()
            left = right if _truthy(left) else left
        return left

    def either():
        left = both()
        while peek()[1] == "||":
            take()
            right = both()
            left = left if _truthy(left) else right
        return left

    result = either()
    if position != len(tokens):
        raise ValueError(f"{text!r} has more after position {position}")
    return result


def _expression(value: str) -> str:
    match = re.fullmatch(r"\s*\$\{\{(.*)\}\}\s*", value, re.S)
    if match is None:
        raise ValueError(f"{value!r} is not one ${{{{ }}}} expression")
    return match.group(1)


# --- the workflow -------------------------------------------------------------


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML reads the bare key `on` as the boolean True.
    return workflow.get("on", workflow.get(True)) or {}


def _legs(ref: str, data_environment: str | None, event: str) -> list[str]:
    """What the publish job's matrix makes of one run's `github` and `inputs`."""
    matrix = _workflow()["jobs"][JOB]["strategy"]["matrix"]
    legs = matrix["data_environment"]
    assert set(matrix) == {"data_environment"}, (
        f"the matrix has {sorted(matrix)}; an include or exclude would add legs this test does not evaluate"
    )
    if isinstance(legs, list):
        return legs
    inputs = {} if data_environment is None else {"data_environment": data_environment}
    return _evaluate(_expression(legs), {"github": {"ref": ref, "event_name": event}, "inputs": inputs})


def _guard(leg: str, ref: str, asked: str | None) -> subprocess.CompletedProcess:
    """The first step's script, run under bash with the env the step gives it."""
    step = _workflow()["jobs"][JOB]["steps"][0]
    env = {"LEG": leg, "REF": ref, "ASKED": asked or "", "PATH": "/usr/bin:/bin"}
    return subprocess.run(["bash", "-e", "-c", step["run"]], env=env, capture_output=True, text=True)


def test_the_evaluator_reads_github_expressions_the_way_github_does():
    """The evaluator is what the matrix assertions stand on, so its four rules
    that matter here are held to the docs' own statements: case-insensitive
    string equality, JavaScript-style `&&`/`||` operands, a missing context
    value as null, and null against a string compared as numbers."""
    assert _evaluate("'refs/heads/Main' == 'refs/heads/main'", {}) is True
    assert _evaluate("'' && 'a' || 'b'", {}) == "b"
    assert _evaluate("'x' && 'a' || 'b'", {}) == "a"
    assert _evaluate("inputs.nothing", {"inputs": {}}) is None
    assert _evaluate("inputs.nothing != 'ua'", {"inputs": {}}) is True
    assert _evaluate("fromJSON('[\"ua\"]')", {}) == ["ua"]
    with pytest.raises(ValueError):
        _evaluate("contains(github.ref, 'main')", {"github": {"ref": MAIN}})


def test_only_a_schedule_and_a_dispatch_start_this_workflow():
    """`github.ref` is main on a schedule and the named ref on a dispatch, and
    both are cases below. A push, a pull request or a call from another
    workflow brings refs and inputs of its own, which this file has not
    reasoned about, so one added here fails until it has."""
    assert set(_triggers(_workflow())) == {"schedule", "workflow_dispatch"}


@pytest.mark.parametrize(("ref", "asked"), list(product(OTHER_REFS, INPUTS)))
def test_a_run_from_any_ref_but_main_never_reaches_the_production_leg(ref, asked):
    """The guard's claim: from a pull request's branch, a tag, `Main` or
    `main-old`, under every input, no production leg runs. Either the matrix
    leaves it out, or the first step fails it before the checkout."""
    legs = _legs(ref, asked, "workflow_dispatch")
    assert "ua" in legs, f"{ref} with data_environment={asked!r} gave {legs}: the UA leg must still run"
    if "production" in legs:
        refused = _guard("production", ref, asked)
        assert refused.returncode != 0, (
            f"{ref} with data_environment={asked!r} gave {legs}, and the first step let the production leg past: "
            f"{refused.stdout}{refused.stderr}"
        )
        assert "Production leg refused" in refused.stdout


def test_a_branch_that_github_reads_as_main_is_stopped_by_the_first_step():
    """`refs/heads/Main` is the case lock 1 cannot see, since GitHub's `==`
    ignores case: the matrix keeps the production leg, and only the bash
    comparison stops it."""
    assert "production" in _legs("refs/heads/Main", "both", "workflow_dispatch")
    assert _guard("production", "refs/heads/Main", "both").returncode != 0


def test_the_schedule_and_a_main_dispatch_run_both_legs_as_today():
    """The production leg is ELT.md's design for this bake, so the guard must
    not take it away from main: the schedule, and a dispatch from main asking
    for both, run both legs, and the first step lets both through."""
    assert _legs(MAIN, None, "schedule") == ["production", "ua"]
    assert _legs(MAIN, "both", "workflow_dispatch") == ["production", "ua"]
    assert _guard("production", MAIN, None).returncode == 0
    assert _guard("ua", MAIN, None).returncode == 0


def test_a_dispatch_can_choose_the_ua_leg_alone_even_from_main():
    """`data_environment: ua` is how a dispatch from main publishes UA and
    leaves production's keys alone; the soak's dispatch from the pull
    request's branch asks the same."""
    assert _legs(MAIN, "ua", "workflow_dispatch") == ["ua"]
    choice = _triggers(_workflow())["workflow_dispatch"]["inputs"]["data_environment"]
    assert choice["type"] == "choice" and "ua" in choice["options"]


def test_the_refusal_is_the_first_step_and_nothing_after_it_runs_regardless():
    """A failed first step skips every later step unless that step asks to run
    anyway. Nothing that reads a conditions database or writes the bucket may
    ask: its `if:` names none of always(), failure() or cancelled(), so a
    refused production leg reads nothing and publishes nothing."""
    steps = _workflow()["jobs"][JOB]["steps"]
    assert steps[0].get("name") == GUARD_STEP
    assert "if" not in steps[0], "the refusal must run on every leg, not only when a condition holds"
    sensitive = [
        step
        for step in steps[1:]
        if "publish.py" in str(step.get("run", ""))
        or "CONDITIONS_DATABASE_URL" in json.dumps(step.get("env") or {})
        or any("R2_" in name for name in (step.get("env") or {}))
    ]
    assert sensitive, "no step reads a conditions database or writes the bucket, so this test checks nothing"
    runs_regardless = [
        step.get("name") for step in sensitive if re.search(r"\b(always|failure|cancelled)\(", str(step.get("if", "")))
    ]
    assert runs_regardless == [], f"these would run after a refused first step: {runs_regardless}"
