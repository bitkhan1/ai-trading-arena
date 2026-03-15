"""initial

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
    op.execute("
    CREATE TYPE IF NOT EXISTS agenttype AS ENUM ('builtin', 'openclaw');
    ")
    op.execute("
    DO $$ BEGIN
        CREATE TYPE agenttype AS ENUM ('builtin', 'openclaw');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    ")
    op.execute("
    DO $$ BEGIN
        CREATE TYPE agentstatus AS ENUM ('active', 'paused', 'stopped');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    ")
    op.execute("
    DO $$ BEGIN
        CREATE TYPE betstatustype AS ENUM ('pending', 'won', 'lost', 'refunded', 'settled');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    ")
    op.execute("
    DO $$ BEGIN
        CREATE TYPE conteststatus AS ENUM ('open', 'locked', 'settling', 'settled', 'cancelled');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    ")
    op.execute("
    DO $$ BEGIN
        CREATE TYPE signaltype AS ENUM ('trade', 'position', 'strategy', 'discussion');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    ")

    op.execute("
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        hashed_password VARCHAR(255),
        username VARCHAR(100) UNIQUE NOT NULL,
        display_name VARCHAR(100),
        avatar_url VARCHAR(512),
        google_id VARCHAR(255) UNIQUE,
        token_balance BIGINT DEFAULT 0 NOT NULL,
        total_tokens_won BIGINT DEFAULT 0 NOT NULL,
        total_tokens_bet BIGINT DEFAULT 0 NOT NULL,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        is_admin BOOLEAN DEFAULT FALSE NOT NULL,
        last_login_bonus_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
        updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
    )
    ")

    op.execute("
    CREATE TABLE IF NOT EXISTS agents (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) UNIQUE NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        hashed_password VARCHAR(255) NOT NULL,
        description TEXT,
        strategy_type VARCHAR(100) DEFAULT 'unknown',
        avatar_emoji VARCHAR(10) DEFAULT '🤖',
        llm_model VARCHAR(100),
        agent_type agenttype DEFAULT 'builtin',
        status agentstatus DEFAULT 'active',
        cash FLOAT DEFAULT 100000.0 NOT NULL,
        starting_capital FLOAT DEFAULT 100000.0 NOT NULL,
        points INTEGER DEFAULT 100 NOT NULL,
        reputation_score FLOAT DEFAULT 0.0 NOT NULL,
        total_pnl FLOAT DEFAULT 0.0,
        total_pnl_pct FLOAT DEFAULT 0.0,
        daily_pnl FLOAT DEFAULT 0.0,
        daily_pnl_pct FLOAT DEFAULT 0.0,
        weekly_pnl_pct FLOAT DEFAULT 0.0,
        sharpe_ratio FLOAT DEFAULT 0.0,
        win_rate FLOAT DEFAULT 0.0,
        max_drawdown FLOAT DEFAULT 0.0,
        total_trades INTEGER DEFAULT 0,
        jwt_token TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        last_trade_at TIMESTAMPTZ
    )
    ")

    op.execute("
    CREATE TABLE IF NOT EXISTS agent_positions (
        id SERIAL PRIMARY KEY,
        agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
        symbol VARCHAR(20) NOT NULL,
        quantity FLOAT NOT NULL,
        entry_price FLOAT NOT NULL,
        current_price FLOAT DEFAULT 0.0,
        pnl FLOAT DEFAULT 0.0,
        pnl_pct FLOAT DEFAULT 0.0,
        is_open BOOLEAN DEFAULT TRUE,
        opened_at TIMESTAMPTZ DEFAULT NOW(),
        closed_at TIMESTAMPTZ
    )
    ")

    op.execute("
    CREATE TABLE IF NOT EXISTS agent_trades (
        id SERIAL PRIMARY KEY,
        agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
        symbol VARCHAR(20) NOT NULL,
        action VARCHAR(10) NOT NULL,
        quantity FLOAT NOT NULL,
        price FLOAT NOT NULL,
        slippage_cost FLOAT DEFAULT 0.0,
        total_cost FLOAT NOT NULL,
        reasoning TEXT,
        realized_pnl FLOAT DEFAULT 0.0,
        executed_at TIMESTAMPTZ DEFAULT NOW()
    )
    ")

    op.execute("
    CREATE TABLE IF NOT EXISTS equity_snapshots (
        id SERIAL PRIMARY KEY,
        agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
        equity FLOAT NOT NULL,
        cash FLOAT NOT NULL,
        positions_value FLOAT DEFAULT 0.0,
        daily_pnl_pct FLOAT DEFAULT 0.0,
        captured_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
    )
    ")

    op.execute("
    CREATE TABLE IF NOT EXISTS signals (
        id SERIAL PRIMARY KEY,
        agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
        signal_type signaltype NOT NULL DEFAULT 'trade',
        market VARCHAR(50),
        symbol VARCHAR(20),
        action VARCHAR(10),
        price FLOAT,
        quantity FLOAT,
        realized_pnl FLOAT,
        title VARCHAR(300),
        content TEXT,
        tags VARCHAR(500),
        points_earned INTEGER DEFAULT 0,
        adoption_count INTEGER DEFAULT 0,
        reply_count INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    ")

    op.execute("
    CREATE TABLE IF NOT EXISTS signal_replies (
        id SERIAL PRIMARY KEY,
        signal_id INTEGER NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
        agent_id INTEGER REFERENCES agents(id),
        user_name VARCHAR(100) NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    ")

    op.execute("
    CREATE TABLE IF NOT EXISTS daily_contests (
        id SERIAL PRIMARY KEY,
        contest_date DATE UNIQUE NOT NULL,
        status conteststatus DEFAULT 'open' NOT NULL,
        total_pot BIGINT DEFAULT 0,
        platform_fee BIGINT DEFAULT 0,
        winner_pot BIGINT DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        settled_at TIMESTAMPTZ
    )
    ")

    op.execute("
    CREATE TABLE IF NOT EXISTS bets (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
        contest_id INTEGER NOT NULL REFERENCES daily_contests(id) ON DELETE CASCADE,
        amount BIGINT NOT NULL,
        payout BIGINT DEFAULT 0,
        status betstatustype DEFAULT 'pending' NOT NULL,
        placed_at TIMESTAMPTZ DEFAULT NOW(),
        settled_at TIMESTAMPTZ
    )
    ")

    op.execute("
    CREATE TABLE IF NOT EXISTS daily_results (
        id SERIAL PRIMARY KEY,
        contest_id INTEGER UNIQUE NOT NULL REFERENCES daily_contests(id) ON DELETE CASCADE,
        winning_agent_id INTEGER REFERENCES agents(id),
        winning_agent_name VARCHAR(100),
        winning_pnl_pct FLOAT DEFAULT 0.0,
        total_bettors INTEGER DEFAULT 0,
        winning_bettors INTEGER DEFAULT 0,
        total_pot BIGINT DEFAULT 0,
        winner_pot BIGINT DEFAULT 0,
        platform_fee BIGINT DEFAULT 0,
        settled_at TIMESTAMPTZ DEFAULT NOW()
    )
    ")


def downgrade() -> None:
    for t in ['daily_results','bets','daily_contests','signal_replies','signals',
              'equity_snapshots','agent_trades','agent_positions','agents','users']:
        op.execute(f'DROP TABLE IF EXISTS {t} CASCADE')
    for e in ['agenttype','agentstatus','betstatustype','conteststatus','signaltype']:
        op.execute(f'DROP TYPE IF EXISTS {e} CASCADE')
