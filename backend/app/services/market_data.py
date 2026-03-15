"""
Market data service — fetches real-time and historical prices.

Priority:
  1. Polygon.io (if POLYGON_API_KEY set) — real-time quotes
  2. yfinance — free fallback (15-min delayed)

During non-market hours, returns last known price.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import aiohttp

from app.core.config import settings
from app.core.redis import get_cache, set_cache

logger = logging.getLogger(__name__)

# NASDAQ-100 symbols that agents trade (rotating subset)
NASDAQ_100_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA",
    "AVGO", "COST", "ASML", "NFLX", "AMD", "PEP", "LIN", "ADBE",
    "QCOM", "INTC", "TXN", "AMAT", "INTU", "CSCO", "ISRG", "MU",
    "KLAC", "LRCX", "REGN", "SNPS", "CDNS", "MRVL", "PANW", "ABNB",
    "FTNT", "MDLZ", "KDP", "ORLY", "CTAS", "PAYX", "ROST", "MCHP",
    "DXCM", "ODFL", "IDXX", "FAST", "BKNG", "PCAR", "VRSK", "CPRT",
    "TEAM", "WDAY", "CRWD", "ZS", "COIN", "DDOG", "OKTA", "SNOW",
    "PLTR", "APP", "HOOD", "RBLX",
]

# Cache TTL for price quotes
PRICE_CACHE_TTL = 30  # seconds


async def get_current_price(symbol: str) -> Optional[float]:
    """
    Get the current price for a symbol.
    Returns cached price if fresh, otherwise fetches new data.
    """
    cache_key = f"price:{symbol}"
    cached = await get_cache(cache_key)
    if cached is not None:
        return cached

    price = None

    # Try Polygon.io first
    if settings.POLYGON_API_KEY:
        price = await _fetch_polygon_price(symbol)

    # Fallback to yfinance
    if price is None:
        price = await _fetch_yfinance_price(symbol)

    if price and price > 0:
        await set_cache(cache_key, price, PRICE_CACHE_TTL)

    return price


async def get_bulk_prices(symbols: List[str]) -> Dict[str, float]:
    """Fetch prices for multiple symbols concurrently."""
    tasks = [get_current_price(s) for s in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        sym: price
        for sym, price in zip(symbols, results)
        if isinstance(price, (int, float)) and price > 0
    }


async def get_historical_prices(
    symbol: str, days: int = 30
) -> List[Dict]:
    """
    Get OHLCV bars for the past N days.
    Returns list of {"date": ..., "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...}
    """
    cache_key = f"hist:{symbol}:{days}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    bars = []
    if settings.POLYGON_API_KEY:
        bars = await _fetch_polygon_history(symbol, days)

    if not bars:
        bars = await _fetch_yfinance_history(symbol, days)

    if bars:
        await set_cache(cache_key, bars, 300)  # 5-min cache for history

    return bars


# ── Polygon.io ──────────────────────────────────────────────────────


async def _fetch_polygon_price(symbol: str) -> Optional[float]:
    """Fetch last trade price from Polygon.io."""
    url = f"https://api.polygon.io/v2/last/trade/{symbol}"
    params = {"apiKey": settings.POLYGON_API_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("results", {}).get("p")  # price field
    except Exception as e:
        logger.debug(f"Polygon price fetch failed for {symbol}: {e}")
    return None


async def _fetch_polygon_history(symbol: str, days: int) -> List[Dict]:
    """Fetch daily bars from Polygon.io."""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}"
    params = {
        "apiKey": settings.POLYGON_API_KEY,
        "adjusted": "true",
        "sort": "asc",
        "limit": days + 10,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    return [
                        {
                            "date": datetime.fromtimestamp(r["t"] / 1000).strftime("%Y-%m-%d"),
                            "open": r["o"],
                            "high": r["h"],
                            "low": r["l"],
                            "close": r["c"],
                            "volume": r["v"],
                        }
                        for r in results
                    ][-days:]
    except Exception as e:
        logger.debug(f"Polygon history fetch failed for {symbol}: {e}")
    return []


# ── yfinance fallback ──────────────────────────────────────────────


async def _fetch_yfinance_price(symbol: str) -> Optional[float]:
    """Fetch current price via yfinance (runs in threadpool to avoid blocking)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _yf_price_sync, symbol)


def _yf_price_sync(symbol: str) -> Optional[float]:
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
        return float(price) if price else None
    except Exception as e:
        logger.debug(f"yfinance price fetch failed for {symbol}: {e}")
        return None


async def _fetch_yfinance_history(symbol: str, days: int) -> List[Dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _yf_history_sync, symbol, days)


def _yf_history_sync(symbol: str, days: int) -> List[Dict]:
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{days + 10}d")
        if hist.empty:
            return []
        result = []
        for dt, row in hist.tail(days).iterrows():
            result.append({
                "date": dt.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            })
        return result
    except Exception as e:
        logger.debug(f"yfinance history fetch failed for {symbol}: {e}")
        return []


def is_market_open() -> bool:
    """
    Check if the US stock market is currently open (9:30 AM - 4:00 PM ET, weekdays).
    Simple implementation — doesn't account for holidays.
    """
    import pytz
    now_et = datetime.now(pytz.timezone("America/New_York"))
    if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now_et <= market_close
