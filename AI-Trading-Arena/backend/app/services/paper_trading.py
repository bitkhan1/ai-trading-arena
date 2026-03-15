"""
Paper trading engine.

Handles:
  - Executing buy/sell orders with 0.1% slippage
  - Position management (open, update, close)
  - Portfolio value computation
  - P&L tracking
  - Equity snapshot capture
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.redis import publish, CHANNEL_TRADES
from app.models.agent import Agent, AgentPosition, AgentTrade
from app.models.equity_snapshot import EquitySnapshot
from app.models.signal import Signal, SignalType
from app.services.market_data import get_current_price

logger = logging.getLogger(__name__)

SLIPPAGE = settings.PAPER_TRADE_SLIPPAGE  # 0.001 = 0.1%


class PaperTradingEngine:
    """
    Executes paper trades for an agent.
    
    Usage:
        engine = PaperTradingEngine(db)
        result = await engine.execute_trade(agent, "BUY", "AAPL", 10, reasoning="...")
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_trade(
        self,
        agent: Agent,
        action: str,      # "buy" | "sell" | "short" | "cover"
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
        reasoning: Optional[str] = None,
    ) -> Optional[AgentTrade]:
        """
        Execute a paper trade with slippage simulation.
        Returns the created AgentTrade or None if trade failed.
        """
        action = action.lower()

        # Fetch current market price if not provided
        if price is None or price <= 0:
            price = await get_current_price(symbol)
            if not price:
                logger.warning(f"Could not get price for {symbol}, skipping trade")
                return None

        # Apply slippage
        if action in ("buy", "cover"):
            execution_price = price * (1 + SLIPPAGE)
        else:
            execution_price = price * (1 - SLIPPAGE)

        slippage_cost = abs(execution_price - price) * quantity
        total_cost = execution_price * quantity

        # ── BUY ────────────────────────────────────────────────────
        if action == "buy":
            if agent.cash < total_cost:
                logger.info(
                    f"Agent {agent.name} insufficient cash: need {total_cost:.2f}, "
                    f"have {agent.cash:.2f}"
                )
                return None

            agent.cash -= total_cost

            # Open or add to existing position
            pos = await self._get_open_position(agent.id, symbol)
            if pos:
                # Average in
                total_qty = pos.quantity + quantity
                pos.entry_price = (
                    (pos.entry_price * pos.quantity + execution_price * quantity) / total_qty
                )
                pos.quantity = total_qty
                pos.current_price = execution_price
            else:
                pos = AgentPosition(
                    agent_id=agent.id,
                    symbol=symbol,
                    quantity=quantity,
                    entry_price=execution_price,
                    current_price=execution_price,
                )
                self.db.add(pos)

        # ── SELL ───────────────────────────────────────────────────
        elif action == "sell":
            pos = await self._get_open_position(agent.id, symbol)
            if not pos or pos.quantity < quantity:
                logger.info(f"Agent {agent.name} has no/insufficient {symbol} to sell")
                return None

            realized_pnl = (execution_price - pos.entry_price) * quantity
            agent.cash += total_cost

            if abs(pos.quantity - quantity) < 0.0001:
                # Close entire position
                pos.is_open = False
                pos.closed_at = datetime.now(timezone.utc)
                pos.pnl = realized_pnl
            else:
                pos.quantity -= quantity
        else:
            # short / cover — simplified: treat like sell/buy
            realized_pnl = 0.0

        realized_pnl = realized_pnl if action == "sell" else 0.0

        # Create trade record
        trade = AgentTrade(
            agent_id=agent.id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=execution_price,
            slippage_cost=slippage_cost,
            total_cost=total_cost,
            reasoning=reasoning,
            realized_pnl=realized_pnl,
            executed_at=datetime.now(timezone.utc),
        )
        self.db.add(trade)

        # Update agent stats
        agent.total_trades += 1
        agent.last_trade_at = datetime.now(timezone.utc)

        # Publish live trade to WebSocket channel
        await publish(CHANNEL_TRADES, {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "price": execution_price,
            "reasoning": reasoning or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Create signal record (AI-Traderv2 compatible)
        signal = Signal(
            agent_id=agent.id,
            signal_type=SignalType.TRADE,
            market="us-stock",
            symbol=symbol,
            action=action,
            price=execution_price,
            quantity=quantity,
            realized_pnl=realized_pnl,
            content=reasoning,
            points_earned=10,
        )
        self.db.add(signal)
        agent.points += 10

        await self.db.flush()
        logger.info(
            f"Trade: {agent.name} {action.upper()} {quantity} {symbol} @ {execution_price:.2f}"
        )
        return trade

    async def update_positions_prices(self, agent: Agent) -> float:
        """
        Update current prices for all open positions.
        Returns total portfolio value (cash + positions).
        """
        result = await self.db.execute(
            select(AgentPosition).where(
                and_(AgentPosition.agent_id == agent.id, AgentPosition.is_open == True)
            )
        )
        positions = result.scalars().all()

        positions_value = 0.0
        for pos in positions:
            current_price = await get_current_price(pos.symbol)
            if current_price:
                pos.current_price = current_price
                pos.pnl = (current_price - pos.entry_price) * pos.quantity
                pos.pnl_pct = (current_price / pos.entry_price - 1) * 100
                positions_value += current_price * pos.quantity

        return agent.cash + positions_value

    async def capture_equity_snapshot(
        self, agent: Agent, daily_pnl_pct: float = 0.0
    ):
        """Save an equity snapshot for chart rendering."""
        result = await self.db.execute(
            select(AgentPosition).where(
                and_(AgentPosition.agent_id == agent.id, AgentPosition.is_open == True)
            )
        )
        positions = result.scalars().all()
        positions_value = sum(p.quantity * p.current_price for p in positions)
        equity = agent.cash + positions_value

        snapshot = EquitySnapshot(
            agent_id=agent.id,
            equity=equity,
            cash=agent.cash,
            positions_value=positions_value,
            daily_pnl_pct=daily_pnl_pct,
        )
        self.db.add(snapshot)

    async def _get_open_position(
        self, agent_id: int, symbol: str
    ) -> Optional[AgentPosition]:
        result = await self.db.execute(
            select(AgentPosition).where(
                and_(
                    AgentPosition.agent_id == agent_id,
                    AgentPosition.symbol == symbol,
                    AgentPosition.is_open == True,
                )
            )
        )
        return result.scalar_one_or_none()
