"""
Agent models — AI trading agents that compete in the arena.

Fully OpenClaw-compatible: same registration flow as AI-Traderv2.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, Integer, String, Text,
    ForeignKey, Numeric, BigInteger, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base


class AgentType(str, enum.Enum):
    BUILTIN = "builtin"      # Pre-loaded arena agents
    OPENCLAW = "openclaw"    # External OpenClaw agents


class AgentStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class TradeAction(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    SHORT = "short"
    COVER = "cover"


class Agent(Base):
    """
    An AI trading agent.
    Builtin agents are seeded; external OpenClaw agents self-register
    via POST /api/claw/agents/selfRegister (same as AI-Traderv2).
    """
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Agent metadata
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strategy_type: Mapped[str] = mapped_column(String(100), default="unknown")
    avatar_emoji: Mapped[str] = mapped_column(String(10), default="🤖")
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    agent_type: Mapped[str] = mapped_column(
        String(20), server_default="builtin"
    )
    status: Mapped[str] = mapped_column(
        String(20), server_default="active"
    )

    # Paper trading capital
    cash: Mapped[float] = mapped_column(Float, default=100_000.0, nullable=False)
    starting_capital: Mapped[float] = mapped_column(Float, default=100_000.0, nullable=False)

    # Points (AI-Traderv2 compatible)
    points: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    reputation_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Performance stats (denormalized for fast leaderboard)
    total_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    total_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    daily_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    daily_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    weekly_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)

    # Auth token (for API auth, AI-Traderv2 style)
    jwt_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_trade_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    positions: Mapped[list["AgentPosition"]] = relationship(
        "AgentPosition", back_populates="agent", cascade="all, delete-orphan"
    )
    trades: Mapped[list["AgentTrade"]] = relationship(
        "AgentTrade", back_populates="agent", cascade="all, delete-orphan"
    )
    equity_snapshots: Mapped[list["EquitySnapshot"]] = relationship(
        "EquitySnapshot", back_populates="agent", cascade="all, delete-orphan"
    )
    signals: Mapped[list["Signal"]] = relationship(
        "Signal", back_populates="agent", cascade="all, delete-orphan"
    )
    bets: Mapped[list["Bet"]] = relationship("Bet", back_populates="agent")

    @property
    def portfolio_value(self) -> float:
        """Cash + sum of open position market values."""
        pos_value = sum(
            p.quantity * p.current_price for p in self.positions if p.is_open
        )
        return self.cash + pos_value

    def __repr__(self) -> str:
        return f"<Agent {self.name} cash={self.cash:.2f}>"


class AgentPosition(Base):
    """Open or closed position held by an agent."""
    __tablename__ = "agent_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    agent: Mapped["Agent"] = relationship("Agent", back_populates="positions")


class AgentTrade(Base):
    """
    A single paper trade execution.
    Mirrors the AI-Traderv2 signal format so the signal feed is compatible.
    """
    __tablename__ = "agent_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # buy/sell/short/cover
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    slippage_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False)

    # AI reasoning — shown in the live trade ticker
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Realized P&L (for sell/cover trades)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    agent: Mapped["Agent"] = relationship("Agent", back_populates="trades")

    def __repr__(self) -> str:
        return f"<Trade {self.action} {self.quantity} {self.symbol} @ {self.price}>"
