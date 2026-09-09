-- Where a POI cannot be, which is the guard `int_pois_unioned`'s positional
-- union does not have.
--
-- THE HOLE THIS CLOSES WAS PROVEN, NOT SUSPECTED. During Phase D's review a
-- verifier swapped the `st_x`/`st_y` lines in one staging model and rebuilt:
-- `PASS=145 WARN=0 ERROR=0`, a completely green run, with every DEC lean-to
-- relocated to Antarctica. `dbt_utils.accepted_range` did not catch it
-- because a transposed pair is still inside +/-180 and +/-90 - and the
-- reconciliation tests could not, because they compare ROW COUNTS. `int_pois_
-- unioned` is `select *` across thirteen branches, so column ORDER is a
-- semantic contract and nothing was checking it.
--
-- .sqlfluff's ST06 note used to claim the reconciliation tests covered this.
-- They never did, and the claim is corrected there alongside this file.
--
-- WHY IT MATTERS MORE AFTER PHASE D than before it. Phase A's union had one
-- organization's field order to agree with. It now has three, with three
-- different upstream conventions, and a fourth arrives whenever another org
-- registers. A POI in the wrong place is CLAUDE.md's first way this app can
-- hurt somebody - lost - so the asymmetry is the usual one: this test is
-- allowed to miss a subtle error, and is not allowed to pass a gross one.
--
-- THE BOX, and what it rests on. Every source in `pipeline/sources.json`
-- publishes in the eastern United States: the A.T. runs from Springer
-- Mountain, Georgia to Katahdin, Maine, and the four non-A.T. organizations
-- (NYNJTC, NYS OPRHP, Mohonk Preserve, NYS DEC) all publish inside New York
-- and New Jersey, which sits within that span. The bounds below are that
-- extent with several degrees of margin on every side - roughly 500 km - so
-- an ordinary registration cannot trip it and a transposition cannot survive
-- it. A latitude of -74 or a longitude of 41 is outside by hundreds of
-- degrees, not by a rounding error.
--
-- @unvalidated The margin is picked rather than measured: no source records
-- its own bounding box, so nothing here was computed from real geometry. What
-- would settle it is one pass over a live fetch reporting each layer's actual
-- extent - at which point these numbers should tighten toward it rather than
-- stay generous. The test's VALUE does not depend on the margin being right,
-- only on it being far smaller than a transposition.
--
-- THE FIRST SOURCE OUTSIDE THIS BOX SHOULD FAIL HERE, and that is the design
-- rather than a limitation: a Pacific Crest Trail registration is a decision
-- somebody makes, and widening a safety bound is part of making it.
--
-- Fails by returning rows, like every singular test here.
{{ config(severity='error') }}

select
    source,
    source_id,
    name,
    longitude,
    latitude
from {{ ref('int_pois_unioned') }}
where
    latitude is not null
    and longitude is not null
    and (
        latitude not between 30.0 and 50.0
        or longitude not between -90.0 and -66.0
    )
