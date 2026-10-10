"""Hold pipeline/dbt/dbt_packages/ to the sha256 of every file its four packages shipped (decision 144).

    python check_dbt_packages.py            # compare the tree with dbt/packages.sha256; exit 1 on any difference
    python check_dbt_packages.py --write    # rewrite dbt/packages.sha256 from the tree, after a reviewed upgrade

packages.yml and package-lock.yml pin each package to a version, and `dbt deps` fetches that version's tarball from
codeload.github.com, but nothing checks what the tarball holds: a tag moved upstream would change the macros every
dbt command here runs, in jobs that hold the raw store's and the bucket's write keys. The maintainer's poll of
2026-10-09 asked for the dbt install and the dbt packages to be hash-pinned (decision 144, pipeline/ELT.md);
requirements-dbt.txt pins the install, and this file pins the packages, by comparing every file under
dbt_packages/ with dbt/packages.sha256 and failing on any file changed, missing or added.

A package folder's own `.git` is left out. The sandbox workaround the dbt skill documents clones each package at
its tag, and a tag's archive, which is what `dbt deps` unpacks, holds exactly the tag's tracked files when the
repository sets no export-ignore rule (none of the four does; read 2026-10-10 from three clean clones at 0.14.1,
v1.4.0 and 1.4.1, and from Elementary's 0.26.0 export, which carries no .gitattributes). Measured on runners,
2026-10-10, the tree `dbt deps` writes there holds these same bytes: the check passed on a cache hit in
pipeline-tests.yml run 38020970450 and after a fresh deps in pr-preview.yml run 38021442664's docs build. A
difference prints each path with the sha256 found, so the manifest can be corrected from the log once the
difference is understood.

Standard library only, so it runs in any job's Python before the dbt venv exists.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGES_DIR = HERE / "dbt" / "dbt_packages"
MANIFEST = HERE / "dbt" / "packages.sha256"

#: The most differences printed before a count of the rest, so a wholly wrong tree does not flood the log.
SHOWN = 40


def tree_hashes(root: Path) -> dict[str, str]:
    """{path relative to `root`, posix: sha256 hex} for every regular file under it, each package's `.git` left out."""
    found: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if len(relative.parts) > 1 and relative.parts[1] == ".git":
            continue
        if path.is_symlink() or not path.is_file():
            continue
        found[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def read_manifest(path: Path) -> dict[str, str]:
    """{path: sha256} from sha256sum-style lines, `<hex>  <path>`; a blank line or a `#` comment is skipped."""
    pinned: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        digest, sep, name = line.partition("  ")
        if not sep or len(digest) != 64 or not name:
            raise ValueError(f"{path.name}:{number}: not `<sha256>  <path>`: {line!r}")
        pinned[name] = digest
    return pinned


def differences(pinned: dict[str, str], found: dict[str, str]) -> list[str]:
    """One line per file that differs, sorted: changed, missing from the tree, or not in the manifest."""
    lines = []
    for name in sorted(pinned.keys() | found.keys()):
        want, have = pinned.get(name), found.get(name)
        if want == have:
            continue
        if have is None:
            lines.append(f"missing   {name} (pinned {want})")
        elif want is None:
            lines.append(f"unpinned  {name} {have}")
        else:
            lines.append(f"changed   {name} {have} (pinned {want})")
    return lines


def write_manifest(path: Path, found: dict[str, str]) -> None:
    header = (
        "# sha256 of every file under pipeline/dbt/dbt_packages/, checked by pipeline/check_dbt_packages.py\n"
        "# (decision 144). Rewrite only with `python check_dbt_packages.py --write`, after reviewing the upgrade.\n"
    )
    path.write_text(header + "".join(f"{digest}  {name}\n" for name, digest in sorted(found.items())), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--write", action="store_true", help="rewrite the manifest from the tree instead of checking")
    parser.add_argument("--packages-dir", type=Path, default=PACKAGES_DIR)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args(argv)

    if not args.packages_dir.is_dir():
        print(f"::error title=dbt packages missing::{args.packages_dir} does not exist; run dbt deps first", flush=True)
        return 2
    found = tree_hashes(args.packages_dir)
    if args.write:
        write_manifest(args.manifest, found)
        print(f"wrote {len(found)} file hashes to {args.manifest}")
        return 0
    lines = differences(read_manifest(args.manifest), found)
    if not lines:
        print(f"dbt packages: all {len(found)} files match {args.manifest.name}")
        return 0
    print(
        f"::error title=dbt packages differ from {args.manifest.name}::{len(lines)} file(s) differ from the pinned "
        "packages; dbt runs nothing from this tree until they are understood (decision 144)",
        flush=True,
    )
    for line in lines[:SHOWN]:
        print(f"  {line}")
    if len(lines) > SHOWN:
        print(f"  ... and {len(lines) - SHOWN} more")
    return 1


if __name__ == "__main__":
    sys.exit(main())
