"""RebalanceRunner 단위테스트 (MockBroker — 실 API 불요).

order_sleep_s=0으로 rate-limit 간격을 꺼 테스트를 빠르게 유지.
"""
from __future__ import annotations

import json

import pytest

from execution.errors import CircuitBreakerTripped, ExecutionError, KillSwitchActive
from conftest import _as_broker_error
from execution.interface import AccountSnapshot, Fill, OrderIntent
from execution.managed import ManagedState
from execution.interface import RunnerPolicy
from execution.runner import RebalanceRunner
from execution.safety import CircuitBreaker




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
        self._orders: dict[str, OrderIntent] = {}

    def snapshot(self, target_symbols):
        symbols = sorted(set(target_symbols) | set(self._holdings))
        return AccountSnapshot(
            holdings=dict(self._holdings),
            prices={s: self._prices.get(s, 100.0) for s in symbols},
            buying_power_usd=self._buying_power,
            daily_pnl=dict(self._daily_pnl),
        )

    def get_sellable(self, symbols):
        return {s: self._sellable.get(s, self._holdings.get(s, 0.0)) for s in symbols}

    def is_market_open(self):
        return self._market_open

    def place(self, intent):
        errs = self._place_errors.get(intent.symbol)
        if errs:
            raise _as_broker_error(errs.pop(0))
        self.placed.append(intent)
        oid = f"ord-{len(self.placed)}"
        self._orders[oid] = intent
        return oid

    def get_fill(self, order_id):
        # 어댑터가 이미 스키마를 해석해 Fill로 준다 — 러너는 camelCase를 모른다.
        if order_id not in self._orders:
            return None
        return Fill(filled_quantity="1", avg_filled_price="101.5", filled_amount="101.5",
                    commission="0.1", tax="0")


def _runner(broker, **kw):
    policy_fields = {"min_order_usd", "budget_usd", "rebalance_band",
                     "order_sleep_s", "rate_limit_retries", "rate_limit_backoff_s"}
    pk = {k: kw.pop(k) for k in list(kw) if k in policy_fields}
    pk.setdefault("min_order_usd", 1.0)
    pk.setdefault("order_sleep_s", 0)
    pk.setdefault("rate_limit_backoff_s", 0)
    return RebalanceRunner(broker, RunnerPolicy(**pk), **kw)


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


def test_fills_captured_with_order_id():
    # 발주 응답의 orderId로 체결을 되받아 RunResult.fills에 담는다(슬리피지 계산 입력).
    b = MockBroker(prices={"AAPL": 100.0})
    res = _runner(b).run({"AAPL": 1.0}, "20260718", dry_run=False)
    assert len(res.fills) == 1
    f = res.fills[0]
    assert f["symbol"] == "AAPL" and f["order_id"] == "ord-1"
    assert f["avg_filled_price"] == "101.5" and f["commission"] == "0.1"


class _NoQueryBroker(MockBroker):
    """체결 조회를 지원하지 않는 브로커 — 미지원이면 None을 준다.

    종전에는 속성 부재를 인위적으로 위조해야 했다. Protocol이 체결조회를 필수로 선언하면서
    러너는 hasattr로 선택 취급하던 모순의 대가였다. get_fill이
    `Fill | None`이라 그 위조가 필요 없다."""

    def get_fill(self, order_id):
        return None


def test_fills_recorded_without_values_when_broker_cannot_query():
    """체결 조회 미지원 브로커: 주문 추적 정보는 남기고 체결 값만 빈다.

    종전에는 행 자체를 버려 fills == [] 였다. 그러면 orderId까지 사라져 나중에 다시
    조회할 실마리가 없다. 값이 비는 것과 기록이 없는 것은 다르다.
    """
    b = _NoQueryBroker(prices={"AAPL": 100.0})
    res = _runner(b).run({"AAPL": 1.0}, "20260718", dry_run=False)
    assert res.placed and len(res.fills) == 1
    assert res.fills[0]["order_id"] == "ord-1"
    assert "avg_filled_price" not in res.fills[0]


def test_snapshot_records_decision_inputs():
    # 결정 시점 입력(가격·밴드·예수금)이 남아야 사후에 주문 근거를 재구성할 수 있다.
    b = MockBroker(prices={"AAPL": 100.0}, buying_power=500.0)
    res = _runner(b, rebalance_band=0.10).run({"AAPL": 1.0}, "20260718", dry_run=True)
    assert res.snapshot["prices"]["AAPL"] == 100.0
    assert res.snapshot["rebalance_band"] == 0.10
    assert res.snapshot["buying_power_usd"] == 500.0


def test_circuit_breaker_persists_through_runner(tmp_path):
    """★ E10 통합: 러너의 발주 루프가 카운터를 파일에 남기고, 재기동이 상한을 우회하지 못한다.

    safety 단위테스트는 CircuitBreaker 자체를 검증한다. 여기서 보는 것은 **배선** —
    러너가 record_order()를 실제로 호출하는가, 그 결과가 파일에 남는가다.
    """
    path = tmp_path / "cb.json"
    b = MockBroker(prices={"AAPL": 100.0, "MSFT": 100.0}, buying_power=700.0)
    cb = CircuitBreaker(max_orders_per_day=1, max_loss_usd=1e9, path=path, day="20260718")

    with pytest.raises(CircuitBreakerTripped):
        _runner(b, circuit_breaker=cb).run({"AAPL": 0.5, "MSFT": 0.5}, "20260718", dry_run=False)

    assert len(b.placed) == 1                      # 상한이 두 번째 주문을 막았다
    assert json.loads(path.read_text())["orders_today"] == 1

    # 재기동: 같은 날 다시 띄워도 첫 guard에서 즉시 트립 → 주문 0건
    b2 = MockBroker(prices={"AAPL": 100.0}, buying_power=700.0)
    cb2 = CircuitBreaker(max_orders_per_day=1, max_loss_usd=1e9, path=path, day="20260718")
    with pytest.raises(CircuitBreakerTripped):
        _runner(b2, circuit_breaker=cb2).run({"AAPL": 1.0}, "20260718", dry_run=False)
    assert b2.placed == []


def test_circuit_breaker_state_absent_in_dry_run(tmp_path):
    # dry-run은 발주하지 않으므로 카운터도 파일도 건드리지 않는다.
    path = tmp_path / "cb.json"
    b = MockBroker(prices={"AAPL": 100.0})
    cb = CircuitBreaker(max_orders_per_day=1, max_loss_usd=1e9, path=path, day="20260718")
    _runner(b, circuit_breaker=cb).run({"AAPL": 1.0}, "20260718", dry_run=True)
    assert not path.exists() and b.placed == []


class _RaisingQueryBroker(MockBroker):
    def get_fill(self, order_id):
        raise RuntimeError("boom")


# 스키마 불일치 검증은 tests/test_broker.py로 옮겼다
# (test_get_fill_returns_none_when_execution_absent). 응답 필드를 해석하는 주체가
# 러너에서 어댑터로 넘어갔으므로, 스키마가 틀렸는지도 실측 픽스처 옆에서 봐야 한다.
# 종전 테스트는 print 경고 문자열을 계약 대신 단언하고 있었다 — 러너에 검증할 실응답이
# 없으니 그것 말고 확인할 게 없었기 때문이다.


def test_fill_query_failure_does_not_lose_order():
    # 조회가 터져도 발주 결과를 버리지 않는다(사유는 기록).
    b = _RaisingQueryBroker(prices={"AAPL": 100.0})
    res = _runner(b).run({"AAPL": 1.0}, "20260718", dry_run=False)
    assert res.placed and res.fills[0]["fetch_error"] == "RuntimeError"


def test_daily_loss_not_double_counted_across_runner_reruns(tmp_path):
    """★ P0-1 배선 회귀: 러너가 절대 스냅샷을 증분 API로 넘기지 않는지 본다.

    safety 쪽 단위테스트는 CircuitBreaker의 두 축을 검증할 뿐, **러너가 어느 쪽을
    호출하는지**는 보지 못한다. 버그는 배선에 있었으므로(observe_daily_loss ↔ record_loss)
    러너를 통과시켜야 잡힌다. 이 테스트가 없으면 배선을 되돌려도 전 스위트가 통과한다.
    """
    path = tmp_path / "cb.json"
    for _ in range(7):                       # 같은 날 7번 재실행
        broker = MockBroker(prices={"NVDA": 100.0}, buying_power=700.0,
                            daily_pnl={"NVDA": -100.0})
        state = ManagedState(excluded=set(), managed={"NVDA"}, bootstrapped=True)
        cb = CircuitBreaker(max_orders_per_day=99, max_loss_usd=700.0,
                            path=path, day="20260718")
        _runner(broker, managed_state=state, circuit_breaker=cb).run(
            {"NVDA": 1.0}, "20260718", dry_run=False)

    # 실제 당일손실은 -$100 하나뿐이다. 누적됐다면 700에 도달해 트립했을 것이다.
    assert cb.daily_loss_usd == 100.0
    assert json.loads(path.read_text())["daily_loss_usd"] == 100.0
    cb.guard()                               # 상한 700 미만이므로 통과해야 한다


def test_daily_loss_survives_liquidation_of_losing_position(tmp_path):
    """★ 손실 종목을 청산해도 그날 손실이 지워지지 않는다.

    청산하면 그 종목이 holdings에서 사라지고 daily_pnl에도 없다. 관리셋 합산이 0이나 이익이
    되므로 단순 대입이면 영속된 손실이 덮어써진다 — **손실을 확정하는 행위가 상한을 해제한다.**
    상한이 걸려야 할 바로 그날 안전판이 풀리므로 fail-open이다.

    safety 쪽 단위테스트는 CircuitBreaker의 워터마크 동작만 본다. 이 시나리오는 러너가
    daily_pnl을 어떻게 합산해 넘기는지까지 걸려 있어 러너를 통과시켜야 잡힌다.
    """
    path = tmp_path / "cb.json"

    # 1회차 — NVDA -600, MSFT +10. 관리셋 합산 손실 590이 영속된다(상한 700).
    broker = MockBroker(holdings={"MSFT": 1.0, "NVDA": 1.0},
                        prices={"MSFT": 100.0, "NVDA": 100.0}, buying_power=0.0,
                        daily_pnl={"MSFT": 10.0, "NVDA": -600.0})
    state = ManagedState(managed={"MSFT", "NVDA"}, bootstrapped=True)
    cb = CircuitBreaker(max_orders_per_day=99, max_loss_usd=700.0, path=path, day="20260718")
    _runner(broker, managed_state=state, circuit_breaker=cb).run(
        {"MSFT": 0.5, "NVDA": 0.5}, "20260718", dry_run=False)
    assert cb.daily_loss_usd == 590.0

    # 2회차 — NVDA 청산 완료. holdings·daily_pnl·관리셋 어디에도 없다.
    broker2 = MockBroker(holdings={"MSFT": 1.0}, prices={"MSFT": 100.0}, buying_power=0.0,
                         daily_pnl={"MSFT": 10.0})
    state2 = ManagedState(managed={"MSFT"}, bootstrapped=True)
    cb2 = CircuitBreaker(max_orders_per_day=99, max_loss_usd=700.0, path=path, day="20260718")
    _runner(broker2, managed_state=state2, circuit_breaker=cb2).run(
        {"MSFT": 1.0}, "20260718", dry_run=False)

    assert cb2.daily_loss_usd == 590.0
    assert json.loads(path.read_text())["daily_loss_usd"] == 590.0


# --- B4: 읽기 호출 축소 ---

def test_sellable_queried_only_for_sell_symbols():
    """매도 대상만 조회한다 — 보유 전 종목을 미리 받으면 호출이 오히려 늘어난다.

    보유 5종목 중 목표에서 빠진 1종목만 판다. sellable을 스냅샷에 넣었다면 5건을 조회했을 것이다.
    """
    asked = []

    class Spy(MockBroker):
        def get_sellable(self, symbols):
            asked.append(list(symbols))
            return super().get_sellable(symbols)

    holdings = {s: 1.0 for s in ("AAA", "BBB", "CCC", "DDD", "EEE")}
    broker = Spy(holdings=holdings, buying_power=0.0)
    state = ManagedState(managed=set(holdings), bootstrapped=True)
    keep = {s: 0.25 for s in ("AAA", "BBB", "CCC", "DDD")}
    _runner(broker, managed_state=state).run(keep, "20260716", dry_run=True)

    assert asked == [["EEE"]]


def test_snapshot_is_fetched_once_per_run():
    # 시점이 섞이면 예산 계산이 흔들린다 — 한 실행에 한 번만 읽는다.
    calls = []

    class Spy(MockBroker):
        def snapshot(self, target_symbols):
            calls.append(target_symbols)
            return super().snapshot(target_symbols)

    _runner(Spy(buying_power=700.0)).run(TW, "20260716", dry_run=False)
    assert len(calls) == 1


# --- 리뷰 조치: 배치 조회·추적 불가 주문 ---

def test_unreported_sellable_symbol_aborts():
    """조회 안 된 심볼을 0으로 보면 매도가 '미결제'로 둔갑해 조용히 사라진다."""
    class Partial(MockBroker):
        def get_sellable(self, symbols):
            return {}                       # 요청은 받았지만 아무것도 안 돌려줌

    broker = Partial(holdings={"NVDA": 3.0}, buying_power=0.0)
    state = ManagedState(managed={"NVDA"}, bootstrapped=True)
    with pytest.raises(ExecutionError, match="매도가능수량 미조회"):
        _runner(broker, managed_state=state).run({"AAPL": 1.0}, "20260716", dry_run=True)


def test_order_without_id_is_still_recorded():
    """주문 ID를 못 받아도 발주 사실은 남는다 — 없으면 나중에 조회할 실마리가 없다."""
    class NoId(MockBroker):
        def place(self, intent):
            self.placed.append(intent)
            return ""

    broker = NoId(prices={"AAPL": 100.0}, buying_power=700.0)
    res = _runner(broker).run({"AAPL": 1.0}, "20260718", dry_run=False)
    assert res.placed and len(res.fills) == 1
    assert res.fills[0]["fetch_error"] == "no_order_id"
    assert res.fills[0]["client_order_id"] == res.placed[0]


def test_settlement_date_reaches_order_log():
    """어댑터가 담은 결제일이 주문로그까지 흘러야 원장이 나중에 읽을 수 있다."""
    class WithSettlement(MockBroker):
        def get_fill(self, order_id):
            return Fill(filled_quantity=1.0, avg_filled_price=101.5,
                        settlement_date="2026-07-22")

    broker = WithSettlement(prices={"AAPL": 100.0}, buying_power=700.0)
    res = _runner(broker).run({"AAPL": 1.0}, "20260718", dry_run=False)
    assert res.fills[0]["settlement_date"] == "2026-07-22"
