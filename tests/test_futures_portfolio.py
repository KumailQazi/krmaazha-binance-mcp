"""Tests para el motor de cartera de futuros USDⓈ-M (futures/portfolio.py).

Verifica los pilares del roadmap:
1. Multi-símbolo Long/Short simultáneo.
2. Nocional vs Margen, apalancamiento bruto/neto y ratio de margen.
3. Volatility Targeting sin lookahead con tope de apalancamiento.
4. Devengo real de funding integrado con futures/costs.py.
5. Aserción estricta de proximidad y quiebra por liquidación (end-of-bar e intra-bar).
6. Liquidación forzosa en delisteos de activos.
"""

from __future__ import annotations

import pandas as pd
import pytest

from krmaazha_binance_mcp.futures.costs import (
    CostModel,
    FeeModel,
    FixedBasisPointSlippage,
)
from krmaazha_binance_mcp.futures.portfolio import (
    AccountLiquidatedError,
    FuturesPortfolioSimulator,
    MarginTierConfig,
    VolatilityTargetConfig,
    compute_rolling_realized_vol,
)


@pytest.fixture
def base_cost_model() -> CostModel:
    return CostModel(
        fee_model=FeeModel(taker_fee=0.0004, maker_fee=0.0002),
        slippage_model=FixedBasisPointSlippage(bps=2.0),
    )


# ── 1. Validaciones de Configuración ─────────────────────────────────────────


def test_volatility_target_config_validation() -> None:
    # Válido
    cfg = VolatilityTargetConfig(target_annual_vol=0.15, lookback_days=30, max_gross_leverage=2.0)
    assert cfg.target_annual_vol == 0.15

    with pytest.raises(ValueError, match="target_annual_vol debe ser positivo"):
        VolatilityTargetConfig(target_annual_vol=0.0)

    with pytest.raises(ValueError, match="lookback_days debe ser >= 2"):
        VolatilityTargetConfig(target_annual_vol=0.15, lookback_days=1)

    with pytest.raises(ValueError, match="max_gross_leverage debe ser positivo"):
        VolatilityTargetConfig(target_annual_vol=0.15, max_gross_leverage=0.0)

    with pytest.raises(ValueError, match="min_vol_floor debe ser positivo"):
        VolatilityTargetConfig(target_annual_vol=0.15, min_vol_floor=0.0)


def test_margin_tier_config_validation() -> None:
    m_cfg = MarginTierConfig(base_mmr=0.005, liquidation_fee_rate=0.015)
    assert m_cfg.base_mmr == 0.005

    with pytest.raises(ValueError, match="base_mmr debe ser positivo"):
        MarginTierConfig(base_mmr=0.0)

    with pytest.raises(ValueError, match="liquidation_fee_rate no puede ser negativo"):
        MarginTierConfig(liquidation_fee_rate=-0.01)


def test_simulator_init_validation(base_cost_model: CostModel) -> None:
    with pytest.raises(ValueError, match="initial_equity debe ser positivo"):
        FuturesPortfolioSimulator(initial_equity=0.0, cost_model=base_cost_model)


# ── 2. Cálculo de Volatilidad Rodante ─────────────────────────────────────────


def test_compute_rolling_realized_vol() -> None:
    # Serie de 30 días con volatilidad oscilante (5% arriba/abajo)
    prices = pd.Series([100.0 * (1.05 if i % 2 == 0 else 0.95) for i in range(35)])
    vol = compute_rolling_realized_vol(prices, lookback=30)
    assert vol > 0.05

    # Serie vacía o muy corta devuelve el piso (min_floor)
    assert compute_rolling_realized_vol(pd.Series([100.0]), lookback=30) == 0.05
    assert compute_rolling_realized_vol(pd.Series(dtype=float), lookback=30) == 0.05


# ── 3. Multi-Símbolo Long/Short y Nocional vs Margen ─────────────────────────


def test_multi_symbol_long_short_simulation(base_cost_model: CostModel) -> None:
    t0 = 1704067200000  # Día 1
    t1 = t0 + 86_400_000  # Día 2

    # Señal: Long 50% BTC, Short 50% ETH
    signals = pd.DataFrame(
        {"BTCUSDT": [0.5, 0.5], "ETHUSDT": [-0.5, -0.5]},
        index=[t0, t1],
    )
    # Precios: BTC sube de 50k a 52k (+4%), ETH baja de 3000 a 2850 (-5%)
    closes = pd.DataFrame(
        {"BTCUSDT": [50_000.0, 52_000.0], "ETHUSDT": [3_000.0, 2_850.0]},
        index=[t0, t1],
    )

    sim = FuturesPortfolioSimulator(initial_equity=100_000.0, cost_model=base_cost_model)
    history, decomp = sim.run(signals, closes)

    assert len(history) == 2
    snap_day2 = history.loc[t1]

    # Gross notional = |BTC| + |ETH| ≈ 50k + 50k = 100k
    assert snap_day2["gross_notional"] == pytest.approx(100_000.0, rel=0.1)
    # Gross leverage debe ser ~1.0
    assert snap_day2["gross_leverage"] == pytest.approx(1.0, rel=0.1)
    # Net leverage = BTC(long) + ETH(short) ≈ 0.0
    assert snap_day2["net_leverage"] == pytest.approx(0.0, abs=0.1)

    # Ambos lados ganaron dinero: BTC Long ganó, ETH Short ganó
    assert decomp.gross_pnl > 0.0
    assert decomp.net_pnl > 0.0
    assert (
        decomp.net_pnl
        == pytest.approx(
            decomp.gross_pnl - decomp.fee_cost - decomp.slippage_cost + decomp.funding_pnl
        )
    )


# ── 4. Devengo Real de Funding en Cartera ─────────────────────────────────────


def test_portfolio_funding_accrual(base_cost_model: CostModel) -> None:
    t0 = 1704067200000
    t1 = t0 + 86_400_000

    # Long 1.0 BTC mantenido de t0 a t1
    signals = pd.DataFrame({"BTCUSDT": [1.0, 1.0]}, index=[t0, t1])
    closes = pd.DataFrame({"BTCUSDT": [50_000.0, 50_000.0]}, index=[t0, t1])

    # 3 eventos de funding en el día: 0.0001 cada uno (suma 0.0003 = 0.03%)
    funding_btc = pd.DataFrame(
        [
            {"calc_time": t0 + 1000, "funding_interval_hours": 8.0, "last_funding_rate": 0.0001},
            {
                "calc_time": t0 + 8 * 3600 * 1000,
                "funding_interval_hours": 8.0,
                "last_funding_rate": 0.0001,
            },
            {
                "calc_time": t0 + 16 * 3600 * 1000,
                "funding_interval_hours": 8.0,
                "last_funding_rate": 0.0001,
            },
        ]
    )

    sim = FuturesPortfolioSimulator(initial_equity=50_000.0, cost_model=base_cost_model)
    _, decomp = sim.run(signals, closes, funding_dfs={"BTCUSDT": funding_btc})

    # Long paga funding con tasa positiva: flujo negativo
    assert decomp.funding_pnl < 0.0
    # Nocional ~50k * 0.0003 ≈ -$15 de funding
    assert decomp.funding_pnl == pytest.approx(-15.0, rel=0.1)


# ── 5. Volatility Targeting y Leverage Cap ───────────────────────────────────


def test_volatility_targeting_and_leverage_cap(base_cost_model: CostModel) -> None:
    dates = [1704067200000 + i * 86_400_000 for i in range(40)]

    # BTC con baja volatilidad (0.1% diario), SOL con alta volatilidad (3% diario)
    btc_prices = [50_000.0 * (1.001**i) for i in range(40)]
    sol_prices = [100.0 * (1.03 if i % 2 == 0 else 0.97) for i in range(40)]

    signals = pd.DataFrame({"BTCUSDT": [1.0] * 40, "SOLUSDT": [1.0] * 40}, index=dates)
    closes = pd.DataFrame({"BTCUSDT": btc_prices, "SOLUSDT": sol_prices}, index=dates)

    vol_cfg = VolatilityTargetConfig(
        target_annual_vol=0.20, lookback_days=15, max_gross_leverage=1.8
    )
    sim = FuturesPortfolioSimulator(
        initial_equity=100_000.0, cost_model=base_cost_model, vol_config=vol_cfg
    )

    history, _ = sim.run(signals, closes)

    for _, row in history.iterrows():
        # El apalancamiento bruto se ciñe al techo de 1.8x (permitiendo margen mínimo por fricción)
        assert row["gross_leverage"] <= 1.85


# ── 6. Aserción de Proximidad y Quiebra por Liquidación ───────────────────────


def test_end_of_bar_liquidation_assertion(base_cost_model: CostModel) -> None:
    t0 = 1704067200000
    t1 = t0 + 86_400_000

    # Long 5x apalancado (sobre equity 10k, nocional 50k = 1 BTC a 50k)
    signals = pd.DataFrame({"BTCUSDT": [5.0, 5.0]}, index=[t0, t1])
    # Caída del 25% (de 50k a 37.5k): la pérdida es 12.5k, mayor al equity inicial de 10k
    closes = pd.DataFrame({"BTCUSDT": [50_000.0, 37_500.0]}, index=[t0, t1])

    sim = FuturesPortfolioSimulator(
        initial_equity=10_000.0, cost_model=base_cost_model, assert_liquidation=True
    )

    with pytest.raises(AccountLiquidatedError) as exc_info:
        sim.run(signals, closes)

    assert "CUENTA LIQUIDADA" in str(exc_info.value)
    assert exc_info.value.open_time == t1


def test_intra_bar_wick_liquidation_assertion(base_cost_model: CostModel) -> None:
    t0 = 1704067200000
    t1 = t0 + 86_400_000

    # Posición long apalancada 3x
    signals = pd.DataFrame({"BTCUSDT": [3.0, 3.0]}, index=[t0, t1])
    # El close apenas cae de 50k a 49k (parece seguro al cierre)
    closes = pd.DataFrame({"BTCUSDT": [50_000.0, 49_000.0]}, index=[t0, t1])
    # Pero el Low intra-barra se desploma a 30k (wick liquidation)
    lows = pd.DataFrame({"BTCUSDT": [50_000.0, 30_000.0]}, index=[t0, t1])
    highs = pd.DataFrame({"BTCUSDT": [50_000.0, 51_000.0]}, index=[t0, t1])

    sim = FuturesPortfolioSimulator(
        initial_equity=10_000.0,
        cost_model=base_cost_model,
        assert_liquidation=True,
        check_intra_bar_liquidation=True,
    )

    with pytest.raises(AccountLiquidatedError) as exc_info:
        sim.run(signals, closes, lows_df=lows, highs_df=highs)

    assert "Intra-bar adverse price excursion" in str(exc_info.value)


# ── 7. Liquidación Automática en Delisteo ─────────────────────────────────────


def test_delisting_liquidation(base_cost_model: CostModel) -> None:
    t0 = 1704067200000
    t1 = t0 + 86_400_000
    t2 = t1 + 86_400_000

    # Símbolo ALTUSDT se delista en t2 (desaparece de closes_df)
    signals = pd.DataFrame(
        {"BTCUSDT": [0.5, 0.5, 0.5], "ALTUSDT": [0.5, 0.5, 0.0]},
        index=[t0, t1, t2],
    )
    closes = pd.DataFrame(
        {
            "BTCUSDT": [50_000.0, 51_000.0, 52_000.0],
            "ALTUSDT": [10.0, 12.0, float("nan")],  # NaN en t2: ya no cotiza
        },
        index=[t0, t1, t2],
    )

    sim = FuturesPortfolioSimulator(initial_equity=50_000.0, cost_model=base_cost_model)
    history, decomp = sim.run(signals, closes)

    # En t2, ALTUSDT debe haber sido liquidado y ya no estar en posiciones
    snap_t2 = history.loc[t2]
    assert "ALTUSDT" not in snap_t2["positions"]
    # Pagó comisión por la liquidación de salida
    assert decomp.fee_cost > 0.0


def test_account_liquidated_error_with_symbol() -> None:
    err = AccountLiquidatedError(
        open_time=123456789,
        equity=50.0,
        maintenance_margin=100.0,
        margin_ratio=2.0,
        reason="Test breach",
        symbol="BTCUSDT",
    )
    assert "en símbolo BTCUSDT" in str(err)


def test_intra_bar_short_liquidation_assertion(base_cost_model: CostModel) -> None:
    t0 = 1704067200000
    t1 = t0 + 86_400_000

    # Posición short apalancada 3x
    signals = pd.DataFrame({"BTCUSDT": [-3.0, -3.0]}, index=[t0, t1])
    closes = pd.DataFrame({"BTCUSDT": [50_000.0, 50_100.0]}, index=[t0, t1])
    # Mecha de subida extrema a 70k para liquidar al short
    lows = pd.DataFrame({"BTCUSDT": [50_000.0, 49_900.0]}, index=[t0, t1])
    highs = pd.DataFrame({"BTCUSDT": [50_000.0, 70_000.0]}, index=[t0, t1])

    sim = FuturesPortfolioSimulator(
        initial_equity=10_000.0,
        cost_model=base_cost_model,
        assert_liquidation=True,
        check_intra_bar_liquidation=True,
    )

    with pytest.raises(AccountLiquidatedError) as exc_info:
        sim.run(signals, closes, lows_df=lows, highs_df=highs)

    assert "Intra-bar adverse price excursion" in str(exc_info.value)


def test_position_closure_to_flat(base_cost_model: CostModel) -> None:
    t0 = 1704067200000
    t1 = t0 + 86_400_000
    t2 = t1 + 86_400_000

    # Abre en t0, cierra a flat (0.0) en t1
    signals = pd.DataFrame({"BTCUSDT": [0.5, 0.0, 0.0]}, index=[t0, t1, t2])
    closes = pd.DataFrame({"BTCUSDT": [50_000.0, 52_000.0, 52_500.0]}, index=[t0, t1, t2])

    sim = FuturesPortfolioSimulator(initial_equity=10_000.0, cost_model=base_cost_model)
    history, _ = sim.run(signals, closes)

    assert len(history.loc[t2, "positions"]) == 0


def test_volatility_targeting_edge_cases(base_cost_model: CostModel) -> None:
    sim = FuturesPortfolioSimulator(
        initial_equity=10_000.0,
        cost_model=base_cost_model,
        vol_config=VolatilityTargetConfig(target_annual_vol=0.15, max_gross_leverage=5.0),
    )
    # Sin pesos
    assert sim._scale_weights({}, pd.DataFrame()) == {}
    # Señales con cero
    res = sim._scale_weights({"BTCUSDT": 0.0}, pd.DataFrame({"BTCUSDT": [100.0, 101.0]}))
    assert res == {}
    # Símbolo no presente en el historial de precios
    res_missing = sim._scale_weights({"SOLUSDT": 0.2}, pd.DataFrame({"BTCUSDT": [100.0, 101.0]}))
    assert "SOLUSDT" in res_missing
    # Sin techo alcanzado
    res2 = sim._scale_weights({"BTCUSDT": 0.1}, pd.DataFrame({"BTCUSDT": [100.0, 101.0, 102.0]}))
    assert "BTCUSDT" in res2


def test_liquidation_without_assertion_mode(base_cost_model: CostModel) -> None:
    t0 = 1704067200000
    t1 = t0 + 86_400_000

    # Pérdida con apalancamiento 5x que quiebra el equity al cierre de barra
    signals = pd.DataFrame({"BTCUSDT": [5.0, 5.0]}, index=[t0, t1])
    closes = pd.DataFrame({"BTCUSDT": [50_000.0, 37_500.0]}, index=[t0, t1])

    sim = FuturesPortfolioSimulator(
        initial_equity=10_000.0,
        cost_model=base_cost_model,
        assert_liquidation=False,
    )
    hist, decomp = sim.run(signals, closes)
    assert not hist.empty
    assert hist.loc[t1, "equity"] == 0.0
    assert len(hist.loc[t1, "positions"]) == 0


def test_intra_bar_liquidation_without_assertion(base_cost_model: CostModel) -> None:
    t0 = 1704067200000
    t1 = t0 + 86_400_000

    # Long 3x donde el close aguanta pero el wick intra-barra quiebra el margen
    signals = pd.DataFrame({"BTCUSDT": [3.0, 3.0]}, index=[t0, t1])
    closes = pd.DataFrame({"BTCUSDT": [50_000.0, 49_000.0]}, index=[t0, t1])
    lows = pd.DataFrame({"BTCUSDT": [50_000.0, 30_000.0]}, index=[t0, t1])
    highs = pd.DataFrame({"BTCUSDT": [50_000.0, 51_000.0]}, index=[t0, t1])

    sim = FuturesPortfolioSimulator(
        initial_equity=10_000.0,
        cost_model=base_cost_model,
        assert_liquidation=False,
        check_intra_bar_liquidation=True,
    )
    hist, decomp = sim.run(signals, closes, lows_df=lows, highs_df=highs)
    assert not hist.empty
    assert hist.loc[t1, "equity"] == 0.0
    assert len(hist.loc[t1, "positions"]) == 0


def test_funding_with_empty_or_zero_values(base_cost_model: CostModel) -> None:
    t0 = 1704067200000
    t1 = t0 + 86_400_000

    signals = pd.DataFrame({"BTCUSDT": [0.5, 0.5]}, index=[t0, t1])
    closes = pd.DataFrame({"BTCUSDT": [50_000.0, 50_000.0]}, index=[t0, t1])
    empty_funding = {"BTCUSDT": pd.DataFrame()}

    sim = FuturesPortfolioSimulator(initial_equity=10_000.0, cost_model=base_cost_model)
    hist, decomp = sim.run(signals, closes, funding_dfs=empty_funding)
    assert not hist.empty
    assert decomp.funding_pnl == 0.0


def test_simulation_with_volume_df(base_cost_model: CostModel) -> None:
    t0 = 1704067200000
    t1 = t0 + 86_400_000

    signals = pd.DataFrame({"BTCUSDT": [0.5, 0.5]}, index=[t0, t1])
    closes = pd.DataFrame({"BTCUSDT": [50_000.0, 51_000.0]}, index=[t0, t1])
    volumes = pd.DataFrame({"BTCUSDT": [10_000_000.0, 12_000_000.0]}, index=[t0, t1])

    sim = FuturesPortfolioSimulator(initial_equity=10_000.0, cost_model=base_cost_model)
    hist, decomp = sim.run(signals, closes, volumes_df=volumes)
    assert not hist.empty
    assert decomp.fee_cost > 0.0


# ── 8. Manejo de Entradas Vacías ─────────────────────────────────────────────


def test_empty_inputs(base_cost_model: CostModel) -> None:
    sim = FuturesPortfolioSimulator(initial_equity=10_000.0, cost_model=base_cost_model)
    hist, decomp = sim.run(pd.DataFrame(), pd.DataFrame())
    assert hist.empty
    assert decomp.net_pnl == 0.0
