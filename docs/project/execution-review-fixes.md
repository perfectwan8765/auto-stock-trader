# 실행 코드 리뷰 조치 작업계획서

- 작성일: 2026-08-16
- 최종수정: 2026-08-16
- 상태: 진행중 (1~9단계 완료, 10단계 PR만 남음)

> **후속 코드리뷰 조치 (2026-08-17).** 1~9단계를 마친 뒤 브랜치 전체를 다시 리뷰해 12건을
> 받았고 7건을 이 브랜치에서 조치했다. 그중 **`market_closed`·예외 경로가 실발주 원장을
> 덮어쓰던 것은 5-1이 만든 회귀**다(종전에는 그 경로가 로그를 쓰지 않아 충돌이 없었다).
> 나머지 5건은 아래 "명시적 제외"에 근거와 함께 기록했다.

## 목표

`src/execution/`·`src/toss/` 실거래 경로의 정확성 결함 **8건**을 첫 실발주 전에 닫고,
그 조치를 `docs/project/roadmap.md`에 반영한다.
브랜치 `fix/execution-review` 하나에 11개 커밋으로 처리하고, PR 1개로 머지한다.

⚠️ **손실 서킷브레이커는 완결되지 않는다.** 손실 축의 결함은 둘인데(B-1 청산 직후 리셋,
B-2 실현손실 미계상) **B-1만 고친다.** B-2는 평단가 수집 경로 신설이 필요해 제외했다.
이 계획이 끝나도 **실현손실은 여전히 상한에 반영되지 않는다** — "손실 상한이 완성됐다"로
읽으면 안 된다.

완료 판정은 두 가지다 — 전체 테스트 통과, 그리고 **실계좌 dry-run 1회 무예외 완주**.

이 계획은 Phase 6 스모크(최소금액 실발주)를 **포함하지 않는다.** roadmap.md의 Phase 6·7
진입 조건이 "사용자 승인 없이는 진행하지 않는다"로 못박혀 있고, 그 승인은 이 계획서와
별개의 결정이다.

## 배경

2026-08-16 코드리뷰에서 `src/execution/` 전체와 `src/toss/broker.py`·`client.py`·`auth.py`를
현재 코드 전체 기준으로 점검해 15건을 찾았다. 부분체결·T+N 결제·서킷브레이커·멱등/재개·
rate-limit·파싱 fail-safe·임포트 규약의 7개 축으로 봤다.

전제로 확인한 사실:

- **실거래는 아직 시작 전이다.** `crontab` 비어 있고 `KILL` 파일 없음.
  `execution_logs/`에는 dry-run 산출물 `rebalance_20260716.json` 1건뿐이다.
  [roadmap.md](roadmap.md) 기준 Phase 6 미착수, Phase 7 보류.
- **실 계좌 읽기는 동작한다.** Phase 0이 2026-07-20 실주문까지 포함해 완료됐고,
  `execution_logs/holdings_20260816.json`이 오늘 생성돼 있다.
- 따라서 이번 작업은 사고 대응이 아니라 **첫 실발주 전 사전 정비**다. 마이그레이션 부담이
  0인 지금이 파일 포맷·기본값을 바꾸기 가장 싼 시점이다.

### 결함 매핑 — 조치 8건 + 제외 1건

아래 9행 중 **B-2만 이번 범위 밖**이다. 나머지 8건을 닫는다.

| # | 결함 | 위치 |
|---|---|---|
| A | 서킷브레이커의 "하루"가 캘린더 날짜가 아니라 시그널 날짜 | `scripts/live/rebalance.py:139` · `src/execution/safety.py:64` |
| B-1 | 손실 축이 청산 직후 리셋됨 (**이번에 조치**) | `src/execution/runner.py:218-220` · `src/execution/safety.py:101` |
| B-2 | 실현손실을 전혀 세지 않음 — `record_loss` 프로덕션 호출 0건 (**이번엔 제외**) | `src/execution/safety.py:104` |
| C | 손실 상한이 매도(청산)까지 차단 | `src/execution/runner.py:229-231` |
| D | 주문 수량 문자열이 지수표기로 나감 | `src/toss/broker.py:275` |
| E | 클램프된 부분매도 exit이 관리셋 M에서 빠짐 | `src/execution/runner.py:151` · `src/execution/managed.py:80` |
| F | 매도가능수량 미조회 가드가 실 어댑터에서 발동 불가 | `src/toss/broker.py:240` · `src/execution/runner.py:130` |
| G | 예외 경로에서 주문로그 유실 + `market_closed` 반환에 snapshot 없음 | `src/execution/runner.py:212, 247-257` |
| H | 401 재발급 토큰 폐기 · 토큰 캐시 chmod 경합 · `place()` 반환 어노테이션 | `src/toss/client.py:60` · `src/toss/auth.py:75` · `src/toss/broker.py:264` |

### 재현 시나리오

커밋 본문과 PR에 그대로 쓸 재료다. 각 항목은 **입력 → 오동작 → 실돈 결과** 순이다.

**A. 서킷브레이커 일일 경계**
주문건수 상한 60에 걸려 멈춘다 → 운영자가 `generate_signal.py`를 다시 돌린다 → 새 시그널
날짜 → `_restore`의 `d.get("day") != self.day`가 조기 return → `orders_today=0`,
`daily_loss_usd=0`. **같은 캘린더 날에 상한이 통째로 리셋된다.** 역방향도 있다 —
`--max-age-days` 기본 5라 같은 시그널이 최대 5일간 같은 `day` 키를 써서, 월요일 주문 60건이
금요일 발주를 막는다.

**B-1. 손실 축 리셋**
`managed={MSFT, NVDA}`, `daily_pnl={MSFT:+10, NVDA:-600}` → `observe_daily_loss(590)` 영속
(상한 700). 그 실행이 NVDA를 전량 청산 → `managed={MSFT}`. 같은 날 재실행: NVDA가 holdings에서
사라져 `daily=+10` → `observe_daily_loss(-10)` → `max(0.0,-10)=0.0` **대입** → 590이 지워진다.
**손실을 확정하는 행위(청산)가 상한을 해제한다.**

**C. 손실 상한이 청산을 차단**
`guard()`가 `plan.orders` 전 주문 앞에서 걸리고 `plan.orders`는 매도가 앞이다. 당일 손실이
상한을 넘으면 **첫 매도에서 트립**해 청산이 불가능해진다. `--max-loss 700`(=예산 전액)일 때는
절대 발동하지 않아 드러나지 않았고, **70으로 내리는 순간 살아난다.** 시장이 10% 빠진 날
봇은 팔지 못하고 물린 채 멈춘다.

**D. 수량 문자열 지수표기**
`f"{3e-05}"` → `'3e-05'`, `f"{1e-08}"` → `'1e-08'` (확인됨). exit 주문은 보유수량 원값을 쓰고
`qty <= 0`만 거르므로 dust 잔량이 그대로 나간다. API는 십진 문자열을 기대하므로 거부하거나
다른 크기로 오해석한다. 거부 코드가 `_ORDER_REJECT_CODES` 밖이면 `_place_order`가 잡지 않아
**리밸런싱 전체가 중단**된다.

**E. 부분매도 exit이 관리셋에서 이탈**
`managed={"OLD"}`, holdings `OLD=5.0`, sellable `OLD=3.0`(T+N 미결제), OLD가 목표에서 편출 →
exit 주문 5.0주가 3.0주로 클램프되는데 `reason`은 `"exit"` 그대로 → 발주 성공 →
`update_after_place`가 M에서 discard → `managed=set()`. 잔여 2.0주가 M에도 X에도 없어
**청산이 끝나지 않은 채 영구 방치**되고, `bot_value`가 줄어 `buying_power`가 과대 산출돼
**예산 상한을 넘겨 매수**한다.

**F. sellable 가드 무력화**
토스가 `/api/v1/sellable-quantity`에 `{"result": {}}`를 준다(HTTP 200) → `get_sellable_quantity`가
`0.0` 반환 → `get_sellable`이 모든 키를 채우므로 러너의 `unreported`가 빈 리스트 → 가드 통과 →
`sellable <= 0` → `skipped=[("OLD","not_sellable_settlement")]`. **매도가 조용히 사라지고
매 사이클 반복**된다. 이는 `runner.py:128-129` 주석이 막겠다고 명시한 바로 그 상황이다.

**G. 예외 경로 주문로그 유실**
주문 3건 발주 후 4번째 `guard()`가 `CircuitBreakerTripped` → `finally`가 M만 영속 → 예외가
`run()`을 뚫고 → `_cli`가 `SystemExit`. **발주된 3건의 `client_order_id`·`fills`·`snapshot`이
어디에도 없다.** rate-limit 소진·미분류 `TossApiError`·`requests.Timeout`도 같은 경로다.
`market_closed` 조기 반환은 `snapshot`조차 버린다.

**H. 인증 3건**
① 토큰 응답에 `expires_in`이 없거나 0이면 `_write_cache`가 생략되고, 401 재시도가
`get_token(force_refresh=True)` 반환값을 버린 채 캐시를 다시 읽어 **거부된 옛 토큰을 재전송**한다
→ 401 → `_retry=True`라 `TossApiError`. **401 복구 영구 불능.**
② `write_text`가 umask 기본(0644)으로 만든 뒤 `chmod(0o600)` — 그 사이 토큰 노출, 두 줄 사이에서
죽으면 0644로 영구 잔존.
③ `place()`가 `-> dict`인데 `str`을 반환(런타임 영향 없음, Protocol은 `str`로 맞다).

### 확정된 결정

| 결정 | 내용 | 근거 |
|---|---|---|
| 손실 축 처리 | 당일 최대 손실 워터마크(대입 → `max`) | 실배선(`record_loss`)은 평단가 수집 경로 신설이 필요해 이번 크기와 안 맞음. 후속 항목 |
| `--max-loss` 기본값 | 700.0 → **70.0** | 기존값이 `--budget` 기본값과 같아 포트폴리오 전액 손실에서만 트립 = 사실상 무발동 |
| `--max-orders` 기본값 | 60 유지 | 실측 데이터 없이 바꾸지 않는다. Phase 6에서 실제 주문 수 관찰 후 재평가 |
| 브랜치 | 단일 `fix/execution-review` | `broker.py`를 D·H가, `runner.py`를 E·G가 함께 건드려 브랜치를 가르면 충돌. 선례 `7fd287e fix: 코드리뷰 지적 15건 조치` |
| 테스트 | 어노테이션(H-3)·원자적 쓰기(I-1) 제외, 나머지 전부 재현 테스트 | 크래시 중 부분쓰기 재현 비용이 가치보다 크고, `write_text_atomic`은 이미 검증된 헬퍼 |
| dry-run 로그 | `rebalance_<date>.dryrun.json`으로 분리 | 대시보드가 파일명을 파싱하지 않고 파일을 열어 `d['date']`를 읽으므로(`scripts/dashboard/app.py:360`) 소비자 수정 불필요 |
| 완료 기준 | 실계좌 dry-run 포함 | 8건 중 4건이 실 응답 형태에 대한 판단인데 mock은 상상한 응답만 검증한다 |

### 명시적 제외

이번 범위 밖이며, 각각 별도 판단이 필요하다.

- **발주 중 네트워크 예외로 주문 성사 불명** — 근본책은 발주 전 intent WAL.
  `docs/research/dashboard-features.md:1129`에 "POST 전 flush" 설계가 이미 있다.
- **중복 `clientOrderId` 재발주가 주문 카운터를 이중계상** — 토스 응답이 신규/기존을
  구분해 주는지 미실측. Phase 6 스모크에서 관찰할 것.
- **`_collect_fills` 페이싱 부재** — `_get`의 백오프가 재시도하므로 데이터 유실이 아니라
  지연이다. 올바른 해법은 어댑터의 배치 조회이고 그건 인터페이스 변경이다.
- **kill switch가 `_build_plan` 뒤에 확인됨** — 최상단으로 옮기면 dry-run도 막혀
  계획 검토가 불가능해진다. 별도 설계 판단.
- **exit 최소수량(dust) 하한** — 하한 값 선택에 실측 근거가 없다. E 조치 후 첫 실측에서
  잔량 분포를 본 뒤 결정한다.
- **같은 날 실발주끼리의 주문로그 덮어쓰기** — dry-run/실발주 충돌만 이번에 막는다.
  실발주 재실행 간 충돌은 run_id 도입이 필요해 별건이다.
- **`exit_partial` 잔량이 같은 시그널 수명 안에서는 재매도 불가** — `make_client_order_id`가
  (일자·심볼·side)만 해싱하므로, 클램프로 남은 잔량 exit이 원 주문과 **같은 멱등키**를 쓴다.
  브로커가 중복으로 처리하므로 새 시그널이 나올 때까지(기본 최대 5일) 잔량 청산이 지연된다.
  회귀는 아니다 — 조치 전에는 그 종목이 M에서 빠져 **영영** 못 팔았고, 지금은 새 시그널이면
  팔린다. 근본 해결은 멱등키에 수량이나 실행 식별자를 넣는 것이고 그건 개선5 설계 변경이다.
- **같은 날 정상 종료 실발주 재실행의 원장 덮어쓰기** — 종료 경로(정상·중단·장마감·dry-run)는
  갈랐지만 *정상끼리*는 여전히 같은 이름이다. run_id 도입이 필요하다.
- **주문로그 파일 모드가 0600** — `write_text_atomic`(`mkstemp`)의 결과다. 상태 파일과 같아졌고
  보유 종목이 담기는 파일이라 방향은 맞다고 봤다. 봇과 다른 계정으로 대시보드를 띄우면
  읽지 못하므로, 그런 운영을 하게 되면 `write_text_atomic`에 mode 인자를 두는 편이 낫다.
- **`--max-loss` 워터마크의 운영자 해제 수단** — `dailyProfitLoss.amount`의 통화가 미검증인
  상태에서 임계를 70으로 조였다. 값이 USD가 아니면 첫 실발주에서 워터마크가 상한을 넘고,
  `max()`라 장중 회복으로도 안 내려간다. **해제는 `execution_logs/circuit_breaker.json` 삭제**다
  (`day` 키가 바뀌어도 리셋된다). Phase 6 관찰 항목의 통화 확인이 이 위험을 닫는다.
- **`_build_plan` 단계 예외는 주문로그를 남기지 않는다** — 매도가능수량 미조회 중단(4-3)이
  여기 해당한다. `snapshot`이 완성되기 전이라 남길 내용이 부실하고, kill switch·정규장 확인
  **앞**이라 그날 매수까지 전부 막힌다. 의도된 fail-safe지만 관측 근거가 생기면 재평가할 것.
- **실현손실 실배선(`record_loss`)** — 평단가 수집 경로 신설. `cost` 필드는
  `get_holdings_raw`에만 있고 `snapshot`이 담지 않는다. `roadmap.md:375`가 "`cost.commission`은
  조회 시점의 누적 상태라 저장하지 않으면 되살릴 수 없다"고 못박고 있어, 배선하려면
  `snapshot`이 `cost`를 담고 그걸 영속하는 단계가 먼저다 — 이번 크기가 아니다.

## 단계별 계획

각 단계는 앞 단계가 머지되지 않아도 진행할 수 있으나, 커밋 순서는 지켜야 한다
(특히 5-1이 5-2보다 앞).

### 1. 브랜치 생성

- 내용: `fix/execution-review` 분기. 이후 모든 커밋은 이 브랜치에 쌓는다.
- 🔴 **분기 전에 반드시 `git status --short`와 `git rev-parse --abbrev-ref HEAD`를 확인한다.**
  이 저장소는 **워킹트리를 여러 작업이 공유한다** — 브랜치는 격리 수단이 **아니다.**
  다른 세션이 브랜치를 만들면 이쪽 HEAD도 함께 움직이고, `git checkout -b`는 미커밋 변경을
  새 브랜치로 그대로 끌고 간다.
- **분기 기준점을 확인하고 시작한다.** 2026-08-16 현재 리서치 문서 재편이 `2e7038d`로
  main에 머지·푸시됐고 `feature/study-pitfalls`는 삭제됐다. HEAD = `main`, `origin/main`과 동일,
  워킹트리는 이 계획서만 미추적. **`git checkout -b fix/execution-review main`으로 바로 간다.**
- ⚠️ **다시 갈릴 때를 위한 규칙 (교훈).** HEAD가 `main`이 아닌 상태에서 `main` 기준으로 분기하면
  **워킹트리가 되감긴다** — 다른 작업이 방금 커밋한 파일이 옛 내용으로 돌아가고 **삭제한 파일이
  되살아난다.** 되감김은 **추적 파일에만** 일어나므로 내 미추적 파일이 멀쩡한 것은 안전 신호가
  아니고, 파일이 되살아나는 쪽이 사라지는 쪽보다 훨씬 알아채기 어렵다.
  분기 전에 `git rev-parse --abbrev-ref HEAD`·`git log --oneline main..HEAD`로 관계를 먼저 본다.
- 따라서 이 계획 전체에서 지킬 커밋 규칙:
  - **`git add -A`·`git add .`·`git commit -a` 금지.**
  - 커밋은 항상 경로를 명시한다 — `git commit <바꾼 파일들>`.
  - 커밋 직전 `git status --short`로 스테이징 영역에 내 것만 있는지 확인한다.
- 검증: `git rev-parse --abbrev-ref HEAD` 출력이 `fix/execution-review`.
  각 커밋 후 `git show --stat HEAD`에 **이 계획이 지목한 파일만** 나온다.

### 2. 서킷브레이커 일일 경계를 미국 거래일로 (결함 A)

- 내용: `scripts/live/rebalance.py`가 `CircuitBreaker(day=...)`에 넘기는 값을 시그널 날짜
  (`date_raw.replace("-","")`)에서 `datetime.now(US_MARKET_TZ).date()` 기반 `YYYYMMDD`로
  바꾼다. `US_MARKET_TZ`는 같은 파일 34행에 이미 있고 시그널 신선도 가드가 쓰고 있다.
  `src/execution/safety.py`는 수정하지 않되, 36행 주석의 "러너는 `rebalance_date`"를
  갱신한다.
- **스펙 반전 동반:** `tests/test_live_rebalance.py:120`의
  `test_circuit_breaker_day_comes_from_signal_date`가 현재 결함을 스펙으로 고정하고 있다.
  이 테스트를 `test_circuit_breaker_day_is_us_trading_date`로 다시 쓴다. 원 테스트
  docstring이 우려한 "정규장이 KST 자정을 넘길 때 경계가 어긋난다"는 문제의식은 그대로
  유효하며, 미국 거래일 기준이 그 우려를 로컬 날짜보다 정확히 해결한다 — 커밋 본문에 명시.
- 커밋: `fix(safety): 서킷브레이커 일일 경계를 미국 거래일로`
- 검증: `.venv/bin/python -m pytest tests/test_live_rebalance.py -q` 전량 통과,
  그중 `test_circuit_breaker_day_is_us_trading_date` 포함.

### 3. 손실 상한을 실제로 동작하게 (결함 B-1·C)

세 커밋으로 나눈다. 각각 다른 메커니즘이다.

**3-1. 당일 손실을 워터마크로 유지**

- 내용: `CircuitBreaker.observe_daily_loss`를 `self.daily_loss_usd = max(self.daily_loss_usd,
  max(0.0, usd))`로. 관리 종목을 청산하면 그 손실이 `holdings` 응답에서 사라져 다음
  실행이 0을 대입하고 영속된 손실이 지워지는 문제를 막는다.
- **스펙 반전 동반:** `tests/test_safety.py:102`의 `test_daily_loss_absolute_assignment`가
  "이익 전환 시 0"을 단언한다. `src/execution/safety.py:98-99` 주석이 그 의도를 명시했다.
  워터마크는 이 동작을 **의도적으로 포기**하는 것이다 — 장중에 손실이 회복돼도 그날은
  상한이 유지된다. 테스트를 새 스펙으로 다시 쓰고, 포기한 것과 그 이유를 주석에 남긴다.
- 커밋: `fix(safety): 당일 손실을 워터마크로 유지`
- 검증: `.venv/bin/python -m pytest tests/test_safety.py -q` 전량 통과. 신규 테스트가
  "손실 관측 → 관리 종목 청산 → 재관측 0 → `daily_loss_usd`가 유지된다"를 재현.

**3-2. 손실 상한을 매수에만 적용**

- 내용: `CircuitBreaker.guard()`가 손실 축과 주문건수 축을 분리 적용하도록 바꾼다.
  주문건수 상한은 전 주문에(폭주 방지), 손실 상한은 **매수에만**. 현재는
  `src/execution/runner.py:229-231`이 매도를 포함한 모든 주문 앞에서 `guard()`를 부르고
  `plan.orders`는 매도가 앞이라, 손실이 상한을 넘으면 첫 매도에서 트립해 **청산이 불가능**해진다.
- 호출 측도 함께 바꾼다 — `guard()`가 어느 축을 적용할지 알려면 주문의 `side`가 필요하다.
  러너의 `self.cb.guard()`를 `self.cb.guard(side=order.side)`로 넘긴다.
- **`side`에 기본값을 두지 않는다.** 기본값을 `"BUY"`로 두면 인자를 빠뜨린 호출이 매도 주문을
  매수로 취급해 **정확히 이 커밋이 고치려는 버그로 되돌아간다.** 안전한 기본값이 존재하지 않는
  자리이므로 필수 인자가 맞다.
- ⚠️ **수정 규모:** 무인자 `guard()` 호출이 **14곳**이라 전부 고쳐야 한다.
  `tests/test_safety.py` 25·26·28·33·36·46·51·62·71·98·119·122행(12곳),
  `tests/test_runner.py:343`(1곳), `src/execution/safety.py:26`의 docstring 사용 예(1곳).
  구현 자체는 3~5줄이지만 커밋 전체는 이보다 크다 — 견적할 때 감안할 것.
  각 테스트가 어느 축을 검증하는지 `side=`로 드러나므로 결과적으로 스펙이 더 읽힌다.
- 커밋: `fix(safety): 손실 상한을 매수에만 적용`
- 검증: `.venv/bin/python -m pytest tests/test_safety.py tests/test_runner.py -q` 전량 통과.
  신규 테스트가 "손실 상한 초과 상태에서 매도는 나가고 매수는 막힌다"를 재현.

**3-3. 일일 손실 상한 기본값 조정**

- 내용: `scripts/live/rebalance.py`의 `--max-loss` 기본값 700.0 → 70.0.
  기존값은 `--budget` 기본값과 같아 포트폴리오 전액이 하루에 사라져야 트립했다.
  70.0은 `--budget` 기본값 700.0의 10%다.
- ⚠️ **두 기본값의 커플링은 코드에 없다.** 사용자가 `--budget 2000`으로 올리면 70은 3.5%가
  되고 `--budget 300`으로 내리면 23%가 된다. 자동 연동은 넣지 않는다(근거 없는 유연성) —
  대신 `--max-loss`의 help 문자열에 **"기본값은 `--budget` 기본값의 10%. 예산을 바꾸면 함께
  조정할 것"** 을 명시해 사용 시점에 보이게 한다.
- 커밋: `fix(live): 일일 손실 상한 기본값을 예산의 10%로`
- 검증: `.venv/bin/python scripts/live/rebalance.py --help` 출력에 `default: 70.0` 반영.
  `.venv/bin/python -m pytest tests/test_live_rebalance.py -q` 통과.

### 4. 매도 경로 정합 (결함 D·E·F)

**순서가 중요하다** — 4-2(E)를 고치면 부분매도 잔량이 M에 남아 다음 사이클에 잔량 exit
주문이 나가므로, 4-1(D)이 노출되는 빈도가 **의도적으로 늘어난다.** 4-1을 먼저 넣는다.

**4-1. 주문 수량 문자열 지수표기 제거**

- 내용: `TossBroker.place`의 `f"{intent.value}"`를 십진 고정 포맷으로. 1e-4 미만 float이
  `'3e-05'`처럼 렌더돼 API에 나가는 것을 막는다(`f"{3e-05}"` → `'3e-05'` 확인됨).
  `orderAmount`·`quantity` 양쪽에 적용.
- 커밋: `fix(toss): 주문 수량 문자열 지수표기 제거`
- 검증: `.venv/bin/python -m pytest tests/test_broker.py -q` 전량 통과. 신규 테스트가
  `place(OrderIntent(value=3e-05, ...))` 호출 후 `posted` body의 `quantity`에 `e`가
  포함되지 않음을 단언.

**4-2. 부분매도 exit이 관리셋에서 빠지지 않게**

- 내용: `RebalanceRunner._clamp_sells_to_sellable`이 수량을 줄일 때 `reason`을 `"exit"`에서
  구분되는 값(예: `"exit_partial"`)으로 바꾼다. `ManagedState.update_after_place`는
  `"exit"`만 M에서 discard하도록 유지. 전량 청산이 아닌데 M에서 빠져 잔여 포지션이
  영구히 관리 밖으로 나가고, 동시에 `bot_value`가 줄어 예산이 과대 산출되는 문제를 막는다.
- `src/execution/interface.py:37-38`의 `skipped` 사유 목록 주석과
  `src/execution/managed.py:71-72`의 한계 주석을 새 상태에 맞게 갱신한다.
  **체결 시점 부분체결(시장가 미전량체결)은 여전히 미해결이며 그 사실을 주석에 남긴다.**
- 대시보드 표시 사전도 함께 채운다. `scripts/dashboard/app.py:70`의
  `ORDER_REASON = {"exit": "청산", "trim": "축소", "enter": "신규", "add": "추가"}`에
  `"exit_partial"`이 없어 화면에 원문이 그대로 뜬다. 같은 파일 71-76행의 `SKIP_REASON`에도
  러너가 실제로 내는 `not_sellable_settlement`·`sell_clamped_to_sellable`가 빠져 있다
  (기존 누락 — 이번 변경으로 생긴 것이 아니다). 세 항목을 한 번에 넣는다.
  `.get(r, r)` 폴백이 있어 파손은 아니지만, 사유 코드가 화면에 노출되면 읽는 사람이 판단을 못 한다.
- 커밋: `fix(execution): 부분매도 exit이 관리셋에서 빠지지 않게`
- 검증: `.venv/bin/python -m pytest tests/test_runner.py tests/test_managed.py -q` 전량 통과.
  신규 테스트가 "holdings 5.0 · sellable 3.0 · 목표에서 편출 → 발주 후 M에 심볼이 남는다"를 재현.

**4-3. 매도가능수량 미상을 0으로 접지 않게**

- 내용: `TossBroker.get_sellable_quantity`가 응답 형태가 예상 밖이거나 `sellableQuantity`가
  없을 때 `0.0` 대신 `None`을 반환하고, `get_sellable`이 그 심볼을 결과 dict에서 제외한다.
  그러면 `RebalanceRunner._clamp_sells_to_sellable`의 기존 `unreported` 가드가 비로소
  발동한다 — 지금은 어댑터가 모든 키를 채우므로 그 가드가 절대 트립하지 않는다.
  러너는 수정하지 않는다.
- **스펙 반전 동반:** `tests/test_broker.py:108`이 `== 0.0`("알 수 없으면 보수적 0")을
  단언한다. 매수 경로(`get_buying_power_usd`)에서 0은 보수적이지만 매도 경로에서 0은
  "청산 실패"라 위험하다 — 방향이 반대라는 근거를 주석과 커밋 본문에 남긴다.
- 커밋: `fix(toss): 매도가능수량 미상을 0으로 접지 않게`
- 검증: `.venv/bin/python -m pytest tests/test_broker.py tests/test_runner.py -q` 전량 통과.
  신규 테스트가 "`sellable-quantity`가 `{"result": {}}`를 주면 러너가 `ExecutionError`로
  중단한다"를 재현(어댑터부터 러너까지 관통).

### 5. 주문로그 신뢰성 (결함 G + 원자적 쓰기 + dry-run 분리)

**5-1. 예외 경로에서도 주문로그를 남긴다**

- 내용: `RebalanceRunner.run`의 `try/finally`가 지금은 상태 영속만 감싼다. `RunResult`
  구성과 `write_order_log`가 try 밖이라, 루프 중간에 `CircuitBreakerTripped`·
  `BrokerRateLimited`·미분류 `TossApiError`가 나면 **이미 발주된 주문의 기록이 통째로
  사라진다.** 로그 기록까지 예외 안전하게 만든다.
  같은 커밋에서 `market_closed` 조기 반환에 `snapshot=self._snapshot`을 넘기고 로그도 남긴다.
- **구현 주의 3가지:**
  - `_collect_fills`를 예외 경로에서 부르지 않는다. 장마감·rate-limit 소진 상황에서
    추가 API 호출이 또 실패한다. 예외 경로는 `fills=[]`로 로그만 남긴다.
  - 로그 쓰기 자체를 별도 `try/except`로 감싼다. `finally` 안의 예외가 원 예외를 가리면
    CLI 메시지가 뒤바뀐다.
  - 원 예외는 반드시 재전파한다. 로그를 남겼다고 삼키지 않는다.
- 커밋: `fix(execution): 예외 경로에서도 주문로그를 남긴다`
- **이 커밋이 저장소 최초로 `orderlog.py`를 실행 검증한다.** 현재 `log_dir`을 넘기는 테스트가
  0건이고(`grep -rn "log_dir\|write_order_log" tests/` 무결과), `test_runner.py:67`의 `_runner`
  헬퍼가 `log_dir`을 지원하지 않는다. 헬퍼에 `log_dir` 전달 경로를 먼저 뚫어야 한다.
  즉 `write_order_log`의 직렬화 경로는 지금까지 한 번도 실행된 적이 없다 — 이 커밋 전에는
  `json.dumps`가 비직렬화 타입에서 죽어도 전 스위트가 통과한다.
- 같은 커밋에서 오해를 부르는 테스트 이름을 정리한다. `tests/test_runner.py:410`의
  `test_settlement_date_reaches_order_log`는 이름과 달리 주문로그를 건드리지 않고
  메모리상 `RunResult.fills`만 단언한다. 실제 로그 파일 단언으로 승격한다.
- 함께 정리할 테스트 더블 문제 2가지(같은 테스트에서 유입됐다):
  - `WithSettlement.get_fill`(`test_runner.py:412-413`)이 베이스 `MockBroker`의
    "미발주 주문 → `None`" 가드(`:59-64`)를 버리고 `order_id`를 무시한다.
  - 베이스는 `Fill(filled_quantity="1", ...)` 문자열, 오버라이드는 `1.0` float로
    dataclass 선언(`float | None`)과 서로 다르다. 슬리피지 계산 테스트를 나중에 쓸 때
    어느 규약을 잡느냐에 따라 `str - float` TypeError가 나거나 안 난다.
  - 조치: 서브클래스를 없애고 베이스 `MockBroker.get_fill`에 `settlement_date` 인자를
    추가한다. 기존 `test_fills_captured_with_order_id`(`:228`)가 그대로 커버한다.
- 검증: `.venv/bin/python -m pytest tests/test_runner.py -q` 전량 통과. 신규 테스트 2건 —
  ① "3건 발주 후 서킷브레이커 트립 → 예외가 전파되면서도 로그 파일에 3건이 남는다",
  ② "`market_closed` 반환에 `snapshot`이 있고 로그 파일이 생성된다".
  그리고 `test_settlement_date_reaches_order_log`가 실제 파일을 읽어 단언한다.

**5-2. 원자적 쓰기 + dry-run 로그 분리**

- 내용: `write_order_log`의 `path.write_text`를 `src/execution/atomic.py`의
  `write_text_atomic`으로 교체한다(형제 상태파일 `managed.py:57`·`safety.py:73`이 이미 쓴다).
  동시에 `result.dry_run`이 참이면 파일명을 `rebalance_<date>.dryrun.json`으로 분리한다 —
  `scripts/model_backtest/dry_run_rebalance.py:81`과 실발주 러너가 지금 같은 경로에 써서
  실발주 원장이 계획 문서로 덮어써진다.
- 대시보드는 수정하지 않는다. `scripts/dashboard/app.py:358`의 `glob("rebalance_*.json")`이
  두 이름을 모두 잡고, 라벨은 파일명이 아니라 파일 내용의 `d['date']`·`d['dry_run']`에서
  나온다(`app.py:360-362`).
- ⚠️ **`scripts/model_backtest/dry_run_rebalance.py`에는 테스트가 없다.** 이 변경으로 그
  스크립트의 출력 경로가 `.dryrun.json`으로 바뀌는데 자동 검증이 없다. 8단계 `make test`도
  잡지 못한다. → 커밋 후 `.venv/bin/python scripts/model_backtest/dry_run_rebalance.py`를
  한 번 돌려 새 경로에 파일이 생기는지 눈으로 확인한다. (실 API를 안 쓰는 오프라인 데모라
  비용이 없다.)
- 커밋: `fix(execution): 주문로그 원자적 쓰기 + dry-run 로그 분리`
- 같은 커밋에서 `orderlog.py:29`의 거짓 주석을 정정한다. 현재
  `"fills": list(result.fills),   # 체결 실측 — 슬리피지·실효 수수료의 출처`라고 적혀 있는데
  **실효 수수료의 출처가 아니다** — `Fill.commission`은 `execution.commission`에서 오고
  그 값은 실측상 항상 0이다(`roadmap.md:164`: "주문 응답의 `commission`은 38건 전부 `0`이다.
  실제 값은 holdings의 `cost.commission`(0.13%)에만 있다"). 슬리피지 출처인 것은 맞으므로
  수수료 부분만 걷어내고 실제 출처를 가리킨다. `Fill.commission`·`Fill.tax` 필드 주석에도
  같은 사실을 남긴다.
- ⚠️ 이 테스트는 **`write_order_log`를 직접 호출**해야 한다. `runner.run(dry_run=True)`는
  로그를 쓰지 않으므로(`runner.py:204-206`에서 조기 반환) 러너를 통해서는 dry-run 분기에
  도달할 수 없다. 실제 dry-run 로그 생산자는 `scripts/model_backtest/dry_run_rebalance.py:81`의
  직접 호출이고, 접미사 분리를 `write_order_log` 안에 두는 이유가 그것이다.
- 검증: `.venv/bin/python -m pytest tests/test_runner.py -q` 통과.
  신규 테스트가 `write_order_log`를 `dry_run=True`/`False` 두 `RunResult`로 각각 호출해
  `.dryrun.json`과 `.json`이 따로 생기고 서로 덮어쓰지 않음을 단언.
  원자적 쓰기 자체는 테스트하지 않는다(결정 사항).

### 6. 인증·부수 (결함 H)

- 내용: 세 가지를 한 커밋에 묶는다. 모두 `src/toss` 안이고 각각 3줄 이하다.
  - `TossClient.request`의 401 재시도가 `get_token(force_refresh=True)` 반환값을 버리고
    캐시를 다시 읽는다. `TokenManager.get_token`은 `expires_in > 0`일 때만 캐시를 쓰므로
    (`auth.py:109`), 응답에 `expires_in`이 없거나 0이면 **거부된 옛 토큰을 재전송**하고
    401 복구가 영구 불능이 된다. 반환된 토큰을 그대로 쓰도록 고친다.
  - `TokenManager._write_cache`가 `write_text`로 파일을 만든 뒤 `chmod(0o600)`한다.
    그 사이 토큰이 노출되고, 두 줄 사이에서 죽으면 0644로 영구히 남는다.
    `os.open(..., O_CREAT|O_WRONLY|O_TRUNC, 0o600)`으로 바꾼다.
  - `TossBroker.place`의 반환 어노테이션이 `dict`인데 실제로는 `str`을 돌려준다.
    `Broker` Protocol(`interface.py:121`)은 `str`로 맞다. 어노테이션만 고친다.
- 커밋: `fix(toss): 401 재발급 토큰 폐기·캐시 권한 경합·place 반환형`
- 검증: `.venv/bin/python -m pytest tests/test_toss.py tests/test_broker.py -q` 전량 통과.
  신규 테스트 2건 — ① "`expires_in=0`을 주는 토큰 발급 mock에서 401 재시도가 **새** 토큰을
  보낸다", ② "캐시 파일 모드가 `0o600`이다". 어노테이션은 테스트하지 않는다(결정 사항).

### 7. roadmap 정정

- 내용: `docs/project/roadmap.md`의 두 항목에 조치 이력을 덧붙인다. **✅는 취소하지 않는다** —
  구현 자체는 있었고 결함이 있었을 뿐이다.
  - **302행** "[개선11] invalid-token 재시도 ✅(2026-07-20 구현, mock 검증)" → 재발급 토큰
    폐기 결함이 있었고 2026-08-16 조치했음을 추가.
  - **376행** "✅ E10 서킷브레이커 파일영속" → 일일 경계·손실 축·청산 차단 3건을 조치했음을 추가.
    (이 두 행은 `2e7038d`가 269줄을 삽입하면서 각각 1행씩 밀렸다. 착수 시 `grep -n`으로
    재확인할 것 — 행 번호를 문서에 박아두면 반드시 낡는다.)
  - 이 계획서로 가는 링크를 두 곳에 남긴다.
- 같은 커밋에서 `roadmap.md`의 낡은 사실 2건을 정정한다.
  - **184행 "아직 브로커 래퍼가 없는 엔드포인트의 실측 스키마"** — `GET /api/v1/orders/{orderId}`
    래퍼는 이미 있다(`src/toss/broker.py:244` `get_order`, `:287` `get_fill`).
    200-201행의 "정밀화하려면 위 GET 래퍼부터 추가해야 한다"도 같이 갱신한다.
    이 블록이 `settlementDate`를 "실측 스키마"로 보이게 하는데 그 필드는 미관측이다(리스크 참조).
  - **182행 `[tests/test_broker.py](tests/test_broker.py)` 링크가 깨져 있다** —
    `docs/project/` 기준이라 `docs/project/tests/...`로 해석된다. `../../tests/test_broker.py`로
    고친다. 같은 표의 다른 링크는 전부 `../../` 형식이다.
- ✅ **선행조건 해소됨 (2026-08-16).** 리서치 문서 재편이 `2e7038d`로 커밋돼
  `roadmap.md`에 미커밋 변경이 없다. **위 행 번호는 `2e7038d` 이후 기준이다** — 그보다 앞선
  커밋에서 분기하면 어긋나므로 1단계의 기준점 선택과 함께 봐야 한다.
- ⚠️ **다시 겹치면 지킬 규칙 (교훈으로 남긴다).** 같은 파일을 다른 작업이 동시에 편집 중이면:
  - **편집 자체는 안전하다.** Edit 도구는 디스크 현재 내용에 문자열 치환을 하므로 상대 변경을
    덮어쓰지 않고, 편집 지점이 떨어져 있으면 충돌도 없다.
  - 🔴 **위험한 것은 커밋 범위다.** `git add <path>`는 그 파일의 **모든** 변경을 담으므로
    **경로를 명시해도 상대 변경이 함께 딸려 들어간다.** 파일 단위 아래로는 못 좁힌다.
    `git add -p`는 이 환경에서 대화형 플래그가 지원되지 않아 대안이 못 된다.
  - **회피법은 순서다** — 먼저 커밋하는 쪽이 자기 파일만 경로로 스테이징해 즉시 커밋하면
    뒤에 오는 쪽이 깨끗한 상태에서 시작한다. 이번에 실제로 그렇게 갈랐다.
  - 그때까지는 편집만 해 두거나 이 단계를 뒤로 돌린다. 7단계는 문서 전용이라
    8·9단계보다 뒤로 가도 무방하다.
  - `git add -A`는 이 계획 어디서도 쓰지 않는다(워킹트리를 여러 작업이 공유한다).
- 커밋: `docs(roadmap): 코드리뷰 조치 반영`
- 검증: `grep -n "execution-review-fixes" docs/project/roadmap.md`가 2행 이상 출력.
  `grep -n "아직 브로커 래퍼가 없는" docs/project/roadmap.md`가 무결과.
  `grep -n "](tests/test_broker.py)" docs/project/roadmap.md`가 무결과.

### 8. 전체 테스트

- 내용: 브랜치 전체에서 회귀가 없는지 확인한다.
- 검증: `make test`가 실패 0으로 종료(`.venv/bin/python -m pytest tests/ -q`).

### 9. 실계좌 dry-run 검증

- 내용: `.venv/bin/python scripts/live/rebalance.py` — `--confirm` **없이** 실행한다.
  dry-run은 `snapshot`(holdings·prices·buying-power)과 `get_sellable`을 실제로 호출하고
  발주만 하지 않으므로, 주문 위험 0으로 어댑터 파싱 경로를 실 응답에 대볼 수 있다.
  조치 8건 중 4건(D·E·F·H-1)이 실 응답 형태에 대한 판단이라 mock만으로는 검증되지 않는다.
- 관찰해서 아래 "dry-run 관찰 기록"에 적을 것 3가지:
  - 실 `sellable-quantity` 응답이 `sellableQuantity`를 담는가 (4-3의 전제 확인)
  - 보유 수량 중 1e-4 미만이 있는가 (4-1의 노출 빈도, 그리고 제외한 dust 하한의 판단 근거)
  - `dailyProfitLoss.amount`의 크기가 USD 단위로 그럴듯한가 (3-3의 임계값 70 타당성)
- ⚠️ **이 문서는 git 추적 대상이다.** 관찰 결과는 **예/아니오와 자릿수만** 적는다.
  종목 심볼·보유 수량·잔액·계좌번호를 쓰지 않는다. 계좌 고유값이 필요하면
  `docs/findings/`에 두고 여기서는 참조만 한다(CLAUDE.md 문서 위치 규칙).
- **dry-run은 파일을 하나도 남기지 않는다.** `run()`이 `runner.py:204-206`에서 반환하고
  `write_order_log`는 `:255-256`이라, `scripts/live/rebalance.py`가 `log_dir`을 넘겨도
  dry-run 경로에서는 무효다. `execution_logs/rebalance_20260716.json`이 존재하는 것은
  `scripts/model_backtest/dry_run_rebalance.py:81`이 `write_order_log`를 **직접** 부르기
  때문이지 러너를 통해서가 아니다. 이 계획은 그 동작을 바꾸지 않는다(5-2 참조 — 접미사 분리는
  `write_order_log` 안에서 하므로 직접 호출 경로에 그대로 적용된다).
- **상태 파일도 건드리지 않는다.** bootstrap은 `runner.py:70`의 `if not dry_run` 가드 뒤에
  있고, `observe_daily_loss`·`update_after_place`·`state.save()`는 전부 205행 조기 반환
  뒤에 있다. 즉 `managed_state.json`·`circuit_breaker.json`은 dry-run으로 오염되지 않는다.
- 검증: **결과가 셋 중 하나다. 어느 쪽인지 판정해 기록한다.**
  - **정상 완주** — exit 0으로 종료하고 stdout에 `DRY-RUN 발주계획` 블록이 출력된다.
    (파일 생성은 검증 대상이 아니다 — 위 참조)
  - **`매도가능수량 미조회` 중단** — `ExecutionError`가 CLI에서 `SystemExit`으로 바뀌므로
    traceback 없이 그 메시지만 나온다. 이는 **실패가 아니라 4-3의 미관측 가정이 확인된 것**이다.
    관찰 기록에 남기고, 원인 조사는 별건으로 뺀다. 나머지 완료 기준은 그대로 충족된 것으로 본다.
  - **그 밖의 예외** — 진짜 실패다. 원인을 잡기 전에는 10단계로 넘어가지 않는다.

#### dry-run 관찰 기록 (2026-08-16 실행)

| 관찰 항목 | 결과 | 후속 판단 |
|---|---|---|
| 실행 결과 | **정상 완주** (exit 0, traceback 없음) | — |
| `sellable-quantity` 응답에 `sellableQuantity`가 있는가 | **관찰 불가** | Phase 6로 이관 |
| 보유 수량에 1e-4 미만이 있는가 | **관찰 불가** | Phase 6로 이관 |
| `dailyProfitLoss.amount`가 USD 자릿수인가 | **관찰 불가** | Phase 6로 이관 |

**확인된 것** — 읽기 경로가 실 응답으로 무예외 완주했다. `holdings`·`prices`·`buying-power`
파싱, 화이트리스트 필터, `compute_rebalance`, 최소금액·이월 처리까지 실 데이터로 돌았다.
설계대로 **파일을 하나도 남기지 않았다** — 주문로그도, `managed_state.json`·
`circuit_breaker.json`도 생성되지 않았음을 확인했다.

**⚠️ 9단계 설계의 한계가 드러났다 — 3항목이 관찰 불가였다.** 이유는 두 가지다.

- `managed_state.json`이 없어 관리셋 M이 비었다 → `bot_holdings`가 비어 **매도 대상이 0건** →
  `get_sellable`이 아예 호출되지 않는다. sellable 응답도, 보유 수량 분포도 볼 수 없다.
  (dry-run은 bootstrap을 하지 않으므로 이 상태가 계속된다.)
- `observe_daily_loss`는 `run()`의 **실발주 전용 경로**에 있다. dry-run은 그 앞에서 반환하므로
  `dailyProfitLoss`가 소비되지 않는다.

즉 **dry-run으로 검증 가능한 것은 읽기·계산 경로까지이고, 매도 게이트와 손실 축은 첫 실발주
전까지 실 응답으로 확인할 수 없다.** 세 항목을 아래 "Phase 6 관찰 항목"으로 옮긴다.

**운영 메모** — 실행 시점에 USD 가용액이 부족해 목표 대부분이 `insufficient_buying_power`로
스킵됐다. 스모크 전에 KRW→USD 환전이 선행돼야 한다(진입점 docstring의 "USD 선환전 필수").
구체 수치는 이 문서에 적지 않는다 — git 추적 대상이다.

### 10. PR

- 내용: `fix/execution-review` → `main` PR 생성. 본문에 결함 8건의 재현 시나리오와
  스펙 반전 3건(2단계·3-1·4-3)을 명시한다. **푸시와 PR 생성은 사용자 확인 후 진행한다.**
- 검증: `gh pr view --json state`가 `OPEN`.

## 리스크

- **스펙 반전 3건이 기존 테스트를 다시 쓰게 한다** (2단계 `test_circuit_breaker_day_comes_from_signal_date`,
  3-1 `test_daily_loss_absolute_assignment`, 4-3 `tests/test_broker.py:108`).
  → 통과시키려는 변경과 구분되지 않으면 나중에 되돌려진다. **대응:** 세 곳 모두 커밋 본문에
  "왜 종전 스펙이 틀렸는가"를 적고, 새 테스트 docstring에 근거를 남긴다.
  리뷰어에게 이 3건을 PR 본문에서 먼저 지목한다.

- **4-3의 트리거가 미관측이다.** "토스가 200과 함께 `sellableQuantity`를 빠뜨릴 수 있다"는
  가정 위에 서 있고, 실 응답으로 확인한 적이 없다. → **대응:** 가정이 틀려도 조치는 옳다
  (발동할 수 없는 가드는 제거하거나 살리거나 둘 중 하나여야 한다). 9단계 dry-run에서
  실 응답을 관찰해 기록한다.

- **3-1 워터마크가 장중 회복 시 상한을 해제하지 않는다.** `--max-loss 70`에서는 10% 드로다운
  한 번으로 그날 매수가 잠긴다. → **대응:** 이는 의도된 대가이며 3-2(매도는 계속 가능)가
  최악을 막는다. Phase 6 스모크에서 실제 트립 빈도를 관찰하고, 잦으면 임계값을 재조정한다.

- **5-1이 유일하게 구조를 건드린다.** `finally` 안의 예외가 원 예외를 가리거나,
  예외 경로의 추가 API 호출이 또 실패할 수 있다. → **대응:** 5-1의 구현 주의 3가지를
  체크리스트로 쓰고, 이 커밋만 따로 리뷰받는다.

- **4-2가 dust 주문 빈도를 의도적으로 올린다.** 부분매도 잔량이 M에 남아 다음 사이클에
  잔량 exit이 나간다. → **대응:** 4-1을 4-2보다 먼저 커밋한다. 9단계에서 잔량 분포를
  관찰해 dust 하한 도입 여부를 판단한다.

- **`settlementDate` 필드명이 실응답으로 검증된 적 없다.** `src/toss/broker.py:307`이 읽는
  이름의 유일한 근거는 `roadmap.md:184`의 "아직 래퍼가 없는 엔드포인트" 블록이고, 저장소 안
  다른 출처가 없다. 틀렸다면 모든 `fills` 행에 `settlement_date: null`이 조용히 쌓이는데,
  `interface.py:103-106` 주석이 스스로 "세법상 양도시기·환율기준일의 근거"라 선언한 값이다.
  `tests/test_broker.py:401`의 `test_get_fill_settlement_date_absent_is_none`이 그 무음 `None`을
  스펙으로 고정한다. → **대응:** dry-run은 발주가 없어 `get_fill`을 호출하지 않으므로
  9단계로는 확인할 수 없다. 아래 "Phase 6 관찰 항목"으로 등록한다. 코드는 지금 고치지 않는다.

- **`settlement_date`만 검증 없이 원시 통과한다.** `get_fill`의 다른 필드는 전부 `_num`/`_opt_num`을
  지나는데 이 하나만 `ex.get("settlementDate")` 그대로다. `broker.py` 모듈 docstring이 선언한
  fail-fast 파싱 정책과 `Fill.settlement_date: str | None` 어노테이션을 동시에 어긴다.
  같은 `execution` 객체의 `filledAt`이 `"2026-07-20T22:31:00.000+09:00"` 포맷이라
  `settlementDate`도 datetime일 수 있다. → **대응:** 실제 포맷을 모르는 채 정규화하면 추측
  코드가 된다. Phase 6에서 실응답을 본 뒤 정규화 형태를 정한다. 그때 `interface.py:103-105`와
  `tests/test_broker.py:390-394`에 near-verbatim으로 중복된 T+1/T+2 근거 설명도 한쪽으로 합친다.

- **`Fill.commission`·`Fill.tax`는 구조적으로 항상 0이다.** `execution.commission`에서 읽는데
  `roadmap.md:164`가 "주문 응답의 `commission`은 38건 전부 `0`"이라고 실측으로 확정했다
  (n=38). 실제 값은 holdings의 `cost.commission`(0.13%)에만 있다. → **대응:** 필드 자체는
  API가 주는 값이므로 그대로 둔다. 5-2에서 `orderlog.py:29`의 "실효 수수료의 출처" 주석만
  정정한다. **주문로그만 보고 실효 비용을 계산하면 수수료를 0으로 착각한다** — Phase 5.5
  집행 캘리브레이션이 이 원장을 입력으로 쓸 때 반드시 holdings 스냅샷을 함께 봐야 한다.

- **9단계가 실 계좌 자격증명에 의존한다.** `.env`의 `TOSS_ACCOUNT`가 없으면
  `load_config(require_account=True)`가 `TossConfigError`로 중단한다.
  → **대응:** 9단계 실패 시 8단계까지를 부분 완료로 기록하고, 자격증명 확보 후 9단계만
  재실행한다. 8단계까지의 커밋은 되돌리지 않는다.

## 완료 기준

아래가 모두 참일 때 이 계획을 완료로 본다.

1. `make test`가 실패 0으로 종료한다.
2. 재현 테스트 **11건**이 존재하고 통과한다 — 2단계 1건(재작성), 3-1 1건(재작성),
   3-2 1건, 4-1 1건, 4-2 1건, 4-3 1건(+ `tests/test_broker.py:108` 재작성),
   5-1 2건, 5-2 1건, 6단계 2건.
   추가로 5-1이 기존 테스트 2건을 정리한다 — `test_settlement_date_reaches_order_log` 승격,
   `WithSettlement` 서브클래스 제거 후 `MockBroker`로 병합.
3. `scripts/live/rebalance.py`를 `--confirm` 없이 실행해 9단계의 세 결과 중 **"정상 완주"
   또는 "`매도가능수량 미조회` 중단"** 으로 끝난다. (dry-run은 파일을 남기지 않으므로
   파일 생성은 판정 대상이 아니다.)
4. 9단계 판정 결과와 관찰 가능 여부가 "dry-run 관찰 기록"에 적혀 있다.
   (관찰 불가로 판명된 항목은 "Phase 6 관찰 항목"으로 이관돼 있어야 한다.)
5. `fix/execution-review` PR이 열려 있고 본문에 스펙 반전 3건이 명시돼 있다.
6. `docs/project/roadmap.md`의 두 항목에 조치 이력과 이 문서 링크가 있다.

**완료 후에도 남는 것:** 명시적 제외 7건. 그중 실현손실 실배선과 intent WAL은 Phase 6
스모크 전에 다시 판단할 가치가 있다.

## Phase 6 관찰 항목

dry-run으로는 확인할 수 없어 첫 실발주(Phase 6 스모크)로 넘긴 것들이다. Phase 6 착수 시
이 목록을 체크리스트로 쓴다. 여기서도 **계좌 고유값은 적지 않는다**(git 추적 문서).

| 관찰 항목 | 왜 필요한가 | 결과에 따른 조치 |
|---|---|---|
| `sellable-quantity` 응답에 `sellableQuantity`가 있는가 | 4-3의 전제. dry-run에서는 매도 대상이 0건이라 호출조차 안 됐다 | 없으면 4-3의 가드가 실제로 발동한다 — 원인 조사는 별건 |
| 보유 수량에 1e-4 미만(dust)이 있는가 | 4-1의 노출 빈도이자, 제외한 dust 하한의 판단 근거 | 있으면 exit 최소수량 하한 도입을 재평가 |
| `dailyProfitLoss.amount`가 USD 자릿수인가 | `observe_daily_loss`가 실발주 경로에만 있어 dry-run으로는 못 본다 | 아니면 `--max-loss 70`을 즉시 재산정 |
| `execution.settlementDate` 필드명이 실제로 오는가 | `broker.py`의 유일 근거가 roadmap Phase 0 스키마 블록뿐 | 안 오면 실제 필드명으로 교체 + `test_get_fill_settlement_date_absent_is_none` 재작성 |
| `settlementDate` 값의 포맷(날짜만 / ISO datetime / 정수) | 유일하게 검증 없이 통과하는 필드 | 포맷 확정 후 `_num`/`_opt_num`에 준하는 정규화 도입 |
| 실 결제일이 T+1인가 T+2인가 | `interface.py:103-106`이 미결로 남긴 판단 | 확정 후 `interface.py`와 `test_broker.py`의 중복 근거 설명을 한쪽으로 합침 |
| 동일 `clientOrderId` 재발주 응답이 신규/기존을 구분해 주는가 | 명시적 제외한 "주문 카운터 이중계상"의 전제 | 구분되면 `record_order` 조건부화, 아니면 제외 유지 |
| 1회 리밸의 실제 주문 건수 | `--max-orders 60`을 근거 없이 유지 중 | 상한 재산정 |
| 손실 상한 트립 빈도 | `--max-loss 70` + 워터마크의 실제 영향 | 잦으면 임계값 재조정 |
