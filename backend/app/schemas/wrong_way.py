"""Pydantic request/response models for `/wrong-way-events`."""

from pydantic import BaseModel


class WrongWayEventCreate(BaseModel):
    hike_id: str


class WrongWayEventAck(BaseModel):
    received: bool = True
