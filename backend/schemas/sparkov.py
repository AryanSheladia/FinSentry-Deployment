from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NewPayment(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)
    customer_id: str = Field(pattern=r"^(CUST_[a-f0-9]{16}|NEW_[A-Za-z0-9_-]{1,32})$")
    timestamp: datetime
    amount: float = Field(gt=0, le=10_000_000)
    currency: Literal["USD"] = "USD"
    merchant: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=40)
    merchant_lat: float = Field(ge=-90, le=90)
    merchant_lon: float = Field(ge=-180, le=180)
    home_lat: float | None = Field(default=None, ge=-90, le=90)
    home_lon: float | None = Field(default=None, ge=-180, le=180)
    device_id: str | None = Field(default=None, min_length=1, max_length=64)
    payment_method: Literal["CARD"] = "CARD"

    @field_validator("timestamp")
    @classmethod
    def aware_timestamp(cls,value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must include a timezone")
        if not 2018 <= value.year <= 2100:
            raise ValueError("Supported year range is 2018–2100")
        return value


class HumanReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reviewer: str = Field(min_length=1,max_length=80)
    action: Literal["CLEAR","FLAG","ESCALATE"]
    notes: str = Field(min_length=3,max_length=1000)
