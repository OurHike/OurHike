"""build_marts: the dbt build in the order the Python steps need, from the seeds to the phone files.

    python build_marts.py --fixtures [--dbt dbt] [--python <interpreter>]
        [--warehouse data/warehouse.duckdb] [--processed-dir data/processed/dbt]
        [--raw-dir data/raw] [--threads N] [--dry-run]
    python build_marts.py --lane monthly ...                 # build-reference.yml
    python build_marts.py --lane hourly [--state <dir>] ...  # the hourly conditions lane

The one home of the build order (pipeline/ELT.md, "Python steps, outside dbt"
and "Running it"). CI's dbt job and scripts/test.sh call it with --fixtures.

WHY MORE THAN ONE `dbt build`. A rule that stays Python runs as a step between
dbt invocations: it reads a named intermediate and writes `derived.<table>`,
which dbt reads back as a source (models/staging/derived/). A single
`dbt build` would reach the first stg_derived__ model before any step had
written its table, and fail. So:

1. `dbt seed`;
2. stage A: everything not downstream of a `derived` source, except the pub_
   writers and the evaluator package (CI runs it on its own, at severity
   error);
3. for each STEPS entry, in order: the step, then
   `dbt build -s source:derived.<its table>+`, less what a later step's table
   also feeds, which waits for that step;
4. the pub_ writers after every other model (`-s path:models/publish`): `dbt
   build` tests each model after building it, so a writer built beside its
   parents would write its file before a failing test upstream could stop it
   (ELT.md, "Publish (reverse ETL)");
5. Elementary's checks (`dbt test -s tag:elementary_check`), which every
   build before leaves out: below, "ELEMENTARY'S CHECKS RUN AFTER THE
   WRITERS".

Contracts stay enforced in every invocation. `dbt deps` is not here: CI and
scripts/test.sh run it first, and a sandbox whose proxy cannot fetch the
packages skips it (scripts/test.sh --no-dbt-deps).

A LANE BUILDS ONLY ITS OWN NODES (--lane; ELT.md, "Every node carries its
cadence"). A node's cadence is the fastest `meta.cadence` among the sources
it reads, so `config.meta.cadence:hourly+` selects every node an hourly
source reaches.
- `monthly` (build-reference.yml) excludes every node an hourly or daily
  source reaches, writers included: its warehouse holds only the monthly raw
  tables, so those nodes would fail on a missing source or, if built, store
  month-old closures (ELT.md's probe, measured on dbt-oss 2.0.5). A source
  with no `meta.cadence` is built here, so an untagged source lands where
  today's build puts it rather than nowhere.
- `hourly` builds the seeds, every node an hourly or daily source reaches,
  the hourly steps and what they unblock, then those nodes' writers. What
  they read from the monthly lane comes through `--defer --state`; without
  --state the build also takes every parent of those nodes (LANE_PARENTS),
  so the warehouse must hold the monthly raw tables they read (the registry,
  today).
- Each STEPS entry runs in its `lane`. After `dbt seed`, lane_problems()
  refuses a step with no `step_<name>` exposure listing its inputs
  (models/intermediate/*/_*__intermediate.yml) unless it `reads_no_model`, a
  monthly step reading a node an hourly or daily source reaches, and a step
  whose table feeds only the other lane's writers.
- --without-step NAME leaves a step out with everything its table unblocks,
  so those writers keep their last files (publish.py's `kept`): for an input
  a run does not have, such as the weather squares the hourly production leg
  lacks (publish-conditions.yml).
With no --lane every step and node builds, as CI's fixture warehouse, which
holds both lanes' tables, needs.

A MODEL TAGGED `builds_alone` BUILDS WITH NO OTHER MODEL BESIDE IT, so it has
DuckDB's whole memory limit to itself. Monthly run 20 (refresh-reference.yml
37296900535) failed at "what derived.poi_photos unblocks" with
int_places__resolved and int_trail_network__cuts building side by side:
"Out of Memory Error: failed to allocate data of size 16.0 MiB (12.5 GiB/12.4
GiB used)" (its log, 2026-10-05). Alone was not enough: monthly run 21
(37323395441) built each of them by itself, the rest of the step waiting on
it, and each ran out the same way, so both queries were rewritten to hold
less (each model's own header says how, and what it was measured on). That
either now fits in the limit is @unvalidated until a monthly run passes that
build; the tag stays, so neither shares the limit while that is unknown.
dbt has no per-model setting that keeps two
table models apart: `concurrent_batches` is a microbatch model's, about its
own batches. So every dbt build here but the writers' and the hourly lane's
is split into up to three, each keeping the build's selection and excludes:
(a) the same command, `--exclude tag:builds_alone+` added, at --threads;
(b) the tagged models, `-s <each -s item>,tag:builds_alone` (`-s
    tag:builds_alone` for a build with no -s), at --threads 1;
(c) what they feed, `-s <each -s item>,tag:builds_alone+` and `--exclude
    tag:builds_alone` added, at --threads.
Nothing in (a) reads a node of (b) or (c), since `+` takes every descendant,
and (b) reads only what (a) built, unless a tagged model reads a model that
(c) builds (an untagged descendant of another tagged one), or a test that (b)
runs reads one: alone_problems() refuses both after `dbt seed`, naming them.
Once `dbt seed` has written the manifest, main() plans again with it: a pass
it shows selecting nothing is left out (selects_anything()), and a build
whose pass (b) selects nothing runs whole, as it did before the split. That
is because dbt 2.0.6 answers an empty selection with exit 0 and two
warnings (dbt1092, dbt1601) only after reading the whole project: stage A's
pass (b), which selects nothing, took 30.9 to 34.2 s three times over against
the fixture warehouse (Measured 2026-10-05, in a 4-core sandbox), and the
fixture build leaves 18 passes out. Over the real project with today's two
tags, the split reaches one build, "what derived.poi_photos unblocks", in the
monthly lane and in a build with no lane (plan() over `dbt parse`'s manifest,
2026-10-05). The hourly lane never splits: publish-conditions.yml gives its
build 10 minutes (6 until decision 103), and a dbt invocation on a runner
spends about 9.4 s before its first node (run 20's step 13, from its start
to its first result: Measured). alone_problems() refuses a tagged model an
hourly or daily source reaches, whose tag that lane would ignore.

THE PUB_ WRITERS BUILD ONE AT A TIME (--threads 1) in every lane but the
hourly one. Monthly run 25 (refresh-reference.yml 37614075245) built every
stage and then failed at "the pub_ writers" with pub_nearby_trails,
pub_trail_graph, pub_trail_graph_geometry and pub_trail_graph_profile
building side by side, each 9.4 to 9.9 s in: "Out of Memory Error: failed to
allocate data of size 256.0 MiB (12.4 GiB/12.4 GiB used)" (its log,
2026-10-07). Each of the four is one row holding a whole network-wide file
as one string (nearby_trails.geojson was published at 228,820,578 bytes,
artifactBudget.ts), which DuckDB holds in memory rather than spilling. That
each fits the limit alone is @unvalidated: settled by the writers step of
the next monthly run. One thread for every writer, rather than a
builds_alone tag on the four: the other 38 writers' own times in run 25 sum
to 48.3 s, against a monthly run of four hours or more, and a heavy
writer added later is covered without anybody tagging it. The hourly lane
keeps --threads: it writes only the files an hourly or daily source reaches,
none of the four, inside publish-conditions.yml's 10 minutes.

A FAILED dbt BUILD IS RETRIED, up to DBT_RETRIES (3) times, in every lane:
`dbt retry --threads 1` after the build, then after each retry that fails,
until one exits 0 (the maintainer, 2026-10-07, on monthly run 26: "I would
expect the run to execute that if there is a failure up to 3 times", pointing
at dbt's `retry` command; then "The hourly lane should get the same retry
logic", and "do up to 3 retries. period"). Run 26's build job failed twice on
nodes that run 25 had built: attempt 1 on int_places__resolved ("Invalid
unicode (byte sequence mismatch) detected in segment statistics update"),
which built in 3 m 18 s on attempt 2; attempt 2 out of DuckDB's 12.4 GiB with
assert_every_elevation_sample_was_read_at_its_own_point,
int_elevation__edge_samples and int_elevation__profile building side by side,
as run 25 had built all three (refresh-reference.yml 37649648453 and
37614075245, their logs, 2026-10-07). Measured on dbt 2.0.6 in a scratch
project the same day: a retry builds only the nodes that failed and the ones
they skipped, keeps the build's `-s` and `--exclude` (an excluded model stayed
unbuilt), accepts `--indirect-selection` (retry_argv() passes the build's),
exits 1 while one still fails and 0 once all pass, and exits 1 when there is
nothing left to retry, so a retry never follows a pass. One thread, because
both of run 26's failures were one node beside others. Each retry leaves
run_results.json holding only its own nodes, so retry_failed_build() writes
back every node the build ran with its last attempt's result: a test that
warned and holds a source in the first attempt still holds it after a retry
passes. A failure that is not chance, a SQL error, costs three more runs of
its failed nodes and what they skipped, at one thread; what that costs a
monthly run is @unvalidated, settled by the step times of the first run that
retries one. The hourly lane gets no deadline either: a build that fails and
retries three times can meet publish-conditions.yml's 10-minute step cap, which
fails the job before "Publish to R2", so that hour publishes nothing new; how
often is @unvalidated, settled by the summary's retry lines over the first
weeks. A build that defers (`--defer --state`) is retried the same way:
retry_argv() passes no `--state`, and after a deferred build failed, a plain
`dbt retry` re-ran its failed model, the two models it skipped and their test
(measured the same day; given `--state` itself, retry read that directory's
run_results.json and found nothing to retry). Whether the retry still defers
is @unvalidated; publish-conditions.yml passes no `--state`.

NOT dbt's `selectors.yml` (ELT.md's shape): dbt documents `--selector` as not
combinable with `-s` or `--exclude`, which every invocation here carries, so a
selector file would need one selector per invocation per lane. A lane is one
more `--exclude` on each, and LANE_EXCLUDES is its one home. That 2.0.6 keeps
dbt's rule is @unvalidated: the one probe (2026-10-02) named an undefined
selector beside `--exclude`, and dbt crashed rather than answering. A probe
with a defined selector beside `--exclude` would settle it.

A NEW STEP IS ONE STEPS ENTRY plus its script; nothing in CI or
scripts/test.sh changes. After `dbt seed`, derived_source_problems() refuses
a `derived` table no step writes, which would leave everything downstream of
it unbuilt without one failing node, and a step writing a table no source
declares.

THE ROW HISTORY IS RESTORED FIRST AND SAVED LAST. The row-history snapshots
(int_<mart>__history, one per mart, decision 57; macros/row_history.sql) are
the only state a build carries from one run to the next, and the warehouse is
rebuilt from raw every
run, so `row_history.py restore` runs before `dbt seed` and `row_history.py
save` after the writers and Elementary's checks, only when every command
before it succeeded (the checks pass excepted, which never stops a build). The
store is --history-url, else OURHIKE_HISTORY_URL. A store with no history
yet is a cold start, and cold starts are allowed only:
- under --fixtures with no store named, into a new temporary directory, so
  CI and scripts/test.sh start history in every run and keep none;
- for a store whose name (its URL's last part, `monthly` for
  s3://<bucket>/history/monthly) row_history_stores.toml does not list as
  started: its first run, said in a warning;
- with --history-cold-start, by hand.
Anything else with no history fails before dbt runs, because a silent cold
start would date every row as first seen in this build. Without --fixtures a
store must be named: there is no default that keeps history. The restore and
the save run on --history-python (default: this interpreter), which needs
DuckDB, and s3fs for an s3:// store: the extract's venv in a workflow.
Every dbt command runs with TZ=UTC, so a TIMESTAMPTZ column is hashed in the
same characters on every machine (macros/row_hash.sql), and with
OURHIKE_BUILT_BY, the git commit and workflow run, which each snapshot
version records as `_built_by` (never hashed), so a reader can tell a change
upstream from a change to this project's rules.
ELEMENTARY'S HISTORY RIDES IN THE SAME TWO COMMANDS (decision 102;
row_history.py, "ELEMENTARY'S HISTORY"): the restore puts its four kept
tables back before "Elementary's own tables" builds, so their incremental
models add this build to them, and the save writes them out with the
snapshots, keeping ELEMENTARY_KEEP_DAYS of the lane's builds (--keep-days).
A store with no Elementary history yet may start it under the same three
rules, against row_history_stores.toml's [elementary_started] rather than
[started]: every store saved before decision 102 holds the snapshots and no
Elementary history, which is its first run, not a loss.

--no-history-save restores the history and builds with it, and saves
nothing back, Elementary's history included, so a build known to lack inputs
never joins its checks' training set either: for a build that knows some of
its inputs are missing, so that a row's absence is never recorded as its
removal. publish-conditions.yml passes it when the notices legs' served copy was not the newest
(extract/_warehouse.py, "THE SERVED COPY"), because the closures and
warnings marts then lack, or hold older, notices; saved, the history would
close those rows and reopen them an hour later with a new `_changed_at`.
What it costs is the date of a row that did change: it is dated by the next
build that saves (Reasoned).

--history-on-failure degrade IS THE CONDITIONS LEGS' (the maintainer, by poll,
2026-10-03): closures and warnings must still publish when their history
cannot be restored. Then the restore's failure is printed as an error, every
dbt command runs with OURHIKE_ROW_HISTORY=off and leaves the snapshots out,
so the marts read their final intermediates with both dates null (unknown,
never "new"), nothing is saved, and the build exits DEGRADED_EXIT once
everything else has passed, so the workflow publishes and then goes red. A
command that fails with that code itself is answered with 1, so the workflow
never reads a failed build as a publishable one. The
default, `fail`, is the monthly lane's: a restore that fails stops the build
before dbt runs. Elementary's history fails the same way in each lane, with
one difference degrade needs: row_history.py gets --elementary-on-failure
degrade, and when only Elementary's part fails it still restores or saves
the snapshots and exits ELEMENTARY_DEGRADED_EXIT (3). That is answered as
part of the build held back, PARTIAL_EXIT, never as DEGRADED_EXIT: the row
dates stand, Elementary's checks see no earlier build in that run or its
history is not saved, and the workflow publishes and then goes red. A
failure of Elementary's history never nulls a hiker's row dates.

ONE SOURCE OR ONE WRITER NEVER STOPS THE REST (decision 81, the maintainer's
poll of 2026-10-05: "Hold that source and publish the rest"; review finding
ARCH-1 of PR #1805 — dlt → dbt re-platform as one go/no-go change). Five of
the hourly soak's first ten runs published nothing because of one source:
runs 525 to 527 and 530 on a test of one source's rows, run 531 on one
writer's SQL after six other writers had written. Four things now answer
PARTIAL_EXIT instead, once everything else has run, so the workflow publishes
what was written and then turns the run red:
- a test whose `meta` sets `holds_a_source` warned: it names rows that
  int_closures__gate holds their source for (a club's wording in a published
  column, a row outside its region box), and its rows are printed as a failed
  test's are;
- a model of one generated club notice source failed in stage A (a SQL error
  on one source's rows): that source's raw tables are dropped from the
  warehouse and stage A runs once more, so the gate holds the source as "not
  in this warehouse" and it carries its last good rows. Any other failure in
  stage A stops the build, as before;
- some pub_ writers failed and every failure in that dbt run is a writer's
  own (its model, or a test or unit test of it): each failed writer's file is
  removed from the processed directory, so a half-written or untested file
  is never there to publish, and its key keeps the bucket's last copy. The
  log says which files were written. publish.py, told so by
  OURHIKE_BUILD_PARTIAL, keeps a failed writer's key rather than refusing
  the whole publish;
- a table the extract withdrew (WITHDRAWABLE: OurHike's field notes and
  disputes, when the reader cannot see public.field_notes): it is not in the
  warehouse, and its hand-staged base model reads source() directly, so
  stage A used to fail on it and publish nothing, #922 — The whole
  conditions bake has been failing hourly since field notes landed, so the
  closures baseline is ageing, back on this path (review finding PY-2 of PR
  #1805). Its source and everything below it are left out of every dbt
  build; no mart reads either table.
The row history is still saved: the marts passed their tests, and a source
held this way carries its rows rather than losing them (Reasoned).

--dbt and --python differ in CI, where dbt is in the job's
requirements-dbt.txt venv and the steps need requirements.txt's rasterio
($RUNNER_TEMP/pipeline); this file imports only the standard library, so it
runs on either. Every dbt command gets OURHIKE_WAREHOUSE and
OURHIKE_PROCESSED_DIR as absolute paths, so dbt and the steps read one
warehouse.

ELEMENTARY'S TABLES ARE BUILT FIRST, right after the row history and
Elementary's own history are restored (decision 102, ELT.md "Data quality
(decision 102)"). Every dbt command here
runs with OURHIKE_ELEMENTARY=true, dbt_project.yml's switch for Elementary's
models and its two hooks, and the end-of-run hook writes each command's
results into those tables. With a table missing, a command records nothing
and still passes (measured 2026-10-08 on dbt 2.0.6), so `dbt run --select
package:elementary` comes before `dbt seed`, and stage A leaves the package
out. That run also loads the tables describing the project itself, through
their own post-hooks, which is why dbt_project.yml turns the end-of-run
hook's copy of that work off. The pytest suites leave the switch off.

ELEMENTARY'S CHECKS RUN AFTER THE WRITERS, in a pass of their own, before the
row history's save (decision 102, ELT.md "Data quality (decision 102)"):
`dbt test -s tag:elementary_check` at one thread, lane-scoped as the writers
are (the lane's excludes, a held step's and a withdrawn table's). Every check
is tagged `elementary_check` at warn (make_dbt_staging.py's raw_table_checks()
on every raw table, the marts' YAML for the rest), and every dbt build before
the pass leaves that tag out, so no check runs beside its model, where one
that errored would fail the build. The pass never changes the build's exit
and never stops a publish. Warnings are the design, and the data-quality file
reads them; a check that errors, or a pass that ends without results or
selects none, is named in the log with one `::warning` annotation
(checks_report()), and the build goes on to save its history. It is never retried: `dbt retry` follows
a build that failed, whose nodes a publish needs, and a check is no such node
(Reasoned; the maintainer's three retries were asked of builds). The checks
on a raw table the warehouse does not hold are left out (absent_sources()),
because they would error on an absence the extract has already reported. The
monthly lane's pass trains on MONTHLY_TRAINING_DAYS, given as --vars.
Nearly all of the pass's time is Elementary's own work while dbt compiles each
check (it queries the table, stores the metrics and scores them, before the
test's one select runs), so the pass grows with the number of checks and
hardly with their kind, and not with --threads: 0.32 to 0.35 s of CPU a check
and about 20 s a pass (measured 2026-10-08 on the fixtures in a 4-CPU
sandbox: the monthly lane's 917 checks took 314 s of CPU and 295 s of wall on
a quiet machine; under other builds' load the hourly lane's 1,041 took 381 s
and 485 s, 280 of them 117 s and 189 s, and all 1,041 at four threads 407 s
in 390 s; dbt timed the tests themselves at 5 to 22 s a pass). The checks
are enabled only where they are needed, for Elementary's own tables and for
the pass, and only in a build that runs them (CHECKS_SWITCH), because enabled
they cost every dbt command too: `dbt parse` with Elementary on took 16.9 to
17.5 s of CPU with the 1,979 enabled against 12.0 to 12.8 s without them,
alternated three times the same day, and 13.9 to 16.8 s with them disabled.
The hourly lane, which runs none, took 406 s of CPU against 347 s before the
checks with them enabled, 86 s against 47 s of its Elementary tables' wall
in loading dbt_tests, and 384 s against 359 s with them disabled (two runs,
each beside a build of the commit before, the same day). CI's fixture build
runs the 1,949 whose tables its warehouse holds: 718 s and 802 s of wall in
two builds in that sandbox, about 650 to 700 s of CPU by the figures above,
against the 253 to 428 s its whole build_marts.py took on runners before the
checks (ELT.md, "What step 1 measured").

THE HOURLY LANE RUNS NO CHECKS YET (HOURLY_LANE_CHECKS, the maintainer's to
decide). Its 1,053 checks would cost about 360 to 385 s of CPU by the
figures above, 7.2 to 10.6 minutes on a runner that pays Elementary 1.2 to
1.65 times what the sandbox did (ELT.md, "What step 1 measured"), where
decision 103 gives the whole build step 10 minutes and the build already
takes about 263 to 303 s of them (Reasoned from those figures; one timed run
of the lane with its checks settles it). Without them the lane still parses
them, disabled, in each of its five dbt commands. CI's fixture build, which
has no lane, runs every check of both lanes meanwhile, so one that errors is
annotated on every pull request rather than found first in the lane.

THE DATA-QUALITY FILE IS WRITTEN LAST (decision 102, step 4): the lane's
DATA_QUALITY_WRITERS entry, pub_data_quality or pub_conditions_data_quality,
in a pass of its own after the writers and Elementary's checks, before the
row history is saved, because it reads what those checks recorded. The
writers' pass leaves both out. Every dbt command gets OURHIKE_BUILD_STARTED_AT
(UTC, to the second), which tells the file this build's results from the
history in Elementary's tables (macros/data_quality.sql). Two rules keep the
pass from touching what hikers get:
- publish.py reads the run results of the writers' run as the proof that a
  phone file was written (publish.collect_dbt_phone_files), and every later
  dbt command writes its own over them, so the writers' are kept aside as
  writers_run_results.json, beside run_results.json, and written back after
  this pass with its own results added. With them lost, publish.py would read
  every phone file but this one as kept, and publish nothing else, quietly.
- a failed pass never stops the build or changes its exit: the file is page
  data, not a phone file (decision 102: the checks "never block a publish").
  Its file is removed, the writers' run results are written back without it,
  so publish.py keeps the bucket's last copy, and an ::error says so.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import tomllib

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
#: Whether the hourly lane runs ELEMENTARY_CHECKS. Not yet: its 1,053 checks would take longer than the hourly build
#: step has left inside decision 103's 10 minutes (the module docstring, "THE HOURLY LANE RUNS NO CHECKS YET", has the
#: sums), and turning them on is the maintainer's decision. CI's fixture build runs every check of both lanes meanwhile.
HOURLY_LANE_CHECKS = False
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
#: lane a window of about 400 ("Memory between runs"), so that the 7 earlier builds an anomaly check waits for, one a
#: month, fall inside it. Hourly: Elementary's default days_back of 14, plus 7. Reasoned from Elementary 0.26.0: a
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
#: The `meta` key of a test whose warning means int_closures__gate held a source for the rows it returns.
HOLDS_A_SOURCE = "holds_a_source"
#: The readers seed: which raw tables are each club notice source's, and which of them are generated.
NOTICE_READERS = DBT_DIR / "seeds" / "notice_readers.csv"
#: THE HAND-STAGED RAW TABLES A CONDITIONS LEG MAY WITHDRAW, each with its dbt source: OurHike's field notes and
#: disputes, the ConditionsQuery tables whose database table export_conditions.py's PENDING_READER_SETUP lets go
#: missing. Their base models read source() directly, so a withdrawn one fails stage A (review finding PY-2 of PR
#: #1805). Named here because this file imports only the standard library; tests/test_build_marts.py holds it against
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


#: Run.stage of stage A, of the pub_ writers' dbt run, of Elementary's checks, and of the data-quality file's.
STAGE_A, WRITERS, CHECKS, DATA_QUALITY = "stage_a", "writers", "checks", "data_quality"


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
) -> list[Run]:
    """One `dbt build -s <select> --exclude <exclude>`, or with `split` its three passes (the module docstring, "A MODEL
    TAGGED `builds_alone`"), `alone` being `common` at one thread. Given the manifest, a pass that selects nothing is
    left out, and a build whose tagged-models pass selects nothing is not split at all. Every run carries `stage`, so
    each of stage A's passes is answered as stage A (Run.stage)."""

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
    if not split or (manifest is not None and not selects_anything(manifest, *passes[1][2:])):
        return [run(label, common, select, exclude)]
    return [run(*each) for each in passes if manifest is None or selects_anything(manifest, *each[2:])]


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
    (absent_sources()), in their own pass (the module docstring, "ELEMENTARY'S CHECKS RUN AFTER THE WRITERS"). The
    lane's data-quality writer builds after them, whether or not they ran (the module docstring, "THE DATA-QUALITY
    FILE IS WRITTEN LAST")."""
    if lane not in (None, *LANES):
        raise ValueError(f"no lane {lane!r}; lanes are {', '.join(LANES)}")
    if state is not None and lane != HOURLY:
        raise ValueError("--state is the hourly lane's: only it defers to another build's nodes")
    if unknown := sorted(set(without) - {step.name for step in steps}):
        raise ValueError(f"--without-step names no entry of STEPS: {', '.join(unknown)}")
    common = ("--profiles-dir", profiles_dir, *(("--threads", str(threads)) if threads else ()))
    alone = ("--profiles-dir", profiles_dir, "--threads", "1")
    builds = {"dbt": dbt, "common": common, "alone": alone, "split": lane != HOURLY, "manifest": manifest}
    fields = {"warehouse": str(paths.warehouse), "raw_dir": str(paths.raw_dir)}
    running = [step for step in steps if step.name not in without and (lane is None or step.lane == lane)]
    # What a step that does not run here would have unblocked, and what a
    # table the extract withdrew feeds: built by no invocation of this build,
    # so a writer below either keeps its last file.
    held = tuple(f"source:{DERIVED_SOURCE}.{step.table}+" for step in steps if step not in running)
    held += tuple(f"source:{WITHDRAWABLE[table]}.{table}+" for table in withdrawn)
    selection: tuple[str, ...] = ()
    lane_exclude: tuple[str, ...] = ()
    after: tuple[str, ...] = ()  # options every dbt build of the lane carries after its --exclude
    if lane == MONTHLY:
        lane_exclude = LANE_EXCLUDES
    elif lane == HOURLY:
        selection = (*LANE_EXCLUDES, *(LANE_PARENTS if state is None else ()))
        after = ("--defer", "--state", str(state)) if state is not None else ("--indirect-selection", "cautious")

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
    no_checks = f"tag:{ELEMENTARY_CHECK}"  # every dbt build's: the checks pass runs them, after the writers
    stage_a_exclude = ["package:dbt_project_evaluator", "package:elementary", "path:models/publish", no_checks]
    if running:
        stage_a_exclude.append(f"source:{DERIVED_SOURCE}+")
    no_snapshots = () if snapshots else (SNAPSHOTS,)
    stage_a_exclude += [*held, *lane_exclude, *no_snapshots]
    label = "stage A: everything no Python step reads back"
    if lane == HOURLY:
        label = "stage A of the hourly lane: every node an hourly or daily source reaches, no step reads back"
    runs += _builds(label, **builds, select=selection, exclude=tuple(stage_a_exclude), after=after, stage=STAGE_A)
    for position, step in enumerate(running):
        arguments = step.command + (step.fixture_args if fixtures else dict(step.lane_args).get(lane, ()))
        runs.append(Run(step.name, (python, *(argument.format(**fields) for argument in arguments)), PIPELINE_DIR))
        later = [f"source:{DERIVED_SOURCE}.{following.table}+" for following in running[position + 1 :]]
        runs += _builds(
            f"what {DERIVED_SOURCE}.{step.table} unblocks",
            **builds,
            select=(f"source:{DERIVED_SOURCE}.{step.table}+",),
            exclude=("path:models/publish", no_checks, *later, *held, *no_snapshots, *lane_exclude),
            after=after,
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
        # Lane-scoped as the writers are, at one thread, and with the monthly lane's training window (the module
        # docstring, "ELEMENTARY'S CHECKS RUN AFTER THE WRITERS").
        if lane == HOURLY:
            chosen = tuple(f"{no_checks},{selector}" for selector in LANE_EXCLUDES)
        else:
            chosen = (no_checks,)
        left_out = (*lane_exclude, *held, *absent)
        argv = (dbt, "test", *alone, "-s", *chosen, *(("--exclude", *left_out) if left_out else ()), *after)
        if lane == MONTHLY:
            argv += ("--vars", json.dumps({"days_back": MONTHLY_TRAINING_DAYS}))
        runs.append(Run(ELEMENTARY_CHECKS, argv, DBT_DIR, CHECKS, CHECKS_SWITCH))
    # The module docstring, "THE DATA-QUALITY FILE IS WRITTEN LAST". It leaves out what every other build does, which
    # neither writer reads, so that each dbt build of a lane leaves out the same nodes.
    quality = tuple(DATA_QUALITY_WRITERS.values()) if lane is None else (DATA_QUALITY_WRITERS[lane],)
    quality_out = (no_checks, *held, *no_snapshots, *lane_exclude)
    quality_argv = (dbt, "build", *common, "-s", *quality, "--exclude", *quality_out, *after)
    runs.append(Run(DATA_QUALITY_LABEL, quality_argv, DBT_DIR, DATA_QUALITY))
    if history is not None:
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


def runs_checks(lane: str | None) -> bool:
    """Whether a build in `lane` runs Elementary's checks: every lane but the hourly one, until HOURLY_LANE_CHECKS (the
    module docstring, "THE HOURLY LANE RUNS NO CHECKS YET")."""
    return lane != HOURLY or HOURLY_LANE_CHECKS


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


def _matching(manifest: dict, criterion: str, *, selecting: bool) -> set[str]:
    """What one dbt selector criterion (`method:value`, its graph `+`s, no `,`) can select: exactly for the methods
    this file's commands use, and for any other, everything when `selecting` and nothing when not, so that
    selects_anything() errs toward running a pass."""
    resources = _resources(manifest)
    body = criterion.removeprefix("+").removesuffix("+")
    method, colon, value = body.partition(":")
    found: set[str] | None = None
    if not colon or any(character in body for character in "*?@+ "):
        found = None  # a bare name, a wildcard, `@` or a depth such as `2+`: not read here
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


def selects_anything(manifest: dict, select: tuple[str, ...], exclude: tuple[str, ...]) -> bool:
    """Whether `dbt build -s <select> --exclude <exclude>` can run anything in this manifest: a model, seed, snapshot or
    test. It over-reads `select` and under-reads `exclude`, so a pass is skipped only when dbt would surely run nothing
    in it. Tests go as dbt's default (eager) indirect selection takes them, which no split build changes: in with any
    parent selected, out only here with every parent excluded (where eager takes out a test with any)."""
    tests = ("test.", "unit_test.")
    if select:
        chosen: set[str] = set()
        for item in select:
            chosen |= set.intersection(*(_matching(manifest, part, selecting=True) for part in item.split(",")))
    else:
        chosen = set(_resources(manifest)) | set(manifest.get("child_map") or {})
    children, parents = manifest.get("child_map") or {}, manifest.get("parent_map") or {}
    chosen |= {child for uid in chosen for child in children.get(uid) or [] if child.startswith(tests)}
    excluded: set[str] = set()
    for item in exclude:
        excluded |= set.intersection(*(_matching(manifest, part, selecting=False) for part in item.split(",")))
    excluded |= {uid for uid in chosen if uid.startswith(tests) and parents.get(uid) and set(parents[uid]) <= excluded}
    return any(uid.split(".")[0] in ("model", "seed", "snapshot", "test", "unit_test") for uid in chosen - excluded)


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
    """The generated club notice sources whose own models errored in this dbt run, each with its raw tables, or None
    unless every failure in it is that (the module docstring, "ONE SOURCE OR ONE WRITER NEVER STOPS THE REST").

    A model is one source's own when the only club notice raw tables above it are that one source's, and the source
    is generated (seeds/notice_readers.csv's `staged_by` is a model, never `hand`): its base and staging models read
    an absent table as typed and empty (macros/notices.sql's notice_raw_table), and the gate holds the source with
    that reason. A union of several sources, a hand-staged source's model, any failed test or unit test, and anything
    else is not one source's own, so the build stops on it as before. Skipped nodes are what a failure left unbuilt
    and say nothing of their own."""
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
        if not unique_id.startswith("model.") or status != "error":
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


def checks_report(results: list[dict] | None, returncode: int) -> list[str]:
    """What the log says about Elementary's checks pass, which never changes the build's exit (the module docstring,
    "ELEMENTARY'S CHECKS RUN AFTER THE WRITERS"): a count of each status, every check that warned or errored by name,
    each error's first line cut at FAILED_VALUE_WIDTH, and an annotation (`::warning`) when any check errored or the
    pass ended without results. No check's rows: Elementary keeps none (dbt_project.yml's test_sample_row_count)."""
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
    if not results:
        # Every lane's pass selects its marts' checks at least, so none at all is a switch or a selection gone wrong.
        lines.append(
            f"::warning title=Elementary's checks ran none::the checks pass selected no check (exit {returncode}), so "
            "nothing of this build was checked: CHECKS_SWITCH or the pass's selection is wrong. The build and its "
            "publish go on."
        )
    errored = []
    for result in sorted(results, key=lambda each: str(each.get("unique_id"))):
        status = str(result.get("status"))
        if status not in ("warn", "fail", "error", "runtime error"):
            continue
        name = str(result.get("unique_id", "")).removeprefix("test.")
        first = (str(result.get("message") or "").strip().splitlines() or [""])[0][:FAILED_VALUE_WIDTH]
        lines.append(f"-- build_marts: {ELEMENTARY_CHECKS}: {status}: {name}" + (f": {first}" if status != "warn" else ""))
        if status in ("error", "runtime error"):
            errored.append(name)
    if errored or returncode != 0:
        shown = ", ".join(errored[:10]) + (f" and {len(errored) - 10} more" if len(errored) > 10 else "")
        lines.append(
            f"::warning title=Elementary's checks errored::{len(errored)} check(s) errored (exit {returncode})"
            + (f": {shown}" if shown else "")
            + ". A check that errors stops nothing: the build, its exit and its publish go on, and the page counts it."
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


def keep_writers_results(results_path: Path | None = None) -> None:
    """Copy the writers' run results aside, where no later dbt command writes (the module docstring, "THE DATA-QUALITY
    FILE IS WRITTEN LAST")."""
    path = results_path or RUN_RESULTS_PATH
    kept = path.with_name(WRITERS_RESULTS_NAME)
    kept.unlink(missing_ok=True)
    if path.exists():
        shutil.copyfile(path, kept)


def data_quality_written(
    completed: subprocess.CompletedProcess, manifest: dict, processed_dir: Path, results_path: Path | None = None
) -> None:
    """After the data-quality pass, run_results.json as publish.py reads it: the writers' run's results, with the
    pass's own added when it passed. A failed pass's files are removed, so publish.py keeps the bucket's last copy, and
    an ::error says so; the build goes on (the module docstring, "THE DATA-QUALITY FILE IS WRITTEN LAST"). With no
    writers' results kept, no run_results.json is left, so publish.py refuses rather than reads every file as kept."""
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
        print(
            f"::error title=Data-quality file not written::{DATA_QUALITY_LABEL} failed (exit {completed.returncode}), so "
            f"{', '.join(sorted(file.name for file in files.values())) or 'its file'} is not published and the bucket's "
            "last copy stands. Every phone file still publishes, and the build's exit is unchanged.",
            flush=True,
        )
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
    parser.add_argument("--dry-run", action="store_true", help="print the commands and run none")
    args = parser.parse_args(argv)

    paths = Paths(
        warehouse=_resolved(args.warehouse, "OURHIKE_WAREHOUSE", PIPELINE_DIR / "data" / "warehouse.duckdb"),
        processed_dir=_resolved(args.processed_dir, "OURHIKE_PROCESSED_DIR", PIPELINE_DIR / "data" / "processed" / "dbt"),
        raw_dir=args.raw_dir.resolve(),
    )
    try:
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
        }
        planned = {**options, "history": history, "save_history": not args.no_history_save}
        runs = plan(STEPS, **planned)
    except ValueError as refused:
        parser.error(str(refused))
    files = {"OURHIKE_WAREHOUSE": str(paths.warehouse), "OURHIKE_PROCESSED_DIR": str(paths.processed_dir)}
    # TZ=UTC and OURHIKE_BUILT_BY: the module docstring, "THE ROW HISTORY IS RESTORED FIRST AND SAVED LAST";
    # OURHIKE_BUILD_STARTED_AT: "THE DATA-QUALITY FILE IS WRITTEN LAST".
    env = {
        **os.environ,
        **files,
        "TZ": "UTC",
        "OURHIKE_BUILT_BY": built_by(os.environ),
        "OURHIKE_BUILD_STARTED_AT": build_started_at(),
        **ELEMENTARY_SWITCH,
    }
    for name, _ in CHECKS_SWITCH:
        env.pop(name, None)  # the checks' switch is each Run's own to give (Run.env), never inherited by every command
    print("-- build_marts: " + " ".join(f"{name}={value}" for name, value in files.items()), flush=True)
    print(f"-- build_marts: OURHIKE_BUILT_BY={env['OURHIKE_BUILT_BY']}", flush=True)
    if notice:
        # A workflow command is one only at the start of its line, so a warning is printed as it is.
        print(notice if notice.startswith("::") else f"-- build_marts: {notice}", flush=True)
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
    for table in options["withdrawn"]:
        print(
            f"::error title={table} withdrawn::the extract found {table} unavailable (its newest {RUN_LOG_TABLE} row), "
            f"so it is not in this warehouse, and source:{WITHDRAWABLE[table]}.{table} and everything below it are "
            "left out of every dbt build here. No mart reads it, so every other source still builds and publishes, and "
            "the run goes red afterwards.",
            flush=True,
        )
    if options["withdrawn"]:
        partial.append(f"{', '.join(options['withdrawn'])} withdrawn by the extract")
    stage_a_rerun = False
    position = 0
    while position < len(runs):
        run = runs[position]
        position += 1
        if run.stage == CHECKS:
            # Less the checks on each raw table the warehouse does not hold now, which counts the tables of a source
            # dropped after a failed model of its own (one_sources_failures()), and the same pass otherwise. A
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
                (run,) = [each for each in plan(STEPS, **planned, absent=absent) if each.stage == CHECKS]
        print(f"-- build_marts {position}/{len(runs)}: {run.label}", flush=True)
        # A dbt run's results are the run_results.json it leaves, and an earlier run's file is removed first so
        # nothing else can be mistaken for them. Never told apart by mtime: Linux stamps a file from a coarse clock
        # that can lag time.time() by a few milliseconds, so results written within one tick of `started` read as
        # older than the run that wrote them (CI's pytest job on 461954c4, Pipeline tests run 37357769435, which
        # lost a stage A hold that way). A Python step leaves none, so the mtime still turns the last dbt run's away.
        if run.cwd == DBT_DIR:
            RUN_RESULTS_PATH.unlink(missing_ok=True)
        started = time.time()
        results_since = float("-inf") if run.cwd == DBT_DIR else started
        completed = subprocess.run(run.argv, cwd=run.cwd, env={**env, **dict(run.env)}, check=False)
        if run.stage == CHECKS:
            # Never retried, never a stop, never the build's exit (the module docstring, "ELEMENTARY'S CHECKS RUN
            # AFTER THE WRITERS"): reported, and the build goes on to save its history.
            for line in checks_report(read_run_results(results_since), completed.returncode):
                print(line, flush=True)
            continue
        if completed.returncode != 0 and run.argv[1:2] == ("build",) and run.cwd == DBT_DIR:
            completed = retry_failed_build(run, {**env, **dict(run.env)}, completed)
        # The module docstring, "THE DATA-QUALITY FILE IS WRITTEN LAST".
        if run.stage == WRITERS:
            keep_writers_results()
        if run.stage == DATA_QUALITY:
            data_quality_written(completed, _read_manifest(), paths.processed_dir)
            continue
        if completed.returncode != 0 and run.stage in (STAGE_A, WRITERS) and completed.returncode not in PUBLISHABLE_EXITS:
            print(f"-- build_marts: {run.label} failed (exit {completed.returncode}): {' '.join(run.argv)}", flush=True)
            for line in failed_test_rows(paths.warehouse, results_since):
                print(line, flush=True)
            results, manifest = read_run_results(results_since), _read_manifest()
            if results is not None and run.stage == STAGE_A and not stage_a_rerun:
                if held := one_sources_failures(results, manifest, notice_readers()):
                    for key, tables in sorted(held.items()):
                        dropped = drop_raw_tables(paths.warehouse, tables)
                        print(
                            f"::error title={key} held for a failed model::a model of {key} alone failed in {run.label}, "
                            f"so its raw tables ({', '.join(dropped) or 'none held'}) are dropped from this build's "
                            "warehouse and int_closures__gate holds it as not in this warehouse: it carries its last good "
                            "rows, every other source still publishes, and the run goes red afterwards.",
                            flush=True,
                        )
                    partial.append(f"{', '.join(sorted(held))} held for a failed model")
                    stage_a_rerun = True
                    position -= 1  # stage A once more, with those tables gone
                    continue
            if results is not None and run.stage == WRITERS:
                writers, others = failed_writers(results, manifest)
                if writers and not others:
                    partial.append(_report_writers(results, manifest, writers, paths.processed_dir, started))
                    continue
            return completed.returncode
        if completed.returncode == 0 and run.argv[1:2] == ("build",) and run.cwd == DBT_DIR:
            results = read_run_results(results_since)
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
    if partial:
        print(f"-- build_marts: built with part of it held back ({'; '.join(partial)})", flush=True)
    if degraded:
        code = DEGRADED_PARTIAL_EXIT if partial else DEGRADED_EXIT
        print(f"-- build_marts: built without the row history; exit {code}", flush=True)
        return code
    if partial:
        print(f"-- build_marts: exit {PARTIAL_EXIT}: publish what was written, then go red", flush=True)
        return PARTIAL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
