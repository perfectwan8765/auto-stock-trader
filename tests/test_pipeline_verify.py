"""파이프라인 신선도 게이트 (6) — 번들 직접 스캔.

qlib 없이 돌린다. lag_by_symbol을 대역으로 바꿔 판정 로직만 본다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parent.parent / "scripts" / "data_pipeline"
sys.path.insert(0, str(_DIR))
verify = importlib.import_module("verify")


@pytest.fixture
def lags(monkeypatch):
    def setter(mapping):
        monkeypatch.setattr(verify, "lag_by_symbol", lambda qlib_dir: mapping)
    return setter


def test_flags_lagging_symbol(lags):
    lags({"AAA": 0, "BBB": 30})
    assert verify.stale_in_bundle(Path("x"), exclude=set()) == [("BBB", 30)]


def test_passes_when_all_fresh(lags):
    """양방향을 다 고정해야 항상 통과/항상 실패하는 상수 함수가 아님이 보장된다."""
    lags({"AAA": 0, "BBB": 1})
    assert verify.stale_in_bundle(Path("x"), exclude=set()) == []


def test_threshold_is_exclusive(lags):
    lags({"AAA": 10, "BBB": 11})
    assert verify.stale_in_bundle(Path("x"), max_lag_days=10, exclude=set()) == [("BBB", 11)]


def test_delisted_symbols_are_not_stale(lags):
    """폐지는 '수집 실패'가 아니라 '유니버스에서 빠질 것'이다 — 게이트가 잡을 대상이 아니다.

    마이크로캡은 폐지가 정상 사건이라(표본: 피인수 70.5%·파산 10.5%) 이걸 stale로 세면
    게이트가 상시 발동한다.
    """
    lags({"DEAD": 300, "ALIVE": 0})
    assert verify.stale_in_bundle(Path("x"), exclude={"DEAD"}) == []


def test_delisted_lookup_reads_meta(tmp_path):
    meta = tmp_path / "toss_stock_meta.csv"
    meta.write_text(
        "symbol,status,delistDate\n"
        "AAA,ACTIVE,\n"
        "BBB,ACTIVE,2025-03-01\n"      # delistDate 있으면 폐지
        "CCC,DELISTED,\n"              # status로도 판정
        "DDD,,\n",                     # 값 없으면 ACTIVE 취급
        encoding="utf-8")
    assert verify.delisted_symbols(meta) == {"BBB", "CCC"}


def test_missing_meta_excludes_nothing(tmp_path):
    # 메타가 없는 환경(S&P500 전용)에서는 전량 판정한다 — 대형주는 폐지가 드물다.
    assert verify.delisted_symbols(tmp_path / "absent.csv") == set()
