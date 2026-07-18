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

> ⚠️ K값·유니버스는 Phase 0의 **최소 주문금액·소수점 가능 종목** 실측 결과에 따라 조정될 수 있음.

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

**Phase 0 완료 게이트:** 위 7개 모두 확인 + K값/유니버스 확정 → Phase 1 착수

---

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
- **[개선2] 백테스트=실전 조건 미러링:** 주간 리밸런싱·K·롱온리·소수점(fractional) 포지션·**토스 실제 수수료(`GET /commissions`)**·환전비용을 백테스트에 반영. ⚠️ **실수수료는 Phase 0(키 승인 대기)에 의존** → 아래 **보수적 placeholder**로 시작, Phase 0 풀리면 실측치로 교체:
  - 거래 수수료: **0.10%/편도** (매수·매도 각각)
  - 환전 비용: **0.20%/편도** (원↔달러 스프레드 가정)
  - 슬리피지: **0.10%** (하한 가정)
  - ※ 위 수치는 실측 아님·추측 placeholder. Phase 0 `GET /commissions`+환율 실측으로 반드시 갱신
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
> **잔여**: 실 API 배선·응답필드 확정(Phase 0 대기), 발주 runner(Phase 4 시그널 필요), 개선11(401 재시도).

- 모듈: `auth`(토큰캐싱) · `account`(holdings·buying-power) · `order`(생성·조회)
- 리밸런싱 로직: 현 보유 vs 목표 diff → 매도(빠질 종목, 수량 시장가) → 매수(금액 시장가 orderAmount)
- **[개선1] 매도→매수 자금순환(T+N):** 매수 전 `buying-power` 재조회, **가용 USD 기준으로만 발주**. 매도대금이 T+N로 즉시 안 잡히면(Phase 0-6 결과) 매수는 결제 반영분·현금버퍼 내에서만 → 목표 미달분은 다음 주기로 이월(부분 리밸런싱 허용)
- **[개선5] 결정적 멱등키 + 재개 정합성:** `clientOrderId = hash(리밸런싱일자+symbol+side+금액)` — 재시도해도 동일 값이라 중복주문 방지. 매 실행은 **live holdings 재조회 후 diff**로 시작 → 크래시 후 재실행해도 이미 체결된 주문 재발주 안 함(멱등·재개 가능)
- **[개선8] 최소금액 미달 배분:** 목표금액이 최소주문금액(Phase 0-4) 미만인 종목은 **스킵 또는 상위 종목으로 금액 재배분**. K는 실제 발주 가능 종목 수로 수렴
- **[개선4] 안전장치:** `--dry-run`(주문 대신 발주계획 로그만) · 파일/env 기반 **kill switch**(존재 시 즉시 중단) · **서킷브레이커**(일일 주문건수·손실 상한 초과 시 정지)
- **market-calendar/US로 정규장 확인 후** 발주
- Rate limit 준수(호출 간 sleep), 에러코드별 처리(잔액부족·장마감·rate-limit)
- **[개선10] 라이브러리 예외화 ✅(2026-07-18 완료):** `src/toss/`는 설정/계좌/토큰 오류를 `SystemExit` 대신 `TossError` 계열(`TossConfigError`·`TossAuthError`·`TossApiError`, `errors.py`)로 던진다. `SystemExit` 종료 변환은 CLI(`_bootstrap.cli`)에서만 → cron 자동화가 서킷브레이커·kill switch·부분 이월로 잡을 수 있음.
- **[개선11] invalid-token 재시도 ⏳(Phase 5 유보):** `TossClient.request()`가 401 응답 시 `get_token(force_refresh=True)` 후 **1회만** 재시도(`_retry` 플래그로 상한). 401은 미처리 거부라 POST /orders 재시도도 안전(clientOrderId 멱등키 이중안전망). **API 동작 의존(실 401)이라 실검증은 키 승인 후** → 실 발주 흐름과 함께 구현.
- **[개선13] OAuth 응답바디 로깅 누설 ✅(2026-07-18 완료):** 토큰 발급 실패 시 `resp.text`(전체 본문) 대신 표준 OAuth `error`/`error_description`만 노출(비-JSON이면 status만). `auth.py:_oauth_error_detail`. (code-review 2026-07-17 발견)
- **에지케이스:** 정규장 외 호출·부분체결·잔액부족·네트워크 재시도·환전 미완·크래시 중 부분 리밸런싱
- **검증:** 각 함수 단위 테스트 (mock 응답) — dry-run 발주계획·멱등키 재현·최소금액 스킵·자금부족 이월 케이스 포함
- 커밋: `feat(broker): 토스 OpenAPI 리밸런싱 어댑터`

## Phase 6 — 스모크 테스트 + cron 가동

- **1주(또는 최소금액) 실발주 스모크** → 수량계산·중복주문·인증 버그 실측 검증 (먼저 `--dry-run`으로 발주계획 확인 후 실발주)
- **[개선6] 리밸런싱 스케줄 + DST:** "매주 X요일" 확정. 미국 정규장의 한국시간은 서머타임으로 이동(밤 22:30↔23:30) → cron은 넉넉히 일찍 깨우고 **market-calendar/US로 정규장 개장·휴장 확인 후** 발주 (하드코딩 시각 금지)
- cron 등록: 데이터갱신(장마감후) + 발주(정규장 확인 후). 초기엔 cron, 다단계 고도화 시 Airflow
- **검증:** 스모크 주문 체결 + 로그·알림 정상 + kill switch 동작 확인
- 커밋: `feat(ops): cron 스케줄 + 1주 스모크 검증`

## Phase 7 — 소액 실전 + 모니터링

- 전액(100만원) 가동, 텔레그램/로그 알림
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
- Phase 0 실측 결과(최소 주문금액·소수점 가능 종목)에 따라 **K값·유니버스 규모만** 조정 가능.