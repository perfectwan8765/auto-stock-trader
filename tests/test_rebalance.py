"""compute_rebalance 단위테스트 (순수 함수 — 브로커 불요).

개선1(자금이월)·5(멱등키)·8(최소금액) 검증.
실행:  .venv/bin/python -m pytest tests/test_rebalance.py -q
"""
from __future__ import annotations

from execution.interface import RebalanceParams
from execution.rebalance import compute_rebalance, make_client_order_id


def _params(**kw):
    base = dict(total_equity_usd=700.0, buying_power_usd=700.0, min_order_usd=1.0, rebalance_date="20260718")
    base.update(kw)
    return RebalanceParams(**base)


def test_enter_from_empty_equal_weight():
    # 빈 계좌 → 목표 2종목 동일비중. 각 350 매수.
    plan = compute_rebalance({"AAPL": 0.5, "MSFT": 0.5}, {}, {"AAPL": 100, "MSFT": 200}, _params())
    buys = {o.symbol: o for o in plan.orders if o.side == "BUY"}
    assert set(buys) == {"AAPL", "MSFT"}
    assert all(o.kind == "amount" and o.reason == "enter" for o in buys.values())
    assert abs(buys["AAPL"].value - 350.0) < 1e-6
    assert plan.skipped == []


def test_exit_dropped_symbol_full_quantity():
    # NVDA 보유하나 목표에 없음 → 전량 매도(exit).
    plan = compute_rebalance({"AAPL": 1.0}, {"NVDA": 3.0, "AAPL": 1.0},
                             {"AAPL": 100, "NVDA": 50}, _params())
    sells = [o for o in plan.orders if o.side == "SELL"]
    exit_o = [o for o in sells if o.reason == "exit"]
    assert len(exit_o) == 1 and exit_o[0].symbol == "NVDA"
    assert exit_o[0].kind == "quantity" and exit_o[0].value == 3.0


def test_sells_before_buys_order():
    plan = compute_rebalance({"AAPL": 1.0}, {"NVDA": 3.0}, {"AAPL": 100, "NVDA": 50}, _params())
    sides = [o.side for o in plan.orders]
    assert sides.index("SELL") < sides.index("BUY")  # 매도先→매수(개선1)


def test_below_min_order_skipped():
    # 목표 매수액 0.5 < min 1.0 → 스킵(개선8).
    p = _params(total_equity_usd=1.0, min_order_usd=1.0)
    plan = compute_rebalance({"AAPL": 0.5}, {}, {"AAPL": 100}, p)
    assert not [o for o in plan.orders if o.side == "BUY"]
    assert ("AAPL", "below_min_order") in plan.skipped


def test_insufficient_buying_power_carryover():
    # 목표 2종목 각 350 매수인데 가용 400뿐 → 큰 갭 먼저 완전체결, 나머지 부분/이월(개선1).
    p = _params(buying_power_usd=400.0)
    plan = compute_rebalance({"AAPL": 0.5, "MSFT": 0.5}, {}, {"AAPL": 100, "MSFT": 100}, p)
    buys = [o for o in plan.orders if o.side == "BUY"]
    total_buy = sum(o.value for o in buys)
    assert total_buy <= 400.0 + 1e-6  # 가용 초과 안 함
    assert any("insufficient_buying_power" in r for _, r in plan.skipped)


def test_client_order_id_deterministic():
    a = make_client_order_id("20260718", "AAPL", "BUY")
    b = make_client_order_id("20260718", "AAPL", "BUY")
    c = make_client_order_id("20260719", "AAPL", "BUY")
    assert a == b and a != c  # 재현 가능·일자 다르면 다름(개선5)
    assert a.startswith("rb-")


def test_trim_overweight_sells_excess():
    # AAPL 목표 350인데 700 보유(overweight) → 초과분 350어치(3.5주) trim 매도.
    plan = compute_rebalance({"AAPL": 0.5, "MSFT": 0.5}, {"AAPL": 7.0}, {"AAPL": 100, "MSFT": 100}, _params())
    trims = [o for o in plan.orders if o.reason == "trim"]
    assert len(trims) == 1 and trims[0].symbol == "AAPL"
    assert trims[0].side == "SELL" and trims[0].kind == "quantity"
    assert abs(trims[0].value - 3.5) < 1e-6


def test_client_order_id_stable_across_buying_power():
    # 개선5 핵심: 부분매수든 완전매수든 (일자·종목·side) 같으면 동일 키 → T+N로 가용액
    # 달라져도 재실행 시 중복주문 안 남.
    full = compute_rebalance({"AAPL": 1.0}, {}, {"AAPL": 100}, _params(buying_power_usd=700.0))
    part = compute_rebalance({"AAPL": 1.0}, {}, {"AAPL": 100}, _params(buying_power_usd=400.0))
    fb = [o for o in full.orders if o.symbol == "AAPL"][0]
    pb = [o for o in part.orders if o.symbol == "AAPL"][0]
    assert fb.value != pb.value          # 금액은 다름(700 vs 400)
    assert fb.client_order_id == pb.client_order_id  # 그러나 키는 동일(멱등 유지)


def test_no_trade_when_on_target():
    # 이미 목표와 일치 → 주문 없음.
    plan = compute_rebalance({"AAPL": 1.0}, {"AAPL": 7.0}, {"AAPL": 100}, _params())
    assert plan.orders == []
