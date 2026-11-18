-- 001_initial_schema.sql: Esquema inicial para investigación de futuros USDⓈ-M

-- 1. Tabla de control de migraciones con checksum SHA-256
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INT PRIMARY KEY,
    name TEXT NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Metadatos de corridas de investigación walk-forward
CREATE TABLE IF NOT EXISTS research_runs (
    run_id UUID PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    config_json JSONB NOT NULL,
    n_candles INT NOT NULL,
    n_windows INT NOT NULL,
    oos_return_pct DOUBLE PRECISION NOT NULL,
    oos_sharpe DOUBLE PRECISION NOT NULL,
    oos_sortino DOUBLE PRECISION NOT NULL,
    oos_max_drawdown DOUBLE PRECISION NOT NULL,
    deflated_sharpe_ratio DOUBLE PRECISION NOT NULL,
    pbo DOUBLE PRECISION,
    gate_passed BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_research_runs_strategy_symbol
    ON research_runs (strategy_name, symbol);

-- 3. Todos los trials (parámetros y métricas de cada hipótesis evaluada)
CREATE TABLE IF NOT EXISTS trials (
    trial_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES research_runs(run_id) ON DELETE CASCADE,
    trial_index INT NOT NULL,
    params_json JSONB NOT NULL,
    in_sample_sharpe DOUBLE PRECISION NOT NULL,
    in_sample_return_pct DOUBLE PRECISION NOT NULL,
    out_of_sample_sharpe DOUBLE PRECISION,
    out_of_sample_return_pct DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_trials_run_id ON trials (run_id);

-- 4. Matriz completa de retornos diarios por trial (tabla de alto volumen para COPY)
CREATE TABLE IF NOT EXISTS trial_period_returns (
    trial_id BIGINT NOT NULL REFERENCES trials(trial_id) ON DELETE CASCADE,
    bar_time TIMESTAMPTZ NOT NULL,
    is_oos BOOLEAN NOT NULL DEFAULT true,
    daily_return DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (trial_id, bar_time)
);

CREATE INDEX IF NOT EXISTS idx_trial_returns_bar_time ON trial_period_returns (bar_time);

-- 5. Ventanas walk-forward individuales
CREATE TABLE IF NOT EXISTS walk_forward_windows (
    window_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES research_runs(run_id) ON DELETE CASCADE,
    window_index INT NOT NULL,
    train_start TIMESTAMPTZ NOT NULL,
    train_end TIMESTAMPTZ NOT NULL,
    test_start TIMESTAMPTZ NOT NULL,
    test_end TIMESTAMPTZ NOT NULL,
    best_params_json JSONB NOT NULL,
    train_metric DOUBLE PRECISION NOT NULL,
    test_return_pct DOUBLE PRECISION NOT NULL,
    buy_hold_return_pct DOUBLE PRECISION NOT NULL,
    beat_buy_hold BOOLEAN NOT NULL,
    trades_count INT NOT NULL,
    fee_cost NUMERIC(18, 8) NOT NULL,
    slippage_cost NUMERIC(18, 8) NOT NULL,
    funding_cost NUMERIC(18, 8) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wf_windows_run_id ON walk_forward_windows (run_id);

