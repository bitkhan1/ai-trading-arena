"""
Signal model — AI-Traderv2 compatible trading signals.
Agents publish signals; users can view the strategy reasoning.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base


class SignalType(str, enum.Enum):
    TRADE = "trade"            # Executed trade (buy/sell)
    POSITION = "position"      # Current position update
    STRATEGY = "strategy"      # Strategy analysis
    DISCUSSION = "discussion"  # Discussion post


class Signal(Base):
    """
    A published signal from an agent.
    This is the AI-Traderv2-compatible signal that also powers
    the live trade ticker on the Arena Watch page.
    """
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    signal_type: Mapped[SignalType] = mapped_column(
        SAEnum(SignalType), nullable=False, default=SignalType.TRADE, index=True
    )

    # Trade fields (for TRADE type)
    market: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "us-stock"
    symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    action: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # buy/sell
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    realized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Content fields (for STRATEGY / DISCUSSION)
    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # comma-sep

    # Points earned from this signal
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    adoption_count: Mapped[int] = mapped_column(Integer, default=0)

    reply_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="signals")  # type: ignore
    replies: Mapped[list["SignalReply"]] = relationship(
        "SignalReply", back_populates="signal", cascade="all, delete-orphan"
    )


class SignalReply(Base):
    __tablename__ = "signal_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("agents.id"), nullable=True
    )
    user_name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    signal: Mapped["Signal"] = relationship("Signal", back_populates="replies")
