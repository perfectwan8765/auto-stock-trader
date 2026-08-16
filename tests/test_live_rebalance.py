"""scripts/live/rebalance.py 유틸 테스트 — 시그널 신선도(F1).

라이브 진입점은 패키지가 아니라 importlib로 파일에서 로드한다(모듈 최상위는 함수 정의뿐,
load_config 등 부작용은 main 안에서만).
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "live" / "rebalance.py"
_spec = importlib.util.spec_from_file_location("live_rebalance", _PATH)
live = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(live)


def test_signal_age_days_basic():
    assert live._signal_age_days("2026-07-16", date(2026, 7, 20)) == 4
    assert live._signal_age_days("2026-07-20", date(2026, 7, 20)) == 0


def test_signal_age_days_future_is_zero():
    # 미래 날짜 시그널은 음수 대신 0(too-old 판정에서 통과)
    assert live._signal_age_days("2026-07-25", date(2026, 7, 20)) == 0


# --- A4: 라이브 진입점 조립 검증 ---
#
# 지금까지 이 파일은 _signal_age_days(날짜 산술) 하나만 봤다. dry-run과 실제 돈 사이의
# 유일한 분기인 --confirm 게이트와 그 아래 조립부(config → broker → CircuitBreaker → runner)는
# 통째로 미검증이었다. seam 리팩터가 Broker를 바꾸면 조립이 깨져도 아무 테스트가 울리지 않는다.

import json as _json

import pytest


class _StubBroker:
    """Broker Protocol 최소 구현. 발주 호출을 기록한다."""

    def __init__(self, *_a, **_kw):
        self.placed = []

    def get_holdings(self):
        return {}

    def get_prices(self, symbols):
        return {s: 100.0 for s in symbols}

    def get_buying_power_usd(self):
        return 1000.0

    def get_sellable_quantity(self, symbol):
        return 0.0

    def get_daily_pnl_usd(self, symbols):
        return 0.0

    def is_market_open(self):
        return True

    def place(self, intent):
        self.placed.append(intent)
        return {"result": {"orderId": f"ord-{len(self.placed)}"}}

    def get_order(self, order_id):
        return {}


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """라이브 진입점을 실 브로커 없이 조립한다. 반환: (broker, cb_kwargs, argv_builder)."""
    broker = _StubBroker()
    cb_kwargs = {}

    monkeypatch.setattr(live, "load_config", lambda **kw: object())
    monkeypatch.setattr(live, "TossClient", lambda cfg: object())
    monkeypatch.setattr(live, "TossBroker", lambda client: broker)
    monkeypatch.setattr(live, "LOG_DIR", tmp_path / "logs")
    # main()이 시그널 경로를 ROOT 기준 상대경로로 출력하고, kill switch 기본값도 ROOT/KILL이다.
    # tmp_path로 옮겨야 저장소 밖 시그널을 쓸 수 있고 실제 KILL 파일에도 영향받지 않는다.
    monkeypatch.setattr(live, "ROOT", tmp_path)

    real_cb = live.CircuitBreaker

    def spy(*args, **kw):
        cb_kwargs.update(kw)
        return real_cb(*args, **kw)

    monkeypatch.setattr(live, "CircuitBreaker", spy)

    sig = tmp_path / "signal_20260716.json"

    def argv(*extra, signal_date="2026-07-16"):
        sig.write_text(_json.dumps(
            {"date": signal_date, "topk": 2, "weights": {"AAPL": 0.5, "MSFT": 0.5}}))
        monkeypatch.setattr(live.sys, "argv", [
            "rebalance.py", "--signal", str(sig),
            "--state", str(tmp_path / "state.json"),
            "--circuit-state", str(tmp_path / "cb.json"),
            *extra,
        ])

    return broker, cb_kwargs, argv


def test_dry_run_never_places_order(wired, monkeypatch):
    """★ --confirm 없으면 실발주가 절대 없다. 이 게이트가 dry-run과 실제 돈을 가른다."""
    broker, _, argv = wired
    argv()                                    # --confirm 없음
    monkeypatch.setattr(live, "_signal_age_days", lambda *a: 0)
    live.main()
    assert broker.placed == []


def test_confirm_places_orders(wired, monkeypatch):
    # 게이트가 항상 막기만 하면 위 테스트는 무의미하다 — 반대 방향도 고정한다.
    broker, _, argv = wired
    argv("--confirm")
    monkeypatch.setattr(live, "_signal_age_days", lambda *a: 0)
    live.main()
    assert len(broker.placed) == 2


def test_circuit_breaker_day_comes_from_signal_date(wired, monkeypatch):
    """서킷브레이커의 '일일' 경계는 시그널 날짜여야 한다.

    로컬 날짜를 쓰면 정규장이 KST 자정을 넘길 때 경계가 어긋나 카운터가 조기 리셋되고,
    재기동 우회 방지(E10)가 무력화된다.
    """
    _, cb_kwargs, argv = wired
    argv(signal_date="2026-07-16")
    monkeypatch.setattr(live, "_signal_age_days", lambda *a: 0)
    live.main()
    assert cb_kwargs["day"] == "20260716"     # 하이픈 없는 리밸 일자


def test_stale_signal_blocks_live_but_not_dry_run(wired, monkeypatch, capsys):
    """오래된 시그널: 실발주는 거부, dry-run은 경고 후 계획만."""
    broker, _, argv = wired
    monkeypatch.setattr(live, "_signal_age_days", lambda *a: 99)

    argv("--confirm")
    with pytest.raises(SystemExit, match="중단"):
        live.main()
    assert broker.placed == []

    argv()                                    # dry-run
    live.main()
    assert broker.placed == []
    assert "dry-run이라 계획만" in capsys.readouterr().out
