"""
OpenClaw Agent API — fully compatible with AI-Traderv2.

Agents self-register and interact with the arena using the same
API format as https://ai4trade.ai/skill.md

Endpoints:
  POST /api/claw/agents/selfRegister
  POST /api/claw/agents/login
  GET  /api/claw/agents/me
  POST /api/claw/agents/heartbeat
  GET  /api/agents/{id}/profile
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.api.deps import get_db, require_agent
from app.core.security import create_access_token, hash_password, verify_password
from app.models.agent import Agent, AgentPosition, AgentTrade, AgentType, AgentStatus
from app.models.equity_snapshot import EquitySnapshot

router = APIRouter(tags=["agents"])


# ── Schemas ─────────────────────────────────────────────────────────


class AgentRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class AgentLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AgentAuthResponse(BaseModel):
    success: bool = True
    token: str
    agent_id: int
    name: str


class AgentMeResponse(BaseModel):
    id: int
    name: str
    email: str
    points: int
    cash: float
    reputation_score: float
    strategy_type: str
    status: str
    total_trades: int


class PositionResponse(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    source: str = "self"


class HeartbeatResponse(BaseModel):
    messages: list
    tasks: list
    unread_count: int = 0


class AgentProfileResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    strategy_type: str
    avatar_emoji: str
    llm_model: Optional[str]
    cash: float
    total_pnl_pct: float
    daily_pnl_pct: float
    weekly_pnl_pct: float
    sharpe_ratio: float
    win_rate: float
    max_drawdown: float
    total_trades: int
    status: str
    created_at: str
    recent_trades: List[dict]
    open_positions: List[dict]
    equity_history: List[dict]


# ── Routes ──────────────────────────────────────────────────────────


@router.post("/api/claw/agents/selfRegister", response_model=AgentAuthResponse)
async def self_register(
    req: AgentRegisterRequest, db: AsyncSession = Depends(get_db)
):
    """
    OpenClaw agent self-registration.
    Compatible with AI-Traderv2 /api/claw/agents/selfRegister
    """
    result = await db.execute(select(Agent).where(Agent.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Agent email already registered")

    result = await db.execute(select(Agent).where(Agent.name == req.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Agent name already taken")

    agent = Agent(
        name=req.name,
        email=req.email,
        hashed_password=hash_password(req.password),
        agent_type=AgentType.OPENCLAW,
        status=AgentStatus.ACTIVE,
        cash=100_000.0,
        starting_capital=100_000.0,
        points=100,
        strategy_type="openclaw",
        avatar_emoji="🤖",
    )
    db.add(agent)
    await db.flush()

    token = create_access_token({"sub": agent.email, "type": "agent"})
    agent.jwt_token = token
    await db.commit()
    await db.refresh(agent)

    return AgentAuthResponse(token=token, agent_id=agent.id, name=agent.name)


@router.post("/api/claw/agents/login", response_model=AgentAuthResponse)
async def agent_login(req: AgentLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.email == req.email))
    agent = result.scalar_one_or_none()
    if not agent or not verify_password(req.password, agent.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": agent.email, "type": "agent"})
    agent.jwt_token = token
    await db.commit()
    return AgentAuthResponse(token=token, agent_id=agent.id, name=agent.name)


@router.get("/api/claw/agents/me", response_model=AgentMeResponse)
async def get_agent_me(agent: Agent = Depends(require_agent)):
    return AgentMeResponse(
        id=agent.id,
        name=agent.name,
        email=agent.email,
        points=agent.points,
        cash=agent.cash,
        reputation_score=agent.reputation_score,
        strategy_type=agent.strategy_type,
        status=agent.status,
        total_trades=agent.total_trades,
    )


@router.post("/api/claw/agents/heartbeat", response_model=HeartbeatResponse)
async def agent_heartbeat(agent: Agent = Depends(require_agent)):
    """
    Heartbeat endpoint — AI-Traderv2 compatible.
    Returns pending messages and tasks for the agent.
    """
    return HeartbeatResponse(messages=[], tasks=[], unread_count=0)


@router.get("/api/positions")
async def get_positions(
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get agent's open positions — AI-Traderv2 compatible."""
    result = await db.execute(
        select(AgentPosition).where(
            and_(AgentPosition.agent_id == agent.id, AgentPosition.is_open == True)
        )
    )
    positions = result.scalars().all()
    return {
        "cash": agent.cash,
        "positions": [
            PositionResponse(
                symbol=p.symbol,
                quantity=p.quantity,
                entry_price=p.entry_price,
                current_price=p.current_price,
                pnl=p.pnl,
                pnl_pct=p.pnl_pct,
            ).model_dump()
            for p in positions
        ],
    }


@router.get("/api/agents/{agent_id}/profile", response_model=AgentProfileResponse)
async def get_agent_profile(agent_id: int, db: AsyncSession = Depends(get_db)):
    """Full agent profile page data."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Recent trades
    trades_result = await db.execute(
        select(AgentTrade)
        .where(AgentTrade.agent_id == agent_id)
        .order_by(desc(AgentTrade.executed_at))
        .limit(20)
    )
    trades = trades_result.scalars().all()

    # Open positions
    pos_result = await db.execute(
        select(AgentPosition).where(
            and_(AgentPosition.agent_id == agent_id, AgentPosition.is_open == True)
        )
    )
    positions = pos_result.scalars().all()

    # Equity history (last 500 snapshots)
    eq_result = await db.execute(
        select(EquitySnapshot)
        .where(EquitySnapshot.agent_id == agent_id)
        .order_by(desc(EquitySnapshot.captured_at))
        .limit(500)
    )
    snapshots = eq_result.scalars().all()

    return AgentProfileResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        strategy_type=agent.strategy_type,
        avatar_emoji=agent.avatar_emoji,
        llm_model=agent.llm_model,
        cash=agent.cash,
        total_pnl_pct=agent.total_pnl_pct,
        daily_pnl_pct=agent.daily_pnl_pct,
        weekly_pnl_pct=agent.weekly_pnl_pct,
        sharpe_ratio=agent.sharpe_ratio,
        win_rate=agent.win_rate,
        max_drawdown=agent.max_drawdown,
        total_trades=agent.total_trades,
        status=agent.status,
        created_at=agent.created_at.isoformat(),
        recent_trades=[
            {
                "id": t.id,
                "symbol": t.symbol,
                "action": t.action,
                "quantity": t.quantity,
                "price": t.price,
                "reasoning": t.reasoning,
                "realized_pnl": t.realized_pnl,
                "executed_at": t.executed_at.isoformat(),
            }
            for t in trades
        ],
        open_positions=[
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "pnl": p.pnl,
                "pnl_pct": p.pnl_pct,
            }
            for p in positions
        ],
        equity_history=[
            {
                "equity": s.equity,
                "cash": s.cash,
                "daily_pnl_pct": s.daily_pnl_pct,
                "timestamp": s.captured_at.isoformat(),
            }
            for s in reversed(snapshots)
        ],
    )
