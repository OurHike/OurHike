#!/usr/bin/env python3
"""
Lightweight cost-detection script for CI.
Behavior:
 - Finds files changed against origin/main
 - Scans changed files for keywords that often indicate paid providers or services
 - If such keywords are found and no COSTS.md exists in the repo root or was added in the PR, exits non-zero

This script is intentionally simple and conservative — it flags potential cost impacts for manual review, not as a final audit.
"""
import os
import re
import subprocess
import sys

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


def run(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()


# Determine changed files against origin/main — Actions should fetch origin/main before running
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

changed_files = [p for p in changed.splitlines() if p]

# Check if COSTS.md exists in repo root or is included in changed files
costs_present_in_repo = os.path.exists('COSTS.md')
costs_in_pr = any(os.path.basename(p).lower() == 'costs.md' for p in changed_files)

# If no changed files (e.g., shallow checkout), be conservative and scan repository for keywords
candidates = set()
if changed_files:
    files_to_scan = changed_files
else:
    # scan common directories only to limit runtime
    files_to_scan = []
    for root, dirs, files in os.walk('.', topdown=True):
        # skip .git and node_modules
        if '/.git' in root or 'node_modules' in root:
            continue
        for f in files:
            if f.endswith(('.py', '.js', '.ts', '.json', '.yaml', '.yml', '.md')):
                files_to_scan.append(os.path.join(root, f))

for path in files_to_scan:
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            content = fh.read()
    except Exception:
        continue
    if RE.search(content):
        candidates.add(path)

if candidates:
    print('Potential paid-provider keywords found in the following changed files:')
    for p in sorted(candidates):
        print('  ', p)
    if costs_present_in_repo or costs_in_pr:
        print('\nCOSTS.md detected (repo or PR). Please ensure it documents cost estimates and mitigation. Passing check.')
        sys.exit(0)
    else:
        print('\nNo COSTS.md found in repo root or added in this PR.\nAs Money Man requires, add a COSTS.md documenting estimated recurring costs, mitigation plans, and approvals.\nFailing the check until documented.')
        sys.exit(2)

print('No likely paid-provider keywords found in changed files. Passing cost check.')
sys.exit(0)
