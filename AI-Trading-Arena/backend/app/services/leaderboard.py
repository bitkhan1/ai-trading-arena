"""
Leaderboard service — computes and caches agent rankings.

Stats computed:
  - Overall P&L % (all-time)
  - Daily P&L %
  - Weekly P&L %
  - Sharpe Ratio (annualized, from equity snapshots)
  - Win Rate (winning trades / total trades)
  - Max Drawdown %
"""
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.core.redis import get_cache, set_cache, publish, CHANNEL_LEADERBOARD
from app.models.agent import Agent, AgentTrade, AgentPosition
from app.models.equity_snapshot import EquitySnapshot

logger = logging.getLogger(__name__)

LEADERBOARD_CACHE_KEY = "leaderboard:full"
LEADERBOARD_CACHE_TTL = 15  # seconds


async def compute_agent_stats(agent: Agent, db: AsyncSession) -> Dict:
    """Compute full performance stats for a single agent."""
    # ── Equity snapshots for Sharpe + drawdown ─────────────────
    snapshots_result = await db.execute(
        select(EquitySnapshot)
        .where(EquitySnapshot.agent_id == agent.id)
        .order_by(EquitySnapshot.captured_at.asc())
    )
    snapshots = snapshots_result.scalars().all()

    # ── All-time P&L ───────────────────────────────────────────
    open_positions_result = await db.execute(
        select(AgentPosition).where(
            and_(AgentPosition.agent_id == agent.id, AgentPosition.is_open == True)
        )
    )
    open_positions = open_positions_result.scalars().all()
    positions_value = sum(p.quantity * p.current_price for p in open_positions)
    current_equity = agent.cash + positions_value
    total_pnl_pct = (current_equity / agent.starting_capital - 1) * 100

    # ── Daily P&L ──────────────────────────────────────────────
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    day_snapshot_result = await db.execute(
        select(EquitySnapshot)
        .where(
            and_(
                EquitySnapshot.agent_id == agent.id,
                EquitySnapshot.captured_at >= today_start,
            )
        )
        .order_by(EquitySnapshot.captured_at.asc())
        .limit(1)
    )
    day_first_snap = day_snapshot_result.scalar_one_or_none()
    day_start_equity = day_first_snap.equity if day_first_snap else agent.starting_capital
    daily_pnl_pct = (current_equity / day_start_equity - 1) * 100 if day_start_equity > 0 else 0.0

    # ── Weekly P&L ─────────────────────────────────────────────
    week_start = datetime.now(timezone.utc) - timedelta(days=7)
    week_snapshot_result = await db.execute(
        select(EquitySnapshot)
        .where(
            and_(
                EquitySnapshot.agent_id == agent.id,
                EquitySnapshot.captured_at >= week_start,
            )
        )
        .order_by(EquitySnapshot.captured_at.asc())
        .limit(1)
    )
    week_first_snap = week_snapshot_result.scalar_one_or_none()
    week_start_equity = week_first_snap.equity if week_first_snap else agent.starting_capital
    weekly_pnl_pct = (current_equity / week_start_equity - 1) * 100 if week_start_equity > 0 else 0.0

    # ── Sharpe Ratio ───────────────────────────────────────────
    sharpe = _compute_sharpe(snapshots)

    # ── Max Drawdown ───────────────────────────────────────────
    max_drawdown = _compute_max_drawdown(snapshots)

    # ── Win Rate ───────────────────────────────────────────────
    trades_result = await db.execute(
        select(AgentTrade).where(
            and_(AgentTrade.agent_id == agent.id, AgentTrade.action == "sell")
        )
    )
    sell_trades = trades_result.scalars().all()
    wins = sum(1 for t in sell_trades if t.realized_pnl > 0)
    win_rate = (wins / len(sell_trades) * 100) if sell_trades else 0.0

    # Update denormalized stats on agent
    agent.total_pnl_pct = round(total_pnl_pct, 4)
    agent.daily_pnl_pct = round(daily_pnl_pct, 4)
    agent.weekly_pnl_pct = round(weekly_pnl_pct, 4)
    agent.sharpe_ratio = round(sharpe, 4)
    agent.max_drawdown = round(max_drawdown, 4)
    agent.win_rate = round(win_rate, 2)

    return {
        "id": agent.id,
        "name": agent.name,
        "strategy_type": agent.strategy_type,
        "avatar_emoji": agent.avatar_emoji,
        "llm_model": agent.llm_model,
        "cash": round(agent.cash, 2),
        "equity": round(current_equity, 2),
        "positions_value": round(positions_value, 2),
        "total_pnl": round(current_equity - agent.starting_capital, 2),
        "total_pnl_pct": round(total_pnl_pct, 4),
        "daily_pnl_pct": round(daily_pnl_pct, 4),
        "weekly_pnl_pct": round(weekly_pnl_pct, 4),
        "sharpe_ratio": round(sharpe, 4),
        "win_rate": round(win_rate, 2),
        "max_drawdown": round(max_drawdown, 4),
        "total_trades": agent.total_trades,
        "status": agent.status,
        "last_trade_at": agent.last_trade_at.isoformat() if agent.last_trade_at else None,
    }


async def build_leaderboard(db: AsyncSession, period: str = "all") -> List[Dict]:
    """
    Build the ranked leaderboard for a given period.
    period: "all" | "today" | "week"
    """
    # Try cache first
    cache_key = f"leaderboard:{period}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    result = await db.execute(
        select(Agent).where(Agent.status == "active")
    )
    agents = result.scalars().all()

    rows = []
    for agent in agents:
        stats = await compute_agent_stats(agent, db)
        rows.append(stats)
    await db.commit()

    # Sort by appropriate P&L column
    sort_key = {
        "all": "total_pnl_pct",
        "today": "daily_pnl_pct",
        "week": "weekly_pnl_pct",
    }.get(period, "total_pnl_pct")

    rows.sort(key=lambda x: x[sort_key], reverse=True)
    for i, row in enumerate(rows):
        row["rank"] = i + 1

    await set_cache(cache_key, rows, LEADERBOARD_CACHE_TTL)
    return rows


async def push_leaderboard_update(db: AsyncSession):
    """Recompute leaderboard and broadcast via Redis pub/sub."""
    leaderboard = await build_leaderboard(db)
    await publish(CHANNEL_LEADERBOARD, {
        "type": "leaderboard_update",
        "data": leaderboard,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    logger.debug(f"Leaderboard pushed: {len(leaderboard)} agents")


# ── Math Utilities ─────────────────────────────────────────────────────────────


def _compute_sharpe(snapshots: List[EquitySnapshot], risk_free_rate: float = 0.05) -> float:
    """Annualized Sharpe ratio from equity snapshots."""
    if len(snapshots) < 10:
        return 0.0
    equities = [s.equity for s in snapshots]
    returns = [(equities[i] / equities[i - 1] - 1) for i in range(1, len(equities))]
    if not returns:
        return 0.0
    n = len(returns)
    mean_r = sum(returns) / n
    variance = sum((r - mean_r) ** 2 for r in returns) / n
    std_r = math.sqrt(variance) if variance > 0 else 0.0
    if std_r == 0:
        return 0.0
    # Annualize: assuming ~525,960 minutes/year, with ~1-min snapshots
    # Use 252 trading days * 390 minutes as proxy
    annualization = math.sqrt(252 * 390 / max(n, 1))
    daily_rf = risk_free_rate / 252
    return (mean_r - daily_rf) / std_r * annualization


def _compute_max_drawdown(snapshots: List[EquitySnapshot]) -> float:
    """Maximum peak-to-trough drawdown percentage."""
    if len(snapshots) < 2:
        return 0.0
    equities = [s.equity for s in snapshots]
    peak = equities[0]
    max_dd = 0.0
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd
