"""
Betting API — Arena Token daily contest system.

All amounts are fake Arena Tokens — no real money.

Endpoints:
  GET  /api/betting/daily-contest        — Today's contest info
  POST /api/betting/place                — Place a bet
  GET  /api/betting/my-bets              — User's bet history
  GET  /api/betting/history              — Past contest results
  POST /api/betting/admin/settle         — Admin: force settle (testing)
"""
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.api.deps import get_db, require_user, require_admin
from app.models.agent import Agent
from app.models.betting import Bet, BetStatus, ContestStatus, DailyContest, DailyResult
from app.models.user import User
from app.services.settlement import get_or_create_daily_contest, settle_daily_contest

router = APIRouter(prefix="/api/betting", tags=["betting"])


# ── Schemas ─────────────────────────────────────────────────────────


class PlaceBetRequest(BaseModel):
    agent_id: int
    amount: int  # Arena Tokens (min 1, max user.token_balance)


class BetResponse(BaseModel):
    id: int
    agent_id: int
    agent_name: str
    contest_date: str
    amount: int
    payout: int
    status: str
    placed_at: str
    settled_at: Optional[str] = None


class ContestResponse(BaseModel):
    contest_date: str
    status: str
    total_pot: int
    total_bettors: int
    user_bet: Optional[BetResponse] = None
    agents: List[dict]
    time_until_close: Optional[str] = None


# ── Routes ──────────────────────────────────────────────────────────


@router.get("/daily-contest", response_model=ContestResponse)
async def get_daily_contest(
    user: Optional[User] = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get today's contest info including user's current bet."""
    contest = await get_or_create_daily_contest(db)
    await db.commit()

    # Count bettors
    bets_result = await db.execute(
        select(Bet).where(Bet.contest_id == contest.id)
    )
    bets = bets_result.scalars().all()

    # Get user's bet
    user_bet = None
    if user:
        for bet in bets:
            if bet.user_id == user.id:
                agent_result = await db.execute(
                    select(Agent).where(Agent.id == bet.agent_id)
                )
                bet_agent = agent_result.scalar_one_or_none()
                user_bet = BetResponse(
                    id=bet.id,
                    agent_id=bet.agent_id,
                    agent_name=bet_agent.name if bet_agent else "Unknown",
                    contest_date=contest.contest_date.isoformat(),
                    amount=bet.amount,
                    payout=bet.payout,
                    status=bet.status,
                    placed_at=bet.placed_at.isoformat(),
                    settled_at=bet.settled_at.isoformat() if bet.settled_at else None,
                )
                break

    # Get all active agents with current daily P&L
    agents_result = await db.execute(
        select(Agent).where(Agent.status == "active")
    )
    agents = agents_result.scalars().all()

    # Sum bets per agent
    bets_by_agent = {}
    for bet in bets:
        bets_by_agent[bet.agent_id] = bets_by_agent.get(bet.agent_id, 0) + bet.amount

    agent_list = [
        {
            "id": a.id,
            "name": a.name,
            "avatar_emoji": a.avatar_emoji,
            "strategy_type": a.strategy_type,
            "daily_pnl_pct": a.daily_pnl_pct,
            "total_bets": bets_by_agent.get(a.id, 0),
        }
        for a in sorted(agents, key=lambda x: x.daily_pnl_pct, reverse=True)
    ]

    return ContestResponse(
        contest_date=contest.contest_date.isoformat(),
        status=contest.status,
        total_pot=contest.total_pot,
        total_bettors=len(bets),
        user_bet=user_bet,
        agents=agent_list,
    )


@router.post("/place")
async def place_bet(
    req: PlaceBetRequest,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Place a bet on an agent for today's contest."""
    # Validate amount
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Bet amount must be positive")
    if req.amount > user.token_balance:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient tokens. You have {user.token_balance}, tried to bet {req.amount}"
        )

    # Get today's contest
    contest = await get_or_create_daily_contest(db)
    if contest.status not in ("open", "locked"):
        raise HTTPException(
            status_code=400,
            detail=f"Contest is not open for betting (status: {contest.status})"
        )

    # Check agent exists
    agent_result = await db.execute(select(Agent).where(Agent.id == req.agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check user hasn't already bet today
    existing_result = await db.execute(
        select(Bet).where(
            and_(
                Bet.user_id == user.id,
                Bet.contest_id == contest.id,
                Bet.status == "PENDING",
            )
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already have an active bet for today. Cancel it first."
        )

    # Deduct tokens
    user.token_balance -= req.amount
    user.total_tokens_bet += req.amount

    # Create bet
    bet = Bet(
        user_id=user.id,
        agent_id=req.agent_id,
        contest_id=contest.id,
        amount=req.amount,
        status="PENDING",
    )
    db.add(bet)

    # Update contest pot
    contest.total_pot += req.amount

    await db.commit()
    await db.refresh(bet)

    return {
        "success": True,
        "bet_id": bet.id,
        "agent_name": agent.name,
        "amount": req.amount,
        "remaining_balance": user.token_balance,
        "message": f"Bet placed! {req.amount} tokens on {agent.name}",
    }


@router.get("/my-bets")
async def get_my_bets(
    limit: int = 50,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's full bet history."""
    result = await db.execute(
        select(Bet)
        .where(Bet.user_id == user.id)
        .order_by(desc(Bet.placed_at))
        .limit(limit)
    )
    bets = result.scalars().all()

    # Load agent names
    agent_ids = list({b.agent_id for b in bets})
    agents_result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
    agents_map = {a.id: a.name for a in agents_result.scalars().all()}

    return {
        "bets": [
            {
                "id": b.id,
                "agent_name": agents_map.get(b.agent_id, "Unknown"),
                "amount": b.amount,
                "payout": b.payout,
                "profit": b.payout - b.amount if b.status == "WON" else -b.amount if b.status == "LOST" else 0,
                "status": b.status,
                "placed_at": b.placed_at.isoformat(),
                "settled_at": b.settled_at.isoformat() if b.settled_at else None,
            }
            for b in bets
        ],
        "summary": {
            "total_bet": sum(b.amount for b in bets),
            "total_won": sum(b.payout for b in bets if b.status == "WON"),
            "total_lost": sum(b.amount for b in bets if b.status == "LOST"),
            "win_count": sum(1 for b in bets if b.status == "WON"),
            "loss_count": sum(1 for b in bets if b.status == "LOST"),
        },
    }


@router.get("/history")
async def get_contest_history(
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """Get past contest results."""
    result = await db.execute(
        select(DailyResult)
        .order_by(desc(DailyResult.settled_at))
        .limit(limit)
    )
    results = result.scalars().all()

    return {
        "results": [
            {
                "contest_date": r.contest.contest_date.isoformat() if r.contest else "Unknown",
                "winning_agent": r.winning_agent_name,
                "winning_pnl_pct": r.winning_pnl_pct,
                "total_pot": r.total_pot,
                "winner_pot": r.winner_pot,
                "platform_fee": r.platform_fee,
                "total_bettors": r.total_bettors,
                "winning_bettors": r.winning_bettors,
                "settled_at": r.settled_at.isoformat(),
            }
            for r in results
        ]
    }


@router.post("/admin/settle")
async def admin_settle(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin endpoint: force settle today's contest immediately."""
    result = await settle_daily_contest(db)
    if not result:
        return {"success": False, "message": "No active contest or no bets to settle"}
    return {
        "success": True,
        "winning_agent": result.winning_agent_name,
        "total_pot": result.total_pot,
        "winning_pnl_pct": result.winning_pnl_pct,
    }
