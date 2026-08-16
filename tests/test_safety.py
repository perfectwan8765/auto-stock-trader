"""안전장치 단위테스트 (개선4): kill switch · 서킷브레이커."""
from __future__ import annotations

import json

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
    cb.guard(side="BUY"); cb.record_order()
    cb.guard(side="BUY"); cb.record_order()
    with pytest.raises(CircuitBreakerTripped):
        cb.guard(side="BUY")  # 3번째 → 상한(2) 초과


def test_circuit_breaker_loss_limit():
    cb = CircuitBreaker(max_orders_per_day=100, max_loss_usd=50.0)
    cb.guard(side="BUY")
    cb.record_loss(60.0)
    with pytest.raises(CircuitBreakerTripped):
        cb.guard(side="BUY")  # 손실 60 > 50


def test_circuit_breaker_survives_restart(tmp_path):
    # ★ E10 회귀: 상한에 걸려 멈춘 뒤 재기동해도 카운터가 유지돼야 한다.
    path = tmp_path / "cb.json"
    cb = CircuitBreaker(max_orders_per_day=2, max_loss_usd=100.0, path=path, day="20260718")
    cb.record_order()
    cb.record_order()
    with pytest.raises(CircuitBreakerTripped):
        cb.guard(side="BUY")

    revived = CircuitBreaker(max_orders_per_day=2, max_loss_usd=100.0, path=path, day="20260718")
    assert revived.orders_today == 2
    with pytest.raises(CircuitBreakerTripped):
        revived.guard(side="BUY")   # 재시작으로 우회되지 않는다


def test_circuit_breaker_resets_on_new_day(tmp_path):
    path = tmp_path / "cb.json"
    cb = CircuitBreaker(max_orders_per_day=2, max_loss_usd=100.0, path=path, day="20260718")
    cb.record_order()
    cb.record_loss(50.0)

    next_day = CircuitBreaker(max_orders_per_day=2, max_loss_usd=100.0, path=path, day="20260719")
    assert next_day.orders_today == 0 and next_day.realized_loss_usd == 0.0
    next_day.guard(side="BUY")   # 새 날이므로 통과


def test_circuit_breaker_loss_persisted(tmp_path):
    path = tmp_path / "cb.json"
    cb = CircuitBreaker(max_orders_per_day=99, max_loss_usd=10.0, path=path, day="20260718")
    cb.record_loss(12.0)
    revived = CircuitBreaker(max_orders_per_day=99, max_loss_usd=10.0, path=path, day="20260718")
    with pytest.raises(CircuitBreakerTripped):
        revived.guard(side="BUY")


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
        cb.guard(side="BUY")              # 트립되면 안 된다
    assert cb.daily_loss_usd == 100.0


def test_daily_loss_is_watermark_not_assignment(tmp_path):
    """★ 당일 손실은 그날의 최대치로 유지된다 — 값이 줄어도 따라 내려가지 않는다.

    종전 스펙은 단순 대입이었고("이익 전환 시 0") 그게 결함이었다. 손실 난 관리 종목을
    청산하면 그 손익이 holdings 응답에서 사라져 다음 실행이 0을 대입한다 — **손실을 확정하는
    행위가 상한을 해제한다.** 상한이 걸려야 할 바로 그날 안전판이 풀리는 것이라 fail-open이다.

    대가로 장중에 손실이 이익으로 돌아서도 그날은 상한이 유지된다. 의도한 선택이다.
    """
    path = tmp_path / "cb.json"
    cb = CircuitBreaker(max_orders_per_day=99, max_loss_usd=700.0, path=path, day="20260718")
    cb.observe_daily_loss(300.0)
    assert cb.daily_loss_usd == 300.0
    cb.observe_daily_loss(120.0)          # 줄어도 최대치 유지
    assert cb.daily_loss_usd == 300.0
    cb.observe_daily_loss(-50.0)          # 이익 전환도 지우지 않는다
    assert cb.daily_loss_usd == 300.0
    assert json.loads(path.read_text())["daily_loss_usd"] == 300.0

    # 재기동해도 워터마크가 살아 있어야 한다 — 영속이 목적이었다.
    revived = CircuitBreaker(max_orders_per_day=99, max_loss_usd=700.0, path=path, day="20260718")
    assert revived.daily_loss_usd == 300.0


def test_guard_sums_daily_and_realized(tmp_path):
    # 두 축은 합산해서 상한과 비교한다.
    cb = CircuitBreaker(max_orders_per_day=99, max_loss_usd=100.0,
                        path=tmp_path / "cb.json", day="20260718")
    cb.observe_daily_loss(60.0)
    cb.record_loss(30.0)
    cb.guard(side="BUY")                  # 90 < 100
    cb.record_loss(20.0)
    with pytest.raises(CircuitBreakerTripped):
        cb.guard(side="BUY")              # 110 >= 100


def test_loss_limit_blocks_buys_but_not_sells():
    """★ 손실 상한은 매수만 막는다 — 청산(리스크 축소)까지 막으면 방향이 거꾸로다.

    주문건수 상한은 폭주 방지가 목적이라 매도에도 그대로 적용된다.
    """
    cb = CircuitBreaker(max_orders_per_day=100, max_loss_usd=50.0)
    cb.observe_daily_loss(60.0)
    cb.guard(side="SELL")                 # 손실 60 > 50 이어도 매도는 통과
    with pytest.raises(CircuitBreakerTripped):
        cb.guard(side="BUY")

    # 주문건수 축은 매도도 센다.
    counted = CircuitBreaker(max_orders_per_day=1, max_loss_usd=1e9)
    counted.record_order()
    with pytest.raises(CircuitBreakerTripped):
        counted.guard(side="SELL")


def test_guard_rejects_unknown_side():
    """오타를 조용히 넘기면 손실 상한이 통째로 비활성화된다 — 안전한 기본값이 없는 자리다.

    "BUY"로 접으면 오타 난 매도가 막히고(이 커밋이 고친 결함), "SELL"로 접으면 손실 상한이
    꺼진다. 어느 쪽도 보수적이지 않아 검증만 남는다.
    """
    cb = CircuitBreaker(max_orders_per_day=100, max_loss_usd=50.0)
    cb.observe_daily_loss(60.0)
    with pytest.raises(ValueError):
        cb.guard(side="buy")            # 소문자 — 현실적인 오타


def test_legacy_state_without_daily_loss(tmp_path):
    # 구 스키마(daily_loss_usd 없음) 상태 파일도 읽혀야 한다.
    path = tmp_path / "cb.json"
    path.write_text('{"day": "20260718", "orders_today": 3, "realized_loss_usd": 5.0}')
    cb = CircuitBreaker(max_orders_per_day=99, max_loss_usd=100.0, path=path, day="20260718")
    assert cb.orders_today == 3 and cb.realized_loss_usd == 5.0 and cb.daily_loss_usd == 0.0


# --- A3: 서킷브레이커 상태 원자적 쓰기 ---

def test_persist_leaves_no_partial_file_on_failure(tmp_path, monkeypatch):
    """카운터 flush가 실패해도 직전 상태가 잘리지 않는다.

    상한에 걸려 멈춘 상태 파일이 손상되면, 재기동 시 카운터가 0에서 다시 세어
    E10(재기동 우회 방지)이 무력화된다.
    """
    path = tmp_path / "cb.json"
    cb = CircuitBreaker(max_orders_per_day=5, max_loss_usd=100.0, path=path, day="20260718")
    cb.record_order()
    before = path.read_text()

    import execution.atomic as atomic_mod

    def boom(src, dst):
        raise OSError("디스크 가득")

    monkeypatch.setattr(atomic_mod.os, "replace", boom)
    with pytest.raises(OSError):
        cb.record_order()

    assert path.read_text() == before                  # 잘리지 않았다
    assert list(tmp_path.glob(".*tmp")) == []          # 임시파일 잔여 없음
    assert json.loads(before)["orders_today"] == 1
