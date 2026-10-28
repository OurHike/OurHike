"""Every rule that turns a CSI site into an action, a need score, a tier and a crew size.

The thresholds are apps/remediation/PLAN.md §2's, and almost all of them are
`@unvalidated`: they were picked so the analysis had a shape the maintainer
could react to, and each one says below what would settle it. The two that are
not are ATC's own: the CSI formula (Measured) and its 3-12 "Low" band.

Pure functions over `SiteFacts`, so each rule can be tested from a handful of
invented numbers without a layer, a network or a DataFrame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# --- ATC's vocabulary, as the CSI layer spells it ---------------------------------------------------

USER_CREATED = "User Created Campsite"
SHELTER = "Shelter"
CLUB_CAMPSITE = "A.T. Club or Agency Created Campsite"
OFFICIAL = frozenset({SHELTER, CLUB_CAMPSITE})

#: Inventory states ATC already counts as closed. Their need is 0: the work
#: left is photographing the recovery, which the follow-up visits do.
RECOVERING = frozenset({"Closed/Recovering", "Site Absent/Recovered"})

# --- The CSI score ----------------------------------------------------------------------------------

#: Measured 2026-10-24: a least-squares fit of `CSI_Score` on the eight
#: indicator fields returned these whole-number weights, and with them the sum
#: reproduces 3,442 of 3,442 published scores. ATC publishes no description of
#: its method (PLAN.md §1), so this is the only written one, and the job
#: re-checks it on every run (`build.csi_reproduction`) rather than trusting it.
CSI_WEIGHTS = {
    "Expansion_Potential_Indicator": 2,
    "Size_Indicator": 2,
    "Proximity_Other_Site_Indicator": 1,
    "Proximity_Water_Ecological_Indicator": 1,
    "Proximity_Water_Social_Indicator": 1,
    "Proximity_AT_Indicator": 1,
    "Side_Hill_Footprint_Indicator": 3,
    "Side_Hill_Buffer_Indicator": 3,
}

#: The lowest and highest CSI the weights above can produce, as ATC's map
#: legend states them (3-30). The observed range on 2026-10-24 was the same.
CSI_MIN = 3
CSI_MAX = 30


def csi_from_indicators(indicators: dict) -> int:
    """The CSI the eight indicator fields add up to under `CSI_WEIGHTS`."""
    return sum(weight * int(indicators[field]) for field, weight in CSI_WEIGHTS.items())


# --- Actions ----------------------------------------------------------------------------------------

CLOSE_RESTORE = "close_restore"
HARDEN = "harden"
ADOPT_NOTE = "adopt_note"
MONITOR = "monitor"
MONITOR_RECOVERY = "monitor_recovery"
OK = "ok"
UNKNOWN = "unknown"

#: The two actions that put a site on a club's work list. Everything else is
#: shown, never claimed.
ACTIONABLE = frozenset({CLOSE_RESTORE, HARDEN})

#: ATC's own "Low sustainability" band ends at 12 (the CSI map's legend: Low
#: 3-12, Medium 13-21, High 22-30). Using it as the line for "needs work" is
#: `@unvalidated`: what would settle it is a club walking a sample of sites on
#: each side of it and saying whether the action fits.
WORK_CSI_MAX = 12

#: A user-created site this close to water is a closure candidate whatever its
#: CSI. 100 ft is half of ATC's 200 ft siting distance in its 2023 Overnight
#: Site Planning Guidance, picked to catch only the worst cases.
#: `@unvalidated`: settled the same way as WORK_CSI_MAX.
CLOSE_WATER_FT = 100

#: ATC's "High sustainability" band starts at 22. A user-created site there
#: gets the "your club may want to adopt it" note (decided 2026-10-24).
ADOPT_CSI_MIN = 22


@dataclass(frozen=True)
class SiteFacts:
    """What the rules read about one site, already joined and cleaned."""

    site_type: str
    inventory_status: str
    csi: int
    size_ft2: float
    water_ft: float
    trail_ft: float
    slope_footprint_pct: float
    complex_size: int
    #: True only where a reviewed camping rule (not the placeholder guess) says
    #: dispersed camping is prohibited or restricted on the site's land unit.
    camping_restricted: bool = False


def action(site: SiteFacts) -> str:
    if site.inventory_status in RECOVERING:
        return MONITOR_RECOVERY
    if site.site_type in OFFICIAL:
        # An official site cannot be closed by a volunteer, so the most it can
        # need is hardening in place.
        if site.csi <= WORK_CSI_MAX:
            return HARDEN
        return OK if site.csi >= ADOPT_CSI_MIN else MONITOR
    if site.site_type == USER_CREATED:
        if site.csi <= WORK_CSI_MAX or site.water_ft < CLOSE_WATER_FT:
            return CLOSE_RESTORE
        return ADOPT_NOTE if site.csi >= ADOPT_CSI_MIN else MONITOR
    # 8 rows had a blank Site_Type on 2026-10-24. Nothing is recommended for a
    # site nobody can say the kind of.
    return UNKNOWN


# --- The need score ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Weights:
    """The need score's weights: the defaults below, or a club's own (decided 2026-10-26).

    `@unvalidated`, every one. They count again impacts CSI already includes,
    on purpose: water and trail distance are the two ATC's 2023 guidance sets
    distances for. What would settle them: a club ranking twenty of its own
    sites by hand, and comparing that order with the one these produce.
    """

    #: Points for the whole distance from CSI_MIN to CSI_MAX.
    deficit: float = 60
    #: Within NEAR_WATER_FT; half of it within WATER_FT.
    water: float = 12
    #: Within NEAR_TRAIL_FT of the A.T.
    trail: float = 6
    #: In a complex of 4 or more; half of it in a complex of 2-3.
    cluster: float = 8
    #: A user-created site where a reviewed rule restricts camping.
    restricted: float = 10


DEFAULT_WEIGHTS = Weights()

#: Distances the water and trail points apply within. ATC's guidance puts
#: sites "at least 200 feet from water sources"; CSI's own trail indicator
#: scores 0 under 50 ft. Reused rather than chosen, so not `@unvalidated` in
#: themselves - only the points attached to them are.
NEAR_WATER_FT = 100
WATER_FT = 200
NEAR_TRAIL_FT = 50
BIG_COMPLEX = 4


#: The weights by name, in the order need_parts() lists them.
WEIGHT_NAMES = ("deficit", "water", "trail", "cluster", "restricted")


def need_parts(site: SiteFacts) -> dict[str, float]:
    """What each weight is multiplied by for this site: need is the sum of weight x part.

    Written into sites.json beside the need itself, so the web app can re-rank
    a club's sites under that club's own weights (#1906) by multiplying and
    adding, with no second copy of the rules below to drift from this one.
    All zero for a site already recovering, whose need is 0 whatever the weights.
    """
    if site.inventory_status in RECOVERING:
        return dict.fromkeys(WEIGHT_NAMES, 0.0)
    if site.water_ft < NEAR_WATER_FT:
        water = 1.0
    elif site.water_ft < WATER_FT:
        water = 0.5
    else:
        water = 0.0
    if site.complex_size >= BIG_COMPLEX:
        cluster = 1.0
    elif site.complex_size >= 2:
        cluster = 0.5
    else:
        cluster = 0.0
    return {
        "deficit": (CSI_MAX - site.csi) / (CSI_MAX - CSI_MIN),
        "water": water,
        "trail": 1.0 if site.trail_ft < NEAR_TRAIL_FT else 0.0,
        "cluster": cluster,
        "restricted": 1.0 if site.site_type == USER_CREATED and site.camping_restricted else 0.0,
    }


def need_from_parts(parts: dict[str, float], weights: Weights = DEFAULT_WEIGHTS) -> int:
    """0-100: the weighted sum, clamped, and rounded half up.

    Half up rather than Python's round(), which rounds a half to the even
    neighbour, because the web app does this same sum with JavaScript's
    Math.round, which rounds a half up. A club's own weights can land a sum
    on exactly .5 (a water weight of 13 gives 6.5), and the two must agree.
    """
    score = sum(getattr(weights, name) * parts[name] for name in WEIGHT_NAMES)
    return math.floor(min(max(score, 0), 100) + 0.5)


def need(site: SiteFacts, weights: Weights = DEFAULT_WEIGHTS) -> int:
    """0-100. Higher means more in need of work."""
    return need_from_parts(need_parts(site), weights)


# --- Tiers ------------------------------------------------------------------------------------------

#: `@unvalidated`. Picked so that roughly the worst tenth of all sites is P1:
#: 60 is the 90th percentile of need across all 3,442 sites, measured by the
#: planning spike on 2026-10-24 and again by this job on 2026-10-26. What would
#: settle them is the same hand-ranking that settles the weights.
P1_MIN = 60
P2_MIN = 50


def tier(need_score: int, site_action: str) -> str | None:
    if site_action not in ACTIONABLE:
        return None
    if need_score >= P1_MIN:
        return "P1"
    return "P2" if need_score >= P2_MIN else "P3"


# --- Crew size --------------------------------------------------------------------------------------

ONE_PERSON = "one_person"
TEAM = "team"
CREW = "crew"

#: The largest close-and-restore site one person takes on: 500 ft², chosen by
#: the maintainer by poll on 2026-10-24 over 300 and 750 (127 of 647 sites
#: then, against 83 and 162). Water distance does not enter crew size: it was
#: dropped the same day, because nothing ATC publishes ties it to labour.
#: `@unvalidated`, with CREW_MIN_FT2: ATC publishes no crew size or
#: person-hours for a restoration. What would settle both: the hours and crew
#: sizes recorded on the first verified submissions.
ONE_PERSON_MAX_FT2 = 500
CREW_MIN_FT2 = 1500

#: CSI's own side-hill break: a footprint at 15% or more is cut into a slope,
#: and ATC's 2023 guidance prefers side-hill sites "where the slope is >15%".
#: Work on one is harder footing, so it is never a one-person job.
STEEP_PCT = 15


def crew(site: SiteFacts, site_action: str) -> str | None:
    if site_action not in ACTIONABLE:
        return None
    if site_action == HARDEN or site.size_ft2 > CREW_MIN_FT2 or site.complex_size >= BIG_COMPLEX:
        return CREW
    if site.size_ft2 > ONE_PERSON_MAX_FT2 or site.complex_size >= 2 or site.slope_footprint_pct >= STEEP_PCT:
        return TEAM
    return ONE_PERSON


# --- Camping regime, until the reviewed table exists ------------------------------------------------

#: How specific each PAD-US designation is, most specific first, so a site in
#: a wilderness inside a national forest takes the wilderness's rule.
DESIGNATION_ORDER = ("NP", "WA", "SP", "SREC", "SCA", "SRMA", "NRA", "IRA", "NF", "NT")


def regime_guess(manager: str | None, designation: str | None, unit: str | None) -> str:
    """A guess at the camping regime from the land manager's type alone. It is never scored.

    Every value but "unknown" ends in "?" because none of them is a cited rule
    (PLAN.md §2e). The reviewed table, transcribed by hand from ATC's camping
    regulations page and reviewed row by row, replaces it; until then
    `need()` adds nothing for restricted camping, so a guess cannot move a
    site's rank.
    """
    if unit == "Great Smoky Mountains National Park":
        return "designated_only?"
    if designation == "NP":
        return "permit_or_designated?"
    if manager == "USFS":
        return "dispersed_allowed?"
    if manager == "SFW":
        return "restricted?"
    if designation == "SP":
        return "designated_only?"
    return "unknown"
