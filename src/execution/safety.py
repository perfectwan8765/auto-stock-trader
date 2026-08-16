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
        cb.guard(side=intent.side)  # 발주 직전 상한 확인(초과 시 CircuitBreakerTripped)
        broker.place(intent)
        cb.record_order()     # 발주 성공 후 카운트
        cb.observe_daily_loss(usd)  # 브로커가 보고한 당일 손실(절대값). 그날 최대치로 유지
        cb.record_loss(usd)         # 개별 실현손실 누적(증분)
    상태를 파일로 영속한다. 인메모리만 쓰면 상한에 걸려 멈춘 뒤 프로세스를 다시
    띄우는 것만으로 카운터가 0이 되어 **재시작이 안전판을 우회**한다. `path`를 주면
    기록할 때마다 즉시 저장하므로 루프 중간에 죽어도 반영된 상태로 재개된다.
    `path=None`이면 종전대로 인메모리(테스트·드라이런).

    "일일"의 경계는 호출자가 `day`로 준다. 저장된 날짜와 다르면 카운터를 리셋하므로,
    **날짜가 바뀌는 순간이 곧 상한이 풀리는 순간**이다. 라이브 진입점은 미국 거래일을 넘긴다
    (`scripts/live/rebalance.py`) — 시그널 날짜를 넘기면 시그널을 다시 만드는 것만으로
    같은 날 상한이 리셋돼 안전판이 우회된다.

    손실 축이 둘인 이유: 브로커의 당일손익은 **절대 스냅샷**이라 증분처럼 누적하면
    같은 날 재실행마다 같은 손실이 다시 더해진다. 인메모리일 때는 매 실행이 0에서 시작해
    드러나지 않았고, 영속을 붙이자 "재기동 우회 방지"가 반대로 정당한 매매를 막는 오류가 됐다.
    → 절대값은 `observe_daily_loss`(워터마크), 증분은 `record_loss`(누적)로 나눈다.

    ⚠️ `record_loss`는 아직 프로덕션 호출자가 없다. 실현손익을 계산하려면 평단가가 필요한데
    `cost`는 holdings 응답에만 있고 `AccountSnapshot`이 담지 않는다. 즉 **지금 손실 상한은
    보유 중인 관리 종목의 미실현 손익만 본다** — 청산으로 확정된 손실은 반영되지 않는다.
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

    def guard(self, side: str) -> None:
        """발주 직전 상한 확인. `side`는 `"BUY"` | `"SELL"`.

        두 축의 적용 범위가 다르다:
        - **주문건수** 상한은 전 주문에. 목적이 폭주 방지이므로 매도도 세야 한다.
        - **손실** 상한은 **매수에만**. 목적이 "더 이상 돈을 걸지 마라"인데 매도는 리스크를
          줄이는 행위다. 손실 제한 장치가 청산을 막으면 방향이 거꾸로다.

        매도를 빼지 않으면 실제로 청산이 불가능해진다 — `compute_rebalance`가 매도를 앞에
        배치하므로, 손실이 상한을 넘은 날에는 **첫 매도에서 트립해 한 주도 못 판다.**

        `side`에 기본값을 두지 않는 이유: `"BUY"`를 기본으로 두면 인자를 빠뜨린 호출이 매도를
        매수로 취급해 정확히 그 결함으로 되돌아간다. 안전한 기본값이 없는 자리다.

        Args:
            side: 발주하려는 주문의 방향.
        Raises:
            CircuitBreakerTripped: 해당 축의 상한을 넘었을 때.
            ValueError: `side`가 `"BUY"`/`"SELL"`이 아닐 때. 조용히 넘기면 오타 하나로
                손실 상한이 통째로 비활성화된다.
        """
        if side not in ("BUY", "SELL"):
            raise ValueError(f"side는 'BUY' 또는 'SELL'이어야 한다: {side!r}")
        if self.orders_today >= self.max_orders_per_day:
            raise CircuitBreakerTripped(
                f"일일 주문건수 상한 초과: {self.orders_today}/{self.max_orders_per_day}"
            )
        if side == "SELL":
            return
        total_loss = self.daily_loss_usd + self.realized_loss_usd
        if total_loss >= self.max_loss_usd:
            raise CircuitBreakerTripped(
                f"일일 손실 상한 초과: ${total_loss:.2f}/${self.max_loss_usd:.2f} (매수 차단)"
            )

    def record_order(self) -> None:
        self.orders_today += 1
        self._persist()   # 주문마다 flush — 루프 중간에 죽어도 재시작이 상한을 우회 못 한다

    def observe_daily_loss(self, usd: float) -> None:
        """브로커가 보고한 당일 손실(절대값)을 **그날의 최대치로** 유지한다(워터마크).

        누적(`+=`)이 아니라 `max`이므로 같은 값을 몇 번 보고해도 결과가 같다 — 절대 스냅샷의
        멱등성은 그대로다. 다만 **값이 줄어도 따라 내려가지 않는다.**

        단순 대입이면 안 되는 이유: 손실 난 종목을 청산하면 그 손익이 holdings 응답에서
        사라져 다음 실행이 0을 대입한다. **손실을 확정하는 행위가 상한을 해제한다.**

        대가: 장중에 손실이 이익으로 돌아서도 그날은 상한이 유지된다. 의도한 선택이다 —
        관측된 드로다운을 근거로 그날 매수를 멈추는 쪽이, 회복을 근거로 재개했다 다시 빠지는
        쪽보다 낫다고 봤다. 이 축은 **미실현 손익만** 본다(실현손실 배선은 아직 없다).
        """
        self.daily_loss_usd = max(self.daily_loss_usd, max(0.0, usd))
        self._persist()

    def record_loss(self, usd: float) -> None:
        """개별 실현손실을 누적한다(증분). 절대 스냅샷에는 쓰지 않는다."""
        if usd > 0:
            self.realized_loss_usd += usd
            self._persist()
