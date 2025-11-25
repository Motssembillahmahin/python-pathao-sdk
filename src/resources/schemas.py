from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

from src.resources.utils import validate_address


class City(BaseModel):
    city_id: int
    city_name: str


class Store(BaseModel):
    """Store model"""

    model_config = ConfigDict(frozen=True)

    id: int = Field(..., gt=0)
    name: str = Field(..., min_length=3, max_length=50)
    contact_name: str = Field(..., min_length=3, max_length=50)
    contact_number: str = Field(..., min_length=11, max_length=11)
    address: str = Field(..., min_length=15, max_length=120)
    city_id: int = Field(..., gt=0)
    zone_id: int = Field(..., gt=0)
    area_id: int = Field(..., gt=0)


class StoreCreate(BaseModel):
    """Store creation model with validation"""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=3, max_length=50)
    contact_name: str = Field(..., min_length=3, max_length=50)
    contact_number: str = Field(..., min_length=11, max_length=11)
    secondary_contact: Optional[str] = Field(None, min_length=11, max_length=11)
    otp_number: Optional[str] = Field(None, min_length=11, max_length=11)
    address: str = Field(..., min_length=15, max_length=120)
    city_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("address")
    @classmethod
    def validate_address_field(cls, v: str) -> str:
        validate_address(v)
        return v
