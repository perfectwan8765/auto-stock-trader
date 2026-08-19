"""scripts/live/rebalance.py 유틸 테스트 — 시그널 신선도(F1).

라이브 진입점은 패키지가 아니라 importlib로 파일에서 로드한다(모듈 최상위는 함수 정의뿐,
load_config 등 부작용은 main 안에서만).
"""
from __future__ import annotations

import importlib.util
import json as _json
from datetime import date, datetime
from pathlib import Path

import pytest

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


class _StubBroker:
    """Broker Protocol 최소 구현. 발주 호출을 기록한다."""

    def __init__(self, *_a, **_kw):
        self.placed = []

    def snapshot(self, target_symbols):
        from execution.interface import AccountSnapshot

        return AccountSnapshot(holdings={}, prices={s: 100.0 for s in target_symbols},
                               buying_power_usd=1000.0, daily_pnl={})

    def get_sellable(self, symbols):
        return {}

    def is_market_open(self):
        return True

    def place(self, intent):
        self.placed.append(intent)
        return f"ord-{len(self.placed)}"

    def get_fill(self, order_id):
        return None


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


def test_max_loss_default_is_reachable(wired, monkeypatch):
    """★ 손실 상한 기본값이 예산 기본값과 같으면 트립할 수 없다.

    종전 기본값은 --budget 기본값과 똑같은 700이었다. $700 예산에서 하루 $700을 잃으려면
    포트폴리오 전액이 사라져야 하므로 이 축은 사실상 무발동이었다. 배선을 고쳐도 임계값이
    도달 불가면 아무것도 안 바뀐다.
    """
    _, cb_kwargs, argv = wired
    argv()                                    # --max-loss 미지정 → 기본값
    monkeypatch.setattr(live, "_signal_age_days", lambda *a: 0)
    live.main()

    assert cb_kwargs["max_loss_usd"] == 70.0
    assert cb_kwargs["max_loss_usd"] < 700.0  # 예산 기본값으로 회귀하면 잡는다


def _clock_fixed_at(moment):
    """`live.datetime` 대역. now()만 고정하고 나머지는 진짜 datetime에 위임한다."""

    class _Clock:
        @staticmethod
        def now(tz=None):
            return moment.astimezone(tz) if tz is not None else moment

        @staticmethod
        def strptime(*a, **kw):
            return datetime.strptime(*a, **kw)

    return _Clock


def test_circuit_breaker_day_is_us_trading_date(wired, monkeypatch):
    """서킷브레이커의 '일일' 경계는 미국 거래일이다 — 시그널 날짜도 로컬 날짜도 아니다.

    종전 스펙은 시그널 날짜였고 그게 결함이었다. 양방향으로 깨진다 —
    같은 시그널을 여러 날 재사용하면(--max-age-days 기본 5) 카운터가 날짜를 넘겨 누적되고,
    시그널을 다시 만들면 같은 캘린더 날인데도 day 키가 바뀌어 _restore가 조기 return,
    주문건수·손실 상한이 통째로 0이 된다. 후자가 안전판 우회라 더 위험하다.

    종전 docstring이 우려한 "정규장이 KST 자정을 넘길 때 경계가 어긋난다"는 문제의식은
    그대로 유효하고, 미국 거래일이 그 우려를 로컬 날짜보다 정확히 해결한다 — 한 세션이
    한 day에 온전히 담긴다.
    """
    _, cb_kwargs, argv = wired
    argv(signal_date="2026-07-16")
    monkeypatch.setattr(live, "_signal_age_days", lambda *a: 0)
    # 13:00 ET = 익일 02:00 KST. 로컬(KST) 날짜는 7/21, 미국 거래일은 7/20 — 셋 다 다르다.
    monkeypatch.setattr(
        live, "datetime",
        _clock_fixed_at(datetime(2026, 7, 20, 13, 0, tzinfo=live.US_MARKET_TZ)))

    live.main()

    assert cb_kwargs["day"] == "20260720"      # 미국 거래일
    assert cb_kwargs["day"] != "20260716"      # 시그널 날짜로 회귀하면 잡는다
    assert cb_kwargs["day"] != "20260721"      # 로컬 날짜로 가도 잡는다


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
