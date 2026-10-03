"""NC Division of Parks & Recreation: warnings, from the same park page closures.py reads.

A park's alert carousel mixes closure and warning text ('There are no gas stations between Asheville &
the park' beside 'the Parkway is closed'), so one resource feeds both types and dbt splits them
(decision 7).

Before decision 53 phase B (2026-10-03) this file was the coverage audit's note (confirmed 2026-10-01,
batch c9_federal_state_rest): "Banners mix closure and warning text, so they need the decision-7
classifier."
"""

SHARES = "closures"
