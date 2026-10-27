"""Every size and count the API enforces, in one place.

`@unvalidated`, all of them: picked to sit well above what a club volunteer
is expected to do and far below what would let one account fill the
database. Nobody has measured real use; the numbers to compare against,
once there is some, are the largest list and the busiest weights history.
"""

#: Each of the need score's five weights, in the analysis job's order
#: (apps/steward/pipeline/steward_analysis/rules.py, WEIGHT_NAMES). A test
#: holds the two equal.
WEIGHT_NAMES = ("deficit", "water", "trail", "cluster", "restricted")

#: A weight is a whole number of points from 0 to this. The need score is
#: clamped to 100, so a larger weight could only ever saturate it.
WEIGHT_MAX = 100

#: The defaults, the job's rules.DEFAULT_WEIGHTS: what a club's ranking is
#: until somebody changes it. Also held equal to the job's by a test.
DEFAULT_WEIGHTS = {"deficit": 60, "water": 12, "trail": 6, "cluster": 8, "restricted": 10}

DISPLAY_NAME_MAX = 40
LIST_NAME_MAX = 80
NOTE_MAX = 200
#: ATC's RIMS_ID: all 3,442 are 36-character GUIDs (measured 2026-10-27); 64
#: and the pattern below leave room for a format change without accepting markup.
RIMS_ID_MAX = 64
RIMS_ID_PATTERN = r"^[A-Za-z0-9-]{1,64}$"
#: The longest of the 29 club names in the CSI layer is 57 characters (2026-10-27).
CLUB_MAX = 120

LISTS_PER_USER = 50
ITEMS_PER_LIST = 500
#: Weights changes one account may make across all clubs in 24 hours. Open
#: editing is decided (PLAN.md §10, "Open weights"); this caps how fast one
#: account can bury a club's history in noise.
WEIGHT_CHANGES_PER_DAY = 30

#: Any request body, in bytes. The largest legitimate one is a list rename.
MAX_BODY_BYTES = 16 * 1024
