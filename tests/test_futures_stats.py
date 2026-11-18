"""Tests para el motor estadístico de futuros, DSR y PBO (futures/stats.py).

Verifica exhaustivamente:
1. Primitivas de distribución normal sin SciPy (normal_cdf, inverse_normal_cdf Acklam).
2. Momentos superiores (media, varianza, asimetría, curtosis de Pearson).
3. Ratios de rendimiento institucional (Sharpe, Sortino, Calmar, Max Drawdown).
4. Probabilistic Sharpe Ratio (PSR) bajo asimetría y curtosis no-normales.
5. Expected Maximum Sharpe Ratio (SR_0) y Deflated Sharpe Ratio (DSR).
6. Combinatorially Symmetric Cross-Validation (CSCV) y Probability of Backtest Overfitting (PBO).
7. Casos de borde (series vacías, varianza cero, degradación de Sharpe, etc.).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from krmaazha_binance_mcp.futures.stats import (
    DeflatedSharpeResult,
    PBOResult,
    PerformanceSummary,
    compute_calmar_ratio,
    compute_deflated_sharpe_ratio,
    compute_drawdown_series,
    compute_expected_max_sharpe,
    compute_higher_moments,
    compute_pbo_cscv,
    compute_performance_summary,
    compute_probabilistic_sharpe_ratio,
    compute_sharpe_ratio,
    compute_sortino_ratio,
    inverse_normal_cdf,
    normal_cdf,
)

# ── 1. Primitivas de Distribución Normal (Sin SciPy) ──────────────────────────


def test_normal_cdf_properties() -> None:
    # Simetría y valores de referencia estándar
    assert normal_cdf(0.0) == pytest.approx(0.5, abs=1e-12)
    assert normal_cdf(float("inf")) == 1.0
    assert normal_cdf(float("-inf")) == 0.0
    assert math.isnan(normal_cdf(float("nan")))

    # Simetría Φ(-z) = 1 - Φ(z)
    for z in [0.5, 1.0, 1.645, 1.96, 2.576, 3.0]:
        assert normal_cdf(-z) == pytest.approx(1.0 - normal_cdf(z), abs=1e-10)

    # Puntos críticos estándar (1.96 -> 0.975 aprox)
    assert normal_cdf(1.959963984540054) == pytest.approx(0.975, abs=1e-6)
    assert normal_cdf(1.6448536269514722) == pytest.approx(0.950, abs=1e-6)


def test_inverse_normal_cdf_properties() -> None:
    # Casos extremos
    assert inverse_normal_cdf(0.5) == pytest.approx(0.0, abs=1e-12)
    assert inverse_normal_cdf(0.0) == float("-inf")
    assert inverse_normal_cdf(1.0) == float("inf")

    with pytest.raises(ValueError, match="intervalo abierto"):
        inverse_normal_cdf(-0.1)

    with pytest.raises(ValueError, match="intervalo abierto"):
        inverse_normal_cdf(1.1)

    # Puntos críticos de colas
    z_95 = inverse_normal_cdf(0.95)
    assert z_95 == pytest.approx(1.64485362695, abs=1e-5)

    z_975 = inverse_normal_cdf(0.975)
    assert z_975 == pytest.approx(1.9599639845, abs=1e-5)

    # Simetría inversa: Φ⁻¹(p) = -Φ⁻¹(1 - p)
    for p in [0.001, 0.01, 0.05, 0.1, 0.25, 0.4]:
        assert inverse_normal_cdf(p) == pytest.approx(-inverse_normal_cdf(1.0 - p), abs=1e-9)

    # Roundtrip: Φ(Φ⁻¹(p)) == p
    for p in [0.0001, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 0.9999]:
        assert normal_cdf(inverse_normal_cdf(p)) == pytest.approx(p, abs=1e-8)


# ── 2. Momentos Superiores (Media, Varianza, Skewness, Kurtosis) ───────────────


def test_compute_higher_moments() -> None:
    # Insuficientes observaciones
    assert compute_higher_moments([]) == (0.0, 0.0, 0.0, 3.0)
    assert compute_higher_moments([0.01, 0.02]) == (0.0, 0.0, 0.0, 3.0)

    # Varianza cero
    mean_val, std_val, skew, kurt = compute_higher_moments([0.01, 0.01, 0.01, 0.01])
    assert mean_val == pytest.approx(0.01)
    assert std_val == 0.0
    assert skew == 0.0
    assert kurt == 3.0

    # Distribución simétrica (skewness ≈ 0.0)
    sym_returns = np.array([-0.02, -0.01, 0.0, 0.01, 0.02])
    m, s, sk, kt = compute_higher_moments(sym_returns)
    assert m == pytest.approx(0.0, abs=1e-12)
    assert s > 0.0
    assert sk == pytest.approx(0.0, abs=1e-10)

    # Distribución con sesgo a la derecha (asimetría positiva)
    skewed = np.array([-0.01, -0.01, -0.01, -0.01, 0.08])
    _, _, sk_pos, _ = compute_higher_moments(skewed)
    assert sk_pos > 1.0


# ── 3. Ratios de Rendimiento (Sharpe, Sortino, Calmar, Drawdown) ───────────────


def test_compute_sharpe_ratio() -> None:
    # Serie corta o varianza nula
    assert compute_sharpe_ratio([]) == 0.0
    assert compute_sharpe_ratio([0.01]) == 0.0
    assert compute_sharpe_ratio([0.01, 0.01, 0.01]) == 0.0

    # Retorno diario medio = 0.001, std diaria = 0.01 -> SR diario = 0.1
    # Con A = 365, SR anualizado = 0.1 * sqrt(365) ≈ 1.9105
    np.random.seed(42)
    daily_returns = np.random.normal(0.001, 0.01, size=1000)
    sr = compute_sharpe_ratio(daily_returns, annualization_factor=365)
    mean_obs = np.mean(daily_returns)
    std_obs = np.std(daily_returns, ddof=1)
    expected_sr = (mean_obs / std_obs) * math.sqrt(365)
    assert sr == pytest.approx(expected_sr, abs=1e-6)

    # Con risk-free rate
    sr_rf = compute_sharpe_ratio(daily_returns, risk_free_rate=0.05, annualization_factor=365)
    assert sr_rf < sr


def test_compute_sortino_ratio() -> None:
    assert compute_sortino_ratio([]) == 0.0
    assert compute_sortino_ratio([0.01]) == 0.0

    # Todos retornos positivos (sin downside deviation) -> 999.0
    all_pos = [0.01, 0.02, 0.015, 0.03]
    assert compute_sortino_ratio(all_pos) == 999.0

    # Todos negativos sin variación -> Sortino negativo
    all_neg = [-0.01, -0.01, -0.01]
    assert compute_sortino_ratio(all_neg) < 0.0

    # Serie mixta
    mixed = np.array([0.02, -0.01, 0.03, -0.02, 0.01, 0.04])
    sortino = compute_sortino_ratio(mixed, annualization_factor=365)
    assert sortino > 0.0


def test_compute_drawdown_series() -> None:
    # Vacío
    mdd, dur, s = compute_drawdown_series([])
    assert mdd == 0.0
    assert dur == 0
    assert s.empty

    # Serie que sube constantemente
    up = pd.Series([100.0, 105.0, 110.0, 115.0])
    mdd_up, dur_up, s_up = compute_drawdown_series(up)
    assert mdd_up == 0.0
    assert dur_up == 0
    assert (s_up == 0.0).all()

    # Caída de 100 a 80 (drawdown del 20%) y recuperación
    wealth = pd.Series([100.0, 90.0, 80.0, 85.0, 105.0])
    mdd, dur, s = compute_drawdown_series(wealth)
    assert mdd == pytest.approx(0.20, abs=1e-6)
    assert dur == 3  # bar 1 (90), bar 2 (80), bar 3 (85)
    assert s.iloc[2] == pytest.approx(-0.20, abs=1e-6)


def test_compute_calmar_ratio() -> None:
    assert compute_calmar_ratio([]) == 0.0
    assert compute_calmar_ratio([0.01]) == 0.0

    # Retorno constante sin drawdown
    pos = [0.001] * 365
    assert compute_calmar_ratio(pos, max_drawdown=0.0) == 999.0

    # Con max_drawdown=None (calculado automáticamente desde wealth)
    calmar_auto = compute_calmar_ratio([0.001, -0.005, 0.002] * 50)
    assert calmar_auto != 0.0

    # Con drawdown conocido
    returns = [0.001] * 365
    calmar = compute_calmar_ratio(returns, max_drawdown=0.10, annualization_factor=365)
    assert calmar > 0.0


def test_compute_performance_summary() -> None:
    # Entrada vacía
    summary_empty = compute_performance_summary([])
    assert summary_empty.num_bars == 0
    assert summary_empty.sharpe_ratio == 0.0

    # Serie sintética de 365 días con equity_series None
    np.random.seed(123)
    rets = pd.Series(np.random.normal(0.0008, 0.015, size=365))
    summary_no_equity = compute_performance_summary(rets)
    assert summary_no_equity.max_drawdown > 0.0

    # Con equity_series y turnover_series
    equity = 10_000.0 * np.cumprod(1.0 + rets)
    turnover = pd.Series([0.05] * 365)

    summary = compute_performance_summary(
        rets, equity_series=equity, turnover_series=turnover, annualization_factor=365
    )
    assert isinstance(summary, PerformanceSummary)
    assert summary.num_bars == 365
    assert summary.turnover == pytest.approx(0.05)
    assert summary.max_drawdown > 0.0
    assert summary.annualized_volatility > 0.0
    assert 0.0 <= summary.probabilistic_sharpe_ratio <= 1.0


# ── 4. Probabilistic Sharpe Ratio (PSR) ───────────────────────────────────────


def test_compute_probabilistic_sharpe_ratio() -> None:
    # n_bars <= 1
    assert compute_probabilistic_sharpe_ratio(1.5, num_bars=1) == 0.5

    # Con SR = 0 frente a benchmark 0, PSR = 0.5
    psr_zero = compute_probabilistic_sharpe_ratio(
        observed_sharpe=0.0, benchmark_sharpe=0.0, num_bars=365
    )
    assert psr_zero == pytest.approx(0.5, abs=1e-6)

    # Con SR positivo alto y muestra grande, PSR debe ser cercano a 1.0
    psr_high = compute_probabilistic_sharpe_ratio(
        observed_sharpe=2.5, benchmark_sharpe=0.0, num_bars=500
    )
    assert psr_high > 0.99

    # Impacto de asimetría negativa (reduce el PSR para el mismo Sharpe)
    psr_sym = compute_probabilistic_sharpe_ratio(
        observed_sharpe=1.2, num_bars=365, skewness=0.0, kurtosis=3.0
    )
    psr_neg_skew = compute_probabilistic_sharpe_ratio(
        observed_sharpe=1.2, num_bars=365, skewness=-1.5, kurtosis=5.0
    )
    assert psr_neg_skew < psr_sym


# ── 5. Expected Maximum Sharpe Ratio (SR_0) y Deflated Sharpe Ratio (DSR) ─────


def test_compute_expected_max_sharpe() -> None:
    # 0 o 1 trial
    assert compute_expected_max_sharpe([]) == 0.0
    assert compute_expected_max_sharpe([1.5]) == 0.0
    # Varianza cero
    assert compute_expected_max_sharpe([1.0, 1.0, 1.0]) == 0.0

    # Monotonía: más trials aumentan el Sharpe esperado por ruido
    trials_small = [0.1, -0.2, 0.4, -0.1, 0.3]
    e_max_small = compute_expected_max_sharpe(trials_small, num_trials=5)
    e_max_large = compute_expected_max_sharpe(trials_small, num_trials=100)
    assert e_max_large > e_max_small


def test_compute_deflated_sharpe_ratio() -> None:
    # Estrategia verdaderamente fuerte (SR = 3.0 con 500 días)
    np.random.seed(99)
    alpha_returns = np.random.normal(0.002, 0.01, size=500)
    # N = 10 trials competidores con bajo SR
    competitors = [0.1, 0.2, -0.1, 0.3, 0.0, 0.4, -0.2, 0.15, 0.05, 3.0]

    res = compute_deflated_sharpe_ratio(
        trial_sharpe=3.0,
        all_sharpes=competitors,
        returns=alpha_returns,
        annualization_factor=365,
    )
    assert isinstance(res, DeflatedSharpeResult)
    assert res.observed_sharpe == 3.0
    assert res.num_trials == 10
    assert res.expected_max_sharpe > 0.0
    assert res.deflated_sharpe_ratio > 0.90
    assert res.is_significant_95 is True

    # Estrategia débil en un universo sobreajustado de 100 pruebas
    noise_sharpes = list(np.random.normal(0.0, 0.5, size=100))
    noise_sharpes.append(0.6)  # El "ganador" parece tener SR 0.6
    weak_returns = np.random.normal(0.0001, 0.015, size=200)

    res_weak = compute_deflated_sharpe_ratio(
        trial_sharpe=0.6,
        all_sharpes=noise_sharpes,
        returns=weak_returns,
        annualization_factor=365,
    )
    assert res_weak.expected_max_sharpe > 0.6  # El ruido supera el 0.6
    assert res_weak.deflated_sharpe_ratio < 0.50  # DSR deflactado
    assert res_weak.is_significant_95 is False


# ── 6. Combinatorially Symmetric Cross-Validation (CSCV) y PBO ────────────────


def test_compute_pbo_cscv_validation() -> None:
    # Validaciones de entrada
    dummy = np.zeros((10, 5))
    with pytest.raises(ValueError, match="al menos 2 \\* num_blocks"):
        compute_pbo_cscv(dummy, num_blocks=8)  # 10 < 16

    dummy_t = np.zeros((50, 5))
    with pytest.raises(ValueError, match="num_blocks debe ser un número par"):
        compute_pbo_cscv(dummy_t, num_blocks=7)

    dummy_single = np.zeros((50, 1))
    with pytest.raises(ValueError, match="al menos 2 trials"):
        compute_pbo_cscv(dummy_single, num_blocks=8)


def test_compute_pbo_cscv_noise_overfitting() -> None:
    # 20 estrategias generadas con ruido blanco puro (sin alfa real, N=20, T=300)
    # Al no haber alfa, el ganador in-sample es producto del azar y debe sobreajustar en OOS
    np.random.seed(777)
    pure_noise = np.random.normal(0.0, 0.01, size=(320, 20))

    res = compute_pbo_cscv(pure_noise, num_blocks=8, annualization_factor=365)
    assert isinstance(res, PBOResult)
    # C(8, 4) = 70 combinaciones
    assert res.num_combinations == 70
    assert res.num_trials == 20
    assert res.num_blocks == 8
    assert len(res.lambda_distribution) == 70
    assert len(res.rank_logits) == 70

    # Con ruido blanco puro, el PBO debe ser considerable (habitualmente > 0.40)
    assert res.pbo >= 0.35
    # La degradación de Sharpe debe ser positiva (el Sharpe IS es superior al OOS)
    assert res.sharpe_degradation > 0.0


def test_compute_pbo_cscv_true_alpha() -> None:
    # 1 estrategia con alfa persistente fuerte (drift positivo constante)
    # y 19 estrategias con ruido blanco
    np.random.seed(888)
    mat = np.random.normal(0.0, 0.01, size=(320, 20))
    # Estrategia 0 tiene alfa real
    mat[:, 0] += 0.005

    res = compute_pbo_cscv(mat, num_blocks=8, annualization_factor=365)
    # Dado que la estrategia 0 gana consistentemente en IS y en OOS:
    # PBO debe ser 0.0 o muy bajo
    assert res.pbo <= 0.10
    assert res.is_overfitted is False
