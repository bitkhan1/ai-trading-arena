"""
Daily contest settlement service.

Settlement process (runs at market close ~16:05 ET):
  1. Find today's active DailyContest
  2. Determine winning agent = highest daily_pnl_pct
  3. Calculate payouts: 95% of pot split proportionally to winning bettors
  4. Update each user's token_balance
  5. Create DailyResult record
  6. Mark contest as SETTLED
  7. Create next day's contest
"""
import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.core.config import settings
from app.models.betting import Bet, BetStatus, ContestStatus, DailyContest, DailyResult
from app.models.agent import Agent
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_or_create_daily_contest(db: AsyncSession) -> DailyContest:
    """Get today's contest or create it if it doesn't exist."""
    today = date.today()
    result = await db.execute(
        select(DailyContest).where(DailyContest.contest_date == today)
    )
    contest = result.scalar_one_or_none()

    if not contest:
        contest = DailyContest(
            contest_date=today,
            status="open",
            total_pot=0,
        )
        db.add(contest)
        await db.flush()
        logger.info(f"Created new daily contest for {today}")

    return contest


async def settle_daily_contest(db: AsyncSession) -> Optional[DailyResult]:
    """
    Settle today's daily contest.
    Called by the scheduler at market close.
    Returns the DailyResult or None if no contest/no bets.
    """
    today = date.today()
    result = await db.execute(
        select(DailyContest).where(
            and_(
                DailyContest.contest_date == today,
                DailyContest.status.in_(["open", "locked"]),
            )
        )
    )
    contest = result.scalar_one_or_none()

    if not contest:
        logger.info("No active contest to settle today")
        return None

    # Mark as settling
    contest.status = "settling"

    # Load all bets for today
    bets_result = await db.execute(
        select(Bet).where(
            and_(Bet.contest_id == contest.id, Bet.status == "PENDING")
        )
    )
    bets = bets_result.scalars().all()

    if not bets:
        contest.status = "cancelled"
        await db.commit()
        logger.info("Contest cancelled — no bets placed")
        return None

    # Find winning agent (highest daily P&L %)
    agents_result = await db.execute(
        select(Agent).where(Agent.status == "active")
    )
    agents = agents_result.scalars().all()

    if not agents:
        contest.status = "cancelled"
        await db.commit()
        return None

    winning_agent = max(agents, key=lambda a: a.daily_pnl_pct)

    # Compute pot
    total_pot = sum(b.amount for b in bets)
    platform_fee = int(total_pot * settings.PLATFORM_FEE_RATE)
    winner_pot = total_pot - platform_fee

    contest.total_pot = total_pot
    contest.platform_fee = platform_fee
    contest.winner_pot = winner_pot

    # Separate winning vs losing bets
    winning_bets = [b for b in bets if b.agent_id == winning_agent.id]
    losing_bets = [b for b in bets if b.agent_id != winning_agent.id]
    winning_wagers_total = sum(b.amount for b in winning_bets)

    # Pay out winners
    for bet in winning_bets:
        if winning_wagers_total > 0:
            share = bet.amount / winning_wagers_total
            payout = int(winner_pot * share)
        else:
            payout = 0

        bet.payout = payout
        bet.status = "WON"
        bet.settled_at = datetime.now(timezone.utc)

        # Credit user
        user_result = await db.execute(
            select(User).where(User.id == bet.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            user.token_balance += payout
            user.total_tokens_won += payout

    # Mark losers
    for bet in losing_bets:
        bet.payout = 0
        bet.status = "LOST"
        bet.settled_at = datetime.now(timezone.utc)

    # Create result record
    daily_result = DailyResult(
        contest_id=contest.id,
        winning_agent_id=winning_agent.id,
        winning_agent_name=winning_agent.name,
        winning_pnl_pct=winning_agent.daily_pnl_pct,
        total_bettors=len(bets),
        winning_bettors=len(winning_bets),
        total_pot=total_pot,
        winner_pot=winner_pot,
        platform_fee=platform_fee,
    )
    db.add(daily_result)

    contest.status = "settled"
    contest.settled_at = datetime.now(timezone.utc)

    await db.commit()

    logger.info(
        f"Contest settled: winner={winning_agent.name} "
        f"(+{winning_agent.daily_pnl_pct:.2f}%), "
        f"pot={total_pot}, payouts to {len(winning_bets)} winners"
    )

    # Immediately open next contest for tomorrow (handled by scheduler)
    return daily_result


async def reset_daily_pnl(db: AsyncSession):
    """
    Reset daily P&L tracking for all agents at market open.
    Called by scheduler at 9:30 ET.
    """
    agents_result = await db.execute(select(Agent))
    agents = agents_result.scalars().all()
    for agent in agents:
        agent.daily_pnl = 0.0
        agent.daily_pnl_pct = 0.0
    await db.commit()
    logger.info(f"Daily P&L reset for {len(agents)} agents")
