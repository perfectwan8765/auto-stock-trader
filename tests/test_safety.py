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


def test_daily_loss_not_double_counted_on_rerun(tmp_path):
    """★ P0-1 회귀: 당일손익은 절대 스냅샷이라 재실행해도 누적되면 안 된다.

    종전에는 record_loss(+=)로 넣어, 같은 날 7번 재실행하면 -$100 손실이 $700으로
    불어나 상한에 걸렸다. 재기동 우회를 막으려던 영속이 반대로 정당한 매매를 막았다.
    """
    path = tmp_path / "cb.json"
    for _ in range(7):
        cb = CircuitBreaker(max_orders_per_day=99, max_loss_usd=700.0, path=path, day="20260718")
        cb.observe_daily_loss(100.0)      # 브로커가 매번 같은 값을 보고한다
        cb.guard()                        # 트립되면 안 된다
    assert cb.daily_loss_usd == 100.0


def test_daily_loss_absolute_assignment(tmp_path):
    # 손실이 줄어들면 그대로 줄어야 한다(대입). 이익으로 돌아서면 0.
    path = tmp_path / "cb.json"
    cb = CircuitBreaker(max_orders_per_day=99, max_loss_usd=700.0, path=path, day="20260718")
    cb.observe_daily_loss(300.0)
    cb.observe_daily_loss(120.0)
    assert cb.daily_loss_usd == 120.0
    cb.observe_daily_loss(-50.0)          # 이익 전환
    assert cb.daily_loss_usd == 0.0


def test_guard_sums_daily_and_realized(tmp_path):
    # 두 축은 합산해서 상한과 비교한다.
    cb = CircuitBreaker(max_orders_per_day=99, max_loss_usd=100.0,
                        path=tmp_path / "cb.json", day="20260718")
    cb.observe_daily_loss(60.0)
    cb.record_loss(30.0)
    cb.guard()                            # 90 < 100
    cb.record_loss(20.0)
    with pytest.raises(CircuitBreakerTripped):
        cb.guard()                        # 110 >= 100


def test_legacy_state_without_daily_loss(tmp_path):
    # 구 스키마(daily_loss_usd 없음) 상태 파일도 읽혀야 한다.
    path = tmp_path / "cb.json"
    path.write_text('{"day": "20260718", "orders_today": 3, "realized_loss_usd": 5.0}')
    cb = CircuitBreaker(max_orders_per_day=99, max_loss_usd=100.0, path=path, day="20260718")
    assert cb.orders_today == 3 and cb.realized_loss_usd == 5.0 and cb.daily_loss_usd == 0.0
