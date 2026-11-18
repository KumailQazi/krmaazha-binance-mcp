"""Motor estadístico cuantitativo y análisis de sobreajuste (futures/stats.py).

Implementa las métricas de rendimiento institucional y correcciones de pruebas
múltiples exigidas por la doctrina (kb://discipline Regla 7 y ROADMAP.md):

1. Métricas de Primer Orden y Ajustadas por Riesgo:
   - Sharpe Ratio anualizado.
   - Sortino Ratio anualizado (semi-desviación downside).
   - Calmar Ratio (CAGR / Max Drawdown).
   - Drawdown máximo y duración máxima en barras.
   - Rotación (Turnover) de cartera.
2. Momentos Estadísticos Superiores:
   - Media, varianza, asimetría (skewness) y curtosis (kurtosis) para distribuciones fat-tailed.
3. Probabilistic Sharpe Ratio (PSR):
   - Bailey & López de Prado (2012): probabilidad de que el Sharpe supere un benchmark
     ajustando por no-normalidad y longitud de muestra.
4. Expected Maximum Sharpe Ratio (SR_0) y Deflated Sharpe Ratio (DSR):
   - Bailey & López de Prado (2014): deflacta el Sharpe observado por el sesgo de selección
     al probar N hipótesis independientes con varianza V.
5. Combinatorially Symmetric Cross-Validation (CSCV) y Probability of Backtest Overfitting (PBO):
   - Bailey, Borwein, López de Prado & Zhu (2016): mide la probabilidad empírica de que
     el modelo ganador en-muestra genere un rendimiento por debajo de la mediana fuera-de-muestra.

RESTRICCIÓN CRÍTICA:
- Sin dependencia de scipy.
- Probabilidades normales calculadas exclusivamente con math.erf e inversión
  racional de alta precisión (algoritmo de Peter J. Acklam con refinamiento Halley).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Constantes universales
EULER_MASCHERONI: float = 0.5772156649015328606
SQRT_2: float = math.sqrt(2.0)
SQRT_2PI: float = math.sqrt(2.0 * math.pi)


# ── 1. Primitivas Matemáticas de Distribución Normal (Sin SciPy) ───────────────


def normal_cdf(z: float) -> float:
    """Calcula la función de distribución acumulada (CDF) normal estándar Φ(z).

    Utiliza exclusivamente math.erf de la biblioteca estándar de Python:
    Φ(z) = 0.5 * (1 + erf(z / sqrt(2)))
    """
    if math.isnan(z):
        return float("nan")
    if z == float("inf"):
        return 1.0
    if z == float("-inf"):
        return 0.0
    return 0.5 * (1.0 + math.erf(z / SQRT_2))


def inverse_normal_cdf(p: float) -> float:
    """Calcula el cuantil normal estándar Φ⁻¹(p) (Probit / Inverse Normal CDF).

    Implementa el algoritmo de aproximación racional de Peter J. Acklam,
    con un paso de refinamiento de Halley para alcanzar precisión de punto flotante
    de 64 bits (~1e-16 de error relativo) en todo el dominio p ∈ (0, 1).
    """
    if p <= 0.0 or p >= 1.0:
        if p == 0.0:
            return float("-inf")
        if p == 1.0:
            return float("inf")
        raise ValueError(f"p debe estar en el intervalo abierto (0, 1), recibido: {p}")

    # Coeficientes polinómicos de Acklam
    a1 = -3.969683028665376e01
    a2 = 2.209460984245205e02
    a3 = -2.759285104469687e02
    a4 = 1.383577518672690e02
    a5 = -3.066479806614716e01
    a6 = 2.506628277459239e00

    b1 = -5.447609879822406e01
    b2 = 1.615858368580409e02
    b3 = -1.556989798598866e02
    b4 = 6.680131188771972e01
    b5 = -1.328068155288572e01

    c1 = -7.784894002430293e-03
    c2 = -3.223964580411365e-01
    c3 = -2.400758277161838e00
    c4 = -2.549732539343734e00
    c5 = 4.374664141464968e00
    c6 = 2.938163982698783e00

    d1 = 7.784695709041462e-03
    d2 = 3.224671290700398e-01
    d3 = 2.445134137142996e00
    d4 = 3.754408661907416e00

    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        # Cola inferior
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / (
            (((d1 * q + d2) * q + d3) * q + d4) * q + 1.0
        )
    elif p <= p_high:
        # Región central
        q = p - 0.5
        r = q * q
        x = (((((a1 * r + a2) * r + a3) * r + a4) * r + a5) * r + a6) * q / (
            ((((b1 * r + b2) * r + b3) * r + b4) * r + b5) * r + 1.0
        )
    else:
        # Cola superior
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -(((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / (
            (((d1 * q + d2) * q + d3) * q + d4) * q + 1.0
        )

    # Refinamiento de Halley para precisión de 64 bits completa
    e = normal_cdf(x) - p
    u = e * SQRT_2PI * math.exp(0.5 * x * x)
    x = x - u / (1.0 + 0.5 * x * u)
    return float(x)


# ── 2. Clases de Datos (Resultados Tipados) ───────────────────────────────────


@dataclass(frozen=True)
class PerformanceSummary:
    """Resumen completo de métricas de rendimiento de una estrategia."""

    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration_bars: int
    turnover: float
    skewness: float
    kurtosis: float
    probabilistic_sharpe_ratio: float
    num_bars: int


@dataclass(frozen=True)
class DeflatedSharpeResult:
    """Resultado del Deflated Sharpe Ratio (DSR) bajo múltiples pruebas."""

    observed_sharpe: float
    expected_max_sharpe: float
    deflated_sharpe_ratio: float
    is_significant_95: bool
    variance_of_sharpes: float
    num_trials: int
    skewness: float
    kurtosis: float


@dataclass(frozen=True)
class PBOResult:
    """Resultado de la Probabilidad de Sobreajuste de Backtest (PBO via CSCV)."""

    pbo: float
    num_combinations: int
    num_trials: int
    num_blocks: int
    average_is_sharpe: float
    average_oos_sharpe: float
    sharpe_degradation: float
    is_overfitted: bool
    lambda_distribution: list[float]
    rank_logits: list[float]


# ── 3. Momentos Estadísticos y Métricas de Rendimiento Individual ─────────────


def compute_higher_moments(
    returns: pd.Series | np.ndarray,
) -> tuple[float, float, float, float]:
    """Calcula (media, desviación estándar, asimetría, curtosis de Pearson).

    Normal distribution: skewness = 0.0, kurtosis = 3.0.
    """
    arr = np.asarray(returns, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = len(arr)
    if n < 3:
        return 0.0, 0.0, 0.0, 3.0

    mean_val = float(np.mean(arr))
    var_sample = float(np.var(arr, ddof=1))
    if var_sample <= 0.0 or math.isnan(var_sample):
        return mean_val, 0.0, 0.0, 3.0

    std_sample = math.sqrt(var_sample)
    diff = arr - mean_val
    m3 = float(np.mean(diff**3))
    m4 = float(np.mean(diff**4))

    skewness = m3 / (std_sample**3)
    kurtosis = m4 / (std_sample**4)
    return mean_val, std_sample, float(skewness), float(kurtosis)


def compute_sharpe_ratio(
    returns: pd.Series | np.ndarray,
    risk_free_rate: float = 0.0,
    annualization_factor: int = 365,
) -> float:
    """Calcula el Sharpe Ratio anualizado de una serie de retornos diarios."""
    arr = np.asarray(returns, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 2:
        return 0.0

    excess_returns = arr - (risk_free_rate / annualization_factor)
    std_val = float(np.std(excess_returns, ddof=1))
    if std_val <= 1e-12 or math.isnan(std_val):
        return 0.0

    mean_val = float(np.mean(excess_returns))
    return float((mean_val / std_val) * math.sqrt(annualization_factor))


def compute_sortino_ratio(
    returns: pd.Series | np.ndarray,
    target_return: float = 0.0,
    annualization_factor: int = 365,
) -> float:
    """Calcula el Sortino Ratio anualizado usando semi-desviación a la baja."""
    arr = np.asarray(returns, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 2:
        return 0.0

    excess_returns = arr - (target_return / annualization_factor)
    downside = np.minimum(0.0, excess_returns)
    downside_var = float(np.mean(downside**2))

    if downside_var <= 1e-16 or math.isnan(downside_var):
        mean_val = float(np.mean(excess_returns))
        return 999.0 if mean_val > 0.0 else 0.0

    downside_std = math.sqrt(downside_var)
    mean_val = float(np.mean(excess_returns))
    return float((mean_val / downside_std) * math.sqrt(annualization_factor))


def compute_drawdown_series(
    wealth_or_equity: pd.Series | np.ndarray,
) -> tuple[float, int, pd.Series]:
    """Calcula el Maximum Drawdown, duración máxima y la serie de drawdown.

    Retorna:
    - max_drawdown: magnitud máxima del drawdown como número positivo
      (ej: 0.25 para 25% de pérdida).
    - max_duration_bars: longitud máxima en barras consecutivas por debajo del HWM previo.
    - drawdown_series: serie de drawdown negativo en cada barra (entre -1.0 y 0.0).
    """
    s = (
        pd.Series(wealth_or_equity, dtype=float).dropna()
        if not isinstance(wealth_or_equity, pd.Series)
        else wealth_or_equity.dropna()
    )
    if len(s) < 1:
        return 0.0, 0, pd.Series(dtype=float)

    hwm = s.cummax()
    dd = (s - hwm) / hwm
    dd = dd.fillna(0.0)

    min_dd = float(dd.min())
    max_dd_magnitude = abs(min_dd) if min_dd < 0.0 else 0.0

    # Calcular duración máxima en drawdown
    max_duration = 0
    current_duration = 0
    for val in dd:
        if val < 0.0:
            current_duration += 1
            if current_duration > max_duration:
                max_duration = current_duration
        else:
            current_duration = 0

    return max_dd_magnitude, max_duration, dd


def compute_calmar_ratio(
    returns: pd.Series | np.ndarray,
    max_drawdown: float | None = None,
    annualization_factor: int = 365,
) -> float:
    """Calcula el Calmar Ratio (CAGR / |Max Drawdown|)."""
    arr = np.asarray(returns, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = len(arr)
    if n < 2:
        return 0.0

    wealth = np.cumprod(1.0 + arr)
    years = n / annualization_factor
    if years <= 0.0:
        return 0.0

    cagr = float((wealth[-1] ** (1.0 / years)) - 1.0) if wealth[-1] > 0.0 else -1.0

    if max_drawdown is None:
        mdd, _, _ = compute_drawdown_series(wealth)
    else:
        mdd = abs(max_drawdown)

    if mdd <= 1e-8:
        return 999.0 if cagr > 0.0 else 0.0

    return float(cagr / mdd)


def compute_performance_summary(
    returns: pd.Series | np.ndarray,
    equity_series: pd.Series | np.ndarray | None = None,
    turnover_series: pd.Series | np.ndarray | None = None,
    risk_free_rate: float = 0.0,
    annualization_factor: int = 365,
) -> PerformanceSummary:
    """Calcula el resumen completo de estadísticas de desempeño de una estrategia."""
    arr = np.asarray(returns, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = len(arr)
    if n < 2:
        return PerformanceSummary(
            total_return=0.0,
            cagr=0.0,
            annualized_volatility=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_duration_bars=0,
            turnover=0.0,
            skewness=0.0,
            kurtosis=3.0,
            probabilistic_sharpe_ratio=0.0,
            num_bars=n,
        )

    wealth = np.cumprod(1.0 + arr)
    tot_return = float(wealth[-1] - 1.0)
    years = n / annualization_factor
    cagr = float((wealth[-1] ** (1.0 / years)) - 1.0) if (wealth[-1] > 0 and years > 0) else -1.0

    mean_d, std_d, skew, kurt = compute_higher_moments(arr)
    ann_vol = std_d * math.sqrt(annualization_factor)

    sharpe = compute_sharpe_ratio(arr, risk_free_rate, annualization_factor)
    sortino = compute_sortino_ratio(arr, risk_free_rate, annualization_factor)

    if equity_series is not None:
        mdd, mdd_dur, _ = compute_drawdown_series(equity_series)
    else:
        mdd, mdd_dur, _ = compute_drawdown_series(wealth)

    calmar = compute_calmar_ratio(arr, max_drawdown=mdd, annualization_factor=annualization_factor)

    avg_turnover = float(np.mean(turnover_series)) if turnover_series is not None else 0.0

    psr = compute_probabilistic_sharpe_ratio(
        observed_sharpe=sharpe,
        benchmark_sharpe=0.0,
        num_bars=n,
        skewness=skew,
        kurtosis=kurt,
        annualization_factor=annualization_factor,
    )

    return PerformanceSummary(
        total_return=tot_return,
        cagr=cagr,
        annualized_volatility=ann_vol,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        max_drawdown=mdd,
        max_drawdown_duration_bars=mdd_dur,
        turnover=avg_turnover,
        skewness=skew,
        kurtosis=kurt,
        probabilistic_sharpe_ratio=psr,
        num_bars=n,
    )


# ── 4. Probabilistic Sharpe Ratio (PSR) ───────────────────────────────────────


def compute_probabilistic_sharpe_ratio(
    observed_sharpe: float,
    benchmark_sharpe: float = 0.0,
    num_bars: int = 365,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    annualization_factor: int = 365,
) -> float:
    """Calcula el Probabilistic Sharpe Ratio (PSR) según Bailey & López de Prado (2012).

    Ajusta el Sharpe ratio observado por el tamaño muestral T y los momentos de tercer
    y cuarto orden (asimetría y curtosis).

    Fórmula:
    sr_hat = observed_sharpe / sqrt(A)
    sr_star = benchmark_sharpe / sqrt(A)
    V(sr_hat) = 1 - gamma_3 * sr_hat + (gamma_4 - 1)/4 * sr_hat^2
    z = (sr_hat - sr_star) * sqrt(T - 1) / sqrt(V)
    PSR = Φ(z)
    """
    if num_bars <= 1:
        return 0.5

    sr_hat = observed_sharpe / math.sqrt(annualization_factor)
    sr_star = benchmark_sharpe / math.sqrt(annualization_factor)

    var_sr = 1.0 - (skewness * sr_hat) + ((kurtosis - 1.0) / 4.0) * (sr_hat**2)
    if var_sr <= 1e-12:
        var_sr = 1e-12

    z = (sr_hat - sr_star) * math.sqrt(num_bars - 1) / math.sqrt(var_sr)
    return float(normal_cdf(z))


# ── 5. Deflated Sharpe Ratio (DSR) y Corrección por Múltiples Pruebas ──────────


def compute_expected_max_sharpe(
    sharpe_trials: Sequence[float] | np.ndarray,
    num_trials: int | None = None,
) -> float:
    """Calcula el Sharpe ratio máximo esperado E[max SR] bajo la hipótesis nula.

    Aproximación de teoría de valores extremos (Bailey & López de Prado, 2014)
    para N pruebas independientes de estrategias sin alfa (SR = 0):

    E[max SR] ≈ sqrt(V) * [ (1 - γ) * Φ⁻¹(1 - 1/N) + γ * Φ⁻¹(1 - 1/(N * e)) ]
    donde γ es la constante de Euler-Mascheroni y V es la varianza muestral entre trials.
    """
    arr = np.asarray(sharpe_trials, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = len(arr) if num_trials is None else num_trials
    if n <= 1:
        return 0.0

    var_trials = float(np.var(arr, ddof=1)) if len(arr) > 1 else 0.0
    if var_trials <= 1e-12:
        return 0.0

    std_trials = math.sqrt(var_trials)

    # Probabilidades en el extremo superior
    p1 = max(1e-12, min(1.0 - 1e-12, 1.0 - (1.0 / n)))
    p2 = max(1e-12, min(1.0 - 1e-12, 1.0 - (1.0 / (n * math.e))))

    z1 = inverse_normal_cdf(p1)
    z2 = inverse_normal_cdf(p2)

    e_max = std_trials * ((1.0 - EULER_MASCHERONI) * z1 + EULER_MASCHERONI * z2)
    return float(max(0.0, e_max))


def compute_deflated_sharpe_ratio(
    trial_sharpe: float,
    all_sharpes: Sequence[float] | np.ndarray,
    returns: pd.Series | np.ndarray,
    annualization_factor: int = 365,
) -> DeflatedSharpeResult:
    """Calcula el Deflated Sharpe Ratio (DSR) de una estrategia seleccionada.

    Deflacta el Sharpe ratio observado frente al sesgo de selección generado
    por probar N configuraciones, la longitud del historial T, y la no-normalidad:
    DSR = PSR(SR_0)

    Retorna un DeflatedSharpeResult con el resultado y el test de significación al 95%.
    """
    sharpes_arr = np.asarray(all_sharpes, dtype=float)
    sharpes_arr = sharpes_arr[~np.isnan(sharpes_arr)]
    n_trials = len(sharpes_arr)

    returns_arr = np.asarray(returns, dtype=float)
    returns_arr = returns_arr[~np.isnan(returns_arr)]
    n_bars = len(returns_arr)

    _, _, skew, kurt = compute_higher_moments(returns_arr)

    var_s = float(np.var(sharpes_arr, ddof=1)) if n_trials > 1 else 0.0
    sr_0 = compute_expected_max_sharpe(sharpes_arr, num_trials=n_trials)

    dsr = compute_probabilistic_sharpe_ratio(
        observed_sharpe=trial_sharpe,
        benchmark_sharpe=sr_0,
        num_bars=n_bars,
        skewness=skew,
        kurtosis=kurt,
        annualization_factor=annualization_factor,
    )

    return DeflatedSharpeResult(
        observed_sharpe=trial_sharpe,
        expected_max_sharpe=sr_0,
        deflated_sharpe_ratio=dsr,
        is_significant_95=(dsr >= 0.95),
        variance_of_sharpes=var_s,
        num_trials=n_trials,
        skewness=skew,
        kurtosis=kurt,
    )


# ── 6. Combinatorially Symmetric Cross-Validation (CSCV) y PBO ────────────────


def compute_pbo_cscv(
    returns_matrix: pd.DataFrame | np.ndarray,
    num_blocks: int = 8,
    annualization_factor: int = 365,
) -> PBOResult:
    """Calcula la Probabilidad de Sobreajuste de Backtest (PBO) mediante CSCV.

    Implementa el framework de Bailey, Borwein, López de Prado & Zhu (2016):
    - Divide T períodos en S bloques contiguos (S par, por defecto 8).
    - Evalúa las C = C(S, S/2) combinaciones de In-Sample (IS) vs Out-of-Sample (OOS).
    - Para cada combinación c:
        1. Identifica el modelo óptimo n* en IS (mayor Sharpe ratio).
        2. Mide el rango relativo percentil λ_c del modelo n* en OOS.
        3. Si λ_c <= 0.5 (rendimiento OOS por debajo de la mediana), cuenta como sobreajuste.
    - PBO = (1 / C) * Σ I(λ_c <= 0.5)

    Retorna PBOResult con la tasa PBO, logit de rangos y degradación de Sharpe.
    """
    mat = (
        returns_matrix.to_numpy(dtype=float)
        if isinstance(returns_matrix, pd.DataFrame)
        else np.asarray(returns_matrix, dtype=float)
    )

    t_obs, n_trials = mat.shape
    if t_obs < num_blocks * 2:
        raise ValueError(
            f"El número de observaciones T ({t_obs}) debe ser al menos "
            f"2 * num_blocks ({num_blocks * 2})"
        )
    if num_blocks % 2 != 0:
        raise ValueError(f"num_blocks debe ser un número par, recibido: {num_blocks}")
    if n_trials < 2:
        raise ValueError(
            f"PBO requiere al menos 2 trials o estrategias para evaluar, recibido: {n_trials}"
        )

    # 1. Partición de T en S bloques contiguos
    block_size = t_obs // num_blocks
    blocks: list[np.ndarray] = []
    for s_idx in range(num_blocks):
        start = s_idx * block_size
        end = (s_idx + 1) * block_size if s_idx < num_blocks - 1 else t_obs
        blocks.append(mat[start:end, :])

    # 2. Generar todas las C(S, S/2) combinaciones
    k = num_blocks // 2
    combinations = list(itertools.combinations(range(num_blocks), k))
    total_combs = len(combinations)

    overfit_count = 0
    lambda_list: list[float] = []
    logits_list: list[float] = []
    is_best_sharpes: list[float] = []
    oos_corresponding_sharpes: list[float] = []

    sqrt_ann = math.sqrt(annualization_factor)

    for is_indices in combinations:
        is_set = set(is_indices)
        oos_indices = [idx for idx in range(num_blocks) if idx not in is_set]

        # Matrices compuestas IS y OOS
        mat_is = np.vstack([blocks[i] for i in is_indices])
        mat_oos = np.vstack([blocks[i] for i in oos_indices])

        # Calcular Sharpe en In-Sample para cada una de las N estrategias
        mean_is = np.mean(mat_is, axis=0)
        std_is = np.std(mat_is, axis=0, ddof=1)
        std_is[std_is < 1e-12] = 1e-12
        sharpes_is = (mean_is / std_is) * sqrt_ann

        # Mejor estrategia In-Sample n*
        n_star = int(np.argmax(sharpes_is))
        best_is_sr = float(sharpes_is[n_star])

        # Rendimiento Out-of-Sample para todas las estrategias
        mean_oos = np.mean(mat_oos, axis=0)
        std_oos = np.std(mat_oos, axis=0, ddof=1)
        std_oos[std_oos < 1e-12] = 1e-12
        sharpes_oos = (mean_oos / std_oos) * sqrt_ann
        oos_sr = float(sharpes_oos[n_star])

        # Rango percentil de n* en OOS: λ_c = rank(n*) / (N + 1)
        rank_n_star = float(np.sum(sharpes_oos <= oos_sr))
        lambda_c = rank_n_star / (n_trials + 1.0)
        lambda_list.append(lambda_c)

        # Logit de rango
        lambda_clamped = max(1e-6, min(1.0 - 1e-6, lambda_c))
        logit_c = math.log(lambda_clamped / (1.0 - lambda_clamped))
        logits_list.append(logit_c)

        is_best_sharpes.append(best_is_sr)
        oos_corresponding_sharpes.append(oos_sr)

        # Si el rango es <= mediana (0.5), el ganador IS rindió por debajo de la mediana en OOS
        if lambda_c <= 0.5:
            overfit_count += 1

    pbo = float(overfit_count / total_combs)
    avg_is_sr = float(np.mean(is_best_sharpes))
    avg_oos_sr = float(np.mean(oos_corresponding_sharpes))
    degradation = float(avg_is_sr - avg_oos_sr)

    return PBOResult(
        pbo=pbo,
        num_combinations=total_combs,
        num_trials=n_trials,
        num_blocks=num_blocks,
        average_is_sharpe=avg_is_sr,
        average_oos_sharpe=avg_oos_sr,
        sharpe_degradation=degradation,
        is_overfitted=(pbo > 0.50),
        lambda_distribution=lambda_list,
        rank_logits=logits_list,
    )
