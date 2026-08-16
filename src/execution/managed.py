"""봇 관리 종목 상태 (화이트리스트) — 사용자의 수동 보유·현금 보호.

계좌를 사용자와 공유하므로, 봇은 자기가 산 종목(관리셋 M)만 매매하고 사용자가 이미
가진 종목(제외셋 X)은 절대 건드리지 않는다.

- 제외셋 X (`excluded`): 봇 첫 실행 시 계좌 보유를 동결(bootstrap). 봇은 이 종목을 매수·매도
  안 하고 목표에서도 뺀다. 사용자가 `managed_state.json`을 직접 편집해 추가할 수도 있다.
- 관리셋 M (`managed`): 봇이 실제로 산 종목. 실발주(placed)에서만 갱신.

⚠️ 한계: X 동결 이후 사용자가 새로 수동 매수한 종목은 X에 없다. 그 종목이 봇 목표와 겹치면
   commingle 위험 → 사용자가 excluded에 수동 추가하거나 재부트스트랩 필요.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .atomic import write_text_atomic
from .errors import ExecutionError


@dataclass
class ManagedState:
    excluded: set[str] = field(default_factory=set)   # X: 수동 보유 (봇 비관리)
    managed: set[str] = field(default_factory=set)     # M: 봇 보유
    bootstrapped: bool = False
    path: Path | None = None

    @classmethod
    def load(cls, path: str | Path | None) -> "ManagedState":
        """상태 파일을 읽는다. path=None이면 인메모리(영속 안 함), 없으면 빈 상태."""
        if path is None:
            return cls(path=None)
        p = Path(path)
        if not p.exists():
            return cls(path=p)
        # 빈 상태로 폴백하면 bootstrapped=False가 되어 다음 실행이 봇 보유분까지
        # 제외셋 X로 동결한다 — 영구히 관리 밖으로 나간다. 중단이 낫다.
        try:
            d = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            raise ExecutionError(
                f"[상태 파일 손상] {p} 를 읽을 수 없다 ({exc}). 수동 확인 필요 — "
                "백업이 있으면 복구하고, 없으면 계좌 보유와 대조해 excluded/managed를 재작성할 것."
            ) from exc
        return cls(
            excluded=set(d.get("excluded", [])),
            managed=set(d.get("managed", [])),
            bootstrapped=d.get("bootstrapped", True),
            path=p,
        )

    def save(self) -> None:
        if self.path is None:
            return
        write_text_atomic(self.path, json.dumps({
            "bootstrapped": self.bootstrapped,
            "excluded": sorted(self.excluded),
            "managed": sorted(self.managed),
        }, indent=2, ensure_ascii=False))

    def bootstrap(self, holdings: dict[str, float]) -> None:
        """첫 실행: 현재 보유 종목을 제외셋으로 동결. 봇은 이후 산 것만 관리."""
        self.excluded = {s for s, q in holdings.items() if q > 0}
        self.bootstrapped = True

    def update_after_place(self, orders, placed_ids) -> None:
        """실발주된 주문만 반영: 매수→M 추가, 전량 매도(exit)→M 제거.

        ⚠️ 시장가 **전량체결 가정**. exit이 부분체결되면 잔량이 계좌에 남는데 M에서 빠져
        다음 실행에 사용자 종목으로 오인된다(미완 청산). 체결수량 기반 갱신이 필요하다.
        """
        placed = set(placed_ids)
        for o in orders:
            if o.client_order_id not in placed:
                continue
            if o.side == "BUY":
                self.managed.add(o.symbol)
            elif o.side == "SELL" and o.reason == "exit":
                self.managed.discard(o.symbol)
