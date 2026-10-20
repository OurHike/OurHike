"""check_dbt_packages.py holds dbt_packages/ to dbt/packages.sha256: any file changed, missing or added
fails, and a package's own .git is never part of the comparison."""

from __future__ import annotations

from pathlib import Path

import yaml

import check_dbt_packages as check

PIPELINE = Path(__file__).resolve().parents[1]


def _tree(root: Path) -> Path:
    packages = root / "dbt_packages"
    (packages / "dbt_utils" / "macros").mkdir(parents=True)
    (packages / "dbt_utils" / "macros" / "star.sql").write_text("{% macro star() %}*{% endmacro %}\n", encoding="utf-8")
    (packages / "dbt_utils" / "dbt_project.yml").write_text("name: dbt_utils\n", encoding="utf-8")
    (packages / "elementary").mkdir()
    (packages / "elementary" / "dbt_project.yml").write_text("name: elementary\n", encoding="utf-8")
    return packages


def _run(packages: Path, manifest: Path, *extra: str) -> int:
    return check.main(["--packages-dir", str(packages), "--manifest", str(manifest), *extra])


def test_a_tree_that_matches_its_written_manifest_passes(tmp_path, capsys):
    packages, manifest = _tree(tmp_path), tmp_path / "packages.sha256"
    assert _run(packages, manifest, "--write") == 0
    assert _run(packages, manifest) == 0
    assert "all 3 files match" in capsys.readouterr().out


def test_a_changed_macro_fails_and_names_the_file_with_the_hash_found(tmp_path, capsys):
    packages, manifest = _tree(tmp_path), tmp_path / "packages.sha256"
    _run(packages, manifest, "--write")
    (packages / "dbt_utils" / "macros" / "star.sql").write_text("{{ env_var('R2_SECRET') }}\n", encoding="utf-8")

    assert _run(packages, manifest) == 1
    out = capsys.readouterr().out
    assert "changed   dbt_utils/macros/star.sql" in out and "(pinned " in out


def test_a_file_added_or_removed_fails(tmp_path, capsys):
    packages, manifest = _tree(tmp_path), tmp_path / "packages.sha256"
    _run(packages, manifest, "--write")
    (packages / "elementary" / "dbt_project.yml").unlink()
    (packages / "elementary" / "extra.sql").write_text("select 1\n", encoding="utf-8")

    assert _run(packages, manifest) == 1
    out = capsys.readouterr().out
    assert "missing   elementary/dbt_project.yml" in out and "unpinned  elementary/extra.sql" in out


def test_a_packages_own_git_folder_is_left_out(tmp_path):
    """The dbt skill's sandbox workaround clones each package at its tag; CI's deps writes no .git."""
    packages, manifest = _tree(tmp_path), tmp_path / "packages.sha256"
    _run(packages, manifest, "--write")
    (packages / "dbt_utils" / ".git").mkdir()
    (packages / "dbt_utils" / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    assert _run(packages, manifest) == 0


def _hidden_macro(packages: Path) -> Path:
    """The 2026-10-15 review's probe (workflows.md S2-6): a macro written under a package's own .git, which the check
    leaves out, so no pin covers it."""
    hidden = packages / "dbt_utils" / ".git" / "hooks2"
    hidden.mkdir(parents=True)
    (hidden / "payload.sql").write_text("{% macro probe() %}{{ log('ran', info=True) }}{% endmacro %}\n", encoding="utf-8")
    return hidden / "payload.sql"


def test_a_macro_added_through_a_symlink_fails_and_names_the_link_and_its_target(tmp_path, capsys):
    """The review's reproduction: a symlink in macros/ to a file under the package's .git passed as `all 3 files
    match`, and dbt 2.0.6 parsed the macro and ran it. Every file the four packages shipped is a regular file (0
    symlinks in the tree the dbt skill's workaround installs, Measured 2026-10-15 with `find -type l`), so a symlink is
    a difference whatever it points at."""
    packages, manifest = _tree(tmp_path), tmp_path / "packages.sha256"
    _run(packages, manifest, "--write")
    _hidden_macro(packages)
    (packages / "dbt_utils" / "macros" / "zz_probe.sql").symlink_to("../.git/hooks2/payload.sql")

    assert _run(packages, manifest) == 1
    out = capsys.readouterr().out
    assert "symlink   dbt_utils/macros/zz_probe.sql -> ../.git/hooks2/payload.sql" in out


def test_a_symlinked_folder_and_a_symlink_named_git_fail_too(tmp_path, capsys):
    """A link to a folder is never walked, and a package's `.git` is left out only as a real folder at its root."""
    packages, manifest = _tree(tmp_path), tmp_path / "packages.sha256"
    _run(packages, manifest, "--write")
    (packages / "dbt_utils" / "more_macros").symlink_to("macros", target_is_directory=True)
    (packages / "elementary" / ".git").symlink_to("../dbt_utils/macros", target_is_directory=True)

    assert _run(packages, manifest) == 1
    out = capsys.readouterr().out
    assert "symlink   dbt_utils/more_macros -> macros" in out
    assert "symlink   elementary/.git -> ../dbt_utils/macros" in out


def test_write_refuses_a_tree_holding_a_symlink_so_none_is_pinned_around(tmp_path, capsys):
    packages, manifest = _tree(tmp_path), tmp_path / "packages.sha256"
    (packages / "dbt_utils" / "macros" / "zz_probe.sql").symlink_to(_hidden_macro(packages))

    assert _run(packages, manifest, "--write") == 1
    assert not manifest.exists()
    assert "symlink   dbt_utils/macros/zz_probe.sql -> " in capsys.readouterr().out


def test_no_packages_folder_fails_with_its_own_exit(tmp_path):
    assert _run(tmp_path / "absent", tmp_path / "packages.sha256") == 2


def test_the_committed_manifest_covers_every_package_the_lock_names():
    lock = yaml.safe_load((PIPELINE / "dbt" / "package-lock.yml").read_text(encoding="utf-8"))
    named = {package["name"] for package in lock["packages"]}
    pinned = {name.split("/", 1)[0] for name in check.read_manifest(check.MANIFEST)}
    assert named == pinned == {"codegen", "dbt_project_evaluator", "dbt_utils", "elementary"}
    for package in named:
        assert f"{package}/dbt_project.yml" in check.read_manifest(check.MANIFEST), package
