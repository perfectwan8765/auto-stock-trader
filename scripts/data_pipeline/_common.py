"""Phase 2 파이프라인 공통: 경로·유니버스 로딩·로깅.

data/ 아래 산출물은 .gitignore(재생성 가능). universe/는 커밋.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ② 확장: 기본 유니버스 = S&P500 전체(+SPY). pilot(41) 재현은 QLIB_UNIVERSE=sp500_pilot.txt로.
UNIVERSE_FILE = ROOT / "universe" / os.environ.get("QLIB_UNIVERSE", "sp500_full.txt")
# Edge v2(마이크로캡)는 대형주 번들과 raw/정규화/bin을 공유하면 안 된다 — 02_normalize가
# data/raw/*.csv를 통째로 글롭하므로 한 디렉터리에 섞으면 유니버스가 오염된다.
# QLIB_DATASET=_small 이면 data/raw_small · normalized_small · qlib_us_small 로 갈라진다.
_SUFFIX = os.environ.get("QLIB_DATASET", "")
DATA_RAW = ROOT / "data" / f"raw{_SUFFIX}"                # yfinance 원본 CSV
DATA_NORM = ROOT / "data" / f"normalized{_SUFFIX}"        # 정규화 CSV (dump_bin 입력)
QLIB_DIR = ROOT / "data" / f"qlib_us{_SUFFIX}"            # 최종 .bin (provider_uri)
DUMP_BIN = ROOT / "vendor" / "dump_bin.py"

# 수집 시작일. 계획서 권장 8~10년 → 여유 두어 2015-01-01.
START_DATE = "2015-01-01"


def read_universe() -> list[str]:
    """유니버스 파일에서 티커 목록. '#'·빈 줄 무시, 대문자 정규화, 중복 제거(순서 유지)."""
    if not UNIVERSE_FILE.exists():
        raise SystemExit(f"[오류] 유니버스 파일 없음: {UNIVERSE_FILE}")
    seen: set[str] = set()
    out: list[str] = []
    for line in UNIVERSE_FILE.read_text().splitlines():
        s = line.strip().upper()
        if not s or s.startswith("#"):
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    if not out:
        raise SystemExit(f"[오류] 유니버스가 비어있음: {UNIVERSE_FILE}")
    return out


COLLECT_REPORT = DATA_RAW / "_collect_report.json"   # 01_collect 산출, 04_verify 게이트 입력
STALE_MAX_LAG_DAYS = 10       # 이 일수를 넘게 뒤처진 종목이 있으면 검증 실패


def stale_symbols(report: dict, max_lag_days: int = STALE_MAX_LAG_DAYS) -> list[tuple[str, int]]:
    """수집 리포트에서 뒤처진 종목을 (symbol, lag) 목록으로 반환.

    01_collect는 수집 실패 시 직전 CSV를 유지하고(개선9) exit 0으로 끝난다. 그 폴백 사실이
    하류로 전달되지 않으면 6개월 멈춘 종목이 있어도 파이프라인이 성공으로 끝나고, 그 가격이
    학습·예측을 거쳐 잘못된 시그널이 된다. 리포트를 게이트로 삼아 그 경로를 끊는다.
    """
    newest = max((r.get("last_date") or "" for r in report.get("symbols", {}).values()),
                 default="")
    if not newest:
        return []
    ref = _date(newest)
    out = []
    for sym, r in sorted(report.get("symbols", {}).items()):
        d = _date(r.get("last_date") or "")
        if d is None or ref is None:
            continue
        lag = (ref - d).days
        if lag > max_lag_days:
            out.append((sym, lag))
    return out


def _date(s: str):
    from datetime import date
    try:
        y, m, d = (int(x) for x in s[:10].split("-"))
        return date(y, m, d)
    except (ValueError, AttributeError):
        return None


def log(msg: str) -> None:
    print(msg, flush=True)
