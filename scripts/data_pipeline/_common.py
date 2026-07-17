"""Phase 2 파이프라인 공통: 경로·유니버스 로딩·로깅.

data/ 아래 산출물은 .gitignore(재생성 가능). universe/는 커밋.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ② 확장: 기본 유니버스 = S&P500 전체(+SPY). pilot(41) 재현은 QLIB_UNIVERSE=sp500_pilot.txt로.
UNIVERSE_FILE = ROOT / "universe" / os.environ.get("QLIB_UNIVERSE", "sp500_full.txt")
DATA_RAW = ROOT / "data" / "raw"          # yfinance 원본 CSV
DATA_NORM = ROOT / "data" / "normalized"  # 정규화 CSV (dump_bin 입력)
QLIB_DIR = ROOT / "data" / "qlib_us"      # 최종 .bin (provider_uri)
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


def log(msg: str) -> None:
    print(msg, flush=True)
