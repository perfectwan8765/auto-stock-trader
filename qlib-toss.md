# Qlib + 토스증권 미국주식 자동매매 — 작업계획서

> 개인 프로젝트. 자금 100만원(약 $700). 환경: M1 Air + pyenv.
> 목표: Qlib으로 미국주식 예측·백테스트 → 토스증권 OpenAPI로 주간 리밸런싱 자동 발주.
> 원칙: **모르는 값은 추측해서 코드에 박지 않는다. Phase 0에서 실측으로 확정한다.**
> 개선 반영: 2026-07-16 plan-review — T+N 자금순환·백테스트 정합성·point-in-time·안전장치 등 9건 (본문 `[개선N]` 표기).

---

## 0. 전략 개요 (확정)

| 항목 | 값 | 근거 |
|------|-----|------|
| 대상 시장 | 미국 주식 | 사용자 결정 |
| 유니버스 | S&P 500 (시작) | 유동성·데이터품질·용량 |
| 팩터 | Alpha158 | 트리모델 궁합, 검증됨 |
| 모델 | LightGBM (베이스라인) | 빠름·과최적 덜함 |
| 예측 대상 | 다음 기간 상대 순위 (Qlib 기본 라벨) | 퀀트 표준 |
| 포트폴리오 | TopkDropout, 롱온리, **K=15~20** | $700 규모 → 종목당 ~$35~48 |
| 리밸런싱 | **주간** | 거래비용·세금·환전비용 절감 |
| 발주 방식 | `orderAmount` 시장가(MARKET), 미국 정규장 | 토스 소수점 매수 = 금액주문 전용 |
| 검증 | 백테스트 → 앱 모의투자 → 1주 스모크 → 소액 실전 | 샌드박스 API 없음 |

> ✅ Phase 0 실측(2026-07-20) 완료: 최소 주문금액 **≤ $1**·소수점 매수 OK → **K=15~20 유지 가능**(제약 없음).

---

## 0-1. 설계 결정 사항 (grilling-plan 확정, 2026-07-16)

| 항목 | 결정 | 근거 | 확정 경로 |
|------|------|------|-----------|
| 리밸런싱 주기 | 주간 | $700 규모 수수료·환전·세금 절감, Qlib 일/주 예측 강점 | grilling-plan |
| 유니버스 | S&P 500 | 유동성·데이터품질·소수점 커버 가능성, 용량 작음 | grilling-plan |
| 모델 | LightGBM 베이스라인 우선 | 과최적 덜함·빠름, 이후 DL 비교 | grilling-plan |
| 백테스트·학습 데이터 | yfinance (무료) | 깊은 히스토리, 실전 발주는 토스가 담당 | grilling-plan |
| 예측 라벨 horizon | 주간 수익률 순위 | 리밸런싱 주기에서 도출 | 파생 |
| 포지션 방향 | 롱온리 | 한국 개인 미국주식 공매도 사실상 불가 (Phase 0 확인) | 제약 |

---

## 1. 확정된 토스 API 스펙 (openapi.json 정본 기준)

`Base: https://openapi.tossinvest.com`

### 인증
- `POST /oauth2/token` — req: `grant_type=client_credentials` + `client_id` + `client_secret`
- resp: `access_token`(JWT) · `token_type`(Bearer) · `expires_in`(초) → **expires_in 기준 토큰 캐싱**
- 계좌·주문 API는 헤더 2개 필요: `Authorization: Bearer {token}` + `X-Tossinvest-Account: {계좌식별자}`

### 주요 엔드포인트
| 용도 | 엔드포인트 |
|------|-----------|
| 계좌 목록 (→ X-Tossinvest-Account 값) | `GET /api/v1/accounts` |
| 보유주식 | `GET /api/v1/holdings` |
| 매수가능금액 (KRW·USD) | `GET /api/v1/buying-power` |
| 판매가능수량 | `GET /api/v1/sellable-quantity` |
| 현재가 | `GET /api/v1/prices` |
| 미국 장운영시간 | `GET /api/v1/market-calendar/US` |
| 환율 | `GET /api/v1/exchange-rate` |
| 종목정보 | `GET /api/v1/stocks` |
| **주문 생성** | `POST /api/v1/orders` |
| 주문 조회/정정/취소 | `GET /api/v1/orders/{id}` · `.../modify` · `.../cancel` |

### 주문 body (2가지 중 하나 — oneOf)
**소수점 매수 (금액 기반, US MARKET 전용):**
```json
{ "symbol": "AAPL", "side": "BUY", "orderType": "MARKET", "orderAmount": "100.5",
  "clientOrderId": "unique-id-per-order" }
```
**소수점 매도 (수량 기반 시장가):**
```json
{ "symbol": "AAPL", "side": "SELL", "orderType": "MARKET", "quantity": "0.5",
  "clientOrderId": "unique-id-per-order" }
```

### 확정된 제약·함정
- 모든 숫자 필드는 **문자열**(`"100.5"`, `100.5` 아님)
- `clientOrderId` = **멱등성 키** → 자동매매 재시도·크래시 시 중복주문 방지용 필수
- `orderAmount` 매수는 **미국 정규장 시간에만** (정규장 외 → `422 amount-order-outside-regular-hours`)
- US 주문은 **수량 정정 불가**(`us-modify-quantity-not-supported`) → 정정 대신 취소+재주문
- Rate limit (그룹별 TPS): `ACCOUNT` **초당 1회**(빡빡) · `ASSET` 5 · `STOCK` 5 · `MARKET_DATA` 10. **ORDER 그룹 수치는 응답 헤더로 런타임 확인**
- 주요 에러코드: `insufficient-buying-power` · `order-hours-closed` · `amount-order-outside-regular-hours` · `market-not-supported-for-stock` · `rate-limit-exceeded` · `invalid-token`

---

## Phase 0 — 사용자 확인 (★ 첫 작업, 실측으로 미확정 값 확정)

> 코드 작성 전에 반드시 확인. API 문서에 없는 값이라 **본인 계좌·실측·FAQ로만** 확인 가능.
> 이 Phase 완료 전까지 K값·유니버스·발주 로직 확정 불가.

### 0-1. 토스 OpenAPI 신청 및 키 발급
- **방법:**
  1. 토스 앱에서 토스증권 계좌 개설 (비대면, 미보유 시)
  2. PC 웹 `https://developers.tossinvest.com` 접속 → 계좌 연동 로그인
  3. OpenAPI 사전신청 → 승인 후 `client_id` / `client_secret` 발급
  4. 발급 키는 **환경변수/`.env`로 분리** (git 커밋 금지)
- **확인 산출물:** 유효한 client_id/secret, 승인 소요시간 메모
- **검증:** `POST /oauth2/token` 호출 → `access_token` 수신 성공

### 0-2. 계좌 식별자(X-Tossinvest-Account) 확보
- **방법:** 토큰 발급 후 `GET /api/v1/accounts` 호출 → 응답에서 계좌식별자 확인
- **확인 산출물:** 주문에 쓸 계좌식별자 값
- **검증:** `GET /api/v1/holdings`가 해당 헤더로 200 반환

### 0-3. 소수점 가능 종목 범위 확인 ★전략 영향
- **왜:** 토스는 소수점 가능 종목이 제한적일 수 있음. S&P500 전부 가능하지 않으면 유니버스 축소 필요
- **방법 (3중 확인):**
  1. 토스 FAQ `https://support.toss.im/faq/3753` (금액주문 가능 종목)
  2. `GET /api/v1/stocks`로 대상 종목의 시장·통화·상장상태 조회
  3. **실측:** 대표 종목 1개에 `orderAmount` 최소금액 매수 시도 → `market-not-supported-for-stock` 여부 확인
- **확인 산출물:** S&P500 중 소수점 매수 가능 종목 비율/리스트
- **의사결정:** 대부분 가능 → K=15~20 유지 / 제한적 → 유니버스를 소수점 가능 종목으로 교체

### 0-4. 최소 주문금액 확인 ★전략 영향
- **왜:** openapi.json에 최소금액 명시 없음(최대 30억원만 존재). K=20이면 종목당 ~$35인데, 최소가 그보다 크면 K 축소 필요
- **방법:**
  1. 토스 FAQ 확인
  2. **실측:** 정규장 시간에 소액(예: `orderAmount: "1"` = $1) 매수 시도 → 거부되면 에러 메시지의 최소금액 확인
- **확인 산출물:** 종목당 최소 매수금액
- **의사결정:** 최소금액 기준으로 **K 상한 = (총자금 / 최소금액)** 재계산

### 0-5. USD 환전 방식 확인
- **왜:** 원화만 있어도 자동환전(통합증거금)되는지, 선환전 필요한지에 따라 발주 전 처리 달라짐
- **방법:**
  1. 토스 앱에서 원화 입금 후 미국주식 매수 시 자동환전 여부 확인
  2. `GET /api/v1/buying-power`가 USD 매수가능금액을 반환하는지 확인
  3. 필요 시 `GET /api/v1/exchange-rate`로 환율 조회 흐름 점검
- **확인 산출물:** 발주 전 환전 필요 여부 (자동/수동)

### 0-6. 결제주기(T+N) 확인
- **왜:** 매도대금이 다음 주 리밸런싱 매수에 언제 반영되는지가 회전 설계에 영향
- **방법:** 토스 FAQ / 소액 매도 후 `GET /api/v1/buying-power` 반영 시점 관찰
- **확인 산출물:** 미국주식 결제주기, 리밸런싱 주기와의 정합성

### 0-7. ORDER 그룹 Rate Limit 실측
- **방법:** `POST /api/v1/orders` 1회 호출 후 **응답 헤더**(`X-RateLimit-*` 계열) 확인
- **확인 산출물:** 주문 API 초당 허용 횟수 → 발주 루프 간격(sleep) 설정값

**Phase 0 완료 게이트:** ✅ **완료(2026-07-20)** — 7개 모두 실측 확정(실주문 포함).
K=15~20 유지.

> ⚠️ **2026-08-16 — "남은 건 Phase 6 스모크"는 더 이상 맞지 않다.**
> Phase 6·7은 **굴릴 전략이 있다**는 전제 위에 있는데 그 전제가 두 번 부정됐다 —
> Phase 3(대형주 주간 selection alpha 없음, CAPM 분해로 β 틸트 확정)과
> Edge v2(마이크로캡 + Form 4 인사이더, 1층 게이트 불통과 → [`PREREGISTRATION.md`](PREREGISTRATION.md) §10).
> **아래 "Phase 6·7 진입 조건"을 먼저 읽을 것.**

### Phase 0 실측 상수 (확정 2026-07-20, 실주문 기반)

계정 고유값(계좌번호·잔액·보유)은 재조회로 얻으므로 여기 남기지 않는다. 아래는 계정과
무관한 API 계약·비용이며, 코드·config가 이 값을 전제로 짜여 있다.

| 항목 | 실측값 | 소비처 |
|---|---|---|
| 계좌 헤더 | `X-Tossinvest-Account` = **`accountSeq`** (`accountNo`는 `400 account-not-found`) | [client.py](src/toss/client.py) |
| 토큰 | `expires_in` ≈ 86400초(24h), 파일 캐시 | [client.py](src/toss/client.py) |
| 소수점 주문 | 금액주문(fractional) 가능 | 유니버스·K 산정 |
| 최소 주문금액 | **≤ $1** ($1 매수 FILLED) → K 상한 사실상 무제한 | `min_order_usd` |
| 환전 | **자동환전 없음.** KRW 보유·USD 0이면 `422 insufficient-buying-power` → **선환전 필수** | [runner.py](src/execution/runner.py), 운영절차 |
| 결제주기 | **T+2** (`execution.settlementDate`, 영업일) | `not_sellable_settlement` 가드 |
| ORDER rate-limit | `X-RateLimit-Limit=6`, `Reset=1` → **6주문/초** | `order_sleep_s` |
| 그룹별 rate-limit | ACCOUNT 1 TPS · ASSET/STOCK 5 · MARKET_DATA 10 | 상동 |
| 매매 수수료 | **~0.10~0.13%/편도** (매입액 클수록 0.10%에 수렴, 소액은 최소단위 반올림으로 상승) | backtest `open/close_cost` |
| 매수 거래세 | 없음 (`cost.tax` = null) | 상동 |
| 매도 fee | SEC/FINRA `tax` 최소 $0.01 (유의미 규모에선 ~0.001%로 무시가능) | 상동 |
| FX 스프레드 | `basisPoint=3` = **0.03%/편도** (mid 대비), 호가 유효 5분 | 상동 |
| 멱등 보장 | 동일 `clientOrderId` 2회 발주 → **1회만 체결·같은 orderId 반환** | 재시도 설계 |
| 에러 응답 | `{"error":{"code","message","data"}}` **중첩** (flat 아님) | [errors.py](src/toss/errors.py) |
| market-calendar | 모든 시각 **KST**, `isOpen` 필드 없음 → 정규장 `[start,end)` 비교로 판정 | [broker.py](src/toss/broker.py) |

응답 스키마(`result.items[]`·`lastPrice`·`cashBuyingPower`·`today.regularMarket` 등)는
[tests/test_broker.py](tests/test_broker.py)에 실측 픽스처로 고정돼 있다 — 스펙 변경 시 테스트가 깨져 알려준다.

**아직 브로커 래퍼가 없는 엔드포인트의 실측 스키마** (구현 시 이 구조를 전제로 짤 것):

```
POST /api/v1/orders           → result: {orderId, clientOrderId}
GET  /api/v1/orders/{orderId} → result: {orderId, symbol, side, orderType, timeInForce,
                                         status, price, quantity, orderAmount, currency,
                                         orderedAt, canceledAt,
                                         execution: {filledQuantity, averageFilledPrice,
                                                     filledAmount, commission, tax,
                                                     filledAt, settlementDate}}
GET  /api/v1/stocks?symbols=  → result[]: {symbol, market(NASDAQ), securityType(STOCK),
                                           status(ACTIVE), currency, delistDate, isinCode, listDate}
GET  /api/v1/market-calendar/US → result.today: {regularMarket, preMarket, afterMarket} 각 {startTime,endTime}
                                  + previousBusinessDay / nextBusinessDay (휴장 판정에 사용 가능)
```

- `execution.filledQuantity`는 **체결수량 기반 관리셋 M 갱신**의 입력이다. 현재 러너는 발주 의도 기준으로만
  M을 갱신한다([managed.py](src/execution/managed.py) 한계 주석) — 정밀화하려면 위 GET 래퍼부터 추가해야 한다.
- `market` / `status` + `delistDate` / `listDate`는 OTC 배제·생존편향 교차검증·PIT 편입일 판정에 쓴다.
- market-calendar 시각 예: 정규장 `22:30~익일 05:00 KST`(=09:30~16:00 ET), preMarket `17:00~22:30`, afterMarket `05:00~08:50`.

---

## 환경 노트 — qlib 워커 멈춤 (2026-08-16 확인)

`D.features()`가 이 환경에서 **무한 대기**한다. `qlib.init` 자체는 1초 미만으로 정상이다
(초기 진단이 `init`을 지목했으나 오진이었다 — 커밋 `ec74313` 메시지의 서술은 이 절로 정정한다).

```python
qlib.init(provider_uri=<절대경로>, region=REG_US, kernels=1)   # ← 회피책
```

- 멈추는 지점은 `D.features()`의 **멀티프로세싱 워커**다. 파일 실행·heredoc 모두 동일하므로
  stdin 문제가 아니다. macOS spawn 방식과의 조합으로 보이나 근본 원인은 미규명
- `kernels=1`이면 즉시 완료된다. 대량 종목 스캔에서는 느려질 수 있으니 용도에 따라 판단할 것
- 다른 세션의 동일 저장소에서는 기본 설정으로도 1초 미만에 동작했다 — **환경 의존**이다.
  따라서 qlib을 쓰는 검증 코드는 실패를 치명으로 다루지 말고 감싸는 편이 안전하다

## Phase 1 — 개발 환경 구축 (M1 + pyenv)

- `brew install libomp` (LightGBM OpenMP)
- `pyenv install 3.10.14` → 프로젝트 폴더 `python -m venv .venv`
- `pip install "numpy<2" "cython<3" "pandas<2.2"` 선행 → `pip install pyqlib` (실패 시 소스 `pip install -e .`)
- **검증:** `python -c "import qlib, lightgbm, xgboost"` 성공
- 커밋: `build: qlib 환경 구축 (M1+pyenv)`

## Phase 2 — 데이터 파이프라인 (S&P500 → Qlib bin)

- Yahoo collector로 **처음부터** 데이터 구축 (offline data는 증분불가)
- S&P500 종목 리스트 확보 → collector 수집 → `dump_bin`
- 증분 갱신 스크립트: `update_data_to_bin --region US`
- **[개선3] point-in-time 유니버스:** 가능하면 시점별 S&P500 구성 사용. 불가 시 "현재 구성으로 백테스트 → 편입/편출 편향으로 성과 과대평가"를 한계로 기록하고 결과 해석에 반영
- **[개선9] yfinance 취약성 대응:** 비공식 스크래퍼라 간헐 차단·스키마 변경 가능 → 수집에 재시도(backoff)·실패 알림·직전 정상데이터 폴백. 지속 실패 시 토스 candle API 폴백 검토
- **[개선12] $vwap 프록시:** Alpha158이 `$vwap` 참조(feature 1~2개)하나 yfinance 미제공 → normalize에서 `(H+L+C)/3`로 합성·dump. 실제 거래량가중가와 달라 근사(영향 작음). (grilling 2026-07-17 발견, Phase 3 진입 전 소급 반영 완료)
- **에지케이스:** 수정주가(배당·분할)·상장폐지 종목(생존편향)·거래정지·point-in-time 편향
- **검증:** `qlib.init` 후 데이터 로드 + 최근일 존재 확인
- 커밋: `feat(data): S&P500 미국 데이터 수집·bin 변환 파이프라인`

## Phase 3 — 모델 학습 + 백테스트 (과최적 방지)

### grilling 결정 (2026-07-17, Phase 3 진입 전)
- **[B1] $vwap 프록시** — Alpha158이 `$vwap` 참조. Phase 2에 `(H+L+C)/3` 합성으로 소급 반영 완료(개선12). ✅
- **[B2] 라벨 horizon = 주간** — Alpha158 기본 라벨은 익일 수익률(`Ref($close,-2)/Ref($close,-1)-1`). 주간 리밸에 맞춰 **5거래일 fwd로 override**: `["Ref($close,-6)/Ref($close,-1)-1"]` + 백테스트 executor 주간 스텝. ⚠️ 일간샘플+5일 라벨은 **겹침(overlapping)** → validation IC 자기상관 오염을 한계로 명시(파일럿 허용). 엄밀판(주간 비겹침 샘플링)은 유니버스 확장 후.
- **[B3] 유니버스 2단계** — 41종목은 K=15~20이면 유니버스의 37~49% 보유 → 횡단 랭킹 무의미. **① 41종목=config 배선 스모크(돌아가나/지표 계산되나) → ② 현 S&P500 전체(~500)로 확장 재실행=실제 엣지 판독**. 41 지표로 전략 우열 판단 금지. 확장 시 현 구성 리스트 소스 필요(생존편향은 개선3 유지).

### 작업
- Alpha158 + LightGBM, config YAML 작성 (라벨은 B2대로 override)
- **train/valid/test 시간순 분리, test 최근 30% 격리**
- walk-forward 1회 이상
- **[개선2] 백테스트=실전 조건 미러링:** 주간 리밸런싱·K·롱온리·소수점(fractional) 포지션·토스 실제 수수료·환전비용을 백테스트에 반영. **Phase 0(2026-07-20) 실측 반영 완료** — 실측치로 교체(§Phase 0 실측 상수):
  - 거래 수수료: **~0.10%/편도** (보유 `cost.commission` 실측, 매수·매도 각각) ✅
  - 환전 비용: **~0.03%/편도** (FX 스프레드 3bp 실측; 기존 추측 0.20%의 1/6) ✅
  - 슬리피지: **0.10%** (하한 가정 유지 — 실체결 없어 미측정)
  - → config open_cost/close_cost 0.004→**0.0023**. 재판정 결과: 비용 낮춰도 exploitable 엣지 미검출(무비용 초과수익≈0 → 신호품질 병목). Phase 3 결론 유지·확인.
- **[개선7] 회전율 제어:** TopkDropout은 이산 등가중(목표비중 개념 없음)이라 no-trade band 적용 지점 없음 → **회전율은 `n_drop` 튜닝으로 제어**(네이티브). 비중형 band가 필요하면 EnhancedIndexing 등 비중형 전략으로 교체 검토
- **벤치마크:** SPY(+41종목 등가중) 대비 초과수익·정보비율 병행 보고 (절대 Sharpe만으로 판단 금지)
- **검증 지표:** IC/Rank IC, IR, MDD, 회전율. **Sharpe 4+면 과최적 의심 → 재검토**
- **규율:** valid로 early-stop, test는 1회만 관측(test 튜닝 금지), 시드 고정
- **에지케이스:** lookahead bias·비현실적 지표·회전율 과다·백테스트-실전 조건 괴리·$700/최소주문 granularity 미반영(백테스트 낙관 편향, 한계 기록)
- 커밋: `feat(model): Alpha158+LightGBM 학습·백테스트 (walk-forward)`

## Phase 4 — 시그널 생성 자동화

- 학습 모델로 주간 예측 → 상위 K종목 목표비중 파일(JSON) 생성
- Qlib Online Serving 또는 단순 predict 스크립트
- **검증:** 시그널 파일이 K종목·비중합=1 형태로 생성
- 커밋: `feat(signal): 주간 목표 포트폴리오 시그널 생성`

## Phase 5 — 토스 어댑터 (시그널 → 발주)

> **진행(2026-07-18, P2 골격)**: 리서치(qlib은 예측까지만 지원 → 발주는 자작)로 **레이어 분리** 확정.
> `src/toss`(브로커 transport) ↔ `src/execution`(브로커 비의존 OMS). 완료:
> - `execution/rebalance.compute_rebalance`(순수): 목표비중 diff → 매도先→매수, 개선1(자금이월)·5(멱등키)·8(최소금액). 단위테스트 7.
> - `execution/safety`: kill switch·서킷브레이커(개선4). 테스트 4.
> - `toss/broker.TossBroker`: transport glue(⚠️ 응답필드 Phase 0 실측 확정 전 방어파싱).
> - `execution/runner.RebalanceRunner`: 스냅샷→화이트리스트 필터→compute→dry-run/실발주.
> - **[개선14] 계좌 공유 안전(화이트리스트)** — 계좌를 사용자 수동 보유·현금과 공유하므로:
>   `execution/managed.ManagedState`가 제외셋 X(첫 실행 시 보유 동결, 봇 비관리)·관리셋 M(봇 산 종목,
>   placed에서만 갱신)을 `execution_logs/managed_state.json`에 영속. runner는 목표에서 X 제거·M 종목만
>   리밸 → **사용자 종목 절대 매도 안 함**. 예산 상한(budget_usd)으로 계좌 현금 과지출 차단. 테스트 8.
> - `scripts/live/rebalance.py`: 라이브 발주 진입점 — 시그널→TossBroker 조립, **dry-run 기본**(`--confirm` 실발주), 화이트리스트·예산·kill switch·서킷브레이커 배선. 키 없으면 안전 종료(TossConfigError).
> **잔여**: 실 API 배선·응답필드 확정(Phase 0 대기), cron 스케줄(Phase 6), max-loss 손익 배선(Phase 0). 개선11은 구현·mock검증 완료(실 401 확인만 Phase 0).

- 모듈: `auth`(토큰캐싱) · `account`(holdings·buying-power) · `order`(생성·조회)
- 리밸런싱 로직: 현 보유 vs 목표 diff → 매도(빠질 종목, 수량 시장가) → 매수(금액 시장가 orderAmount)
- **[개선1] 매도→매수 자금순환(T+N):** 매수 전 `buying-power` 재조회, **가용 USD 기준으로만 발주**. 매도대금이 T+N로 즉시 안 잡히면(Phase 0-6 결과) 매수는 결제 반영분·현금버퍼 내에서만 → 목표 미달분은 다음 주기로 이월(부분 리밸런싱 허용)
- **[개선5] 결정적 멱등키 + 재개 정합성:** `clientOrderId = hash(리밸런싱일자+symbol+side)` — **금액은 키에서 제외**(T+N 정산으로 재실행 시 가용액·목표금액이 변동 → 금액 포함 시 부분매수 재개 때 키가 바뀌어 멱등 붕괴, code-review 2026-07-18 발견). 하루 한 종목당 side별 1주문(주간 리밸) 가정. 재시도해도 동일 값이라 중복주문 방지. 매 실행은 **live holdings 재조회 후 diff**로 시작 → 크래시 후 재실행해도 이미 체결된 주문 재발주 안 함(멱등·재개 가능)
- **[개선8] 최소금액 미달 배분:** 목표금액이 최소주문금액(Phase 0-4) 미만인 종목은 **스킵 또는 상위 종목으로 금액 재배분**. K는 실제 발주 가능 종목 수로 수렴
- **[개선4] 안전장치:** `--dry-run`(주문 대신 발주계획 로그만) · 파일/env 기반 **kill switch**(존재 시 즉시 중단) · **서킷브레이커**(일일 주문건수·손실 상한 초과 시 정지)
- **market-calendar/US로 정규장 확인 후** 발주
- Rate limit 준수(호출 간 sleep), 에러코드별 처리(잔액부족·장마감·rate-limit)
- **[개선10] 라이브러리 예외화 ✅(2026-07-18 완료):** `src/toss/`는 설정/계좌/토큰 오류를 `SystemExit` 대신 `TossError` 계열(`TossConfigError`·`TossAuthError`·`TossApiError`, `errors.py`)로 던진다. `SystemExit` 종료 변환은 CLI(`_bootstrap.cli`)에서만 → cron 자동화가 서킷브레이커·kill switch·부분 이월로 잡을 수 있음.
- **[개선11] invalid-token 재시도 ✅(2026-07-20 구현, mock 검증):** `TossClient.request()`가 401 응답 시 `get_token(force_refresh=True)` 후 **1회만** 재시도(`_retry` 플래그로 상한). 401은 미처리 거부라 POST /orders 재시도도 안전(clientOrderId 멱등키 이중안전망). mock 테스트 3(재시도·상한·비401 무재시도). **실 401 동작 확인만 Phase 0(키 승인 후).**
- **[개선13] OAuth 응답바디 로깅 누설 ✅(2026-07-18 완료):** 토큰 발급 실패 시 `resp.text`(전체 본문) 대신 표준 OAuth `error`/`error_description`만 노출(비-JSON이면 status만). `auth.py:_oauth_error_detail`. (code-review 2026-07-17 발견)
- **에지케이스:** 정규장 외 호출·부분체결·잔액부족·네트워크 재시도·환전 미완·크래시 중 부분 리밸런싱
- **검증:** 각 함수 단위 테스트 (mock 응답) — dry-run 발주계획·멱등키 재현·최소금액 스킵·자금부족 이월 케이스 포함
- 커밋: `feat(broker): 토스 OpenAPI 리밸런싱 어댑터`

## Phase 5.5 — 집행 캘리브레이션 (2026-08-16 신설)

전략이 없어도 옳은 집행 개선이다. 알파를 찾는 게 아니라 **낭비를 줄이고, 나중에 알파가
생겼을 때 검증할 기록을 미리 남긴다.**

### 왜 — 문헌 근거 (수치를 직접 적어 둔다)

로컬 조사 노트는 git 추적 밖이라 사라질 수 있으므로 근거를 여기 옮긴다.

| 출처 | 수치 | 함의 |
|---|---|---|
| Vanguard, *Getting back on track* (1926–2018, 60/40 세후) | 월간 0% 임계 **1,116회 → 8.20%** / 연간 10% 임계 **14회 → 8.20%** | 회전 80배 차이에 수익은 동일. 자주 리밸런싱할 이유가 없다 |
| 같은 표 | 리밸런싱 **안 함 8.74%**(최고), 변동성 14.0% / 월간 8.20%, 변동성 11.7% | **"리밸런싱 보너스"는 수익이 아니다.** 연 54bp를 내고 변동성과 배분 유지를 산다 |
| Vanguard 결론 인용 | *"we don't find a specific rebalancing threshold or frequency that consistently outperforms"* | 최적값 탐색은 무의미. 정하고 지키는 게 전부 |
| Barber & Odean (2000) | 고회전 가구 순 **11.4%** vs 저회전 **18.5%** — 총수익은 거의 동일 | 격차 7.1%p가 전부 비용 |
| Lo (2002) `SE(SR)=√((1+SR²/2)/T)` | 연 SR 0.5를 0과 구분하는 데 **약 16년**. 월→주→일로 바꿔도 16.2 → 16.0년 | **관측을 자주 해도 알파 판별이 빨라지지 않는다** |
| Chopra & Ziemba | 추정오차 민감도 **평균 : 분산 : 공분산 = 100 : 3 : 1** | 추정 기대수익에 비례한 사이징 금지 |
| DeMiguel, Garlappi & Uppal (2009) | 최적화가 1/N을 이기려면 25종목 **3,000개월(250년)** | 동일비중 유지 |

### 확정 — no-trade 밴드

| 축 | 값 |
|---|---|
| 밴드 | **`rebalance_band = 0.10`** — 목표 대비 \|편차\|/목표 가 10% 이하면 거래하지 않는다 |
| 점검 주기 | **연 1회** (드리프트가 크면 그 사이에도 kill switch로 개입 가능) |
| 집행 하한 | `min_order_usd`는 그대로 두되 **밴드와 역할이 다르다** — 하한은 브로커 제약, 밴드는 정책 |

> ⚠️ **이 값은 실현 성과를 보고 바꾸지 않는다.** 문헌이 우열을 가리지 않으므로 성과를 근거로
> 조정하면 그건 개선이 아니라 노이즈 추종이다. 바꿀 수 있는 경우는 **목표 포트폴리오의 성격이
> 바뀔 때**(예: 종목 수·자산군 변경)뿐이고, 그때도 바꾼 날짜와 이유를 여기 적는다.

**왜 밴드가 필요했나**: 종전에는 `min_order_usd`가 밴드를 겸했는데 Phase 0 실측이 **$1 이하**라,
$700 계좌에서 **포트폴리오의 0.14% 드리프트에도 주문이 나갔다.**

### 자동 갱신 경계 — 무엇을 자동으로 고쳐도 되나

기준은 신호 대 잡음이다. 같은 계좌에서 어떤 값은 수십 건이면 알고 어떤 값은 16년이 걸린다.

**자동 갱신 허용** (평균 대비 분산이 작아 빨리 수렴)

| 파라미터 | 출처 |
|---|---|
| 종목별 실효 스프레드 | 체결가(`execution.averageFilledPrice`) vs 결정 시점 가격 |
| 실효 수수료율 | holdings의 `cost.commission` (주문 응답의 commission은 전부 0) |
| 체결률·부분체결 | `execution.filledQuantity` vs 주문 수량 |
| T+2 실제 반영 지연 | buying-power 시계열 |

**자동 갱신 금지** (노이즈가 지배)

| 파라미터 | 이유 |
|---|---|
| 목표 비중·종목 선택 | SR 판별에 16년. 주기를 올려도 안 줄어든다 |
| 호라이즌·필터·이상치 규칙 | 사전등록 고정 축이면 변경은 재작성 사유 |
| **밴드 폭** | 성과 기반 조정은 그 자체가 사후 최적화 |

### 구현 상태

- ✅ **no-trade 밴드** — `RebalanceParams.rebalance_band`, `compute_rebalance`에서 적용.
  편출(target에서 빠진 종목)에는 적용하지 않는다 — 드리프트가 아니라 편입 해제다
- ✅ **결정 스냅샷** — `RunResult.snapshot`에 목표비중·가격·보유·예수금·밴드를 담아 주문 로그에 기록
- ⚠️ **체결 실측** — `broker.get_order()` 추가. 발주 응답의 `orderId`를 잡아 조회하고
  `RunResult.fills`에 담는다. **필드명은 Phase 0 실측표를 근거로 썼을 뿐 실응답으로 검증되지
  않았다** — 과거 체결 주문을 목록으로 끌어올 경로가 없어서다(`GET /orders`는 `status`에
  `SCHEDULED/ACTIVE/DELISTED`만 받고 미체결은 0건). 대신 실패를 안전하게 만들었다:
  스키마가 다르면 크래시 대신 값이 비고 **경고를 출력**하며, 조회가 터져도 발주 기록은 남는다.
  **첫 실주문 때 이 경고가 뜨는지 반드시 확인할 것**
- ✅ **holdings 스냅샷** — `scripts/live/snapshot_holdings.py` (읽기 전용).
  `cost.commission`은 조회 시점의 누적 상태라 저장하지 않으면 되살릴 수 없다
- ✅ **E10 서킷브레이커 파일영속** — 인메모리만 쓰면 상한에 걸려 멈춘 뒤 재기동하는 것만으로
  카운터가 0이 되어 **재시작이 안전판을 우회**했다. 주문·손실을 기록할 때마다 즉시 저장하고,
  "일일" 경계는 호출자가 주는 리밸 일자로 판정한다(시간대 해석에 의존하지 않는다).
  상태 파일이 손상돼도 발주를 막지는 않되 카운터는 0에서 다시 센다
- ⏳ **비용 캘리브레이터** — **의도적으로 미구현.** 입력 로그가 0건이라 지금 만들면
  실데이터를 못 본 채 스키마를 추측하게 된다. 첫 실주문 뒤에 만든다

---

## Phase 6·7 진입 조건 ⚠️ (2026-08-16 신설)

**두 Phase 다 "net 초과수익이 기대되는 전략"을 전제한다. 지금 그런 전략이 없다.**

| 판정 | 대상 | 결과 |
|---|---|---|
| Phase 3 | 대형주 주간 Alpha158+LightGBM / GRU | 엣지 없음. +12%는 β1.5 틸트였고 alpha≈0 |
| Edge v2 | 마이크로캡 + Form 4 `P` 매수 | 1층 게이트 불통과. 비용 전 BHAR +0.21%(t=0.52) |

따라서:

- **Phase 6 스모크는 "인프라 검증" 목적으로만 유효하다.** 주문·수량계산·인증·kill switch가
  실제로 도는지 최소금액으로 확인하는 것이며, **알파를 기대하고 넣는 돈이 아니다.**
  실탄이 들고 USD 선환전이 선행돼야 하므로 **사용자 승인 없이는 진행하지 않는다.**
- **Phase 7(전액 가동)은 진입 조건을 못 갖췄다.** 굴릴 전략이 없으므로 착수하면
  기댓값이 음수인 매매를 자동화하는 것이 된다. **새 전략이 게이트를 통과하기 전까지 보류.**
- 사전등록이 지목한 귀결은 **인덱스/DCA**다(`PREREGISTRATION.md` §10.2).
  그쪽으로 갈 경우 필요한 것은 알파 탐색이 아니라 **정기 매수 집행 자동화**이며,
  Phase 5까지의 발주 어댑터·안전장치를 그대로 재사용할 수 있다.

## Phase 6 — 스모크 테스트 + cron 가동

> **전제**: 위 진입 조건. 지금은 **인프라 검증 목적으로만** 수행한다.

- **1주(또는 최소금액) 실발주 스모크** → 수량계산·중복주문·인증 버그 실측 검증 (먼저 `--dry-run`으로 발주계획 확인 후 실발주)
- **[개선6] 리밸런싱 스케줄 + DST:** "매주 X요일" 확정. 미국 정규장의 한국시간은 서머타임으로 이동(밤 22:30↔23:30) → cron은 넉넉히 일찍 깨우고 **market-calendar/US로 정규장 개장·휴장 확인 후** 발주 (하드코딩 시각 금지)
- cron 등록: 데이터갱신(장마감후) + 발주(정규장 확인 후). 초기엔 cron, 다단계 고도화 시 Airflow
- **검증:** 스모크 주문 체결 + 로그·알림 정상 + kill switch 동작 확인
- 커밋: `feat(ops): cron 스케줄 + 1주 스모크 검증`

## Phase 7 — 소액 실전 + 모니터링 ⛔ **보류 (진입 조건 미충족)**

- ~~전액(100만원) 가동~~ — **굴릴 전략이 없다.** 위 진입 조건 참조
- 아래는 새 전략이 게이트를 통과했을 때를 위해 남겨 둔 설계다
- 전액 가동, 텔레그램/로그 알림
- 주간 성과 vs 백테스트 괴리 관찰(슬리피지·미체결)
- (선택) 조건주문(OCO)으로 손절/익절

---

## 핵심 에지케이스 (전체)

1. **정규장 외 금액주문** → market-calendar 사전확인, 아니면 대기/스킵
2. **최소금액 미달 매수** → Phase 0 실측값으로 종목당 금액 하한 보장, 미달 종목 스킵·재배분
3. **소수점 불가 종목** → 유니버스에서 사전 제외
4. **네트워크 재시도 중복주문** → 결정적 clientOrderId 멱등키
5. **부분체결/미체결** → 주문조회로 실제 체결 확인 후 회계
6. **잔액부족·환전 미완** → buying-power(USD) 사전확인
7. **생존편향·point-in-time 편향** → 폐지종목 포함 + 시점별 지수구성(불가 시 한계 명시)
8. **매도→매수 자금순환(T+N)** → 매수 전 buying-power 재조회, 가용액 내 발주·부분 이월
9. **크래시 중 부분 리밸런싱** → live holdings 재조회 diff로 멱등 재개

---

## 리스크·한계

- 백테스트 수익 ≠ 실전 수익 (과최적·슬리피지)
- $700 규모는 수수료·환전·세금 비중 큼 → **학습·검증 목적** 성격
- 토스 API 샌드박스 없음 → 실환경 소액이 유일한 코드 검증 통로
- 해외주식 양도소득세(연 250만원 공제 후 22%)·배당 원천징수

---

## 미확정 설계 결정
- 없음. 전략 4대 결정은 §0-1 표로 확정(grilling-plan), API 스펙은 정본 검증 완료.
- Phase 0 실측(2026-07-20) 완료: 최소 ≤$1·소수점 OK → **K=15~20 확정**(유니버스 축소 불필요).
- 운영 제약(신규): 자동환전 안 됨 → 봇 가동 전 KRW→USD **선환전 필요**(Phase 6 반영).