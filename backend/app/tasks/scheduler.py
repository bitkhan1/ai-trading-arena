"""
APScheduler background jobs.

Jobs:
  1. agent_trade_cycle     — runs every 60s, executes strategies for all active agents
  2. leaderboard_update    — runs every 10s, pushes leaderboard via WebSocket
  3. market_close_settle   — runs at 21:05 UTC (16:05 ET), settles daily contest
  4. market_open_reset     — runs at 14:30 UTC (9:30 ET), resets daily P&L + opens new contest
"""
import asyncio
import logging
from datetime import datetime, timezone

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.agent import Agent, AgentPosition
from app.services.agent_runner import STRATEGY_MAP
from app.services.leaderboard import compute_agent_stats, push_leaderboard_update
from app.services.paper_trading import PaperTradingEngine
from app.services.settlement import (
    get_or_create_daily_contest,
    reset_daily_pnl,
    settle_daily_contest,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=pytz.UTC)


async def agent_trade_cycle():
    """
    Execute one trading cycle for all active agents.
    Each agent runs its strategy and may place a trade.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Agent).where(Agent.status == "active")
        )
        agents = result.scalars().all()

        for agent in agents:
            try:
                strategy_fn = STRATEGY_MAP.get(agent.strategy_type)
                if not strategy_fn:
                    continue

                # Get current open position symbols
                pos_result = await db.execute(
                    select(AgentPosition).where(
                        and_(AgentPosition.agent_id == agent.id, AgentPosition.is_open == True)
                    )
                )
                open_positions = pos_result.scalars().all()
                current_positions = [p.symbol for p in open_positions]

                # Recompute portfolio value for sizing
                pos_value = sum(p.quantity * p.current_price for p in open_positions)
                portfolio_value = agent.cash + pos_value

                # Run strategy
                action, symbol, quantity, reasoning = await strategy_fn(
                    agent.cash, portfolio_value, current_positions
                )

                if action != "hold" and symbol and quantity > 0:
                    engine = PaperTradingEngine(db)
                    await engine.execute_trade(
                        agent=agent,
                        action=action,
                        symbol=symbol,
                        quantity=quantity,
                        reasoning=reasoning,
                    )

                # Update position prices + capture snapshot
                engine = PaperTradingEngine(db)
                await engine.update_positions_prices(agent)

                # Compute daily P&L for snapshot
                pos_result2 = await db.execute(
                    select(AgentPosition).where(
                        and_(AgentPosition.agent_id == agent.id, AgentPosition.is_open == True)
                    )
                )
                open_pos2 = pos_result2.scalars().all()
                pos_val2 = sum(p.quantity * p.current_price for p in open_pos2)
                equity = agent.cash + pos_val2
                daily_pnl_pct = (equity / agent.starting_capital - 1) * 100
                agent.daily_pnl_pct = round(daily_pnl_pct, 4)
                agent.total_pnl_pct = round((equity / agent.starting_capital - 1) * 100, 4)

                await engine.capture_equity_snapshot(agent, daily_pnl_pct=daily_pnl_pct)

            except Exception as e:
                logger.error(f"Error in trade cycle for agent {agent.name}: {e}", exc_info=True)

        await db.commit()


async def leaderboard_update_job():
    """Push leaderboard update to all WebSocket subscribers."""
    try:
        async with AsyncSessionLocal() as db:
            await push_leaderboard_update(db)
    except Exception as e:
        logger.error(f"Leaderboard update error: {e}", exc_info=True)


async def market_open_job():
    """Reset daily P&L and create today's contest."""
    logger.info("Market open: resetting daily P&L and opening contest")
    async with AsyncSessionLocal() as db:
        await reset_daily_pnl(db)
        await get_or_create_daily_contest(db)
        await db.commit()


async def market_close_job():
    """Settle today's daily contest."""
    logger.info("Market close: settling daily contest")
    async with AsyncSessionLocal() as db:
        result = await settle_daily_contest(db)
        if result:
            logger.info(
                f"Contest settled: winner={result.winning_agent_name}, "
                f"pot={result.total_pot} tokens"
            )


def start_scheduler():
    """Register all jobs and start the scheduler."""
    # Agent trading — every 60 seconds
    scheduler.add_job(
        agent_trade_cycle,
        trigger=IntervalTrigger(seconds=settings.AGENT_TRADE_INTERVAL, start_date=__import__("datetime").datetime.now() + __import__("datetime").timedelta(seconds=30)),
        id="agent_trade_cycle",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Leaderboard WebSocket push — every 10 seconds
    scheduler.add_job(
        leaderboard_update_job,
        trigger=IntervalTrigger(seconds=settings.LEADERBOARD_UPDATE_INTERVAL, start_date=__import__("datetime").datetime.now() + __import__("datetime").timedelta(seconds=30)),
        id="leaderboard_update",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Market open — 9:30 AM ET (14:30 UTC on standard days)
    scheduler.add_job(
        market_open_job,
        trigger=CronTrigger(hour=14, minute=30, day_of_week="mon-fri"),
        id="market_open",
        replace_existing=True,
    )

    # Market close — 4:05 PM ET (21:05 UTC)
    scheduler.add_job(
        market_close_job,
        trigger=CronTrigger(hour=21, minute=5, day_of_week="mon-fri"),
        id="market_close_settle",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("APScheduler started with all jobs registered")
