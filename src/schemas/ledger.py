"""Ledger documents contain only a double amount and a description."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_serializer

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Money = Annotated[Decimal, Field(gt=0, le=Decimal("999999999.99"), decimal_places=2, allow_inf_nan=False)]


class ExpenseCreate(BaseModel):
    amount: Money
    description: Description

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class ExpenseUpdate(BaseModel):
    description: Description


class ExpenseResponse(ExpenseCreate):
    id: str


class ExpenseList(BaseModel):
    expenses: list[ExpenseResponse]
