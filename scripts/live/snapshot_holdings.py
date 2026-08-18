"""holdings 원 응답 스냅샷 → execution_logs/holdings_<date>.json (읽기 전용).

비용 캘리브레이션의 입력이다. 주문 응답의 `commission`은 전부 0이고 실제 비용은
holdings의 `cost.commission`에만 있다(Phase 0 실측). 그런데 이 값은 조회 시점의
누적 상태라 저장해 두지 않으면 지나간 값을 되살릴 수 없다.

주문을 내지 않는다. cron으로 매 거래일 1회 돌리는 것을 전제로 만들었다.

실행:  uv run python scripts/live/snapshot_holdings.py
옵션:  --out-dir execution_logs
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))   # scripts/live 규약: _bootstrap 대신 직접 삽입

from toss.broker import TossBroker  # noqa: E402
from toss.client import TossClient  # noqa: E402
from toss.config import load_config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(ROOT / "execution_logs"))
    args = ap.parse_args()

    broker = TossBroker(TossClient(load_config()))
    items = broker.get_holdings_raw()

    now = datetime.now(timezone.utc)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"holdings_{now:%Y%m%d}.json"
    path.write_text(json.dumps({"fetched_at": now.isoformat(), "items": items},
                               indent=2, ensure_ascii=False))

    print(f"[완료] {path} — {len(items)}종목")
    for it in items:
        cost = it.get("cost") or {}
        print(f"  {str(it.get('symbol')):6s} 수량 {it.get('quantity')}"
              f"  수수료누적 {cost.get('commission')}")


if __name__ == "__main__":
    main()
