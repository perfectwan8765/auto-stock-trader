"""리밸런싱 로직이 의존하는 브로커 인터페이스·데이터 모델 (브로커 비의존)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

# 이 네 어휘는 주문로그·대시보드가 읽는 계약이다 — tests/test_runner_behaviour.py가
# 스킵 사유 집합을 고정하고 scripts/dashboard/app.py가 한글 라벨로 매핑한다.
# str로 두면 오타가 런타임까지 살아남아 대시보드에서 "알 수 없는 사유"로만 드러난다.
OrderSide = Literal["BUY", "SELL"]
OrderKind = Literal["amount", "quantity"]
OrderReason = Literal["exit", "exit_partial", "trim", "enter", "add"]
SkipReason = Literal[
    "within_band",
    "below_min_order",
    "insufficient_buying_power",
    "partial_insufficient_buying_power",
    # 아래 셋은 러너가 붙인다(compute_rebalance가 아니라) — 화이트리스트·T+N 결제 판단이다.
    "excluded_manual",
    "not_sellable_settlement",
    "sell_clamped_to_sellable",
]


@dataclass(frozen=True)
class OrderIntent:
    """발주 의도(계획). dry-run은 이 리스트만 만들고 실발주는 broker.place로."""

    symbol: str
    side: OrderSide
    kind: OrderKind      # 매수는 amount(USD), 매도는 quantity(주식수)로만 나간다
    value: float         # kind에 따라 USD 금액 또는 주식수
    client_order_id: str  # 결정적 멱등키 — 재시도·재개 시 중복주문 방지
    # exit / exit_partial 구분은 ManagedState가 관리셋에서 뺄지 정하는 근거다 —
    # 잔량이 남은 exit을 exit_partial로 표시하지 않으면 그 종목이 M에도 X에도 없게 된다.
    reason: OrderReason


@dataclass(frozen=True)
class RebalanceParams:
    """`compute_rebalance` 한 번의 입력 중 종목에 딸리지 않는 것들.

    금액은 전부 USD다. 한 실행 안에서 이 값들이 흔들리면 예산 계산이 어긋나므로
    러너가 사이클 시작에 한 번 읽어 고정한다.
    """

    total_equity_usd: float   # 총 평가액(목표 비중 → 금액 환산 기준)
    buying_power_usd: float   # 매수는 이 한도 내에서만(이번 사이클 매도대금 미포함)
    min_order_usd: float      # 최소 주문금액
    rebalance_date: str       # YYYYMMDD, 멱등키 재현용
    # no-trade 밴드: 목표 대비 |편차|/목표 가 이 값 이하면 거래하지 않는다.
    # min_order_usd는 집행 하한이지 정책이 아니다 — 실측값이 $1이라 이것만 쓰면
    # 포트폴리오의 0.14% 드리프트에도 주문이 나간다.
    # 근거는 docs/project/roadmap.md Phase 5.5 — 그 표가 점검 주기와 변경 조건도 정한다.
    rebalance_band: float = 0.10


@dataclass(frozen=True)
class RebalancePlan:
    """리밸런싱 산출물. orders는 실행 순서(매도先→매수), skipped는 무동작 사유."""

    orders: list[OrderIntent]
    skipped: list[tuple[str, SkipReason]]


@dataclass
class RunResult:
    """리밸런싱 1회 실행의 산출물.

    `RebalancePlan`과 같은 급의 seam 데이터 모델이라 러너가 아니라 여기 산다.
    """

    plan: RebalancePlan
    dry_run: bool
    placed: list[str] = field(default_factory=list)          # 발주된 clientOrderId
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (symbol, error_code) 개별 거부
    aborted_reason: str | None = None                        # 예: "market_closed"
    fills: list[dict] = field(default_factory=list)          # 체결 실측(슬리피지 계산 입력)
    # 결정 시점 입력. 사후에 "왜 이 주문이 나갔나"를 재구성하려면 그때 본 값이 있어야 한다.
    # 슬리피지(체결가 − 결정가) 계산의 기준가도 여기서 나온다.
    snapshot: dict | None = None
    policy: dict | None = None   # 적용된 RunnerPolicy(asdict). 사후에 설정을 재구성한다


@dataclass(frozen=True)
class RunnerPolicy:
    """리밸런싱 실행 정책. 협력자·파일경로와 분리해 한 값으로 묶는다.

    실행 로그에 그대로 직렬화되므로 "그때 어떤 설정으로 돌았나"를 사후 재구성할 수 있다.
    """

    min_order_usd: float
    budget_usd: float | None = None
    rebalance_band: float = 0.10       # no-trade 밴드. 성과 보고 목적의 조정 금지
    order_sleep_s: float = 1.0         # 주문 간 간격(rate-limit 준수)
    rate_limit_retries: int = 3
    rate_limit_backoff_s: float = 2.0


@dataclass(frozen=True)
class AccountSnapshot:
    """한 시점의 계좌 상태. 읽기를 한 번에 모아 시점이 섞이지 않게 한다.

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
    # ⚠️ 주문 응답의 commission·tax는 실측상 항상 0이다(Phase 0, n=38). 실효 수수료는
    # holdings의 `cost.commission`(~0.13%)에만 있다 — 이 값으로 비용을 계산하면 0으로 착각한다.
    commission: float | None = None
    tax: float | None = None
    filled_at: str | None = None
    # 결제일. 규칙으로 계산하지 않고 브로커가 준 값을 그대로 담는다 — 미국 현지는
    # 2024-05-28부터 T+1인데 국내 예탁·외화결제 버퍼로 T+2가 되고, 미국 휴장일과 한국
    # 휴장일이 겹치면 규칙 계산이 어긋난다. 세법상 양도시기·환율기준일의 근거이기도 하다.
    settlement_date: str | None = None


@runtime_checkable
class Broker(Protocol):
    """리밸런싱이 요구하는 브로커 능력. src/toss가 구체 구현(TossBroker).

    실패는 `execution.errors`의 정규화된 예외로 던진다 — `BrokerRateLimited` ·
    `BrokerMarketClosed` · `OrderRejected`. 브로커 고유 에러코드 문자열을 러너가
    해석하지 않게 하려는 것이다(그러면 두 번째 어댑터를 붙일 때 러너를 고쳐야 한다).
    """

    def snapshot(self, target_symbols: list[str]) -> AccountSnapshot:
        """보유·가격·예수금·당일손익을 한 시점에서 함께 읽는다.

        시점이 섞이면 예산 계산이 흔들리므로 러너는 한 실행에 한 번만 부른다.

        Args:
            target_symbols: 목표 포트폴리오의 심볼. 보유에 없어도 가격은 필요하다.
        """
        ...

    def get_sellable(self, symbols: list[str]) -> dict[str, float]:
        """T+N 미결제분을 제외한 매도가능수량.

        ⚠️ **값을 알 수 없는 심볼은 결과에 키를 넣지 않는다.** 0으로 채우면 러너가 "미결제라
        못 판다"로 읽어 매도를 조용히 버리고 매 사이클 반복한다. 러너의 미조회 중단 가드가
        이 계약에 의존하므로, 지키지 않는 구현은 가드를 죽은 코드로 만든다(무음 회귀).
        """
        ...

    def is_market_open(self) -> bool:
        """정규장 중인가. 판정 불가면 보수적으로 닫힘을 답해야 한다."""
        ...

    def place(self, intent: OrderIntent) -> str:
        """실발주하고 브로커 주문 ID를 돌려준다.

        `intent.client_order_id`가 멱등키다 — 같은 키로 두 번 부르면 브로커가 거른다.

        Raises:
            OrderRejected: 이 주문만 거부(잔액 부족·미취급 종목 등).
            BrokerMarketClosed: 장 마감. 러너가 잔여 주문을 중단한다.
            BrokerRateLimited: rate-limit 초과.
        """
        ...

    def get_fill(self, order_id: str) -> Fill | None:
        """체결 실측(슬리피지 계산 입력). 미체결·미지원이면 None."""
        ...
