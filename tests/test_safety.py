"""안전장치 단위테스트 (개선4): kill switch · 서킷브레이커."""
from __future__ import annotations

import pytest

from execution.errors import CircuitBreakerTripped, KillSwitchActive
from execution.safety import CircuitBreaker, check_kill_switch


def test_kill_switch_inactive_when_absent(tmp_path):
    check_kill_switch(tmp_path / "STOP")  # 파일 없음 → 통과(예외 없음)


def test_kill_switch_active_when_present(tmp_path):
    sw = tmp_path / "STOP"
    sw.touch()
    with pytest.raises(KillSwitchActive):
        check_kill_switch(sw)


def test_circuit_breaker_order_count():
    cb = CircuitBreaker(max_orders_per_day=2, max_loss_usd=100.0)
    cb.guard(); cb.record_order()
    cb.guard(); cb.record_order()
    with pytest.raises(CircuitBreakerTripped):
        cb.guard()  # 3번째 → 상한(2) 초과


def test_circuit_breaker_loss_limit():
    cb = CircuitBreaker(max_orders_per_day=100, max_loss_usd=50.0)
    cb.guard()
    cb.record_loss(60.0)
    with pytest.raises(CircuitBreakerTripped):
        cb.guard()  # 손실 60 > 50
