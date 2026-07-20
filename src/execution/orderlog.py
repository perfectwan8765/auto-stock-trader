"""리밸런싱 발주계획(dry-run·실발주)을 JSON으로 영속화 — 대시보드가 매매내역을 읽는 소스.

RunResult는 메모리 객체라 실행 후 사라진다. 이 모듈이 orders/skipped/placed를
`execution_logs/rebalance_<date>.json`으로 남겨 "언제 뭘 사고팔았는지"를 기록한다.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .runner import RunResult


def write_order_log(result: RunResult, date: str, out_dir: Path, signal_name: str | None = None) -> Path:
    """RunResult를 out_dir/rebalance_<date>.json으로 저장하고 경로 반환."""
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date,
        "signal": signal_name,
        "dry_run": result.dry_run,
        "aborted_reason": result.aborted_reason,
        "orders": [asdict(o) for o in result.plan.orders],
        "skipped": [list(s) for s in result.plan.skipped],
        "placed": list(result.placed),
        "rejected": [list(r) for r in result.rejected],
    }
    path = out_dir / f"rebalance_{date}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return path
