"""리밸런싱 발주계획(dry-run·실발주)을 JSON으로 영속화 — 대시보드가 매매내역을 읽는 소스.

RunResult는 메모리 객체라 실행 후 사라진다. 이 모듈이 orders/skipped/placed를
`execution_logs/rebalance_<date>.json`으로 남겨 "언제 뭘 사고팔았는지"를 기록한다.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .atomic import write_text_atomic
from .interface import RunResult


def write_order_log(result: RunResult, date: str, out_dir: Path, signal_name: str | None = None) -> Path:
    """RunResult를 주문로그 JSON으로 저장하고 경로 반환.

    dry-run은 `rebalance_<date>.dryrun.json`, 실발주는 `rebalance_<date>.json`으로 갈린다.
    같은 이름을 쓰면 **실발주 원장이 계획 문서로 덮어써진다** —
    `scripts/model_backtest/dry_run_rebalance.py`가 이 함수를 직접 부르므로, 실발주한 날
    dry-run을 한 번만 돌려도 그렇게 된다.

    대시보드는 고치지 않아도 된다. `glob("rebalance_*.json")`이 두 이름을 다 잡고, 라벨은
    파일명이 아니라 내용의 `date`·`dry_run`에서 나온다.
    """
    payload = {
        "date": date,
        "signal": signal_name,
        "dry_run": result.dry_run,
        "aborted_reason": result.aborted_reason,
        "orders": [asdict(o) for o in result.plan.orders],
        "skipped": [list(s) for s in result.plan.skipped],
        "placed": list(result.placed),
        "rejected": [list(r) for r in result.rejected],
        "policy": result.policy,       # 그때 적용된 설정 — 사후 재구성용
        "snapshot": result.snapshot,   # 결정 시점 입력 — 슬리피지 계산의 기준가
        # 체결 실측 — 슬리피지(체결가 − 결정가)의 출처다. **실효 수수료의 출처는 아니다**:
        # Fill.commission은 주문 응답의 execution.commission에서 오는데 실측상 항상 0이고,
        # 실제 값은 holdings의 cost.commission에만 있다(roadmap.md Phase 0 실측표).
        # 이 원장만으로 비용을 계산하면 수수료를 0으로 착각한다.
        "fills": list(result.fills),
    }
    # 상태 파일과 같은 이유로 원자적 쓰기 — 직렬화 도중 죽으면 잘린 JSON이 남는데, 상태
    # 파일과 달리 이쪽은 손상 감지 경로가 없어 대시보드의 json.loads가 그냥 터진다.
    path = out_dir / f"rebalance_{date}{'.dryrun.json' if result.dry_run else '.json'}"
    write_text_atomic(path, json.dumps(payload, indent=2, ensure_ascii=False))
    return path
