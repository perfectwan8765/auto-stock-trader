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

    **종료 경로마다 파일이 다르다.** 같은 이름을 쓰면 뒤에 끝난 실행이 앞의 원장을 지운다.

        rebalance_<date>.json                 실발주 정상 종료 — 그날의 원장
        rebalance_<date>.aborted.json         발주 중 예외로 중단(이미 나간 주문 포함)
        rebalance_<date>.market-closed.json   정규장 아님 — 주문 0건
        rebalance_<date>.dryrun.json          계획만

    `date`는 리밸 일자(=시그널 날짜)라 같은 시그널을 며칠 재사용하면 **여러 실행이 같은
    `date`를 쓴다**(`--max-age-days` 기본 5). 갈라두지 않으면 장 종료 후 `--confirm`을 한 번만
    더 해도 `market_closed`가 `placed=[]`로 그날 체결 기록을 덮어쓴다. `is_market_open`은
    파싱 실패도 닫힘으로 접으므로 스키마가 어긋나면 매 실행이 원장을 지운다.

    ⚠️ **남은 구멍:** 같은 날 *정상 종료* 실발주를 두 번 하면 여전히 덮어쓴다. 실행 단위
    식별자(run_id)가 필요하며 이번 범위 밖이다.

    대시보드는 고치지 않아도 된다. `glob("rebalance_*.json")`이 네 이름을 다 잡고, 라벨은
    파일명이 아니라 내용의 `date`·`dry_run`·`aborted_reason`에서 나온다.
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
        # 슬리피지(체결가 − 결정가)의 출처. 수수료는 여기서 읽으면 안 된다 —
        # 근거는 `Fill.commission` 선언부 주석.
        "fills": list(result.fills),
    }
    # 상태 파일과 같은 이유로 원자적 쓰기 — 직렬화 도중 죽으면 잘린 JSON이 남는데, 상태
    # 파일과 달리 이쪽은 손상 감지 경로가 없어 대시보드의 json.loads가 그냥 터진다.
    path = out_dir / f"rebalance_{date}{_suffix(result)}"
    write_text_atomic(path, json.dumps(payload, indent=2, ensure_ascii=False))
    return path


def _suffix(result: RunResult) -> str:
    if result.dry_run:
        return ".dryrun.json"
    if result.aborted_reason == "market_closed":
        return ".market-closed.json"
    if (result.aborted_reason or "").startswith("aborted_error:"):
        return ".aborted.json"
    return ".json"
