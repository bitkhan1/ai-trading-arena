"""
Leaderboard API — rankings and historical data.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.api.deps import get_db
from app.models.agent import Agent, AgentTrade
from app.models.equity_snapshot import EquitySnapshot
from app.services.leaderboard import build_leaderboard

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("")
async def get_leaderboard(
    period: str = Query("all", regex="^(all|today|week)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the ranked leaderboard.
    period: "all" | "today" | "week"
    """
    rows = await build_leaderboard(db, period=period)
    return {"leaderboard": rows, "period": period}


@router.get("/history")
async def get_leaderboard_history(
    agent_id: Optional[int] = None,
    days: int = Query(7, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get equity history for chart rendering."""
    query = select(EquitySnapshot).order_by(EquitySnapshot.captured_at.asc())

    if agent_id:
        query = query.where(EquitySnapshot.agent_id == agent_id)

    # Limit data points to avoid huge payloads
    result = await db.execute(query)
    snapshots = result.scalars().all()

    # Downsample to max 500 points per agent
    if len(snapshots) > 500:
        step = len(snapshots) // 500
        snapshots = snapshots[::step]

    history = {}
    for snap in snapshots:
        if snap.agent_id not in history:
            history[snap.agent_id] = []
        history[snap.agent_id].append({
            "timestamp": snap.captured_at.isoformat(),
            "equity": snap.equity,
            "daily_pnl_pct": snap.daily_pnl_pct,
        })

    return {"history": history}


@router.get("/agents")
async def list_agents(db: AsyncSession = Depends(get_db)):
    """List all active agents with basic stats."""
    result = await db.execute(select(Agent).where(Agent.status == "active"))
    agents = result.scalars().all()
    return {
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "strategy_type": a.strategy_type,
                "avatar_emoji": a.avatar_emoji,
                "llm_model": a.llm_model,
                "total_pnl_pct": a.total_pnl_pct,
                "daily_pnl_pct": a.daily_pnl_pct,
                "total_trades": a.total_trades,
                "cash": a.cash,
                "status": a.status,
            }
            for a in agents
        ]
    }
