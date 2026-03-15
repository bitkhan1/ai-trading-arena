"""
Betting models — Arena Token daily contest system.

Rules:
  - Users bet Arena Tokens on one agent per day
  - Daily winner = agent with highest Daily P&L%
  - Winners split 95% of the pot proportionally
  - 5% platform fee
  - No real money involved — tokens only
"""
from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Float, Integer, String,
    ForeignKey, BigInteger, Enum as SAEnum, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base


class BetStatus(str, enum.Enum):
    PENDING = "pending"        # Bet placed, contest still running
    WON = "won"                # Bet placed on daily winner
    LOST = "lost"              # Bet placed on non-winner
    REFUNDED = "refunded"      # Contest cancelled / no valid winner
    SETTLED = "settled"        # Fully processed and payout applied


class ContestStatus(str, enum.Enum):
    OPEN = "open"              # Accepting bets
    LOCKED = "locked"          # Market open, no more bets
    SETTLING = "settling"      # Settlement in progress
    SETTLED = "settled"        # All payouts done
    CANCELLED = "cancelled"    # Cancelled (e.g., market holiday)


class Bet(Base):
    """A single user bet on a trading agent for a daily contest."""
    __tablename__ = "bets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contest_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("daily_contests.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Token amounts
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # tokens bet
    payout: Mapped[int] = mapped_column(BigInteger, default=0)       # tokens received

    status: Mapped[str] = mapped_column(
        sa.String(30), server_default='PENDING', nullable=False
    )

    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    settled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="bets")  # type: ignore
    agent: Mapped["Agent"] = relationship("Agent", back_populates="bets")  # type: ignore
    contest: Mapped["DailyContest"] = relationship("DailyContest", back_populates="bets")

    def __repr__(self) -> str:
        return f"<Bet user={self.user_id} agent={self.agent_id} amount={self.amount}>"


class DailyContest(Base):
    """
    One contest per trading day.
    Created at market open (or startup), settled at market close.
    """
    __tablename__ = "daily_contests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contest_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        sa.String(30), server_default='open', nullable=False
    )

    # Total tokens bet across all participants
    total_pot: Mapped[int] = mapped_column(BigInteger, default=0)
    platform_fee: Mapped[int] = mapped_column(BigInteger, default=0)
    winner_pot: Mapped[int] = mapped_column(BigInteger, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    settled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    bets: Mapped[list["Bet"]] = relationship("Bet", back_populates="contest")
    result: Mapped[Optional["DailyResult"]] = relationship(
        "DailyResult", back_populates="contest", uselist=False
    )


class DailyResult(Base):
    """
    Stores the winner and final stats after each daily contest settles.
    Used for historical payout log display.
    """
    __tablename__ = "daily_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contest_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("daily_contests.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True
    )
    winning_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("agents.id"), nullable=True
    )
    winning_agent_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Winner's P&L% on that day
    winning_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)

    # Summary
    total_bettors: Mapped[int] = mapped_column(Integer, default=0)
    winning_bettors: Mapped[int] = mapped_column(Integer, default=0)
    total_pot: Mapped[int] = mapped_column(BigInteger, default=0)
    winner_pot: Mapped[int] = mapped_column(BigInteger, default=0)
    platform_fee: Mapped[int] = mapped_column(BigInteger, default=0)

    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    contest: Mapped["DailyContest"] = relationship("DailyContest", back_populates="result")
    winning_agent: Mapped[Optional["Agent"]] = relationship("Agent")  # type: ignore
