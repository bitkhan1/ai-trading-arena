"""
Equity snapshot — time-series portfolio value for each agent.
Used to render equity curves and compute Sharpe ratio / drawdown.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EquitySnapshot(Base):
    """
    Taken every 60 seconds (after each trade cycle).
    Stores the total portfolio value (cash + open position market value).
    """
    __tablename__ = "equity_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    positions_value: Mapped[float] = mapped_column(Float, default=0.0)
    daily_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    agent: Mapped["Agent"] = relationship("Agent", back_populates="equity_snapshots")  # type: ignore
