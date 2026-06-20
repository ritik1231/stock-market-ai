import pandas as pd
import pytest

from app.tools.price_fetcher import fetch_ohlcv, get_latest_price, normalise_ticker

EXPECTED_COLS = {"date", "open", "high", "low", "close", "volume"}


def test_normalise_ticker_adds_ns_suffix():
    assert normalise_ticker("RELIANCE") == "RELIANCE.NS"


def test_normalise_ticker_preserves_existing_suffix():
    assert normalise_ticker("RELIANCE.NS") == "RELIANCE.NS"
    assert normalise_ticker("RELIANCE.BO") == "RELIANCE.BO"


@pytest.mark.asyncio
async def test_fetch_ohlcv_returns_dataframe():
    df = await fetch_ohlcv("RELIANCE.NS", interval="1d", period="5d")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


@pytest.mark.asyncio
async def test_fetch_ohlcv_has_expected_columns():
    df = await fetch_ohlcv("RELIANCE.NS", interval="1d", period="5d")
    assert EXPECTED_COLS.issubset(set(df.columns)), (
        f"Missing columns: {EXPECTED_COLS - set(df.columns)}"
    )


@pytest.mark.asyncio
async def test_fetch_ohlcv_numeric_values():
    df = await fetch_ohlcv("RELIANCE.NS", interval="1d", period="5d")
    for col in ("open", "high", "low", "close"):
        assert pd.to_numeric(df[col], errors="coerce").notna().all(), f"{col} has non-numeric values"
    assert (df["close"] > 0).all()


@pytest.mark.asyncio
async def test_get_latest_price_positive_float():
    price = await get_latest_price("RELIANCE.NS")
    assert isinstance(price, float)
    assert price > 0


@pytest.mark.asyncio
async def test_normalise_ticker_applied_in_fetch():
    """fetch_ohlcv without suffix should return same data as with .NS."""
    df_with = await fetch_ohlcv("TCS.NS", interval="1d", period="5d")
    df_without = await fetch_ohlcv("TCS", interval="1d", period="5d")
    assert not df_with.empty
    assert not df_without.empty
