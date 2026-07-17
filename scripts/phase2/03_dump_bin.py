"""Phase 2 · T5: normalized CSV → Qlib .bin (vendor/dump_bin.py 호출)

- include_fields 화이트리스트로 숫자 컬럼만 덤프(symbol 문자열 컬럼 배제)
- mode=all: 전체 재빌드(기본). 깔끔한 재현 위해 기존 qlib_dir 삭제 후 생성
- mode=update: 증분(dump_update). 기존 bin에 최신 구간 append

산출물: data/qlib_us/{calendars,instruments,features}

실행:  .venv/bin/python scripts/phase2/03_dump_bin.py
옵션:  --mode all|update   --no-clean(all에서 기존 삭제 안 함)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from _common import DATA_NORM, DUMP_BIN, QLIB_DIR, log

INCLUDE_FIELDS = "open,high,low,close,vwap,volume,factor"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["all", "update"], default="all")
    ap.add_argument("--no-clean", action="store_true", help="all 모드에서 기존 qlib_dir 유지")
    args = ap.parse_args()

    if not DATA_NORM.exists() or not any(DATA_NORM.glob("*.csv")):
        raise SystemExit(f"[오류] 정규화 CSV 없음: {DATA_NORM} (먼저 02_normalize.py 실행)")

    if args.mode == "all" and not args.no_clean and QLIB_DIR.exists():
        log(f"🧹 기존 재빌드 대상 삭제: {QLIB_DIR}")
        shutil.rmtree(QLIB_DIR)

    cmd = [
        sys.executable,
        str(DUMP_BIN),
        f"dump_{args.mode}",
        "--data_path", str(DATA_NORM),
        "--qlib_dir", str(QLIB_DIR),
        "--include_fields", INCLUDE_FIELDS,
        "--date_field_name", "date",
        "--symbol_field_name", "symbol",
        "--freq", "day",
    ]
    log(f"🏗  dump 실행: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(f"[치명] dump_bin 실패 (exit={result.returncode})")

    # 산출 디렉토리 확인
    for sub in ("calendars", "instruments", "features"):
        d = QLIB_DIR / sub
        if not d.exists():
            raise SystemExit(f"[치명] 산출 디렉토리 누락: {d}")
    log(f"✅ bin 생성 완료 → {QLIB_DIR}")


if __name__ == "__main__":
    main()
