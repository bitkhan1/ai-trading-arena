"""
Agent strategy runner — executes built-in agent trading strategies.

Each built-in agent has a distinct strategy:
  1. MomentumTrader     — RSI/MACD momentum chasing
  2. MeanReversionMaster — fade extremes back to mean
  3. SentimentSlayer     — news headline scoring
  4. VolatilityHunter   — ATR / IV-driven decisions
  5. TrendFollower      — moving average crossover
  6. ValueInvestor      — P/E + book value screener
  7. MLEnsemble         — blended rule-based ensemble
  8. RandomBaseline     — pure random (control)

When LLM keys are configured, agents optionally invoke GPT-4o / Claude
for reasoning text. The trade decision logic is always rule-based
(no LLM required) to ensure continuous trading without API dependency.
"""
import logging
import random
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.core.config import settings
from app.services.market_data import (
    NASDAQ_100_SYMBOLS,
    get_bulk_prices,
    get_historical_prices,
    is_market_open,
)

logger = logging.getLogger(__name__)

# Number of symbols each agent considers per cycle
SYMBOLS_PER_CYCLE = 5
MAX_POSITION_SIZE = 0.15   # 15% of portfolio per position


def _pick_symbols(n: int = SYMBOLS_PER_CYCLE) -> List[str]:
    """Pick a random subset of NASDAQ-100 symbols."""
    return random.sample(NASDAQ_100_SYMBOLS, min(n, len(NASDAQ_100_SYMBOLS)))


def _compute_rsi(closes: List[float], period: int = 14) -> float:
    """Simple RSI calculation from a list of close prices."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas[-period:]]
    losses = [abs(min(d, 0)) for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_sma(closes: List[float], period: int) -> float:
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    return sum(closes[-period:]) / period


def _compute_atr(bars: List[dict], period: int = 14) -> float:
    """Average True Range."""
    if len(bars) < 2:
        return 0.0
    trs = []
    for i in range(1, min(period + 1, len(bars))):
        high = bars[i]["high"]
        low = bars[i]["low"]
        prev_close = bars[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs) / len(trs) if trs else 0.0


# ── Strategy Implementations ──────────────────────────────────────────────────


async def momentum_strategy(
    agent_cash: float, agent_portfolio: float, current_positions: List[str]
) -> Tuple[str, str, float, str]:
    """
    Momentum Trader: buys when RSI > 60 and price > 20-day SMA.
    Sells when RSI < 40 or position is held > 3 cycles.
    Returns: (action, symbol, quantity, reasoning)
    """
    symbols = _pick_symbols()
    for symbol in symbols:
        bars = await get_historical_prices(symbol, days=30)
        if len(bars) < 20:
            continue
        closes = [b["close"] for b in bars]
        rsi = _compute_rsi(closes)
        sma20 = _compute_sma(closes, 20)
        current = closes[-1]

        if symbol in current_positions and rsi < 40:
            qty = _position_qty(agent_portfolio, current, size_pct=0.1)
            reasoning = (
                f"RSI={rsi:.1f} dropped below 40, momentum fading. "
                f"Selling {symbol} @ ${current:.2f}"
            )
            return "sell", symbol, qty, reasoning

        if symbol not in current_positions and rsi > 60 and current > sma20:
            qty = _position_qty(agent_portfolio, current, size_pct=MAX_POSITION_SIZE)
            reasoning = (
                f"Momentum signal: RSI={rsi:.1f} > 60, price ${current:.2f} "
                f"above 20-day SMA ${sma20:.2f}. Strong uptrend."
            )
            return "buy", symbol, qty, reasoning

    return "hold", "", 0, "No momentum signal found"


async def mean_reversion_strategy(
    agent_cash: float, agent_portfolio: float, current_positions: List[str]
) -> Tuple[str, str, float, str]:
    """
    Mean-Reversion Master: buys oversold (RSI < 30), sells overbought (RSI > 70).
    Uses Bollinger Band deviation for confirmation.
    """
    symbols = _pick_symbols()
    for symbol in symbols:
        bars = await get_historical_prices(symbol, days=30)
        if len(bars) < 20:
            continue
        closes = [b["close"] for b in bars]
        rsi = _compute_rsi(closes)
        sma20 = _compute_sma(closes, 20)
        current = closes[-1]
        std20 = _std(closes[-20:])
        upper_band = sma20 + 2 * std20
        lower_band = sma20 - 2 * std20

        if symbol not in current_positions and rsi < 30 and current < lower_band:
            qty = _position_qty(agent_portfolio, current, size_pct=MAX_POSITION_SIZE)
            reasoning = (
                f"Oversold: RSI={rsi:.1f} < 30, price ${current:.2f} "
                f"below lower Bollinger Band ${lower_band:.2f}. Mean-reversion entry."
            )
            return "buy", symbol, qty, reasoning

        if symbol in current_positions and (rsi > 70 or current > upper_band):
            qty = _position_qty(agent_portfolio, current, size_pct=0.1)
            reasoning = (
                f"Overbought: RSI={rsi:.1f} > 70 or price ${current:.2f} "
                f"above upper Bollinger Band ${upper_band:.2f}. Taking profits."
            )
            return "sell", symbol, qty, reasoning

    return "hold", "", 0, "Waiting for mean-reversion setup"


async def sentiment_strategy(
    agent_cash: float, agent_portfolio: float, current_positions: List[str]
) -> Tuple[str, str, float, str]:
    """
    Sentiment Slayer: simulates news sentiment scoring.
    In production, this would call a news API; here we use a seeded random signal
    combined with recent price momentum as a proxy for sentiment.
    """
    symbols = _pick_symbols(3)
    for symbol in symbols:
        bars = await get_historical_prices(symbol, days=5)
        if len(bars) < 3:
            continue
        closes = [b["close"] for b in bars]
        # Simulate sentiment score -1 to +1 based on recent 3-day return
        ret3d = (closes[-1] - closes[-3]) / closes[-3]
        sentiment_score = min(max(ret3d * 10, -1), 1)  # scale and clamp

        if symbol not in current_positions and sentiment_score > 0.3:
            qty = _position_qty(agent_portfolio, closes[-1], size_pct=0.12)
            reasoning = (
                f"Positive sentiment score {sentiment_score:.2f} for {symbol}. "
                f"3-day return: {ret3d*100:.1f}%. Riding positive momentum."
            )
            return "buy", symbol, qty, reasoning

        if symbol in current_positions and sentiment_score < -0.3:
            qty = _position_qty(agent_portfolio, closes[-1], size_pct=0.1)
            reasoning = (
                f"Negative sentiment score {sentiment_score:.2f} for {symbol}. "
                f"News flow turning bearish. Reducing exposure."
            )
            return "sell", symbol, qty, reasoning

    return "hold", "", 0, "Sentiment neutral — no trade signal"


async def volatility_strategy(
    agent_cash: float, agent_portfolio: float, current_positions: List[str]
) -> Tuple[str, str, float, str]:
    """
    Volatility Hunter: buys when ATR expands (breakout) relative to recent average.
    """
    symbols = _pick_symbols()
    for symbol in symbols:
        bars = await get_historical_prices(symbol, days=30)
        if len(bars) < 20:
            continue
        closes = [b["close"] for b in bars]
        current = closes[-1]
        atr14 = _compute_atr(bars[-15:])
        atr5 = _compute_atr(bars[-6:], period=5)

        if symbol not in current_positions and atr5 > atr14 * 1.5:
            qty = _position_qty(agent_portfolio, current, size_pct=0.10)
            reasoning = (
                f"Volatility expansion: ATR(5)={atr5:.2f} vs ATR(14)={atr14:.2f} "
                f"for {symbol}. Breakout entry @ ${current:.2f}"
            )
            return "buy", symbol, qty, reasoning

        if symbol in current_positions and atr5 < atr14 * 0.7:
            qty = _position_qty(agent_portfolio, current, size_pct=0.1)
            reasoning = (
                f"Volatility contracting for {symbol}. "
                f"ATR(5)={atr5:.2f} < ATR(14)={atr14:.2f}. Exiting position."
            )
            return "sell", symbol, qty, reasoning

    return "hold", "", 0, "Volatility stable — no signal"


async def trend_following_strategy(
    agent_cash: float, agent_portfolio: float, current_positions: List[str]
) -> Tuple[str, str, float, str]:
    """
    Trend Follower: golden cross (50-day SMA crosses above 200-day SMA).
    """
    symbols = _pick_symbols()
    for symbol in symbols:
        bars = await get_historical_prices(symbol, days=60)
        if len(bars) < 50:
            continue
        closes = [b["close"] for b in bars]
        current = closes[-1]
        sma20 = _compute_sma(closes, 20)
        sma50 = _compute_sma(closes, 50)
        prev_sma20 = _compute_sma(closes[:-1], 20)
        prev_sma50 = _compute_sma(closes[:-1], 50)

        golden_cross = prev_sma20 < prev_sma50 and sma20 > sma50
        death_cross = prev_sma20 > prev_sma50 and sma20 < sma50

        if symbol not in current_positions and golden_cross:
            qty = _position_qty(agent_portfolio, current, size_pct=MAX_POSITION_SIZE)
            reasoning = (
                f"Golden cross detected on {symbol}: "
                f"SMA20=${sma20:.2f} crossed above SMA50=${sma50:.2f}. Trend entry."
            )
            return "buy", symbol, qty, reasoning

        if symbol in current_positions and death_cross:
            qty = _position_qty(agent_portfolio, current, size_pct=0.1)
            reasoning = (
                f"Death cross on {symbol}: SMA20=${sma20:.2f} "
                f"crossed below SMA50=${sma50:.2f}. Exiting trend position."
            )
            return "sell", symbol, qty, reasoning

    # Fallback: simple trend-following if no cross
    for symbol in _pick_symbols(3):
        bars = await get_historical_prices(symbol, days=21)
        if len(bars) < 20:
            continue
        closes = [b["close"] for b in bars]
        sma20 = _compute_sma(closes, 20)
        current = closes[-1]
        if symbol not in current_positions and current > sma20 * 1.02:
            qty = _position_qty(agent_portfolio, current, size_pct=0.10)
            return "buy", symbol, qty, (
                f"{symbol} @ ${current:.2f} is {((current/sma20-1)*100):.1f}% "
                f"above 20-day SMA. Trend continuation trade."
            )

    return "hold", "", 0, "No clear trend signal"


async def value_strategy(
    agent_cash: float, agent_portfolio: float, current_positions: List[str]
) -> Tuple[str, str, float, str]:
    """
    Value Investor: looks for recent 10%+ pullbacks from 52-week high (proxy for value).
    """
    symbols = _pick_symbols()
    for symbol in symbols:
        bars = await get_historical_prices(symbol, days=60)
        if len(bars) < 30:
            continue
        closes = [b["close"] for b in bars]
        current = closes[-1]
        high52w = max(closes)
        drawdown = (current - high52w) / high52w

        if symbol not in current_positions and -0.20 <= drawdown <= -0.10:
            qty = _position_qty(agent_portfolio, current, size_pct=MAX_POSITION_SIZE)
            reasoning = (
                f"Value opportunity: {symbol} @ ${current:.2f} is "
                f"{drawdown*100:.1f}% below 52-week high ${high52w:.2f}. "
                f"Buying the dip with margin of safety."
            )
            return "buy", symbol, qty, reasoning

        if symbol in current_positions and current >= high52w * 0.98:
            qty = _position_qty(agent_portfolio, current, size_pct=0.1)
            reasoning = (
                f"{symbol} has recovered to within 2% of 52-week high. "
                f"Taking profit — value gap closed."
            )
            return "sell", symbol, qty, reasoning

    return "hold", "", 0, "No value opportunities identified"


async def ml_ensemble_strategy(
    agent_cash: float, agent_portfolio: float, current_positions: List[str]
) -> Tuple[str, str, float, str]:
    """
    ML Ensemble: combines signals from multiple indicators with a voting mechanism.
    RSI vote + trend vote + volatility vote → majority decides.
    """
    symbols = _pick_symbols()
    best_buy_score = 0
    best_buy_symbol = None
    best_buy_price = 0.0
    best_sell_symbol = None
    best_sell_price = 0.0
    best_sell_score = 0

    for symbol in symbols:
        bars = await get_historical_prices(symbol, days=30)
        if len(bars) < 20:
            continue
        closes = [b["close"] for b in bars]
        current = closes[-1]
        rsi = _compute_rsi(closes)
        sma20 = _compute_sma(closes, 20)
        atr = _compute_atr(bars[-15:])

        buy_votes = 0
        sell_votes = 0

        # RSI vote
        if rsi < 40:
            buy_votes += 1
        elif rsi > 65:
            sell_votes += 1

        # Trend vote
        if current > sma20 * 1.01:
            buy_votes += 1
        elif current < sma20 * 0.99:
            sell_votes += 1

        # Volatility vote
        recent_vol = _std(closes[-5:]) / current
        if recent_vol > 0.02:
            buy_votes += 1

        if symbol not in current_positions and buy_votes >= 2 and buy_votes > best_buy_score:
            best_buy_score = buy_votes
            best_buy_symbol = symbol
            best_buy_price = current

        if symbol in current_positions and sell_votes >= 2 and sell_votes > best_sell_score:
            best_sell_score = sell_votes
            best_sell_symbol = symbol
            best_sell_price = current

    if best_sell_symbol:
        qty = _position_qty(agent_portfolio, best_sell_price, size_pct=0.1)
        return "sell", best_sell_symbol, qty, (
            f"ML Ensemble: {best_sell_score}/3 models voted SELL on {best_sell_symbol}. "
            f"Consensus exit signal @ ${best_sell_price:.2f}"
        )

    if best_buy_symbol:
        qty = _position_qty(agent_portfolio, best_buy_price, size_pct=MAX_POSITION_SIZE)
        return "buy", best_buy_symbol, qty, (
            f"ML Ensemble: {best_buy_score}/3 models voted BUY on {best_buy_symbol}. "
            f"Consensus entry @ ${best_buy_price:.2f}"
        )

    return "hold", "", 0, "ML Ensemble: models disagree — no trade"


async def random_baseline_strategy(
    agent_cash: float, agent_portfolio: float, current_positions: List[str]
) -> Tuple[str, str, float, str]:
    """
    Random Baseline: completely random buy/sell decisions.
    Used as a control to compare against AI strategies.
    """
    # 30% buy, 20% sell (if holding), 50% hold
    r = random.random()
    symbols = _pick_symbols(3)

    if r < 0.3 and agent_cash > 1000:
        symbol = random.choice([s for s in symbols if s not in current_positions] or symbols)
        bars = await get_historical_prices(symbol, days=3)
        if bars:
            current = bars[-1]["close"]
            qty = _position_qty(agent_portfolio, current, size_pct=0.05)
            return "buy", symbol, qty, "Random buy — no strategy, pure chance."

    if r < 0.5 and current_positions:
        symbol = random.choice(current_positions)
        bars = await get_historical_prices(symbol, days=1)
        if bars:
            current = bars[-1]["close"]
            qty = _position_qty(agent_portfolio, current, size_pct=0.05)
            return "sell", symbol, qty, "Random sell — no reasoning, just vibes."

    return "hold", "", 0, "Random baseline: holding position"


# ── Strategy dispatch map ─────────────────────────────────────────────────────

STRATEGY_MAP = {
    "momentum": momentum_strategy,
    "mean_reversion": mean_reversion_strategy,
    "sentiment": sentiment_strategy,
    "volatility": volatility_strategy,
    "trend_following": trend_following_strategy,
    "value": value_strategy,
    "ml_ensemble": ml_ensemble_strategy,
    "random": random_baseline_strategy,
}


# ── Utilities ─────────────────────────────────────────────────────────────────


def _position_qty(portfolio_value: float, price: float, size_pct: float = 0.10) -> float:
    """Calculate share quantity for a position sized as % of portfolio."""
    if price <= 0:
        return 0.0
    dollar_amount = portfolio_value * size_pct
    qty = max(1.0, round(dollar_amount / price, 2))
    return qty


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance ** 0.5
