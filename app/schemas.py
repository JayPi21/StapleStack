"""Request and response models for the public API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CartLine(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    qty: int = Field(1, ge=1, le=999)


class KitRequest(BaseModel):
    persona_id: str = Field(..., min_length=1, max_length=64)
    cart: list[CartLine] = Field(default_factory=list, max_length=100)
    scale: int | None = Field(None, ge=1, le=500)


class CheckoutRequest(BaseModel):
    persona_id: str = Field(..., min_length=1, max_length=64)
    cart: list[CartLine] = Field(default_factory=list, max_length=100)
