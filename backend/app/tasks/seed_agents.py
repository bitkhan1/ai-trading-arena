"""
Seed script — creates the 8 built-in arena agents on first startup.

Run with: python -m app.tasks.seed_agents

Also creates the first daily contest and an initial admin user.
"""
import asyncio
import logging
import sys
from datetime import date

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password, create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agent import Agent
from app.models.betting import DailyContest
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BUILTIN_AGENTS = [
    {
        "name": "Momentum Trader",
        "email": "momentum@arena.internal",
        "description": (
            "Chases price breakouts using RSI and moving average crossovers. "
            "Powered by Claude Sonnet — generates natural language reasoning for every trade."
        ),
        "strategy_type": "momentum",
        "avatar_emoji": "🚀",
        "llm_model": "claude-3-5-sonnet",
    },
    {
        "name": "Mean-Reversion Master",
        "email": "meanreversion@arena.internal",
        "description": (
            "Fades extremes back to the mean using Bollinger Bands and RSI. "
            "Powered by GPT-4o — thrives in choppy, range-bound markets."
        ),
        "strategy_type": "mean_reversion",
        "avatar_emoji": "🔄",
        "llm_model": "gpt-4o",
    },
    {
        "name": "Sentiment Slayer",
        "email": "sentiment@arena.internal",
        "description": (
            "Trades on news sentiment and social signals. "
            "Uses recent price momentum as sentiment proxy when news APIs are unavailable."
        ),
        "strategy_type": "sentiment",
        "avatar_emoji": "📰",
        "llm_model": None,
    },
    {
        "name": "Volatility Hunter",
        "email": "volatility@arena.internal",
        "description": (
            "Profits from volatility expansion by entering when ATR spikes. "
            "Exits when volatility contracts. Great for trending, volatile markets."
        ),
        "strategy_type": "volatility",
        "avatar_emoji": "⚡",
        "llm_model": None,
    },
    {
        "name": "Trend Follower",
        "email": "trend@arena.internal",
        "description": (
            "Classic moving average crossover strategy. "
            "Golden cross = buy, death cross = sell. Systematic and rules-based."
        ),
        "strategy_type": "trend_following",
        "avatar_emoji": "📈",
        "llm_model": None,
    },
    {
        "name": "Value Investor",
        "email": "value@arena.internal",
        "description": (
            "Buys quality NASDAQ-100 stocks on significant pullbacks from 52-week highs. "
            "Seeks margin of safety, takes profits when value gap closes."
        ),
        "strategy_type": "value",
        "avatar_emoji": "💎",
        "llm_model": None,
    },
    {
        "name": "ML Ensemble",
        "email": "ensemble@arena.internal",
        "description": (
            "Combines RSI, trend, and volatility signals via a voting mechanism. "
            "Requires 2/3 models to agree before trading — reduces false signals."
        ),
        "strategy_type": "ml_ensemble",
        "avatar_emoji": "🤖",
        "llm_model": None,
    },
    {
        "name": "Random Baseline",
        "email": "random@arena.internal",
        "description": (
            "Makes completely random buy/sell decisions. "
            "Included as a scientific control — if you can't beat Random, that's humbling."
        ),
        "strategy_type": "random",
        "avatar_emoji": "🎲",
        "llm_model": None,
    },
]


async def seed():
    async with AsyncSessionLocal() as db:
        # ── Create agents ──────────────────────────────────────
        for agent_data in BUILTIN_AGENTS:
            result = await db.execute(
                select(Agent).where(Agent.email == agent_data["email"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(f"Agent '{agent_data['name']}' already exists — skipping")
                continue

            token_data = {"sub": agent_data["email"], "type": "agent"}
            jwt_token = create_access_token(token_data)

            agent = Agent(
                name=agent_data["name"],
                email=agent_data["email"],
                hashed_password=hash_password("arena-agent-password"),
                description=agent_data["description"],
                strategy_type=agent_data["strategy_type"],
                avatar_emoji=agent_data["avatar_emoji"],
                llm_model=agent_data["llm_model"],
                agent_type="builtin",
                status="active",
                cash=settings.AGENT_STARTING_CAPITAL,
                starting_capital=settings.AGENT_STARTING_CAPITAL,
                points=100,
                jwt_token=jwt_token,
            )
            db.add(agent)
            logger.info(f"Created agent: {agent_data['name']}")

        # ── Create admin user ──────────────────────────────────
        admin_result = await db.execute(
            select(User).where(User.email == settings.ADMIN_EMAIL)
        )
        admin = admin_result.scalar_one_or_none()
        if not admin:
            admin = User(
                email=settings.ADMIN_EMAIL,
                username="admin",
                display_name="Arena Admin",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                token_balance=settings.SIGNUP_TOKEN_BONUS,
                is_admin=True,
                is_active=True,
            )
            db.add(admin)
            logger.info(f"Created admin user: {settings.ADMIN_EMAIL}")

        # ── Create today's contest ─────────────────────────────
        today = date.today()
        contest_result = await db.execute(
            select(DailyContest).where(DailyContest.contest_date == today)
        )
        contest = contest_result.scalar_one_or_none()
        if not contest:
            contest = DailyContest(
                contest_date=today,
                status="open",
                total_pot=0,
            )
            db.add(contest)
            logger.info(f"Created daily contest for {today}")

        await db.commit()
        logger.info("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
