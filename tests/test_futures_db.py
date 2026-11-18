"""Tests para la capa de persistencia PostgreSQL en Railway (futures/db/).

Verifica:
1. Carga de migraciones y cálculo determinista de checksums SHA-256.
2. Detección estricta de alteraciones de migración (MigrationTamperedError).
3. Formato y ejecución del protocolo de streaming masivo COPY.
4. Persistencia completa de corrida walk-forward, ventanas y trials.
5. Reconstrucción fiel de la matriz de retornos periódicos T x N para PBO / CSCV.
6. Auditoría y registro de discrepancias live_vs_model en puntos básicos (bps).
"""

from __future__ import annotations

import io
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from krmaazha_binance_mcp.futures.costs import (
    CostModel,
    FeeModel,
    FixedBasisPointSlippage,
)
from krmaazha_binance_mcp.futures.db.client import DatabaseClient
from krmaazha_binance_mcp.futures.db.copy import execute_copy, format_copy_csv
from krmaazha_binance_mcp.futures.db.migrator import (
    MigrationRunner,
    MigrationTamperedError,
)
from krmaazha_binance_mcp.futures.db.schema import (
    MIGRATION_ADVISORY_LOCK_ID,
    LiveVsModelRecord,
    MigrationFile,
    compute_sql_checksum,
    load_migration_files,
)
from krmaazha_binance_mcp.futures.research import (
    EmaCrossHypothesis,
    WalkForwardConfig,
    WalkForwardEngine,
)
from krmaazha_binance_mcp.futures.stats import compute_pbo_cscv


@pytest.fixture
def memory_db() -> sqlite3.Connection:
    """Provee una base de datos en memoria para pruebas DB-API / SQLite."""
    conn = sqlite3.connect(":memory:")
    # Adaptar sintaxis para emular PostgreSQL en SQLite
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INT PRIMARY KEY,
            name TEXT NOT NULL,
            checksum VARCHAR(64) NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS research_runs (
            run_id TEXT PRIMARY KEY,
            strategy_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            config_json TEXT NOT NULL,
            n_candles INT NOT NULL,
            n_windows INT NOT NULL,
            oos_return_pct REAL NOT NULL,
            oos_sharpe REAL NOT NULL,
            oos_sortino REAL NOT NULL,
            oos_max_drawdown REAL NOT NULL,
            deflated_sharpe_ratio REAL NOT NULL,
            pbo REAL,
            gate_passed INT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS walk_forward_windows (
            window_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            window_index INT NOT NULL,
            train_start TEXT NOT NULL,
            train_end TEXT NOT NULL,
            test_start TEXT NOT NULL,
            test_end TEXT NOT NULL,
            best_params_json TEXT NOT NULL,
            train_metric REAL NOT NULL,
            test_return_pct REAL NOT NULL,
            buy_hold_return_pct REAL NOT NULL,
            beat_buy_hold INT NOT NULL,
            trades_count INT NOT NULL,
            fee_cost REAL NOT NULL,
            slippage_cost REAL NOT NULL,
            funding_cost REAL NOT NULL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trials (
            trial_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            trial_index INT NOT NULL,
            params_json TEXT NOT NULL,
            in_sample_sharpe REAL NOT NULL,
            in_sample_return_pct REAL NOT NULL,
            out_of_sample_sharpe REAL,
            out_of_sample_return_pct REAL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trial_period_returns (
            trial_id INT NOT NULL,
            bar_time TEXT NOT NULL,
            is_oos INT NOT NULL DEFAULT 1,
            daily_return REAL NOT NULL,
            PRIMARY KEY (trial_id, bar_time)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS live_vs_model (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            fill_time TEXT NOT NULL,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            model_price REAL NOT NULL,
            realized_price REAL NOT NULL,
            model_fee REAL NOT NULL,
            realized_fee REAL NOT NULL,
            model_slippage_cost REAL NOT NULL,
            realized_slippage_cost REAL NOT NULL,
            model_funding_cost REAL NOT NULL,
            realized_funding_cost REAL NOT NULL,
            model_pnl REAL NOT NULL,
            realized_pnl REAL NOT NULL,
            discrepancy_bps REAL NOT NULL,
            notes TEXT
        );
        """
    )
    conn.commit()
    return conn


# ── 1. Descubrimiento y Checksums de Migraciones ──────────────────────────────


def test_load_migration_files_and_checksums() -> None:
    migrations = load_migration_files()
    assert len(migrations) >= 2

    # Verificar que están ordenadas por versión
    versions = [m.version for m in migrations]
    assert versions == sorted(versions)
    assert 1 in versions
    assert 2 in versions

    for m in migrations:
        assert len(m.checksum) == 64  # SHA-256 produce 64 caracteres hex
        assert m.sql.strip()
        # Verificar que el checksum coincide con el contenido
        assert compute_sql_checksum(m.sql) == m.checksum

    assert MIGRATION_ADVISORY_LOCK_ID == 14022026


# ── 2. Ejecución de Migraciones y Detección de Alteraciones ────────────────────


def test_migration_runner_apply_and_idempotency(memory_db: sqlite3.Connection) -> None:
    # Crear dos migraciones simuladas
    m1 = MigrationFile(
        version=101,
        name="test_first",
        filepath=memory_db,  # type: ignore[arg-type]
        checksum=compute_sql_checksum("CREATE TABLE t1 (id INT);"),
        sql="CREATE TABLE t1 (id INT);",
    )
    m2 = MigrationFile(
        version=102,
        name="test_second",
        filepath=memory_db,  # type: ignore[arg-type]
        checksum=compute_sql_checksum("CREATE TABLE t2 (id INT);"),
        sql="CREATE TABLE t2 (id INT);",
    )

    runner = MigrationRunner([m1, m2])
    applied = runner.apply_migrations(memory_db)
    assert applied == [101, 102]

    # Re-ejecutar es idempotente
    applied_again = runner.apply_migrations(memory_db)
    assert applied_again == []


def test_migration_runner_tamper_detection(memory_db: sqlite3.Connection) -> None:
    m_orig = MigrationFile(
        version=201,
        name="safe_migration",
        filepath=memory_db,  # type: ignore[arg-type]
        checksum=compute_sql_checksum("CREATE TABLE safe (id INT);"),
        sql="CREATE TABLE safe (id INT);",
    )
    runner = MigrationRunner([m_orig])
    runner.apply_migrations(memory_db)

    # Simular que alguien modificó el archivo de migración después de aplicarlo
    m_tampered = MigrationFile(
        version=201,
        name="safe_migration",
        filepath=memory_db,  # type: ignore[arg-type]
        checksum=compute_sql_checksum("CREATE TABLE safe (id INT, hacked TEXT);"),
        sql="CREATE TABLE safe (id INT, hacked TEXT);",
    )
    runner_tampered = MigrationRunner([m_tampered])

    with pytest.raises(MigrationTamperedError, match="fue alterada"):
        runner_tampered.apply_migrations(memory_db)


# ── 3. Protocolo de Inserción Masiva COPY ──────────────────────────────────────


def test_format_copy_csv() -> None:
    # De DataFrame
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "name": ["BTC", "ETH"],
            "flag": [True, False],
            "price": [50_000.5, float("nan")],
        }
    )
    cols = ["id", "name", "flag", "price"]
    buf = format_copy_csv(df, cols)
    content = buf.getvalue()
    lines = content.strip().split("\n")
    assert lines[0] == "1,BTC,t,50000.5"
    assert lines[1] == "2,ETH,f,\\N"

    # De lista de diccionarios
    dict_records = [
        {"id": 10, "val": None},
        {"id": 20, "val": 1.25},
    ]
    buf2 = format_copy_csv(dict_records, ["id", "val"])
    lines2 = buf2.getvalue().strip().split("\n")
    assert lines2[0] == "10,\\N"
    assert lines2[1] == "20,1.25"


def test_execute_copy_fallback(memory_db: sqlite3.Connection) -> None:
    cols = ["trial_id", "bar_time", "is_oos", "daily_return"]
    data = [
        {"trial_id": 1, "bar_time": "2024-01-01", "is_oos": True, "daily_return": 0.012},
        {"trial_id": 1, "bar_time": "2024-01-02", "is_oos": True, "daily_return": -0.005},
        {"trial_id": 2, "bar_time": "2024-01-01", "is_oos": False, "daily_return": 0.003},
    ]
    buf = format_copy_csv(data, cols)
    inserted = execute_copy(memory_db, "trial_period_returns", cols, buf)
    assert inserted == 3

    cur = memory_db.cursor()
    cur.execute("SELECT COUNT(*) FROM trial_period_returns;")
    assert cur.fetchone()[0] == 3


# ── 4. Persistencia de Walk-Forward y Reconstrucción de Matriz PBO ─────────────


def test_database_client_save_run_and_reconstruct_matrix(memory_db: sqlite3.Connection) -> None:
    client = DatabaseClient(connection=memory_db)

    # 1. Crear una simulación walk-forward sintética
    rng = np.random.default_rng(42)
    n_bars = 400
    prices = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, n_bars)))
    df = pd.DataFrame(
        {
            "open_time": np.arange(n_bars, dtype="int64") * 86_400_000,
            "open": np.concatenate([[100.0], prices[:-1]]),
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.full(n_bars, 500.0),
        }
    )

    cost_model = CostModel(
        fee_model=FeeModel(taker_fee=0.0004, maker_fee=0.0002),
        slippage_model=FixedBasisPointSlippage(bps=2.0),
    )
    cfg = WalkForwardConfig(
        train_bars=150, test_bars=50, step_bars=50, cost_model=cost_model, min_windows=3
    )
    engine = WalkForwardEngine(cfg)
    hyp = EmaCrossHypothesis(fast_periods=[5, 8], slow_periods=[20, 50])
    wf_res = engine.run(df, hyp)

    # 2. Persistir la corrida completa en la base de datos
    run_id = client.save_research_run(wf_res)
    assert run_id

    # 3. Guardar 4 trials con 50 barras cada uno
    trials_records = [
        {"trial_index": 0, "params": {"fast": 5, "slow": 20}, "in_sample_sharpe": 1.2, "in_sample_return_pct": 15.0},
        {"trial_index": 1, "params": {"fast": 5, "slow": 50}, "in_sample_sharpe": 0.8, "in_sample_return_pct": 10.0},
        {"trial_index": 2, "params": {"fast": 8, "slow": 20}, "in_sample_sharpe": 1.5, "in_sample_return_pct": 18.0},
        {"trial_index": 3, "params": {"fast": 8, "slow": 50}, "in_sample_sharpe": 0.5, "in_sample_return_pct": 5.0},
    ]

    returns_records = []
    for t_idx in range(4):
        # Cada trial con id t_idx + 1
        tr_id = t_idx + 1
        for b in range(50):
            bar_t = f"2024-02-{b+1:02d}"
            ret_val = float(rng.normal(0.001 * t_idx, 0.01))
            returns_records.append(
                {"trial_id": tr_id, "bar_time": bar_t, "is_oos": True, "daily_return": ret_val}
            )

    client.save_trials_and_returns(run_id, trials_records, returns_records)

    # 4. Reconstruir la matriz T x N desde la base de datos
    matrix = client.load_trial_return_matrix(run_id)
    assert not matrix.empty
    assert matrix.shape == (50, 4)  # 50 períodos x 4 trials

    # 5. Alimentar la matriz reconstruida directamente al motor PBO
    pbo_res = compute_pbo_cscv(matrix, num_blocks=8)
    assert pbo_res.num_trials == 4
    assert pbo_res.num_combinations == 70
    assert 0.0 <= pbo_res.pbo <= 1.0


# ── 5. Auditoría de Discrepancias live_vs_model ────────────────────────────────


def test_live_vs_model_persistence(memory_db: sqlite3.Connection) -> None:
    client = DatabaseClient(connection=memory_db)

    record = LiveVsModelRecord(
        symbol="BTCUSDT",
        fill_time="2024-11-14T00:00:00Z",
        side="BUY",
        qty=Decimal("0.50000000"),
        model_price=Decimal("65000.00"),
        realized_price=Decimal("65010.00"),
        model_fee=Decimal("13.00"),
        realized_fee=Decimal("13.002"),
        model_slippage_cost=Decimal("6.50"),
        realized_slippage_cost=Decimal("7.00"),
        model_funding_cost=Decimal("0.00"),
        realized_funding_cost=Decimal("0.00"),
        model_pnl=Decimal("150.00"),
        realized_pnl=Decimal("148.50"),
        discrepancy_bps=2.3,
        notes="Prueba de auditoría de fricción",
    )

    client.record_live_vs_model_fill(record)

    cur = memory_db.cursor()
    cur.execute("SELECT symbol, side, discrepancy_bps, notes FROM live_vs_model;")
    row = cur.fetchone()
    assert row[0] == "BTCUSDT"
    assert row[1] == "BUY"
    assert row[2] == pytest.approx(2.3)
    assert row[3] == "Prueba de auditoría de fricción"


def test_live_vs_model_validation() -> None:
    with pytest.raises(ValueError, match="side debe ser 'BUY' o 'SELL'"):
        LiveVsModelRecord(
            symbol="BTCUSDT",
            fill_time="2024-11-14T00:00:00Z",
            side="HOLD",
            qty=Decimal("1.0"),
            model_price=Decimal("100"),
            realized_price=Decimal("100"),
            model_fee=Decimal("0.1"),
            realized_fee=Decimal("0.1"),
            model_slippage_cost=Decimal("0.05"),
            realized_slippage_cost=Decimal("0.05"),
            model_funding_cost=Decimal("0"),
            realized_funding_cost=Decimal("0"),
            model_pnl=Decimal("10"),
            realized_pnl=Decimal("10"),
            discrepancy_bps=0.0,
        )

    with pytest.raises(ValueError, match="qty debe ser positiva"):
        LiveVsModelRecord(
            symbol="BTCUSDT",
            fill_time="2024-11-14T00:00:00Z",
            side="BUY",
            qty=Decimal("0.0"),  # No positiva
            model_price=Decimal("100"),
            realized_price=Decimal("100"),
            model_fee=Decimal("0.1"),
            realized_fee=Decimal("0.1"),
            model_slippage_cost=Decimal("0.05"),
            realized_slippage_cost=Decimal("0.05"),
            model_funding_cost=Decimal("0"),
            realized_funding_cost=Decimal("0"),
            model_pnl=Decimal("10"),
            realized_pnl=Decimal("10"),
            discrepancy_bps=0.0,
        )


def test_database_client_no_url_error() -> None:
    client = DatabaseClient(connection_url=None, connection=None)
    with pytest.raises(ValueError, match="No se especificó connection_url"):
        client.get_connection()


def test_database_client_close_and_empty_matrix(memory_db: sqlite3.Connection) -> None:
    client = DatabaseClient(connection=memory_db)
    assert client.get_connection() is memory_db
    # Matriz vacía para run inexistente
    df_empty = client.load_trial_return_matrix("unknown-run-id")
    assert df_empty.empty

    client.close()
    assert client._conn is None
    # Segundo close es no-op seguro
    client.close()


def test_database_client_missing_driver_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DatabaseClient(connection_url="postgresql://usr:pass@localhost:5432/db")
    import builtins

    orig_import = builtins.__import__

    def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in ("psycopg", "psycopg2"):
            raise ImportError(f"No module named {name}")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    with pytest.raises(RuntimeError, match="Se requiere un controlador PostgreSQL"):
        client.get_connection()


def test_migration_runner_rollback_on_error(memory_db: sqlite3.Connection) -> None:
    bad_migration = MigrationFile(
        version=999,
        name="syntax_error",
        filepath=memory_db,  # type: ignore[arg-type]
        checksum="dummy_chk",
        sql="SYNTAX ERROR NON_EXISTENT_KEYWORD;",
    )
    runner = MigrationRunner([bad_migration])
    with pytest.raises(RuntimeError, match="Fallo aplicando la migración 999_syntax_error"):
        runner.apply_migrations(memory_db)

    cur = memory_db.cursor()
    cur.execute("SELECT version FROM schema_migrations WHERE version = 999;")
    assert cur.fetchone() is None
    cur.close()


def test_copy_nan_inf_and_empty_buffer(memory_db: sqlite3.Connection) -> None:
    # 1. NaN e Inf en DataFrame y dicts
    df_nan = pd.DataFrame(
        [
            {"val": float("nan"), "note": "nan_val"},
            {"val": float("inf"), "note": "inf_val"},
            {"val": -float("inf"), "note": "neg_inf"},
        ]
    )
    buf_df = format_copy_csv(df_nan, ["val", "note"])
    lines_df = buf_df.getvalue().strip().split("\n")
    assert lines_df[0] == "\\N,nan_val"
    assert lines_df[1] == "\\N,inf_val"
    assert lines_df[2] == "\\N,neg_inf"

    dicts_nan = [
        {"val": float("nan"), "note": "nan_dict"},
        {"val": float("inf"), "note": "inf_dict"},
    ]
    buf_dict = format_copy_csv(dicts_nan, ["val", "note"])
    lines_dict = buf_dict.getvalue().strip().split("\n")
    assert lines_dict[0] == "\\N,nan_dict"
    assert lines_dict[1] == "\\N,inf_dict"

    # 2. Buffer vacío a execute_copy
    empty_buf = io.StringIO()
    res = execute_copy(memory_db, "non_existent_table", ["val"], empty_buf)
    assert res == 0


def test_load_migration_files_edge_cases(tmp_path: Path) -> None:
    # 1. Directorio inexistente
    non_existent = tmp_path / "does_not_exist"
    assert load_migration_files(non_existent) == []

    # 2. Archivo con nombre sin prefijo numérico
    valid_dir = tmp_path / "migrations"
    valid_dir.mkdir()
    (valid_dir / "README.sql").write_text("-- Documentation", encoding="utf-8")
    (valid_dir / "001_initial.sql").write_text("CREATE TABLE t1 (id INT);", encoding="utf-8")

    loaded = load_migration_files(valid_dir)
    assert len(loaded) == 1
    assert loaded[0].version == 1
    assert loaded[0].name == "initial"

