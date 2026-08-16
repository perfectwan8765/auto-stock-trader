"""execution 레이어 예외 (브로커 비의존 — toss.errors와 독립).

안전장치 정지 신호. CLI·cron이 잡아 정지·알림한다.
SystemExit 변환은 CLI 경계에서만 한다 — 라이브러리가 프로세스를 죽이면 자동화가
부분 이월·서킷브레이커로 대응할 기회를 잃는다.
"""
from __future__ import annotations


class ExecutionError(Exception):
    """execution 레이어 공통 베이스."""


class KillSwitchActive(ExecutionError):
    """kill switch 파일 존재 → 발주 중단."""


class CircuitBreakerTripped(ExecutionError):
    """일일 주문건수·손실 상한 초과 → 발주 차단."""


class BrokerRateLimited(ExecutionError):
    """브로커 rate-limit 초과 → 백오프 후 재시도 대상."""


class BrokerMarketClosed(ExecutionError):
    """장 마감·정규장 외 → 잔여 주문 중단."""


class OrderRejected(ExecutionError):
    """개별 주문만 거부(잔액 부족·미취급 종목 등) → 그 주문만 건너뛴다.

    `code`는 어댑터가 준 원본 사유 문자열이다. 러너는 분기에 쓰지 않고 기록만 한다 —
    분기는 예외 **타입**으로 한다.
    """

    def __init__(self, code: str = "", message: str = ""):
        self.code = code
        super().__init__(message or code or "주문 거부")
