"""Write every dbt file the two generators own, before anything reads the dbt project (decision 91).

The maintainer, by poll, 2026-10-06, on review findings VOL-1 and DBT2-5 of PR #1805 — dlt → dbt re-platform as one
go/no-go change: "Generate at build time (Recommended): Delete them from the repo; every dbt run (CI, test.sh, the
three lanes, docs) runs the two generators first (<3 s)." So nothing make_dbt_staging.py or
generate_notice_models.py writes is committed (pipeline/dbt/.gitignore lists it), and every place that parses the
project runs this first, from pipeline/:

    python generate_dbt.py

THE PYTHON is one that carries the extract's pins (requirements-extract.txt, or requirements-dev.txt for the pytest
suite): both generators read the extract's club folders through extract/_contract.py's discover(), whose modules
import dlt and requests, so the dbt venv (requirements-dbt.txt) cannot run it.

THE ONE LIST of the generators. A third one is a line here rather than a line in each workflow, action and script
that calls this. Their order does not change what either writes: tests/test_dbt_generated_staging.py runs both
orders from an empty tree and compares every byte.

WHEN IT HAS NOT RUN, dbt fails at parse rather than building less: hand-written models ref the unions the generators
write (int_closures__club_notices reads int_closures__club_notices_unioned, int_points_of_interest__club_points reads
int_points_of_interest__club_unioned), and int_closures__gate reads seeds/notice_readers.csv, which is theirs too.
The pipeline suite refuses to start without the generated tree (tests/conftest.py), so a test that walks the models
cannot pass on the hand-written half alone.

Measured 2026-10-06 in a sandbox, from an empty tree: make_dbt_staging.py 1.7 s (843 files) and
generate_notice_models.py 2.0 s (793 files), on a 4-core container other jobs were sharing.
"""

from __future__ import annotations

import sys

import generate_notice_models
import make_dbt_staging

#: Each generator's main(), run in write mode, in this order.
GENERATORS = (make_dbt_staging, generate_notice_models)


def main() -> int:
    for generator in GENERATORS:
        status = generator.main([])
        if status:
            return status
    return 0


if __name__ == "__main__":
    sys.exit(main())
