"""Tests para el modelo de costos de futuros USDⓈ-M (futures/costs.py).

Verifica los tres pilares del roadmap:
1. Comisión obligatoria sin default silencioso (fee >= 0, prohibido cero total).
2. Slippage que nunca es cero (> 0 siempre, con piso obligatorio).
3. Accrual real de funding con timestamps y tasas históricas variables.
"""

from __future__ import annotations

import pandas as pd
import pytest

from krmaazha_binance_mcp.futures.costs import (
    CostDecomposition,
    CostModel,
    FeeModel,
    FixedBasisPointSlippage,
    VolumeImpactSlippage,
    accrue_funding_events,
    accrue_funding_panel,
    accrue_funding_returns_panel,
    calculate_funding_cash_flow,
    compute_turnover_friction,
)

# ── 1. FeeModel: Parámetro obligatorio sin default silencioso ────────────────


def test_fee_model_requires_explicit_parameters() -> None:
    """Omitir parámetros de comisión debe fallar; no hay defaults silenciosos."""
    with pytest.raises(TypeError):
        FeeModel()  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        FeeModel(taker_fee=0.0004)  # type: ignore[call-arg]


def test_fee_model_rejects_negative_fees() -> None:
    with pytest.raises(ValueError, match="no pueden ser negativas"):
        FeeModel(taker_fee=-0.0004, maker_fee=0.0002)

    with pytest.raises(ValueError, match="no pueden ser negativas"):
        FeeModel(taker_fee=0.0004, maker_fee=-0.0002)


def test_fee_model_rejects_zero_commission() -> None:
    """Cero comisión está prohibido: futuros siempre incurre en comisiones."""
    with pytest.raises(ValueError, match="Comisión cero prohibida"):
        FeeModel(taker_fee=0.0, maker_fee=0.0)


def test_fee_model_calculates_fees_accurately() -> None:
    fee_model = FeeModel(taker_fee=0.0005, maker_fee=0.0002)
    notional = 10_000.0

    taker_fee = fee_model.calculate_fee(notional, is_taker=True)
    maker_fee = fee_model.calculate_fee(notional, is_taker=False)

    assert taker_fee == pytest.approx(5.0)
    assert maker_fee == pytest.approx(2.0)
    # Soporta nocionales negativos sin cambiar el signo del fee
    assert fee_model.calculate_fee(-notional, is_taker=True) == pytest.approx(5.0)


# ── 2. SlippageModel: Slippage que NUNCA es cero ─────────────────────────────


def test_fixed_slippage_requires_explicit_bps() -> None:
    with pytest.raises(TypeError):
        FixedBasisPointSlippage()  # type: ignore[call-arg]


def test_fixed_slippage_rejects_zero_or_negative() -> None:
    with pytest.raises(ValueError, match="estrictamente positivo"):
        FixedBasisPointSlippage(bps=0.0)

    with pytest.raises(ValueError, match="estrictamente positivo"):
        FixedBasisPointSlippage(bps=-2.5)


def test_fixed_slippage_applies_adversely_to_both_sides() -> None:
    slip = FixedBasisPointSlippage(bps=5.0)  # 5 bps = 0.0005
    nominal = 50_000.0
    qty = 2.0

    # Compra (+1): precio efectivo sube (peor para el comprador)
    buy_price = slip.calculate_effective_price(nominal, side=1)
    assert buy_price == pytest.approx(50_000.0 * (1.0 + 0.0005))
    buy_cost = slip.calculate_slippage_cost(nominal, side=1, qty=qty)
    assert buy_cost == pytest.approx((buy_price - nominal) * qty)
    assert buy_cost > 0.0

    # Venta (-1): precio efectivo baja (peor para el vendedor)
    sell_price = slip.calculate_effective_price(nominal, side=-1)
    assert sell_price == pytest.approx(50_000.0 * (1.0 - 0.0005))
    sell_cost = slip.calculate_slippage_cost(nominal, side=-1, qty=qty)
    assert sell_cost == pytest.approx((nominal - sell_price) * qty)
    assert sell_cost > 0.0


def test_fixed_slippage_validates_inputs() -> None:
    slip = FixedBasisPointSlippage(bps=3.0)
    with pytest.raises(ValueError, match="nominal debe ser positivo"):
        slip.calculate_effective_price(0.0, side=1)

    with pytest.raises(ValueError, match="side debe ser"):
        slip.calculate_effective_price(100.0, side=0)


def test_volume_impact_slippage_validation() -> None:
    with pytest.raises(TypeError):
        VolumeImpactSlippage()  # type: ignore[call-arg]

    with pytest.raises(ValueError, match="floor_bps.*estrictamente positivo"):
        VolumeImpactSlippage(floor_bps=0.0, impact_factor=0.1)

    with pytest.raises(ValueError, match="floor_bps.*estrictamente positivo"):
        VolumeImpactSlippage(floor_bps=-1.0, impact_factor=0.1)

    with pytest.raises(ValueError, match="impact_factor no puede ser negativo"):
        VolumeImpactSlippage(floor_bps=1.5, impact_factor=-0.05)

    with pytest.raises(ValueError, match="power debe ser positivo"):
        VolumeImpactSlippage(floor_bps=1.5, impact_factor=0.1, power=0.0)


def test_volume_impact_slippage_scales_with_participation() -> None:
    model = VolumeImpactSlippage(floor_bps=2.0, impact_factor=0.5, power=0.5)

    # Si no hay volumen o nocional es 0, respeta el piso estricto
    assert model.effective_bps(notional=0.0, quote_volume=1_000_000.0) == pytest.approx(2.0)
    assert model.effective_bps(notional=10_000.0, quote_volume=0.0) == pytest.approx(2.0)

    # 10k sobre 1M = 1% participación -> sqrt(0.01) = 0.1 -> 0.5 * 0.1 * 10000 = 500 bps
    eff_bps = model.effective_bps(notional=10_000.0, quote_volume=1_000_000.0)
    assert eff_bps == pytest.approx(2.0 + 500.0)

    # Efecto adverso sobre compra
    nominal = 100.0
    eff_price = model.calculate_effective_price(
        nominal, side=1, notional=10_000.0, quote_volume=1_000_000.0
    )
    assert eff_price > nominal
    cost = model.calculate_slippage_cost(
        nominal, side=1, qty=100.0, quote_volume=1_000_000.0
    )
    assert cost > 0.0

    # Efecto adverso sobre venta
    eff_sell = model.calculate_effective_price(
        nominal, side=-1, notional=10_000.0, quote_volume=1_000_000.0
    )
    assert eff_sell < nominal


# ── 3. CostModel: Integración de fill con desglose ───────────────────────────


def test_cost_model_simulation() -> None:
    fee_model = FeeModel(taker_fee=0.0004, maker_fee=0.0002)
    slippage_model = FixedBasisPointSlippage(bps=2.0)  # 2 bps = 0.0002
    cost_model = CostModel(fee_model=fee_model, slippage_model=slippage_model)

    nominal_price = 40_000.0
    qty = 0.5  # notional nominal = 20,000

    fill_buy = cost_model.simulate_fill(nominal_price, qty, side=1, is_taker=True)
    assert fill_buy.effective_price == pytest.approx(40_000.0 * 1.0002)
    assert fill_buy.slippage_cost == pytest.approx(4.0)
    assert fill_buy.fee == pytest.approx(fill_buy.notional * 0.0004)
    assert fill_buy.total_friction == pytest.approx(fill_buy.fee + fill_buy.slippage_cost)

    fill_sell = cost_model.simulate_fill(nominal_price, qty, side=-1, is_taker=False)
    assert fill_sell.effective_price == pytest.approx(40_000.0 * 0.9998)
    assert fill_sell.slippage_cost == pytest.approx(4.0)
    assert fill_sell.fee == pytest.approx(fill_sell.notional * 0.0002)


# ── 4. Accrual Real de Funding ───────────────────────────────────────────────


def test_calculate_funding_cash_flow_directions() -> None:
    price = 60_000.0
    qty = 1.0
    pos_rate = 0.0001  # +0.01%
    neg_rate = -0.0001  # -0.01%

    # Long (qty > 0) con tasa positiva: paga funding (flujo negativo)
    flow_long_pos = calculate_funding_cash_flow(qty, price, pos_rate)
    assert flow_long_pos == pytest.approx(-6.0)

    # Long (qty > 0) con tasa negativa: cobra funding (flujo positivo)
    flow_long_neg = calculate_funding_cash_flow(qty, price, neg_rate)
    assert flow_long_neg == pytest.approx(6.0)

    # Short (qty < 0) con tasa positiva: cobra funding (flujo positivo)
    flow_short_pos = calculate_funding_cash_flow(-qty, price, pos_rate)
    assert flow_short_pos == pytest.approx(6.0)

    # Short (qty < 0) con tasa negativa: paga funding (flujo negativo)
    flow_short_neg = calculate_funding_cash_flow(-qty, price, neg_rate)
    assert flow_short_neg == pytest.approx(-6.0)


def test_accrue_funding_events_within_holding_window() -> None:
    # 3 eventos de funding en un día (intervalo 8h: 00:00, 08:00, 16:00 UTC)
    t0 = 1704067200000  # 2024-01-01 00:00:00 UTC
    t1 = t0 + 8 * 3600 * 1000  # 08:00 UTC
    t2 = t0 + 16 * 3600 * 1000  # 16:00 UTC
    t3 = t0 + 24 * 3600 * 1000  # 2024-01-02 00:00:00 UTC

    df_funding = pd.DataFrame(
        [
            {"calc_time": t0, "funding_interval_hours": 8.0, "last_funding_rate": 0.0001},
            {"calc_time": t1, "funding_interval_hours": 8.0, "last_funding_rate": 0.0002},
            {"calc_time": t2, "funding_interval_hours": 8.0, "last_funding_rate": 0.00015},
            {"calc_time": t3, "funding_interval_hours": 8.0, "last_funding_rate": 0.0001},
        ]
    )

    # Si se mantiene posición durante todo el día 2024-01-01 [t0, t3)
    total_flow, events = accrue_funding_events(
        df_funding, position_qty=2.0, mark_price=50_000.0, start_time_ms=t0, end_time_ms=t3
    )

    # 3 eventos capturados: t0, t1, t2 (t3 cae fuera del rango semi-abierto)
    assert len(events) == 3
    # Tasas: 0.0001 + 0.0002 + 0.00015 = 0.00045
    # Flujo = - (2 * 50_000 * 0.00045) = -45.0
    assert total_flow == pytest.approx(-45.0)

    # Si la posición se abre a las 09:00 UTC y se cierra a las 15:00 UTC, no cruza ningún evento
    mid_open = t0 + 9 * 3600 * 1000
    mid_close = t0 + 15 * 3600 * 1000
    empty_flow, empty_events = accrue_funding_events(
        df_funding, position_qty=2.0, mark_price=50_000.0, start_time_ms=mid_open, end_time_ms=mid_close
    )
    assert empty_flow == 0.0
    assert len(empty_events) == 0


def test_accrue_funding_events_empty_or_zero() -> None:
    empty_df = pd.DataFrame(columns=["calc_time", "funding_interval_hours", "last_funding_rate"])
    flow, ev = accrue_funding_events(empty_df, 1.0, 100.0, 1000, 2000)
    assert flow == 0.0
    assert ev == []

    # Qty 0
    flow0, ev0 = accrue_funding_events(pd.DataFrame([{"calc_time": 1500, "funding_interval_hours": 8, "last_funding_rate": 0.001}]), 0.0, 100.0, 1000, 2000)
    assert flow0 == 0.0
    assert ev0 == []


def test_accrue_funding_panel_matrix() -> None:
    t0 = 1704067200000  # Día 1
    t1 = t0 + 86_400_000  # Día 2

    positions = pd.DataFrame(
        {"BTCUSDT": [1.0, -1.0], "ETHUSDT": [10.0, 0.0]},
        index=[t0, t1],
    )
    prices = pd.DataFrame(
        {"BTCUSDT": [50_000.0, 52_000.0], "ETHUSDT": [3_000.0, 3_100.0]},
        index=[t0, t1],
    )

    btc_funding = pd.DataFrame(
        [
            {"calc_time": t0 + 1000, "funding_interval_hours": 8.0, "last_funding_rate": 0.0001},
            {"calc_time": t1 + 1000, "funding_interval_hours": 8.0, "last_funding_rate": 0.0001},
        ]
    )
    eth_funding = pd.DataFrame(
        [
            {"calc_time": t0 + 1000, "funding_interval_hours": 4.0, "last_funding_rate": -0.0002},
        ]
    )

    pnl_df = accrue_funding_panel(positions, prices, {"BTCUSDT": btc_funding, "ETHUSDT": eth_funding})

    # Día 1 BTC: Long 1.0 * 50k * (+0.0001) -> Paga $5 (-5.0)
    assert pnl_df.loc[t0, "BTCUSDT"] == pytest.approx(-5.0)
    # Día 2 BTC: Short -1.0 * 52k * (+0.0001) -> Cobra $5.2 (+5.2)
    assert pnl_df.loc[t1, "BTCUSDT"] == pytest.approx(5.2)

    # Día 1 ETH: Long 10.0 * 3k * (-0.0002) -> Cobra $6 (+6.0)
    assert pnl_df.loc[t0, "ETHUSDT"] == pytest.approx(6.0)
    # Día 2 ETH: Qty 0 -> 0.0
    assert pnl_df.loc[t1, "ETHUSDT"] == pytest.approx(0.0)


def test_accrue_funding_panel_empty() -> None:
    res = accrue_funding_panel(pd.DataFrame(), pd.DataFrame(), {})
    assert res.empty


def test_accrue_funding_returns_panel() -> None:
    t0 = 1704067200000
    weights = pd.DataFrame({"BTCUSDT": [0.5], "SOLUSDT": [-0.3]}, index=[t0])
    btc_f = pd.DataFrame([{"calc_time": t0 + 1000, "funding_interval_hours": 8.0, "last_funding_rate": 0.0001}])
    sol_f = pd.DataFrame([{"calc_time": t0 + 1000, "funding_interval_hours": 8.0, "last_funding_rate": 0.0003}])

    ret_df = accrue_funding_returns_panel(weights, {"BTCUSDT": btc_f, "SOLUSDT": sol_f})

    # BTC: -0.5 * 0.0001 = -0.00005
    assert ret_df.loc[t0, "BTCUSDT"] == pytest.approx(-0.00005)
    # SOL: -(-0.3) * 0.0003 = +0.00009
    assert ret_df.loc[t0, "SOLUSDT"] == pytest.approx(0.00009)

    # Empty
    assert accrue_funding_returns_panel(pd.DataFrame(), {}).empty


# ── 5. Turnover Friction & Cost Decomposition ───────────────────────────────


def test_compute_turnover_friction() -> None:
    t0 = 1704067200000
    delta_w = pd.DataFrame({"BTCUSDT": [0.1], "ETHUSDT": [0.0]}, index=[t0])
    volumes = pd.DataFrame({"BTCUSDT": [10_000_000.0], "ETHUSDT": [5_000_000.0]}, index=[t0])

    cost_model = CostModel(
        fee_model=FeeModel(taker_fee=0.0005, maker_fee=0.0002),
        slippage_model=FixedBasisPointSlippage(bps=2.0),
    )

    fee_df, slip_df = compute_turnover_friction(
        delta_w, cost_model, volumes_df=volumes, portfolio_equity=1_000_000.0
    )

    # Delta W = 0.1 de 1M = 100,000 notional
    # Fee = 100,000 * 0.0005 = 50.0
    assert fee_df.loc[t0, "BTCUSDT"] == pytest.approx(50.0)
    # Slippage = 100,000 * 0.0002 = 20.0
    assert slip_df.loc[t0, "BTCUSDT"] == pytest.approx(20.0)

    # ETH: Delta W = 0 -> 0.0
    assert fee_df.loc[t0, "ETHUSDT"] == pytest.approx(0.0)
    assert slip_df.loc[t0, "ETHUSDT"] == pytest.approx(0.0)

    # Empty test
    e1, e2 = compute_turnover_friction(pd.DataFrame(), cost_model)
    assert e1.empty and e2.empty


def test_compute_turnover_friction_with_volume_impact() -> None:
    t0 = 1704067200000
    delta_w = pd.DataFrame({"BTCUSDT": [0.2]}, index=[t0])
    volumes = pd.DataFrame({"BTCUSDT": [2_000_000.0]}, index=[t0])

    model = CostModel(
        fee_model=FeeModel(taker_fee=0.0004, maker_fee=0.0002),
        slippage_model=VolumeImpactSlippage(floor_bps=1.0, impact_factor=0.1),
    )

    fee_df, slip_df = compute_turnover_friction(delta_w, model, volumes_df=volumes, portfolio_equity=100_000.0)
    assert fee_df.loc[t0, "BTCUSDT"] > 0.0
    assert slip_df.loc[t0, "BTCUSDT"] > 0.0


def test_volume_impact_slippage_invalid_inputs() -> None:
    model = VolumeImpactSlippage(floor_bps=2.0, impact_factor=0.5)
    with pytest.raises(ValueError, match="nominal debe ser positivo"):
        model.calculate_effective_price(0.0, side=1)

    with pytest.raises(ValueError, match="side debe ser"):
        model.calculate_effective_price(100.0, side=0)


def test_accrue_funding_panel_missing_branches() -> None:
    t0 = 1704067200000
    positions = pd.DataFrame(
        {"BTCUSDT": [1.0], "NOFUNDING": [2.0], "NOPRICE": [3.0], "BADPRICE": [4.0]},
        index=[t0],
    )
    prices = pd.DataFrame(
        {"BTCUSDT": [50_000.0], "NOFUNDING": [10.0], "BADPRICE": [float("nan")]},
        index=[t0],
    )
    btc_f = pd.DataFrame(
        [{"calc_time": t0 + 1000, "funding_interval_hours": 8.0, "last_funding_rate": 0.0001}]
    )
    res = accrue_funding_panel(positions, prices, {"BTCUSDT": btc_f})
    assert res.loc[t0, "BTCUSDT"] == pytest.approx(-5.0)
    assert res.loc[t0, "NOFUNDING"] == 0.0
    assert res.loc[t0, "NOPRICE"] == 0.0
    assert res.loc[t0, "BADPRICE"] == 0.0


def test_accrue_funding_returns_missing_symbol_or_weight() -> None:
    t0 = 1704067200000
    weights = pd.DataFrame({"BTCUSDT": [float("nan")], "NOFUND": [0.5]}, index=[t0])
    res = accrue_funding_returns_panel(weights, {})
    assert res.loc[t0, "BTCUSDT"] == 0.0
    assert res.loc[t0, "NOFUND"] == 0.0


class CustomSlippage:
    def calculate_effective_price(self, nominal_price: float, side: int, **kwargs: float) -> float:
        return nominal_price * 1.0001

    def calculate_slippage_cost(self, nominal_price: float, side: int, qty: float, **kwargs: float) -> float:
        return 1.0


def test_compute_turnover_friction_custom_slippage() -> None:
    t0 = 1704067200000
    delta_w = pd.DataFrame({"BTCUSDT": [0.1]}, index=[t0])
    model = CostModel(
        fee_model=FeeModel(taker_fee=0.0004, maker_fee=0.0002),
        slippage_model=CustomSlippage(),
    )
    fee_df, slip_df = compute_turnover_friction(delta_w, model, portfolio_equity=100_000.0)
    assert fee_df.loc[t0, "BTCUSDT"] == pytest.approx(4.0)
    assert slip_df.loc[t0, "BTCUSDT"] == pytest.approx(1.0)


def test_cost_decomposition_total_drag() -> None:
    decomp = CostDecomposition(
        gross_pnl=1000.0,
        fee_cost=50.0,
        slippage_cost=30.0,
        funding_pnl=20.0,  # Cobró 20
        net_pnl=940.0,
    )
    # Total drag = 50 (fee) + 30 (slippage) - 20 (funding_gain) = 60.0
    assert decomp.total_drag == pytest.approx(60.0)
    assert decomp.gross_pnl - decomp.total_drag == pytest.approx(decomp.net_pnl)
