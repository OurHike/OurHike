#!/usr/bin/env python3
"""
Lightweight cost-detection script for CI.

Features added in this refactor:
 - Exposes helper functions for unit testing
 - Detects paid SDKs referenced in package.json and requirements files
 - Keeps original behavior of scanning changed files for paid-provider keywords

Behavior:
 - Finds files changed against origin/main
 - Scans changed files for keywords that often indicate paid providers or services
 - If such keywords are found and no COSTS.md exists in the repo root or was added in the PR, exits non-zero

This script is intentionally simple and conservative — it flags potential cost impacts for manual review, not as a final audit.
"""
import json
import os
import re
import subprocess
import sys
from typing import Iterable, Set

KEYWORDS = [
    r"mapbox",
    r"maptiler",
    r"google(-)?maps",
    r"googleapis",
    r"aws",
    r"amazonaws",
    r"stripe",
    r"pay",
    r"tile",
    r"paid",
    r"billing",
    r"mapbox-gl",
    r"mapboxgl",
]

RE = re.compile("|".join(KEYWORDS), re.IGNORECASE)


def run(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True, text=True).strip()


def scan_text_for_keywords(text: str) -> bool:
    """Return True if any keyword appears in the provided text."""
    return bool(RE.search(text))


def scan_package_json_content(text: str) -> bool:
    """Return True if package.json content references known paid SDKs in dependency names or versions."""
    try:
        data = json.loads(text)
    except Exception:
        return False
    candidates = []
    for field in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps = data.get(field) or {}
        for name, ver in deps.items():
            if RE.search(name) or (isinstance(ver, str) and RE.search(ver)):
                candidates.append(f"package:{name}")
    return bool(candidates)


def scan_requirements_content(text: str) -> bool:
    """Return True if any line in requirements content references a keyword (simple heuristic)."""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # check the package name and the full line
        pkg = line.split('==')[0].split('>=')[0].split('<')[0].strip()
        if RE.search(pkg) or RE.search(line):
            return True
    return False


def gather_changed_files() -> Iterable[str]:
    """Return a list of changed files relative to origin/main if possible, otherwise staged files."""
    try:
        run('git fetch origin main --depth=1')
    except Exception:
        # best-effort; continue
        pass

    try:
        changed = run('git diff --name-only origin/main...HEAD')
    except Exception:
        # fallback to listing staged files
        changed = run('git diff --name-only --staged')

    return [p for p in changed.splitlines() if p]


def files_to_scan_from_changed(changed_files: Iterable[str]) -> Iterable[str]:
    if changed_files:
        return changed_files
    # scan common directories only to limit runtime
    files_to_scan = []
    for root, dirs, files in os.walk('.', topdown=True):
        if '/.git' in root or 'node_modules' in root:
            continue
        for f in files:
            if f.endswith(('.py', '.js', '.ts', '.json', '.yaml', '.yml', '.md')):
                files_to_scan.append(os.path.join(root, f))
    return files_to_scan


def find_candidates(files: Iterable[str]) -> Set[str]:
    candidates = set()
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                content = fh.read()
        except Exception:
            continue

        # specialized checks
        base = os.path.basename(path).lower()
        if base == 'package.json':
            if scan_package_json_content(content):
                candidates.add(path)
            continue
        if base in ('requirements.in', 'requirements.txt', 'pipfile'):
            if scan_requirements_content(content):
                candidates.add(path)
            continue

        if scan_text_for_keywords(content):
            candidates.add(path)
    return candidates


def main() -> int:
    changed_files = list(gather_changed_files())

    costs_present_in_repo = os.path.exists('COSTS.md')
    costs_in_pr = any(os.path.basename(p).lower() == 'costs.md' for p in changed_files)

    files_to_scan = list(files_to_scan_from_changed(changed_files))
    candidates = find_candidates(files_to_scan)

    if candidates:
        print('Potential paid-provider keywords found in the following changed files:')
        for p in sorted(candidates):
            print('  ', p)
        if costs_present_in_repo or costs_in_pr:
            print('\nCOSTS.md detected (repo or PR). Please ensure it documents cost estimates and mitigation. Passing check.')
            return 0
        else:
            print('\nNo COSTS.md found in repo root or added in this PR.\nAs Money Man requires, add a COSTS.md documenting estimated recurring costs, mitigation plans, and approvals.\nFailing the check until documented.')
            return 2

    print('No likely paid-provider keywords found in changed files. Passing cost check.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
