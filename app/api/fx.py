from __future__ import annotations

import logging
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from app.schemas.fx import (
    ConvertRequest,
    ConvertResponse,
    CurrencyListResponse,
    ErrorResponse,
    ExchangeQuoteResponse,
    HistoricalConvertRequest,
    HistoricalQuoteRequest,
)
from app.services.frankfurter_client import FrankfurterClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fx", tags=["fx"])

_fx_client: FrankfurterClient | None = None


def get_fx_client() -> FrankfurterClient:
    """Get or create Frankfurter client instance."""
    global _fx_client
    if _fx_client is None:
        _fx_client = FrankfurterClient()
    return _fx_client


@router.get("/quote", response_model=ExchangeQuoteResponse)
def get_quote(
    base: str = Query(..., description="Base currency code (ISO 4217, e.g., USD, EUR)"),
    symbols: str | None = Query(
        None, description="Comma-separated list of target currency codes (e.g., KRW,JPY)"
    ),
) -> ExchangeQuoteResponse:
    """
    Get latest exchange rates.

    Returns exchange rates for the specified base currency and target symbols.
    Rates are updated daily around 16:00 CET (ECB reference rates).
    """
    client = get_fx_client()

    # Parse symbols
    symbol_list = None
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    try:
        result = client.fetch_latest(base.upper(), symbol_list)
    except Exception as exc:
        logger.exception("Error fetching latest rates")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": f"Failed to fetch exchange rates: {str(exc)}",
            },
        )
    
    if result is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": "Failed to fetch exchange rates from Frankfurter API",
            },
        )

    return ExchangeQuoteResponse(**result)


@router.post("/convert", response_model=ConvertResponse)
def convert_currency(request: ConvertRequest) -> ConvertResponse:
    """
    Convert amount from base currency to target currency using latest rates.

    Uses the most recent exchange rate available (typically updated daily around 16:00 CET).
    """
    client = get_fx_client()

    # Fetch latest rate
    quote = client.fetch_latest(request.base.upper(), [request.symbol.upper()])
    if quote is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": "Failed to fetch exchange rates from Frankfurter API",
            },
        )

    rate = quote.get("rates", {}).get(request.symbol.upper())
    if rate is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_currency",
                "message": f"Currency {request.symbol} not found in response",
            },
        )

    converted = round(request.amount * rate, 2)

    return ConvertResponse(
        base=quote["base"],
        symbol=request.symbol.upper(),
        amount=request.amount,
        rate=rate,
        converted=converted,
        as_of=quote["as_of"],
        source=quote.get("source", "ECB via Frankfurter"),
    )


@router.get("/quote/date", response_model=ExchangeQuoteResponse)
def get_historical_quote(
    date_param: date = Query(..., alias="date", description="Date to fetch rates for (YYYY-MM-DD)"),
    base: str = Query(..., description="Base currency code (ISO 4217)"),
    symbols: str | None = Query(
        None, description="Comma-separated list of target currency codes"
    ),
) -> ExchangeQuoteResponse:
    """
    Get historical exchange rates for a specific date.

    Note: Future dates are not supported. Weekend/holiday dates will return the last available business day.
    """
    # Validate date is not in the future
    today = date.today()
    if date_param > today:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_date",
                "message": "Future dates are not supported",
            },
        )

    client = get_fx_client()

    # Parse symbols
    symbol_list = None
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    result = client.fetch_historical(date_param, base.upper(), symbol_list)
    if result is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": "Failed to fetch historical exchange rates from Frankfurter API",
            },
        )

    return ExchangeQuoteResponse(**result)


@router.post("/convert/date", response_model=ConvertResponse)
def convert_currency_historical(request: HistoricalConvertRequest) -> ConvertResponse:
    """
    Convert amount using historical exchange rates for a specific date.

    Note: Future dates are not supported. Weekend/holiday dates will use the last available business day.
    """
    # Validate date is not in the future
    today = date.today()
    if request.target_date > today:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_date",
                "message": "Future dates are not supported",
            },
        )

    client = get_fx_client()

    # Fetch historical rate
    quote = client.fetch_historical(request.target_date, request.base.upper(), [request.symbol.upper()])
    if quote is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": "Failed to fetch historical exchange rates from Frankfurter API",
            },
        )

    rate = quote.get("rates", {}).get(request.symbol.upper())
    if rate is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_currency",
                "message": f"Currency {request.symbol} not found in response",
            },
        )

    converted = round(request.amount * rate, 2)

    return ConvertResponse(
        base=quote["base"],
        symbol=request.symbol.upper(),
        amount=request.amount,
        rate=rate,
        converted=converted,
        as_of=quote["as_of"],
        source=quote.get("source", "ECB via Frankfurter"),
    )


@router.get("/currencies", response_model=CurrencyListResponse)
def get_currencies() -> CurrencyListResponse:
    """
    Get list of supported currency codes and names.

    This list is cached for 24 hours as it changes infrequently.
    """
    client = get_fx_client()
    currencies = client.get_currencies()
    if currencies is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": "Failed to fetch currency list from Frankfurter API",
            },
        )

    return CurrencyListResponse(currencies=currencies)

