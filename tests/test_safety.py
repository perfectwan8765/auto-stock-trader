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


def test_circuit_breaker_survives_restart(tmp_path):
    # ★ E10 회귀: 상한에 걸려 멈춘 뒤 재기동해도 카운터가 유지돼야 한다.
    path = tmp_path / "cb.json"
    cb = CircuitBreaker(max_orders_per_day=2, max_loss_usd=100.0, path=path, day="20260718")
    cb.record_order()
    cb.record_order()
    with pytest.raises(CircuitBreakerTripped):
        cb.guard()

    revived = CircuitBreaker(max_orders_per_day=2, max_loss_usd=100.0, path=path, day="20260718")
    assert revived.orders_today == 2
    with pytest.raises(CircuitBreakerTripped):
        revived.guard()   # 재시작으로 우회되지 않는다


def test_circuit_breaker_resets_on_new_day(tmp_path):
    path = tmp_path / "cb.json"
    cb = CircuitBreaker(max_orders_per_day=2, max_loss_usd=100.0, path=path, day="20260718")
    cb.record_order()
    cb.record_loss(50.0)

    next_day = CircuitBreaker(max_orders_per_day=2, max_loss_usd=100.0, path=path, day="20260719")
    assert next_day.orders_today == 0 and next_day.realized_loss_usd == 0.0
    next_day.guard()   # 새 날이므로 통과


def test_circuit_breaker_loss_persisted(tmp_path):
    path = tmp_path / "cb.json"
    cb = CircuitBreaker(max_orders_per_day=99, max_loss_usd=10.0, path=path, day="20260718")
    cb.record_loss(12.0)
    revived = CircuitBreaker(max_orders_per_day=99, max_loss_usd=10.0, path=path, day="20260718")
    with pytest.raises(CircuitBreakerTripped):
        revived.guard()


def test_circuit_breaker_in_memory_when_no_path():
    # path 없으면 종전대로 인메모리 — 드라이런·테스트 경로가 파일을 만들지 않는다.
    cb = CircuitBreaker(max_orders_per_day=1, max_loss_usd=1.0)
    cb.record_order()
    assert CircuitBreaker(max_orders_per_day=1, max_loss_usd=1.0).orders_today == 0


def test_circuit_breaker_corrupt_state_starts_clean(tmp_path):
    path = tmp_path / "cb.json"
    path.write_text("{ not json")
    cb = CircuitBreaker(max_orders_per_day=2, max_loss_usd=100.0, path=path, day="20260718")
    assert cb.orders_today == 0
