"""Definiciones de esquema, constantes y metadatos de base de datos (futures/db/schema.py)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

MIGRATION_ADVISORY_LOCK_ID: int = 14022026

MIGRATIONS_DIR: Path = Path(__file__).parent / "migrations"


@dataclass(frozen=True)
class MigrationFile:
    """Representación de un archivo de migración SQL versionado."""

    version: int
    name: str
    filepath: Path
    checksum: str
    sql: str


@dataclass(frozen=True)
class LiveVsModelRecord:
    """Registro de discrepancia entre ejecución real y modelo teórico de costos."""

    symbol: str
    fill_time: str
    side: str
    qty: Decimal
    model_price: Decimal
    realized_price: Decimal
    model_fee: Decimal
    realized_fee: Decimal
    model_slippage_cost: Decimal
    realized_slippage_cost: Decimal
    model_funding_cost: Decimal
    realized_funding_cost: Decimal
    model_pnl: Decimal
    realized_pnl: Decimal
    discrepancy_bps: float
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.side not in ("BUY", "SELL"):
            raise ValueError(f"side debe ser 'BUY' o 'SELL', recibido: {self.side}")
        if self.qty <= 0:
            raise ValueError(f"qty debe ser positiva, recibido: {self.qty}")


def compute_sql_checksum(sql_text: str) -> str:
    """Calcula el hash SHA-256 canónico del contenido de una migración."""
    normalized = sql_text.strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def load_migration_files(migrations_dir: Path = MIGRATIONS_DIR) -> list[MigrationFile]:
    """Carga y ordena todos los archivos .sql de migraciones calculando su checksum SHA-256."""
    if not migrations_dir.exists():
        return []

    sql_files = sorted(migrations_dir.glob("*.sql"))
    migrations: list[MigrationFile] = []

    for f in sql_files:
        # Formato esperado: 001_nombre.sql
        parts = f.stem.split("_", 1)
        if not parts[0].isdigit():
            continue
        ver = int(parts[0])
        name = parts[1] if len(parts) > 1 else f.stem
        content = f.read_text(encoding="utf-8")
        chk = compute_sql_checksum(content)
        migrations.append(
            MigrationFile(
                version=ver,
                name=name,
                filepath=f,
                checksum=chk,
                sql=content,
            )
        )

    migrations.sort(key=lambda m: m.version)
    return migrations
