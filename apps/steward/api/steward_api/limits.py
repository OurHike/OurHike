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

# --- Claims (phase 3, #1910) ------------------------------------------------------

#: How long a claim lasts before it is released: the original request's two
#: weeks (PLAN.md §6, `@unvalidated` there: how many claims are released
#: unfinished, by season, would settle it).
CLAIM_DAYS = 14
#: Days an account that rejected a claim must wait before claiming that site.
#: `@unvalidated`: long enough that rejecting cannot be a quick way to take a
#: site; what would settle it is how often rejects happen at all.
REJECTER_WAIT_DAYS = 30
#: How long a crew gets after a reviewer sends a submission back. Picked:
#: PLAN.md stops the clock at Submitted and says nothing about restarting it.
SEND_BACK_DAYS = 7
#: Sites one account may hold at once, counting claims it has submitted and
#: that wait for review, since those hold their sites too (the review's
#: finding 2). High enough to claim a cluster (most are 2-3 sites; the largest
#: is 28, 2026-10-26).
LIVE_CLAIMS_PER_USER = 10
#: Sites in one "claim all" request.
SITES_PER_CLAIM_REQUEST = 10
CREW_MAX = 12

#: The fixed photo points every submission photographs before and after (PLAN.md §5).
PHOTO_POINTS = (1, 2)
#: One photo as it arrives, after the phone has re-encoded it (2048 px on the
#: long side at JPEG quality 0.85 is typically under 1 MB).
PHOTO_MAX_BYTES = 3 * 1024 * 1024
#: The server re-encodes every photo to this long side, as the phone does.
PHOTO_LONG_SIDE = 2048
#: Pixels a photo may claim before it is decoded. Reasoned: the app redraws
#: every photo to at most PHOTO_LONG_SIDE on its long side before sending, so
#: nothing it sends is over 2048 x 2048 (4.2 MP). A camera original is refused
#: unread; 60 MP was allowed until the review's re-check (N1) showed one such
#: upload costing 687 MB to decode.
PHOTO_MAX_PIXELS = 2048 * 2048
#: Seconds a photo's upload may go without a byte arriving, and in all. Idle
#: rather than only a total, so a weak trailhead signal that keeps trickling
#: still gets its photo through (the re-check's N5), while a stalled one is
#: cut off. `@unvalidated`, both: nobody has timed an upload on the trail.
PHOTO_IDLE_SECONDS = 20
PHOTO_READ_SECONDS = 300
PHOTOS_PER_CLAIM = 40
#: Hours one person logs on one claim, across all their visits to it.
HOURS_MAX = 72

NOTES_MAX = 1000
REVIEW_NOTE_MAX = 500
STEP_MAX = 120
STEPS_MAX = 20
