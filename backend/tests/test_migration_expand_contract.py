"""Expand and contract across two releases, never both in one (#374, surface 4).

RELEASING.md §8c: "a column dropped in the same release that stops writing it
breaks the previous release, which is still running during the rollout. It is
a rollback rule as much as a compatibility one (§11b)."

Two rules, both read statically off the revision files. No database: these are
properties of what a revision *says*, and a test that needed Postgres to state
them would be slower and no more true.

WHAT THE EXISTING MIGRATION TESTS ALREADY COVER, AND WHAT THEY DO NOT

test_migrations.py runs the chain up and back down, and test_migration_rls.py
checks every table ends up locked. Neither can catch a revision whose
`downgrade` forgets one of its own columns, and the reason is worth writing
down because it is not obvious: downgrading to *base* drops the whole table in
the initial revision anyway. So a `d4a91c3e7b25` that added `mile` and forgot
to drop it would downgrade cleanly to base and pass, while a rollback of that
one revision - the operation an actual incident performs - left a column
behind. Per-revision symmetry is invisible to a whole-chain test.

WHY THIS IS REVISION GRANULARITY AND NOT RELEASE GRANULARITY

The rule as §8c states it is about releases, and this repository has cut none
- `git tag -l` is empty. A revision is the finest boundary that exists today
and a strict subset of the real rule: a single revision that both adds a
replacement column and drops the one it replaces is an expand and a contract
in one step under any definition of release. When releases exist, this file
grows a release-boundary check rather than changing meaning.
"""

import ast
import pathlib

import pytest

VERSIONS_DIR = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _revision_files() -> list[pathlib.Path]:
    return sorted(path for path in VERSIONS_DIR.glob("*.py") if not path.name.startswith("__"))


def _op_calls(function: ast.FunctionDef) -> list[tuple[str, str | None]]:
    """Every `op.<name>(<first arg>)` in `function`, as (name, first literal arg).

    The first positional argument is the table for `add_column`/`drop_column`
    and the table name for `create_table`/`drop_table`, which is all the
    identity these rules need. A non-literal first argument yields None rather
    than raising - a revision computing a table name is unusual enough that
    refusing to guess is better than guessing.
    """
    calls: list[tuple[str, str | None]] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "op":
            continue
        first: str | None = None
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            first = node.args[0].value
        calls.append((node.func.attr, first))
    return calls


def _functions(path: pathlib.Path) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(path.read_text())
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def _column_name(node: ast.Call) -> str | None:
    """The column a `drop_column` names, or the one an `add_column` builds."""
    if len(node.args) < 2:
        return None
    target = node.args[1]
    if isinstance(target, ast.Constant) and isinstance(target.value, str):
        return target.value
    # `sa.Column("name", ...)` - the added case.
    if isinstance(target, ast.Call) and target.args:
        first = target.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def _columns_touched(function: ast.FunctionDef, op_name: str) -> set[tuple[str, str]]:
    touched: set[tuple[str, str]] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "op":
            continue
        if node.func.attr != op_name:
            continue
        table = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else None
        column = _column_name(node)
        if isinstance(table, str) and column is not None:
            touched.add((table, column))
    return touched


@pytest.fixture(scope="module")
def revisions() -> list[pathlib.Path]:
    found = _revision_files()
    # The guard that keeps every test below from passing vacuously: an empty
    # glob compares clean against every rule there is. Same principle
    # test_preferences_contract.py states - never pass by failing to find the
    # files.
    assert len(found) >= 4, f"expected the revision chain, found {[p.name for p in found]}"
    return found


def test_every_revision_undoes_exactly_what_it_does(revisions):
    """A rollback of ONE revision must leave nothing behind.

    Not covered by test_migrations.py's downgrade-to-base: that drops every
    table in the initial revision, so a forgotten `drop_column` in a later
    downgrade is invisible to it and visible here.

    **Compared per column, not per operation name.** Asking only whether the
    word `drop_column` appears somewhere in `downgrade` is the version of this
    check that does not work, and it is the version I wrote first: a revision
    adding three columns and dropping two of them on the way back passes it,
    because `drop_column` is certainly present. Sets, so the third column is
    the thing that fails.
    """
    unbalanced: list[str] = []

    for path in revisions:
        functions = _functions(path)
        upgrade, downgrade = functions.get("upgrade"), functions.get("downgrade")
        if upgrade is None or downgrade is None:
            unbalanced.append(f"{path.name}: missing upgrade or downgrade")
            continue

        left_behind = _columns_touched(upgrade, "add_column") - _columns_touched(downgrade, "drop_column")
        for table, column in sorted(left_behind):
            unbalanced.append(f"{path.name}: adds {table}.{column}, and downgrade does not drop it")

        # Tables, on the same rule. `create_table`'s first argument is the
        # name, so the pairing is one level simpler than columns.
        created = {target for name, target in _op_calls(upgrade) if name == "create_table" and target}
        removed = {target for name, target in _op_calls(downgrade) if name == "drop_table" and target}
        for table in sorted(created - removed):
            unbalanced.append(f"{path.name}: creates table {table!r}, and downgrade does not drop it")

    assert unbalanced == []


def test_no_revision_adds_and_drops_a_column_on_one_table(revisions):
    """An expand and a contract in a single step.

    The shape this catches is a rename done honestly - add the new column,
    drop the old one - which is correct across two releases and breaks the
    running previous release when it lands as one.
    """
    violations: list[str] = []

    for path in revisions:
        upgrade = _functions(path).get("upgrade")
        if upgrade is None:
            continue
        added = _columns_touched(upgrade, "add_column")
        dropped = _columns_touched(upgrade, "drop_column")
        tables_both = {table for table, _ in added} & {table for table, _ in dropped}
        for table in sorted(tables_both):
            violations.append(
                f"{path.name}: adds {sorted(c for t, c in added if t == table)} and drops "
                f"{sorted(c for t, c in dropped if t == table)} on {table!r} in one revision"
            )

    assert violations == []


def test_a_contract_only_revision_drops_nothing_the_models_still_declare(revisions):
    """A column removed from the database while the ORM still maps it takes
    the app down on the next query, which is the failure that arrives before
    anybody thinks about rollout order."""
    from app.db.base import Base

    mapped = {(table.name, column.name) for table in Base.metadata.tables.values() for column in table.columns}

    still_mapped: list[str] = []
    for path in revisions:
        upgrade = _functions(path).get("upgrade")
        if upgrade is None:
            continue
        for table, column in sorted(_columns_touched(upgrade, "drop_column")):
            if (table, column) in mapped:
                still_mapped.append(f"{path.name}: drops {table}.{column}, which the models still declare")

    assert still_mapped == []


# --- Proof the rules can fail --------------------------------------------
#
# Every assertion above passes on today's chain, which means none of them
# would notice being turned off. These run the same logic over hand-written
# revisions that break each rule.


def _write(tmp_path: pathlib.Path, name: str, body: str) -> pathlib.Path:
    path = tmp_path / name
    path.write_text(body)
    return path


def test_the_symmetry_rule_would_catch_a_forgotten_drop(tmp_path):
    path = _write(
        tmp_path,
        "abc123_forgetful.py",
        "import sqlalchemy as sa\nfrom alembic import op\n"
        "def upgrade():\n    op.add_column('reports', sa.Column('mile', sa.Float()))\n"
        "def downgrade():\n    pass\n",
    )
    functions = _functions(path)

    left_behind = _columns_touched(functions["upgrade"], "add_column") - _columns_touched(functions["downgrade"], "drop_column")

    assert left_behind == {("reports", "mile")}


def test_the_symmetry_rule_would_catch_a_PARTIALLY_forgotten_drop(tmp_path):
    """The case that got past the first version of this check.

    Three columns added, two dropped on the way back. An op-name check sees
    `drop_column` in the downgrade and is satisfied; only the set difference
    names the third.
    """
    path = _write(
        tmp_path,
        "abc124_nearly.py",
        "import sqlalchemy as sa\nfrom alembic import op\n"
        "def upgrade():\n"
        "    op.add_column('closures', sa.Column('closed_since', sa.DateTime()))\n"
        "    op.add_column('closures', sa.Column('expected_reopen', sa.DateTime()))\n"
        "    op.add_column('closures', sa.Column('reroute_url', sa.String()))\n"
        "def downgrade():\n"
        "    op.drop_column('closures', 'expected_reopen')\n"
        "    op.drop_column('closures', 'closed_since')\n",
    )
    functions = _functions(path)

    undone = [name for name, _ in _op_calls(functions["downgrade"])]
    left_behind = _columns_touched(functions["upgrade"], "add_column") - _columns_touched(functions["downgrade"], "drop_column")

    # The weaker rule is satisfied; the real one is not. Both asserted, so
    # this test documents the difference rather than only exercising it.
    assert "drop_column" in undone
    assert left_behind == {("closures", "reroute_url")}


def test_the_one_step_rule_would_catch_a_rename(tmp_path):
    path = _write(
        tmp_path,
        "def456_rename.py",
        "import sqlalchemy as sa\nfrom alembic import op\n"
        "def upgrade():\n"
        "    op.add_column('closures', sa.Column('closed_at', sa.DateTime()))\n"
        "    op.drop_column('closures', 'closed_since')\n"
        "def downgrade():\n"
        "    op.add_column('closures', sa.Column('closed_since', sa.DateTime()))\n"
        "    op.drop_column('closures', 'closed_at')\n",
    )
    upgrade = _functions(path)["upgrade"]

    added = _columns_touched(upgrade, "add_column")
    dropped = _columns_touched(upgrade, "drop_column")

    assert added == {("closures", "closed_at")}
    assert dropped == {("closures", "closed_since")}
    assert {t for t, _ in added} & {t for t, _ in dropped} == {"closures"}
