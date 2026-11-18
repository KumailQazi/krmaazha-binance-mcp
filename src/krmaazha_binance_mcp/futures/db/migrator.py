"""Ejecutor de migraciones con bloqueo consultivo y checksum (futures/db/migrator.py)."""

from __future__ import annotations

import contextlib
from typing import Any, Protocol

from krmaazha_binance_mcp.futures.db.schema import (
    MIGRATION_ADVISORY_LOCK_ID,
    MigrationFile,
    load_migration_files,
)


class MigrationTamperedError(Exception):
    """Se lanza cuando un archivo de migración ya aplicado difiere de su checksum registrado."""


class DbConnectionProtocol(Protocol):
    """Protocolo mínimo de conexión a base de datos para migraciones."""

    def cursor(self) -> Any: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class MigrationRunner:
    """Gestiona la aplicación de migraciones SQL garantizando atomicidad y checksums."""

    def __init__(self, migrations: list[MigrationFile] | None = None) -> None:
        self.migrations = migrations if migrations is not None else load_migration_files()

    def _is_postgres(self, conn: Any) -> bool:
        """Determina si la conexión apunta a un servidor PostgreSQL real."""
        module_name = type(conn).__module__.lower()
        return "psycopg" in module_name or "asyncpg" in module_name or "pg" in module_name

    def _acquire_advisory_lock(self, cur: Any) -> None:
        """Adquiere el bloqueo consultivo para evitar ejecuciones concurrentes en Railway."""
        with contextlib.suppress(Exception):
            cur.execute(f"SELECT pg_advisory_lock({MIGRATION_ADVISORY_LOCK_ID});")

    def _release_advisory_lock(self, cur: Any) -> None:
        """Libera el bloqueo consultivo."""
        with contextlib.suppress(Exception):
            cur.execute(f"SELECT pg_advisory_unlock({MIGRATION_ADVISORY_LOCK_ID});")

    def _ensure_migrations_table(self, cur: Any) -> None:
        """Crea la tabla schema_migrations si aún no existe."""
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INT PRIMARY KEY,
                name TEXT NOT NULL,
                checksum VARCHAR(64) NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    def apply_migrations(self, conn: Any) -> list[int]:
        """Aplica las migraciones pendientes con control de concurrencia y validación de hash."""
        cur = conn.cursor()
        is_pg = self._is_postgres(conn)
        applied_now: list[int] = []

        try:
            if is_pg:
                self._acquire_advisory_lock(cur)

            self._ensure_migrations_table(cur)
            conn.commit()

            # Consultar migraciones previas
            cur.execute("SELECT version, checksum FROM schema_migrations ORDER BY version;")
            existing: dict[int, str] = {row[0]: row[1] for row in cur.fetchall()}

            for m in self.migrations:
                if m.version in existing:
                    recorded_chk = existing[m.version]
                    if recorded_chk != m.checksum:
                        msg = (
                            f"La migración {m.version:03d}_{m.name} fue alterada tras aplicarse. "
                            f"Checksum registrado: {recorded_chk}, actual: {m.checksum}"
                        )
                        raise MigrationTamperedError(msg)
                    continue

                # Ejecutar nueva migración dentro de una transacción
                try:
                    # SQLite no soporta múltiples sentencias en execute(), sólo en executescript()
                    if hasattr(cur, "executescript") and not is_pg:
                        cur.executescript(m.sql)
                    else:
                        cur.execute(m.sql)

                    cur.execute(
                        """
                        INSERT INTO schema_migrations (version, name, checksum)
                        VALUES (%s, %s, %s);
                        """
                        if is_pg
                        else """
                        INSERT INTO schema_migrations (version, name, checksum)
                        VALUES (?, ?, ?);
                        """,
                        (m.version, m.name, m.checksum),
                    )
                    conn.commit()
                    applied_now.append(m.version)
                except Exception as exc:
                    conn.rollback()
                    raise RuntimeError(
                        f"Fallo aplicando la migración {m.version:03d}_{m.name}: {exc}"
                    ) from exc

        finally:
            if is_pg:
                with contextlib.suppress(Exception):
                    self._release_advisory_lock(cur)
                    conn.commit()
            with contextlib.suppress(Exception):
                cur.close()

        return applied_now
