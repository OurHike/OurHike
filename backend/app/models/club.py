"""The `clubs` table - a maintaining club.

`Club` is a first-class concept already anticipated by FEATURES.md's
multi-club support (value #7) and sketched in
../../../features/VOLUNTEERING.md. It arrives here now because
../../../features/SAYING_THANKS.md needs somewhere for a thanks to go when
the hiker knows the club but not the person - which is the common case.

Deliberately minimal: id, name, region. Crews, membership rosters and admin
tooling all live in VOLUNTEERING.md's larger module and are not invented
here on the strength of one feature needing a name to attribute work to.
"""

import uuid

from sqlalchemy import Column, String

from app.db.base import Base


class Club(Base):
    __tablename__ = "clubs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    region = Column(String, nullable=True)
