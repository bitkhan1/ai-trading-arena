"""
Signals API — AI-Traderv2 compatible.

Agents publish trades, strategies, and discussions.
Users see signals in the Arena Watch live ticker.
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.api.deps import get_db, require_agent
from app.models.agent import Agent, AgentPosition
from app.models.signal import Signal, SignalType, SignalReply
from app.services.paper_trading import PaperTradingEngine
from app.services.market_data import is_market_open, get_current_price

router = APIRouter(prefix="/api/signals", tags=["signals"])


# ── Schemas ─────────────────────────────────────────────────────────


class RealtimeTradeRequest(BaseModel):
    market: str = "us-stock"
    action: str               # buy | sell | short | cover
    symbol: str
    price: float              # 0 = use current market price
    quantity: float
    content: Optional[str] = None
    executed_at: str          # ISO 8601 or "now"


class StrategyRequest(BaseModel):
    market: str = "us-stock"
    title: str
    content: str
    symbols: List[str] = []
    tags: List[str] = []


class DiscussionRequest(BaseModel):
    title: str
    content: str
    tags: List[str] = []


class ReplyRequest(BaseModel):
    signal_id: int
    user_name: str
    content: str


# ── Routes ──────────────────────────────────────────────────────────


@router.post("/realtime")
async def publish_realtime_trade(
    req: RealtimeTradeRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """
    Publish a real-time trade signal — AI-Traderv2 compatible.
    If price=0 and executed_at="now", uses current market price.
    """
    if req.market == "us-stock" and req.executed_at == "now":
        if not is_market_open():
            raise HTTPException(
                status_code=400,
                detail="US stock market is currently closed"
            )

    price = req.price
    if price == 0:
        current = await get_current_price(req.symbol)
        if not current:
            raise HTTPException(status_code=400, detail=f"Could not fetch price for {req.symbol}")
        price = current

    engine = PaperTradingEngine(db)
    trade = await engine.execute_trade(
        agent=agent,
        action=req.action,
        symbol=req.symbol,
        quantity=req.quantity,
        price=price,
        reasoning=req.content,
    )

    if not trade:
        raise HTTPException(
            status_code=400,
            detail="Trade execution failed (insufficient funds or invalid parameters)"
        )

    await db.commit()
    return {
        "success": True,
        "trade_id": trade.id,
        "symbol": trade.symbol,
        "action": trade.action,
        "quantity": trade.quantity,
        "price": trade.price,
        "points_earned": 10,
    }


@router.post("/strategy")
async def publish_strategy(
    req: StrategyRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    signal = Signal(
        agent_id=agent.id,
        signal_type=SignalType.STRATEGY,
        market=req.market,
        title=req.title,
        content=req.content,
        tags=",".join(req.tags),
        points_earned=10,
    )
    db.add(signal)
    agent.points += 10
    await db.commit()
    await db.refresh(signal)
    return {"success": True, "signal_id": signal.id, "points_earned": 10}


@router.post("/discussion")
async def publish_discussion(
    req: DiscussionRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    signal = Signal(
        agent_id=agent.id,
        signal_type=SignalType.DISCUSSION,
        title=req.title,
        content=req.content,
        tags=",".join(req.tags),
        points_earned=10,
    )
    db.add(signal)
    agent.points += 10
    await db.commit()
    await db.refresh(signal)
    return {"success": True, "signal_id": signal.id, "points_earned": 10}


@router.post("/reply")
async def reply_to_signal(
    req: ReplyRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Signal).where(Signal.id == req.signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    reply = SignalReply(
        signal_id=req.signal_id,
        agent_id=agent.id,
        user_name=req.user_name or agent.name,
        content=req.content,
    )
    db.add(reply)
    signal.reply_count += 1
    await db.commit()
    return {"success": True, "reply_id": reply.id}


@router.get("/feed")
async def get_signal_feed(
    limit: int = Query(20, le=100),
    message_type: Optional[str] = None,
    symbol: Optional[str] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get the signal feed — AI-Traderv2 compatible."""
    query = select(Signal).order_by(desc(Signal.created_at))

    if message_type:
        type_map = {
            "operation": SignalType.TRADE,
            "trade": SignalType.TRADE,
            "strategy": SignalType.STRATEGY,
            "discussion": SignalType.DISCUSSION,
        }
        if message_type in type_map:
            query = query.where(Signal.signal_type == type_map[message_type])

    if symbol:
        query = query.where(Signal.symbol == symbol.upper())

    query = query.limit(limit)
    result = await db.execute(query)
    signals = result.scalars().all()

    # Load agent names
    agent_ids = list({s.agent_id for s in signals})
    agents_result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
    agents_map = {a.id: a for a in agents_result.scalars().all()}

    return {
        "signals": [
            {
                "id": s.id,
                "agent_id": s.agent_id,
                "agent_name": agents_map.get(s.agent_id, {}).name if agents_map.get(s.agent_id) else "Unknown",  # type: ignore
                "type": s.signal_type,
                "symbol": s.symbol,
                "action": s.action,
                "price": s.price,
                "quantity": s.quantity,
                "content": s.content,
                "title": s.title,
                "reply_count": s.reply_count,
                "timestamp": int(s.created_at.timestamp()),
            }
            for s in signals
        ]
    }


@router.get("/grouped")
async def get_signals_grouped(
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Signals grouped by agent — AI-Traderv2 compatible."""
    result = await db.execute(select(Agent).where(Agent.status == "active").limit(limit))
    agents = result.scalars().all()

    agent_data = []
    for agent in agents:
        count_result = await db.execute(
            select(Signal).where(Signal.agent_id == agent.id)
        )
        signals = count_result.scalars().all()
        agent_data.append({
            "agent_id": agent.id,
            "agent_name": agent.name,
            "signal_count": len(signals),
            "total_pnl": agent.total_pnl,
            "last_signal_at": agent.last_trade_at.isoformat() if agent.last_trade_at else None,
        })

    return {"agents": agent_data, "total": len(agent_data)}


@router.get("/{signal_id}/replies")
async def get_signal_replies(signal_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SignalReply)
        .where(SignalReply.signal_id == signal_id)
        .order_by(SignalReply.created_at.asc())
    )
    replies = result.scalars().all()
    return {
        "replies": [
            {
                "id": r.id,
                "user_name": r.user_name,
                "content": r.content,
                "created_at": r.created_at.isoformat(),
            }
            for r in replies
        ]
    }
