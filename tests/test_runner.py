"""RebalanceRunner 단위테스트 (MockBroker — 실 API 불요).

order_sleep_s=0으로 rate-limit 간격을 꺼 테스트를 빠르게 유지.
"""
from __future__ import annotations

import pytest

from execution.errors import CircuitBreakerTripped, KillSwitchActive
from execution.interface import OrderIntent
from execution.managed import ManagedState
from execution.runner import RebalanceRunner
from execution.safety import CircuitBreaker


class _ApiErr(Exception):
    """토스 TossApiError 대역 — 덕타이핑 .code만 필요."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class MockBroker:
    def __init__(self, holdings=None, prices=None, buying_power=700.0, market_open=True,
                 sellable=None, daily_pnl=None, place_errors=None):
        self._holdings = holdings or {}
        self._prices = prices or {}
        self._buying_power = buying_power
        self._market_open = market_open
        self._sellable = sellable or {}           # symbol -> 매도가능수량(미지정=보유 전량)
        self._daily_pnl = daily_pnl or {}          # symbol -> 당일손익
        self._place_errors = place_errors or {}    # symbol -> [code, ...] 순차 raise 후 성공
        self.placed: list[OrderIntent] = []

    def get_holdings(self):
        return dict(self._holdings)

    def get_prices(self, symbols):
        return {s: self._prices.get(s, 100.0) for s in symbols}

    def get_buying_power_usd(self):
        return self._buying_power

    def get_sellable_quantity(self, symbol):
        return self._sellable.get(symbol, self._holdings.get(symbol, 0.0))

    def get_daily_pnl_usd(self, symbols):
        return sum(self._daily_pnl.get(s, 0.0) for s in symbols)

    def is_market_open(self):
        return self._market_open

    def place(self, intent):
        errs = self._place_errors.get(intent.symbol)
        if errs:
            raise _ApiErr(errs.pop(0))
        self.placed.append(intent)
        return {"clientOrderId": intent.client_order_id, "status": "ACCEPTED"}


def _runner(broker, **kw):
    kw.setdefault("order_sleep_s", 0)
    kw.setdefault("rate_limit_backoff_s", 0)
    return RebalanceRunner(broker, min_order_usd=1.0, **kw)


TW = {"AAPL": 0.5, "MSFT": 0.5}


def test_dry_run_no_orders_placed():
    broker = MockBroker()
    res = _runner(broker).run(TW, "20260716", dry_run=True)
    assert res.dry_run is True
    assert broker.placed == []            # 실발주 없음
    assert len(res.plan.orders) == 2      # 계획은 산출


def test_live_places_orders():
    broker = MockBroker(buying_power=700.0)
    res = _runner(broker).run(TW, "20260716", dry_run=False)
    assert res.dry_run is False
    assert len(broker.placed) == 2
    assert set(res.placed) == {o.client_order_id for o in broker.placed}


def test_live_sells_before_buys():
    broker = MockBroker(holdings={"NVDA": 3.0}, buying_power=700.0)
    state = ManagedState(excluded=set(), managed={"NVDA"}, bootstrapped=True)
    _runner(broker, managed_state=state).run(TW, "20260716", dry_run=False)
    sides = [o.side for o in broker.placed]
    assert broker.placed[0].side == "SELL" and broker.placed[0].symbol == "NVDA"
    assert sides.index("SELL") < sides.index("BUY")


def test_market_closed_aborts():
    broker = MockBroker(market_open=False)
    res = _runner(broker).run(TW, "20260716", dry_run=False)
    assert res.aborted_reason == "market_closed"
    assert broker.placed == []            # 개선6: 정규장 아니면 발주 안 함


def test_kill_switch_blocks_live(tmp_path):
    sw = tmp_path / "STOP"
    sw.touch()
    broker = MockBroker()
    with pytest.raises(KillSwitchActive):
        _runner(broker, kill_switch_path=str(sw)).run(TW, "20260716", dry_run=False)
    assert broker.placed == []


def test_circuit_breaker_stops_mid_run():
    broker = MockBroker()
    cb = CircuitBreaker(max_orders_per_day=1, max_loss_usd=1e9)
    with pytest.raises(CircuitBreakerTripped):
        _runner(broker, circuit_breaker=cb).run(TW, "20260716", dry_run=False)
    assert len(broker.placed) == 1        # 1건 후 상한 → 중단


def test_state_persisted_even_when_guard_trips_midrun():
    # 주문건수 상한이 루프 중간에 트립해도 이미 발주된 심볼은 M에 반영(재실행 중복매수 방지).
    broker = MockBroker(buying_power=700.0)
    state = ManagedState(bootstrapped=True)
    cb = CircuitBreaker(max_orders_per_day=1, max_loss_usd=1e9)
    with pytest.raises(CircuitBreakerTripped):
        _runner(broker, managed_state=state, circuit_breaker=cb).run(TW, "20260716", dry_run=False)
    assert len(broker.placed) == 1
    assert broker.placed[0].symbol in state.managed   # finally에서 상태 영속


def test_dry_run_does_not_check_market_or_kill_switch(tmp_path):
    sw = tmp_path / "STOP"
    sw.touch()
    broker = MockBroker(market_open=False)
    res = _runner(broker, kill_switch_path=str(sw)).run(TW, "20260716", dry_run=True)
    assert res.dry_run is True and len(res.plan.orders) == 2


# --- B: 매도 sellable 상한 ---

def test_sell_clamped_to_sellable():
    # NVDA 보유 3주지만 매도가능 1.5주(T+N 미결제) → 매도수량 1.5로 clamp.
    broker = MockBroker(holdings={"NVDA": 3.0}, sellable={"NVDA": 1.5}, buying_power=0.0)
    state = ManagedState(managed={"NVDA"}, bootstrapped=True)
    res = _runner(broker, managed_state=state).run({"AAPL": 1.0}, "20260716", dry_run=False)
    sells = [o for o in broker.placed if o.side == "SELL"]
    assert len(sells) == 1 and sells[0].value == 1.5
    assert ("NVDA", "sell_clamped_to_sellable") in res.plan.skipped


def test_sell_clamp_rounds_down_not_up():
    # sellable가 소수 다자리면 반올림 시 올림돼 초과매도 위험 → 내림 확인.
    broker = MockBroker(holdings={"NVDA": 5.0}, sellable={"NVDA": 2.999999999}, buying_power=0.0)
    state = ManagedState(managed={"NVDA"}, bootstrapped=True)
    _runner(broker, managed_state=state).run({"AAPL": 1.0}, "20260716", dry_run=False)
    sell = [o for o in broker.placed if o.side == "SELL"][0]
    assert sell.value <= 2.999999999     # 내림(round면 3.0으로 초과)


def test_sell_skipped_when_not_sellable():
    broker = MockBroker(holdings={"NVDA": 3.0}, sellable={"NVDA": 0.0}, buying_power=0.0)
    state = ManagedState(managed={"NVDA"}, bootstrapped=True)
    res = _runner(broker, managed_state=state).run({"AAPL": 1.0}, "20260716", dry_run=False)
    assert [o for o in broker.placed if o.side == "SELL"] == []   # 매도 안 함
    assert ("NVDA", "not_sellable_settlement") in res.plan.skipped


# --- C: max-loss 배선 (봇 관리분 당일손익) ---

def test_max_loss_gate_blocks_when_managed_loss_exceeds():
    # 봇 관리 NVDA 당일손실 -50 → 손실상한 40 초과 → 발주 0.
    broker = MockBroker(holdings={"NVDA": 3.0}, daily_pnl={"NVDA": -50.0}, buying_power=700.0)
    state = ManagedState(managed={"NVDA"}, bootstrapped=True)
    cb = CircuitBreaker(max_orders_per_day=100, max_loss_usd=40.0)
    with pytest.raises(CircuitBreakerTripped):
        _runner(broker, managed_state=state, circuit_breaker=cb).run(TW, "20260716", dry_run=False)
    assert broker.placed == []            # 상한 초과 → 주문 0건


def test_max_loss_gate_excludes_manual_holdings():
    # 사용자 수동 보유(X) NVDA 당일손실 -999라도 봇 관리셋 아님 → 게이트에 안 잡힘.
    broker = MockBroker(holdings={"NVDA": 3.0}, daily_pnl={"NVDA": -999.0}, buying_power=700.0)
    state = ManagedState(excluded={"NVDA"}, managed=set(), bootstrapped=True)
    cb = CircuitBreaker(max_orders_per_day=100, max_loss_usd=40.0)
    res = _runner(broker, managed_state=state, circuit_breaker=cb).run(TW, "20260716", dry_run=False)
    assert len(broker.placed) == 2        # 봇 손실 0 → 정상 발주


# --- D: 주문루프 하드닝 (에러코드 처리) ---

def test_rate_limit_retried_then_succeeds():
    broker = MockBroker(place_errors={"AAPL": ["rate-limit-exceeded", "rate-limit-exceeded"]})
    res = _runner(broker).run({"AAPL": 1.0}, "20260716", dry_run=False)
    assert len(broker.placed) == 1 and len(res.placed) == 1   # 2회 429 후 성공


def test_per_order_reject_skips_and_continues():
    # AAPL은 소수점 불가로 개별 거부, MSFT는 정상 발주 → 전체 중단 없이 계속.
    broker = MockBroker(place_errors={"AAPL": ["market-not-supported-for-stock"]})
    res = _runner(broker).run(TW, "20260716", dry_run=False)
    placed_syms = {o.symbol for o in broker.placed}
    assert placed_syms == {"MSFT"}
    assert ("AAPL", "market-not-supported-for-stock") in res.rejected


def test_market_closed_midrun_aborts_rest():
    broker = MockBroker(place_errors={"MSFT": ["amount-order-outside-regular-hours"]})
    # AAPL 먼저 성공, MSFT에서 장마감 코드 → 잔여 중단.
    res = _runner(broker).run(TW, "20260716", dry_run=False)
    assert res.aborted_reason and res.aborted_reason.startswith("aborted_midrun:")


def test_unknown_error_propagates():
    broker = MockBroker(place_errors={"AAPL": ["some-unexpected-code"]})
    with pytest.raises(Exception):
        _runner(broker).run({"AAPL": 1.0}, "20260716", dry_run=False)
