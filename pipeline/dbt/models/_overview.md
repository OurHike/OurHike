{#
  What ourhike.org/data/ opens on: dbt 2.0.6's docs site draws this block
  where the page opens, in place of dbt's own landing text (P23 of the
  word-choice review of PR #1805, 2026-10-09). Measured that day, in a
  scratch copy of this project built as .github/actions/dbt-docs-site/build.sh
  builds it and opened in Chromium against a local server: the text below
  is the page's first content, and this comment reaches no output file.

  "Hand-written", never "no rows": the unit tests' example rows are on the
  page, and whether decision 10 means them to be is the maintainer's open
  call (pipeline/ELT.md, "Docs and charts").
#}
{% docs __overview__ %}
How each table OurHike publishes is built and tested. Example rows in its
tests are hand-written.

How the checks went on the latest builds is on [Data quality](/data/quality/).
{% enddocs %}
