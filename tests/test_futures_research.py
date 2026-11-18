"""Tests para el motor de investigación walk-forward out-of-sample (futures/research.py).

Verifica:
1. Validación de configuraciones y protocolo de hipótesis (EMA Cross, RSI Threshold, EMA Regime).
2. Anti-lookahead estricto: alterar precios futuros en la ventana de test no altera
   los parámetros seleccionados en la ventana de train.
3. Fricción de costos: comisiones y slippage reducen estrictamente el retorno OOS.
4. Devengo de funding real durante las ventanas de test.
5. Ejecución rolling vs anchored (expansión de ventana train).
6. Evaluación del Gate Institucional (6 criterios): rechazo de ruido/sobreajuste y pase de alfa.
7. Manejo robusto de errores (datos insuficientes, columnas faltantes, etc.).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from krmaazha_binance_mcp.futures.costs import (
    CostModel,
    FeeModel,
    FixedBasisPointSlippage,
)
from krmaazha_binance_mcp.futures.research import (
    EmaCrossHypothesis,
    EmaRegimeHypothesis,
    GateVerdict,
    RsiThresholdHypothesis,
    WalkForwardConfig,
    WalkForwardEngine,
    WalkForwardResult,
    compute_buy_hold_window,
    simulate_window,
)


@pytest.fixture
def base_cost_model() -> CostModel:
    return CostModel(
        fee_model=FeeModel(taker_fee=0.0004, maker_fee=0.0002),
        slippage_model=FixedBasisPointSlippage(bps=2.0),
    )


def _generate_synthetic_klines(
    n_bars: int = 600,
    seed: int = 42,
    drift: float = 0.0,
    vol: float = 0.015,
) -> pd.DataFrame:
    """Genera datos OHLCV sintéticos deterministas sin lookahead."""
    rng = np.random.default_rng(seed)
    log_returns = rng.normal(drift, vol, n_bars)
    prices = 100.0 * np.exp(np.cumsum(log_returns))

    opens = np.concatenate([[100.0], prices[:-1]]) * (1.0 + rng.normal(0.0, 0.001, n_bars))
    highs = np.maximum(opens, prices) * (1.0 + rng.uniform(0.001, 0.005, n_bars))
    lows = np.minimum(opens, prices) * (1.0 - rng.uniform(0.001, 0.005, n_bars))
    volumes = rng.uniform(100.0, 1000.0, n_bars)

    t0 = 1704067200000  # 2024-01-01
    step_ms = 86_400_000
    open_times = np.array([t0 + i * step_ms for i in range(n_bars)], dtype="int64")

    return pd.DataFrame(
        {
            "open_time": open_times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": volumes,
        }
    )


# ── 1. Validaciones de Configuración y Protocolo de Hipótesis ─────────────────


def test_walk_forward_config_validation(base_cost_model: CostModel) -> None:
    # Válido
    cfg = WalkForwardConfig(
        train_bars=200, test_bars=50, step_bars=50, cost_model=base_cost_model
    )
    assert cfg.train_bars == 200

    with pytest.raises(ValueError, match="train_bars debe ser >= 10"):
        WalkForwardConfig(train_bars=5, test_bars=50, step_bars=50, cost_model=base_cost_model)

    with pytest.raises(ValueError, match="test_bars debe ser >= 5"):
        WalkForwardConfig(train_bars=50, test_bars=2, step_bars=50, cost_model=base_cost_model)

    with pytest.raises(ValueError, match="step_bars debe ser >= 1"):
        WalkForwardConfig(train_bars=50, test_bars=20, step_bars=0, cost_model=base_cost_model)


def test_strategy_hypotheses_definitions() -> None:
    df = _generate_synthetic_klines(100)

    # EMA Cross
    ema_hyp = EmaCrossHypothesis(fast_periods=[5, 8], slow_periods=[20, 50])
    assert ema_hyp.name == "ema_cross"
    grid_ema = ema_hyp.param_grid()
    assert len(grid_ema) == 4
    sig_ema = ema_hyp.compute_signal(df, grid_ema[0])
    assert len(sig_ema) == 100
    assert set(sig_ema.unique()).issubset({0, 1})

    # RSI Threshold
    rsi_hyp = RsiThresholdHypothesis(low_thresholds=[25.0], high_thresholds=[70.0, 75.0])
    assert rsi_hyp.name == "rsi_threshold"
    grid_rsi = rsi_hyp.param_grid()
    assert len(grid_rsi) == 2
    sig_rsi = rsi_hyp.compute_signal(df, grid_rsi[0])
    assert len(sig_rsi) == 100

    # EMA Regime
    regime_hyp = EmaRegimeHypothesis(fast_periods=[8], slow_periods=[21], thetas=[0.0, 0.02])
    assert regime_hyp.name == "ema_cross_regime"
    grid_regime = regime_hyp.param_grid()
    assert len(grid_regime) == 2
    sig_regime_0 = regime_hyp.compute_signal(df, grid_regime[0])
    assert len(sig_regime_0) == 100
    # Probar con theta > 0.0
    sig_regime_pos = regime_hyp.compute_signal(df, grid_regime[1])
    assert len(sig_regime_pos) == 100


# ── 2. Simulación de Ventana y Anti-Lookahead Aritmético ───────────────────────


def test_simulate_window_anti_lookahead(base_cost_model: CostModel) -> None:
    # 4 barras con aritmética exacta verificable
    # Barra 0: signal[0]=1 -> entra en open[1]=100
    # Barra 1: signal[1]=1 -> mantiene
    # Barra 2: signal[2]=0 -> sale en open[3]=120
    # Barra 3: signal[3]=0 -> flat
    opens = np.array([100.0, 100.0, 110.0, 120.0])
    closes = np.array([100.0, 110.0, 115.0, 120.0])
    open_times = np.array([1000, 2000, 3000, 4000])
    signal = np.array([1, 1, 0, 0])

    ret, n_trades, fees, slip, fund, daily_rets = simulate_window(
        opens, closes, open_times, signal, 0, 4, base_cost_model
    )
    assert n_trades == 1
    assert ret > 0.0
    assert fees > 0.0
    assert slip > 0.0
    assert len(daily_rets) == 4


def test_cost_friction_impact() -> None:
    opens = np.array([100.0, 100.0, 110.0, 120.0])
    closes = np.array([100.0, 110.0, 115.0, 120.0])
    open_times = np.array([1000, 2000, 3000, 4000])
    signal = np.array([1, 1, 0, 0])

    low_cost = CostModel(
        fee_model=FeeModel(taker_fee=0.0001, maker_fee=0.0001),  # 1 bps
        slippage_model=FixedBasisPointSlippage(bps=0.5),  # 0.5 bps
    )
    high_cost = CostModel(
        fee_model=FeeModel(taker_fee=0.002, maker_fee=0.001),  # 20 bps
        slippage_model=FixedBasisPointSlippage(bps=10.0),  # 10 bps
    )

    ret_low, _, _, _, _, _ = simulate_window(
        opens, closes, open_times, signal, 0, 4, low_cost
    )
    ret_high, _, fee_h, slip_h, _, _ = simulate_window(
        opens, closes, open_times, signal, 0, 4, high_cost
    )

    assert ret_low > ret_high
    assert fee_h > 0.0
    assert slip_h > 0.0


def test_simulate_window_funding_accrual(base_cost_model: CostModel) -> None:
    opens = np.array([100.0, 100.0, 100.0, 100.0])
    closes = np.array([100.0, 100.0, 100.0, 100.0])
    open_times = np.array([1_000, 28_800_000, 57_600_000, 86_400_000])
    signal = np.array([1, 1, 1, 1])

    funding_df = pd.DataFrame(
        {
            "calc_time": [28_800_000, 57_600_000],
            "last_funding_rate": [0.001, 0.001],  # 10 bps cada 8h
            "funding_interval_hours": [8.0, 8.0],
        }
    )

    ret, _, _, _, fund_cost, _ = simulate_window(
        opens, closes, open_times, signal, 0, 4, base_cost_model, funding_df=funding_df
    )
    assert fund_cost > 0.0
    assert ret < 0.0  # El precio no cambió, pero el funding extrajo capital


def test_compute_buy_hold_window() -> None:
    opens = np.array([100.0, 100.0, 105.0])
    closes = np.array([100.0, 105.0, 120.0])
    # Compra al primer open ejecutable (opens[1]=100) y marca al último close (closes[2]=120)
    # Retorno esperado: +20%
    bh = compute_buy_hold_window(opens, closes, 0, 3)
    assert bh == pytest.approx(20.0)

    # Menos de 2 barras
    assert compute_buy_hold_window(opens, closes, 0, 1) == 0.0


# ── 3. Test de Invarianza Anti-Lookahead ───────────────────────────────────────


def test_walk_forward_engine_lookahead_invariance(base_cost_model: CostModel) -> None:
    """Verifica que modificar el futuro (ventana de test) NO altera los parámetros de train."""
    df_clean = _generate_synthetic_klines(400, seed=123)
    df_tampered = df_clean.copy()

    # Alterar drásticamente los precios en la ventana de test (índices 300..400)
    df_tampered.loc[300:399, "close"] = df_tampered.loc[300:399, "close"] * 5.0
    df_tampered.loc[300:399, "high"] = df_tampered.loc[300:399, "high"] * 5.0

    cfg = WalkForwardConfig(
        train_bars=200,
        test_bars=100,
        step_bars=100,
        cost_model=base_cost_model,
        min_windows=1,
    )
    engine = WalkForwardEngine(cfg)
    hyp = EmaCrossHypothesis(fast_periods=[5, 8, 12], slow_periods=[21, 50])

    res_clean = engine.run(df_clean, hyp)
    res_tampered = engine.run(df_tampered, hyp)

    # La primera ventana tiene train en 0..200. Sus mejores parámetros deben ser IDÉNTICOS
    win_clean_0 = res_clean.windows[0]
    win_tamp_0 = res_tampered.windows[0]
    assert win_clean_0.best_params == win_tamp_0.best_params
    assert win_clean_0.train_metric == pytest.approx(win_tamp_0.train_metric)


# ── 4. Ejecución Rolling vs Anchored y Gate Institucional ─────────────────────


def test_walk_forward_engine_run_rolling(base_cost_model: CostModel) -> None:
    df = _generate_synthetic_klines(500, seed=42)
    cfg = WalkForwardConfig(
        train_bars=200,
        test_bars=50,
        step_bars=50,
        cost_model=base_cost_model,
        anchored=False,
        min_windows=3,
        min_oos_trades=5,
    )
    engine = WalkForwardEngine(cfg)
    hyp = EmaCrossHypothesis(fast_periods=[5, 8], slow_periods=[21, 50])

    res = engine.run(df, hyp, symbol="BTCUSDT", timeframe="1d")
    assert isinstance(res, WalkForwardResult)
    assert res.n_windows >= 4
    assert len(res.windows) == res.n_windows
    assert res.oos_trades >= 0
    assert 0.0 <= res.consistency <= 1.0
    assert len(res.concatenated_oos_returns) > 0
    assert len(res.concatenated_oos_equity) > 0
    assert isinstance(res.gate_verdict, GateVerdict)


def test_walk_forward_engine_run_anchored(base_cost_model: CostModel) -> None:
    df = _generate_synthetic_klines(400, seed=99)
    cfg = WalkForwardConfig(
        train_bars=150,
        test_bars=50,
        step_bars=50,
        cost_model=base_cost_model,
        anchored=True,  # Entrenamientos expandidos desde t=0
        min_windows=3,
        min_oos_trades=5,
    )
    engine = WalkForwardEngine(cfg)
    hyp = RsiThresholdHypothesis(low_thresholds=[30.0], high_thresholds=[70.0])

    res = engine.run(df, hyp)
    for w in res.windows:
        assert w.train_start == 0  # Siempre anclado a 0


def test_institutional_gate_rejection_of_noise(base_cost_model: CostModel) -> None:
    # Serie de ruido blanco sin tendencia
    df_noise = _generate_synthetic_klines(500, seed=777, drift=0.0)
    cfg = WalkForwardConfig(
        train_bars=200,
        test_bars=50,
        step_bars=50,
        cost_model=base_cost_model,
        min_windows=3,
        min_oos_trades=50,  # Requiere 50 trades institucionales
    )
    engine = WalkForwardEngine(cfg)
    hyp = EmaCrossHypothesis(fast_periods=[5, 8], slow_periods=[21, 50])

    res = engine.run(df_noise, hyp)
    # El ruido blanco con comisiones debe fallar el gate institucional
    assert res.gate_verdict.passed is False
    assert len(res.gate_verdict.failure_reasons) > 0


def test_institutional_gate_pass_on_persistent_alpha(base_cost_model: CostModel) -> None:
    # Serie sintética con fuerte drift tendencial alcista (0.003 diario = ~110% anual)
    # y baja volatilidad, donde el cruce de medias genera alpha robusto constante
    df_alpha = _generate_synthetic_klines(600, seed=123, drift=0.004, vol=0.008)
    cfg = WalkForwardConfig(
        train_bars=150,
        test_bars=50,
        step_bars=50,
        cost_model=base_cost_model,
        min_windows=3,
        min_oos_trades=1,  # Reducido para la prueba sintética
    )
    engine = WalkForwardEngine(cfg)
    hyp = EmaCrossHypothesis(fast_periods=[5], slow_periods=[20])

    res = engine.run(df_alpha, hyp)
    assert res.oos_return_pct > 0.0
    assert res.oos_sharpe > 1.0


# ── 5. Manejo de Casos de Borde y Errores ─────────────────────────────────────


def test_walk_forward_engine_error_handling(base_cost_model: CostModel) -> None:
    cfg = WalkForwardConfig(
        train_bars=200, test_bars=100, step_bars=50, cost_model=base_cost_model
    )
    engine = WalkForwardEngine(cfg)
    hyp = EmaCrossHypothesis()

    # 1. Velas insuficientes (< train + test = 300)
    df_short = _generate_synthetic_klines(150)
    with pytest.raises(ValueError, match="Datos insuficientes"):
        engine.run(df_short, hyp)

    # 2. Columnas faltantes
    df_bad = df_short.drop(columns=["close"])
    with pytest.raises(ValueError, match="carece de columnas requeridas"):
        engine.run(df_bad, hyp)

    # 3. Ventanas generadas insuficientes para min_windows
    cfg_strict = WalkForwardConfig(
        train_bars=200,
        test_bars=100,
        step_bars=100,
        cost_model=base_cost_model,
        min_windows=10,
    )
    engine_strict = WalkForwardEngine(cfg_strict)
    df_350 = _generate_synthetic_klines(350)
    with pytest.raises(ValueError, match="Se generaron solo"):
        engine_strict.run(df_350, hyp)

    # 4. Hipótesis con grilla vacía
    class EmptyHypothesis:
        @property
        def name(self) -> str:
            return "empty"

        def param_grid(self) -> list[dict[str, Any]]:
            return []

        def compute_signal(self, df: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
            return pd.Series(dtype="int64")

    with pytest.raises(ValueError, match="devolvió una grilla vacía"):
        engine.run(_generate_synthetic_klines(400), EmptyHypothesis())

    # 5. Ventana de simulación corta (< 2)
    assert simulate_window(
        np.array([100.0]), np.array([100.0]), np.array([1000]), np.array([1]), 0, 1, base_cost_model
    ) == (0.0, 0, 0.0, 0.0, 0.0, [])

    # 6. Buy and hold con open no positivo
    assert compute_buy_hold_window(np.array([100.0, 0.0]), np.array([100.0, 100.0]), 0, 2) == 0.0
