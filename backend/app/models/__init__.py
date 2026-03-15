"""
Import all models here so Alembic can discover them via autogenerate.
"""
from app.models.user import User  # noqa: F401
from app.models.agent import Agent, AgentPosition, AgentTrade  # noqa: F401
from app.models.betting import Bet, DailyContest, DailyResult  # noqa: F401
from app.models.signal import Signal, SignalReply  # noqa: F401
from app.models.equity_snapshot import EquitySnapshot  # noqa: F401
