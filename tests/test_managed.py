"""화이트리스트(ManagedState) + runner 통합 테스트 — 사용자 보유·현금 보호 검증."""
from __future__ import annotations

import pytest

from execution.errors import ExecutionError
from execution.interface import OrderIntent
from execution.managed import ManagedState
from execution.runner import RebalanceRunner


class MockBroker:
    def __init__(self, holdings=None, prices=None, buying_power=10000.0, market_open=True):
        self._holdings = holdings or {}
        self._prices = prices or {}
        self._buying_power = buying_power
        self._market_open = market_open
        self.placed: list[OrderIntent] = []

    def get_holdings(self):
        return dict(self._holdings)

    def get_prices(self, symbols):
        return {s: self._prices.get(s, 100.0) for s in symbols}

    def get_buying_power_usd(self):
        return self._buying_power

    def is_market_open(self):
        return self._market_open

    def place(self, intent):
        self.placed.append(intent)
        return {"status": "ACCEPTED"}


# --- ManagedState 단위 ---

def test_bootstrap_freezes_current_holdings_as_excluded():
    st = ManagedState()
    st.bootstrap({"AAPL": 5.0, "TSLA": 2.0, "ZERO": 0.0})
    assert st.excluded == {"AAPL", "TSLA"}   # 수량>0만
    assert st.bootstrapped is True


def test_state_roundtrip(tmp_path):
    p = tmp_path / "managed_state.json"
    st = ManagedState(excluded={"AAPL"}, managed={"NVDA"}, bootstrapped=True, path=p)
    st.save()
    loaded = ManagedState.load(p)
    assert loaded.excluded == {"AAPL"} and loaded.managed == {"NVDA"} and loaded.bootstrapped


def test_update_after_place_adds_buys_removes_exits():
    st = ManagedState(managed={"OLD"}, bootstrapped=True)
    orders = [
        OrderIntent("OLD", "SELL", "quantity", 3.0, "cid-old", "exit"),
        OrderIntent("NEW", "BUY", "amount", 50.0, "cid-new", "enter"),
        OrderIntent("SKIP", "BUY", "amount", 50.0, "cid-skip", "enter"),
    ]
    st.update_after_place(orders, placed_ids=["cid-old", "cid-new"])  # cid-skip 미발주
    assert st.managed == {"NEW"}             # OLD 편출 제거, NEW 추가, SKIP 미반영


# --- runner 통합: 보호 동작 ---

def test_manual_holding_never_sold():
    # 사용자가 TSLA 수동 보유. 봇 목표는 AAPL. TSLA는 목표에 없지만 절대 매도되면 안 됨.
    broker = MockBroker(holdings={"TSLA": 10.0})
    state = ManagedState(excluded={"TSLA"}, managed=set(), bootstrapped=True)
    res = RebalanceRunner(broker, min_order_usd=1.0, budget_usd=700.0,
                          managed_state=state).run({"AAPL": 1.0}, "20260716", dry_run=False)
    assert all(o.symbol != "TSLA" for o in broker.placed)   # TSLA 매매 없음
    assert any(o.symbol == "AAPL" and o.side == "BUY" for o in broker.placed)


def test_target_overlapping_manual_is_skipped():
    # 봇 목표에 TSLA가 있어도, 사용자 수동 보유(X)면 스킵.
    broker = MockBroker(holdings={"TSLA": 10.0})
    state = ManagedState(excluded={"TSLA"}, managed=set(), bootstrapped=True)
    res = RebalanceRunner(broker, min_order_usd=1.0, budget_usd=700.0,
                          managed_state=state).run({"TSLA": 0.5, "AAPL": 0.5}, "20260716", dry_run=True)
    assert all(o.symbol != "TSLA" for o in res.plan.orders)
    assert ("TSLA", "excluded_manual") in res.plan.skipped


def test_first_live_run_bootstraps_and_persists(tmp_path):
    # 상태 없음 + 실발주 → 현재 보유가 X로 동결·저장되고, 그 보유는 안 팔림.
    broker = MockBroker(holdings={"TSLA": 10.0})
    p = tmp_path / "managed_state.json"
    state = ManagedState.load(p)   # 파일 없음 → bootstrapped=False
    RebalanceRunner(broker, min_order_usd=1.0, budget_usd=700.0,
                    managed_state=state).run({"AAPL": 1.0}, "20260716", dry_run=False)
    assert p.exists()
    saved = ManagedState.load(p)
    assert "TSLA" in saved.excluded            # 기존 보유 동결
    assert "AAPL" in saved.managed             # 봇 매수분 관리셋 반영
    assert all(o.symbol != "TSLA" for o in broker.placed)


def test_budget_caps_buying():
    # 예산 $700인데 계좌현금 10000 → 매수합은 예산 내(≤700).
    broker = MockBroker(holdings={}, buying_power=10000.0)
    state = ManagedState(bootstrapped=True)   # 빈 계좌 동결
    res = RebalanceRunner(broker, min_order_usd=1.0, budget_usd=700.0,
                          managed_state=state).run({"AAPL": 0.5, "MSFT": 0.5}, "20260716", dry_run=True)
    total_buy = sum(o.value for o in res.plan.orders if o.side == "BUY")
    assert total_buy <= 700.0 + 1e-6


def test_dry_run_does_not_persist_state(tmp_path):
    # dry-run은 상태 저장 안 함(read-only) → 오프라인 프리뷰가 라이브 부트스트랩을 오염 안 시킴.
    broker = MockBroker(holdings={"TSLA": 10.0})
    p = tmp_path / "managed_state.json"
    state = ManagedState.load(p)
    RebalanceRunner(broker, min_order_usd=1.0, budget_usd=700.0,
                    managed_state=state).run({"AAPL": 1.0}, "20260716", dry_run=True)
    assert not p.exists()


def test_dry_run_does_not_flip_bootstrapped(tmp_path):
    # F1: dry-run이 state.bootstrapped를 True로 바꾸면 안 됨(같은 객체 라이브 시 보호 무력화 방지).
    broker = MockBroker(holdings={"TSLA": 10.0})
    state = ManagedState.load(tmp_path / "s.json")  # bootstrapped=False
    runner = RebalanceRunner(broker, min_order_usd=1.0, budget_usd=700.0, managed_state=state)
    runner.run({"AAPL": 1.0}, "20260716", dry_run=True)
    assert state.bootstrapped is False          # dry-run 후에도 미부트스트랩
    # 이어서 같은 객체로 실발주 → 이제 실제 보유로 동결·보호
    runner.run({"AAPL": 1.0}, "20260716", dry_run=False)
    assert state.bootstrapped is True and "TSLA" in state.excluded
    assert all(o.symbol != "TSLA" for o in broker.placed)


def test_missing_price_for_held_symbol_aborts():
    # F2: 봇 보유 종목 가격 누락 → 예산 왜곡·과지출 위험 → 안전 중단.
    class NoPriceBroker(MockBroker):
        def get_prices(self, symbols):
            return {}  # 가격 전부 누락
    broker = NoPriceBroker(holdings={"NVDA": 3.0})
    state = ManagedState(managed={"NVDA"}, bootstrapped=True)
    with pytest.raises(ExecutionError):
        RebalanceRunner(broker, min_order_usd=1.0, budget_usd=700.0,
                        managed_state=state).run({"AAPL": 1.0}, "20260716", dry_run=True)
