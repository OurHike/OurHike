"""Place accepted survey records on their club's drawn sections: the mile, and the distance off the line (#1987).

    DATABASE_URL=... python scripts/inventory_place.py [--club SLUG]

Accepting a record is meant to place it, once accept exists (#1989 — The
club's chain reviews: accept, send back, merge, not ours, each with a note and
an audit column, and a section supervisor sees only their sections). This
command is for the records accepted before their club drew the sections they
sit on: every accepted
observation with no mile, and every active structure with an accepted
observation and no mile. `app/core/trail_axis.py` is what places them, and
its docstring is why a club with no drawn section gets no mile at all.

It only ever fills a blank. A mile already stored is left alone, and so is the
point a mile was measured from, which nothing here writes. A record that
cannot be placed stays blank and is counted, so the same run said twice
reports the same remainder.

Safe to run twice. Prints counts and nothing that locates a record; a run
that fails exits 1, names the failure by its class alone
(`app/core/logs.py` `describe_failure`), and commits nothing.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import exists  # noqa: E402
from sqlalchemy.orm import Session, aliased  # noqa: E402

from app.core.logs import describe_failure  # noqa: E402
from app.core.trail_axis import MAX_OFF_LINE_FT, place_observation, place_structure  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.club import Club  # noqa: E402
from app.models.inventory import (  # noqa: E402
    InventoryObservation,
    InventoryStructure,
    ReviewState,
    StructureStatus,
)


@dataclass
class Tally:
    looked_at: int = 0
    placed: int = 0

    @property
    def unplaced(self) -> int:
        return self.looked_at - self.placed


def place_unplaced(db: Session, club_id: str | None = None) -> tuple[Tally, Tally]:
    """`(observations, structures)`, each counted as looked at and placed. Does not commit."""
    observations = db.query(InventoryObservation).filter(
        InventoryObservation.review_state == ReviewState.accepted,
        InventoryObservation.mile.is_(None),
    )
    accepted = aliased(InventoryObservation)
    structures = db.query(InventoryStructure).filter(
        InventoryStructure.status == StructureStatus.active,
        InventoryStructure.mile.is_(None),
        exists().where(accepted.structure_id == InventoryStructure.id, accepted.review_state == ReviewState.accepted),
    )
    if club_id is not None:
        observations = observations.filter(InventoryObservation.club_id == club_id)
        structures = structures.filter(InventoryStructure.club_id == club_id)

    observation_tally, structure_tally = Tally(), Tally()
    for observation in observations.order_by(InventoryObservation.id).all():
        observation_tally.looked_at += 1
        if place_observation(db, observation) is not None:
            observation_tally.placed += 1
    for structure in structures.order_by(InventoryStructure.id).all():
        structure_tally.looked_at += 1
        if place_structure(db, structure) is not None:
            structure_tally.placed += 1
    return observation_tally, structure_tally


def _line(what: str, tally: Tally) -> str:
    return (
        f"{what} with no mile: {tally.looked_at}. Placed {tally.placed}; "
        f"{tally.unplaced} have no drawn section within {MAX_OFF_LINE_FT // 5280} mi and stay blank."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--club", metavar="SLUG", help="Place one organization's records only.")
    args = parser.parse_args(argv)

    try:
        with SessionLocal() as db:
            club_id = None
            if args.club is not None:
                club = db.query(Club).filter(Club.slug == args.club).one_or_none()
                if club is None:
                    print(f"No organization has the slug {args.club!r}. Nothing was placed.", file=sys.stderr)
                    return 2
                club_id = club.id
            observations, structures = place_unplaced(db, club_id)
            db.commit()
    except Exception as failure:
        print(f"Nothing was placed, and nothing was committed: {describe_failure(failure)}", file=sys.stderr)
        return 1

    print(_line("Accepted observations", observations))
    print(_line("Structures with an accepted observation", structures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
