"""특성화 테스트 — seam 리팩터가 바꾸면 안 되는 러너 동작을 고정한다.

★ 이 파일의 본문은 리팩터 전후로 **한 줄도 바뀌지 않아야 한다.**

seam 리팩터(Broker Protocol 축소·예외 정규화·RunnerPolicy)는 `tests/test_runner.py`의
MockBroker를 통째로 다시 쓴다. 그러면 기존 테스트만으로는 "리팩터가 동작을 바꿨는지"와
"테스트를 고쳐 맞췄는지"를 구별할 수 없다. 그 구별을 만들려고 이 파일을 둔다.

단언은 전부 `RunResult`(orders·skipped·placed) 관찰로만 한다. 브로커 생성과 러너 생성은
`conftest.py`의 `make_broker`·`make_runner`를 거치므로, Protocol이나 생성자가 바뀔 때
고칠 곳은 그 두 함수뿐이다.
"""
from __future__ import annotations

import pytest

from execution.errors import CircuitBreakerTripped
from execution.managed import ManagedState
from execution.safety import CircuitBreaker

DATE = "20260716"


def _bot(*symbols):
    """봇 관리셋으로 등록된 상태. 보유가 리밸 대상이 되려면 M에 들어 있어야 한다."""
    return ManagedState(managed=set(symbols), bootstrapped=True)


def test_sells_are_ordered_before_buys(make_broker, make_runner):
    """매도先→매수. 매도대금이 안 들어와도 최소한 순서는 지켜져야 자금 확보가 가능하다."""
    broker = make_broker(holdings={"OLD": 10.0}, prices={"OLD": 100.0, "NEW": 100.0},
                         buying_power=1_000.0)
    res = make_runner(broker, managed_state=_bot("OLD")).run(
        {"NEW": 1.0}, DATE, dry_run=True)

    sides = [o.side for o in res.plan.orders]
    assert sides == sorted(sides, key=lambda s: 0 if s == "SELL" else 1)
    assert sides[0] == "SELL" and sides[-1] == "BUY"


def test_exit_sells_whole_broker_quantity(make_broker, make_runner):
    """편출은 브로커 권위값(보유수량) 그대로 판다 — 반올림하면 초과매도 위험."""
    broker = make_broker(holdings={"OLD": 3.14159265}, prices={"OLD": 100.0})
    res = make_runner(broker, managed_state=_bot("OLD")).run({}, DATE, dry_run=True)

    (order,) = res.plan.orders
    assert order.side == "SELL" and order.kind == "quantity"
    assert order.value == 3.14159265
    assert order.reason == "exit"


def test_within_band_is_recorded_not_silent(make_broker, make_runner):
    """밴드 안이면 거래하지 않되 **사유를 남긴다.** 조용히 넘기면 무동작 이유를 알 수 없다."""
    # budget으로 목표 규모를 $1000에 고정. 보유 10.5주 × $100 = $1050 → 편차 5% < 밴드 10%.
    # (예산 미설정이면 total_equity = 봇보유 + 계좌현금이라 목표가 의도대로 안 잡힌다.)
    broker = make_broker(holdings={"AAA": 10.5}, prices={"AAA": 100.0}, buying_power=1_000.0)
    res = make_runner(broker, managed_state=_bot("AAA"), rebalance_band=0.10,
                      budget_usd=1_000.0).run({"AAA": 1.0}, DATE, dry_run=True)

    assert res.plan.orders == []
    assert ("AAA", "within_band") in res.plan.skipped


def test_skip_reasons_vocabulary(make_broker, make_runner):
    """스킵 사유 문자열은 대시보드·로그가 읽는 계약이다. 리팩터가 바꾸면 안 된다."""
    # 목표 규모 $2000(종목당 $1000)인데 가용 현금은 $60뿐 —
    # 먼저 배분된 종목이 부분매수($60), 남은 종목은 잔액 0이라 거부.
    broker = make_broker(prices={"BBB": 100.0, "CCC": 100.0}, buying_power=60.0)
    res = make_runner(broker, min_order_usd=50.0, budget_usd=2_000.0).run(
        {"BBB": 0.5, "CCC": 0.5}, DATE, dry_run=True)

    reasons = {r for _, r in res.plan.skipped}
    assert reasons <= {"within_band", "below_min_order", "insufficient_buying_power",
                       "partial_insufficient_buying_power", "excluded_manual",
                       "not_sellable_settlement", "sell_clamped_to_sellable"}
    assert "partial_insufficient_buying_power" in reasons
    assert "insufficient_buying_power" in reasons


def test_budget_cap_limits_buys_below_account_cash(make_broker, make_runner):
    """예산 상한: 계좌에 현금이 넉넉해도 budget_usd를 넘겨 사지 않는다(계좌 공유 보호)."""
    broker = make_broker(prices={"AAA": 100.0}, buying_power=10_000.0)
    res = make_runner(broker, budget_usd=250.0).run({"AAA": 1.0}, DATE, dry_run=True)

    assert sum(o.value for o in res.plan.orders if o.side == "BUY") <= 250.0


def test_sell_clamped_to_sellable_quantity(make_broker, make_runner):
    """T+N 미결제분이 있으면 매도가능수량까지만 판다(초과매도 거부 방지). 사유도 남는다."""
    broker = make_broker(holdings={"OLD": 10.0}, prices={"OLD": 100.0},
                         sellable={"OLD": 3.0})
    res = make_runner(broker, managed_state=_bot("OLD")).run({}, DATE, dry_run=True)

    (order,) = res.plan.orders
    assert order.value == 3.0
    assert ("OLD", "sell_clamped_to_sellable") in res.plan.skipped


def test_not_sellable_is_skipped_entirely(make_broker, make_runner):
    broker = make_broker(holdings={"OLD": 10.0}, prices={"OLD": 100.0},
                         sellable={"OLD": 0.0})
    res = make_runner(broker, managed_state=_bot("OLD")).run({}, DATE, dry_run=True)

    assert res.plan.orders == []
    assert ("OLD", "not_sellable_settlement") in res.plan.skipped


def test_circuit_breaker_stops_loop_at_limit(make_broker, make_runner):
    """상한에 걸리면 그 지점에서 멈춘다 — 이미 나간 주문은 유지, 나머지는 발주 안 됨."""
    broker = make_broker(prices={"AAA": 100.0, "BBB": 100.0}, buying_power=1_000.0)
    cb = CircuitBreaker(max_orders_per_day=1, max_loss_usd=1e9)

    with pytest.raises(CircuitBreakerTripped):
        make_runner(broker, circuit_breaker=cb).run(
            {"AAA": 0.5, "BBB": 0.5}, DATE, dry_run=False)

    assert len(broker.placed) == 1


def test_dry_run_places_nothing_but_still_plans(make_broker, make_runner):
    broker = make_broker(prices={"AAA": 100.0}, buying_power=1_000.0)
    res = make_runner(broker).run({"AAA": 1.0}, DATE, dry_run=True)

    assert broker.placed == [] and res.dry_run is True
    assert len(res.plan.orders) == 1
