"""리밸런싱 로직이 의존하는 브로커 인터페이스·데이터 모델 (브로커 비의존)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class OrderIntent:
    """발주 의도(계획). dry-run은 이 리스트만 만들고 실발주는 broker.place로."""

    symbol: str
    side: str            # "BUY" | "SELL"
    kind: str            # "amount"(USD, 매수) | "quantity"(주식수, 매도)
    value: float         # 매수=USD 금액, 매도=주식수
    client_order_id: str  # 결정적 멱등키(개선5)
    reason: str          # "exit" | "trim" | "enter" | "add"


@dataclass(frozen=True)
class RebalanceParams:
    total_equity_usd: float   # 총 평가액(목표 비중 → 금액 환산 기준)
    buying_power_usd: float   # 가용 USD(개선1: 매수는 이 한도 내에서만)
    min_order_usd: float      # 최소 주문금액(개선8, Phase 0 실측 전 placeholder)
    rebalance_date: str       # YYYYMMDD, 멱등키 재현용
    # no-trade 밴드: 목표 대비 |편차|/목표 가 이 값 이하면 거래하지 않는다.
    # min_order_usd는 집행 하한이지 정책이 아니다 — 실측값이 $1이라 이것만 쓰면
    # 포트폴리오의 0.14% 드리프트에도 주문이 나간다. 근거는 qlib-toss.md Phase 5.5.
    rebalance_band: float = 0.10


@dataclass(frozen=True)
class RebalancePlan:
    """리밸런싱 산출물. orders는 실행 순서(매도先→매수, 개선1). skipped는 사유 기록."""

    orders: list[OrderIntent]
    # (symbol, reason): within_band | below_min_order | insufficient_buying_power
    #                 | partial_insufficient_buying_power
    skipped: list[tuple[str, str]]


@dataclass
class RunResult:
    """리밸런싱 1회 실행의 산출물. `RebalancePlan`과 같은 급의 seam 데이터 모델이라
    러너가 아니라 여기 산다 — orderlog가 러너를 import하고 러너가 orderlog를 지연
    import하던 순환을 끊는다."""

    plan: RebalancePlan
    dry_run: bool
    placed: list[str] = field(default_factory=list)          # 발주된 clientOrderId
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (symbol, error_code) 개별 거부
    aborted_reason: str | None = None                        # 예: "market_closed"
    fills: list[dict] = field(default_factory=list)          # 체결 실측(슬리피지 계산 입력)
    # 결정 시점 입력. 사후에 "왜 이 주문이 나갔나"를 재구성하려면 그때 본 값이 있어야 한다.
    # 슬리피지(체결가 − 결정가) 계산의 기준가도 여기서 나온다.
    snapshot: dict | None = None


@dataclass(frozen=True)
class AccountSnapshot:
    """한 시점의 계좌 상태. 읽기 호출을 하나로 접은 결과다.

    종전에는 보유·가격·가용액을 각각 조회해 시점이 섞인 값 위에서 예산을 계산했고,
    `/api/v1/holdings`를 한 실행에서 두 번 쳤다(보유 + 당일손익). 어댑터가 한 번에
    만들어 주면 시점 일관성과 호출 절약이 함께 온다.

    `sellable`은 여기 없다 — 계획이 나오기 전에는 쓸 데가 없고, 보유 전 종목을 미리
    받으면 매도 몇 건에 보유 수십 건을 조회하게 된다. `Broker.get_sellable` 참조.
    """

    holdings: dict[str, float]        # symbol -> 보유 주식수(전체)
    prices: dict[str, float]          # target ∪ holdings
    buying_power_usd: float
    daily_pnl: dict[str, float]       # symbol -> 당일손익. 러너가 관리셋 M만 합산한다


@dataclass(frozen=True)
class Fill:
    """체결 실측. 브로커 응답 스키마를 어댑터가 여기로 번역한다.

    미체결이면 `Broker.get_fill`이 `None`을 돌려주므로, 이 타입의 필드가 전부 None인
    상태는 "조회는 됐는데 값이 비어 있다"는 별개 상황을 뜻한다.
    """

    filled_quantity: float | None = None
    avg_filled_price: float | None = None
    filled_amount: float | None = None
    commission: float | None = None
    tax: float | None = None
    filled_at: str | None = None


class Broker(Protocol):
    """리밸런싱이 요구하는 브로커 능력. src/toss가 구체 구현(TossBroker).

    실패는 `execution.errors`의 정규화된 예외로 던진다 — `BrokerRateLimited` ·
    `BrokerMarketClosed` · `OrderRejected`. 브로커 고유 에러코드 문자열을 러너가
    해석하지 않게 하려는 것이다(그러면 두 번째 어댑터를 붙일 때 러너를 고쳐야 한다).
    """

    def snapshot(self, target_symbols: list[str]) -> AccountSnapshot: ...
    def get_sellable(self, symbols: list[str]) -> dict[str, float]: ...  # T+N 미결제분 제외
    def is_market_open(self) -> bool: ...
    def place(self, intent: OrderIntent) -> str: ...         # 실발주(멱등키 포함) → 주문 ID
    def get_fill(self, order_id: str) -> Fill | None: ...    # 체결 실측. 미체결·미지원이면 None
