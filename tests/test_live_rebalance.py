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
