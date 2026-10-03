"""NYC's public restrooms (Socrata `i7jb-7jku`) and NYC Parks' drinking fountains (`qnv7-p7a2`).

Each read under its registry row's own `where`, which the portal applies:
restrooms `status='Operational'`, 975 rows on 2026-10-01; fountains the
outdoor-drinking allowlist, 3,195 of the dataset's 3,849 rows, newest
`:updated_at` 2024-07-15. The fountains' `featuresta` reads Active on every
row, so nothing here says a fountain works, and the registry's
`confidence_floor` keeps every one at low confidence downstream
(sources.json, `nyc_drinking_fountains`). The restrooms row's `url` names a
different dataset, `hjae-yuav`, from the one it fetches (ORG_COVERAGE_SURVEY.md
§3b); the resource reads `dataset_id`, as the old fetcher does.
"""

from extract._kinds import socrata_dataset

CLAIMS = ("nyc_public_restrooms", "nyc_drinking_fountains")
RESOURCES = [socrata_dataset(key) for key in CLAIMS]
