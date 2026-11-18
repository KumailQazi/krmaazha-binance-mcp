"""Cliente PostgreSQL en Railway para persistencia y auditoría (futures/db/client.py)."""

from __future__ import annotations

import contextlib
import json
import os
import uuid
from typing import Any

import pandas as pd

from krmaazha_binance_mcp.futures.db.copy import execute_copy, format_copy_csv
from krmaazha_binance_mcp.futures.db.migrator import MigrationRunner
from krmaazha_binance_mcp.futures.db.schema import LiveVsModelRecord
from krmaazha_binance_mcp.futures.research import WalkForwardResult


class DatabaseClient:
    """Cliente para interactuar con la base de datos PostgreSQL de investigación."""

    def __init__(
        self,
        connection_url: str | None = None,
        connection: Any | None = None,
    ) -> None:
        self.connection_url = connection_url or os.environ.get("DATABASE_URL")
        self._conn = connection

    def get_connection(self) -> Any:
        """Obtiene o reutiliza la conexión a la base de datos."""
        if self._conn is not None:
            return self._conn

        if not self.connection_url:
            raise ValueError(
                "No se especificó connection_url ni se encontró DATABASE_URL en entorno."
            )

        # Intento de conexión con psycopg (v3) o psycopg2
        try:
            import psycopg  # type: ignore[import-not-found]

            self._conn = psycopg.connect(self.connection_url)
            return self._conn
        except ImportError:
            pass

        try:
            import psycopg2  # type: ignore[import-untyped]

            self._conn = psycopg2.connect(self.connection_url)
            return self._conn
        except ImportError as exc:
            msg = "Se requiere un controlador PostgreSQL ('psycopg'/'psycopg2') para DATABASE_URL."
            raise RuntimeError(msg) from exc

    def close(self) -> None:
        """Cierra la conexión si está abierta."""
        if self._conn is not None:
            with contextlib.suppress(Exception):
                self._conn.close()
            self._conn = None

    def migrate(self) -> list[int]:
        """Aplica las migraciones pendientes con control de concurrencia y validación de hash."""
        conn = self.get_connection()
        runner = MigrationRunner()
        return runner.apply_migrations(conn)

    def save_research_run(
        self,
        result: WalkForwardResult,
        run_id: str | None = None,
        config_dict: dict[str, Any] | None = None,
    ) -> str:
        """Persiste una corrida completa de investigación walk-forward con sus ventanas."""
        conn = self.get_connection()
        cur = conn.cursor()
        assigned_run_id = run_id or str(uuid.uuid4())
        cfg_json = json.dumps(config_dict or {})

        pbo_val = result.pbo_result.pbo if result.pbo_result is not None else None

        try:
            is_pg = "psycopg" in type(conn).__module__.lower()
            param_placeholder = "%s" if is_pg else "?"

            # 1. Insertar corrida principal
            sql_run = f"""
            INSERT INTO research_runs (
                run_id, strategy_name, symbol, timeframe, config_json, n_candles, n_windows,
                oos_return_pct, oos_sharpe, oos_sortino, oos_max_drawdown,
                deflated_sharpe_ratio, pbo, gate_passed
            ) VALUES (
                {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder},
                {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder},
                {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder},
                {param_placeholder}, {param_placeholder}
            );
            """
            cur.execute(
                sql_run,
                (
                    assigned_run_id,
                    result.strategy_name,
                    result.symbol,
                    result.timeframe,
                    cfg_json,
                    result.n_candles,
                    result.n_windows,
                    result.oos_return_pct,
                    result.oos_sharpe,
                    result.oos_sortino,
                    result.oos_max_drawdown,
                    result.deflated_sharpe.deflated_sharpe_ratio,
                    pbo_val,
                    result.gate_verdict.passed,
                ),
            )

            # 2. Insertar ventanas individuales
            sql_win = f"""
            INSERT INTO walk_forward_windows (
                run_id, window_index, train_start, train_end, test_start, test_end,
                best_params_json, train_metric, test_return_pct, buy_hold_return_pct,
                beat_buy_hold, trades_count, fee_cost, slippage_cost, funding_cost
            ) VALUES (
                {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder},
                {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder},
                {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder},
                {param_placeholder}, {param_placeholder}, {param_placeholder}
            );
            """
            for w in result.windows:
                cur.execute(
                    sql_win,
                    (
                        assigned_run_id,
                        w.window_index,
                        str(w.train_start),
                        str(w.train_end),
                        str(w.test_start),
                        str(w.test_end),
                        json.dumps(w.best_params),
                        w.train_metric,
                        w.test_return_pct,
                        w.buy_hold_return_pct,
                        w.beat_buy_hold,
                        w.trades_count,
                        w.fee_cost,
                        w.slippage_cost,
                        w.funding_cost,
                    ),
                )

            conn.commit()
            return assigned_run_id
        finally:
            with contextlib.suppress(Exception):
                cur.close()

    def save_trials_and_returns(
        self,
        run_id: str,
        trials_data: list[dict[str, Any]],
        returns_data: list[dict[str, Any]],
    ) -> None:
        """Persiste los trials evaluados y la matriz completa de retornos mediante COPY."""
        conn = self.get_connection()
        cur = conn.cursor()
        is_pg = "psycopg" in type(conn).__module__.lower()
        ph = "%s" if is_pg else "?"

        try:
            # 1. Insertar trials y obtener sus IDs
            for tr in trials_data:
                sql_tr = f"""
                INSERT INTO trials (
                    run_id, trial_index, params_json, in_sample_sharpe, in_sample_return_pct,
                    out_of_sample_sharpe, out_of_sample_return_pct
                ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph});
                """
                cur.execute(
                    sql_tr,
                    (
                        run_id,
                        tr["trial_index"],
                        json.dumps(tr["params"]),
                        tr["in_sample_sharpe"],
                        tr["in_sample_return_pct"],
                        tr.get("out_of_sample_sharpe"),
                        tr.get("out_of_sample_return_pct"),
                    ),
                )
            conn.commit()

            # 2. Inserción masiva de retornos periódicos por COPY
            if returns_data:
                cols = ["trial_id", "bar_time", "is_oos", "daily_return"]
                buf = format_copy_csv(returns_data, cols)
                execute_copy(conn, "trial_period_returns", cols, buf)

        finally:
            with contextlib.suppress(Exception):
                cur.close()

    def load_trial_return_matrix(self, run_id: str) -> pd.DataFrame:
        """Reconstruye la matriz completa de retornos T x N desde la base de datos.

        Devuelve un DataFrame con índice bar_time y columnas con cada trial_index,
        listo para ser alimentado directamente a compute_pbo_cscv().
        """
        conn = self.get_connection()
        cur = conn.cursor()
        is_pg = "psycopg" in type(conn).__module__.lower()
        ph = "%s" if is_pg else "?"

        try:
            sql = f"""
            SELECT t.trial_index, r.bar_time, r.daily_return
            FROM trial_period_returns r
            JOIN trials t ON r.trial_id = t.trial_id
            WHERE t.run_id = {ph}
            ORDER BY r.bar_time, t.trial_index;
            """
            cur.execute(sql, (run_id,))
            rows = cur.fetchall()

            if not rows:
                return pd.DataFrame()

            df_raw = pd.DataFrame(rows, columns=["trial_index", "bar_time", "daily_return"])
            matrix = df_raw.pivot(
                index="bar_time", columns="trial_index", values="daily_return"
            )
            return matrix.fillna(0.0)

        finally:
            with contextlib.suppress(Exception):
                cur.close()

    def record_live_vs_model_fill(self, record: LiveVsModelRecord) -> None:
        """Registra una fila en la tabla de auditoría live_vs_model."""
        conn = self.get_connection()
        cur = conn.cursor()
        is_pg = "psycopg" in type(conn).__module__.lower()
        ph = "%s" if is_pg else "?"

        try:
            sql = f"""
            INSERT INTO live_vs_model (
                symbol, fill_time, side, qty, model_price, realized_price,
                model_fee, realized_fee, model_slippage_cost, realized_slippage_cost,
                model_funding_cost, realized_funding_cost, model_pnl, realized_pnl,
                discrepancy_bps, notes
            ) VALUES (
                {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph},
                {ph}, {ph}, {ph}, {ph}
            );
            """
            cur.execute(
                sql,
                (
                    record.symbol,
                    record.fill_time,
                    record.side,
                    float(record.qty),
                    float(record.model_price),
                    float(record.realized_price),
                    float(record.model_fee),
                    float(record.realized_fee),
                    float(record.model_slippage_cost),
                    float(record.realized_slippage_cost),
                    float(record.model_funding_cost),
                    float(record.realized_funding_cost),
                    float(record.model_pnl),
                    float(record.realized_pnl),
                    record.discrepancy_bps,
                    record.notes,
                ),
            )
            conn.commit()
        finally:
            with contextlib.suppress(Exception):
                cur.close()
