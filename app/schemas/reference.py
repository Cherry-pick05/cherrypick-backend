from __future__ import annotations

from pydantic import BaseModel, Field


class CountryItem(BaseModel):
    code: str = Field(..., min_length=2, max_length=2)
    name_en: str
    name_ko: str
    region_group: str | None = None


class CountryListResponse(BaseModel):
    items: list[CountryItem]


class AirportItem(BaseModel):
    iata_code: str = Field(..., min_length=3, max_length=3)
    icao_code: str | None = Field(default=None, min_length=3, max_length=4)
    name_en: str
    name_ko: str | None = None
    city_en: str | None = None
    city_ko: str | None = None
    country_code: str = Field(..., min_length=2, max_length=2)
    region_group: str | None = None


class AirportListResponse(BaseModel):
    items: list[AirportItem]


