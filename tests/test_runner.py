"""RebalanceRunner 단위테스트 (MockBroker — 실 API 불요)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from execution.errors import CircuitBreakerTripped, KillSwitchActive  # noqa: E402
from execution.interface import OrderIntent  # noqa: E402
from execution.runner import RebalanceRunner  # noqa: E402
from execution.safety import CircuitBreaker  # noqa: E402


class MockBroker:
    def __init__(self, holdings=None, prices=None, buying_power=700.0, market_open=True):
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
        return {"clientOrderId": intent.client_order_id, "status": "ACCEPTED"}


TW = {"AAPL": 0.5, "MSFT": 0.5}


def test_dry_run_no_orders_placed():
    broker = MockBroker()
    res = RebalanceRunner(broker, min_order_usd=1.0).run(TW, "20260716", dry_run=True)
    assert res.dry_run is True
    assert broker.placed == []            # 실발주 없음
    assert len(res.plan.orders) == 2      # 계획은 산출


def test_live_places_orders():
    broker = MockBroker(buying_power=700.0)
    res = RebalanceRunner(broker, min_order_usd=1.0).run(TW, "20260716", dry_run=False)
    assert res.dry_run is False
    assert len(broker.placed) == 2
    assert set(res.placed) == {o.client_order_id for o in broker.placed}


def test_market_closed_aborts():
    broker = MockBroker(market_open=False)
    res = RebalanceRunner(broker, min_order_usd=1.0).run(TW, "20260716", dry_run=False)
    assert res.aborted_reason == "market_closed"
    assert broker.placed == []            # 개선6: 정규장 아니면 발주 안 함


def test_kill_switch_blocks_live(tmp_path):
    sw = tmp_path / "STOP"
    sw.touch()
    broker = MockBroker()
    runner = RebalanceRunner(broker, min_order_usd=1.0, kill_switch_path=str(sw))
    with pytest.raises(KillSwitchActive):
        runner.run(TW, "20260716", dry_run=False)
    assert broker.placed == []


def test_circuit_breaker_stops_mid_run():
    broker = MockBroker()
    cb = CircuitBreaker(max_orders_per_day=1, max_loss_usd=1e9)
    runner = RebalanceRunner(broker, min_order_usd=1.0, circuit_breaker=cb)
    with pytest.raises(CircuitBreakerTripped):
        runner.run(TW, "20260716", dry_run=False)
    assert len(broker.placed) == 1        # 1건 후 상한 → 중단


def test_dry_run_does_not_check_market_or_kill_switch(tmp_path):
    # dry-run은 안전장치 우회(계획만) — kill switch 있어도 계획 산출.
    sw = tmp_path / "STOP"
    sw.touch()
    broker = MockBroker(market_open=False)
    res = RebalanceRunner(broker, min_order_usd=1.0, kill_switch_path=str(sw)).run(TW, "20260716", dry_run=True)
    assert res.dry_run is True and len(res.plan.orders) == 2
