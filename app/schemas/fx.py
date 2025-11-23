from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExchangeQuoteResponse(BaseModel):
    """Response for exchange rate quote."""

    as_of: date = Field(..., description="Date of the exchange rate")
    base: str = Field(..., description="Base currency code (ISO 4217)")
    rates: dict[str, float] = Field(..., description="Exchange rates for target currencies")
    source: str = Field(default="ECB via Frankfurter", description="Data source")


class ConvertRequest(BaseModel):
    """Request for currency conversion."""

    amount: float = Field(..., gt=0, description="Amount to convert")
    base: str = Field(..., min_length=3, max_length=3, description="Base currency code (ISO 4217)")
    symbol: str = Field(..., min_length=3, max_length=3, description="Target currency code (ISO 4217)")


class ConvertResponse(BaseModel):
    """Response for currency conversion."""

    base: str = Field(..., description="Base currency code")
    symbol: str = Field(..., description="Target currency code")
    amount: float = Field(..., description="Original amount")
    rate: float = Field(..., description="Exchange rate used")
    converted: float = Field(..., description="Converted amount")
    as_of: date = Field(..., description="Date of the exchange rate")
    source: str = Field(default="ECB via Frankfurter", description="Data source")


class HistoricalQuoteRequest(BaseModel):
    """Request for historical exchange rate quote."""

    model_config = ConfigDict(populate_by_name=True)

    target_date: date = Field(..., alias="date", description="Date to fetch rates for (YYYY-MM-DD)")
    base: str = Field(..., min_length=3, max_length=3, description="Base currency code (ISO 4217)")
    symbols: list[str] | None = Field(
        None, description="List of target currency codes. If None, returns all available currencies."
    )


class HistoricalConvertRequest(BaseModel):
    """Request for historical currency conversion."""

    model_config = ConfigDict(populate_by_name=True)

    target_date: date = Field(..., alias="date", description="Date to use for conversion (YYYY-MM-DD)")
    amount: float = Field(..., gt=0, description="Amount to convert")
    base: str = Field(..., min_length=3, max_length=3, description="Base currency code (ISO 4217)")
    symbol: str = Field(..., min_length=3, max_length=3, description="Target currency code (ISO 4217)")


class CurrencyItem(BaseModel):
    """Currency code and name."""

    code: str
    name: str


class CurrencyListResponse(BaseModel):
    """Response for supported currencies list."""

    currencies: dict[str, str] = Field(..., description="Currency codes and names")


class ErrorResponse(BaseModel):
    """Error response."""

    error: dict[str, Any] = Field(..., description="Error details")

