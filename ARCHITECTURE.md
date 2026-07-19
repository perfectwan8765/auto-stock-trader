# 아키텍처 & 실행 흐름

전체 계획과 의사결정은 [qlib-toss.md](qlib-toss.md), 진행 상태는 [README.md](README.md)에 있다.
이 문서는 시스템 구조와 데이터가 흐르는 순서를 다룬다.

## 개요

시스템은 두 부분으로 나뉜다.

- 리서치: qlib으로 미국주식을 예측한다. 어떤 종목을 어느 비중으로 담을지 정하는 데까지다.
- 실행: 그 목표 포트폴리오를 현재 보유와 비교해 발주 계획으로 바꾸고, 토스증권에 주문을 낸다.

qlib은 예측까지만 담당한다(주문 생성은 지원하지 않는다). 그래서 발주 계층은 직접 구현했다.
전략은 주간 리밸런싱, 롱온리, 상위 K종목 등가중이다.

## 용어

이 문서에 나오는 주요 용어를 쉬운 말로 정리한다.

| 용어 | 뜻 |
|------|-----|
| 유니버스 | 매매 후보 종목 집합. 여기선 S&P500. |
| 팩터 / Alpha158 | 주가·거래량에서 뽑아낸 158개 수치 지표. 모델의 입력. |
| 모델 (LightGBM) | 팩터를 보고 다음 주 상대 수익률을 예측하는 학습 알고리즘. |
| 시그널 | 모델 예측을 "이 종목들을 이 비중으로 담아라"로 정리한 목표 포트폴리오(JSON 파일). |
| 목표비중 | 종목별로 얼마씩 담을지의 비율(합 = 1). |
| 롱온리 | 매수만 함. 공매도 없음. |
| 등가중 | 고른 K종목에 자금을 똑같이 나눠 담음. |
| 리밸런싱 | 주기적으로 현재 보유를 목표비중에 맞게 다시 맞추는 것(팔 것 팔고 살 것 삼). |
| 백테스트 | 과거 데이터로 전략을 모의 실행해 성과를 가늠하는 것. |
| IC / RankIC | 예측과 실제 수익이 얼마나 맞는지 나타내는 예측력 지표. 높을수록 좋고, 대략 0.02 이상이면 쓸 만하다. |
| 벤치마크 (SPY) | 성과 비교 기준(S&P500 ETF). 이걸 못 이기면 능동 전략을 할 이유가 약하다. |
| 엣지 | 벤치마크 대비 꾸준히 초과수익을 낼 실질적 우위. |
| OMS (주문관리) | 목표와 보유의 차이를 실제 주문으로 바꾸고 주문 상태를 관리하는 계층. |
| 발주계획 | 이번 리밸런싱에서 실제로 낼 매도·매수 주문 목록. |
| dry-run | 실제 주문은 내지 않고 발주계획만 출력해 확인하는 모드. |
| 멱등키 (clientOrderId) | 같은 주문에 같은 식별자를 붙여, 재시도해도 중복 발주되지 않게 하는 값. |
| T+N | 매도대금이 N일 뒤 정산돼, 판 즉시 그 돈으로 다시 못 사는 것. |
| kill switch / 서킷브레이커 | 비상 정지 장치. 특정 파일이 있으면 즉시 중단(kill switch), 하루 주문·손실 한도를 넘으면 차단(서킷브레이커). |
| 소수점 금액주문 | "35달러어치"처럼 금액 기준으로 소수점 단위까지 매수하는 방식(토스 미국주식). |
| provider_uri | qlib이 데이터를 읽어 가는 폴더 경로(`data/qlib_us`). |
| 화이트리스트 (관리셋 M / 제외셋 X) | 계좌를 사용자 수동 보유와 공유하므로, 봇이 산 종목(M)만 매매하고 사용자가 미리 보유한 종목(X)은 안 건드리는 장치. |
| 예산 상한 (budget_usd) | 봇이 쓸 수 있는 최대 금액. 계좌에 다른 현금이 있어도 이 한도 안에서만 매수. |

### Alpha158 자세히

qlib이 기본 제공하는 피처셋으로, OHLCV(시가·고가·저가·종가·거래량)만으로 계산한 158개 기술적 지표다. 이름의 "158"은 지표 개수를 뜻한다. 재무·뉴스 같은 외부 데이터는 쓰지 않고, 오로지 가격과 거래량에서 뽑아낸다. 크게 세 그룹으로 나뉜다.

| 그룹 | 내용 | 예 |
|------|------|-----|
| K-bar | 하루 봉의 모양(몸통·꼬리 비율) | `KMID`=(종가−시가)/시가, `KUP`=윗꼬리, `KLEN`=고가−저가 |
| Price | 당일 시가·고가·저가·VWAP를 종가로 정규화 | `OPEN0`=시가/종가, `HIGH0`, `VWAP0` |
| Rolling | 여러 기간(5·10·20·30·60일) 창의 추세·변동성·상관·거래량 지표 | `ROC`(수익률), `MA`(이동평균), `STD`(변동성), `RSQR`(추세 적합도), `CORR`(가격-거래량 상관), `WVMA` 등 |

대부분은 Rolling 그룹이다(약 30종 지표 × 5개 기간 ≈ 150개). 요컨대 한 종목의 최근 가격·거래량 패턴을 158개 숫자로 요약한 것이고, 모델(LightGBM)이 이를 입력받아 다음 주 상대수익률을 예측한다.

이 프로젝트에서는 Alpha158이 참조하는 `$vwap`을 yfinance가 제공하지 않아 `(H+L+C)/3`으로 근사했다(개선12). Phase 3 결과, 이 158개 지표만으로는 미국 대형주 주간 예측에서 유의미한 신호가 나오지 않았다(IC 0.012).

## 레이어

```mermaid
flowchart TD
  D["① 데이터<br/>yfinance → 정규화 → Qlib bin"]:::data
  M["② 모델·시그널<br/>Alpha158 + LightGBM → 예측 → 목표비중"]:::model
  E["③ 실행·OMS<br/>리밸 계산 + 안전장치 (브로커 비의존)"]:::exec
  B["④ 브로커<br/>TossClient (인증·HTTP)"]:::broker
  T["⑤ 토스 OpenAPI<br/>(키 승인 대기)"]:::blocked

  D -->|"provider_uri"| M
  M -->|"목표비중 JSON"| E
  E -->|"Broker 프로토콜"| B
  B -->|"HTTPS"| T

  classDef data fill:#eef2f7,stroke:#5b7089,color:#2b3a4a
  classDef model fill:#eef2f7,stroke:#5b7089,color:#2b3a4a
  classDef exec fill:#eaf2ee,stroke:#4c7a5d,color:#274736
  classDef broker fill:#f5efe6,stroke:#9a7b4f,color:#5c472a
  classDef blocked fill:#f7ecec,stroke:#a86464,color:#6e3535
```

의존 방향이 핵심이다. ③ 실행 계층은 ④ 브로커를 직접 참조하지 않는다. ③이 `Broker` 인터페이스를 정의하고 ④(토스)가 이를 구현한다. 실제 API 없이 가짜 브로커를 끼워 전 구간을 테스트할 수 있고, 브로커를 교체할 여지도 남는다.

| 레이어 | 폴더 | 핵심 파일 |
|--------|------|-----------|
| ① 데이터 | `scripts/data_pipeline/` | `run_pipeline`, `01~04_*`, `gen_sp500_universe` |
| ② 모델 | `scripts/model_backtest/` | `run_backtest`, `generate_signal`, `*.yaml` |
| ③ 실행 | `src/execution/` | `runner`, `rebalance`, `safety`, `interface` |
| ④ 브로커 | `src/toss/` | `broker`, `client`, `auth`, `config` |

## 흐름 ① — 오프라인 (토스 API 불필요)

데이터 구축부터 발주 계획 산출까지 토스 API 없이 동작한다.

```mermaid
flowchart LR
  A["데이터 구축<br/>run_pipeline.py"]:::data
  B["학습·백테스트<br/>run_backtest.py"]:::model
  C["시그널 생성<br/>generate_signal.py"]:::model
  E["dry-run 계획<br/>dry_run_rebalance.py"]:::exec

  A -->|"data/qlib_us"| B
  A --> C
  C -->|"signal_날짜.json"| E
  E --> R["발주계획 출력<br/>(실발주 없음)"]:::exec

  classDef data fill:#eef2f7,stroke:#5b7089,color:#2b3a4a
  classDef model fill:#eef2f7,stroke:#5b7089,color:#2b3a4a
  classDef exec fill:#eaf2ee,stroke:#4c7a5d,color:#274736
```

| 단계 | 명령 | 결과 |
|------|------|------|
| 데이터 | `run_pipeline.py` | S&P500 503+SPY bin |
| 학습 | `run_backtest.py --config …sp500` | IC 0.012 (엣지 미검출) |
| 시그널 | `generate_signal.py --topk 20` | 목표비중 JSON |
| dry-run | `dry_run_rebalance.py` | 발주계획 20건, $700 |

## 흐름 ② — 리밸런싱 (`RebalanceRunner`)

시그널과 계좌 상태를 받아 발주계획을 만든다. dry-run이면 계획만 출력하고, 실전이면 안전장치를 모두 통과했을 때만 발주한다.

```mermaid
flowchart TD
  S["시그널 (목표비중)"]:::model --> R
  BK["계좌 상태<br/>보유·가격·가용현금"]:::broker --> R["RebalanceRunner"]:::exec
  R --> F["화이트리스트 필터<br/>수동보유(X) 제외 · 봇보유(M)만 · 예산 상한"]:::exec
  F --> C["리밸 계산<br/>매도 먼저 → 매수"]:::exec
  C --> P["발주계획 + 스킵 사유"]:::exec
  P --> DR{"dry-run?"}
  DR -->|"예"| OUT["계획만 출력"]:::exec
  DR -->|"아니오"| K{"kill switch?"}
  K -->|"켜짐"| STOP["즉시 중단"]:::blocked
  K -->|"꺼짐"| MK{"정규장?"}
  MK -->|"닫힘"| AB["발주 안 함"]:::blocked
  MK -->|"열림"| PL["주문 발주<br/>매도→매수, 멱등키"]:::broker

  classDef model fill:#eef2f7,stroke:#5b7089,color:#2b3a4a
  classDef exec fill:#eaf2ee,stroke:#4c7a5d,color:#274736
  classDef broker fill:#f5efe6,stroke:#9a7b4f,color:#5c472a
  classDef blocked fill:#f7ecec,stroke:#a86464,color:#6e3535
```

리밸 계산 규칙 (`compute_rebalance`):

- 매도 먼저: 빠질 종목을 전량 팔고 초과분을 정리한 뒤 매수한다(매수 자금 확보).
- 가용현금 한도: 매수는 현재 현금 범위 안에서만 하고, 넘치는 분량은 다음 주기로 미룬다(매도대금 T+N 정산 반영).
- 최소금액 미달 스킵: 최소 주문금액에 못 미치는 주문은 건너뛴다.
- 멱등키: 같은 날·종목·방향이면 주문번호가 같아, 재시도하거나 도중에 멈췄다 다시 실행해도 중복 발주되지 않는다.
- 화이트리스트(개선14): 사용자가 미리 보유한 종목(X)은 매매하지 않고 봇이 산 종목(M)만 리밸한다. 매수는 예산 상한 안에서만 → 사용자 종목·현금 보호.

## 디렉토리

```
universe/     티커 (sp500_full 503+SPY, sp500_pilot 41)
scripts/
  data_pipeline/    데이터: 수집→정규화→dump→검증
  model_backtest/   모델: 학습·백테스트·시그널·dry-run
  live/             실 발주 진입점 (dry-run 기본, --confirm 실발주)
  toss_probe/       Phase 0 실측 CLI (키 승인 후)
src/
  execution/    리밸·안전장치 (브로커 비의존)
  toss/         토스 HTTP·인증
tests/          단위테스트 (pytest, 29개)
vendor/         qlib dump_bin.py (수정 금지)
data/, signals/ (gitignore) 생성물
```

## 현재 상태

- 데이터 → 예측 → 시그널 → 발주계획까지 오프라인 전 구간 검증을 마쳤다.
- 모델에서 유의미한 엣지는 검출되지 않았다. 현 단계의 목적은 수익이 아니라 학습과 시스템 완성이다.
- 실 발주는 토스 키 발급(Phase 0)을 기다린다. 키가 풀리면 응답 필드 확정, 개선11 실 401 확인, 실측 비용 기반 재판정, dry-run에서 소액 실발주로 이어진다.

개선(N) 항목 위치:

| 번호 | 내용 | 위치 |
|------|------|------|
| 1 | 자금순환·부분이월 | `execution/rebalance` |
| 4 | dry-run·kill switch·서킷브레이커 | `execution/safety`, `runner` |
| 5 | 멱등키 | `execution/rebalance` |
| 8 | 최소금액 스킵 | `execution/rebalance` |
| 10 | 예외화(TossError) | `toss/errors` |
| 13 | 응답본문 누설 방지 | `toss/auth`, `toss/errors` |
| 14 | 계좌 공유 안전(화이트리스트·예산상한) | `execution/managed`, `runner` |
| 11 | 401 재시도 (구현·mock검증, 실 401 확인은 Phase 0) | `toss/client` |
