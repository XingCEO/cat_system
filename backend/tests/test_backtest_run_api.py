import pytest
import pandas as pd
from types import SimpleNamespace
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine

from database import _migrate_existing_schema, _normalize_existing_column_types
from routers import backtest as backtest_router
from schemas.backtest import BacktestRequest, BacktestResponse, BacktestStats


def _request() -> BacktestRequest:
    return BacktestRequest(
        start_date="2026-01-01",
        end_date="2026-01-31",
        change_min=2,
        change_max=5,
        volume_min=500,
        holding_days=[1],
    )


def _response() -> BacktestResponse:
    return BacktestResponse(
        total_signals=1,
        unique_stocks=1,
        stats=[
            BacktestStats(
                holding_days=1,
                total_trades=1,
                winning_trades=1,
                losing_trades=0,
                win_rate=100,
                avg_return=1.23,
                max_gain=1.23,
                max_loss=1.23,
                expected_value=1.23,
            )
        ],
        overall_win_rate=100,
        overall_avg_return=1.23,
        start_date="2026-01-01",
        end_date="2026-01-31",
        trading_days=20,
        return_distribution={"0%~1%": 1},
    )


class FailingHistoryDb:
    def __init__(self):
        self.added = None
        self.rolled_back = False

    def add(self, obj):
        self.added = obj

    async def commit(self):
        raise RuntimeError("history table schema drift")

    async def refresh(self, obj):
        obj.id = 999

    async def rollback(self):
        self.rolled_back = True


class LockedOnceDb:
    def __init__(self):
        self.added = None
        self.add_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def add(self, obj):
        self.added = obj
        self.add_count += 1

    async def commit(self):
        self.commit_count += 1
        if self.commit_count == 1:
            raise OperationalError(
                "INSERT INTO backtest_results ...",
                {},
                Exception("database is locked"),
            )

    async def refresh(self, obj):
        obj.id = 321

    async def rollback(self):
        self.rollback_count += 1


@pytest.mark.asyncio
async def test_run_backtest_returns_result_when_history_save_fails(monkeypatch):
    async def fake_run_backtest(request):
        return _response()

    monkeypatch.setattr(
        backtest_router.backtest_engine,
        "run_backtest",
        fake_run_backtest,
    )

    db = FailingHistoryDb()
    response = await backtest_router.run_backtest(_request(), db)

    assert response.success is True
    assert response.data.total_signals == 1
    assert response.data.id is None
    assert db.added is not None
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_run_backtest_retries_sqlite_locked_history_save(monkeypatch):
    async def fake_run_backtest(request):
        return _response()

    monkeypatch.setattr(
        backtest_router.backtest_engine,
        "run_backtest",
        fake_run_backtest,
    )
    monkeypatch.setattr(backtest_router, "BACKTEST_SAVE_RETRY_DELAYS", (0,))

    db = LockedOnceDb()
    response = await backtest_router.run_backtest(_request(), db)

    assert response.success is True
    assert response.data.id == 321
    assert db.commit_count == 2
    assert db.rollback_count == 1
    assert db.add_count == 2


@pytest.mark.asyncio
async def test_backtest_engine_retries_sqlite_locked_db_load(monkeypatch):
    from services import backtest_engine as engine_mod
    from services.backtest_engine import BacktestEngine

    engine = BacktestEngine()
    calls = 0

    async def fake_load_range_from_db(start_date, end_date, max_holding):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OperationalError(
                "SELECT daily_prices ...",
                {},
                Exception("database is locked"),
            )
        return pd.DataFrame({"ok": [1]})

    monkeypatch.setattr(engine_mod, "DB_LOAD_RETRY_DELAYS", (0,))
    monkeypatch.setattr(engine, "_load_range_from_db", fake_load_range_from_db)

    df = await engine._load_range_from_db_with_retry(
        "2026-04-20",
        "2026-06-19",
        10,
    )

    assert calls == 2
    assert df["ok"].tolist() == [1]


@pytest.mark.asyncio
async def test_migrate_existing_schema_adds_backtest_and_strategy_columns(tmp_path):
    db_path = tmp_path / "old.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE backtest_results (id INTEGER PRIMARY KEY)"))
            await conn.execute(
                text(
                    "CREATE TABLE user_strategies ("
                    "id INTEGER PRIMARY KEY, "
                    "name VARCHAR(100), "
                    "rules_json JSON, "
                    "alert_enabled BOOLEAN)"
                )
            )
            await conn.execute(text("CREATE TABLE daily_prices (id INTEGER PRIMARY KEY)"))

            await _migrate_existing_schema(conn)

            backtest_cols = await _sqlite_columns(conn, "backtest_results")
            strategy_cols = await _sqlite_columns(conn, "user_strategies")
            daily_cols = await _sqlite_columns(conn, "daily_prices")

        assert {
            "filter_conditions",
            "start_date",
            "end_date",
            "avg_return_1d",
            "detailed_results",
            "created_at",
        }.issubset(backtest_cols)
        assert "line_notify_token" in strategy_cols
        assert {"turnover", "market_ok"}.issubset(daily_cols)
    finally:
        await engine.dispose()


async def _sqlite_columns(conn, table_name: str) -> set[str]:
    rows = (await conn.execute(text(f"PRAGMA table_info({table_name})"))).fetchall()
    return {row[1] for row in rows}


@pytest.mark.asyncio
async def test_normalize_existing_column_types_repairs_postgres_market_ok():
    class FakeConn:
        dialect = SimpleNamespace(name="postgresql")

        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(str(statement))

    conn = FakeConn()

    await _normalize_existing_column_types(conn)

    sql = "\n".join(conn.statements)
    assert "ALTER COLUMN market_ok TYPE BOOLEAN" in sql
    assert "information_schema.columns" in sql


@pytest.mark.asyncio
async def test_normalize_existing_column_types_skips_sqlite():
    class FakeConn:
        dialect = SimpleNamespace(name="sqlite")

        async def execute(self, statement):
            raise AssertionError("SQLite should not run PostgreSQL type migration")

    await _normalize_existing_column_types(FakeConn())
