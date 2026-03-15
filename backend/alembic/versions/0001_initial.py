"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('username', sa.String(100), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('avatar_url', sa.String(512), nullable=True),
        sa.Column('google_id', sa.String(255), unique=True, nullable=True),
        sa.Column('token_balance', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('total_tokens_won', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('total_tokens_bet', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_admin', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('last_login_bonus_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    op.create_table('agents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('strategy_type', sa.String(100), server_default='unknown'),
        sa.Column('avatar_emoji', sa.String(20), server_default='bot'),
        sa.Column('llm_model', sa.String(100), nullable=True),
        sa.Column('agent_type', sa.String(20), server_default='builtin'),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('cash', sa.Float(), server_default='100000.0', nullable=False),
        sa.Column('starting_capital', sa.Float(), server_default='100000.0', nullable=False),
        sa.Column('points', sa.Integer(), server_default='100', nullable=False),
        sa.Column('reputation_score', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('total_pnl', sa.Float(), server_default='0.0'),
        sa.Column('total_pnl_pct', sa.Float(), server_default='0.0'),
        sa.Column('daily_pnl', sa.Float(), server_default='0.0'),
        sa.Column('daily_pnl_pct', sa.Float(), server_default='0.0'),
        sa.Column('weekly_pnl_pct', sa.Float(), server_default='0.0'),
        sa.Column('sharpe_ratio', sa.Float(), server_default='0.0'),
        sa.Column('win_rate', sa.Float(), server_default='0.0'),
        sa.Column('max_drawdown', sa.Float(), server_default='0.0'),
        sa.Column('total_trades', sa.Integer(), server_default='0'),
        sa.Column('jwt_token', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('last_trade_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table('agent_positions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('current_price', sa.Float(), server_default='0.0'),
        sa.Column('pnl', sa.Float(), server_default='0.0'),
        sa.Column('pnl_pct', sa.Float(), server_default='0.0'),
        sa.Column('is_open', sa.Boolean(), server_default='true'),
        sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table('agent_trades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('action', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('slippage_cost', sa.Float(), server_default='0.0'),
        sa.Column('total_cost', sa.Float(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('realized_pnl', sa.Float(), server_default='0.0'),
        sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    op.create_table('equity_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('equity', sa.Float(), nullable=False),
        sa.Column('cash', sa.Float(), nullable=False),
        sa.Column('positions_value', sa.Float(), server_default='0.0'),
        sa.Column('daily_pnl_pct', sa.Float(), server_default='0.0'),
        sa.Column('captured_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    op.create_table('signals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('signal_type', sa.String(20), server_default='trade', nullable=False),
        sa.Column('market', sa.String(50), nullable=True),
        sa.Column('symbol', sa.String(20), nullable=True),
        sa.Column('action', sa.String(10), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('realized_pnl', sa.Float(), nullable=True),
        sa.Column('title', sa.String(300), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('tags', sa.String(500), nullable=True),
        sa.Column('points_earned', sa.Integer(), server_default='0'),
        sa.Column('adoption_count', sa.Integer(), server_default='0'),
        sa.Column('reply_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    op.create_table('signal_replies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('signal_id', sa.Integer(), sa.ForeignKey('signals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id'), nullable=True),
        sa.Column('user_name', sa.String(100), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    op.create_table('daily_contests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('contest_date', sa.Date(), unique=True, nullable=False),
        sa.Column('status', sa.String(20), server_default='open', nullable=False),
        sa.Column('total_pot', sa.BigInteger(), server_default='0'),
        sa.Column('platform_fee', sa.BigInteger(), server_default='0'),
        sa.Column('winner_pot', sa.BigInteger(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table('bets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contest_id', sa.Integer(), sa.ForeignKey('daily_contests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('payout', sa.BigInteger(), server_default='0'),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('placed_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table('daily_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('contest_id', sa.Integer(), sa.ForeignKey('daily_contests.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('winning_agent_id', sa.Integer(), sa.ForeignKey('agents.id'), nullable=True),
        sa.Column('winning_agent_name', sa.String(100), nullable=True),
        sa.Column('winning_pnl_pct', sa.Float(), server_default='0.0'),
        sa.Column('total_bettors', sa.Integer(), server_default='0'),
        sa.Column('winning_bettors', sa.Integer(), server_default='0'),
        sa.Column('total_pot', sa.BigInteger(), server_default='0'),
        sa.Column('winner_pot', sa.BigInteger(), server_default='0'),
        sa.Column('platform_fee', sa.BigInteger(), server_default='0'),
        sa.Column('settled_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )


def downgrade() -> None:
    for t in ['daily_results', 'bets', 'daily_contests', 'signal_replies', 'signals',
              'equity_snapshots', 'agent_trades', 'agent_positions', 'agents', 'users']:
        op.drop_table(t)
