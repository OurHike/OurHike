"""build_marts: the dbt build in the order the Python steps need, from the seeds to the phone files.

    python build_marts.py --fixtures [--dbt dbt] [--python <interpreter>]
        [--warehouse data/warehouse.duckdb] [--processed-dir data/processed/dbt]
        [--raw-dir data/raw] [--threads N] [--checks-base <dir>]
        [--state-base <dir>] [--dry-run]                     # --state-base: a pull request, from main's build
    python build_marts.py --lane monthly ...                 # build-reference.yml
    python build_marts.py --lane hourly [--state <dir>] ...  # the hourly conditions lane
    python build_marts.py --lane hourly --checks-only ...    # its checks, check-conditions.yml

The one home of the build order (pipeline/ELT.md, "Python steps, outside dbt"
and "Running it"). CI's dbt job and scripts/test.sh call it with --fixtures.
This file imports only the standard library, so it runs on either of CI's
venvs; --dbt and --python name the interpreters for dbt and the steps.

WHY MORE THAN ONE `dbt build`. A rule that stays Python runs as a step between
dbt invocations: it reads a named intermediate and writes `derived.<table>`,
which dbt reads back as a source (models/staging/derived/). One `dbt build`
would reach a stg_derived__ model before its step had run. So:

1. `dbt seed`;
2. stage A: everything not downstream of a `derived` source, except the pub_
   writers and the evaluator package (CI runs that on its own);
3. for each STEPS entry, in order: the step, then
   `dbt build -s source:derived.<its table>+`, less what a later step's table
   also feeds;
4. the pub_ writers, after every other model, so a failing test upstream
   stops a writer before it writes (ELT.md, "Publish (reverse ETL)");
5. Elementary's checks ("ELEMENTARY'S CHECKS RUN AFTER THE WRITERS", or
   "THE HOURLY LANE'S CHECKS RUN APART");
6. each source's freshness, then the lane's data-quality file.

Contracts are enforced in every invocation. `dbt deps` is not here: CI and
scripts/test.sh run it first.

A LANE BUILDS ONLY ITS OWN NODES (--lane; ELT.md, "Every node carries its
cadence"). A node's cadence is the fastest `meta.cadence` among the sources it
reads, so `config.meta.cadence:hourly+` selects every node an hourly source
reaches.
- `monthly` (build-reference.yml) leaves out every node an hourly or daily
  source reaches, writers included: its warehouse holds only monthly raw
  tables. A source with no `meta.cadence` is built here.
- `hourly` builds the seeds, every node an hourly or daily source reaches, the
  hourly steps and what they unblock, then those nodes' writers. Monthly
  parents come through `--defer --state`; without --state the build also
  takes them (LANE_PARENTS), so the warehouse must hold their raw tables.
- Each STEPS entry runs in its `lane`. After `dbt seed`, lane_problems()
  refuses a step with no `step_<name>` exposure listing its inputs (unless it
  `reads_no_model`), a monthly step reading an hourly node, and a step whose
  table feeds only the other lane's writers.
- --without-step NAME leaves a step out with everything its table unblocks, so
  those writers keep their last files (publish.py's `kept`).
With no --lane every step and node builds, as CI's fixture warehouse needs.

A MODEL TAGGED `builds_alone` BUILDS WITH NO OTHER MODEL BESIDE IT, so it has
DuckDB's whole memory limit. int_places__resolved and int_trail_network__cuts
ran out of memory building side by side (refresh-reference.yml 37296900535,
2026-10-05), and alone too, so both queries were rewritten to hold less.
@unvalidated: that either now fits is settled by the next monthly build that
passes; the tag stays until then. dbt has no per-model setting that keeps two
table models apart, so every build here except the writers' and the hourly
lane's is split into up to three passes, each keeping the build's selection:
(a) the command with `--exclude tag:builds_alone+`, at --threads;
(b) the tagged models (`-s <each -s item>,tag:builds_alone`), at one thread;
(c) what they feed (`-s <each -s item>,tag:builds_alone+`, `--exclude
    tag:builds_alone`), at --threads.
alone_problems() refuses, after `dbt seed`, a tagged model that reads a model
(c) builds, a test in (b) that reads one, and a tagged model an hourly source
reaches. A pass that selects nothing is left out (selects_anything()): dbt
2.0.6 takes 30.9 to 34.2 s to answer an empty selection (measured 2026-10-05).
The hourly lane never splits: it has 10 minutes, and each dbt invocation costs
about 9.4 s before its first node (measured, refresh-reference.yml run 20).

THE PUB_ WRITERS BUILD ONE AT A TIME (--threads 1) in every lane but the
hourly one. Four network-wide writers (pub_nearby_trails and the three
pub_trail_graph files) ran out of DuckDB's 12.4 GiB side by side
(refresh-reference.yml 37614075245, 2026-10-07); each holds a whole file as one
string. @unvalidated: that each fits alone is settled by the next monthly
writers step. One thread for every writer rather than a tag on four: the other
38 took 48.3 s together in that run, and a heavy writer added later is covered.
The hourly lane keeps --threads: it writes none of the four.

A FAILED dbt BUILD IS RETRIED, up to DBT_RETRIES (3) times, in every lane
(the maintainer, 2026-10-07: "do up to 3 retries. period"): `dbt retry
--threads 1` until one exits 0. Measured on dbt 2.0.6 (2026-10-07): a retry
builds only the failed nodes and those they skipped, keeps the build's `-s`
and `--exclude`, accepts `--indirect-selection`, and exits 1 when nothing is
left to retry. Each retry's run_results.json holds only its own nodes, so
retry_failed_build() writes back every node with its last result. retry_argv()
passes no `--state`: given it, retry reads that directory's run_results.json
and finds nothing to retry. @unvalidated: whether a retry of a deferred build
still defers, what retries cost a monthly run, and how often three retries
push the hourly build past its 10-minute cap; each is settled by the run
summary's retry lines over the first weeks.

NOT dbt's `selectors.yml`: dbt documents `--selector` as not combinable with
`-s` or `--exclude`, which every invocation here carries, so a lane is one
more `--exclude` and LANE_EXCLUDES is its one home. @unvalidated for 2.0.6:
a probe with a defined selector beside `--exclude` would settle it.

A NEW STEP IS ONE STEPS ENTRY plus its script; nothing in CI or
scripts/test.sh changes. After `dbt seed`, derived_source_problems() refuses a
`derived` table no step writes, and a step writing a table no source declares.

THE ROW HISTORY IS RESTORED FIRST AND SAVED LAST. The row-history snapshots
(int_<mart>__history, one per mart; macros/row_history.sql) are the only state
a build carries between runs, and the warehouse is rebuilt from raw every run,
so `row_history.py restore` runs before `dbt seed` and `row_history.py save`
after the writers and checks, only when every command before it succeeded.
The store is --history-url, else OURHIKE_HISTORY_URL. A store with no history
is a cold start, allowed only:
- under --fixtures with no store named (a new temporary directory each run);
- for a store row_history_stores.toml does not list as started (its first
  run, said in a warning);
- with --history-cold-start, by hand.
Anything else fails before dbt runs: a silent cold start would date every row
as first seen in this build. The restore and save run on --history-python,
which needs DuckDB, and s3fs for an s3:// store. Every dbt command runs with
TZ=UTC, so a TIMESTAMPTZ hashes the same everywhere (macros/row_hash.sql), and
with OURHIKE_BUILT_BY (commit and workflow run), which each snapshot version
records as `_built_by`, never hashed.
ELEMENTARY'S HISTORY RIDES IN THE SAME TWO COMMANDS (row_history.py,
"ELEMENTARY'S HISTORY"): the restore puts its kept tables back before
"Elementary's own tables" builds, and the save writes them out, keeping
ELEMENTARY_KEEP_DAYS of builds (--keep-days). Its cold start follows the same
rules against row_history_stores.toml's [elementary_started].

--no-history-save restores and builds, and saves nothing back, so a build that
knows some inputs are missing never records a row's absence as its removal.
publish-conditions.yml passes it when the notices legs' served copy was not
the newest (extract/_warehouse.py, "THE SERVED COPY"). The cost: a row that
did change is dated by the next build that saves (Reasoned).

--history-on-failure degrade IS THE CONDITIONS LEGS' (the maintainer,
2026-10-03): closures and warnings still publish when their history cannot be
restored. The failure is printed as an error, every dbt command runs with
OURHIKE_ROW_HISTORY=off, so both row dates are null (unknown, never "new"),
nothing is saved, and the build exits DEGRADED_EXIT after everything else
passed: the workflow publishes, then goes red. A command that itself exits
with that code is answered with 1. The default, `fail`, is the monthly lane's.
When only Elementary's part fails under degrade, row_history.py still
restores or saves the snapshots and exits ELEMENTARY_DEGRADED_EXIT, answered
as PARTIAL_EXIT: a failure of Elementary's history never nulls a row date.

ONE SOURCE OR ONE WRITER NEVER STOPS THE REST (the maintainer, 2026-10-05:
"Hold that source and publish the rest"). Five of the hourly soak's first ten
runs published nothing because of one source or one writer. These four answer
PARTIAL_EXIT once everything else has run, so the workflow publishes what was
written and then turns red:
- a test whose `meta` sets `holds_a_source` warned: int_closures__gate holds
  the rows' source, and the rows are printed as a failed test's are;
- a model or test of one generated club notice source failed in stage A: that
  source's raw tables are dropped and stage A runs again, so the gate holds
  the source and it carries its last good rows;
- some pub_ writers failed and every failure in that run is a writer's own:
  each failed writer's file is removed, so a half-written file is never
  published, and publish.py (told by OURHIKE_BUILD_PARTIAL) keeps that key's
  last copy;
- a table the extract withdrew (WITHDRAWABLE: field notes and disputes, when
  the reader cannot see public.field_notes): its source and everything below
  it are left out of every dbt build (#922 — The whole conditions bake has
  been failing hourly since field notes landed, so the closures baseline is
  ageing).
The row history is still saved: a held source carries its rows (Reasoned).

EVERY TEST HAS TWO THRESHOLDS, AND THE ENVIRONMENT DECIDES WHO STOPS (the
maintainer, 2026-10-15: "prod environment should ignore those, dev & ci should
not"). OURHIKE_DATA_ENV is the one switch (data_environment(); a name
lib/data_env.py does not know is refused), and dbt_project.yml reads it for
every test's severity:
- production and UA (BUILDS_ON): a failing test warns, so dbt builds below it,
  and a warning past the test's own `error_if` is reported here as an error
  (relabelled_errors(): rows, an `::error`, a summary line), then
  PARTIAL_EXIT. What still fails in dbt (a writer's test, a test set to
  `severity: error`, a unit test, a contract, a model's SQL, a Python step) no
  longer stops the build: failure_holds() leaves the failed node and all it
  reaches out of every later dbt build, a step reading any of it
  (steps_reading()) is left out, each writer below keeps its last file, and
  the rest publishes before the run goes red. Elementary's checks never change
  the exit; their errors are an `::error` and a failure on the data-quality
  page.
- dev and CI (unset, or `dev`): a failing test stops the build, and a check
  past its error threshold fails the build at its end, after the history is
  saved.
Measured on dbt 2.0.6 (2026-10-15): at warn a failing test still builds the
models below it and keeps its count in run_results.json, and `error_if` is
not evaluated. A test whose meta sets STAYS_AT_WARN warns everywhere and is
never relabelled.

ELEMENTARY'S TABLES ARE BUILT FIRST, right after both histories are restored.
Every dbt command runs with OURHIKE_ELEMENTARY=true (dbt_project.yml's switch
for Elementary's models and hooks), and the end-of-run hook writes each
command's results into those tables. With a table missing a command records
nothing and still passes (measured 2026-10-08), so `dbt run --select
package:elementary` comes before `dbt seed`, and stage A leaves the package
out. The pytest suites leave the switch off.

ELEMENTARY'S CHECKS RUN AFTER THE WRITERS, in a pass of their own before the
history is saved: `dbt test -s tag:elementary_check` at one thread, scoped as
the writers are. Every check carries that tag (make_dbt_staging.py) and every
build before the pass leaves it out, so no check runs beside its model. Each
check warns where Elementary flags a point or an added column, and errors past
6 deviations and 50% from the usual value, or on a column removed or retyped
(make_dbt_staging.py's elementary_check_config()). In production and UA the
pass never changes the exit; in dev and CI a check that failed or could not
run fails the build at its end. A check that errors, or a pass with no
results, is one `::warning`, and the build goes on. Checks are never retried:
a retry is for nodes a publish needs (Reasoned). Checks on a raw table the
warehouse lacks are left out (absent_sources()). The monthly pass trains on
MONTHLY_TRAINING_DAYS. The checks are switched on (CHECKS_SWITCH) only in the
two commands that need them, because enabled they slow every dbt command:
`dbt parse` took 16.9 to 17.5 s of CPU with them against 12.0 to 12.8 s
without (measured 2026-10-08). A pass costs about 0.33 s of CPU a check,
whatever --threads (measured 2026-10-08 on the fixtures).

A PULL REQUEST RUNS THE CHECKS ITS CHANGE REACHES (--checks-base; the
maintainer, 2026-10-08: "Run all of them that have been modified, and
downstream models"). Given the base commit's dbt project, parsed with
Elementary's two switches on and against the build's own warehouse path (the
file's name is every node's database), the pass selects
`tag:elementary_check,state:modified+` with `--state` at the base's target/.
It runs every check instead, and says why (checks_base_problems()), when no
base is given, the base's manifest is missing, or dbt_project.yml,
packages.yml, package-lock.yml or any macro differs: dbt 2.0.6's state
comparison reads neither a var nor a macro. Measured 2026-10-08 with `dbt ls`:
no change selected 0 of 1,979 checks; a comment in closures.sql selected the 6
on that mart; a comment in a models YAML file selected none. Only a build with
no lane takes a base.

A PULL REQUEST BUILDS ONLY WHAT CHANGED SINCE MAIN'S LAST BUILD (--state-base;
the maintainer, 2026-10-15). The full build took 16 min 7 s of CI's dbt job
(Pipeline tests run 38773605297). A push to main caches its fixture warehouse
and manifest; a pull request that state_base.py lets through (its docstring
has the rules) reuses that warehouse, reloads the fixtures' raw tables, and
passes the cached manifest as --state-base. Then:
- after `dbt seed`, `dbt ls -s state:modified --state <it>` (STATE_LIST) lists
  what changed, and main() plans again with that list;
- stage A selects `state:modified+` plus every node whose SQL reads the clock
  (clock_readers()), so no file publishes main's day;
- each Python step still runs; what its table unblocks is built whole when the
  step read a changed input (changed_step_tables()), otherwise only where it
  meets a change;
- the writers, checks, freshness and data-quality file run as in any build, so
  parity compares every phone file;
- no --defer: every unselected node is already in the warehouse, where main
  built it;
- the row history is neither restored nor saved: a restore would replace
  snapshots this build does not rebuild. Elementary's history alone starts
  cold, so no schema check compares this build with main's.
plan() refuses --state-base with a lane, with --state, and outside
--fixtures; main() refuses it with a history store or --checks-only, and stops
after `dbt seed` when a macro differs (state_base.macro_problems()). A failed
notice source in stage A stops a state build rather than being held.

THE HOURLY LANE'S CHECKS RUN APART, AFTER ITS BUILD HAS PUBLISHED
(HOURLY_LANE_CHECKS; the maintainer, 2026-10-08: "build a different workflow
that kicks off after the actual build"). Its 1,053 checks need 7.2 to 10.6
minutes on a runner, and the build step's 10 minutes leave about 5.9 after the
build's 244.6 s (publish-conditions.yml run 37855544935, 2026-10-08;
Reasoned). So `--lane hourly` builds, writes, saves and publishes with no
checks and no data-quality file, and `--lane hourly --checks-only`
(check-conditions.yml, started once the build has published, with the
warehouse handed over by hand_off.py) runs only these (plan_checks()):
1. Elementary's history alone, restored from the build's save;
2. Elementary's own tables, with the checks' switch;
3. every check the lane has;
4. each source's freshness, on publish-conditions.yml's own selection;
5. the lane's data-quality writer, counting the build's results with its own
   (OURHIKE_BUILD_STARTED_AT is the build's);
6. Elementary's history alone, saved back.
What it needs of the build it reads from BUILD_RECORD, which such a build
writes into its warehouse last (write_build_record()): when it started, the
store it restored from, the steps it held, whether its row history was on,
whether it saved Elementary's history, and when its notices copy was read
(NOTICES_READ_AT_ENV). A build that saved no Elementary history leaves its
own tables to the checks, which then restore and save nothing. The checks run
never touches a phone file; it exits PARTIAL_EXIT when Elementary's history
was held back and the file written, and 1 when the file was not. Measured
2026-10-09 on the fixtures: the hourly build took 202.8 s, the checks run
362.8 s (1,041 checks in 278.6 s).

EACH SOURCE'S FRESHNESS IS MEASURED FOR THE DATA-QUALITY FILE (the maintainer,
2026-10-15: freshness is OurHike's own last successful read of a source, in
every lane). `dbt source freshness` runs right before the data-quality writer,
and Elementary's hook records each result, which macros/data_quality.sql
counts. Each source is measured by its own `loaded_at_query`
(macros/last_read_or_confirmed_at.sql) against its own warn_after and
error_after. What each run measures (freshness_selection()):
- hourly: publish-conditions.yml's own selection, `tag:conditions_job`, with
  `tag:notices_job` when the build read a notices copy;
- monthly: every other source, less the Python steps' tables
  (FRESHNESS_LEFT_OUT);
- no lane (CI's fixtures): every source but those, and under --fixtures the
  PDF notices, which fixtures never land.
Freshness never changes the build's exit and is never retried: in the hourly
lane publish-conditions.yml's own freshness step turns a run red. A run that
measured nothing says so (freshness_report()). Measured 2026-10-15 on
Elementary 0.26.0: the hook leaves max_loaded_at_time_ago_in_s null, so
macros/data_quality.sql works the age out from the two instants.

THE DATA-QUALITY FILE IS WRITTEN LAST: the lane's DATA_QUALITY_WRITERS entry,
in a pass of its own after the writers and checks, before the history is
saved, because it reads what the checks recorded. ONE WRITER OF EACH FILE: a
lane whose checks run apart writes it only in the checks run, so the hourly
file always counts a build and its checks. OURHIKE_BUILD_STARTED_AT tells the
file this build's results from older ones. Two rules keep the pass away from
what hikers get:
- publish.py reads the writers' run results as proof that a phone file was
  written, and every later dbt command overwrites run_results.json, so the
  writers' are kept as writers_run_results.json and written back after this
  pass with its results added;
- a failed pass never stops the build or changes its exit (the checks "never
  block a publish"): its file is removed, so publish.py keeps the last copy,
  and an ::error says so.
In the checks run the file is the run's one product, so a failed pass removes
it and ends the run with 1, after the save.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import tomllib

import state_base
from lib import data_env

PIPELINE_DIR = Path(__file__).resolve().parent
DBT_DIR = PIPELINE_DIR / "dbt"
DERIVED_SOURCE = "derived"
# The first run, after which the manifest it wrote is checked against STEPS.
SEED = "dbt seed"
#: The run before it (the module docstring, "ELEMENTARY'S TABLES ARE BUILT FIRST").
ELEMENTARY_TABLES = "Elementary's own tables"
#: dbt_project.yml's switch for Elementary's models and hooks, on for every dbt command this file runs.
ELEMENTARY_SWITCH = {"OURHIKE_ELEMENTARY": "true"}
#: The tag of every Elementary check (make_dbt_staging.py's ELEMENTARY_CHECK, spelled out because this file imports only
#: the standard library; tests/test_build_marts.py holds the two equal). Every dbt build here leaves the tagged tests
#: out, and ELEMENTARY_CHECKS runs them (the module docstring, "ELEMENTARY'S CHECKS RUN AFTER THE WRITERS").
ELEMENTARY_CHECK = "elementary_check"
ELEMENTARY_CHECKS = "Elementary's checks"
#: The checks' own switch (make_dbt_staging.py's ELEMENTARY_ENABLED reads it and says why they have one), as Run.env:
#: on only in a build that runs them, and there only for the two dbt commands that need them in the graph, Elementary's
#: own tables, whose dbt_tests table must describe every check the data-quality file counts, and the checks pass.
CHECKS_SWITCH = (("OURHIKE_ELEMENTARY_CHECKS", "true"),)
#: The monthly lane's training window for them, in days, given as `--vars` on its checks pass alone: ELT.md's "about
#: 400 days", so a lane that builds once a month trains on its last 13 builds where Elementary's 14 would hold none.
#: @unvalidated: settled by counting the monthly lane's false alarms over its first season. dbt_project.yml says why
#: --vars and not the var itself (a var rendered from Jinja reaches Elementary as a string).
MONTHLY_TRAINING_DAYS = 400
#: Where a lane runs ELEMENTARY_CHECKS: IN_BUILD, a pass of the build itself after its writers (the monthly lane, and a
#: build with no lane), or APART, a run of their own over the warehouse the build left, after the build has published
#: (--checks-only; the module docstring, "THE HOURLY LANE'S CHECKS RUN APART").
IN_BUILD, APART = "in the build", "apart"
#: The hourly lane runs every check every hour, APART, because they take longer than its 10-minute build step has
#: left (the module docstring has the sums).
HOURLY_LANE_CHECKS = APART
#: The table a build whose lane's checks run apart writes into its warehouse last, for the checks run to read: what
#: that run needs of the build (write_build_record()). Not a dbt schema, so no dbt command touches it.
BUILD_RECORD = "build_marts.build_record"
BUILD_RECORD_FORMAT = 1
#: The files of a dbt project whose change dbt's state comparison cannot see, each compared byte for byte with the
#: base's (the module docstring, "A PULL REQUEST RUNS THE CHECKS ITS CHANGE REACHES"): the vars every check reads, and
#: the packages Elementary's checks are made of.
CHECKS_BASE_FILES = ("dbt_project.yml", "packages.yml", "package-lock.yml")
MANIFEST_PATH = DBT_DIR / "target" / "manifest.json"
#: What the dbt run that just ended did, node by node: read for its failed tests, its warnings and its failed writers.
RUN_RESULTS_PATH = DBT_DIR / "target" / "run_results.json"

#: The scheduled lanes (the module docstring, "A LANE BUILDS ONLY ITS OWN NODES").
MONTHLY, HOURLY = "monthly", "hourly"
LANES = (MONTHLY, HOURLY)
#: Each lane's data-quality writer (the module docstring, "THE DATA-QUALITY FILE IS WRITTEN LAST"); a build with no lane
#: writes both.
DATA_QUALITY_WRITERS = {MONTHLY: "pub_data_quality", HOURLY: "pub_conditions_data_quality"}
DATA_QUALITY_LABEL = "the data-quality file"
#: The run that measures each source's freshness for the data-quality file (the module docstring, "EACH SOURCE'S
#: FRESHNESS IS MEASURED FOR THE DATA-QUALITY FILE").
FRESHNESS_LABEL = "the sources' freshness"
#: The tags publish-conditions.yml's freshness step selects the hourly lane's sources by: the conditions job's own
#: upstreams every run, and the notices job's (generate_notice_models.py's NOTICES_JOB_TAG) when the build read a
#: notices copy. Spelled out because this file imports only the standard library; tests/test_build_marts.py holds them
#: to generate_notice_models.py's and to that step.
CONDITIONS_JOB_TAG, NOTICES_JOB_TAG = "conditions_job", "notices_job"
#: generate_notice_models.py's PDF_NOTICE_TAG, which CI's freshness commands leave out: fixture mode lands no PDF.
PDF_NOTICE_TAG = "pdf_notice"
#: What every freshness run but the hourly lane's leaves out (that lane's tags select none of it): the Python steps'
#: own tables, which a step writes in the build that reads them and no run log row names, so none is an upstream
#: OurHike reads (their sources block says why they keep `_loaded_at`). Two of them are the hourly steps' and absent
#: from the monthly warehouse.
FRESHNESS_LEFT_OUT = (f"source:{DERIVED_SOURCE}",)
#: extract/_warehouse.py's NOTICES_READ_AT_ENV: when the run of the notices copy the hourly build read began, which
#: add-served puts in publish-conditions.yml's $GITHUB_ENV only when the build read a copy (its exits 0, 5 and 7, the
#: step's `latest` and `older`), so the build step inherits it. The build record keeps it, and the checks run's
#: freshness selects the notices job's sources by it, as that workflow's freshness step selects them by `read`.
NOTICES_READ_AT_ENV = "OURHIKE_NOTICES_READ_AT"
#: What a freshness run leaves, dbt's own record of each source it measured.
SOURCES_RESULTS_PATH = DBT_DIR / "target" / "sources.json"
#: Where the writers' run results wait while later dbt commands run, beside run_results.json.
WRITERS_RESULTS_NAME = "writers_run_results.json"
#: The cadences faster than monthly. Daily rides the hourly lane when due
#: (extract/_run.py's DUE_AFTER), so its nodes are the hourly lane's too.
FASTER_THAN_MONTHLY = ("hourly", "daily")
#: Every node a faster-than-monthly source reaches, as dbt selects it. Measured
#: 2026-10-02 on dbt 2.0.6 against this project (`dbt ls --resource-type
#: model`): of 247 models, 22 are reached by an hourly source and 9 by a daily
#: one, which leaves 224 to the monthly lane; of the 29 writers, 4 are the
#: hourly lane's.
LANE_EXCLUDES = tuple(f"config.meta.cadence:{cadence}+" for cadence in FASTER_THAN_MONTHLY)
#: The hourly lane's other half when it has no --state to defer to: every
#: parent of a node whose own cadence is hourly or daily (the hourly exposures
#: among them), so the monthly nodes the closures and warnings marts read
#: (int_sources__publication, the registry staging, two seeds) are built in
#: the same warehouse. Selected under `--indirect-selection cautious`: with the
#: default (eager), the relationships tests on points_of_interest,
#: suggested_hikes and int_trail_lines__coded_domains come along and fail on
#: tables an hourly warehouse does not hold. Both measured 2026-10-02 on dbt
#: 2.0.6 against the fixture warehouse: `dbt ls -s +config.meta.cadence:hourly
#: --indirect-selection cautious` selected 30 models and seeds, 11 sources and
#: the 4 pub_conditions_* writers.
LANE_PARENTS = tuple(f"+config.meta.cadence:{cadence}" for cadence in FASTER_THAN_MONTHLY)
#: How many times a failed `dbt build` is retried with `dbt retry`, in every lane (the module docstring, "A FAILED dbt
#: BUILD IS RETRIED"): the maintainer's 3.
DBT_RETRIES = 3
#: The tag of a model that builds with no other model beside it (the module docstring, "A MODEL TAGGED
#: `builds_alone`"), set in the model's own config().
BUILDS_ALONE = "builds_alone"
#: A state build's selector (the module docstring, "A PULL REQUEST BUILDS ONLY WHAT CHANGED SINCE MAIN'S LAST BUILD"):
#: what dbt finds changed against --state-base, and everything below it.
STATE_MODIFIED = "state:modified+"
#: The run that lists what changed, right after `dbt seed`, and its Run.stage.
STATE_LIST_LABEL, STATE_LIST = "what changed since main's build (dbt ls state:modified)", "state_list"
#: A state build's first command: Elementary's history alone, started cold, the cached warehouse's snapshots kept.
ELEMENTARY_COLD_LABEL = "start Elementary's history cold, the warehouse's snapshots kept"
#: SQL that reads the clock: DuckDB's date and time functions, and dbt's run_started_at. Matched on a node's code and
#: each macro's with every comment removed (_code()), since a comment saying "today (" is no read.
CLOCK = re.compile(
    r"\b(?:now|today|get_current_time|get_current_timestamp|transaction_timestamp)\("
    r"|\b(?:current_date|current_time|current_timestamp|localtime|localtimestamp|run_started_at)\b",
    re.IGNORECASE,
)
_COMMENTS = re.compile(r"\{#.*?#\}|/\*.*?\*/|--[^\n]*", re.DOTALL)


@dataclass(frozen=True)
class Step:
    """A Python step: its name, the `derived.<table>` it writes, and how it runs.

    `command` is the script and its arguments, run with --python from
    pipeline/; `fixture_args` are added under --fixtures, and a lane's
    `lane_args` under --lane without --fixtures, where a scheduled build
    reads an input from somewhere a fixture build does not. All may hold
    `{warehouse}` and `{raw_dir}`."""

    name: str
    table: str
    command: tuple[str, ...]
    fixture_args: tuple[str, ...] = ()
    lane_args: tuple[tuple[str, tuple[str, ...]], ...] = ()
    # The lane that runs it under --lane: the lane of the nodes its table
    # unblocks, which lane_problems() holds it to. Without --lane every step runs.
    lane: str = MONTHLY
    # True for a step that reads no dbt node, only a file (step_weather_squares
    # lands squares.json whole): it then needs no step_<name> exposure, and
    # lane_problems() has no input of its to check.
    reads_no_model: bool = False


#: The Python steps, in the order they run (pipeline/ELT.md, "Python steps,
#: outside dbt", has the four planned and why each stays Python).
STEPS: list[Step] = [
    # The network lines an organization's own notice closes by naming their
    # section (#1801 — The junction graph routes hikers onto the Tuscarora's
    # Doll Ridge section, which PATC says is closed for loss of landowner
    # permission), from the conditions/notices.json the hourly lane published;
    # the monthly lane reads it from the bucket, --fixtures from
    # make_dbt_fixtures.py's copy. FIRST: its table reaches the network lines,
    # which OSM water's reach and the graph read. No file closes nothing and
    # never stops the build.
    Step(
        name="step_section_closures",
        table="section_closures",
        command=("step_section_closures.py", "--warehouse", "{warehouse}"),
        fixture_args=("--notices", "{raw_dir}/section_closures/notices.json"),
        lane_args=((MONTHLY, ("--from-bucket",)),),
    ),
    # THE POI STEPS COME FIRST: every table they write reaches the trail_lines
    # mart (points_of_interest -> int_trail_lines__spur_destinations -> the
    # spurs -> int_trail_lines__at_published -> trail_lines), which
    # step_node_lines' int_trail_network__routable and step_dem_sampling's
    # sample points both read.
    # PO36 (a row of pipeline/ELT.md's ledger, as is each code below): NYNJTC's
    # Long Path guide placed as waypoints, from the guide_pages sections and the
    # Long Path layer's lines, both staged; under --fixtures,
    # extract/_fixtures.py serves the pages. Before the water steps, because its
    # records join int_points_of_interest__unioned, upstream of OSM water's
    # distance pass.
    Step(
        name="step_long_path_guide",
        table="long_path_guide",
        command=("step_long_path_guide.py", "--warehouse", "{warehouse}"),
    ),
    # PO07 and PO17: which A.T. shelters and campsites have water a hiker can
    # walk to, fetch_trail_water.py's rule over int_points_of_interest__water_sites.
    # Under --fixtures it reads each site's candidate reaches and the EPQS
    # answers make_dbt_fixtures.py wrote, never the network. The monthly lane
    # lands the site water refresh-reference.yml's pin job derived from the
    # Geofabrik extracts the raw store keeps (fetch_trail_water.py --derive,
    # #1652), pinned with that run's raw inputs, or the last landed one.
    Step(
        name="step_site_water",
        table="site_water",
        command=("step_site_water.py", "--warehouse", "{warehouse}"),
        fixture_args=(
            "--candidates",
            "{raw_dir}/site_water/candidates.json",
            "--elevations",
            "{raw_dir}/site_water/epqs_elevations.json",
        ),
        lane_args=((MONTHLY, ("--from-file", "{raw_dir}/derived/trail_water.json")),),
    ),
    # PO03: OSM's water points. Under --fixtures it lands make_dbt_fixtures.py's
    # points; the monthly lane lands refresh-reference.yml's pin job's scan of
    # the Geofabrik extracts (fetch_osm_water.py, #1652), pinned with that
    # run's raw inputs, or the last landed one, and warns when none has ever
    # landed (step_osm_water.py's docstring says how).
    Step(
        name="step_osm_water",
        table="osm_water",
        command=("step_osm_water.py", "--warehouse", "{warehouse}"),
        fixture_args=("--points", "{raw_dir}/osm_water/points.geojson"),
        lane_args=((MONTHLY, ("--landed", "{raw_dir}/derived/osm_water.geojson")),),
        reads_no_model=True,
    ),
    # PO06 and PO07: the grade half of OSM water's reach, over
    # int_points_of_interest__osm_water_reach's distance pass. Under --fixtures
    # it reads the EPQS answers make_dbt_fixtures.py wrote, never the network.
    Step(
        name="step_osm_water_grade",
        table="osm_water_grade",
        command=("step_osm_water_grade.py", "--warehouse", "{warehouse}"),
        fixture_args=("--elevations", "{raw_dir}/osm_water/epqs_elevations.json"),
    ),
    # PO24 and PO38: the photo manifests export_poi.py attaches, a stand-in for
    # the Commons extract kind. Under --fixtures it lands make_dbt_fixtures.py's
    # outcome files and decisions; otherwise the files export_poi.py reads.
    Step(
        name="step_poi_photos",
        table="poi_photos",
        command=("step_poi_photos.py", "--warehouse", "{warehouse}"),
        fixture_args=(
            "--commons",
            "{raw_dir}/poi_photos/poi_images.json",
            "--atc",
            "{raw_dir}/poi_photos/poi_images_atc.json",
            "--decisions",
            "{raw_dir}/poi_photos/photo_screen_decisions.json",
        ),
        reads_no_model=True,
    ),
    # TN04: every routable trail part cut where int_trail_network__cuts says,
    # by build_trail_graph.py's own _split_all, from warehouse inputs alone (so
    # no fixture_args). Before step_dem_sampling, whose input
    # int_elevation__dem_points is downstream of this step's graph_pieces
    # (through int_trail_network__edges and int_elevation__edge_sample_points).
    Step(
        name="step_node_lines",
        table="graph_pieces",
        command=("step_node_lines.py", "--warehouse", "{warehouse}"),
    ),
    # EL06: the DEM's elevation at every int_elevation__sample_points row.
    # Under --fixtures it reads the tile index and synthetic GeoTIFF
    # make_dbt_fixtures.py wrote; otherwise fetch_elevation.py's index, the
    # step's own default.
    Step(
        name="step_dem_sampling",
        table="dem_samples",
        command=("step_dem_sampling.py", "--warehouse", "{warehouse}"),
        fixture_args=("--index", "{raw_dir}/elevation/tile_index.json"),
    ),
    # WN03: the NBM weather squares build_weather_squares.py chose, which the
    # NWS alerts' placement reads. Under --fixtures it reads the squares.json
    # make_dbt_fixtures.py wrote; otherwise the weather job's own file.
    Step(
        name="step_weather_squares",
        table="weather_squares",
        command=("step_weather_squares.py", "--warehouse", "{warehouse}"),
        fixture_args=("--squares", "{raw_dir}/weather/squares.json"),
        lane=HOURLY,
        reads_no_model=True,
    ),
    # The release's trail lines (the A.T.'s among them) whose box meets an area
    # closure's, for int_closures__area_trail_cuts to cut. The hourly lane reads the lines
    # prepare_closure_trail_lines.py prepared once per release, which
    # publish-conditions.yml restores from the cache; with none it lands no
    # row and warns, and only the area closures miss that hour. Under
    # --fixtures it prepares make_dbt_fixtures.py's nearby_trails.geojson and
    # trails.geojson first. Never left out with --without-step: the line and
    # point closures its writer also carries need no lines.
    Step(
        name="step_closure_trail_lines",
        table="closure_trail_lines",
        command=("step_closure_trail_lines.py", "--warehouse", "{warehouse}"),
        fixture_args=(
            "--geojson",
            "{raw_dir}/closure_trail_lines/nearby_trails.geojson",
            "--at-geojson",
            "{raw_dir}/closure_trail_lines/trails.geojson",
            "--release",
            "fixture",
        ),
        lane_args=((HOURLY, ("--lines", "{raw_dir}/closure_trail_lines/lines.parquet")),),
        lane=HOURLY,
    ),
    # SH03, SH06: each Hike Finder hike's route formed from its description,
    # or its published track re-walked, over the junction graph. Last of the
    # steps, because it reads the graph's edges and their climb, which the
    # graph's own step and the network elevation will write ahead of it.
    Step(
        name="step_form_route",
        table="formed_routes",
        command=("step_form_route.py", "--warehouse", "{warehouse}"),
    ),
]


@dataclass(frozen=True)
class Paths:
    warehouse: Path
    processed_dir: Path
    raw_dir: Path


#: The history stores that have been saved to at least once, by name (the store URL's last part), each with the
#: run that started it: an empty one of these is lost history, never a first run (the module docstring, "THE ROW
#: HISTORY IS RESTORED FIRST AND SAVED LAST").
HISTORY_STORES = PIPELINE_DIR / "row_history_stores.toml"
RESTORE_LABEL, SAVE_LABEL = "restore the row history", "save the row history"
#: How many days of Elementary's history each lane's save keeps (row_history.py's docstring, "RETENTION"), as
#: --keep-days: the training window its checks read back, plus a margin. Monthly: 400 days, plus 30; ELT.md gives that
#: lane a window of about 400 ("Memory between runs"), so that the 10 earlier builds an anomaly check waits for beside
#: its own (11 points: dbt_project.yml's ELEMENTARY'S TRAINING AND DETECTION), one a month, fall inside it.
#: Hourly: Elementary's default days_back of 14, plus 7. Reasoned from Elementary 0.26.0: a
#: check reads back from its days_back before now, moved to the start of that day and then of its bucket
#: (get_trunc_min_bucket_start_expr()), and the save before a build ran earlier than the build, so a margin of 30
#: days covers buckets of up to four weeks and 7 days buckets of up to six. A lane whose checks take a longer
#: days_back or bucket than that needs these moved with it. The windows themselves are @unvalidated (ELT.md), settled
#: by the first season's false alarms. A build with no lane, CI's fixtures, builds both lanes' checks and keeps the
#: longer.
ELEMENTARY_KEEP_DAYS = {MONTHLY: 430, HOURLY: 21}
#: row_history.py's exit when, under --elementary-on-failure degrade, Elementary's history alone could not be restored
#: or saved: answered as part of the build held back (the module docstring, "--history-on-failure degrade").
ELEMENTARY_DEGRADED_EXIT = 3
#: What --history-on-failure degrade leaves out of every dbt build once the restore has failed: the snapshots,
#: which would otherwise start a history this run cannot keep and the marts must not read.
SNAPSHOTS = "resource_type:snapshot"
#: build_marts.py's exit when a degraded build passed: the marts and their writers are built, with null dates,
#: and nothing was saved. Not 0, so the workflow goes red once it has published; not 1, so it can tell.
DEGRADED_EXIT = 4
HISTORY_ON_FAILURE = ("fail", "degrade")
#: build_marts.py's exit when the build finished with part of it held back (the module docstring, "ONE SOURCE OR ONE
#: WRITER NEVER STOPS THE REST", and Elementary's history under "--history-on-failure degrade"): every file written may
#: publish, and the workflow goes red once it has. Not 0 and not
#: 1 for DEGRADED_EXIT's reason; and DEGRADED_PARTIAL_EXIT when the build was degraded too, so the workflow can say both.
PARTIAL_EXIT = 5
DEGRADED_PARTIAL_EXIT = 6
#: The exits that mean "built, publish what was written": a dbt command or step that answers one of them itself is
#: answered with 1, so the workflow never reads a failed build as a publishable one.
PUBLISHABLE_EXITS = (DEGRADED_EXIT, PARTIAL_EXIT, DEGRADED_PARTIAL_EXIT)
#: How much older than the writers' run a file may look and still count as written by it: publish.py's
#: WRITER_CLOCK_SLACK_S, for the same filesystems, @unvalidated there.
WRITER_CLOCK_SLACK_S = 2.0
#: THE A.T. PROFILE'S NULL SHARE IN FIXTURE MODE. dbt_project.yml's var elevation_profile_max_null_share (above
#: it, pub_elevation_profile's and pub_elevation_profile_v2's error-level test fails each writer, so the
#: bucket's last good copy stays) reads this variable, 0.01 when it is unset. make_dbt_fixtures.py's DEM leaves 8 of
#: the fixture profile's 45 samples null on purpose, two in the tile's nodata rows and six past its edge
#: (tests/test_dbt_elevation_parity.py, test_the_fixture_dem_gives_the_fixture_profile_both_kinds_of_gap), which 1%
#: would refuse, failing every fixture build. So --fixtures sets it to 0.2, which still refuses a fixture profile that
#: has lost most of its heights, and every other build clears whatever value it inherits, so no lane's build can
#: loosen the check. tests/test_dbt_elevation_profile_null_share.py holds the 1% side.
PROFILE_NULL_SHARE_VARIABLE = "OURHIKE_ELEVATION_PROFILE_MAX_NULL_SHARE"
FIXTURE_PROFILE_MAX_NULL_SHARE = "0.2"
#: The `meta` key of a test whose warning means int_closures__gate held a source for the rows it returns.
HOLDS_A_SOURCE = "holds_a_source"
#: The `meta` key of a test that warns in every environment and is never reported as an error: the four closures key
#: tests recorded as exceptions in seeds/model_key_exceptions.csv.
STAYS_AT_WARN = "stays_at_warn"
#: The module docstring, "EVERY TEST HAS TWO THRESHOLDS, AND THE ENVIRONMENT DECIDES WHO STOPS": the data environments
#: (lib/data_env.py's names) whose build goes on past a failure, as dbt_project.yml's switch makes a failing test warn.
BUILDS_ON = (data_env.PRODUCTION, data_env.UA)
#: A test's `warn_if` or `error_if` as dbt compares it with the test's `failures`: an operator and a number.
THRESHOLD = re.compile(r"\s*(>=|<=|!=|<>|==|=|>|<)\s*(-?[0-9]+(?:\.[0-9]+)?)\s*")
#: The readers seed: which raw tables are each club notice source's, and which of them are generated.
NOTICE_READERS = DBT_DIR / "seeds" / "notice_readers.csv"
#: THE HAND-STAGED RAW TABLES A CONDITIONS LEG MAY WITHDRAW, each with its dbt source: OurHike's field notes and
#: disputes, the ConditionsQuery tables whose database table export_conditions.py's PENDING_READER_SETUP lets go
#: missing. Their base models read source() directly, so a withdrawn one would fail stage A. Named here because this file imports only the standard library; tests/test_build_marts.py holds it against
#: PENDING_READER_SETUP.
WITHDRAWABLE = {"raw_ourhike__notes": "ourhike", "raw_ourhike__disputes": "ourhike"}
#: extract/_run.py's RUNS_TABLE and UNAVAILABLE, as extract/_warehouse.py loads the run log into the warehouse.
RUN_LOG_TABLE, WITHDRAWN_OUTCOME = "_extract_runs", "unavailable"


@dataclass(frozen=True)
class History:
    """Where the row-history snapshots are kept between runs, whether an empty store may start them, and the
    interpreter row_history.py runs on."""

    url: str
    cold_start: bool
    python: str
    #: Whether a store with no Elementary history may start it in this build (the module docstring, "THE ROW HISTORY
    #: IS RESTORED FIRST AND SAVED LAST"): resolve_history()'s rules, against [elementary_started].
    elementary_cold_start: bool = False
    #: --history-on-failure, which reaches row_history.py as --elementary-on-failure (the module docstring,
    #: "--history-on-failure degrade").
    on_failure: str = "fail"


def resolve_history(
    url: str | None,
    *,
    fixtures: bool,
    cold_start: bool,
    python: str,
    started: dict[str, str],
    elementary_started: dict[str, str] | None = None,
) -> tuple[History, str | None]:
    """The store this build restores from and saves to, and a line to print about it. `started` and
    `elementary_started` are row_history_stores.toml's [started] and [elementary_started] (None: no store listed).

    Raises ValueError when no store is named outside --fixtures."""
    if not url:
        if not fixtures:
            raise ValueError(
                "no row-history store: pass --history-url or set OURHIKE_HISTORY_URL. Without one every snapshot "
                "would start its history again in a warehouse this run throws away (pipeline/row_history.py)."
            )
        url = tempfile.mkdtemp(prefix="ourhike-history-")
        return History(url, True, python, True), (
            f"--fixtures with no history store named: a cold start in {url}, a new temporary directory no later run reads"
        )
    if cold_start:
        return History(url, True, python, True), f"--history-cold-start: an empty {url} starts its history in this build"
    name = history_store_name(url)
    if name not in started:
        return History(url, True, python, True), (
            f"::warning title=Row history store not started::{name} is not in row_history_stores.toml, so an empty "
            f"{url} starts its history in this build, and Elementary's. Once this run has saved, list {name} there, "
            "under [started] and [elementary_started], so that from then on an empty store is refused as lost history."
        )
    if name not in (elementary_started or {}):
        return History(url, False, python, True), (
            f"::warning title=Elementary's history not started::{name} is not in row_history_stores.toml's "
            f"[elementary_started], so if {url} holds no elementary.json, Elementary's history starts in this build. "
            f"Once this run has saved, list {name} there, so that from then on a missing one is refused as lost history."
        )
    return History(url, False, python), None


def built_by(environ: dict[str, str]) -> str:
    """What each snapshot version records as `_built_by`: OURHIKE_BUILT_BY when set, else the commit (GITHUB_SHA,
    else `git rev-parse HEAD`) and, in a workflow, `run <GITHUB_RUN_ID>.<GITHUB_RUN_ATTEMPT>`. Only characters a SQL
    string literal takes as they are (macros/row_history.sql writes it into one)."""
    value = environ.get("OURHIKE_BUILT_BY")
    if not value:
        commit = environ.get("GITHUB_SHA")
        if not commit:
            found = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PIPELINE_DIR, capture_output=True, text=True, check=False)
            commit = found.stdout.strip() if found.returncode == 0 else "unknown"
        value = commit[:12]
        if run_id := environ.get("GITHUB_RUN_ID"):
            value += f" run {run_id}.{environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    return "".join(character for character in value if character.isalnum() or character in " .:/_-")


def history_store_name(url: str) -> str:
    """A store's name in row_history_stores.toml: the last part of its URL."""
    return url.rstrip("/").rsplit("/", 1)[-1]


def started_history_stores(path: Path = HISTORY_STORES) -> dict[str, str]:
    return tomllib.loads(path.read_text(encoding="utf-8"))["started"]


def started_elementary_stores(path: Path = HISTORY_STORES) -> dict[str, str]:
    """row_history_stores.toml's [elementary_started]: the stores whose Elementary history has been saved at least once."""
    return tomllib.loads(path.read_text(encoding="utf-8")).get("elementary_started", {})


@dataclass(frozen=True)
class Run:
    """One command of the build: what the log calls it, its argv, the directory it runs in, which of the dbt runs
    main() answers differently it is (STAGE_A or WRITERS, the module docstring, "ONE SOURCE OR ONE WRITER NEVER STOPS
    THE REST"; CHECKS, "ELEMENTARY'S CHECKS RUN AFTER THE WRITERS"; DATA_QUALITY, "THE DATA-QUALITY FILE IS WRITTEN
    LAST"), and what it adds to the build's environment (CHECKS_SWITCH)."""

    label: str
    argv: tuple[str, ...]
    cwd: Path
    stage: str = ""
    env: tuple[tuple[str, str], ...] = ()


#: Run.stage of stage A, of the pub_ writers' dbt run, of Elementary's checks, of the sources' freshness, and of the
#: data-quality file's.
STAGE_A, WRITERS, CHECKS, FRESHNESS, DATA_QUALITY = "stage_a", "writers", "checks", "freshness", "data_quality"


def _builds(
    label: str,
    *,
    dbt: str,
    common: tuple[str, ...],
    alone: tuple[str, ...],
    select: tuple[str, ...],
    exclude: tuple[str, ...],
    after: tuple[str, ...],
    split: bool,
    manifest: dict | None,
    stage: str = "",
    modified: frozenset[str] | None = None,
) -> list[Run]:
    """One `dbt build -s <select> --exclude <exclude>`, or with `split` its three passes (the module docstring, "A MODEL
    TAGGED `builds_alone`"), `alone` being `common` at one thread. Given the manifest, a pass that selects nothing is
    left out, and a build whose tagged-models pass selects nothing is not split at all; `modified` is a state build's
    list for `state:modified` (selects_anything()). Every run carries `stage`, so each of stage A's passes is answered
    as stage A (Run.stage)."""

    def run(name: str, options: tuple[str, ...], chosen: tuple[str, ...], excluded: tuple[str, ...]) -> Run:
        argv = (dbt, "build", *options, *(("-s", *chosen) if chosen else ()), "--exclude", *excluded, *after)
        return Run(name, argv, DBT_DIR, stage)

    tagged, below = f"tag:{BUILDS_ALONE}", f"tag:{BUILDS_ALONE}+"
    # (a), (b) and (c) of the module docstring: name, options, -s items, --exclude items.
    passes = [
        (f"{label}: all but the models that build alone and what they feed", common, select, (*exclude, below)),
        (
            f"{label}: the models that build alone, one at a time",
            alone,
            tuple(f"{item},{tagged}" for item in select) or (tagged,),
            exclude,
        ),
        (
            f"{label}: what the models that build alone feed",
            common,
            tuple(f"{item},{below}" for item in select) or (below,),
            (*exclude, tagged),
        ),
    ]
    if modified is not None and manifest is not None and not selects_anything(manifest, select, exclude, modified):
        # A state build's: most of its builds select nothing, and dbt 2.0.6 read the whole project for 30.9 to 34.2 s
        # before it said one did (the module docstring, "A MODEL TAGGED `builds_alone`").
        return []
    if not split or (manifest is not None and not selects_anything(manifest, *passes[1][2:], modified)):
        return [run(label, common, select, exclude)]
    return [run(*each) for each in passes if manifest is None or selects_anything(manifest, *each[2:], modified)]


def plan(
    steps: list[Step],
    *,
    dbt: str,
    python: str,
    paths: Paths,
    fixtures: bool,
    threads: int | None = None,
    profiles_dir: str = ".",
    lane: str | None = None,
    state: Path | None = None,
    without: tuple[str, ...] = (),
    history: History | None = None,
    snapshots: bool = True,
    save_history: bool = True,
    manifest: dict | None = None,
    withdrawn: tuple[str, ...] = (),
    checks: bool | None = None,
    absent: tuple[str, ...] = (),
    checks_base: Path | None = None,
    held_nodes: tuple[str, ...] = (),
    state_base: Path | None = None,
    modified: frozenset[str] | None = None,
) -> list[Run]:
    """Every command of the build, in order, for these steps, in `lane` (None: every node), less the steps `without` names,
    between the row history's restore and its save when `history` names a store (the save left out when
    `save_history` is false: --no-history-save), and with no snapshot built when `snapshots` is false (the module
    docstring, "--history-on-failure degrade"). Every dbt build but the writers' and the hourly lane's is split around
    the builds_alone models, the writers' runs at one thread but in the hourly lane, and given `manifest` (main()
    plans again once `dbt seed` has written it), the passes it shows select nothing are left out (the module
    docstring, "A MODEL TAGGED `builds_alone`"). Each `withdrawn` raw table (withdrawn_tables()) is left out of every
    dbt build with everything below its source. Every dbt build leaves Elementary's checks out, and with `checks`
    (None: the lane's own answer, runs_checks()) they run after the writers, less the checks on each `absent` source
    (absent_sources()), in their own pass (the module docstring, "ELEMENTARY'S CHECKS RUN AFTER THE WRITERS"), and
    given `checks_base`, a build with no lane runs only those state:modified+ reaches from it (the module docstring,
    "A PULL REQUEST RUNS THE CHECKS ITS CHANGE REACHES"). The lane's data-quality writer builds after them, whether
    or not they ran, after the sources' freshness (freshness_selection()), unless the lane's checks run apart, which
    leaves both to their run (the module docstring, "THE DATA-QUALITY FILE IS WRITTEN LAST"). Each of `held_nodes`, a
    selector of what an earlier failure of this build holds back (failure_holds()), is left out of every dbt build as
    a step that does not run is (the module docstring, "EVERY TEST HAS TWO THRESHOLDS, AND THE ENVIRONMENT DECIDES WHO
    STOPS"). Given `state_base`, the build is a pull request's from main's build (the module docstring, "A PULL REQUEST
    BUILDS ONLY WHAT CHANGED SINCE MAIN'S LAST BUILD"): Elementary's history alone starts cold, `dbt ls` lists what
    changed right after the seeds, and every build but the writers' takes only what changed, what reads the clock and
    what a step rewrote from a changed input, with what each feeds; given `modified`, what that listing found, a build
    that selects none of it is left out."""
    if lane not in (None, *LANES):
        raise ValueError(f"no lane {lane!r}; lanes are {', '.join(LANES)}")
    if state_base is not None:
        if state is not None:
            raise ValueError(
                "--state-base and --state are two different bases: --state is the hourly lane's defer to the monthly "
                "build, --state-base CI's build of what changed in a warehouse main built"
            )
        if lane is not None:
            raise ValueError(f"--state-base is CI's build with no lane: the {lane} lane builds every node it has")
        if not fixtures:
            raise ValueError("--state-base is CI's fixture build's: the warehouse main's dbt job left, under --fixtures")
    if state is not None and lane != HOURLY:
        raise ValueError("--state is the hourly lane's: only it defers to another build's nodes")
    if checks_base is not None and lane is not None:
        raise ValueError(f"--checks-base is a build's with no lane: the {lane} lane runs every check it has")
    if unknown := sorted(set(without) - {step.name for step in steps}):
        raise ValueError(f"--without-step names no entry of STEPS: {', '.join(unknown)}")
    common = ("--profiles-dir", profiles_dir, *(("--threads", str(threads)) if threads else ()))
    alone = ("--profiles-dir", profiles_dir, "--threads", "1")
    builds = {
        "dbt": dbt,
        "common": common,
        "alone": alone,
        "split": lane != HOURLY,
        "manifest": manifest,
        "modified": modified if state_base is not None else None,
    }
    fields = {"warehouse": str(paths.warehouse), "raw_dir": str(paths.raw_dir)}
    running = [step for step in steps if step.name not in without and (lane is None or step.lane == lane)]
    # What a step that does not run here would have unblocked, and what a
    # table the extract withdrew feeds: built by no invocation of this build,
    # so a writer below either keeps its last file.
    held = tuple(f"source:{DERIVED_SOURCE}.{step.table}+" for step in steps if step not in running)
    held += tuple(f"source:{WITHDRAWABLE[table]}.{table}+" for table in withdrawn)
    held += tuple(held_nodes)
    selection: tuple[str, ...] = ()
    lane_exclude: tuple[str, ...] = ()
    after: tuple[str, ...] = ()  # options every dbt build of the lane carries after its --exclude
    if lane == MONTHLY:
        lane_exclude = LANE_EXCLUDES
    elif lane == HOURLY:
        selection = (*LANE_EXCLUDES, *(LANE_PARENTS if state is None else ()))
        after = ("--defer", "--state", str(state)) if state is not None else ("--indirect-selection", "cautious")
    # A state build's (the module docstring, "A PULL REQUEST BUILDS ONLY WHAT CHANGED SINCE MAIN'S LAST BUILD"): what
    # reads the clock, selected by its file, once there is a manifest; the tables a step writes from an input that
    # changed, once `dbt ls` has listed what did; and the option of a build that selects by state, with no --defer.
    clock: list[str] = []  # each a `path:<its file>+` selector
    rewritten: list[str] = []
    by_state: tuple[str, ...] = ()
    if state_base is not None:
        by_state = ("--state", str(state_base))
        if manifest is not None:
            readers = clock_readers(manifest)
            resources = _resources(manifest)
            clock = sorted({selector for uid in readers if (selector := _hold_selector(resources, uid))})
            if modified is not None:
                rewritten = changed_step_tables(manifest, running, modified, readers)
        selection = (STATE_MODIFIED, *clock)

    if checks is None:
        checks = runs_checks(lane)
    runs = [
        # With the checks' switch when they run, so Elementary's dbt_tests describes each (CHECKS_SWITCH).
        Run(
            ELEMENTARY_TABLES,
            (dbt, "run", *common, "--select", "package:elementary"),
            DBT_DIR,
            env=CHECKS_SWITCH if checks else (),
        ),
        Run(SEED, (dbt, "seed", *common), DBT_DIR),
    ]
    if state_base is not None:
        listing = ("-s", "state:modified", *by_state, "--output", "json", "--output-keys", "unique_id", "--quiet")
        runs.append(Run(STATE_LIST_LABEL, (dbt, "ls", "--profiles-dir", profiles_dir, *listing), DBT_DIR, STATE_LIST))
    no_checks = f"tag:{ELEMENTARY_CHECK}"  # every dbt build's: the checks pass runs them, after the writers
    stage_a_exclude = ["package:dbt_project_evaluator", "package:elementary", "path:models/publish", no_checks]
    if running:
        stage_a_exclude.append(f"source:{DERIVED_SOURCE}+")
    no_snapshots = () if snapshots else (SNAPSHOTS,)
    stage_a_exclude += [*held, *lane_exclude, *no_snapshots]
    label = "stage A: everything no Python step reads back"
    if lane == HOURLY:
        label = "stage A of the hourly lane: every node an hourly or daily source reaches, no step reads back"
    runs += _builds(label, **builds, select=selection, exclude=tuple(stage_a_exclude), after=(*after, *by_state), stage=STAGE_A)
    for position, step in enumerate(running):
        arguments = step.command + (step.fixture_args if fixtures else dict(step.lane_args).get(lane, ()))
        runs.append(Run(step.name, (python, *(argument.format(**fields) for argument in arguments)), PIPELINE_DIR))
        later = [f"source:{DERIVED_SOURCE}.{following.table}+" for following in running[position + 1 :]]
        table = f"source:{DERIVED_SOURCE}.{step.table}+"
        unblocked, by = (table,), ()
        if state_base is not None and step.table not in rewritten:
            # The step wrote the rows main's build did (each step re-run over a fixture build's warehouse wrote the
            # same rows, every column but _loaded_at the same: measured 2026-10-15), so only where its table meets
            # what changed, what reads the clock, or an earlier rewritten table is there anything to build again.
            earlier = [each.table for each in running[:position] if each.table in rewritten]
            unblocked = (
                f"{table},{STATE_MODIFIED}",
                *(f"{table},{selector}" for selector in clock),
                *(f"{table},source:{DERIVED_SOURCE}.{other}+" for other in earlier),
            )
            by = by_state
        runs += _builds(
            f"what {DERIVED_SOURCE}.{step.table} unblocks",
            **builds,
            select=unblocked,
            exclude=("path:models/publish", no_checks, *later, *held, *no_snapshots, *lane_exclude),
            after=(*after, *by),
        )
    if lane == HOURLY:
        writers = ("-s", *(f"path:models/publish,{selector}" for selector in LANE_EXCLUDES))
        label = "the hourly lane's pub_ writers"
        leave_out = (no_checks, *lane_exclude, *held)
    else:
        writers = ("-s", "path:models/publish")
        label = "the pub_ writers"
        # The data-quality writers wait for Elementary's checks; no hourly or daily source reaches either, so the
        # hourly lane's selection takes neither.
        leave_out = (no_checks, *DATA_QUALITY_WRITERS.values(), *lane_exclude, *held)
    writers += ("--exclude", *leave_out)
    # One writer at a time but in the hourly lane (the module docstring, "THE PUB_ WRITERS BUILD ONE AT A TIME").
    options = common if lane == HOURLY else alone
    runs.append(Run(label, (dbt, "build", *options, *writers, *after), DBT_DIR, WRITERS))
    if checks:
        runs.append(_checks_run(dbt, alone, lane, (*lane_exclude, *held, *absent), after, checks_base))
    if not checks_apart(lane):
        runs.append(_freshness_run(dbt, common, freshness_selection(lane, fixtures=fixtures)))
        runs.append(_quality_run(dbt, common, lane, (*held, *no_snapshots, *lane_exclude), after))
    if history is not None and state_base is not None:
        # The module docstring, "A PULL REQUEST BUILDS ONLY WHAT CHANGED SINCE MAIN'S LAST BUILD": the warehouse keeps
        # main's snapshots, Elementary's history starts cold as every fixture build's does, and nothing is saved.
        store = ("--url", history.url, "--warehouse", str(paths.warehouse))
        cold = (history.python, "row_history.py", "restore", *store, "--elementary-only", "--cold-start")
        runs.insert(0, Run(ELEMENTARY_COLD_LABEL, cold, PIPELINE_DIR))
    elif history is not None:
        store = ("--url", history.url, "--warehouse", str(paths.warehouse))
        # --cold-start lets Elementary's history start too (row_history.py's docstring, "THE COLD START").
        cold = ("--cold-start",) if history.cold_start else ("--elementary-cold-start",) if history.elementary_cold_start else ()
        policy = ("--elementary-on-failure", "degrade") if history.on_failure == "degrade" else ()
        restore = (history.python, "row_history.py", "restore", *store, *cold, *policy)
        runs.insert(0, Run(RESTORE_LABEL, restore, PIPELINE_DIR))
        if save_history:
            keep = ("--keep-days", str(ELEMENTARY_KEEP_DAYS[lane] if lane else max(ELEMENTARY_KEEP_DAYS.values())))
            runs.append(Run(SAVE_LABEL, (history.python, "row_history.py", "save", *store, *keep, *policy), PIPELINE_DIR))
    return runs


def checks_apart(lane: str | None) -> bool:
    """Whether `lane` runs Elementary's checks in a run of their own after its build (--checks-only), rather than in the
    build: the hourly lane, by HOURLY_LANE_CHECKS (the module docstring, "THE HOURLY LANE'S CHECKS RUN APART")."""
    return lane == HOURLY and HOURLY_LANE_CHECKS == APART


def runs_checks(lane: str | None) -> bool:
    """Whether a build in `lane` runs Elementary's checks itself: every build but one whose lane runs them apart."""
    return not checks_apart(lane)


def _checks_run(
    dbt: str,
    alone: tuple[str, ...],
    lane: str | None,
    left_out: tuple[str, ...],
    after: tuple[str, ...],
    checks_base: Path | None = None,
) -> Run:
    """Elementary's checks pass (the module docstring, "ELEMENTARY'S CHECKS RUN AFTER THE WRITERS"): lane-scoped as the
    writers are, less `left_out`, at one thread, with the monthly lane's training window, and given `checks_base` only
    the checks state:modified+ reaches from that base project's target/ ("A PULL REQUEST RUNS THE CHECKS ITS CHANGE
    REACHES")."""
    no_checks = f"tag:{ELEMENTARY_CHECK}"
    chosen = tuple(f"{no_checks},{selector}" for selector in LANE_EXCLUDES) if lane == HOURLY else (no_checks,)
    if checks_base is not None:
        chosen = tuple(f"{item},state:modified+" for item in chosen)
        after = (*after, "--state", str(checks_base / "target"))
    argv = (dbt, "test", *alone, "-s", *chosen, *(("--exclude", *left_out) if left_out else ()), *after)
    if lane == MONTHLY:
        argv += ("--vars", json.dumps({"days_back": MONTHLY_TRAINING_DAYS}))
    return Run(ELEMENTARY_CHECKS, argv, DBT_DIR, CHECKS, CHECKS_SWITCH)


def freshness_selection(lane: str | None, *, notices_read: bool = False, fixtures: bool = False) -> tuple[str, ...]:
    """The selection of a lane's freshness run (the module docstring, "EACH SOURCE'S FRESHNESS IS MEASURED FOR THE
    DATA-QUALITY FILE"): the hourly lane's is publish-conditions.yml's freshness step's own, the notices job's sources
    only when `notices_read`; the monthly lane's every other source; and a build with no lane's every source, the PDF
    notices left out under `fixtures`. Every one but the hourly lane's leaves out FRESHNESS_LEFT_OUT."""
    if lane == HOURLY:
        return ("-s", f"tag:{CONDITIONS_JOB_TAG}", *((f"tag:{NOTICES_JOB_TAG}",) if notices_read else ()))
    left_out = [*FRESHNESS_LEFT_OUT]
    if lane == MONTHLY:
        left_out += [f"config.meta.cadence:{cadence}" for cadence in FASTER_THAN_MONTHLY]
        left_out += [f"tag:{CONDITIONS_JOB_TAG}", f"tag:{NOTICES_JOB_TAG}"]
    elif fixtures:
        left_out.append(f"tag:{PDF_NOTICE_TAG}")
    return ("--exclude", *left_out)


def _freshness_run(dbt: str, common: tuple[str, ...], selection: tuple[str, ...]) -> Run:
    """`dbt source freshness` on `selection`, Elementary's hook recording each source (FRESHNESS, never a stop)."""
    return Run(FRESHNESS_LABEL, (dbt, "source", "freshness", *common, *selection), DBT_DIR, FRESHNESS)


def freshness_report(returncode: int, results_path: Path | None = None) -> list[str]:
    """What a freshness run measured, for the log, from dbt's sources.json: never an annotation and never the build's
    exit (the module docstring, "EACH SOURCE'S FRESHNESS IS MEASURED FOR THE DATA-QUALITY FILE"). dbt exits 1 when a
    source is past its error limit and 0 when the worst is a warning (measured on 2.0.6, 2026-10-07)."""
    try:
        results = json.loads((results_path or SOURCES_RESULTS_PATH).read_text(encoding="utf-8"))["results"]
    except (OSError, ValueError, KeyError, TypeError):
        return [
            f"-- build_marts: {FRESHNESS_LABEL}: exit {returncode}, and dbt left no sources.json, so the data-quality "
            "file counts no freshness this time; the build goes on"
        ]
    statuses = [str(result.get("status", "")).lower() for result in results]
    counts = {status: statuses.count(status) for status in ("pass", "warn", "error")}
    other = len(statuses) - sum(counts.values())
    return [
        f"-- build_marts: {FRESHNESS_LABEL}: {len(results)} source(s) measured, {counts['pass']} passed, "
        f"{counts['warn']} warned, {counts['error']} past their error limit, {other} not measured; exit {returncode}, "
        "recorded in the data-quality file and never this build's exit"
    ]


def _quality_run(dbt: str, common: tuple[str, ...], lane: str | None, left_out: tuple[str, ...], after: tuple[str, ...]) -> Run:
    """The lane's data-quality writer (the module docstring, "THE DATA-QUALITY FILE IS WRITTEN LAST"), both with no lane.
    It leaves out what every other build does, which neither writer reads, so each dbt build of a lane leaves out the
    same nodes."""
    quality = tuple(DATA_QUALITY_WRITERS.values()) if lane is None else (DATA_QUALITY_WRITERS[lane],)
    argv = (dbt, "build", *common, "-s", *quality, "--exclude", f"tag:{ELEMENTARY_CHECK}", *left_out, *after)
    return Run(DATA_QUALITY_LABEL, argv, DBT_DIR, DATA_QUALITY)


#: The checks run's restore and save of Elementary's history alone (row_history.py's --elementary-only), so the loop in
#: main() can tell them from the build's restore and save of both.
ELEMENTARY_RESTORE_LABEL, ELEMENTARY_SAVE_LABEL = "restore Elementary's history", "save Elementary's history"


def plan_checks(
    steps: list[Step],
    *,
    dbt: str,
    paths: Paths,
    lane: str,
    record: dict,
    threads: int | None = None,
    profiles_dir: str = ".",
    history: History | None = None,
    save_history: bool = True,
    withdrawn: tuple[str, ...] = (),
    absent: tuple[str, ...] = (),
) -> list[Run]:
    """The checks run of `lane`, whose checks run apart, over the warehouse the build that wrote `record` left
    (read_build_record(); the module docstring, "THE HOURLY LANE'S CHECKS RUN APART"): Elementary's history alone
    restored from `history`, Elementary's own tables with the checks' switch, every check the lane has but those on
    a step the build held, a `withdrawn` table or an `absent` source, the sources' freshness on the lane's selection
    (the notices job's sources only when the record says the build read their copy), the lane's data-quality writer,
    and Elementary's history alone saved back (the save left out when `save_history` is false). The restore and the save are left out
    when the record says the build saved no Elementary history, so the checks keep the history it restored."""
    if not checks_apart(lane):
        raise ValueError(f"--checks-only is a lane's whose checks run apart ({HOURLY}); the {lane} lane runs its own")
    if record.get("lane") != lane:
        raise ValueError(f"the warehouse's build record is the {record.get('lane')} lane's, not the {lane} lane's")
    if record.get("state"):
        raise ValueError(f"the build deferred to {record['state']} (--state), which a checks run does not have")
    without = tuple(record.get("without") or ())
    if unknown := sorted(set(without) - {step.name for step in steps}):
        raise ValueError(f"the build record's held steps name no entry of STEPS: {', '.join(unknown)}")
    common = ("--profiles-dir", profiles_dir, *(("--threads", str(threads)) if threads else ()))
    alone = ("--profiles-dir", profiles_dir, "--threads", "1")
    # The build's own selection: no --state (refused above), so every build of it took --indirect-selection cautious.
    after = ("--indirect-selection", "cautious")
    held = tuple(f"source:{DERIVED_SOURCE}.{step.table}+" for step in steps if step.lane != lane or step.name in without)
    held += tuple(f"source:{WITHDRAWABLE[table]}.{table}+" for table in withdrawn)
    # What the build held back for a failure (failure_holds()): checked by nothing, as it built nothing.
    held += tuple(record.get("held_nodes") or ())
    no_snapshots = (SNAPSHOTS,) if record.get("row_history") == "off" else ()
    runs = [
        # With the checks' switch, so Elementary's dbt_tests describes each check the file counts (CHECKS_SWITCH).
        Run(ELEMENTARY_TABLES, (dbt, "run", *common, "--select", "package:elementary"), DBT_DIR, env=CHECKS_SWITCH),
        _checks_run(dbt, alone, lane, (*held, *absent), after),
        _freshness_run(dbt, common, freshness_selection(lane, notices_read=bool(record.get("notices_read_at")))),
        _quality_run(dbt, common, lane, (*held, *no_snapshots), after),
    ]
    if history is not None and record.get("elementary_saved"):
        store = ("--url", history.url, "--warehouse", str(paths.warehouse), "--elementary-only")
        policy = ("--elementary-on-failure", "degrade") if history.on_failure == "degrade" else ()
        runs.insert(
            0, Run(ELEMENTARY_RESTORE_LABEL, (history.python, "row_history.py", "restore", *store, *policy), PIPELINE_DIR)
        )
        if save_history:
            keep = ("--keep-days", str(ELEMENTARY_KEEP_DAYS[lane]))
            save = (history.python, "row_history.py", "save", *store, *keep, *policy)
            runs.append(Run(ELEMENTARY_SAVE_LABEL, save, PIPELINE_DIR))
    return runs


def _cadence(source: dict) -> str | None:
    return ((source.get("config") or {}).get("meta") or {}).get("cadence") or (source.get("meta") or {}).get("cadence")


def _reached(manifest: dict, starts: list[str]) -> set[str]:
    """`starts` and every node below them in the manifest's child_map, as dbt's `+` follows it."""
    children = manifest.get("child_map") or {}
    reached: set[str] = set()
    queue = list(starts)
    while queue:
        node = queue.pop()
        if node in reached:
            continue
        reached.add(node)
        queue.extend(children.get(node) or [])
    return reached


def faster_nodes(manifest: dict) -> set[str]:
    """Every node a faster-than-monthly source reaches."""
    sources = manifest.get("sources") or {}
    return _reached(manifest, [uid for uid, source in sources.items() if _cadence(source) in FASTER_THAN_MONTHLY])


def lane_problems(manifest: dict, steps: list[Step], lane: str | None) -> list[str]:
    """What stops a lane's build: a step with no exposure naming its inputs, a monthly step reading a node an
    hourly or daily source reaches, or a step whose lane is not the lane of what its table unblocks."""
    if lane is None:
        return []
    exposures = {exposure.get("name"): exposure for exposure in (manifest.get("exposures") or {}).values()}
    derived = {
        source.get("name"): uid
        for uid, source in (manifest.get("sources") or {}).items()
        if source.get("source_name") == DERIVED_SOURCE
    }
    reached = faster_nodes(manifest)
    problems = []
    for step in steps:
        exposure = exposures.get(step.name)
        if step.reads_no_model:
            if exposure is not None and (exposure.get("depends_on") or {}).get("nodes"):
                problems.append(
                    f"{step.name} says it reads no dbt node (reads_no_model), and its exposure {step.name} lists some"
                )
        elif exposure is None:
            problems.append(
                f"{step.name} has no exposure named {step.name} listing what it reads, so the {lane} lane cannot "
                "check that it builds the step's inputs"
            )
        elif step.lane == MONTHLY:
            for node in (exposure.get("depends_on") or {}).get("nodes") or []:
                if node in reached:
                    problems.append(
                        f"{step.name} reads {node}, which an hourly or daily source reaches: the monthly lane, where "
                        "the step runs, does not build it, so the step would read a stale or missing input"
                    )
        # A step's lane is the lane of the phone files its table ends in: the
        # models between (its own staging, say) are reached by no source with a
        # cadence, and are built by whichever lane runs the step.
        unblocked = _reached(manifest, [derived[step.table]] if step.table in derived else [])
        writers = sorted(node for node in unblocked if _is_writer(node))
        if step.lane == MONTHLY and writers and all(node in reached for node in writers):
            problems.append(
                f"{step.name} runs in the monthly lane, and every writer derived.{step.table} feeds is the hourly "
                f"lane's ({', '.join(writers)}): give its STEPS entry lane=HOURLY"
            )
        if step.lane == HOURLY and (monthly := [node for node in writers if node not in reached]):
            problems.append(
                f"{step.name} runs in the hourly lane, and derived.{step.table} feeds monthly-lane writers "
                f"({', '.join(monthly)}), which no hourly or daily source reaches: the monthly lane leaves out what an "
                "hourly step unblocks, so nothing would write them"
            )
    return problems


def _is_writer(node: str) -> bool:
    """A pub_ writer's unique id, `model.<project>.pub_<file>` (models/publish/; the evaluator holds the prefix)."""
    parts = node.split(".")
    return len(parts) >= 3 and parts[0] == "model" and parts[2].startswith("pub_")


def _resources(manifest: dict) -> dict[str, dict]:
    """Every node, source, exposure and unit test in the manifest, by unique id."""
    kinds = ("nodes", "sources", "exposures", "unit_tests")
    return {uid: node for kind in kinds for uid, node in (manifest.get(kind) or {}).items()}


def _tags(node: dict) -> set[str]:
    return set(node.get("tags") or []) | set((node.get("config") or {}).get("tags") or [])


def _ancestors(manifest: dict, start: str) -> set[str]:
    """Every node above `start` in the manifest's parent_map, as dbt's leading `+` follows it, `start` left out."""
    parents = manifest.get("parent_map") or {}
    return _reached({"child_map": parents}, list(parents.get(start) or []))


def _name(uid: str) -> str:
    return uid.split(".")[2] if uid.count(".") >= 2 else uid


def alone_problems(manifest: dict) -> list[str]:
    """What stops a build split around the builds_alone models (the module docstring, "A MODEL TAGGED `builds_alone`"):
    a tagged model reading, at any distance, a model the split builds only after the tagged ones (an untagged
    descendant of another tagged model); a test the tagged models' pass runs that reads one; and a tagged model an
    hourly or daily source reaches."""
    resources = _resources(manifest)
    tagged = {uid for uid, node in (manifest.get("nodes") or {}).items() if BUILDS_ALONE in _tags(node)}
    # Each node pass (c) builds, with the tagged models above it.
    later: dict[str, set[str]] = {}
    for uid in sorted(tagged):
        for node in _reached(manifest, [uid]) - tagged:
            later.setdefault(node, set()).add(uid)

    def why(node: str) -> str:
        return f"{_name(node)}, which is downstream of {', '.join(sorted(map(_name, later[node])))}"

    problems = []
    for uid in sorted(tagged):
        for ancestor in sorted(_ancestors(manifest, uid) & later.keys()):
            problems.append(
                f"{_name(uid)} builds alone ({BUILDS_ALONE}) and reads {why(ancestor)}: the split builds that only after "
                f"the models that build alone, so {_name(uid)} would be built from a stale or missing table. Tag every "
                f"model between them {BUILDS_ALONE} too, or untag one end"
            )
    parents = manifest.get("parent_map") or {}
    for test in sorted(uid for uid, node in resources.items() if node.get("resource_type") in ("test", "unit_test")):
        read = set(parents.get(test) or [])
        if read & tagged and (stale := sorted(read & later.keys())):
            problems.append(
                f"{test} tests {', '.join(sorted(map(_name, read & tagged)))}, which builds alone ({BUILDS_ALONE}), and "
                f"reads {'; '.join(map(why, stale))}: it would run before that is built"
            )
    for uid in sorted(tagged & faster_nodes(manifest)):
        problems.append(
            f"{_name(uid)} builds alone ({BUILDS_ALONE}), and an hourly or daily source reaches it: the hourly lane never "
            "splits its builds (each split is one more dbt invocation inside its step cap), so it would build beside "
            "other models there"
        )
    return problems


def _matching(manifest: dict, criterion: str, *, selecting: bool, modified: frozenset[str] | None = None) -> set[str]:
    """What one dbt selector criterion (`method:value`, its graph `+`s, no `,`) can select: exactly for the methods
    this file's commands use, `state:modified` among them once `modified` holds what dbt listed for it, and for any
    other, everything when `selecting` and nothing when not, so that selects_anything() errs toward running a pass."""
    resources = _resources(manifest)
    body = criterion.removeprefix("+").removesuffix("+")
    method, colon, value = body.partition(":")
    found: set[str] | None = None
    if not colon or any(character in body for character in "*?@+ "):
        found = None  # a bare name, a wildcard, `@` or a depth such as `2+`: not read here
    elif method == "state":
        found = set(modified) if value == "modified" and modified is not None else None
    elif method == "source" and len(parts := value.split(".")) <= 2:
        found = {
            uid
            for uid, node in (manifest.get("sources") or {}).items()
            if [node.get("source_name"), node.get("name")][: len(parts)] == parts
        }
    elif method == "tag":
        found = {uid for uid, node in resources.items() if value in _tags(node)}
    elif method == "path":
        prefix = value.rstrip("/")
        found = {
            uid
            for uid, node in resources.items()
            if (path := node.get("original_file_path") or "") == prefix or path.startswith(prefix + "/")
        }
    elif method == "package":
        found = {uid for uid, node in resources.items() if node.get("package_name") == value}
    elif method == "resource_type":
        found = {uid for uid, node in resources.items() if node.get("resource_type") == value}
    elif method == "config.meta.cadence":
        found = {uid for uid, node in resources.items() if _cadence(node) == value}
    if found is None:
        return set(resources) | set(manifest.get("child_map") or {}) if selecting else set()
    below = _reached(manifest, sorted(found)) if criterion.endswith("+") else set()
    above = _reached({"child_map": manifest.get("parent_map") or {}}, sorted(found)) if criterion.startswith("+") else set()
    return found | below | above


def selects_anything(
    manifest: dict, select: tuple[str, ...], exclude: tuple[str, ...], modified: frozenset[str] | None = None
) -> bool:
    """Whether `dbt build -s <select> --exclude <exclude>` can run anything in this manifest: a model, seed, snapshot or
    test. It over-reads `select` and under-reads `exclude`, so a pass is skipped only when dbt would surely run nothing
    in it. Tests go as dbt's default (eager) indirect selection takes them, which no split build changes: in with any
    parent selected, out only here with every parent excluded (where eager takes out a test with any). `modified` is
    what `dbt ls -s state:modified` listed in a state build, read for `state:modified` (_matching())."""
    tests = ("test.", "unit_test.")
    if select:
        chosen: set[str] = set()
        for item in select:
            chosen |= set.intersection(
                *(_matching(manifest, part, selecting=True, modified=modified) for part in item.split(","))
            )
    else:
        chosen = set(_resources(manifest)) | set(manifest.get("child_map") or {})
    children, parents = manifest.get("child_map") or {}, manifest.get("parent_map") or {}
    chosen |= {child for uid in chosen for child in children.get(uid) or [] if child.startswith(tests)}
    excluded: set[str] = set()
    for item in exclude:
        excluded |= set.intersection(*(_matching(manifest, part, selecting=False, modified=modified) for part in item.split(",")))
    excluded |= {uid for uid in chosen if uid.startswith(tests) and parents.get(uid) and set(parents[uid]) <= excluded}
    return any(uid.split(".")[0] in ("model", "seed", "snapshot", "test", "unit_test") for uid in chosen - excluded)


def _code(text: str | None) -> str:
    """SQL or Jinja with its comments removed, for CLOCK."""
    return _COMMENTS.sub(" ", text or "")


def clock_readers(manifest: dict) -> list[str]:
    """The unique id of every model, snapshot and test of this project, a pub_ writer aside, whose code reads the clock
    (CLOCK), itself or through a macro it calls at any depth: what a state build always selects, by its file
    (_hold_selector()), since main's copy holds main's day (the module docstring, "A PULL REQUEST BUILDS ONLY WHAT
    CHANGED SINCE MAIN'S LAST BUILD"). The writers build whole in every build already."""
    macros = manifest.get("macros") or {}
    callers: dict[str, set[str]] = {}
    for uid, macro in macros.items():
        for called in (macro.get("depends_on") or {}).get("macros") or []:
            callers.setdefault(called, set()).add(uid)
    reading = _reached(
        {"child_map": callers}, [uid for uid, macro in macros.items() if CLOCK.search(_code(macro.get("macro_sql")))]
    )
    project = manifest.get("metadata", {}).get("project_name") or "ourhike"
    found = set()
    for uid, node in (manifest.get("nodes") or {}).items():
        if node.get("package_name") != project or node.get("resource_type") not in ("model", "snapshot", "test"):
            continue
        if _is_writer(uid):
            continue
        if CLOCK.search(_code(node.get("raw_code"))) or reading & set((node.get("depends_on") or {}).get("macros") or []):
            found.add(uid)
    return sorted(found)


def _derived_source(manifest: dict, table: str) -> str | None:
    for uid, source in (manifest.get("sources") or {}).items():
        if source.get("source_name") == DERIVED_SOURCE and source.get("name") == table:
            return uid
    return None


def changed_step_tables(manifest: dict, steps: list[Step], modified: frozenset[str], clock: list[str]) -> list[str]:
    """The derived table of each of `steps`, in order, whose step reads an input that changed: its step_<name> exposure
    lists a node below what dbt's state:modified listed (`modified`), below what reads the clock (`clock`,
    clock_readers()), or below the table of an earlier step this answers for. A state build builds what each of those
    tables unblocks whole, since the step wrote it again from inputs main's build did not have (the module docstring,
    "A PULL REQUEST BUILDS ONLY WHAT CHANGED SINCE MAIN'S LAST BUILD")."""
    changed = _reached(manifest, sorted({*modified, *clock}))
    tables = []
    for step in steps:
        if step.reads_no_model or not steps_reading(manifest, [step], changed):
            continue
        tables.append(step.table)
        if source := _derived_source(manifest, step.table):
            changed |= _reached(manifest, [source])
    return tables


def state_report(manifest: dict, modified: frozenset[str], runs: list[Run], steps: list[Step]) -> list[str]:
    """What a state build found and planned, for the log: what dbt listed by kind, what reads the clock, which steps'
    tables build whole, and the dbt builds left (the module docstring, "A PULL REQUEST BUILDS ONLY WHAT CHANGED SINCE
    MAIN'S LAST BUILD")."""
    kinds: dict[str, int] = {}
    for uid in modified:
        kinds[uid.split(".", 1)[0]] = kinds.get(uid.split(".", 1)[0], 0) + 1
    clock = clock_readers(manifest)
    rewritten = changed_step_tables(manifest, steps, modified, clock)
    builds = [run.label for run in runs if run.argv[1:2] == ("build",)]
    return [
        f"-- build_marts: dbt lists {len(modified)} node(s) changed since main's build"
        + (f" ({', '.join(f'{count} {kind}' for kind, count in sorted(kinds.items()))})" if kinds else ""),
        f"-- build_marts: {len(clock)} node(s) read the clock and build again in every state build: "
        f"{', '.join(map(_name, clock)) or 'none'}",
        f"-- build_marts: steps that read a changed input, so what their table unblocks builds whole: "
        f"{', '.join(step.name for step in steps if step.table in rewritten) or 'none'}",
        f"-- build_marts: {len(builds)} dbt build(s) left to run: {'; '.join(builds) or 'none'}",
    ]


def listed_ids(stdout: str) -> frozenset[str]:
    """The unique ids `dbt ls --output json --output-keys unique_id` printed, one JSON object a line; other lines are
    dbt's own and are skipped."""
    found = set()
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            found.add(json.loads(line)["unique_id"])
        except (ValueError, KeyError, TypeError):
            continue
    return frozenset(found)


def state_base_problems(head_manifest: dict, base: Path) -> list[str]:
    """Why a state build cannot trust `base` (--state-base, the directory holding main's manifest.json): its manifest
    cannot be read, or a macro differs from this build's (state_base.macro_problems())."""
    path = base / "manifest.json"
    try:
        base_manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as unread:
        return [f"main's manifest, {path}, could not be read ({unread})"]
    return state_base.macro_problems(head_manifest, base_manifest)


#: How much of a failed test's answer the log shows: rows, and characters a value. Enough to name the source and the
#: row; little enough that a wording test's failure does not copy a club's paragraph into a public log.
FAILED_ROWS_SHOWN = 10
FAILED_VALUE_WIDTH = 120


def _rows_query(result: dict, manifest: dict) -> str:
    """The SQL whose rows show why `result`'s test failed: its compiled SQL, or for dbt_utils' expression_is_true,
    which selects a constant, the rows of the model the test is attached to where the expression does not hold."""
    node = manifest.get("nodes", {}).get(result["unique_id"], {})
    meta = node.get("test_metadata") or {}
    attached = manifest.get("nodes", {}).get(node.get("attached_node") or "", {})
    if meta.get("name") == "expression_is_true" and attached.get("relation_name"):
        where = (node.get("config") or {}).get("where")
        condition = f"not ({meta['kwargs']['expression']})" + (f" and ({where})" if where else "")
        return f"select * from {attached['relation_name']} where {condition}"
    return (result.get("compiled_code") or "").strip().rstrip(";")


def failed_test_rows(
    warehouse: Path,
    since: float,
    results_path: Path | None = None,
    manifest_path: Path | None = None,
    *,
    statuses: tuple[str, ...] = ("fail", "error"),
    only: set[str] | None = None,
) -> list[str]:
    """What each test that failed or errored in the dbt run that just ended returned, as log lines (`statuses` to ask
    for others, such as the warnings of the tests that hold a source; `only` to ask for these unique ids alone).

    dbt 2.0.6 prints a failed test's name and row count and nothing of the rows, and no artifact keeps the
    warehouse, so a failure on data only a live run holds (soak run 525, publish-conditions.yml 37216623795: three
    tests on the first real club notices) could not be read. Each failed test's compiled SQL is asked again, read-only,
    for FAILED_ROWS_SHOWN rows, every value cut at FAILED_VALUE_WIDTH characters (_rows_query(): for
    expression_is_true, the attached model's own failing rows, since soak run 526 printed its constant). A
    run_results.json older than `since` is an earlier run's, and says nothing about this failure: main() passes -inf
    after a dbt run, whose earlier file it removed before the run, and the start of a Python step, which writes none."""
    path = results_path or RUN_RESULTS_PATH
    try:
        if path.stat().st_mtime < since:
            return []
        results = json.loads(path.read_text(encoding="utf-8"))["results"]
    except (OSError, ValueError, KeyError):
        return []
    failed = [
        result
        for result in results
        if result.get("unique_id", "").startswith("test.")
        and result.get("status") in statuses
        and (only is None or result.get("unique_id") in only)
    ]
    if not failed:
        return []
    import duckdb

    try:
        manifest = json.loads((manifest_path or MANIFEST_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    lines = []
    with duckdb.connect() as con:
        try:
            con.execute("load spatial")
        except duckdb.Error:
            pass  # a test that needs it says so below
        con.execute(f"attach '{warehouse}' as warehouse (read_only)")
        con.execute("use warehouse")
        for result in failed:
            lines.append(f"::group::{result['unique_id']}: {result.get('failures')} row(s), {result.get('status')}")
            code = _rows_query(result, manifest)
            try:
                if not code:
                    raise ValueError("run_results.json holds no compiled SQL for it")
                cursor = con.execute(f"select * from ({code}) limit {FAILED_ROWS_SHOWN}")
                names = [column[0] for column in cursor.description]
                for row in cursor.fetchall():
                    shown = {name: None if value is None else str(value)[:FAILED_VALUE_WIDTH] for name, value in zip(names, row)}
                    lines.append(json.dumps(shown, ensure_ascii=False))
            except (duckdb.Error, ValueError) as failure:
                lines.append(f"(not asked again: {failure})")
            lines.append("::endgroup::")
    return lines


def _run_results_document(path: Path) -> dict | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) and isinstance(document.get("results"), list) else None


def retry_argv(run: Run) -> tuple[str, ...]:
    """`dbt retry` for the failed `dbt build` `run`: its failed nodes and the ones they skipped, at one thread, with the
    build's own profiles and `--indirect-selection` (the module docstring, "A FAILED dbt BUILD IS RETRIED")."""
    profiles = run.argv[run.argv.index("--profiles-dir") + 1] if "--profiles-dir" in run.argv else "."
    indirect = run.argv[run.argv.index("--indirect-selection") :][:2] if "--indirect-selection" in run.argv else ()
    return (run.argv[0], "retry", "--profiles-dir", profiles, "--threads", "1", *indirect)


def retry_failed_build(
    run: Run, env: dict, completed: subprocess.CompletedProcess, results_path: Path | None = None
) -> subprocess.CompletedProcess:
    """`dbt retry` after the failed `dbt build` `run`, up to DBT_RETRIES times, until one exits 0; the last attempt's
    process. Then run_results.json holds every node the build ran, each with its last attempt's result, because a
    retry's own file holds only the nodes it retried."""
    path = results_path or RUN_RESULTS_PATH
    first = _run_results_document(path)
    attempts = []
    for attempt in range(1, DBT_RETRIES + 1):
        print(
            f"-- build_marts: {run.label} failed (exit {completed.returncode}); dbt retry {attempt}/{DBT_RETRIES} at one "
            "thread, of the nodes that failed and the ones they skipped",
            flush=True,
        )
        completed = subprocess.run(retry_argv(run), cwd=run.cwd, env=env, check=False)
        if (retried := _run_results_document(path)) is not None:
            attempts.append(retried)
        if completed.returncode == 0:
            print(f"-- build_marts: {run.label} passed on retry {attempt}", flush=True)
            break
    if first is not None and attempts:
        latest = {result.get("unique_id"): result for result in first["results"]}
        for retried in attempts:
            latest.update({result.get("unique_id"): result for result in retried["results"]})
        path.write_text(json.dumps({**first, "results": list(latest.values())}), encoding="utf-8")
    return completed


def read_run_results(since: float, results_path: Path | None = None) -> list[dict] | None:
    """The results in run_results.json, or None when it is missing, unreadable or older than `since` (an earlier run's;
    failed_test_rows() says what main() passes)."""
    path = results_path or RUN_RESULTS_PATH
    try:
        if path.stat().st_mtime < since:
            return None
        return json.loads(path.read_text(encoding="utf-8"))["results"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _node(manifest: dict, unique_id: str) -> dict:
    return (manifest.get("nodes") or {}).get(unique_id) or (manifest.get("unit_tests") or {}).get(unique_id) or {}


def source_holds(results: list[dict], manifest: dict) -> set[str]:
    """The tests that warned in this run and whose `meta` says a warning holds a source (HOLDS_A_SOURCE)."""
    held = set()
    for result in results:
        if result.get("status") != "warn":
            continue
        node = _node(manifest, result.get("unique_id", ""))
        meta = {**(node.get("meta") or {}), **((node.get("config") or {}).get("meta") or {})}
        if meta.get(HOLDS_A_SOURCE):
            held.add(result["unique_id"])
    return held


def data_environment(environ: dict[str, str]) -> str:
    """OURHIKE_DATA_ENV as dbt_project.yml's switch reads it: `dev` when unset or empty, else one of lib/data_env.py's
    three exactly as written, so that this file and dbt never read one value two ways. Anything else is refused
    (ValueError), as publish.py refuses it: `uat` is a typo, and read as dev it would stop a production build."""
    name = environ.get(data_env.ENVIRONMENT_VAR) or ""
    if not name:
        return data_env.DEV
    try:
        return data_env.validate(name)
    except data_env.UnknownEnvironment as unknown:
        raise ValueError(str(unknown)) from None


def builds_on(environment: str) -> bool:
    """Whether a build in `environment` goes on past a failure (BUILDS_ON): production and UA, never dev or CI."""
    return environment in BUILDS_ON


def passes(failures: object, threshold: object) -> bool:
    """Whether `failures` passes a test's threshold (`>0`, `> 50`, `!= 0`), as dbt compares the two. Unreadable, either
    one counts as passed: a test this cannot read is an error rather than a warning (round toward caution)."""
    match = THRESHOLD.fullmatch(str(threshold))
    if match is None or isinstance(failures, bool) or not isinstance(failures, (int, float)):
        return True
    operator, number = match.group(1), float(match.group(2))
    return {
        ">": failures > number,
        ">=": failures >= number,
        "<": failures < number,
        "<=": failures <= number,
        "=": failures == number,
        "==": failures == number,
        "!=": failures != number,
        "<>": failures != number,
    }[operator]


def relabelled_errors(results: list[dict], manifest: dict, *, history_off: bool = False) -> dict[str, str]:
    """The tests that warned in this dbt run past their own `error_if`, each with its failures and threshold (the module
    docstring, "EVERY TEST HAS TWO THRESHOLDS, AND THE ENVIRONMENT DECIDES WHO STOPS").

    In production and UA dbt_project.yml's switch makes every failing test a warning, and dbt does not evaluate
    `error_if` under warn (measured on dbt 2.0.6, 2026-10-15), so this is where an error is told from a warning. A test
    whose meta says STAYS_AT_WARN is left out, and so is one that HOLDS_A_SOURCE, which source_holds() reports. With
    `history_off` (OURHIKE_ROW_HISTORY=off, "--history-on-failure degrade"), so is a mart's not_null on its two row
    dates, whose severity reads that switch: both dates are null by design there, and DEGRADED_EXIT already turns the
    run red for it. In dev and CI the switch makes dbt itself fail such a test, so a warning past its error_if is only
    ever one whose own YAML says `severity: warn`."""
    found: dict[str, str] = {}
    for result in results:
        if result.get("status") != "warn":
            continue
        unique_id = result.get("unique_id", "")
        node = _node(manifest, unique_id)
        meta = {**(node.get("meta") or {}), **((node.get("config") or {}).get("meta") or {})}
        if meta.get(STAYS_AT_WARN) or meta.get(HOLDS_A_SOURCE):
            continue
        if history_off and "OURHIKE_ROW_HISTORY" in str((node.get("unrendered_config") or {}).get("severity", "")):
            continue
        error_if = (node.get("config") or {}).get("error_if", "!= 0")
        if passes(result.get("failures"), error_if):
            found[unique_id] = f"{result.get('failures')} against error_if {error_if}"
    return found


def _hold_selector(resources: dict[str, dict], unique_id: str) -> str | None:
    """The dbt selector for `unique_id` and everything below it: `source:<source>.<table>+`, else `path:<its file>+`."""
    node = resources.get(unique_id) or {}
    if unique_id.startswith("source."):
        return f"source:{node.get('source_name')}.{node.get('name')}+"
    path = node.get("original_file_path")
    return f"path:{path}+" if path else None


def failure_holds(results: list[dict], manifest: dict) -> tuple[list[str], list[str], set[str]]:
    """What the failures of this dbt run hold back from every later dbt build of a build that goes on (BUILDS_ON): each
    failure with its status, the selectors every later build excludes, and the nodes they reach.

    A model, seed or snapshot that errored holds itself and everything below it; a data test or a unit test that failed
    or errored holds everything below each node it reads, which is what dbt itself skipped in the run where it failed
    (measured on dbt 2.0.6, 2026-10-15: a failing test at error skipped every descendant of its model, a failing unit
    test its model). Later runs would otherwise build those nodes from a table this build never made, or a writer
    would write a file from it. Skipped nodes are below a failure and say nothing of their own."""
    resources = _resources(manifest)
    failed: list[str] = []
    roots: set[str] = set()
    for result in results:
        unique_id = result.get("unique_id", "")
        status = result.get("status")
        if status not in ("error", "fail", "runtime error"):
            continue
        failed.append(f"{_name(unique_id)} ({status})")
        if unique_id.split(".", 1)[0] in ("model", "seed", "snapshot"):
            roots.add(unique_id)
        else:
            roots.update(_depends_on(manifest, unique_id))
    selectors = sorted({selector for root in roots if (selector := _hold_selector(resources, root))})
    return failed, selectors, _reached(manifest, sorted(roots))


def steps_reading(manifest: dict, steps: list[Step], nodes: set[str]) -> list[str]:
    """The STEPS entries whose exposure (lane_problems() asks every lane's step for one) reads any of `nodes`."""
    exposures = {exposure.get("name"): exposure for exposure in (manifest.get("exposures") or {}).values()}
    return [
        step.name for step in steps if set(((exposures.get(step.name) or {}).get("depends_on") or {}).get("nodes") or []) & nodes
    ]


def failed_checks(results: list[dict] | None) -> list[str]:
    """Elementary's checks that finished past their error threshold (`fail`) or could not run, by name."""
    return sorted(
        str(result.get("unique_id", "")).removeprefix("test.")
        for result in results or []
        if result.get("status") in ("fail", "error", "runtime error")
    )


def write_step_summary(lines: list[str], environ: dict[str, str] | None = None) -> None:
    """Append `lines` to the run summary page, $GITHUB_STEP_SUMMARY, where a workflow sets one."""
    path = (environ if environ is not None else os.environ).get("GITHUB_STEP_SUMMARY")
    if not path or not lines:
        return
    with open(path, "a", encoding="utf-8") as page:
        page.write("\n".join(lines) + "\n\n")


#: A dbt result that is a failure: a model or snapshot that errored, a test that failed or errored, and a node dbt
#: skipped because something it needs failed.
FAILED_STATUSES = ("error", "fail", "skipped", "runtime error")


def _depends_on(manifest: dict, unique_id: str) -> list[str]:
    node = _node(manifest, unique_id)
    return list((node.get("depends_on") or {}).get("nodes") or []) + (
        [node["attached_node"]] if node.get("attached_node") else []
    )


def failed_writers(results: list[dict], manifest: dict) -> tuple[dict[str, str], list[str]]:
    """The pub_ writers this dbt run failed, each with why, and every other failure in it.

    A writer fails when its own model did not succeed, or when a test or unit test of it failed: dbt builds a model
    before its tests, so a writer whose not_null test failed has already written its file."""
    models: dict[str, str] = {}
    tests: dict[str, str] = {}
    others: list[str] = []
    for result in results:
        unique_id = result.get("unique_id", "")
        status = result.get("status")
        if status not in FAILED_STATUSES:
            continue
        if _is_writer(unique_id):
            models[unique_id] = f"its model finished {status}"
            continue
        tested = [node for node in _depends_on(manifest, unique_id) if _is_writer(node)]
        if tested and unique_id.split(".", 1)[0] in ("test", "unit_test"):
            # A test skipped because its writer failed says nothing the writer's own result does not.
            if status != "skipped":
                for writer in tested:
                    tests.setdefault(writer, f"{unique_id} finished {status}")
            continue
        others.append(unique_id)
    # A failed unit test says more than the writer dbt then skipped; a writer's own error, more than nothing.
    return {**models, **tests}, others


def writer_files(manifest: dict, writers: set[str] | list[str], processed_dir: Path) -> dict[str, Path]:
    """Each writer's file in the processed directory, by its `location` (macros/materializations/phone_file.sql)."""
    files = {}
    for writer in writers:
        location = (_node(manifest, writer).get("config") or {}).get("location")
        if location:
            files[writer] = processed_dir / location
    return files


def notice_readers(path: Path | None = None) -> list[dict[str, str]]:
    with (path or NOTICE_READERS).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _ancestor_sources(manifest: dict, unique_id: str) -> set[str]:
    """Every source node above `unique_id`, by the manifest's parent_map (else each node's depends_on)."""
    parents = manifest.get("parent_map")
    seen: set[str] = set()
    sources: set[str] = set()
    queue = [unique_id]
    while queue:
        node = queue.pop()
        if node in seen:
            continue
        seen.add(node)
        if node.startswith("source."):
            sources.add(node)
            continue
        queue.extend((parents.get(node) or []) if parents is not None else _depends_on(manifest, node))
    return sources


def one_sources_failures(results: list[dict], manifest: dict, readers: list[dict[str, str]]) -> dict[str, list[str]] | None:
    """The generated club notice sources whose own models or data tests failed in this dbt run, each with its raw
    tables, or None unless every failure in it is that (the module docstring, "ONE SOURCE OR ONE WRITER NEVER STOPS
    THE REST").

    A model that errored, or a data test that errored or failed, is one source's own when the only club notice raw
    tables above it are that one source's, and the source is generated (seeds/notice_readers.csv's `staged_by` is a
    model, never `hand`): its base and staging models read an absent table as typed and empty (macros/notices.sql's
    notice_raw_table), a test on the absent table itself passes (tests/generic/duplicates_are_exact.sql), and the
    gate holds the source with that reason. Tests count since publish-conditions.yml run 599 (37999435763,
    2026-10-09), where a held Nebraska source's key test could not bind `globalid`, a column its layer does not
    have, and that one error stopped every hourly file. A union of several sources, a hand-staged source's model, a
    unit test, which fails on the code and not on one source's rows, and anything else is not one source's own, so
    the build stops on it as before. Skipped nodes are what a failure left unbuilt and say nothing of their own."""
    by_table = {row["raw_table"]: row for row in readers}
    tables_of: dict[str, list[str]] = {}
    for row in readers:
        tables_of.setdefault(row["source_key"], []).append(row["raw_table"])
    hand = {row["source_key"] for row in readers if row["staged_by"] == "hand"}
    sources = manifest.get("sources") or {}
    held: dict[str, list[str]] = {}
    for result in results:
        unique_id = result.get("unique_id", "")
        status = result.get("status")
        if status not in FAILED_STATUSES or status == "skipped":
            continue
        own = (unique_id.startswith("model.") and status == "error") or (
            unique_id.startswith("test.") and status in ("error", "fail")
        )
        if not own:
            return None
        keys = set()
        for source in _ancestor_sources(manifest, unique_id):
            node = sources.get(source) or {}
            for name in (node.get("identifier"), node.get("name")):
                if name in by_table:
                    keys.add(by_table[name]["source_key"])
        if len(keys) != 1 or keys & hand:
            return None
        (key,) = keys
        held[key] = sorted(set(tables_of[key]))
    return held or None


def withdrawn_tables(warehouse: Path, schema: str = "raw") -> tuple[str, ...]:
    """Each WITHDRAWABLE table the warehouse lacks and whose newest run log row says the extract withdrew it.

    A table absent for any other reason is not answered here, so its build fails as before: a missing table is not
    evidence that it was withdrawn (extract/_warehouse.py's BuildRefused)."""
    if not warehouse.exists():
        return ()
    import duckdb

    with duckdb.connect(str(warehouse), read_only=True) as con:
        present = {
            name
            for (name,) in con.execute(
                "select table_name from information_schema.tables where table_schema = ?", [schema]
            ).fetchall()
        }
        if RUN_LOG_TABLE not in present:
            return ()
        newest = dict(
            con.execute(
                f'select table_name, arg_max(outcome, run_id) from "{schema}"."{RUN_LOG_TABLE}" '
                "where table_name in (select unnest(?)) group by table_name",
                [sorted(WITHDRAWABLE)],
            ).fetchall()
        )
    return tuple(table for table in sorted(WITHDRAWABLE) if table not in present and newest.get(table) == WITHDRAWN_OUTCOME)


def absent_sources(manifest: dict, warehouse: Path, lane: str | None, schema: str = "raw") -> tuple[str, ...]:
    """`source:<source>.<table>` for each raw table of `lane`'s (every one with no lane) that the warehouse does not
    hold, for the checks pass to leave out: a check on a table that is not there errors ("Table with name ... does
    not exist", measured 2026-10-08 on four of the fixture warehouse's notice tables), and its absence says nothing
    about the data. A generated base model reads such a table as no rows (macros/raw_or_empty.sql,
    macros/notices.sql), so the build itself goes on: a PDF's table where the extract had no pypdf, a keyed API whose
    key the job lacks, a layer that has never landed."""
    if not warehouse.exists():
        return ()
    import duckdb

    with duckdb.connect(str(warehouse), read_only=True) as con:
        present = {
            name
            for (name,) in con.execute(
                "select table_name from information_schema.tables where table_schema = ?", [schema]
            ).fetchall()
        }
    faster = faster_nodes(manifest) if lane is not None else set()
    left_out = []
    for uid, source in sorted((manifest.get("sources") or {}).items()):
        if source.get("schema") != schema or (source.get("identifier") or source.get("name")) in present:
            continue
        if lane is not None and (uid in faster) != (lane == HOURLY):
            continue  # the other lane's table, which this lane's checks never select
        left_out.append(f"source:{source.get('source_name')}.{source.get('name')}")
    return tuple(left_out)


def checks_report(results: list[dict] | None, returncode: int, *, none_is_an_answer: bool = False) -> list[str]:
    """What the log says about Elementary's checks pass, which never changes a production or UA build's exit (the module
    docstring, "ELEMENTARY'S CHECKS RUN AFTER THE WRITERS"): a count of each status, every check that warned, failed or
    errored by name, each failure's and error's first line cut at FAILED_VALUE_WIDTH, an annotation (`::error`) naming
    the checks that finished past their error threshold, and one (`::warning`) when any check errored or
    the pass ended without results. No check's rows: Elementary keeps none (dbt_project.yml's test_sample_row_count).
    `none_is_an_answer` for a pass that selects what a change reaches ("A PULL REQUEST RUNS THE CHECKS ITS CHANGE
    REACHES"): a change that reaches no check selects none, which is said without an annotation, and so is a pass
    that exited 0 and left no results, as dbt may answer a selection of nothing."""
    if results is None and none_is_an_answer and returncode == 0:
        results = []
    if results is None:
        return [
            f"::warning title=Elementary's checks recorded nothing::the checks pass ended with exit {returncode} and left "
            "no run_results.json of its own, so no check of this build is reported. The build and its publish go on."
        ]
    statuses: dict[str, int] = {}
    for result in results:
        statuses[str(result.get("status"))] = statuses.get(str(result.get("status")), 0) + 1
    counts = ", ".join(f"{count} {status}" for status, count in sorted(statuses.items())) or "none selected"
    lines = [f"-- build_marts: {ELEMENTARY_CHECKS}: {len(results)} check(s), {counts}; exit {returncode}"]
    if not results and none_is_an_answer:
        lines.append(f"-- build_marts: {ELEMENTARY_CHECKS}: nothing this change reaches carries a check")
    elif not results:
        # Every lane's pass selects its marts' checks at least, so none at all is a switch or a selection gone wrong.
        lines.append(
            f"::warning title=Elementary's checks ran none::the checks pass selected no check (exit {returncode}), so "
            "nothing of this build was checked: CHECKS_SWITCH or the pass's selection is wrong. The build and its "
            "publish go on."
        )
    errored = []
    failing = []
    for result in sorted(results, key=lambda each: str(each.get("unique_id"))):
        status = str(result.get("status"))
        if status not in ("warn", "fail", "error", "runtime error"):
            continue
        name = str(result.get("unique_id", "")).removeprefix("test.")
        first = (str(result.get("message") or "").strip().splitlines() or [""])[0][:FAILED_VALUE_WIDTH]
        lines.append(f"-- build_marts: {ELEMENTARY_CHECKS}: {status}: {name}" + (f": {first}" if status != "warn" else ""))
        if status in ("error", "runtime error"):
            errored.append(name)
        if status == "fail":
            failing.append(name)
    if failing:
        shown = ", ".join(failing[:10]) + (f" and {len(failing) - 10} more" if len(failing) > 10 else "")
        lines.append(
            f"::error title=Elementary's checks past their error threshold::{len(failing)} check(s) failed: {shown}. "
            "An anomaly past 6 deviations and 50% from its usual value, or a column removed or retyped. "
            "Production and UA build and publish on, and the page counts it; dev and CI fail the build at its end."
        )
    if errored or returncode != 0:
        shown = ", ".join(errored[:10]) + (f" and {len(errored) - 10} more" if len(errored) > 10 else "")
        lines.append(
            f"::warning title=Elementary's checks errored::{len(errored)} check(s) errored (exit {returncode})"
            + (f": {shown}" if shown else "")
            + ". A check that errors stops nothing in production and UA: the build, its exit and its publish go on, and "
            "the page counts it. Dev and CI fail the build at its end."
        )
    return lines


def drop_raw_tables(warehouse: Path, tables: list[str], schema: str = "raw") -> list[str]:
    """Drop each of `tables` the warehouse holds in `schema`, a table or a view, and return the ones it held."""
    import duckdb

    dropped = []
    with duckdb.connect(str(warehouse)) as con:
        for table in tables:
            found = con.execute(
                "select table_type from information_schema.tables where table_schema = ? and table_name = ?", [schema, table]
            ).fetchone()
            if found is None:
                continue
            kind = "view" if found[0] == "VIEW" else "table"
            con.execute(f'drop {kind} "{schema}"."{table}"')
            dropped.append(table)
    return dropped


def _read_manifest() -> dict:
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build_started_at(now: datetime | None = None) -> str:
    """OURHIKE_BUILD_STARTED_AT: when this build started, UTC to the second, as DuckDB casts a TIMESTAMP."""
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S")


def write_build_record(warehouse: Path, record: dict) -> None:
    """Write BUILD_RECORD, one row of `record` as JSON, into the warehouse, replacing any earlier one (the module
    docstring, "THE HOURLY LANE'S CHECKS RUN APART")."""
    import duckdb

    schema = BUILD_RECORD.split(".", 1)[0]
    with duckdb.connect(str(warehouse)) as con:
        con.execute(f'create schema if not exists "{schema}"')
        con.execute(f"create or replace table {BUILD_RECORD} (format integer, record varchar)")
        con.execute(f"insert into {BUILD_RECORD} values (?, ?)", [BUILD_RECORD_FORMAT, json.dumps(record, sort_keys=True)])


def read_build_record(warehouse: Path) -> dict:
    """The record the build of this warehouse wrote (write_build_record()). Raises ValueError, saying why, for a
    warehouse that is not there or holds no record a checks run can read."""
    if not warehouse.exists():
        raise ValueError(f"--checks-only reads a build's warehouse, and there is none at {warehouse}")
    import duckdb

    with duckdb.connect(str(warehouse), read_only=True) as con:
        try:
            rows = con.execute(f"select format, record from {BUILD_RECORD}").fetchall()
        except duckdb.Error as missing:
            raise ValueError(
                f"{warehouse} holds no build record ({BUILD_RECORD}), so which build it is, and what it saved, is not "
                f"known; a build of a lane whose checks run apart writes one last ({missing})"
            ) from missing
    if len(rows) != 1 or rows[0][0] != BUILD_RECORD_FORMAT:
        raise ValueError(f"{warehouse}'s {BUILD_RECORD} is not one row of format {BUILD_RECORD_FORMAT}: {rows!r}")
    return json.loads(rows[0][1])


def _macro_sql(manifest: dict) -> dict[str, str | None]:
    return {uid: macro.get("macro_sql") for uid, macro in (manifest.get("macros") or {}).items()}


def checks_base_problems(base: Path, head_manifest: dict, project: Path = DBT_DIR) -> list[str]:
    """Why a pass given the base project directory `base` runs every check rather than those state:modified+ reaches
    from it (the module docstring, "A PULL REQUEST RUNS THE CHECKS ITS CHANGE REACHES"): each a sentence, and none when
    `base` answers. `head_manifest` is this build's, `project` this project's directory."""
    manifest_path = base / "target" / "manifest.json"
    try:
        base_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as unread:
        return [f"the base's manifest, {manifest_path}, could not be read ({unread})"]
    problems = []
    for name in CHECKS_BASE_FILES:
        mine, theirs = project / name, base / name
        if (mine.read_bytes() if mine.exists() else None) != (theirs.read_bytes() if theirs.exists() else None):
            problems.append(f"{name} differs from the base's, and dbt's state comparison reads no var and no package")
    head, before = _macro_sql(head_manifest), _macro_sql(base_manifest)
    if not head:
        problems.append("this build's manifest holds no macro, so the base's cannot be compared with it")
    elif changed := sorted(uid for uid in head.keys() | before.keys() if head.get(uid) != before.get(uid)):
        shown = ", ".join(changed[:3]) + (f" and {len(changed) - 3} more" if len(changed) > 3 else "")
        problems.append(
            f"{len(changed)} macro(s) differ from the base's ({shown}), and dbt 2.0.6's state comparison reads no macro"
        )
    return problems


def checks_base_answer(lane: str | None, base: Path | None, head_manifest: dict) -> Path | None:
    """The base the checks pass of a build in `lane` compares with, or None for every check, said in the log either way
    for a build with no lane (the module docstring, "A PULL REQUEST RUNS THE CHECKS ITS CHANGE REACHES"). A lane runs
    every check it has, and plan() refuses it a base."""
    if lane is not None:
        return None
    if base is None:
        print(
            f"-- build_marts: {ELEMENTARY_CHECKS}: every check, since no --checks-base names a base to compare with", flush=True
        )
        return None
    if problems := checks_base_problems(base, head_manifest):
        for problem in problems:
            print(f"-- build_marts: {ELEMENTARY_CHECKS}: every check, not only those this change reaches: {problem}", flush=True)
        return None
    print(
        f"-- build_marts: {ELEMENTARY_CHECKS}: only the checks on what changed since the base, {base}, and below it "
        "(state:modified+)",
        flush=True,
    )
    return base


def build_record_written(warehouse: Path, record: dict) -> None:
    """write_build_record(), said in the log, and never a stop: the build stands whatever its checks will find."""
    try:
        if not warehouse.exists():
            raise FileNotFoundError(f"{warehouse} is not there")
        write_build_record(warehouse, record)
    except Exception as failed:  # whatever DuckDB raises: the build and its publish stand
        print(
            f"::warning title=No build record::{BUILD_RECORD} was not written ({failed}), so the checks after this "
            "build will find no record and check nothing. The build, its exit and its publish are unchanged.",
            flush=True,
        )
        return
    print(
        f"-- build_marts: {BUILD_RECORD} written for the checks after this build: exit {record['exit']}, Elementary's "
        f"history {'saved' if record['elementary_saved'] else 'not saved'}, held steps "
        f"{', '.join(record['without']) or 'none'}",
        flush=True,
    )


def keep_writers_results(results_path: Path | None = None) -> None:
    """Copy the writers' run results aside, where no later dbt command writes (the module docstring, "THE DATA-QUALITY
    FILE IS WRITTEN LAST")."""
    path = results_path or RUN_RESULTS_PATH
    kept = path.with_name(WRITERS_RESULTS_NAME)
    kept.unlink(missing_ok=True)
    if path.exists():
        shutil.copyfile(path, kept)


def data_quality_written(
    completed: subprocess.CompletedProcess,
    manifest: dict,
    processed_dir: Path,
    results_path: Path | None = None,
    *,
    alone: bool = False,
) -> None:
    """After the data-quality pass, run_results.json as publish.py reads it: the writers' run's results, with the
    pass's own added when it passed. A failed pass's files are removed, so publish.py keeps the bucket's last copy, and
    an ::error says so; the build goes on (the module docstring, "THE DATA-QUALITY FILE IS WRITTEN LAST"). With no
    writers' results kept, no run_results.json is left, so publish.py refuses rather than reads every file as kept.
    `alone`, the checks run's pass, which has no writers' run before it: a pass that passed leaves its own results,
    which `publish.py --sidecar` reads, and one that failed leaves none."""
    path = results_path or RUN_RESULTS_PATH
    kept = _run_results_document(path.with_name(WRITERS_RESULTS_NAME))
    own = _run_results_document(path) if completed.returncode == 0 else None
    if completed.returncode != 0:
        writers = [
            uid for uid in (manifest.get("nodes") or {}) if _is_writer(uid) and _name(uid) in DATA_QUALITY_WRITERS.values()
        ]
        files = writer_files(manifest, writers, processed_dir)
        for file in files.values():
            file.unlink(missing_ok=True)
        where = (
            "This checks run goes red once Elementary's history is saved."
            if alone
            else "Every phone file still publishes, and the build's exit is unchanged."
        )
        print(
            f"::error title=Data-quality file not written::{DATA_QUALITY_LABEL} failed (exit {completed.returncode}), so "
            f"{', '.join(sorted(file.name for file in files.values())) or 'its file'} is not published and the bucket's "
            f"last copy stands. {where}",
            flush=True,
        )
    if alone:
        if own is None:
            path.unlink(missing_ok=True)
        return
    if kept is None:
        path.unlink(missing_ok=True)
        return
    if own is not None:
        latest = {result.get("unique_id"): result for result in kept["results"]}
        latest.update({result.get("unique_id"): result for result in own["results"]})
        kept = {**kept, "results": list(latest.values())}
    path.write_text(json.dumps(kept), encoding="utf-8")


def _report_writers(results: list[dict], manifest: dict, failed: dict[str, str], processed_dir: Path, since: float) -> str:
    """Remove each failed writer's file and say which files the others wrote: the lines publish-conditions.yml's log
    keeps, and the summary for the build's last line.

    A failed writer's file is removed whatever its age, so nothing it half-wrote, and nothing a test of it refused,
    can be published; its key then keeps the bucket's last copy (publish.py's `kept`)."""
    for writer, path in sorted(writer_files(manifest, failed, processed_dir).items()):
        removed = path.exists()
        path.unlink(missing_ok=True)
        print(
            f"::error title={writer.rsplit('.', 1)[-1]} failed::{failed[writer]}, so {path.name} "
            f"{'is removed' if removed else 'was not written'} and its key keeps the bucket's last copy. Every other "
            "writer's file still publishes, and the run goes red afterwards.",
            flush=True,
        )
    succeeded = [
        result["unique_id"]
        for result in results
        if _is_writer(result.get("unique_id", "")) and result.get("status") == "success" and result["unique_id"] not in failed
    ]
    wrote = sorted(
        path.name
        for path in writer_files(manifest, succeeded, processed_dir).values()
        if path.exists() and path.stat().st_mtime >= since - WRITER_CLOCK_SLACK_S
    )
    print(f"-- build_marts: wrote {len(wrote)} file(s): {', '.join(wrote) or 'none'}", flush=True)
    return f"{len(failed)} writer(s) failed: {', '.join(sorted(name.rsplit('.', 1)[-1] for name in failed))}"


def derived_source_problems(manifest: dict, steps: list[Step]) -> list[str]:
    """What stops the build: a derived table no step writes, or a step writing a table no source declares."""
    declared = {
        source["name"] for source in (manifest.get("sources") or {}).values() if source.get("source_name") == DERIVED_SOURCE
    }
    written = [step.table for step in steps]
    problems = [
        f"source {DERIVED_SOURCE}.{table} is declared and no entry of build_marts.STEPS writes it, so nothing "
        "downstream of it would be built"
        for table in sorted(declared - set(written))
    ]
    problems += [
        f"{step.name} writes {DERIVED_SOURCE}.{step.table}, which no source declares, so dbt would never read it"
        for step in steps
        if step.table not in declared
    ]
    problems += [
        f"{DERIVED_SOURCE}.{table} is written by more than one step"
        for table in sorted({t for t in written if written.count(t) > 1})
    ]
    return problems


def _resolved(value: Path | str | None, variable: str, default: Path) -> Path:
    """An argument, else the variable dbt's own files read, else the default; relative to the directory dbt reads it from."""
    if value is not None:
        return Path(value).resolve()
    if os.environ.get(variable):
        return (DBT_DIR / os.environ[variable]).resolve()
    return default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--fixtures", action="store_true", help="point every step at make_dbt_fixtures.py's inputs")
    parser.add_argument("--dbt", default="dbt", help="the dbt executable (default: dbt, from PATH)")
    parser.add_argument("--python", default=sys.executable, help="the interpreter the Python steps run on")
    parser.add_argument("--warehouse", type=Path, help="default: OURHIKE_WAREHOUSE, else data/warehouse.duckdb")
    parser.add_argument("--processed-dir", type=Path, help="default: OURHIKE_PROCESSED_DIR, else data/processed/dbt")
    parser.add_argument("--raw-dir", type=Path, default=PIPELINE_DIR / "data" / "raw", help="the fixtures' directory")
    parser.add_argument("--threads", type=int, help="passed to every dbt seed and build")
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        help="default: pipeline/dbt, whose profiles.yml CI uses; another one can cap DuckDB's memory on a shared machine",
    )
    parser.add_argument("--lane", choices=LANES, help="build only that lane's nodes (default: every node, as CI's fixtures need)")
    parser.add_argument("--state", type=Path, help="the hourly lane only: defer to the build whose target/ this is")
    parser.add_argument(
        "--without-step",
        action="append",
        default=[],
        metavar="NAME",
        help="leave this STEPS entry out, and everything its derived table unblocks, writers included (repeatable)",
    )
    parser.add_argument(
        "--history-url",
        default=os.environ.get("OURHIKE_HISTORY_URL"),
        help="the row-history store, a directory or s3:// URL (default: OURHIKE_HISTORY_URL; none: --fixtures only)",
    )
    parser.add_argument(
        "--history-cold-start", action="store_true", help="let an empty history store start its history in this build"
    )
    parser.add_argument(
        "--history-python",
        default=sys.executable,
        help="the interpreter row_history.py runs on: DuckDB, and s3fs for an s3:// store (default: this one)",
    )
    parser.add_argument(
        "--history-on-failure",
        choices=HISTORY_ON_FAILURE,
        default="fail",
        help="degrade: a failed restore builds and publishes with null row dates and exits DEGRADED_EXIT (conditions legs)",
    )
    parser.add_argument(
        "--no-history-save",
        action="store_true",
        help="restore the row history and build with it, but save nothing back: some of this build's inputs are missing",
    )
    parser.add_argument(
        "--checks-only",
        action="store_true",
        help="the hourly lane's checks run: Elementary's checks and the data-quality file over the warehouse its build left",
    )
    parser.add_argument(
        "--checks-base",
        type=Path,
        help="no lane: a base commit's dbt project, parsed with Elementary's switches on; only the checks its change reaches run",
    )
    parser.add_argument(
        "--state-base",
        type=Path,
        help="no lane, --fixtures: the directory holding the manifest.json of main's build, whose warehouse is --warehouse; "
        "only what changed since, and what it reaches, is built again",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the commands and run none")
    args = parser.parse_args(argv)

    paths = Paths(
        warehouse=_resolved(args.warehouse, "OURHIKE_WAREHOUSE", PIPELINE_DIR / "data" / "warehouse.duckdb"),
        processed_dir=_resolved(args.processed_dir, "OURHIKE_PROCESSED_DIR", PIPELINE_DIR / "data" / "processed" / "dbt"),
        raw_dir=args.raw_dir.resolve(),
    )
    checks_only = args.checks_only
    record: dict = {}
    try:
        # The environment switch, read as dbt_project.yml reads it (data_environment()).
        environment = data_environment(os.environ)
        history, notice = resolve_history(
            args.history_url,
            fixtures=args.fixtures,
            cold_start=args.history_cold_start,
            python=args.history_python,
            started=started_history_stores(),
            elementary_started=started_elementary_stores(),
        )
        history = replace(history, on_failure=args.history_on_failure)
        options = {
            "dbt": args.dbt,
            "python": args.python,
            "paths": paths,
            "fixtures": args.fixtures,
            "threads": args.threads,
            "profiles_dir": str(args.profiles_dir.resolve()) if args.profiles_dir else ".",
            "lane": args.lane,
            "state": args.state.resolve() if args.state else None,
            "without": tuple(args.without_step),
            # Read before anything runs: the extract and the served copy have written the warehouse already.
            "withdrawn": withdrawn_tables(paths.warehouse),
            "checks_base": args.checks_base.resolve() if args.checks_base else None,
            "state_base": args.state_base.resolve() if args.state_base else None,
        }
        if args.state_base and args.history_url:
            # The module docstring, "A PULL REQUEST BUILDS ONLY WHAT CHANGED SINCE MAIN'S LAST BUILD".
            raise ValueError(
                "--state-base keeps the snapshots main's build left in the warehouse and saves no row history, so it "
                "takes no history store (--history-url, OURHIKE_HISTORY_URL)"
            )
        planned = {**options, "history": history, "save_history": not args.no_history_save}
        if checks_only:
            # The module docstring, "THE HOURLY LANE'S CHECKS RUN APART": what the run needs of the build is its record.
            if args.without_step or args.state or args.checks_base or args.state_base:
                raise ValueError(
                    "--checks-only takes the build's held steps from its record, and no --state, --checks-base or --state-base"
                )
            record = read_build_record(paths.warehouse)
            if record.get("elementary_saved") and record.get("history_url") != history.url:
                raise ValueError(
                    f"the build saved Elementary's history to {record.get('history_url')}, and this run would restore and "
                    f"save it at {history.url}: pass that store as --history-url"
                )
            planned = {
                "dbt": args.dbt,
                "paths": paths,
                "lane": args.lane,
                "record": record,
                "threads": args.threads,
                "profiles_dir": options["profiles_dir"],
                "history": history,
                "save_history": not args.no_history_save,
                "withdrawn": options["withdrawn"],
            }
            runs = plan_checks(STEPS, **planned)
        else:
            runs = plan(STEPS, **planned)
    except ValueError as refused:
        parser.error(str(refused))
    files = {"OURHIKE_WAREHOUSE": str(paths.warehouse), "OURHIKE_PROCESSED_DIR": str(paths.processed_dir)}
    # TZ=UTC and OURHIKE_BUILT_BY: the module docstring, "THE ROW HISTORY IS RESTORED FIRST AND SAVED LAST";
    # OURHIKE_BUILD_STARTED_AT: "THE DATA-QUALITY FILE IS WRITTEN LAST", the build's own in its checks run.
    env = {
        **os.environ,
        **files,
        "TZ": "UTC",
        "OURHIKE_BUILT_BY": built_by(os.environ),
        "OURHIKE_BUILD_STARTED_AT": record.get("started_at") or build_started_at(),
        **ELEMENTARY_SWITCH,
    }
    for name, _ in CHECKS_SWITCH:
        env.pop(name, None)  # the checks' switch is each Run's own to give (Run.env), never inherited by every command
    # Fixture mode's own A.T. profile null share, and no other build's (FIXTURE_PROFILE_MAX_NULL_SHARE says why).
    env.pop(PROFILE_NULL_SHARE_VARIABLE, None)
    if args.fixtures:
        env[PROFILE_NULL_SHARE_VARIABLE] = FIXTURE_PROFILE_MAX_NULL_SHARE
        print(f"-- build_marts: {PROFILE_NULL_SHARE_VARIABLE}={FIXTURE_PROFILE_MAX_NULL_SHARE} (the fixture profile's gaps)")
    if record.get("row_history") == "off":
        env["OURHIKE_ROW_HISTORY"] = "off"  # as the build's dbt commands ran, so the project renders as it did there
    print("-- build_marts: " + " ".join(f"{name}={value}" for name, value in files.items()), flush=True)
    print(f"-- build_marts: OURHIKE_BUILT_BY={env['OURHIKE_BUILT_BY']}", flush=True)
    # The module docstring, "EVERY TEST HAS TWO THRESHOLDS, AND THE ENVIRONMENT DECIDES WHO STOPS".
    goes_on = builds_on(environment)
    print(
        f"-- build_marts: {data_env.ENVIRONMENT_VAR}={environment}: "
        + (
            "a failing test warns, a test past its error threshold is reported as an error, and the build goes on "
            "past any failure, holding what it reaches, then goes red after the publish"
            if goes_on
            else "a failing test is an error, the build stops on it, and an Elementary check past its error threshold "
            "fails the build at its end"
        ),
        flush=True,
    )
    if checks_only:
        print(
            f"-- build_marts: the checks of the {record.get('lane')} build that started {record.get('started_at')} "
            f"({record.get('built_by')}), which exited {record.get('exit')}: "
            + (
                "Elementary's history restored from its store and saved back"
                if record.get("elementary_saved")
                else "that build saved no Elementary history, so this run keeps the history it restored and saves none"
            ),
            flush=True,
        )
    if notice and not checks_only:
        # A workflow command is one only at the start of its line, so a warning is printed as it is.
        print(notice if notice.startswith("::") else f"-- build_marts: {notice}", flush=True)
    if options["state_base"] is not None:
        print(
            f"-- build_marts: a state build from main's build, whose manifest is in {options['state_base']} and whose "
            f"warehouse is {paths.warehouse}: only what dbt lists as changed, what reads the clock and what a step "
            "wrote from a changed input are built again, with what each reaches; main's snapshots are kept, and "
            "Elementary's history starts cold",
            flush=True,
        )
    if args.no_history_save:
        print(
            "::warning title=Row history not saved::--no-history-save: this build restores the row history and saves "
            "nothing back, so a row missing from its inputs is never recorded as removed. A row that changed is dated "
            "by the next build that saves.",
            flush=True,
        )
    if args.dry_run:
        for run in runs:
            print(f"{run.label}: (cd {run.cwd} && {' '.join([*(f'{name}={value}' for name, value in run.env), *run.argv])})")
        return 0

    # COPY creates no directory (phone_file.sql), and the writers write here.
    paths.processed_dir.mkdir(parents=True, exist_ok=True)
    degraded = False
    # What this build held back and still finished, for PARTIAL_EXIT (the module docstring, "ONE SOURCE OR ONE WRITER
    # NEVER STOPS THE REST").
    partial: list[str] = []
    # The row history's restore and save, by exit, for the build record's elementary_saved; and the checks run's file.
    history_exits: dict[str, int] = {}
    quality_failed = False
    # Whether the checks pass selects only what a change reaches (the module docstring, "A PULL REQUEST RUNS THE
    # CHECKS ITS CHANGE REACHES"), which makes none an answer rather than a fault.
    modified_only = False
    for table in options["withdrawn"] if not checks_only else ():
        # The checks run leaves them out of its checks as the build left them out of its builds, and says nothing: the
        # build's own run already went red for them.
        print(
            f"::error title={table} withdrawn::the extract found {table} unavailable (its newest {RUN_LOG_TABLE} row), "
            f"so it is not in this warehouse, and source:{WITHDRAWABLE[table]}.{table} and everything below it are "
            "left out of every dbt build here. No mart reads it, so every other source still builds and publishes, and "
            "the run goes red afterwards.",
            flush=True,
        )
    if options["withdrawn"] and not checks_only:
        partial.append(f"{', '.join(options['withdrawn'])} withdrawn by the extract")
    stage_a_rerun = False
    # The tests reported as errors past their error_if, the checks that failed, and the run summary's lines.
    relabelled: dict[str, str] = {}
    checks_failing: list[str] = []
    summary: list[str] = []
    step_names = {step.name for step in STEPS}
    position = 0
    while position < len(runs):
        run = runs[position]
        position += 1
        if run.stage == CHECKS:
            # Less the checks on each raw table the warehouse does not hold now, which counts the tables of a source
            # dropped after a failed model or test of its own (one_sources_failures()), and the same pass otherwise. A
            # warehouse that cannot be read here leaves nothing out, rather than stopping a build the pass never stops.
            try:
                absent = absent_sources(_read_manifest(), paths.warehouse, args.lane)
            except Exception as unread:  # whatever DuckDB raises: the pass goes on without it
                print(f"-- build_marts: {ELEMENTARY_CHECKS}: the warehouse's raw tables were not read ({unread})", flush=True)
                absent = ()
            if absent:
                print(
                    f"-- build_marts: {ELEMENTARY_CHECKS} leave out {len(absent)} raw table(s) this warehouse does not "
                    f"hold: {', '.join(selector.removeprefix('source:') for selector in absent)}",
                    flush=True,
                )
            if checks_only:
                (run,) = [each for each in plan_checks(STEPS, **planned, absent=absent) if each.stage == CHECKS]
            else:
                base = checks_base_answer(args.lane, planned.get("checks_base"), _read_manifest())
                modified_only = base is not None
                again = plan(STEPS, **{**planned, "absent": absent, "checks_base": base})
                (run,) = [each for each in again if each.stage == CHECKS]
        print(f"-- build_marts {position}/{len(runs)}: {run.label}", flush=True)
        # A dbt run's results are the run_results.json it leaves, and an earlier run's file is removed first so
        # nothing else can be mistaken for them. Never told apart by mtime: Linux stamps a file from a coarse clock
        # that can lag time.time() by a few milliseconds, so results written within one tick of `started` read as
        # older than the run that wrote them (CI's pytest job on 461954c4, Pipeline tests run 37357769435, which
        # lost a stage A hold that way). A Python step leaves none, so the mtime still turns the last dbt run's away.
        if run.cwd == DBT_DIR:
            RUN_RESULTS_PATH.unlink(missing_ok=True)
        if run.stage == FRESHNESS:
            SOURCES_RESULTS_PATH.unlink(missing_ok=True)
        started = time.time()
        results_since = float("-inf") if run.cwd == DBT_DIR else started
        if run.stage == STATE_LIST:
            # Its answer is its output, one JSON object a line (listed_ids()).
            completed = subprocess.run(
                run.argv, cwd=run.cwd, env={**env, **dict(run.env)}, check=False, capture_output=True, text=True
            )
        else:
            completed = subprocess.run(run.argv, cwd=run.cwd, env={**env, **dict(run.env)}, check=False)
        if run.stage == STATE_LIST:
            # The module docstring, "A PULL REQUEST BUILDS ONLY WHAT CHANGED SINCE MAIN'S LAST BUILD": what dbt lists,
            # checked against main's macros, and the rest of the build planned again from it.
            manifest = _read_manifest()
            problems = state_base_problems(manifest, options["state_base"]) if completed.returncode == 0 else []
            if completed.returncode != 0 or problems:
                print(f"-- build_marts: {run.label} failed (exit {completed.returncode}): {' '.join(run.argv)}", flush=True)
                for line in [*(completed.stdout or "").splitlines()[-20:], *(completed.stderr or "").splitlines()[-20:]]:
                    print(line, flush=True)
                for problem in problems:
                    print(f"-- build_marts: no state build from {options['state_base']}: {problem}", flush=True)
                return 1 if problems or completed.returncode in PUBLISHABLE_EXITS else completed.returncode
            planned = {**planned, "modified": listed_ids(completed.stdout)}
            again = plan(STEPS, **planned, manifest=manifest)
            again = again[[each.label for each in again].index(STATE_LIST_LABEL) + 1 :]
            for line in state_report(
                manifest, planned["modified"], again, [step for step in STEPS if step.name not in planned["without"]]
            ):
                print(line, flush=True)
            runs = runs[:position] + again
            continue
        if run.label in (RESTORE_LABEL, SAVE_LABEL):
            history_exits[run.label] = completed.returncode
        if run.stage == CHECKS:
            # Never retried, never a stop, never the build's exit (the module docstring, "ELEMENTARY'S CHECKS RUN
            # AFTER THE WRITERS"): reported, and the build goes on to save its history.
            results = read_run_results(results_since)
            for line in checks_report(results, completed.returncode, none_is_an_answer=modified_only):
                print(line, flush=True)
            checks_failing += failed_checks(results)
            continue
        if run.stage == FRESHNESS:
            # Recorded, never raised (the module docstring, "EACH SOURCE'S FRESHNESS IS MEASURED FOR THE
            # DATA-QUALITY FILE"): the data-quality file counts it, and the build goes on.
            for line in freshness_report(completed.returncode):
                print(line, flush=True)
            continue
        is_build = run.argv[1:2] == ("build",) and run.cwd == DBT_DIR
        if completed.returncode != 0 and is_build:
            completed = retry_failed_build(run, {**env, **dict(run.env)}, completed)
        # The module docstring, "THE DATA-QUALITY FILE IS WRITTEN LAST".
        if run.stage == WRITERS:
            keep_writers_results()
        if run.stage == DATA_QUALITY:
            data_quality_written(completed, _read_manifest(), paths.processed_dir, alone=checks_only)
            quality_failed = completed.returncode != 0
            continue
        if run.label in (ELEMENTARY_RESTORE_LABEL, ELEMENTARY_SAVE_LABEL):
            # The checks run's restore and save of Elementary's history alone: under degrade, a failure of either is
            # row_history.py's ELEMENTARY_DEGRADED_EXIT, and the file is still written and published, and the run goes
            # red after; anything else stops the run, before or after its checks.
            if completed.returncode == ELEMENTARY_DEGRADED_EXIT and args.history_on_failure == "degrade":
                partial.append(f"Elementary's history not {'restored' if run.label == ELEMENTARY_RESTORE_LABEL else 'saved'}")
                continue
            if completed.returncode != 0:
                print(f"-- build_marts: {run.label} failed (exit {completed.returncode}): {' '.join(run.argv)}", flush=True)
                return 1 if completed.returncode in PUBLISHABLE_EXITS else completed.returncode
            continue
        if completed.returncode != 0 and run.stage in (STAGE_A, WRITERS) and completed.returncode not in PUBLISHABLE_EXITS:
            print(f"-- build_marts: {run.label} failed (exit {completed.returncode}): {' '.join(run.argv)}", flush=True)
            for line in failed_test_rows(paths.warehouse, results_since):
                print(line, flush=True)
            results, manifest = read_run_results(results_since), _read_manifest()
            # Not in a state build, whose stage A selected only what changed: the module docstring, "A PULL REQUEST
            # BUILDS ONLY WHAT CHANGED SINCE MAIN'S LAST BUILD".
            if results is not None and run.stage == STAGE_A and not stage_a_rerun and options["state_base"] is None:
                if held := one_sources_failures(results, manifest, notice_readers()):
                    for key, tables in sorted(held.items()):
                        dropped = drop_raw_tables(paths.warehouse, tables)
                        print(
                            f"::error title={key} held for a failure of its own::a model or data test of {key} alone "
                            f"failed in {run.label}, "
                            f"so its raw tables ({', '.join(dropped) or 'none held'}) are dropped from this build's "
                            "warehouse and int_closures__gate holds it as not in this warehouse: it carries its last good "
                            "rows, every other source still publishes, and the run goes red afterwards.",
                            flush=True,
                        )
                    partial.append(f"{', '.join(sorted(held))} held for a failure of its own")
                    stage_a_rerun = True
                    position -= 1  # stage A once more, with those tables gone
                    continue
            if results is not None and run.stage == WRITERS:
                writers, others = failed_writers(results, manifest)
                if writers and not others:
                    partial.append(_report_writers(results, manifest, writers, paths.processed_dir, started))
                    continue
            if not goes_on:
                return completed.returncode
        if is_build and (completed.returncode == 0 or goes_on):
            results = read_run_results(results_since)
            # A warning past its own error_if is an error, reported here and red after the publish.
            history_off = env.get("OURHIKE_ROW_HISTORY") == "off"
            if results is not None and (errors := relabelled_errors(results, _read_manifest(), history_off=history_off)):
                errors = {test: why for test, why in errors.items() if test not in relabelled}
                relabelled.update(errors)
                for line in failed_test_rows(paths.warehouse, results_since, statuses=("warn",), only=set(errors)):
                    print(line, flush=True)
                for test, why in sorted(errors.items()):
                    print(
                        f"::error title=A test past its error threshold::{_name(test)} warned with {why}, so it is "
                        f"an error. {data_env.ENVIRONMENT_VAR}={environment} builds on past it, "
                        "and the run goes red after the publish.",
                        flush=True,
                    )
                    summary.append(f"- error past its threshold: `{_name(test)}`, {why}")
                if errors:
                    partial.append(f"{len(errors)} test(s) past their error threshold")
            if results is not None and (holds := source_holds(results, _read_manifest())):
                for line in failed_test_rows(paths.warehouse, results_since, statuses=("warn",), only=holds):
                    print(line, flush=True)
                for test in sorted(holds):
                    print(
                        f"::error title=A source held for its rows::{test} warned: int_closures__gate holds the source "
                        "of each row it names, which carries its last good rows while every other source publishes. "
                        "The run goes red afterwards.",
                        flush=True,
                    )
                partial.append(f"{len(holds)} test(s) holding a source")
        if completed.returncode != 0 and goes_on and (is_build or run.label in step_names):
            # The module docstring, "EVERY TEST HAS TWO THRESHOLDS, AND THE ENVIRONMENT DECIDES WHO STOPS": hold what
            # failed and everything it reaches, a failed writer's file removed, and build the rest.
            manifest = _read_manifest()
            if is_build:
                results = read_run_results(results_since)
                if results is None:
                    print(f"-- build_marts: {run.label} failed (exit {completed.returncode}) and left no results", flush=True)
                    return 1 if completed.returncode in PUBLISHABLE_EXITS else completed.returncode
                if run.stage == WRITERS and (writers := failed_writers(results, manifest)[0]):
                    partial.append(_report_writers(results, manifest, writers, paths.processed_dir, started))
                failed, selectors, reached = failure_holds(results, manifest)
                held_steps = [name for name in steps_reading(manifest, STEPS, reached) if name not in planned["without"]]
            else:
                failed, selectors, held_steps = [f"{run.label} (exit {completed.returncode})"], [], [run.label]
            planned = {
                **planned,
                "without": tuple(sorted({*planned["without"], *held_steps})),
                "held_nodes": tuple(sorted({*planned.get("held_nodes", ()), *selectors})),
            }
            what = ", ".join(failed) or f"exit {completed.returncode}"
            print(
                f"::error title=Part of the build held back for a failure::{run.label} failed ({what}). "
                f"{data_env.ENVIRONMENT_VAR}={environment} builds on: what it reaches is held, so each writer below it "
                "keeps its last published file"
                + (f", the step(s) {', '.join(held_steps)} with it" if held_steps else "")
                + ", everything else builds and publishes, and the run goes red afterwards.",
                flush=True,
            )
            summary.append(f"- held back for a failure in {run.label}: {what}")
            partial.append(f"{run.label} failed ({what}), and what it reaches is held")
            done = {each.label for each in runs[:position]}
            runs = runs[:position] + [each for each in plan(STEPS, **planned, manifest=manifest) if each.label not in done]
            continue
        if (
            completed.returncode == ELEMENTARY_DEGRADED_EXIT
            and run.label in (RESTORE_LABEL, SAVE_LABEL)
            and args.history_on_failure == "degrade"
        ):
            # The module docstring, "--history-on-failure degrade": the row dates stand, and only Elementary's history
            # is held back; row_history.py's ::error above says why.
            done = "restored" if run.label == RESTORE_LABEL else "saved"
            partial.append(f"Elementary's history not {done}")
            continue
        if completed.returncode != 0 and run.label == RESTORE_LABEL and args.history_on_failure == "degrade":
            # The module docstring, "--history-on-failure degrade": build and publish with null dates, save nothing.
            print(
                f"::error title=Row history not restored::{run.label} failed (exit {completed.returncode}); this leg "
                "builds and publishes with _first_seen_at and _changed_at null, saves no history, and goes red "
                "afterwards. Fix the store before the next run.",
                flush=True,
            )
            degraded = True
            env["OURHIKE_ROW_HISTORY"] = "off"
            planned = {**options, "snapshots": False}
            runs = runs[:position] + plan(STEPS, **planned)
            continue
        if completed.returncode != 0:
            print(f"-- build_marts: {run.label} failed (exit {completed.returncode}): {' '.join(run.argv)}", flush=True)
            for line in failed_test_rows(paths.warehouse, results_since):
                print(line, flush=True)
            # PUBLISHABLE_EXITS mean built-and-publishable to publish-conditions.yml, so a command's own 4 is a 1.
            return 1 if completed.returncode in PUBLISHABLE_EXITS else completed.returncode
        if run.label == SEED:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            checked = derived_source_problems(manifest, STEPS) + lane_problems(manifest, STEPS, args.lane)
            if problems := checked + alone_problems(manifest):
                for problem in problems:
                    print(f"-- build_marts: {problem}", flush=True)
                return 1
            # Plan again with the manifest, which leaves out each split pass that selects nothing (the module
            # docstring, "A MODEL TAGGED `builds_alone`"), and run what follows the seeds.
            again = plan(STEPS, **planned, manifest=manifest)
            again = again[[each.label for each in again].index(SEED) + 1 :]
            alone = sorted(_name(uid) for uid, node in (manifest.get("nodes") or {}).items() if BUILDS_ALONE in _tags(node))
            print(
                f"-- build_marts: {len(alone)} model(s) build alone ({', '.join(alone) or 'none'}); "
                f"{len(runs) - position - len(again)} split pass(es) that select nothing left out",
                flush=True,
            )
            runs = runs[:position] + again
    write_step_summary(([f"**build_marts.py ({data_env.ENVIRONMENT_VAR}={environment})**", ""] + summary) if summary else [])
    if checks_failing and not goes_on:
        # Dev and CI stop on an Elementary check past its error threshold, once everything else has run.
        print(
            f"-- build_marts: exit 1: {len(checks_failing)} of Elementary's checks finished past their error threshold "
            f"or could not run, which {data_env.ENVIRONMENT_VAR}={environment} does not build past: "
            + ", ".join(checks_failing[:10])
            + (f" and {len(checks_failing) - 10} more" if len(checks_failing) > 10 else ""),
            flush=True,
        )
        return 1
    if checks_only:
        # The module docstring, "THE HOURLY LANE'S CHECKS RUN APART": the file is this run's one product.
        if partial:
            print(f"-- build_marts: checked with part of it held back ({'; '.join(partial)})", flush=True)
        if quality_failed:
            print("-- build_marts: exit 1: the data-quality file was not written, so there is nothing to publish", flush=True)
            return 1
        if partial:
            print(f"-- build_marts: exit {PARTIAL_EXIT}: publish the data-quality file, then go red", flush=True)
            return PARTIAL_EXIT
        return 0
    if partial:
        print(f"-- build_marts: built with part of it held back ({'; '.join(partial)})", flush=True)
    code = (DEGRADED_PARTIAL_EXIT if partial else DEGRADED_EXIT) if degraded else PARTIAL_EXIT if partial else 0
    if checks_apart(args.lane):
        # Last, so the record says what the build did: the module docstring, "THE HOURLY LANE'S CHECKS RUN APART".
        build_record_written(
            paths.warehouse,
            {
                "lane": args.lane,
                "started_at": env["OURHIKE_BUILD_STARTED_AT"],
                "built_by": env["OURHIKE_BUILT_BY"],
                "without": sorted(planned.get("without") or ()),
                "state": str(options["state"]) if options["state"] else None,
                # What a failure held back, which the checks run then leaves unchecked.
                "held_nodes": sorted(planned.get("held_nodes") or ()),
                "history_url": history.url,
                "row_history": "off" if degraded else "on",
                "elementary_saved": history_exits.get(RESTORE_LABEL) == 0 and history_exits.get(SAVE_LABEL) == 0,
                # The checks run measures the notices job's sources only when the build read their copy.
                "notices_read_at": os.environ.get(NOTICES_READ_AT_ENV) or None,
                "exit": code,
            },
        )
    if degraded:
        print(f"-- build_marts: built without the row history; exit {code}", flush=True)
    elif partial:
        print(f"-- build_marts: exit {PARTIAL_EXIT}: publish what was written, then go red", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
