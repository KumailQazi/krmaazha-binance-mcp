-- 002_live_vs_model.sql: Tabla de auditoría entre ejecuciones reales y modelo teórico

CREATE TABLE IF NOT EXISTS live_vs_model (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol TEXT NOT NULL,
    fill_time TIMESTAMPTZ NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    qty NUMERIC(18, 8) NOT NULL CHECK (qty > 0),
    model_price NUMERIC(18, 8) NOT NULL,
    realized_price NUMERIC(18, 8) NOT NULL,
    model_fee NUMERIC(18, 8) NOT NULL,
    realized_fee NUMERIC(18, 8) NOT NULL,
    model_slippage_cost NUMERIC(18, 8) NOT NULL,
    realized_slippage_cost NUMERIC(18, 8) NOT NULL,
    model_funding_cost NUMERIC(18, 8) NOT NULL,
    realized_funding_cost NUMERIC(18, 8) NOT NULL,
    model_pnl NUMERIC(18, 8) NOT NULL,
    realized_pnl NUMERIC(18, 8) NOT NULL,
    discrepancy_bps DOUBLE PRECISION NOT NULL,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_live_vs_model_symbol_time
    ON live_vs_model (symbol, fill_time);

