"""수집 신선도 게이트 단위테스트 (P0-3) — qlib 불요.

01_collect는 수집 실패 시 직전 CSV를 유지하고 exit 0으로 끝난다(개선9). 그 폴백이
하류로 전달되지 않으면 04_verify의 게이트 (2)(3)(4)가 전부 통과한다 — 각각 전역
달력의 마지막 날짜, instruments 개수, 종목 하나만 보기 때문이다. 한 종목이라도
최신이면 stale이 숨는다.

실행:  .venv/bin/python -m pytest tests/test_data_freshness.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "data_pipeline"))

from _common import stale_symbols


def _report(**symbols: str) -> dict:
    return {"symbols": {s: {"last_date": d} for s, d in symbols.items()}}


def test_all_fresh_passes():
    r = _report(AAPL="2026-08-14", MSFT="2026-08-14", NVDA="2026-08-13")
    assert stale_symbols(r) == []


def test_single_stale_symbol_detected():
    # ★ 핵심: 나머지가 최신이면 달력·개수·샘플 게이트는 전부 통과한다. 이 게이트만 잡는다.
    r = _report(AAPL="2026-08-14", MSFT="2026-08-14", OLD="2026-02-14")
    assert stale_symbols(r) == [("OLD", 181)]


def test_lag_measured_against_newest_not_today():
    """기준은 '오늘'이 아니라 표본 내 최신일이다.

    주말·휴장·오래된 스냅샷에서 전 종목이 동시에 stale로 뜨는 것을 막는다 —
    잡고 싶은 것은 '남들은 최신인데 혼자 뒤처진 종목'이다.
    """
    r = _report(A="2020-01-10", B="2020-01-09", C="2020-01-08")
    assert stale_symbols(r) == []


def test_threshold_boundary():
    r = _report(NEW="2026-08-14", EDGE="2026-08-04")      # 정확히 10일
    assert stale_symbols(r) == []
    r = _report(NEW="2026-08-14", EDGE="2026-08-03")      # 11일
    assert stale_symbols(r) == [("EDGE", 11)]


def test_custom_threshold():
    r = _report(NEW="2026-08-14", MID="2026-08-10")
    assert stale_symbols(r) == []
    assert stale_symbols(r, max_lag_days=2) == [("MID", 4)]


def test_missing_or_malformed_dates_are_skipped():
    # 날짜를 못 읽는 항목 때문에 게이트가 죽으면 안 된다 — 판정에서 빠질 뿐이다.
    r = {"symbols": {"OK": {"last_date": "2026-08-14"},
                     "NONE": {"last_date": None},
                     "BAD": {"last_date": "not-a-date"},
                     "EMPTY": {}}}
    assert stale_symbols(r) == []


def test_empty_report_is_not_a_failure():
    assert stale_symbols({"symbols": {}}) == []
    assert stale_symbols({}) == []
