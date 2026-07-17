"""Phase 2 오케스트레이션: 수집 → 정규화 → dump → 검증 (전체 재빌드).

증분갱신 = 이 스크립트 재실행. 41종목 전체 재빌드도 1~2분이라 dump_update(증분)
대신 매번 전체 재빌드로 멱등·안전하게 간다(factor 재계산·달력 드리프트 위험 제거).

실행:  .venv/bin/python scripts/data_pipeline/run_pipeline.py
옵션:  --symbols AAPL MSFT (부분)   --skip-collect(이미 받은 raw로 재빌드만)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = ["01_collect.py", "02_normalize.py", "03_dump_bin.py", "04_verify.py"]


def run(script: str, extra: list[str]) -> None:
    cmd = [sys.executable, str(HERE / script), *extra]
    print(f"\n{'='*60}\n▶ {script} {' '.join(extra)}\n{'='*60}", flush=True)
    if subprocess.run(cmd).returncode != 0:
        raise SystemExit(f"[중단] {script} 실패")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*")
    ap.add_argument("--skip-collect", action="store_true", help="수집 생략, raw로 재빌드만")
    args = ap.parse_args()

    collect_extra = []
    if args.symbols:
        collect_extra += ["--symbols", *args.symbols]

    for step in STEPS:
        if step == "01_collect.py":
            if args.skip_collect:
                print("⏭  01_collect.py 생략(--skip-collect)")
                continue
            run(step, collect_extra)
        else:
            run(step, [])

    print("\n🎉 Phase 2 파이프라인 완료")


if __name__ == "__main__":
    main()
