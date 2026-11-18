"""Protocolo de inserción masiva de alto rendimiento COPY (futures/db/copy.py)."""

from __future__ import annotations

import contextlib
import csv
import io
import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd


def format_copy_csv(
    data: Sequence[dict[str, Any]] | pd.DataFrame,
    columns: Sequence[str],
) -> io.StringIO:
    """Convierte registros o DataFrame a buffer CSV compatible con COPY de Postgres.

    Estándar de formato:
    - NULL representado canónicamente como '\\N'.
    - Caracteres de escape y comillas gestionados según estándar RFC 4180.
    """
    buffer = io.StringIO()
    writer = csv.writer(
        buffer,
        delimiter=",",
        quotechar='"',
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )

    if isinstance(data, pd.DataFrame):
        for _, row in data.iterrows():
            formatted_row: list[str] = []
            for col in columns:
                val = row.get(col, None)
                if val is None or pd.isna(val):
                    formatted_row.append("\\N")
                elif isinstance(val, bool):
                    formatted_row.append("t" if val else "f")
                elif isinstance(val, (float, np.floating)):
                    if math.isnan(val) or math.isinf(val):
                        formatted_row.append("\\N")
                    else:
                        formatted_row.append(str(val))
                else:
                    formatted_row.append(str(val))
            writer.writerow(formatted_row)
    else:
        for item in data:
            formatted_row = []
            for col in columns:
                val = item.get(col)
                if val is None:
                    formatted_row.append("\\N")
                elif isinstance(val, bool):
                    formatted_row.append("t" if val else "f")
                elif isinstance(val, float):
                    if math.isnan(val) or math.isinf(val):
                        formatted_row.append("\\N")
                    else:
                        formatted_row.append(str(val))
                else:
                    formatted_row.append(str(val))
            writer.writerow(formatted_row)

    buffer.seek(0)
    return buffer


def execute_copy(
    conn: Any,
    table_name: str,
    columns: Sequence[str],
    csv_buffer: io.StringIO,
) -> int:
    """Ejecuta la sentencia COPY masiva en PostgreSQL, con fallback a batch insert para tests."""
    cols_str = ", ".join(columns)
    sql_copy = f"COPY {table_name} ({cols_str}) FROM STDIN WITH (FORMAT csv, NULL '\\N')"

    cur = conn.cursor()
    try:
        # 1. psycopg 3: cur.copy()
        if hasattr(cur, "copy"):
            with cur.copy(sql_copy) as copy:
                copy.write(csv_buffer.getvalue())
            conn.commit()
            return int(cur.rowcount) if hasattr(cur, "rowcount") and cur.rowcount >= 0 else 0

        # 2. psycopg2: cur.copy_expert()
        if hasattr(cur, "copy_expert"):
            cur.copy_expert(sql_copy, csv_buffer)
            conn.commit()
            return int(cur.rowcount) if hasattr(cur, "rowcount") and cur.rowcount >= 0 else 0

        # 3. Fallback DB-API / SQLite (para tests locales y CI sin Postgres activo)
        csv_buffer.seek(0)
        reader = csv.reader(csv_buffer, delimiter=",", quotechar='"')
        rows = []
        for r in reader:
            parsed_row = [None if cell == "\\N" else cell for cell in r]
            rows.append(parsed_row)

        if not rows:
            return 0

        placeholders = ", ".join(["?"] * len(columns))
        insert_sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
        cur.executemany(insert_sql, rows)
        conn.commit()
        return len(rows)

    finally:
        with contextlib.suppress(Exception):
            cur.close()
