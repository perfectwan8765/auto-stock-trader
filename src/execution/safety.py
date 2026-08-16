"""발주 안전장치: kill switch · 서킷브레이커.

- kill switch: 지정 파일이 존재하면 즉시 중단(외부에서 `touch`로 정지).
- 서킷브레이커: 일일 주문건수·손실 상한 초과 시 발주 차단.
자동화(cron)가 라이브러리 예외와 함께 이 장치로 폭주를 막는다.
"""
from __future__ import annotations

import json
from pathlib import Path

from .atomic import write_text_atomic
from .errors import CircuitBreakerTripped, KillSwitchActive


def check_kill_switch(path: str | Path) -> None:
    """kill switch 파일 존재 시 KillSwitchActive. 존재 자체가 정지 신호."""
    if Path(path).exists():
        raise KillSwitchActive(f"kill switch 활성: {path} 존재 → 발주 중단")


class CircuitBreaker:
    """일일 주문건수·손실 상한.

    발주 루프 사용 패턴(러너):
        cb.guard()            # 발주 직전 상한 확인(초과 시 CircuitBreakerTripped)
        broker.place(intent)
        cb.record_order()     # 발주 성공 후 카운트
        cb.observe_daily_loss(usd)  # 브로커가 보고한 당일 손실(절대값). 재실행에 멱등
        cb.record_loss(usd)         # 개별 실현손실 누적(증분)
    상태를 파일로 영속한다. 인메모리만 쓰면 상한에 걸려 멈춘 뒤 프로세스를 다시
    띄우는 것만으로 카운터가 0이 되어 **재시작이 안전판을 우회**한다. `path`를 주면
    기록할 때마다 즉시 저장하므로 루프 중간에 죽어도 반영된 상태로 재개된다.
    `path=None`이면 종전대로 인메모리(테스트·드라이런).

    "일일"의 경계는 호출자가 `day`로 준다(러너는 `rebalance_date`). 저장된 날짜와 다르면
    카운터를 리셋한다 — 시간대 해석에 의존하지 않으려는 것이다.

    손실 축이 둘인 이유: 브로커의 당일손익은 **절대 스냅샷**이라 증분처럼 누적하면
    같은 날 재실행마다 같은 손실이 다시 더해진다. 인메모리일 때는 매 실행이 0에서 시작해
    드러나지 않았고, 영속을 붙이자 "재기동 우회 방지"가 반대로 정당한 매매를 막는 오류가 됐다.
    → 절대값은 `observe_daily_loss`(대입), 증분은 `record_loss`(누적)로 나눈다.
    """

    def __init__(self, max_orders_per_day: int, max_loss_usd: float,
                 path: str | Path | None = None, day: str | None = None):
        self.max_orders_per_day = max_orders_per_day
        self.max_loss_usd = max_loss_usd
        self.orders_today = 0
        self.daily_loss_usd = 0.0      # 브로커 보고 당일손실(절대값, 대입)
        self.realized_loss_usd = 0.0   # 개별 실현손실(증분, 누적)
        self.path = Path(path) if path else None
        self.day = day
        self._restore()

    def _restore(self) -> None:
        """저장된 같은 날짜의 카운터를 복원. 날짜가 다르거나 파일이 없으면 0에서 시작."""
        if self.path is None or not self.path.exists():
            return
        try:
            d = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return  # 손상된 상태 파일이 발주를 막지는 않되, 카운터는 0에서 다시 센다
        if self.day is not None and d.get("day") != self.day:
            return
        self.orders_today = int(d.get("orders_today", 0))
        self.daily_loss_usd = float(d.get("daily_loss_usd", 0.0))   # 구 스키마엔 없다
        self.realized_loss_usd = float(d.get("realized_loss_usd", 0.0))

    def _persist(self) -> None:
        if self.path is None:
            return
        write_text_atomic(self.path, json.dumps({
            "day": self.day,
            "orders_today": self.orders_today,
            "daily_loss_usd": round(self.daily_loss_usd, 4),
            "realized_loss_usd": round(self.realized_loss_usd, 4),
        }, indent=2, ensure_ascii=False))

    def guard(self) -> None:
        if self.orders_today >= self.max_orders_per_day:
            raise CircuitBreakerTripped(
                f"일일 주문건수 상한 초과: {self.orders_today}/{self.max_orders_per_day}"
            )
        total_loss = self.daily_loss_usd + self.realized_loss_usd
        if total_loss >= self.max_loss_usd:
            raise CircuitBreakerTripped(
                f"일일 손실 상한 초과: ${total_loss:.2f}/${self.max_loss_usd:.2f}"
            )

    def record_order(self) -> None:
        self.orders_today += 1
        self._persist()   # 주문마다 flush — 루프 중간에 죽어도 재시작이 상한을 우회 못 한다

    def observe_daily_loss(self, usd: float) -> None:
        """브로커가 보고한 당일 손실(절대값)을 대입한다. 같은 날 몇 번 호출해도 결과가 같다.

        이익이면 0이 된다 — 장중에 손실이 이익으로 돌아섰는데 옛 손실이 남아 있으면
        상한이 근거 없이 걸린다.
        """
        self.daily_loss_usd = max(0.0, usd)
        self._persist()

    def record_loss(self, usd: float) -> None:
        """개별 실현손실을 누적한다(증분). 절대 스냅샷에는 쓰지 않는다."""
        if usd > 0:
            self.realized_loss_usd += usd
            self._persist()
