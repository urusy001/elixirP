from __future__ import annotations

from typing import Literal, Optional, Any

from pydantic import Field, BaseModel


class CalcDestination(BaseModel):
    platform_station_id: Optional[str] = None
    address: Optional[str] = None


class CalcPlaceDims(BaseModel):
    dx: int = Field(..., ge=1)           # cm
    dy: int = Field(..., ge=1)           # cm
    dz: int = Field(..., ge=1)           # cm
    weight_gross: int = Field(..., ge=1) # g
    predefined_volume: Optional[int] = Field(None, ge=1)  # cm3


class CalcPlace(BaseModel):
    physical_dims: CalcPlaceDims


class CalcRequest(BaseModel):
    delivery_mode: Literal["self_pickup", "time_interval"]
    destination: CalcDestination

    total_weight: int = Field(..., ge=1)                 # g
    total_assessed_price: int = Field(0, ge=0)           # копейки
    client_price: int = Field(0, ge=0)                   # копейки
    payment_method: Literal["already_paid", "card_on_receipt"] = "already_paid"

    places: list[CalcPlace] = Field(default_factory=list)
    is_oversized: bool = False
    send_unix: bool = True

class PickupPointsResponse(BaseModel):
    points: list[dict[str, Any]]


class PhysicalDims(BaseModel):
    dx: int
    dy: int
    dz: int
    weight_gross: int
    predefined_volume: int | None = None


class Place(BaseModel):
    physical_dims: PhysicalDims


class DestinationSelfPickup(BaseModel):
    platform_station_id: str


class DestinationCourier(BaseModel):
    address: str


class ConfirmInterval(BaseModel):
    from_: int = Field(alias="from")
    to: int

    class Config:
        populate_by_name = True


class ConfirmRequest(BaseModel):
    delivery_mode: Literal["self_pickup", "time_interval"]
    destination: DestinationSelfPickup | DestinationCourier

    total_weight: int = 1
    total_assessed_price: int = 0
    client_price: int = 0

    payment_method: Literal["already_paid", "card_on_receipt"] = "already_paid"
    places: list[Place] = []
    is_oversized: bool = False
    send_unix: bool = True

    interval: ConfirmInterval