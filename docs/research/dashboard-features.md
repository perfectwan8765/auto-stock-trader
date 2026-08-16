# 앱 기능 확장 리서치 — 외부 사례·표준 조사

> 조사일: 2026-08-09. 목적: 현재 읽기전용 Streamlit 대시보드([scripts/dashboard/app.py](../../scripts/dashboard/app.py), 417줄, 탭 2개)를
> 실운영 애플리케이션으로 확장하기 위한 **기능 후보의 외부 근거** 확보.
>
> **1차 조사** (§1~§7): 4개 각도 — ① 오픈소스/인디 트레이딩 앱 ② 기관 트레이딩 운영 표준
> ③ 한국 거주자 미국주식 세무·환전·결제 ④ 퀀트 리서치 워크벤치·라이브 모니터링. → "무엇을 만들 수 있나"
>
> **2차 조사** (§8~§10): 2개 각도 — ⑤ 실제 라이브 운용자의 1인칭 실패 기록 ⑥ go-live 최소요건·범위 규율.
> → "무엇을 **먼저** 만들어야 하나". **1차 조사의 결론 일부를 반박했다.**
>
> **이 문서는 근거 기록이다. 기능 확정·우선순위는 별도 기획 문서에서 한다.**
>
> ### 정정 이력
> - **2026-08-09 (2차 조사 반영):** §1의 "포착 시한 데이터 7개" 주장을 **3~4개로 축소 정정**.
>   `settlement_date`와 FX 환율은 사후 회수 가능하므로 회복불가 논거로 정당화할 수 없다. §1·§9-3 참조.
> - **2026-08-09:** §2-4(preflight 인간 승인)에 **반대 근거** 추가. §8-4 참조.
> - **2026-08-09 (전제 정정):** §9-5(3)·§10의 UI 유예 권고는 *"앱은 전략에 종속된 부차적 목표"* 라는
>   **암묵 가정 위에 서 있었다.** 사용자가 **앱 자체를 1급 목표로 확정**함에 따라 해당 가정은 무효.
>   조사 결과 어디에도 "Streamlit을 유지하라"는 근거는 없으며, 오히려 §7의 수렴 신호는
>   **core API + 얇은 클라이언트**를 가리킨다. 뷰 스택은 자유롭게 선택한다. §7·§9-5·§10 수정 반영.
>
> 관련: [qlib-toss.md](../project/roadmap.md)(전체 계획 + §Phase 0 실측 상수) · [ledger-design.md](../project/ledger.md)(원장 설계)

---

## 0. 요약

내부 문서만으로 뽑은 기능 맵은 "이미 아는 빈틈"에 갇힌다. 외부 조사로 드러난 것.

**1차 조사에서:**
1. **포착 시한이 있는 데이터가 있다** — 라이브 첫 주문 이후 소급 복원 불가. 기능보다 이게 먼저다. → §1
2. **기존 문서 10곳이 정정·보강 대상이다.** 스키마 누락 3건, 운영 제약 2건, 분석 오류 2건 등. → §2
3. **서로 다른 도메인의 조사가 같은 결론에 수렴한 기능이 8개 있다.** 수렴 = 강한 설계 신호. → §3
4. 아키텍처 신호: Hummingbot이 Streamlit 대시보드를 deprecated 처리하고
   **core API + 얇은 클라이언트** 구조로 재편. 417줄을 키우기 전에 로직 분리가 선행돼야 한다. → §7

**2차 조사가 이를 수정했다:**

5. **포착 시한 주장은 과장이었다.** 진짜 회복불가는 3~4개이고 **전부 JSONL 한 줄에 들어간다.**
   원장 스키마 대공사·정식 상태기계·섀도 서브시스템으로 확장한 것은 근거를 넘어선 확장이다. → §9-3
6. **1인칭 사고 빈도로는 "주문 전 입력 검증"이 "주문 후 대사"보다 잦다.**
   1차 조사가 뽑은 항목 전부가 *주문을 낸 뒤*에 집중돼 있어 이쪽이 통째로 비었다. → §8-3
7. **라이브 성과로는 엣지를 검증할 수 없다.** Lo(2002) 기준 SR=0.5를 t=2로 확인하려면 **약 16년**.
   주간 리밸런싱 1년 = 52관측. **모니터링 도구군 전체가 측정 불가능한 것을 측정한다.** → §9-4
8. **과잉 엔지니어링 위험 8/10.** 후보 32개 중 **수익을 개선하는 항목이 0개**다. → §9-5

**결론: 라이브 전에 필요한 것은 13개이고 나머지는 라이브 데이터를 보고 재선정한다.** → §10

---

## 1. 포착 시한이 있는 데이터 ⚠️ 2차 조사로 정정됨

> **정정 요지:** 1차 조사는 회복불가 항목을 7개로 봤다. **2차 조사 결과 실제로는 3~4개이며,
> 전부 append-only 이벤트 로그(JSONL) 한 줄에 들어간다.** 나머지는 사후 회수 가능하므로
> "지금 안 잡으면 잃는다"로 정당화할 수 없고, 별도 근거로 정당화해야 한다.

### 1-A. 진짜 회복불가 — 이벤트 로그에 반드시 남길 것

| # | 데이터 | 없으면 영영 못 하는 것 | 왜 회복 불가인가 |
|---|---|---|---|
| 1 | **의사결정 시점 입력 + `arrival_px`** | 슬리피지·implementation shortfall 분해 | 흔히 말하는 "장중 가격을 못 구해서"가 아니다. **yfinance adjusted price는 배당·분할 때마다 과거 전체가 소급 수정**된다 → "그때 모델이 본 숫자"는 같은 소스로 재현되지 않는다(point-in-time / restatement bias). MARKET 주문이라 지정가 기록조차 없다 |
| 2 | **반사실(counterfactual)** — skip reason, 탈락 후보, 사람이 거부한 주문 | "왜 X를 안 샀나" | **안 한 일은 어디에도 흔적이 남지 않는다** |
| 3 | **`git_commit` + config hash** | "이 주문은 어느 코드·모델이 냈나" | rebase/force-push 없고 실행 전 commit 규율이 있으면 사후 복원 "가능"하지만, dirty tree에서 돌면 불가. **보험료가 문자열 두 개** |
| 4 | **타이밍** — 런 시작·결정·발주 시각 | 지연(delay) 비용 분해 | 브로커는 `orderedAt`만 안다. **결정 시각은 모른다** |

### 1-B. 회복 가능 — "포착 시한"으로 정당화하면 안 되는 것 (1차 조사의 오류)

| 1차 조사 주장 | 실제 |
|---|---|
| `fills.settlement_date` "오늘 당장, 놓치면 복원 어려움" | **`GET /api/v1/orders/{id}.execution.settlementDate`로 언제든 회수 가능.** 저장은 편의지 보존이 아니다 (자체 phase 0에서 확인한 사실) |
| 결제일 매매기준율(MAR) 일별 수집 크론 | **환율 히스토리는 영구 공개.** 회복불가 논거로 정당화 불가. 게다가 환전 자체가 수동이라 급하지 않다 |
| 섀도우 페이퍼 수익 `[B]`를 서브시스템으로 | **이벤트 로그 위의 replay 스크립트면 동일.** 로그를 먼저, 숫자가 필요할 때 replay를 나중에 |
| `lots` (취득 로트) | 체결 이력이 남아 있으면 사후 구성 가능. 세무 필요 시점에 만들면 된다 |
| `fx_conversions` 수동 환전 기록 | 필요하긴 하나 회복불가는 아니다(잔고 델타로 역산 가능). 다만 API에 환전 엔드포인트가 없으므로 **기록 습관은 지금 들이는 게 낫다** |
| `commission`, `tax`, `averageFilledPrice`, `filledQuantity` | 전부 `GET /orders/{id}.execution`에서 회수 가능 |
| 보유 포지션 | **브로커가 source of truth**다. 그게 대사(reconciliation)를 하는 이유다 |
| 모든 파생 지표 (rank-IC, attribution, waterfall, CUSUM, regime matrix) | 원시 이벤트만 있으면 **나중에 전부 계산된다** |

**마지막 항목이 구조적으로 중요하다.** 정보 손실은 **이벤트 → 집계** 방향으로만 발생한다. 반대는 언제든 된다.
Honeycomb의 논지가 이것이다 — *"메트릭은 풍부한 데이터를 이해하는 데 형편없는 building block이다.
쓰기 시점에 그 모든 맥락을 버려야 하기 때문이다… 이벤트에서 메트릭·로그·트레이스를 파생시킬 수 있고, 다 같은 데이터다."*

> **종합: "지금 안 잡으면 잃는다"는 참이되, 그 대상은 *결정 이벤트 로그 하나*다.**
> 원장 스키마 마이그레이션 프로젝트로 확장하는 것은 이 논거의 범위를 넘어선다.
> 스키마는 **데이터가 쌓인 뒤 도출하는 편이 더 정확하다.**

---

## 2. 기존 문서 정정 필요 — 10건

| # | 현재 문서 | 조사 결과 | 심각도 |
|---|---|---|---|
| 1 | ledger-design 스키마 — `fills`에 결제일 컬럼 없음 | 세무 계산에 필요. 단 **`GET /orders/{id}`로 사후 회수 가능**하므로 긴급하지 않다 (2차 조사로 심각도 🔴→🟡 하향, §1-B) | 🟡 |
| 2 | ledger-design 결정 8 — `orders.status`가 `placed`부터 시작 | **write-ahead `intent` 상태 누락.** HTTP 요청 *전에* 커밋하지 않으면 크래시 시 "보냈는지 모르는 주문"이 남는다. 결정적 멱등키가 있어도 **순서가 틀리면 무의미** | 🔴 |
| 3 | ledger-design `status` enum | **`unknown` 상태 누락.** 응답 없음 = 대부분의 봇이 중복 발주하거나 체결을 유실하는 지점. 재기동 시 non-terminal 주문은 반드시 브로커 조회로 해소 | 🔴 |
| 4 | qlib-toss — "T+2 실측 확정" | 측정은 맞다. 단 미국 현지는 **2024-05-28부터 T+1**이고 T+2는 국내 예탁·외화결제 버퍼다. **상수로 박지 말고 API `settlementDate`를 그대로 저장할 것** — 미국 휴장일 + 한국 휴장일이 겹치면 규칙 계산이 어긋난다 | 🔴 |
| 5 | qlib-toss — "자동환전 X, 선환전 필요" | 맞다. 추가로 **환전 시간창이 비용을 10배 가른다**: 평일 09:00~15:30 KST(서울외환시장 영업일) = 스프레드 0.05%, 그 외/주말/공휴일 = 0.5%. 문서에 없는 운영 제약 | 🔴 |
| 6 | 개선4 kill switch | **safe state가 미정의.** long-only 현물의 안전 상태는 `flat`(청산)이 아니라 `frozen`(동결)이다. 자동 청산은 왕복 20bp를 확정 실현시키고 저점매도를 고착시킨다. **자동 손실 청산 로직은 넣지 말 것** | 🟠 |
| 7 | ledger-design §연결/동시성 — "대시보드는 리더" | 승인·kill·M/X 토글 등 쓰기 기능이 들어오면 이 가정이 깨진다. §7 참조 | 🟠 |
| 8 | [analyze_capm.py](../../scripts/model_backtest/analyze_capm.py) | **RF를 차감하지 않고 SPY 원수익에 회귀** → alpha가 `RF·(1−β)`만큼 편향. t-stat 미출력. CAPM 결론(커밋 `552b4c0`) 재검증 필요 | 🟠 |
| 9 | qlib-toss B2 — overlapping 라벨을 "한계로 명시" | 명시만으로 부족. **Purge(경계 양쪽 5거래일) + Embargo(전체 T의 약 1%)** 가 표준 해법. 또는 주간 비겹침 샘플링 전환 시 대부분 소멸 | 🟠 |
| 10 | qlib-toss 개선2 — 슬리피지 0.10% "하한 가정 유지" | 가정 방치 대신 **민감도 곡선**(0/10/25/50/100bp에서 Sharpe)으로 "엣지가 몇 bp에서 사라지는가"를 단일 숫자로 확정 | 🟡 |

---

## 3. 수렴 기능 — 2개 이상 각도에서 독립 도출

서로 다른 도메인의 조사가 같은 결론에 도달한 항목. 수렴은 강한 설계 신호다.

| 기능 | 도출 각도 | 요지 |
|---|---|---|
| **대사(reconciliation) + break 관리** | OSS·기관·세무 | 브로커가 진실. 시장가+소수점 주문은 원장 드리프트가 **반드시** 발생. 미해소 break가 있으면 다음 실행 차단 |
| **미실행(skipped)을 1급 이벤트로** | OSS·기관 | Nautilus `OrderDenied`, Freqtrade 거부시그널 CSV export, Edgewonk "Missed Trades" — 3개 프로젝트가 독립적으로 도달. 기존 `skipped` 테이블에 **reason_code enum**만 얹으면 됨 |
| **2단계 정지 (진입중단 / 전면정지)** | OSS·기관 | Freqtrade `/pause` vs `/stop`, Nautilus `REDUCING` vs `HALTED`. 주간 리밸에서 가장 자주 필요한 개입은 "이번 주 매수만 스킵" |
| **preflight 체크리스트 + 승인 게이트** | OSS·기관 | 전 항목 PASS여야 EXECUTE 활성. 소액 계좌에서 이 화면 하나가 사고 대부분을 막음 |
| **회전율 비용 예산** | OSS·기관·리서치 | `연간 명시적 비용 ≈ 20bp × 주간회전율 × 52`. 회전율 50% → **연 5.2% 소모**. $700에서 TCA의 목적은 실행품질 개선이 아니라 **회전율 억제 근거 제공** |
| **arrival price 슬리피지** | OSS·기관·리서치 | 발주 직전 참조가 스냅샷. 시장가 봇의 유일한 실행품질 지표 |
| **헬스체크 — 조용한 미실행 탐지** | OSS·기관 | 주 1회 잡의 최대 실패 모드는 크래시가 아니라 **아예 안 돈 것** |
| **벤치마크 대비 + rolling beta** | OSS·리서치 | "초과수익=베타 틸트" 결론을 지속 감시하는 계기판 |

---

## 4. 각도별 상세

### 4-1. 오픈소스 / 인디 트레이딩 앱

조사 대상: Freqtrade·FreqUI, Hummingbot(Dashboard→Condor), Jesse, OctoBot, NautilusTrader,
Ghostfolio, Portfolio Performance, Lean CLI, Tradervue, Edgewonk, QuantStats, vectorbt.

#### 수렴 항목 (3개 이상 프로젝트)

| 기능 | 채택 프로젝트 | 적용도 |
|---|---|---|
| **Dry-run / Paper trading 모드** — config 플래그 하나로 전환, 별도 코드 경로 없음 | Freqtrade `dry_run`, Hummingbot `paper_trade`, OctoBot, Jesse, Lean | **HIGH** — 토스에 샌드박스가 없으므로 앱 내부 dry-run이 유일한 리허설 수단 |
| **2단계 정지** | Freqtrade `/pause`·`/stopentry` vs `/stop`, Nautilus `REDUCING` vs `HALTED`, Hummingbot | **HIGH** |
| **강제 청산/진입 (수동 오버라이드)** | Freqtrade `/forceexit`·`/fx all`, FreqUI 버튼, Condor | **HIGH** — 시장가·금액주문 환경이라 구현 난도 낮음 |
| **채팅봇 제어 표면 (양방향)** | Freqtrade Telegram 30+ 명령, OctoBot, Condor(인라인 버튼·상태 동기화) | **HIGH** — Streamlit 없이 주 1회 승인/중단 |
| **이벤트별 알림 세분화 (on/silent/off)** | Freqtrade `notification_settings`(entry/entry_fill/exit/exit_fill/protection_trigger 개별), webhook 7종 | **HIGH** — "주문 제출"과 "체결"을 분리 알림하는 설계 차용 |
| **설정 원문 조회 + 무중단 리로드 (시크릿 마스킹)** | Freqtrade `/show_config`·`/reload_config`, Hummingbot `config`, `lean config` | **HIGH** — 재현성의 최소 단위 |
| **앱 내 로그 뷰어** | Freqtrade `/logs`·`GET /logs`, Condor, OctoBot | **HIGH** — 주 1회 잡은 실패 시점에 사람이 없음 |
| **헬스/시스템 상태 엔드포인트** | Freqtrade `/health`·`/sysinfo`, Hummingbot `status`, PP "Price Update Status" | **HIGH** |
| **사유(tag)별 성과 귀속** | Freqtrade `backtesting-analysis`(enter_tag/exit_tag 0~5단계), `/stats`, Tradervue 100+ 리포트, PP Taxonomies | **HIGH** — TopkDropout의 enter/add/trim/exit 구분에 직결 |
| **벤치마크 대비 성과** | QuantStats tearsheet, Ghostfolio, PP benchmarking, `lean report` | **HIGH** |
| **드로다운·리스크 패널** | QuantStats, PP Risk Indicators, vectorbt, Ghostfolio X-ray | **HIGH** — 특히 **Current Drawdown**·**MDD Duration**은 현 백테스트 뷰어에 없음 |
| **거래 잠금 / 쿨다운** | Freqtrade `CooldownPeriod`·`StoplossGuard`·`MaxDrawdown`, `/locks`·`/unlock` | **HIGH** — 같은 종목 왕복매매(회전율) 억제 |
| **체결에 메모·태그** | Tradervue(노트·태그·스크린샷), Edgewonk(다이어리), PP(거래 노트) | **HIGH** — 컬럼 2개 추가 비용으로 분석력 확보 |
| **자본 상한 가드레일** | Freqtrade `tradable_balance_ratio`(기본 99%)·`available_capital`, Nautilus `max_notional_per_order`, Hummingbot Balance Limit | **HIGH** — 버그 하나가 전액을 태우는 것을 막는 최후 방어선 |
| **백테스트 결과 브라우저 + 비교** | FreqUI, Hummingbot Dashboard, Jesse, `lean report`, QuantStats | **HIGH** — 현 앱이 하는 일. **비교** 기능이 빠져 있음 |

#### 비자명한 기능 (대시보드 프레이밍에서는 안 나오는 것)

1. **`/marketdir` — 사람이 세팅하고 전략이 읽는 전역 시장방향 플래그.** Freqtrade는 `long/short/even/none`을
   Telegram에서 바꾸면 전략 코드가 참조한다. 코드 수정·재배포 없이 사람 판단을 모델에 주입하는 통로.
   커밋 이력(레짐 틸트, CAPM beta 틸트)과 정확히 맞물린다.
2. **거부(denial)를 예외가 아니라 이벤트로 기록.** Nautilus `OrderDenied`(표준 사유 코드),
   Freqtrade `--export=signals`(거부 시그널까지 CSV), Edgewonk "Missed Trades"(저널 1급 객체).
   3개 프로젝트가 독립적으로 **"실행되지 않은 것을 기록하라"** 에 도달.
3. **봇 관리 잔고와 계좌 전체 잔고의 분리.** `/balance` vs `/balance full`, `tradable_balance_ratio`.
   한 계좌에 봇 자산과 비봇 자산이 섞이는 상황을 전제로 설계돼 있음 — 개선14와 동일 문제의식.
4. **`REDUCING` 상태.** ACTIVE/HALTED 사이 중간 상태. 노출을 **늘리지 않는** 주문만 통과.
   "정지 vs 정상" 이분법이 실전에서 부족하다는 증거.
5. **Lookahead-analysis.** 정적 코드 분석이 아니라 *전체 백테스트 vs 개별 시그널 백테스트*의 **결과 비교**로
   미래참조를 잡아내고 편향된 지표명까지 지목. (문서가 스스로 위음성 가능성을 경고 — 통과했다고 안전 결론 금지)
6. **Trade Management Simulator (Edgewonk).** 실제 거래 vs "가능했던 최선의 거래"를 대조해
   조기청산 비용을 **금액으로** 산출. 집행 품질의 what-if.
7. **Tilt-Meter (Edgewonk).** 자기 규칙 위반 횟수 누적 그래프. 자동화 시스템에서는
   **"수동 오버라이드 횟수와 그 손익"** 으로 그대로 번역된다.
8. **Sanity Check + Fix/Restore (Portfolio Performance).** 데이터 정합성 검사를 앱 메뉴에 내장.
   → 원장 앱에서 대사는 스크립트가 아니라 **기능**이다.
9. **Discreet Mode(PP) / Zen Mode(Ghostfolio).** 금액을 숨기는 모드가 두 앱에 독립 존재. 심리적 안전장치도 기능.
10. **위젯 형태의 조건 알림.** PP "Limit Price Exceeded", "Date Reached" — 푸시 인프라 없이 조건 알림 구현.
11. **`test-pairlist`.** 주문 없이 종목 선정 로직만 실행. "이번 주 Top-K 미리보기"의 정확한 선례.
12. **Ghostfolio X-ray.** 리스크 진단이 하드코딩이 아니라 **임계값 조정 가능한 규칙 엔진**
    (Liquidity, Account/Asset Class/Currency/Regional Cluster Risk 등).
13. **Ghostfolio 백그라운드 스냅샷 재계산.** 무거운 집계를 요청 시점이 아니라 미리 계산.
    Streamlit의 전체 재실행 모델과 정면 배치되는 설계.
14. **TTWROR와 IRR 병기 (PP).** 한쪽만 보면 소액·불규칙 입금 계좌에서 자기 실력을 오판한다.
15. **Portfolio Turnover Rate / Fee Rate / Average Holding Period (PP).** $700 규모에서 수수료 비율은 치명적.

#### 안티패턴 · 유지보수자 경고

**Streamlit 대시보드 자체가 사장된 사례 (가장 중요)**
Hummingbot의 Streamlit 기반 Dashboard가 **Condor로 대체되며 deprecated**. 대체 구조는
*Hummingbot API를 deterministic infrastructure로 두고, 그 위에 Telegram 봇 / 웹 대시보드 / 에이전트를
얇은 클라이언트로 얹는* 형태. 세 표면이 상태를 동기화한다. → §7

**Freqtrade가 제거한 기능들**

| 제거 항목 | 명시된 이유 | 버전 | 교훈 |
|---|---|---|---|
| Edge 모듈 (승률 기반 포지션 사이징) | 전면 제거 | 2025.6 | 정교한 자동 사이징 서브시스템은 유지비 대비 가치 낮음 |
| `order_book_min/max` (호가창 스테핑) | "increased risk without benefit" | 2021.7 | 체결가 미세최적화는 리스크만 증가 |
| `--live` (실시간 데이터 백테스트) | 500캔들만 받아 백테스트 무의미 | 2019.8 | 데이터 윈도 부족한 "빠른 백테스트" 만들지 말 것 |
| `--refresh-pairs-cached` | "leads to much confusion, and slows down backtesting" | 2019.9 | 캐시 제어 플래그를 사용자에게 노출하면 혼란 |
| `populate_any_indicators` | feature engineering / target 분리 | 2023.3 | 피처 생성과 타깃 정의를 한 함수에 섞지 말 것 (Qlib 파이프라인에 직접 적용) |
| config의 `protections` 섹션 | 3년 deprecation 경고 후 제거, 전략 코드로 이동 | 2024.10 | **리스크 규칙을 config와 코드에 이중 정의 금지** |
| CatBoost 모델 | LightGBM/XGBoost 권장 | 2025.12 | 모델 백엔드는 늘리는 것보다 줄이는 편이 나았음 |

**명시적 경고**
- **REST API를 인터넷에 노출하지 말 것.** Freqtrade 문서: 기본 localhost only,
  "We strongly recommend to not expose this API to the internet", SSH 터널/VPN 권장.
  → 원격 사용은 웹 노출이 아니라 Telegram/SSH 터널이 정석.
- Ghostfolio는 활동 타입을 세분화했다가 `ITEM`을 BUY로 **재통합**, 소셜 로그인 제거.
  → 타입 과세분화와 이색 인증은 유지비만 발생.

---

### 4-2. 기관 트레이딩 운영 표준 → 1인 봇으로 축소

#### 규모와 무관하게 필요한 것 (scale-free)

기관 통제의 대부분은 **자본 규모**에 비례한다. 아래는 다르다 — **실패 모드**에 비례하고,
그 확률은 $700이든 $700M이든 같으며 손실 상한은 양쪽 다 "가진 것 전부"다.

**1. Idempotency + write-ahead intent**
FIX는 ClOrdID를 "하루 안에서 유일, 여러 날에 걸쳐서도 재사용 금지"로 규정.
이유는 **전송은 성공했는데 응답을 못 받는 상태가 반드시 존재**하기 때문.
결정적인 부분은 결정적 clientOrderId가 아니다(이미 있음). **순서**다.
HTTP 요청 *전에* 주문 의도를 커밋하지 않으면 크래시 시 "보냈는지 모르는 주문"이 생기고,
포지션이 두 배로 잡히거나 리밸런싱이 절반만 되어 의도치 않은 집중 노출이 남는다.

> 규칙: `orders` row를 `intent`로 커밋 → API 호출 → 응답으로 상태 전이.
> 재기동 시 `intent`/`sent` 상태 row는 **반드시 브로커 조회로 해소**. 절대 재전송부터 하지 않는다.

**2. 브로커를 single source of truth로 두는 대사**
FIA: 자동매매 참가자의 frequent reconciliation은 "early warning for potential problems".
SEC는 브로커-딜러에게 분기별 실물 대사와 미해소 차이의 별도 기록을 의무화(17a-13).
$700에서도 필요한 이유는 **API가 체결을 놓칠 수 있기 때문** — 부분체결, 응답 타임아웃,
소수점 반올림, 그리고 무엇보다 **corporate action(분할·병합·배당)**.
어긋난 상태로 다음 주 리밸런싱이 돌면 오차가 주문 수량에 증폭되어 들어간다.
**원장 기반 봇은 대사 없이는 오차가 누적되는 시스템이다.**

**3. Append-only audit trail + reason code**
1인 봇에서 감사의 대상은 규제기관이 아니라 **6개월 뒤의 본인**이다.
"이 종목을 왜 안 샀지?", "왜 이 주에 벤치마크와 갈렸지?"에 답하려면
상태를 덮어쓰는 테이블이 아니라 이벤트를 덧붙이는 테이블이 필요하다.
특히 `skipped`에 **구조화된 reason code**가 없으면 백테스트-라이브 괴리를 영원히 설명할 수 없다.

**4. Kill switch와 safe state**
FIA 정의: kill switch는 "즉시 모든 거래 활동 비활성화, 신규 주문 차단, 작동 중 주문 취소"이며
"다른 조치가 실패했을 때의 최후 수단". ESMA RTS 6 Art.12는 미체결 주문 즉시 취소 능력을 요구.

> **축소 이식의 핵심 판단:** 기관의 safe state는 대체로 `flat`(청산). $700 long-only의 safe state는 **`frozen`(동결)**.
> - 자동 청산은 왕복 20bp를 즉시 확정 실현
> - 자동 FX 전환이 없어 청산해도 원화 회수 안 됨 — USD 현금으로 남을 뿐
> - long-only 현물은 마진콜도 강제청산도 무한손실도 없다. **아무것도 안 하는 것이 안전한 상태다**
>
> → kill switch = 신규 발주 영구 차단 + 미체결 취소 시도 + 기존 보유 유지 + **수동 해제 필수**.
> **자동 손절 청산 로직은 넣지 않는다.**

**5. 사전 한도 — fat-finger가 아니라 fat-model 방지용**
Rule 15c3-5(c)(1)은 "price or size parameters를 초과하는 주문 거부"를 요구.
1인 봇에 fat-finger는 없다(사람이 안 침). 하지만 **fat-model**은 있다 —
시그널의 NaN, 잘못된 가격 스케일, 리밸런싱 루프의 off-by-one이 정확히 같은 결과를 만든다.
RTS 6 Art.15의 4개 통제 중 **maximum order value + 배치 총 notional 상한**만 있으면 된다.
코드 20줄로 계좌를 날리는 클래스의 버그 전체를 막는다.

**6. 결제 사이클 반영 현금 예측**
자동 FX 부재가, 기관에서는 단순 유동성 예측이던 것을 **리드타임 있는 수동 액션 트리거**로 승격시킨다.

#### 실무 인벤토리 — 판정 요약

| 영역 | WORTH BUILDING | LIGHTWEIGHT | SKIP |
|---|---|---|---|
| **Pre-trade** | max order value + 배치 notional 상한, 중복주문 UNIQUE 보강, 거래가능성 필터(소수점 가능·거래정지·상장폐지) | price collar(preflight의 quote staleness + post-trade 이탈 알림), rate limit 토큰버킷, 배치 내 netting, 종목별 비중 상한, orphan sweep | credit/capital threshold(현금계좌 long-only는 구조적 불가), direct and exclusive control, 연례 CEO 인증 |
| **Reconciliation** | 3-way 포지션 대사, 현금 대사(traded vs settled), break lifecycle(open→investigate→resolve, 미해소 시 실행 차단), orphan/stale 주문 해소 | corporate action은 별도 피드 대신 **대사가 break로 잡고 사람이 확인 후 조정** | drop copy(리테일 API에 없음), fund admin 3-way |
| **TCA** | arrival price 슬리피지, **명시적 비용(수수료+FX) 추적** | implementation shortfall 3구간 분해, opportunity cost(skipped 종목의 사후 수익) | VWAP/interval VWAP(주문 안 쪼갬), market impact 분해($70 주문은 임팩트 0), peer TCA |
| **Audit trail** | order state machine, append-only `order_events`, 이벤트 체인(run→signal→order→fill) | ms/ns 정밀도 대신 초+단조 seq | CAT/OATS 규제 리포팅, WORM 물리 저장소(SQLite 트리거로 대체) |
| **Kill/breaker** | kill switch UI 승격, **safe state=frozen 정의**, 자동 트리거 4종, 사유 필수 수동 재가동 | loss limit은 **알림만** | 리스크 기능 조직 분리, 자동 청산형 safe state |
| **Runbook** | preflight 체크리스트, close-out 체크리스트 | post-deployment 축소 한도, change management("리밸런싱 당일 배포 금지"), 분기 self-assessment | DR/BCP·이중화·co-location(백업만 남김), market abuse surveillance |
| **Cash/settlement** | settled vs unsettled 구분, good-faith 규칙 1개, **현금 사다리** | — | buying power 실시간 재계산, Reg T/margin |

#### 원장 스키마 추가 제안

기존 `runs / signals / orders / fills / positions_snapshot / skipped / instruments`에:

```
order_events(id, order_id, seq, ts_utc, from_state, to_state,
             actor, reason_code, payload_json)       -- append-only, UPDATE/DELETE 트리거 차단

recon_runs(id, run_id, ts_utc, kind,                 -- kind: position | cash
           broker_snapshot_json, ledger_snapshot_json, break_count, status)

breaks(id, recon_run_id, kind, symbol, ledger_value, broker_value, delta,
       opened_at, status, resolution, resolved_at, resolved_by_run_id, note)
       -- status: open | investigating | resolved | accepted

cash_flows(id, run_id, ts_utc, currency, amount, kind,    -- buy|sell|commission|fx|deposit
           trade_date, settle_date, order_id)

control_state(key, value, updated_at, updated_by, reason)  -- kill_switch, breaker_tripped, limits_version
```

`orders` 추가: `state`, `arrival_px`, `arrival_ts`, `decision_px`, `intent_committed_at`,
UNIQUE(`run_id`, `symbol`, `side`).

**주문 상태 머신** (FIX OrdStatus 축소판):

```
intent → sent → accepted → partially_filled → filled
                        ↘ rejected
                        ↘ canceled
              ↘ unknown  (응답 없음 — 반드시 브로커 조회로 해소)
```

`unknown`을 1급 상태로 두는 것이 요점.

#### Preflight 체크리스트 (전부 PASS여야 실행)

| # | 체크 | 실패 시 |
|---|---|---|
| 1 | Kill switch OFF / breaker 미발동 | BLOCK |
| 2 | 미해소 `breaks`(status=open) 없음 | BLOCK |
| 3 | non-terminal 주문 없음 (orphan sweep 완료) | BLOCK |
| 4 | 브로커 포지션 == 원장 포지션 | BLOCK |
| 5 | 브로커 USD 예수금 == 원장 현금 (tolerance $0.01) | BLOCK |
| 6 | 시장 데이터 정상 (NaN/0/음수 없음, 나이 < N시간, 전일비 이상변동 없음) | BLOCK |
| 7 | 배치 notional ≤ 한도, 주문 건수 ≤ 한도, 단건 notional ≤ 한도 | BLOCK |
| 8 | 계획 매수액 ≤ 가용 USD (settled 기준) | WARN + 환전 액션 제시 |
| 9 | 미국 정규장 개장 중 | BLOCK |
| 10 | 종목별 tradable (거래정지·소수점불가·상장폐지예정 아님) | 해당 종목만 `skipped` |

#### 경량 TCA 계산식

```
side_sign      = +1 (BUY) / −1 (SELL)
delay_bps      = side_sign * (arrival_px - decision_px) / decision_px * 10000
slippage_bps   = side_sign * (avg_fill_px - arrival_px) / arrival_px  * 10000
explicit_bps   = commission / notional * 10000          (≈ 10bp/side)
total_is_bps   = delay_bps + slippage_bps + explicit_bps
```

`decision_px` = 시그널이 사용한 종가, `arrival_px` = 발주 직전 스냅샷. 양수 = 손해.

**리포트 상단 고정 숫자 — 회전율 비용 예산:**

```
연간 명시적 비용 ≈ 20bp × 주간회전율 × 52
  회전율 30% → 3.1%/yr
  회전율 50% → 5.2%/yr
  회전율 80% → 8.3%/yr
```

$700 규모에서 이 숫자가 TCA의 전부다. VWAP 대비 몇 bp는 노이즈에 묻히지만 회전율 비용은 알파를 확정적으로 잡아먹는다.
**이 화면의 목적은 실행 품질 개선이 아니라 회전율 억제 근거 제공.**

---

### 4-3. 한국 거주자 미국주식 — 세무 · 환전 · 결제

#### 헤드라인

1. **세법상 환율은 "결제일의 기준환율(매매기준율)"이다.** 체결일도, 실제 환전일도, 실제 환전 환율도 아니다.
2. **과세연도 귀속도 결제일 기준** — 12월 말 매도는 다음 해 귀속이 될 수 있다.
3. **토스 OpenAPI에 환전 엔드포인트가 아예 없다** — 전체 36개 엔드포인트 전수 확인. 선환전은 **영구 제약**.
4. **T+2 vs T+1 불일치는 실재하며 정상** — 미국 현지 T+1(2024-05-28~), 국내기준 T+2(기존 T+3→T+2).
5. **토스 OpenAPI는 `settlementDate`를 이미 내려준다** — 원장이 당장 저장해야 할 1순위 필드.

#### 양도소득세 규칙

| # | 규칙 | 내용 |
|---|---|---|
| T1 | 과세대상 | 5년 이상 국내 거주자의 국외주식 양도. **대주주 여부 무관 = 소액 개인도 전액 과세** |
| T2 | 세율 | 20% + 지방소득세 = 실효 **22%** |
| T3 | 기본공제 | 국내+국외 양도소득 합산액에서 **연 250만원** |
| T4 | 예정신고 | **의무 없음.** 확정신고로 종결 |
| T5 | 확정신고 | 다음 해 **5.1~5.31** |
| T8 | 손익통산 | 같은 과세기간 내 국외↔국외 통산 가능. **확정신고 시에만** |
| T9 | 이월결손금 | **다음 연도 이월공제 불가** → 연말 손실 실현의 가치가 큼 |
| T11 | 취득가액 | 실지거래가액. 취득시기 불명확 시 **FIFO 원칙**(소득세법 시행령 §162⑤) |
| T12 | 예외 | 증권사가 **이동평균법을 계속 적용**한 경우 이동평균법도 인정 → 토스 방식 확인 필요(U1) |
| T13 | 필요경비 | 취득가액 + 양도비용(증권사 수수료 등) |
| **T14** | **환율** | 시행령 **§178-5①**: "양도가액 및 필요경비를 **수령하거나 지출한 날** 현재 「외국환거래법」에 의한 **기준환율 또는 재정환율**" |
| **T15** | **"수령·지출한 날"** | NTS 회신: **"결제대금이 고객계좌로 입금되거나 출금된 날의 환율"** → **결제일 환율** |
| T16 | 양도시기 | 대금청산일(결제일). 증권사 안내도 "매도(**결제일 기준**)" |
| T17 | 계산식 | 양도가액 = 가격 × 주식수 × **결제일 환율**, 취득가액 동일, 필요경비 = 수수료 × **결제일 환율** |
| T18 | 실제 환전손익 | 매도일과 실제 환전일 사이 환율변동은 **과세표준에 미반영** |

**기준환율 = 매매기준율(MAR)**: 외국환중개사 미달러 현물환 거래량 가중평균(시장평균환율).
서울외국환중개(주)가 매 영업일 **08:30경 고시**. **하루 1개 값**.
⚠️ 토스 API `/api/v1/exchange-rate`의 `midRate`는 **1분 갱신 실시간 참고값**으로,
문서가 "실제 주문 시 적용되는 거래 환율과 다를 수 있습니다"라고 명시 → **세무용 대체재가 아님**.

#### 배당 — 구현 불필요

- 미국 원천징수 15%(한미조세조약). 현지세율(15%)이 국내세율(14%)보다 높아 **국내 추가 원천징수 없음**.
- 금융소득종합과세 기준 2,000만원 대비 자본 100만원의 배당은 무의미.
- **결론: 세무 기능 불필요.** 단 총배당·원천징수액은 total return 성과측정용으로 기록 권장.

#### 원장이 저장해야 할 필드

**`fills`** (세무 원장의 근간)

| 필드 | 왜 | 캡처 시점 | 토스 API |
|---|---|---|---|
| `settlement_date` | **세법상 양도시기 + 환율기준일 + 과세연도** | 체결 시 즉시 | ✅ `OrderExecution.settlementDate` |
| `fx_mar_krw` | 결제일 매매기준율. 없으면 원화 가액 계산 불가 | 결제일 08:30 이후 백필 | ❌ 서울외국환중개/ECOS |
| `commission_usd`, `tax_usd` | 필요경비 | 체결 시 | ✅ `OrderExecution.commission`/`tax` |
| `quantity` | 소수점 주식 → **DECIMAL, float 금지** | 체결 시 | ✅ `filledQuantity` |
| `price_usd`, `gross_amount_usd` | 실지거래가액 | 체결 시 | ✅ `averageFilledPrice`/`filledAmount` |
| `isin` | 신고서 필수 항목 | 최초 매수 시 1회 | ❌ 외부 조달(U7) |
| `tax_year` | `YEAR(settlement_date)` — **체결일 연도 아님** | 백필 시 파생 | 파생 |
| `actual_fx_rate` | 실제 환전 대고객환율 (세무용 X, 실현 원화손익용 O) | 환전 시 | ❌ |

**`lots`** — FIFO 원가: `acq_settlement_date`, `acq_qty_remaining`, `acq_price_usd`,
**`acq_fx_mar_krw`(몇 년 뒤에도 필요 → 반드시 스냅샷 저장)**, `acq_krw_cost_total`, `cost_method`

**`disposals`** — 매도-로트 매칭(1:N): `krw_proceeds`, `krw_acq_cost`, `krw_expenses`, `krw_gain`, `tax_year`

**`fx_rates`** — 일별 MAR 캐시: `rate_date`(PK), `mar_krw_per_usd`, `source`, `fetched_at`, `raw_payload`
> 매일 1회 수집 크론. 과거값 소급 조회가 어려워질 수 있으니 매일 저장이 안전.

**`fx_conversions`** — 선환전 기록: `converted_at`, `krw_amount`, `usd_amount`, `applied_rate`,
`mar_at_time`, `spread_bps`, `channel`

**흔한 실수**

| 실수 | 왜 틀렸나 |
|---|---|
| 체결일 환율 저장 | 세법은 **결제일** 환율 |
| 실제 환전 환율로 취득가액 산정 | 세법은 **매매기준율**, 대고객환율 아님 |
| 토스 `midRate`를 세무 환율로 사용 | 1분 갱신 참고값. 일일 고시 MAR이 아님 |
| `tax_year = YEAR(filled_at)` | 12월 말 매도는 다음 해 귀속 가능 |
| quantity를 float로 | 소수점 주식 → 반올림 오차가 세액 오차로 전파 |
| 평균단가만으로 매도 원가 계산 | FIFO 로트 추적 없으면 증권사 계산자료와 불일치 |

#### 환전 운영

- **토스 OpenAPI에 환전 엔드포인트 0개** (36개 전수 확인). 조회용 `GET /api/v1/exchange-rate`만 존재.
  → 선환전은 API 계약상 **영구 제약**(일시적 버그·권한 문제 아님).
- **`GET /api/v1/buying-power`가 `currency`를 필수로 받음** → API는 **통화별 분리 회계** 모델. 실측과 일치.
- **스프레드 시간창** (토스 FAQ 3549):

  | 구간 | 스프레드 | 우대 | 실효 |
  |---|---|---|---|
  | 기본 | MAR 대비 1% | — | 1% |
  | **평일 09:00~15:30 KST** (서울외환시장 영업일) | 1% | **95% 할인** | **0.05%** |
  | 그 외·주말·공휴일 | 1% | 50% 할인 | 0.5% |

  실측 0.03%와 대조: 편도 0.5% × 5% = 0.025% ≈ 0.03% → 정합.
  **운영 함의: 선환전은 반드시 평일 09:00~15:30 KST. 벗어나면 비용 10배.**
- **환차익**: 개인의 환차익은 소득세법 열거주의상 비과세(⚠️ 1차 출처 미확보, U5).
  양도세 계산에서 환율변동분은 취득·양도 결제일 환율 차이로 이미 반영되며 별도 과세되지 않음.
- **통합증거금**: "결제일에 필요금액만큼 자동환전"하는 서비스. 주문 시점 환전이 아님.
  토스 앱 제공 여부와 OpenAPI 경로 동작은 별개(U3).

#### 결제 — T+1 vs T+2 해명

| 구분 | 사이클 | 근거 |
|---|---|---|
| 미국 현지 (DTCC) | **T+1** (2024-05-28 시행) | 유안타 공지: "미국현지 기준으로는 T+2일에서 T+1일로 결제주기 단축" |
| 한국 증권사 국내기준 | **T+2** (기존 T+3 → T+2) | 동 공지: "T+3일 → T+2일", "2024년 5월 28일 체결분부터" |

**판정: 실측 T+2가 정확하다. 브로커/예탁 측 버퍼가 맞다.**
차이 1영업일은 시차 + 외화 결제·예탁(한국예탁결제원 경유) 처리 버퍼.
**세무상 중요:** §178-5①의 "수령·지출한 날"은 "결제대금이 고객계좌로 입금·출금된 날" →
미국 현지 T+1이 아니라 **국내기준 T+2**가 세법상 결제일. 토스 `settlementDate`가 바로 이 값(추정, U8).

> ❗ `settlement_date`를 **계산하지 말 것.** 미국 휴장일 + 한국 휴장일 + 브로커 버퍼가 겹쳐 규칙이 복잡하다
> (예: 2024-05-24·05-28 체결분이 Memorial Day 때문에 05-30에 동시 결제).
> **API가 주는 값을 그대로 저장하는 것이 유일하게 안전한 방법.**

- 매도대금은 결제일에 USD 외화예수금으로 입금, **통상 결제일 오후 3시 이후** 반영.
- **12월 말 컷오프**: 12월 마지막 주 매도는 결제일이 다음 해 1월 → 다음 과세연도 귀속.

#### 앱 기능 권고

**이중 P&L 엔진**

| | 세무 P&L | 실현 원화 P&L |
|---|---|---|
| 환율 | 결제일 **매매기준율** | 실제 **대고객환율** |
| 수수료 | 매매수수료만 (환전스프레드 제외 권장, U2) | 매매수수료 + 환전스프레드 전액 |
| 용도 | 5월 신고, 250만원 한도 관리 | 실제 성과·전략 평가 |

**봇 성과 평가에 세무 P&L을 쓰면 틀린 결론이 나온다.**

기타: MAR 일일 수집 크론 / 환전 시간창 가드레일 / USD 부족 시 `skipped` 사유 `INSUFFICIENT_USD` /
세무 대시보드(250만원 공제 잔여, 12월 컷오프 경고, 손실실현 후보) / 신고 산출물 export.

> ⚠️ 자본 100만원 기준 연 250만원 초과 차익은 현실적으로 거의 발생하지 않는다.
> **세금 계산 기능의 본질은 "지금 계산"이 아니라 "나중에 계산 가능하도록 데이터를 축적"하는 것.**
> 계산 로직보다 **필드 캡처를 먼저** 구현할 것.
>
> 토스증권은 **무료 신고대행**을 제공하고 10개 증권사 합산 신고가 가능하다.
> NTS도 증권사 계산보조자료 제출 시 부표2·증빙 생략을 허용한다.
> → **증권사 자료가 정본, 우리 원장은 검산·조기경보용**으로 포지셔닝.

---

### 4-4. 퀀트 리서치 워크벤치 · 라이브 모니터링

#### 오버피팅 정직성

**시행 횟수 N 원장 — 모든 것의 전제**
Bailey & López de Prado: 백테스트에서 빠진 가장 중요한 정보는 **시도 횟수**.
N을 모르면 백테스트는 "worthless, regardless of how excellent the reported performance".
이 프로젝트는 [tune_hyperparams.py](../../scripts/model_backtest/tune_hyperparams.py),
[probe_models.py](../../scripts/model_backtest/probe_models.py),
[probe_label_horizon.py](../../scripts/model_backtest/probe_label_horizon.py)로 이미 다수 설정을 돌렸고
**mlruns가 사실상 시행 원장인데 아무도 세지 않고 있다.**

**Deflated Sharpe Ratio (DSR)**

```
E[max SR] ≈ E[SR] + sqrt(V[SR]) · ( (1−γ)·Z⁻¹[1 − 1/N] + γ·Z⁻¹[1 − 1/(N·e)] )
γ = 0.5772 (Euler–Mascheroni), Z = 표준정규 CDF

DSR = Z[ (SR̂ − SR₀)·sqrt(T−1) / sqrt(1 − γ₃·SR̂ + ((γ₄−1)/4)·SR̂²) ]
γ₃ = 왜도, γ₄ = 첨도, T = 관측 수, SR₀ = E[max SR]
```

논문 수치예: SR̂=0.0362, N=88 → E[max SR]≈0.0243, DSR=0.9004 → 95% 미달로 기각.
N=46이었으면 DSR=0.9505로 통과. **비정규성(왜도·첨도)만으로도 합불이 갈린다.**
→ UI: 원시 Sharpe 옆에 DSR 배지 상시 표시. 툴팁에 T·왜도·첨도·N·V[SR̂] 노출.

**Minimum Backtest Length**
`MinBTL < 2·ln(N) / E[max SR]²` (년). 데이터 5년뿐이면 독립 설정 45개 초과 시
IS Sharpe 1인데 OOS 기대 Sharpe 0인 전략이 거의 확실히 나온다.
→ UI: 게이지 `보유 데이터 12년 vs 필요 MinBTL 9.8년(N=137)`.

**PBO / CSCV**
수익 행렬을 S블록으로 쪼개 C(S,S/2) 조합 전부에 대해 IS 최적 설정의 OOS 상대순위 → 로짓 λ.
**PBO = Prob[λ < 0]**, 관례적 기각선 0.05.
부수 통계가 더 중요할 수 있음:
- **Performance degradation**: `SR_OOS = α + β·SR_IS` 회귀. **β<0이면 과적합**
  (논문 예시: SR_IS는 100% 양수인데 SR_OOS의 78%가 음수)
- **Probability of loss**: Prob[SR_OOS < 0]

**다중검정 허들**: Harvey·Liu·Zhu — 신규 팩터는 t>2.0이 아니라 **t>3.0**.
현 `analyze_capm.py`는 t-stat 자체를 안 냄.

#### 시그널 진단 — Qlib이 이미 주는 것

| 기능 | 위치 |
|---|---|
| IC, ICIR, Rank IC, Rank ICIR, Long-Short Ann Return/Sharpe | `qlib/workflow/record_temp.py::SigAnaRecord` |
| 분위(N=5) 수익, IC 시계열/월별/히스토그램/QQ, 예측 자기상관, 예측 회전율 | `qlib/contrib/report/analysis_model/analysis_model_performance.py` |
| mean/std/annualized_return/IR/MDD | `qlib/contrib/evaluate.py::risk_analysis` |
| **체결품질: `pa`(price advantage), `pos`, `ffr`(fulfill rate)** | `qlib/contrib/evaluate.py::indicator_analysis` |

> **"IC/분위수익/회전율/자기상관"은 새로 만들 게 아니라 대시보드에 노출만 하면 된다.**
> 현 앱은 자산곡선과 보유·매매만 보여줘 이 부분이 통째로 사장돼 있다.
> 그리고 `indicator_analysis`의 pa/pos/ffr을 **라이브 체결에 대해 계산하면 백테스트↔라이브 직접 비교가 된다** — 새 지표 발명 불필요.

**Alphalens가 더 주는 것**: 다중 forward-return 기간(1D/5D/10D) 동시 처리, IC t-stat/p-value/skew/kurtosis 테이블,
분위 평균수익 **표준오차 포함**, top−bottom 스프레드 밴드, `quantile_turnover`(분위별),
`factor_rank_autocorrelation`, 섹터별 IC.

**IC decay / half-life**: 1/5/21/63일 forward IC 감쇠곡선.
**IC 피크 = 자연 보유기간, IC 절반 지점 = 신호 반감기 → 리밸런싱 주기의 직접 근거.**

**Grinold–Kahn 기본법칙 타일**: `IR ≈ IC · sqrt(breadth)`.
K=15~20 주간이면 breadth ≈ 780/년 → IC 0.02면 **IR ≈ 0.56이 이론 상한**.
백테스트 IR이 이를 크게 넘으면 그 자체가 누출/버그 신호. 한 줄 타일인데 데이터 누출 탐지에 잘 먹힌다.

#### 성과 귀인

- **데이터**: Kenneth French Data Library, `pandas-datareader`로 직접 로드
  (`F-F_Research_Data_5_Factors_2x3_daily`, `F-F_Momentum_Factor_daily`).
  ⚠️ %단위이고 RF 포함 → 회귀 좌변은 **전략수익 − RF**.
  **현 `analyze_capm.py`는 SPY 원수익에 회귀하고 RF를 안 뺌 → alpha가 `RF·(1−β)`만큼 편향.**
- **통계**: 주간 5년 ≈ 260관측 → 알파 t-stat 검정력이 매우 낮음.
  **Newey–West HAC** 표준오차(`cov_type='HAC', maxlags=4`) 사용,
  **알파는 반드시 신뢰구간과 함께** — `α = +2.1%/yr [−4.8%, +9.0%]`.
  이 표기 하나가 "알파 있다" 착각을 가장 효과적으로 막는다.
- **모델 사다리** (핵심 도표): CAPM / FF3 / FF5 / FF5+UMD 4개 회귀의 α를 나란히.
  **α가 모델 추가마다 줄어드는 패턴**이 "알파가 아니라 틸트"의 시각적 증거.
  Alpha158+LightGBM은 모멘텀·리버설·변동성 피처가 대부분이라 UMD·저변동성 노출이 강하게 잡힐 가능성이 높다.
- **Brinson 섹터 귀인**: `Allocation = (w_p−w_B)·R_B`, `Selection = w_B·(R_p−R_B)`, `Interaction = (w_p−w_B)·(R_p−R_B)`.
  K=15~20 롱온리면 **섹터 집중이 성과의 대부분일 개연성이 크다.**

#### 강건성 · 레짐

**Purged / Embargoed CV — 알려진 결함의 표준 해법**
일간 샘플 + 5일 forward 라벨 → 인접 샘플 라벨이 시간 중첩 → 표준 KFold는 누출로 IS 성과를 부풀린다.
- **Purging**: 테스트셋 라벨과 시간이 겹치는 훈련 관측 제거 (5일 라벨이면 경계 양쪽 **최소 5거래일**)
- **Embargo**: 테스트 직후 구간(관례상 전체 T의 약 1%) 추가 제외
- **CPCV**: k폴드 중 p>1개를 테스트로 → **여러 백테스트 경로** 생성 → 단일 Sharpe가 아니라 **Sharpe 분포**
  (이 분포가 PBO의 입력이 되므로 두 기능은 파이프라인 공유)

> 설계 권고: **백테스트를 주간 샘플링으로 바꾸면 중첩 문제가 상당 부분 소멸한다.**

**Walk-forward**: Anchored(저빈도 권장) vs Rolling.
**Walk-Forward Efficiency = OOS 성과 / IS 성과** — 이 한 숫자를 run 카드에 박을 것. 0.5 미만이면 적색.

**레짐 분할**: pyfolio `interesting_periods.py`가 사전정의 구간을 코드로 보유
(Low Volatility Bull 2005–2007.8, GFC Crash 2007.8–2009.4, Recovery 2009.4–2013.1, New Normal 2013.1–).
여기에 이미 수동 검증한 **2022 약세장**을 정식 레짐으로 추가.
추가 축: 실현변동성 3분위, VIX 3분위, 벤치마크 드로다운 구간, 금리 레짐.
→ **레짐 매트릭스 테이블**(행=레짐, 열=[기간, 연율수익, IR, MDD, Rank IC, 베타, 알파]).
목표는 "이 전략은 회복장에서만 작동한다"를 한눈에 — 커밋 `3278dde`에서 손수 도달한 결론의 자동화.

**다중 시드**: 최소 5시드, 평균±표준편차 보고가 관례. 시드 수는 검정력 분석으로 결정.
GRU 4시드(커밋 `967a60c`)는 좋은 직관이지만 **자동화·상시화**돼야 함.
→ MLflow **nested run**(부모=설정, 자식=시드), 카드에 `IR 0.71 ± 0.23 (n=5 seeds)`,
설정별 박스플롯(겹치면 "차이 없음" 배너), **단일 시드 run에 `⚠️ 비교 근거로 사용 불가` 고정 배너**.

#### 라이브 vs 백테스트 괴리 모니터링 (핵심)

> 현 상태: 모니터링 전무. [src/execution/orderlog.py](../../src/execution/orderlog.py)가
> `execution_logs/rebalance_<date>.json`에 orders/skipped/placed/rejected를 남기는 것이 유일한 라이브 데이터 소스.

**3계층 괴리 분해 (설계 원칙)**

```
[A] 백테스트 페이퍼 수익   : 백테스트 가정(종가 체결, 가정 비용)
[B] 라이브 섀도우 페이퍼   : 실제 라이브 신호 · 실제 목표비중 · 종가 · 가정 비용
[C] 라이브 실현 수익       : 실제 체결가 · 실제 수수료 · 실제 보유

[A] − [B] = 신호/모델 열화 (alpha decay, 레짐)
[B] − [C] = 실행 결함 (슬리피지·수수료·미체결·라운딩·현금drag)
```

**이걸 안 하면 슬리피지 문제를 모델 문제로 오진하고 모델을 갈아엎게 된다.**
[B]는 소급 재구성이 불가능하므로 **첫 주문이 나가는 순간부터 기록**돼야 한다(§1-4).

**CUSUM — "전략이 죽었는가"의 통계적 판정**
Philips·Yashchin·Stein의 SPC 절차. Wald SPRT의 후향 버전으로 Moustakides(1986)에 의해
**주어진 오경보율에서 변화 탐지가 최속임이 증명**됨. 현재 3개 대륙 $500B+ 운용자산 모니터링에 사용.

```
0) 초기화: L₀ = 0, σ̂₀ = σ₀ (기대 트래킹에러)
1) 로그 초과수익:  eᵢ = ln((1+rᵢ)/(1+bᵢ))
2) 트래킹에러 갱신 (von Neumann, γ=0.9):
   σ̂ᵢ² = γ·σ̂ᵢ₋₁² + (1−γ)·(eᵢ − eᵢ₋₁)²/2
3) 현재 IR 추정:   ÎRᵢ = sqrt(12)·eᵢ / σ̂ᵢ₋₁      ← 분모에 σ̂ᵢ₋₁ (편향 방지)
4) Lindley 재귀:   L_N = max[0, L_{N−1} + 0.25 − ÎR_N]
5) L_N > h 이면 알람
```

k=0.25는 "좋은 매니저 IR=0.5"와 "나쁜 매니저 IR=0"의 중점. 임계치 h (관측 단위):

| h | IR=0.5(오경보)까지 | IR=0(플랫) 탐지 | IR=−0.5 탐지 |
|---|---|---|---|
| 11.81 | 24 | 16 | 11 |
| 17.60 | 48 | 27 | 18 |
| **23.59** | **84** | **41** | **25** |

논문 권장 h=23.59. t-검정 대비 **탐지 속도 10배**.

> **이 프로젝트 적용:** 테이블은 **관측 개수** 단위. 주간 리밸런싱이면 주간 초과수익을 관측 단위로 쓰고
> 연율화 계수 sqrt(12)→sqrt(52). h=23.59 → 오경보 84주(≈1.6년)당 1회,
> **플랫 성과 41주(≈9.5개월) 탐지, IR=−0.5는 25주(≈6개월) 탐지.**
> 더 민감하게는 h=17.60 → 오경보 48주, 플랫 27주.
> 전제는 주간 초과수익의 근사 무상관 — SPY를 제대로 잡으면 성립.
>
> ⚠️ **CUSUM은 인과를 설명하지 않는다. 알람은 자동 청산 신호가 아니라 조사 착수 신호다** (논문 강력 경고).
> 조사 결과 프로세스가 건전하면 오경보로 간주하고 리셋 후 재개.

**모니터링 지표 우선순위 (Carver)**
1. 실현 변동성 vs 기대치 → 2. **비용 vs 기대치** → 3. 왜도·평균이익손실비 → 4. **Sharpe는 맨 마지막, 가장 덜 중요**
(짧은 기간에서 분산이 가장 크기 때문)

| 타일 | 표시 | 경고 |
|---|---|---|
| ① 실현변동성 | `라이브 연율 18.2% / 백테스트 16.4% (+11%)` | ±25% 황색, ±50% 적색 |
| ② 비용 | `실현 41bp/회전 vs 가정 25bp (+64%)` | +50% 초과 적색 |
| ③ 왜도·손익비 | `skew −0.4 vs −0.2` | — |
| ④ Sharpe | 회색·작게, **CI 필수** `0.4 [−1.1, +1.9]` | **단독 적색 처리 금지** |

> 이 순서 자체가 반-자기기만 장치다. 대부분의 개인 프로젝트는 Sharpe를 맨 위 큰 글씨로 놓아 노이즈에 반응한다.

**신뢰 콘(Forecast Cone)** — pyfolio `forecast_cone_bootstrap`, `simulate_paths`,
`summarize_paths(cone_std=(1., 1.5, 2.))`, `plot_cones`, `show_perf_stats(live_start_date=..., bootstrap=True)`.
→ 자산곡선에 백테스트(회색)/라이브(파랑) + 1σ·1.5σ·2σ 밴드. 성과 비교 3열 테이블(Backtest/Live/All).

**드로다운 정상성 검정**: 라이브 MDD를 백테스트 수익의 **블록 부트스트랩**(자기상관 보존)으로
동일 길이 구간 1만 회 샘플링한 MDD 분포와 대조 → `현재 DD −14.2% = 78퍼센타일(정상)`.

**Chan의 킬 룰**: 드로다운 **기간**이 백테스트 최대 DD 기간에 근접하면 축소/중단.
"쇠퇴가 얼마간 지속되면 회복되는 일은 드물다." → 타일 `DD 지속 11주 / 백테스트 최대 19주 (58%)`.

**실행 결함 계층 — $700 고유 리스크 (최대 괴리 원인일 가능성)**
포지션당 약 $35~47. **라운딩 오차가 목표비중 대비 수십 %**가 될 수 있음.
→ **가중치 오차 지표 `weight_error_L1 = Σ|w_live − w_target|`를 반드시 모니터링.**
슬리피지보다 훨씬 큰 항일 가능성이 높다. 여기에 미체결/스킵의 기회비용, 라운딩 잔여 현금 drag가 더해진다.

**괴리 워터폴 (핵심 위젯)**
`백테스트 주간수익 X%` → `−신호열화` → `−가중치오차(라운딩)` → `−스킵/미체결 기회비용`
→ `−슬리피지` → `−수수료/환전` → `−현금drag` → `라이브 실현 Y%`. 누적 및 주차별 둘 다.

**슬리피지 민감도 곡선**: 비용을 0/10/25/50/100bp로 놓고 백테스트 재실행 시 Sharpe.
pyfolio `plot_slippage_sweep`/`plot_slippage_sensitivity` 참고.
**"내 엣지는 몇 bp에서 사라지는가"를 한 숫자로.**

**신호 레벨 조기경보 (P&L보다 빠름)**
매주 지난주 예측 점수 vs 실현 5일 수익의 유니버스 Rank IC 계산 → 백테스트 IC의 5/50/95 퍼센타일 밴드 오버레이.
**IC에도 CUSUM 적용** → P&L CUSUM보다 먼저 울리는 경보.
신호는 맞는데 실행이 나쁜 경우(IC 정상, P&L 부진)와 신호가 죽은 경우(IC 붕괴)를 즉시 분리해준다.

**발사 시점 편향 경고**
1,726개 구조화 전략의 마케팅 백테스트 vs 실제 라이브 성과 연구:
백테스트는 주로 **런칭 직전에 존재하던 공통 팩터 레짐**을 포착할 뿐 전략 고유 스킬이 아니며,
**극단적 팩터 랠리 직후 런칭일수록 백테스트를 더 크게 할인**해야 한다.
→ 라이브 시작 시 1회: `개시 시점 직전 12개월 SPX 수익 = 상위 15퍼센타일 → 기대치를 보수적으로 할인할 것`.

**알람 룰 (전부 숫자로 고정)**

| 조건 | 등급 | 액션 |
|---|---|---|
| CUSUM L > 17.60 | 황색 | 조사 착수 |
| CUSUM L > 23.59 | 적색 | 조사 + 익스포저 축소 검토 |
| 실현 vol이 기대 대비 ±50% | 적색 | 포지션 사이징 점검 |
| 실현 비용 > 가정 비용 × 1.5 | 적색 | 백테스트 비용모델 재보정 |
| 라이브 MDD > 백테스트 부트스트랩 MDD 95퍼센타일 | 적색 | 분포 이탈 |
| DD 지속기간 ≥ 백테스트 최대 지속기간 | 적색 | Chan 룰 — 중단 검토 |
| 12주 롤링 Rank IC < 백테스트 IC 5퍼센타일 | 황색 | 신호 열화 의심 |
| 가중치 오차 L1 > 0.15 | 황색 | 실행 로직 점검 |
| 라이브 곡선이 −2σ 콘 이탈 | 황색 | — |

#### 실험 관리 (MLflow)

Qlib Recorder = MLflow (`qlib/workflow/expm.py::MLflowExpManager`). 이미 깔려 있다.
**애드혹 스크립트 stdout을 MLflow 메트릭으로 옮기는 것만으로 비교가능성이 확보된다** —
현 `analyze_capm.py`는 결과를 print만 하고 끝나므로 beta/alpha/R²를 원본 run에 `log_metrics`로 되먹여야 한다.

**로깅 대상**
- params: `git_commit`(+dirty 여부 태그), `data_snapshot_hash`(qlib bin + universe csv 해시),
  `seed`, `label_horizon`, `purge_days`, `embargo_pct`, train/valid/test 구간,
  `topk`, `n_drop`, `rebalance_freq`, **비용모델(`open_cost`/`close_cost`/`min_cost`/`deal_price`)**,
  `benchmark`, 유니버스 정의, `requirements.txt` 아티팩트, `OMP_NUM_THREADS`
  (OpenMP 충돌 이력이 있어 특히 중요)
- metrics: `is_*`/`oos_*`/`live_*` **접두사 강제**, `*_rank_ic`, `*_rank_icir`, `*_ann_return`, `*_ir`,
  `*_mdd`, `*_turnover`, `capm_beta`, `capm_alpha_ann`, `capm_alpha_t`, `ff5_alpha_ann`, `ff5_alpha_t`,
  `dsr`, `pbo`, `n_trials_at_run`, `wf_efficiency`, 시드 집계(`ir_mean`, `ir_std`, `n_seeds`)
- 구조: 설정 = 부모 run, 시드 = **nested child run**

**승격 게이트** (통과 시에만 레지스트리 등록)

```
Gate 1: OOS Rank ICIR > 0.3        (시드 평균)
Gate 2: DSR > 0.95                  (현재 누적 N 기준)
Gate 3: PBO < 0.20                  (개인 프로젝트 현실 기준; 논문 관례 0.05)
Gate 4: 시드 표준편차 < 평균의 50%
Gate 5: 모든 레짐에서 IR > 0 (또는 실패 레짐이 명시적으로 문서화됨)
Gate 6: 가정비용 2배에서도 IR > 0   (슬리피지 민감도)
```

통과 시 `Staging` → 1개월 페이퍼 → `Production`.
**[scripts/live/rebalance.py](../../scripts/live/rebalance.py)는 모델 파일 경로가 아니라 레지스트리 버전으로 로드**하고,
그 버전 문자열을 원장에 기록. 그래야 "이 주문은 어느 모델이 냈나"를 되짚고 괴리 분해를 모델 버전별로 할 수 있다(§1-7).

---

## 5. 명시적 SKIP — 만들지 말 것

근거를 갖고 배제한 항목. 목록만큼 가치 있다.

| 항목 | 이유 |
|---|---|
| VWAP / interval VWAP TCA | 주문을 쪼개지 않는 시장가 단발. 벤치마크가 의사결정을 바꾸지 않고 분봉 데이터 비용만 발생 |
| Market impact 분해 (temporary/permanent) | $70 주문의 임팩트는 측정 한계 이하 |
| **자동 손절 청산 / loss-limit kill** | long-only 현물은 강제청산이 없다. 자동 청산은 확정 비용 20bp를 실현시키고 저점매도를 고착. **알림만** |
| 자동 청산형 safe state | 위와 동일. safe state는 flat이 아니라 **frozen** |
| 정교한 자동 포지션 사이징 서브시스템 | Freqtrade Edge 모듈 **제거** 전례 |
| 호가창 기반 주문가 최적화 | Freqtrade가 "increased risk without benefit"으로 제거 |
| WebSocket 실시간 스트리밍 | 주간 케이던스 |
| 멀티유저 인증(JWT/OIDC), 공개 포트폴리오 공유 | 단일 사용자. Freqtrade: REST API를 인터넷에 노출하지 말 것 |
| 멀티봇 오케스트레이션, DEX gateway, 레버리지/숏 제어 | 롱온리 단일 전략 |
| **배당 세무 기능** | 현지 15% 원천징수로 납세의무 종결. 종합과세 2,000만원 기준 대비 무의미 |
| FIRE 계산기 | $700 규모에서 무의미 |
| Credit/capital threshold 엔진 | 현금계좌 long-only는 자본 초과가 구조적으로 불가. 브로커가 이미 거부 |
| Drop copy 대사, fund admin 3-way 대사 | 리테일 API에 독립 체결 피드 없음. 당사자가 브로커 하나뿐 |
| CAT/OATS 규제 리포팅 | 브로커-딜러 의무. 개인 대상 아님 |
| ms/ns 타임스탬프, WORM 물리 저장소 | 주간 배치. 초+단조 seq, SQLite 트리거+백업으로 충분 |
| Self-match prevention 엔진, message throttle 프레임워크 | 단일 계좌·주당 수십 건. netting 한 줄 / 토큰버킷 하나로 충분 |
| DR/BCP, 이중화, co-location, 레이턴시 측정 | 주간 리밸런싱은 하루 연기 가능. **DB 백업만** 남김 |
| 리스크 기능 조직 분리, 연례 CEO 인증 | 1인. 한도 config 변경을 코드 배포와 시간 분리하는 것으로 근사 |
| Automated market abuse surveillance | $70 주문으로 시세조종 불가 |
| Buying power 실시간 재계산, Reg T/margin | 실행 직전 1회 조회로 충분. 현금계좌 long-only |
| config와 코드 양쪽에 리스크 규칙 이중 정의 | Freqtrade가 `protections`를 config에서 걷어내고 코드로 일원화한 전례 |
| HMM 기반 자동 레짐 탐지 | 개인 프로젝트 규모에선 과잉. 사전정의 레짐으로 충분 |

---

## 6. UNVERIFIED — 확인 필요 (추측 금지)

| # | 항목 | 상태 | 확인 방법 |
|---|---|---|---|
| U1 | **토스의 취득가액 산정 방식 (FIFO vs 이동평균)** | 미확인 | 고객센터 문의 또는 실거래 후 계산보조자료 대조. 불일치 시 매년 어긋남 |
| U2 | **환전수수료의 필요경비 인정 여부** | **미확인 — 추측 금지** | NTS 서식은 "수수료·증권거래세 등"이라 하나 환전수수료 명시 예규 미발견. 보수적으로 **제외** 권장. 세무사 확인 |
| U3 | 토스 앱의 통합증거금 적용 여부 및 OpenAPI 경로 동작 | 미확인 (공식 페이지 JS 렌더링으로 크롤링 실패) | 토스 문의. 단 **API에 환전 엔드포인트가 없다는 사실은 확정** |
| U4 | 토스 환전 스프레드의 정확한 편도/왕복 정의 | 부분 확인 | 실측 0.03% 신뢰. `fx_conversions.spread_bps` 실측 로깅으로 상시 검증 |
| U5 | 개인 환차익 비과세의 NTS 1차 출처 | PARTIALLY VERIFIED | 소득세법 열거주의상 결론은 견고하나 공식 URL 미확보 |
| U6 | 한국은행 ECOS 매매기준율 통계코드 | 미확인 (`731Y001`은 외환보유액 — 오답) | ECOS 통계검색에서 직접 확인. **서울외국환중개 직접 수집이 더 정확** |
| U7 | ISIN 조달 경로 | 미해결 | 토스 API 미제공. 대안: 신고 시 "발행법인 소재 국가명(미국)" 기재 허용 → **ISIN 없이도 신고 가능** |
| U8 | **토스 `settlementDate`가 국내기준(T+2)인지 현지기준(T+1)인지** | 미확인 | 첫 실거래 후 실제 USD 예수금 입금일과 대조. **원장 정확성의 핵심 검증점** |
| U9 | 소수점 주식 매도 시 원가 배분 규칙 | 미확인 | 소수 로트 FIFO 소진이 증권사 계산과 일치하는지 실측 |
| U10 | **수수료 0.10%에 최소 수수료가 붙는지** | 미확인 | $70 주문에 최소 $1이 붙으면 실효 비용 급등. 첫 체결의 실제 수수료를 명목과 대조 |
| U11 | 미국 배당 W-8BEN 제출 방식 (토스 일괄 처리 여부) | 미확인 | 통상 국내 증권사 일괄 처리. 실무 영향 미미 |

---

## 7. 아키텍처 신호

조사에서 나온 가장 강한 단일 신호는 기능이 아니라 **구조**다.

**Hummingbot이 Streamlit 기반 Dashboard를 deprecated 처리하고 Condor로 재편했다.**
대체 구조는 *Hummingbot API를 "deterministic infrastructure"로 두고,
그 위에 Telegram 봇 / 웹 대시보드 / 에이전트를 얇은 클라이언트로 얹는* 형태이며 세 표면이 상태를 동기화한다.

현 [scripts/dashboard/app.py](../../scripts/dashboard/app.py) 417줄을 "앱"으로 키우려면:

> **로직을 뷰 안에 넣지 말고 별도 core 모듈에 두고, 모든 UI를 그 위의 얇은 클라이언트로 취급한다.**
> 그래야 cron·CLI·웹 UI·Telegram이 같은 로직을 재사용한다.

**이 신호는 "Streamlit을 유지하라"가 아니라 정확히 그 반대다.** Hummingbot은 Streamlit 대시보드를
**버렸고**, 조사 전체 어디에도 Streamlit을 권하는 근거는 없다.
core 경계만 서면 **뷰 스택은 자유다** — Streamlit이든 React든 Telegram이든 전부 그 위의 클라이언트다.
핵심은 스택 선택이 아니라 **선택을 되돌릴 수 있는 상태로 만드는 것**이고, 그게 core 분리의 목적이다.

부수 근거:
- [ledger-design.md](../project/ledger.md) §연결/동시성의 "라이터는 단일(runner/스크립트), 대시보드는 리더" 가정이
  승인·kill·M/X 토글 등 쓰기 기능 도입 시 깨진다. core 모듈이 단일 라이터를 유지하면 이 가정이 보존된다.
- Ghostfolio는 무거운 집계를 요청 시점이 아니라 **백그라운드 스냅샷으로 미리 계산**한다.
  Streamlit의 전체 재실행 모델과 정면 배치되는 설계.
- 원격 사용은 웹 노출이 아니라 **Telegram / SSH 터널**이 정석 (Freqtrade 문서 권고).

**정보구조 관점:** 현 대시보드는 "백테스트 1개 보기"인데,
조사된 스펙의 무게중심은 전부 **분포와 비교**에 있다 —
단일 백테스트 vs 시행 분포, 라이브 vs 백테스트 콘, 시드 vs 시드, 레짐 vs 레짐.
**"run 하나 렌더" → "run 집합 + 라이브 스트림"** 으로 바꾸는 것이 실질적 리팩터링 포인트.

---

## 8. 【2차】 실전 실패 모드 — 1인칭 사고 기록

> **조사 품질 선언 (먼저 읽을 것)**
> - `reddit.com`은 크롤러 차단 → **r/algotrading 근거는 이 조사에 없다.**
> - 이 주제 검색 공간의 대부분이 SEO 스팸(봇 판매 블로그)이다. **신뢰할 1급 1인칭 자료는 3건**뿐이었고,
>   나머지는 프레임워크 GitHub 이슈와 증권사 공식 문서로 보강했다.
> - ⚠️ *"2025 Stanford study, 58% of retail algo strategies collapse within 3 months"* 라는 수치가
>   여러 마케팅 블로그에 돌아다니는데 **원 출처를 찾지 못했다. 인용하지 말 것.**
>
> 핵심 자료:
> **[A]** florinelchis, *Production Trading Bots: 15 Failure Patterns Nobody Warns You About* —
> 크립토 봇 4쌍, cron 구동, SQLite, 소액. **버그 17건 · 실패 주문 8,000건 · 28일 무음 · 실현이익 $3.25.** 구조적으로 가장 유사한 사례.
> **[B]** Concretum Group, *Operational Pitfalls of Algo Trading* — IBKR 실운용 1인칭 사고 기록.
> **[C]** nautechsystems/nautilus_trader GitHub 이슈 — 실계좌 운용자들의 정합성 붕괴 신고.

### 8-1. 확인된 항목 (외부 1인칭 근거 있음)

| 항목 | 근거 | 등급 |
|---|---|---|
| **write-ahead intent (HTTP 호출 *전* DB 커밋)** | [A] #7 — 쿨다운이 *성공한* 거래만 확인. 실패 주문은 기록이 안 남아 즉시 재시도. **60분 쿨다운인데 몇 분 안에 3연속 매수 체결.** 처방이 문자 그대로 일치: *"Record attempts to database before API calls, not after."* | **최상** |
| **원장⇄브로커 대사 + break 시 차단** | [A] #4 — 매수는 `status='open'`인데 매도 시 갱신 누락 → **몇 달 뒤 "246 rows with status='open'", 실제 포지션은 42개.** 유령 포지션이 쿨다운 로직을 걸어 **모든 매수를 몇 달간 차단**. / [B] — *"reconciling against broker execution records on every restart — **not optional**"* / [C] 이슈 4건 | **최상** (5개 독립 출처) |
| **무음 실패 경보** | [A] #15 — *"Cron showed green, logs were filling, no exceptions were raised — and the bot was doing nothing economically useful."* **28일 무음, 그 사이 실패 매수 8,000건** | **최상** |
| **사전 notional·건수 한도** | [A] #13 — 6주 하락장에서 매수 신호 ~50회, USD 잔고 $44 → $0.83, 이후 **28일간 8,000건 실패 주문**, 봇 4개 전부 정지 | **중간** |
| **코어/뷰 분리** | [A] #11·#12 — 모니터링이 코드 디렉터리 DB를, 봇은 런타임 디렉터리 DB를 봐서 **정상 작동 중인 봇 3/5개가 "error — no such table"로 표시.** 별건: `check_pnl.py`가 **3주 묵은 하드코딩 가격**으로 계산했는데 출력이 실시간과 구분 불가 | **중간~강함** |
| **결제·환전 필드 (한국 특수)** | 증권사 공식 문서(미래에셋·메리츠·신한 통합증거금): *"결제일 당일 오전 6시 20분경 최근일 기준환율로 **가환전**되며, 국내 영업일 오전 09시30분경 실시간 환율로 **정산**하여 차액을 입/출금"*, 환율 급변 시 **원화 미수금 + 연체료 14%** | **1차 권위 문서** |

> **중요한 반례 — 자동 치유형 대사는 하지 말 것.**
> [C] 이슈 #3176: 불일치를 **자동으로 봉합하려던** 로직이 랜덤 UUID synthetic 주문을 만들고(원본과 타입도 불일치, MARKET→LIMIT)
> 재시작마다 중복을 누적시켰다. 보고자 표현: *"the reconciliation system is meant to prevent state corruption, but is actually creating it."*
> → **"breaks에 적재하고 차단만 한다(자동 치유 안 함)"는 설계가 옳다.** 이 방향으로 기능을 키우지 말 것.

> **헬스체크 지표 재정의 필요.** [A] #15 사례에서 **실행 자체는 매번 성공했다.**
> "마지막 성공 실행 이후 경과시간"으로는 못 잡는다. **"의도한 경제적 행위"** 를 지표로 삼아야 한다
> — 리밸런싱 주에 주문 0건, 미결 주문 나이, 잔고 최저선 미달, 고아 포지션 수.

### 8-2. 외부 근거를 찾지 못한 항목 (지어내지 않음)

| 항목 | 상태 |
|---|---|
| `arrival_px` / `decision_px` | 소매 1인칭 근거 **0건**. TCA는 기관 개념. → §1-A의 point-in-time 논거로만 정당화됨 |
| `git_commit` + 모델 버전 | 트레이딩 맥락 1인칭 근거 **0건**. 일반 MLOps 상식 (단 원가 1줄) |
| `lots` (세금 로트) | **0건** |
| `control_state` | **0건**. 킬스위치 구현 세부에 가까움 |
| **preflight 10게이트 + 인간 승인** | **지지 근거 0건. 오히려 반대 근거 존재 → §8-4** |
| 킬스위치 UI 승격 / `frozen` vs `flat` / 재활성화 사유 강제 | 필요성 자체는 Knight Capital(**기관 사례**)뿐. 세부 설계는 **전부 합리적 추론이지 검증된 것이 아니다** |
| `skipped` reason_code enum | 1인칭 근거 **0건**. 단 [A] #4·#9가 "왜 거래가 안 됐는지 몰라 몇 달/25시간 방치"였으므로 **간접 지지** |
| 섀도우 페이퍼 포트폴리오 | **1인칭 근거 0건.** 개념을 정확히 서술한 유일 자료가 **자사 플랫폼 마케팅 콘텐츠**이며 실운용 주장·수치 없음 |
| `unknown` 상태 | 트레이딩 실전 사례 **0건**(일반 분산시스템 idempotency 글만 존재) |

### 8-3. ⚠️ 빠진 실패 모드 — 빈도순 (1차 조사가 통째로 놓친 영역)

1차 조사가 뽑은 항목은 **전부 *주문을 낸 뒤* 무엇을 기록·대조할지**에 집중돼 있다.
**주문을 내기 전에 데이터가 신선한가 / 오늘이 거래일인가 / 수량이 규격에 맞는가**를 검사하는 항목이 하나도 없다.
**1인칭 사고 빈도로는 이쪽이 대사보다 잦다.**

| 순위 | 실패 모드 | 사고 기록 |
|---|---|---|
| 1 | **데이터 신선도·무결성 무음 붕괴** | [B] *"시스템이 오전 11시에 멈춘 가격으로 몇 시간 동안 거래했다"* — 연결 정상, **에러 없음**. / [A] #6 — 복붙 후 find-and-replace가 SQL `UNIQUE`를 `XRPQUE`/`ETHQUE`로 파괴, SQLite가 조용히 제약 무시 → **캔들 47%·51% 중복, 몇 달간 모든 지표가 틀림** (34,806행 중복제거 마이그레이션) |
| 2 | **수량·금액 정밀도** | [A] #2 — `round(1.50/2274.00, 2)` → **`0.0`**(필요값 0.00066). **68건 연속 거부, 몇 주간 해당 종목 거래 0건.** 종목마다 증상이 달라 발견이 늦음 → **소수점/USD 금액매수를 쓰는 이 프로젝트에 직격** |
| 3 | **거래 캘린더·조기폐장·DST·시계 드리프트** | [B] 별개 사고 4건 — 추수감사절·크리스마스 이브 13:00 조기폐장에 하드코딩 16:00 로직이 **조용히** 붕괴(지표가 미완성 세션으로 계산, MOC 주문이 폐장 몇 시간 뒤 발사) / DST 전환으로 연 2회 약 2주간 스케줄 1시간 이동, **경고 없음** / 서버 시계 드리프트로 15:49:55 예약이 15:50:02 도착해 거부. 처방: **캘린더 동적 조회 + `America/New_York` 고정 + NTP** → **한국↔뉴욕 + 미국DST + 양국 공휴일 4중 조합** |
| 4 | **비용 모델이 실제와 다름** | [A] #1 — 문서상 0.04%/0.075% → **실제 0.50%/0.25%, 6~12배.** 몇 주간 모든 거래가 손실. 처방: **문서가 아니라 실제 체결 이력에서 수수료를 역산하고 관측 최악값을 상수로 쓸 것** |
| 5 | **모든 대기 상태에 최대 체류시간 없음** | [A] #9 — 미체결 주문 1건이 pending 파일을 물고 **25시간 파이프라인 전체 정지(cron 1,500 사이클).** 그 사이 Williams %R −93(극단 과매도) 신호가 stale pending 때문에 무시됨 |
| 6 | **브로커 응답값 미검증** | [A] #8 — 체결이 `filled_quantity = 0.0`으로 도착 → 0으로 나눔 → **하룻밤 537회 크래시, 8시간+ 마비** |
| 7 | **비원자적 쓰기** | [A] #3 — JSON flush 도중 크래시 → 부분 JSON → `JSONDecodeError` **"every minute. Forever."** 무한 재시도. (SQLite 트랜잭션으로 대부분 해결되나, "HTTP 호출 전 커밋"이 별도 커밋이면 크래시 창이 정확히 여기 생긴다) |
| 8 | **자본 하한 / 최소 주문금액** | [A] #13 — 잔고 $0.83에서 8,000건 실패. 1차 조사의 한도는 **상한만 있고 하한이 없다** |
| 9 | **체결이 몰아서 들어옴** | [A] #14 — GTC 매도 6건이 **3초 안에 동시 체결.** 사이클마다 모든 pending을 순회하지 않으면 5건이 잘못 남는다 → **대사는 배치 전체를 순회해야지 첫 불일치에서 멈추면 안 된다** |
| 10 | 기업행위(분할·배당·티커 변경) | 근거 **약함**. 1인칭 사고 기록 없음, 벤더 문서가 "수동 오버라이드하라"고 제품 한계를 명시한 정도 |
| 11 | 한국 특수 — 원화 미수금 | T+2 결제 전 원화 부족 시 **해외현금 미수 → 연체료 14%.** 가환전 후 익영업일 재정산에서 **잔고가 사후에 줄어든다** → "주문 가능 현금"을 보수적으로 계산하는 방법이 어디에도 없음 |

### 8-4. ⚠️ OVER-BUILT 경고 — 인간 승인 게이트에 대한 반대 근거

> 정직하게: *"내가 X를 만들었는데 한 번도 안 썼다"* 류의 구체적 1인칭 회고는 **거의 찾지 못했다.**
> 실패보다 더 쓰이지 않는 종류의 글이다. 아래가 찾은 전부다.

**(1) 인간 개입이 전략 성과를 훼손한다 — 직접적인 반대 근거**

HN 1인칭, 알고리즘 트레이딩으로 $100k 손실:
> ***"I didn't trust the algorithm, and would cut the trades short instead of waiting for the full profit (or loss). That messed with my results."***

두 번째 계정(~$10k 손실)도 동일 패턴 — 감정이 거래를 중단시켜 설계 대비 미달.

**해석:** "주문 전 명시적 인간 승인"은 이 실패 모드를 **제도화**한다.
매주 화면 앞에서 승인 버튼을 누르는 사람은 결국 하락장에서 승인을 안 누르게 된다.
그러면 라이브 실적이 전략의 실적이 아니게 되고 — **섀도우 분해(신호붕괴 vs 집행결함)가 무력화된다.**
승인 게이트와 섀도우 분해는 서로를 갉아먹는 조합이다.

> **권고:** 승인은 유지하되 **binary(전량 실행 / 전량 중단)로 제한**하고,
> 종목별 취사선택·수량 조정은 **불가능하게 만들 것.**
> 중단을 누를 때마다 **사유를 기록**해 "내가 몇 번 개입했는가"를 감사 가능하게 할 것.
> **개입 자체가 측정 대상이어야 한다.**

**(2) 백테스터 과투자.** 같은 HN 사례자는 *"my own multi-threaded backtester, working on hundreds of gigabytes of data"* 를 직접 만들었다.
손실 원인은 백테스트 품질이 아니었다. **정교한 오프라인 인프라가 라이브 실패를 전혀 막지 못했다.**

**(3) 자동 치유형 대사** — §8-1 인용 참조.

### 8-5. 빈도표 (독립 출처 수)

| 실패 모드 | 출처 | 등급 | 1차 조사 커버 |
|---|---:|---|---|
| 원장⇄브로커 포지션/현금 불일치 | 5+ | 1인칭 사고 | ✅ |
| **무음 실패 — 예외도 에러도 없는데 잘못 동작** | 5 | 1인칭 사고 | ❌ **없음** |
| 봇이 "돌아가는 것처럼 보이는데" 경제적으로 아무것도 안 함 | 3 | 1인칭 사고 | ⚠️ 지표 재정의 필요 |
| **데이터 신선도/무결성 붕괴** | 3 | 1인칭 사고 | ❌ **없음** |
| **시간대·캘린더·DST·시계 드리프트** | 4 | 1인칭 사고 | ❌ **없음** |
| 대기 상태 타임아웃 부재로 파이프라인 정지 | 3 | 1인칭 사고 | ⚠️ 부분 |
| 실패 주문 미기록 → 중복/재시도 폭주 | 2 | 1인칭 사고 | ✅ |
| 모니터링이 코어와 다른 진실을 봄 | 2 | 1인칭 사고 | ✅ |
| **인간 개입이 성과 훼손** | 2 | 1인칭 사고 | ⚠️ **반대 근거** |
| 실제 수수료 ≠ 문서상 수수료 | 2 | 1인칭 사고 | ⚠️ 부분 |
| 수량 반올림·정밀도로 주문 무효화 | 1 | 1인칭 사고 | ❌ **없음** |
| 브로커 응답값 미검증 크래시 | 1 | 1인칭 사고 | ❌ 없음 |
| 비원자적 쓰기로 상태 손상 | 1 | 1인칭 사고 | ❌ 없음 |
| 자본 하한 미달 | 1 | 1인칭 사고 | ❌ 없음 |
| 자동 대사 보정이 상태를 더 망가뜨림 | 1 | 1인칭 사고 | ✅ 회피 |
| 원화 결제/가환전/미수 (한국) | 3 | 1차 권위 문서 | ✅ |
| 킬스위치 부재로 폭주 | 1 | **기관 사례** | ⚠️ 약함 |
| 섀도우/페이퍼 병행 비교 | 1 | **마케팅 콘텐츠** | ⚠️ **최약** |

---

## 9. 【2차】 go-live 최소요건과 범위 규율

### 9-1. 권위 있는 출처가 실제로 요구하는 것

**FINRA Regulatory Notice 15-09** — 배포 전 요건을 가장 구체적으로 열거:
개발과 분리된 **독립 테스트**, *"최소한의 단계로 알고리즘을 신속히 중단시키는 수단"*(kill switch),
코드 변경 추적·승인 프로토콜(change management), **문서화된 전략 요약**,
그리고 ***"제한된 규모의 pilot phase로 배포하고 결과가 확인되는 만큼만 증액"***, 배포 직후 heightened scrutiny.

**FIA (2024-07)** — 통제를 이름으로 못 박음: §1.1 Maximum Order Size
(*"주문 크기 한도가 설정되지 않은 경우 시스템은 주문 자체를 막아야 한다"*), §1.2 Maximum Intraday Position,
§1.3 Price Tolerance, §1.4 Cancel-On-Disconnect, §1.5 Kill Switches, §4.1 Drop Copy Reconciliation, §4.2 일일 손실 한도.

**Robert Carver, pysystemtrade `docs/production.md`** — 이 목록 중 **유일하게 개인 트레이더가 실제 운영하는 1차 문서**:
일별 스케줄 프로세스, 3계층 주문 스택, **정기 스케줄이 주문 스택을 다시 훑어 새 체결을 잡는 백업 경로**,
reconciliation·P&L·status·trade·risk 리포트, 가격 스파이크 경보, position/trade limit,
***"백업 머신을 진지하게 고려하라 — 1시간 내 라이브 전환 가능해야"***, DB 덤프·CSV 백업.

**Kevin Davey** — 라이브 전환을 수치로 말하는 거의 유일한 실무자:
walk-forward → Monte Carlo → **실시간 인큐베이션 6~12개월(실제 돈 없이)**.
학생 설문에서 85~90%가 인큐베이션 덕에 나쁜 전략을 걸렀거나 좋은 전략을 확인했다고 응답.

> **중요한 공백:** 소액 참여자에 대한 **브로커·거래소 인증·컨포먼스 요건은 존재하지 않는다.**
> FIA §5.1의 conformance testing은 "거래소 대면 소프트웨어 인터페이스를 배포하려는 참여자"에게 적용되고,
> **SEC Rule 15c3-5는 통제 의무를 브로커-딜러에게 지운다 — 고객은 규칙의 대상이 아니다.**
> 토스증권도 API 사용자 사전 인증 절차가 공개돼 있지 않다.
> **→ 라이브 전 항목 중 규제·브로커가 강제하는 것은 하나도 없다. 전부 자발적 선택이고, 비용/편익으로만 정당화된다.**

> **근거를 찾지 못해 비워둔 영역:** Ernest Chan의 페이퍼트레이딩 기간·라이브 전환 인프라 1차 텍스트(접근 403, 2차 요약만 존재 → 인용 안 함),
> Andreas Clenow의 go-live 인프라 공개 발췌(검색되지 않음).

### 9-2. 빠진 것 — go-live 문헌이 요구하는데 1차 조사에 없던 것

**(a) forward test 기간과 합격 기준이 없다.** 기록 장치는 있는데 "얼마나 오래, 무엇을 측정해서, 무엇이 통과인가"가 없다.
Davey 기준 6~12개월인데 **주간 리밸런싱이면 6개월 = 리밸런스 26회**뿐이다. → 합격 기준은 §9-4 참조.

**(b) 자본 램프업 스케줄이 게이트로 없다.** FINRA 15-09가 명시 요구하는 pilot phase.
**흥미롭게도 [qlib-toss.md](../project/roadmap.md) L22에 이미 "백테스트 → 앱 모의투자 → 1주 스모크 → 소액 실전"이라 적혀 있다.
로드맵이 자기 문서에 있는 규율을 릴리스 항목으로 승격하지 않았을 뿐이다.**

> **샌드박스 부재의 함의가 뒤집힌다.** 보통 "샌드박스가 없으니 내부 페이퍼트레이딩을 크게 지어야 한다"로 읽히는데,
> 실측값을 보면 반대다. **최소주문 ≤$1, 소수점 가능, $1 체결 시 commission $0.**
> **$1짜리 진짜 주문이 어떤 시뮬레이터보다 정확하고 거의 공짜다.**
> 게다가 섀도우 포트폴리오는 원리적으로 체결·슬리피지를 측정할 수 없다 —
> 시뮬레이션은 통상 주문이 호가 큐 맨 앞에 있다고 가정해 **체결을 과대평가한다.**
>
> → **램프: $1 스모크(전 종목 1회전) → $50 → $200 → $700.**
> 각 승급 조건은 *"대사 break 0 + 무음실패 0 + 비용이 예산 내"* 를 N회 연속.
> 섀도우는 이 램프와 **병렬로** 돌려 이론 성과와의 차이를 축적하는 용도.

**(c) 계좌 단위 손실 한도가 없다.** 주문당 notional 한도만 있다. FIA §4.2는 일별 포지션/손실 한도를 별도 요구.
주문 하나하나가 작아도 매주 전량 회전하면 계좌는 갈려나간다. **equity floor는 코드 3줄.**

**(d) 백업·복구가 전무하다.** Carver가 굵게 강조하는 항목. M1 Air 1대에서 미체결·미대사 상태로 죽으면 복구 경로가 없다.

**(e) 롤백 런북이 없다.** 봇이 잘못 샀을 때 무엇을 하는가. 자동매매에서 되돌리기는 코드가 아니라 **사람이 앱에서 파는 것**이다. 문서 반 장.

**(f) 문서화된 전략 요약이 없다.** FINRA 요구 항목. 1인 개발자에게도 **6개월 뒤의 자신이 감독 인력**이다.

**(g) 독립 테스트가 구조적으로 불가능하다.** 1인 개발자는 FINRA의 "코드 개발과 독립적으로 수행"을 만족시킬 수 없다.
현실적 대체물은 **실제 브로커 응답을 녹화해 고정 픽스처로 회귀 테스트**하는 것이고,
Phase 0에서 실주문 응답을 이미 확보했으므로 **자산이 있다.**

### 9-3. 회복불가 주장 — 판정

**원리는 참이지만 1차 조사가 주장한 범위는 과장이다.** 상세는 §1로 이관(정정 완료).
요지: 진짜 회복불가는 **결정 이벤트 로그 하나**이고, 그 안의 arrival price·skip code·git sha·타임스탬프 뿐이다.

반대편 가드레일도 있다 — Google SRE:
*"거의 사용되지 않는 데이터 수집과 알림 설정은 제거 대상이다.
어떤 대시보드에도 노출되지 않고 어떤 알림에도 쓰이지 않는 시그널은 제거 후보다."*

### 9-4. ⚠️ 결정적 재계산 — 라이브 성과로는 엣지를 검증할 수 없다

Lo (2002), *The Statistics of Sharpe Ratios*:

```
SE(SR) ≈ √( (1 + SR²/2) / T )
```

> **연율 SR=0.5 전략을 t=2로 확인하려면 약 16년의 라이브 데이터가 필요하다.**
> 6개월 forward test(리밸런스 26회)의 t값은 **약 0.35.**

**즉 forward test는 엣지를 검증할 수 없다. 배관(plumbing)만 검증할 수 있다.**

이것이 §4-4의 라이브 모니터링 스펙 전체(CUSUM·rank-IC 조기경보·레짐 매트릭스·귀인 사다리)에 대한 판정이다.
주간 리밸런싱 라이브 1년 = **52관측**. 이 도구들이 신호를 낼 표본에 도달하려면 수년~수십 년이다.
**그 전까지 이들이 내는 건 신호가 아니라 노이즈이고, 노이즈에 반응해 전략을 손대는 것이
정확히 López de Prado가 경고하는 실패 경로다.**

**합격 기준은 수익이 아니라 배관으로 정의해야 한다:**
> *12회 연속 리밸런스에서 대사 break 0건, 무음 실패 0건,
> 실현 비용이 백테스트 가정의 ±50% 이내, 목표 비중과 실제 비중의 괴리 < X%.*

**순서 재배치가 따라온다:**

| 이동 | 항목 | 이유 |
|---|---|---|
| 모니터링군 → **라이브 전** | **비용·회전율 예산 1회 계산** | 실측 0.10%/편도 + FX 3bp + 주간 리밸. **연 3%대 비용 드래그 추정**(회전율 가정 의존 — 백테스트 회전율로 확정 필요). $700에서 이건 대시보드 주제가 아니라 **전략을 돌릴지 말지의 go/no-go 입력** |
| 조건부 → **라이브 전** | **PBO/CSCV 1회** | 라이브로 엣지 검증이 불가능하므로 **과최적화를 판정할 수 있는 유일한 시점이 백테스트 단계**다. 상시 시스템이 아니라 1회 계산이라 비용도 작다. 조건부 최하위에 둔 것은 **배치 오류** |
| 조건부 → **무기한 연기** | 세무 대시보드 | $700 규모에서 250만원 공제에 걸릴 일이 없다 |

### 9-5. 과잉 엔지니어링 위험 평가 — **8/10**

**(1) 후보 32개 중 수익을 개선하는 항목이 0개다.** 전부 관측·통제·운영이고,
전략 자체(유니버스·팩터·모델·리밸런싱 주기·비용 구조)를 건드리는 항목이 하나도 없다.
$700 계좌에서 연 3%대 비용 드래그가 유력한데, 로드맵은 그것을 *측정할 도구*는 두고 *고칠 항목*은 어디에도 없다.

**(2) 모니터링군 전체가 통계적으로 무의미한 것을 측정한다.** §9-4.

**(3) 운영 콘솔군은 연 52회 실행되는 작업의 UI 레이어다.** 각 항목이 절약하는 시간은 회당 몇 분,
짓는 데는 며칠씩이다.

> ⚠️ **전제 정정 (2026-08-09).** 위 판단은 *"앱은 전략을 돌리기 위한 수단"* 이라는 가정 위에 서 있다.
> **앱 자체가 목표라면 성립하지 않는다** — 그때 UI 투자의 회수 대상은 "절약된 분(分)"이 아니라
> 앱의 완성도 자체이고, 이 항목의 비용/편익 계산은 적용 대상이 아니다.
> 남는 사실은 하나뿐이다: **상호작용 빈도가 낮다(연 52회)** → 실시간성·고빈도 UX에 투자할 이유는 없다.
> 이건 스택 선택의 제약이 아니라 **기능 설계의 입력**이다(§10-B).

**(4) 라이브 전 항목이 브로커가 이미 해주는 것을 다시 짓는다.**
`clientOrderId` 멱등은 Phase 0-8에서 **실측 검증**됐고([qlib-toss.md](../project/roadmap.md) §Phase 0 실측 상수)
(동일 cid 2회 발주 → 1회만 차감, 같은 orderId 반환), 매수여력 초과는 `422 insufficient-buying-power`로 막히고,
정산일·수수료는 API가 돌려준다. **정식 write-ahead 상태기계를 처음부터 설계하는 건 이미 있는 보장을 재구현하는 것이다.**

**(5) 1인 개발자에게 지배적 위험은 손실이 아니라 중단이다.**
Startup Genome은 3,200개 표본에서 고성장 스타트업의 **74%가 premature scaling으로 실패**한다고 보고한다 —
*"필요한 증거 없이 대규모 성장을 예상하고 돈과 자원을 쓰는 것."*
Fowler는 presumptive feature의 **cost of carry**를 지목한다 —
*"코드에 복잡성을 더해 수정과 디버깅을 어렵게 만드는 비용."*

**(6) 비대칭이 결정적이다.** 전부 지으면 $700을 매우 잘 보호하는 시스템을 얻는데
소요는 저녁 기준 32~96회 ≈ **4~12개월**이다. 그동안 자본은 놀고, 배관은 한 번도 실제 스트레스를 안 받고, 모델은 계속 늙는다.
반대로 라이브 전 최소만 짓고 램프를 시작하면 **2주 뒤에 진짜 데이터가 흐르고,
나머지 중 무엇이 실제로 필요한지를 상상이 아니라 관측으로 알게 된다.**

**one-way / two-way door로 정리하면** — 이 로드맵은 거의 전부 two-way door인데 Type 1 프로세스로 다뤄지고 있다.
진짜 one-way door는 셋뿐이다:
**① 체결된 주문**(되돌릴 수 없음 → 사전 한도와 halt로 방어)
**② 잃어버린 결정 컨텍스트**(이벤트 로그로 방어)
**③ 소진된 개발자 의욕**(범위 축소로 방어).
나머지는 언제든 나중에 지을 수 있고, **나중에 지으면 더 잘 짓게 된다.**

> **반대 방향의 위험도 인정한다.** "먼저 출시하고 나중에 계측하라"는 돈을 다루는 시스템에 그대로 적용되지 않는다.
> Charity Majors의 observability-driven development — *코드를 쓰면서 계측하고,
> 프로덕션에서 그 계측을 통해 코드를 들여다보기 전까지 일이 끝난 게 아니다* — 는 여기서도 유효하다.
> 그래서 결론이 "계측을 미루라"가 아니라 **"계측을 원시 이벤트 로그 하나로 축소하고, 그 위의 해석 계층을 전부 미루라"** 인 것이다.
> **그 하나는 미룰 수 없고, 나머지는 전부 미룰 수 있다.**

---

## 10. 최종 권고안

### Phase A — 라이브 전 (13개)

| # | 항목 | 근거 | 비고 |
|---|---|---|---|
| 1 | **결정 이벤트 로그** (JSONL, append-only, **POST 전 flush**) | §1-A, §8-1 | `run_id`·ts·git sha·config hash·유니버스 스냅샷·모델 스코어·목표비중·심볼별 `arrival_px`·skip reason·의도 주문 + `clientOrderId`. **이 하나가 원장·intent WAL·skip code·섀도우 입력을 전부 포섭** |
| 2 | **`unknown` 해소 경로** | §8-1, phase0 0-8 | POST 실패·타임아웃 시 같은 cid 재시도 또는 `GET /orders/{id}`로 확정. 브로커 멱등이 실측 보장돼 **정식 상태기계 불필요, 함수 하나** |
| 3 | **사전 notional 한도 3종** — 주문당 / 런 전체 / 최대 건수. **미설정이면 발주 차단** | FIA §1.1 | MARKET 전용이라 **구현 가능한 유일한 사전통제** (지정가 없어 price collar 불가) |
| 4 | **계좌 단위 halt** — equity floor, 주간 손실 한도 | FIA §4.2, §9-2(c) | **신규.** 코드 3줄 |
| 5 | **대사 + break 시 halt. 자동 치유 금지** | §8-1 (5개 출처) | **타협 불가.** 배치 전체 순회(§8-3 #9) |
| 6 | **무음 실패 경보** — 목표≠현재인데 주문 0건 / USD 0 / cron 미실행 | §8-1 | **타협 불가.** 지표는 "실행 성공"이 아니라 **"의도한 경제적 행위"** |
| 7 | **입력 사전검증** — 데이터 신선도 / 거래일·조기폐장·DST(`America/New_York` 고정 + 캘린더 동적 조회) / 수량·금액 규격 | §8-3 #1·#2·#3 | **신규.** "10게이트"를 근거 있는 것으로 채움 |
| 8 | **상태 최대 체류시간 + 브로커 응답값 검증** | §8-3 #5·#6 | **신규** |
| 9 | **kill switch = 플래그 파일 + 수동 청산 런북 1장** | FIA §1.5, §9-2(e) | **UI 아님.** FIA가 스스로 "충분한 사전통제가 있으면 kill switch는 중복이 될 수 있다"고 명시 |
| 10 | **자본 램프 게이트 문서** — $1 → $50 → $200 → $700 | FINRA 15-09, §9-2(b) | **신규.** 최소주문 ≤$1이라 $1 실주문이 시뮬레이터보다 정확하고 거의 공짜 |
| 11 | **core 분리 + API 경계 확립** | Fowler YAGNI 예외, §7 | 로직을 뷰 밖으로. **뷰 스택은 이 단계에서 결정하지 않아도 된다** — core가 서면 나중에 자유롭게 고른다 |
| 12 | **비용·회전율 예산 1회 + PBO/CSCV 1회** | §9-4 | **go/no-go 판단.** 상시 시스템 아님 |
| 13 | **백업** (ledger·`.cache`) + 재개 절차 1장 | Carver, §9-2(d) | **신규** |

**인간 승인:** 유지하되 **binary(전량 실행 / 전량 중단)로 제한.**
종목별 취사선택·수량 조정 불가. 중단 시 사유 기록 → 개입 횟수를 감사 가능하게. (§8-4)

### Phase B — 램프 (4~8주)

코드 추가 없이 **운영만.** 매주 대사 통과 여부만 기록.
승급 조건: 대사 break 0 + 무음실패 0 + 비용이 예산 내를 N회 연속.

### Phase C — 라이브 3개월 후

**실제로 매주 손으로 하기 싫었던 것 1~2개만.** 운영 콘솔 후보군(§3, §4-1)에서 재선정.

### Phase D — 라이브 12개월 후

이벤트 로그가 1년 쌓였을 때 비로소 replay·분석. 모니터링·분석 후보군(§4-4)에서 재선정.

> **운영 콘솔군·모니터링군은 Phase C/D의 후보 풀로 강등하고 지금 확정하지 않는다.**
> Phase C 진입 시점에 "지난 12주 동안 실제로 반복해서 짜증났던 것"으로 재선정하는 것이,
> 지금 상상으로 고르는 것보다 항상 낫다.

### 미룰 수 있고 실제로 잃는 게 없는 것

**전제: "라이브 개시를 늦추지 않는다"가 기준이다.** 앱 완성도가 별도 목표라면 아래 UI 항목은
Phase A와 **병행**해도 무방하다 — 미루라는 게 아니라 **라이브를 막지 않는다**는 뜻이다.

| 항목 | 이유 | 앱 목표 시 |
|---|---|---|
| 일별 FX 수집 크론 | 사후 복원 가능. 환전도 어차피 수동 | 그대로 유예 |
| `settlement_date` 스키마 필드 | `execution.settlementDate`로 회수 가능 | 그대로 유예 |
| 섀도우 페이퍼 포트폴리오 (서브시스템으로서) | 이벤트 로그 위의 replay 스크립트로 충분 | 그대로 유예 |
| 원장 스키마 마이그레이션 프로젝트 | JSONL이 라이브 첫 해에 충분. **스키마는 데이터가 쌓인 뒤 도출하는 게 더 정확** | 그대로 유예 |
| kill switch **UI** | **안전성 관점에선** 플래그 파일로 동일 | **병행 가능.** 단 플래그 파일이 먼저 서야 UI가 그걸 토글하는 형태가 됨 |
| 정식 `frozen` 3상태 | halt 플래그가 곧 frozen | **병행 가능** |
| preflight 게이트 UI + 승인 화면 | 라이브 개시엔 dry-run diff 출력으로 충분 | **병행 가능.** 단 승인은 binary로 제한(§8-4) |

### ⚠️ 뷰 스택에 대해 조사가 말한 것 / 말하지 않은 것

| 말한 것 | 말하지 않은 것 |
|---|---|
| 로직을 뷰 밖으로 빼라 (§7) | **"Streamlit을 유지하라" — 이런 근거는 없다** |
| core API + 얇은 클라이언트가 수렴 패턴 (§7) | 어떤 프론트엔드 프레임워크를 쓸지 |
| 상호작용 빈도가 낮다 → 실시간 UX 불필요 (§9-5) | UI 품질에 투자하지 말라 (그건 목표에 달린 문제) |
| REST API를 인터넷에 노출하지 말 것 (§4-1) | 로컬/터널 환경에서의 스택 제약 |
| 채팅 표면(Telegram)이 3개 프로젝트에서 수렴 (§3, §4-1) | 채팅이 웹 UI를 **대체**해야 한다 (보완 관계) |
| 무거운 집계는 백그라운드 선계산 (Ghostfolio, §4-1) | — 이건 어떤 스택에서도 유효한 설계 원칙 |

---

## 11. 출처

### 1차 조사 — 오픈소스 / 인디 앱
- Freqtrade — [Configuration](https://www.freqtrade.io/en/stable/configuration/) · [Telegram Usage](https://www.freqtrade.io/en/stable/telegram-usage/) · [REST API](https://www.freqtrade.io/en/stable/rest-api/) · [FreqUI](https://www.freqtrade.io/en/stable/freq-ui/) · [Webhook Config](https://www.freqtrade.io/en/stable/webhook-config/) · [Plugins](https://www.freqtrade.io/en/stable/plugins/) · [Advanced Backtesting](https://www.freqtrade.io/en/stable/advanced-backtesting/) · [Lookahead Analysis](https://www.freqtrade.io/en/stable/lookahead-analysis/) · [Utils](https://www.freqtrade.io/en/stable/utils/) · [Deprecated](https://www.freqtrade.io/en/stable/deprecated/)
- Hummingbot — [Client](https://hummingbot.org/client/) · [Dashboard](https://hummingbot.org/dashboard/) · [Condor 소개(Streamlit deprecation)](https://hummingbot.org/blog/introducing-condor-the-open-source-harness-for-trading-agents/) · [dashboard repo](https://github.com/hummingbot/dashboard)
- NautilusTrader — [Execution (RiskEngine, TradingState, OrderDenied)](https://nautilustrader.io/docs/latest/concepts/execution/) · [Docs](https://nautilustrader.io/docs/latest/)
- Jesse — [Docs](https://docs.jesse.trade/) · [Live Trade](https://docs.jesse.trade/docs/livetrade.html)
- OctoBot — [GitHub](https://github.com/Drakkar-Software/OctoBot)
- Ghostfolio — [GitHub](https://github.com/ghostfolio/ghostfolio) · [CHANGELOG](https://raw.githubusercontent.com/ghostfolio/ghostfolio/main/CHANGELOG.md)
- Portfolio Performance — [Site](https://www.portfolio-performance.info/en/) · [Reference](https://help.portfolio-performance.info/en/reference/) · [Dashboard Widgets](https://help.portfolio-performance.info/en/reference/view/reports/performance/dashboard/)
- Lean CLI — [API Reference](https://www.lean.io/docs/v2/lean-cli/api-reference/lean-backtest)
- Tradervue — [Features](https://www.tradervue.com/features/) · [MFE/MAE Calculations](https://help.tradervue.com/article/3440-mfe-and-mae-calculations)
- Edgewonk — [Features](https://edgewonk.com/features)
- QuantStats — [GitHub](https://github.com/ranaroussi/quantstats) · vectorbt — [Features](https://vectorbt.dev/getting-started/features/)

### 기관 트레이딩 운영 · 규제
- [17 CFR § 240.15c3-5 — Market Access Rule](https://www.law.cornell.edu/cfr/text/17/240.15c3-5)
- [17 CFR § 240.17a-13 — Quarterly security counts](https://www.law.cornell.edu/cfr/text/17/240.17a-13)
- [Commission Delegated Regulation (EU) 2017/589 (RTS 6)](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32017R0589)
- [ESMA — Supervisory Briefing on Algorithmic Trading in the EU (2026-02)](https://www.esma.europa.eu/sites/default/files/2026-02/ESMA74-1505669079-10311_Supervisory_Briefing_on_Algorithmic_Trading_in_the_EU.pdf)
- [FIA — Best Practices for Automated Trading Risk Controls and System Safeguards (2024-07)](https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf)
- [FIA — Guide to the Development and Operation of Automated Trading Systems (2015-03)](https://matbarofex.com.ar/documentos/mpi/fia-guide)
- [SEC — Rule 613 (Consolidated Audit Trail)](https://www.sec.gov/about/divisions-offices/division-trading-markets/rule-613-consolidated-audit-trail)
- [Smarsh — SEC Rule 17a-4 (WORM vs audit-trail alternative)](https://www.smarsh.com/regulations/sec-rule-17a-4-records-preservation/)
- [FIX 4.4 Dictionary — OrdStatus (Tag 39)](https://www.onixs.biz/fix-dictionary/4.4/tagNum_39.html) · [FIX 4.2 — ClOrdID (Tag 11)](https://www.b2bits.com/fixopaedia/fixdic42/tag_11_ClOrdID.html)
- [Limina — Cash Reconciliation Guide](https://www.limina.com/blog/cash-reconciliation-guide) · [Prodktr — Causes of cash and position breaks](https://prodktr.com/common-causes-of-cash-and-position-breaks/)
- [Perold (1988) — Implementation Shortfall](https://www.cis.upenn.edu/~mkearns/finread/impshort.pdf) · [Talos — TCA Benchmarks and Slippage](https://www.talos.com/insights/execution-insights-through-transaction-cost-analysis-tca-benchmarks-and-slippage)
- [Morrison Foerster — SEC T+1 (Rule 15c6-1, 2024-05-28)](https://www.mofo.com/resources/insights/230224-new-sec-rules-and-amendments) · [FINRA Notice 23-15](https://www.finra.org/rules-guidance/notices/23-15)
- [Fidelity — Avoiding Cash Account Trading Violations](https://www.fidelity.com/learning-center/trading-investing/trading/avoiding-cash-trading-violations) · [Schwab — Trading in Cash Accounts](https://www.schwab.com/learn/story/avoid-these-violations-when-trading-cash)

### 한국 세무 · 환전 · 결제
- [국세청 — 주식등 양도소득세 과세대상](https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=8800)
- [국세청 보도참고자료 「해외주식 양도 하셨나요?」 (2025.5.8)](https://www.nts.go.kr/comm/nttFileDownload.do?fileKey=5ea48b22f746011a1634f48b04d11625) — **핵심 1차 출처**
- [국세청 — 배당소득 원천징수 방법](https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=6478&cntntsId=7914)
- [예규 국제세원-229 (2010.5.10) — 외화환산 환율 = 결제일 기준환율](https://casenote.kr/%EA%B5%AD%EC%84%B8%EC%B2%AD/%EA%B5%AD%EC%A0%9C%EC%84%B8%EC%9B%90-229-2f375e)
- [예규 서면-2022-국제세원-0764 — FIFO/이동평균](https://casenote.kr/%EA%B5%AD%EC%84%B8%EC%B2%AD/%EC%84%9C%EB%A9%B4-2022-%EA%B5%AD%EC%A0%9C%EC%84%B8%EC%9B%90-0764-0ffb62)
- [소득세법 §129](https://casenote.kr/%EB%B2%95%EB%A0%B9/%EC%86%8C%EB%93%9D%EC%84%B8%EB%B2%95/%EC%A0%9C129%EC%A1%B0) · [별지 제84호서식](https://www.law.go.kr/LSW/flDownload.do?gubun=&flSeq=160271465&bylClsCd=110202)
- [서울외국환중개 — 환율산출 근거(매매기준율)](http://www.smbs.biz/Company/Buss_3_4.jsp) · [한국은행 ECOS API](https://ecos.bok.or.kr/api/)
- [유안타증권 — 미국주식 결제일 변경 공지 (T+3→T+2 / 현지 T+2→T+1)](https://www.myasset.com/myasset/customer/notice/CU_0201000_P2.cmd?SEQ=202405240944360000000004&gubun=norNotice) · [해외주식 양도소득세 안내](https://www.myasset.com/myasset/static/investinfo/IN_1104000_P1.jsp)
- [하나증권 — 해외주식 세금안내 (결제일 환율 계산식)](https://www.hanaw.com/main/wts/foreign/WT_070400_P.htm) · [한국투자증권 — 시장별 결제일](https://www.truefriend.com/main/bond/research/_static/TF03ca050002.jsp)
- [신한투자증권 — 양도소득세 신고대행](https://www.shinhansec.com/siw/trading/foreign-equity/orstock_business_guide5_tab1/contents.do) · [통합증거금 약관 PDF](https://file.shinhansec.com/filedoc/clause/FS_deposit.pdf)
- [토스증권 — 환전 수수료 FAQ 3549](https://support.toss.im/faq/3549) · [양도소득세 신고대행 공지](https://corp.tossinvest.com/ko/post?type=notice&id=20624&category=52)
- [토스 OpenAPI JSON (36 endpoints — 환전 엔드포인트 부재 확인)](https://openapi.tossinvest.com/openapi-docs/latest/openapi.json) · [llms.txt](https://developers.tossinvest.com/llms.txt)
- [자본시장연구원 — 미국 주식시장 결제주기 단축의 영향](https://www.kcmi.re.kr/report/report_view?report_no=1788)

### 퀀트 리서치 · 라이브 모니터링
- [Bailey & López de Prado — Deflated Sharpe Ratio (SSRN 2460551)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) · [PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- [Bailey et al. — Pseudo-Mathematics and Financial Charlatanism (AMS Notices, MinBTL)](https://www.ams.org/notices/201405/rnoti-p458.pdf) · [SSRN 2308659](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659)
- [Bailey et al. — Probability of Backtest Overfitting (CSCV)](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) · [SSRN 2326253](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253) · 구현 [pypbo](https://github.com/esvhd/pypbo)
- [López de Prado & Lewis — Detection of False Investment Strategies (SSRN 3167017)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3167017)
- [Harvey, Liu & Zhu — …and the Cross-Section of Expected Returns (RFS 29(1), t>3.0)](https://academic.oup.com/rfs/article/29/1/5/1843824) · [NBER w20592](https://www.nber.org/system/files/working_papers/w20592/w20592.pdf)
- **[Philips, Yashchin & Stein — Using Statistical Process Control To Monitor Active Managers (CUSUM)](https://investicsfiles.s3.amazonaws.com/Documentation/Using+Statistical+Process+Control+To+Monitor+Active+Managers.pdf)** · [Northfield 144.pdf](https://www.northinfo.com/Documents/144.pdf)
- [Purged cross-validation (Wikipedia)](https://en.wikipedia.org/wiki/Purged_cross-validation) · [QuantInsti — Purging, Embargoing, Combinatorial CV](https://blog.quantinsti.com/cross-validation-embargo-purging-combinatorial/) · [skfolio CombinatorialPurgedCV](https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html)
- [Walk forward optimization (Wikipedia)](https://en.wikipedia.org/wiki/Walk_forward_optimization) · [Better System Trader — Robert Pardo 인터뷰](https://bettersystemtrader.com/060-strategy-optimization-with-robert-pardo/)
- [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) · [pandas-datareader famafrench](https://pydata.github.io/pandas-datareader/readers/famafrench.html)
- [R Journal RJ-2013-025 — Performance Attribution for Equity Portfolios (Brinson)](https://journal.r-project.org/articles/RJ-2013-025/)
- pyfolio — [timeseries.py (forecast_cone_bootstrap)](https://github.com/quantopian/pyfolio/blob/master/pyfolio/timeseries.py) · [plotting.py](https://github.com/quantopian/pyfolio/blob/master/pyfolio/plotting.py) · [interesting_periods.py](https://github.com/quantopian/pyfolio/blob/master/pyfolio/interesting_periods.py)
- alphalens — [performance.py](https://github.com/quantopian/alphalens/blob/master/alphalens/performance.py) · [plotting.py](https://github.com/quantopian/alphalens/blob/master/alphalens/plotting.py)
- [AlphaArchitect — Information Decay: which factors have the longest half-lives?](https://alphaarchitect.com/information-decay/)
- [Ernest Chan — The life and death of a strategy](http://epchan.blogspot.com/2012/04/life-and-death-of-strategy.html) · [Robert Carver — Systematic Trading 요약](https://threadreaderapp.com/thread/1234306875379683328.html)
- [How Many Random Seeds? Statistical Power Analysis (arXiv 1806.08295)](https://ar5iv.labs.arxiv.org/html/1806.08295) · [Impact of Randomness on Reproducibility (arXiv 2410.02806)](https://arxiv.org/pdf/2410.02806)
- [Evaluating Structured Strategy Backtests: Peer Benchmarks, Regime Timing, Live Performance (arXiv 2604.18821)](https://arxiv.org/abs/2604.18821)
- [David vs Goliath — separating impact and timing of trading costs (arXiv 1603.00984)](https://arxiv.org/pdf/1603.00984)
- Qlib — [Analysis/Report](https://qlib.readthedocs.io/en/stable/component/report.html) · [Recorder](https://qlib.readthedocs.io/en/stable/component/recorder.html)
- MLflow — [Tracking](https://mlflow.org/docs/latest/ml/tracking/) · [Model Registry](https://mlflow.org/docs/latest/ml/model-registry/)

### 2차 조사 — 실전 실패 기록 (1인칭)
- **[A]** [Production Trading Bots: 15 Failure Patterns Nobody Warns You About — florinelchis](https://florinelchis.medium.com/production-trading-bots-15-failure-patterns-nobody-warns-you-about-af917d263c35) — **최우선 자료**
- **[B]** [Operational Pitfalls of Algo Trading — Concretum Group](https://concretumgroup.substack.com/p/operational-pitfalls-of-algo-trading)
- **[C]** nautilus_trader 이슈 — [#3176 자동 대사가 중복 주문 생성](https://github.com/nautechsystems/nautilus_trader/issues/3176) · [#3104](https://github.com/nautechsystems/nautilus_trader/issues/3104) · [#3476](https://github.com/nautechsystems/nautilus_trader/issues/3476) · [#3655](https://github.com/nautechsystems/nautilus_trader/issues/3655) · [#3023](https://github.com/nautechsystems/nautilus_trader/issues/3023)
- [HN 16923294 — "I lost about $100k doing algorithmic trading"](https://news.ycombinator.com/item?id=16923294) — 인간 개입이 성과 훼손한 1인칭 기록
- [HN 44810552 — NautilusTrader discussion](https://news.ycombinator.com/item?id=44810552)
- [메리츠증권 — 해외주식 통합증거금](https://home.imeritz.com/fstock/ForeignStock01_07.do) · [미래에셋증권 — 통합증거금 설명서](https://securities.miraeasset.com/hki/hki3032/n10.do) · [뉴시스 — 통합증거금 장단점](https://www.newsis.com/view/NISX20230926_0002465571)
- [Option Alpha — Bot Limitations (기업행위 수동 오버라이드)](https://optionalpha.com/help/bot-limitations)
- [TG's Programming Blog — 한국투자증권 Open API 초당 20건 제한](https://tgparkk.github.io/robotrader/2025/10/09/robotrader-1-70stocks-problem.html)
- [SQLite concurrent writes and "database is locked"](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)
- [Knight Capital — 정지 스위치 부재 (기관 사례)](https://www.business-standard.com/amp/article/markets/trading-software-ran-amok-with-no-off-switch-at-knight-capital-112080500040_1.html)

### 2차 조사 — go-live 요건 · 범위 규율
- [FINRA Regulatory Notice 15-09 — Algorithmic Trading](https://www.finra.org/rules-guidance/notices/15-09) — **pilot phase 요구의 1차 출처**
- [SEC — Rule 15c3-5 Market Access FAQ (의무 주체 = 브로커-딜러)](https://www.sec.gov/rules-regulations/staff-guidance/trading-markets-frequently-asked-questions/divisionsmarketregfaq-0)
- [Robert Carver — pysystemtrade `docs/production.md`](https://github.com/robcarver17/pysystemtrade/blob/master/docs/production.md) — **개인 트레이더의 유일한 1차 운영 문서**
- [Robert Carver — qoppac](https://qoppac.blogspot.com/p/systematic-trading-start-here.html) · [Leveraged Trading (최소자본 £1,100)](https://qoppac.blogspot.com/2019/10/new-book-leveraged-trading.html)
- [Kevin Davey — IBKR Campus, Algo Advantage 036 (인큐베이션 6~12개월)](https://ibkrcampus.com/campus/ibkr-quant-news/algo-advantage-036-kevin-davey-part-i-its-all-about-process-in-algo-trading/) · [Walk-forward testing](https://kjtradingsystems.com/walkforward-testing-for-algorithmic-trading.html)
- **[Andrew W. Lo — The Statistics of Sharpe Ratios, FAJ 2002](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios)** · [PDF](https://traders.studentorg.berkeley.edu/papers/The-Statistics-of-Sharpe-Ratios.pdf) — **SE(SR) 재계산의 근거**
- [López de Prado — Backtesting (SSRN 2606462)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2606462) · [10 Reasons Most ML Funds Fail (PDF)](https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf)
- [Martin Fowler — Yagni (cost of carry, "수정 용이성 노력에는 적용 안 됨")](https://martinfowler.com/bliki/Yagni.html)
- [Dan McKinley — Choose Boring Technology (innovation token)](https://mcfunley.com/choose-boring-technology)
- [Google SRE — Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/) · [Production Readiness Review](https://sre.google/sre-book/evolving-sre-engagement-model/)
- [Honeycomb — Observability 2.0 (이벤트 → 메트릭 단방향 손실)](https://www.honeycomb.io/blog/time-to-version-observability-signs-point-to-yes) · [Observability-Driven Development](https://www.honeycomb.io/resources/changing-practices-on-your-team-observability-driven-development-thanks)
- [Stripe — Idempotency](https://stripe.com/blog/idempotency) · [brandur — Idempotency Keys in Postgres](https://brandur.org/idempotency-keys)
- [Modern Treasury — Enforcing Immutability in your Double-Entry Ledger](https://www.moderntreasury.com/journal/enforcing-immutability-in-your-double-entry-ledger)
- [Startup Genome — Premature Scaling (74%, PDF)](https://s3.amazonaws.com/startupcompass-public/StartupGenomeReport2_Why_Startups_Fail_v2.pdf)
- [Jeff Bezos — 2015 Letter to Shareholders (one-way/two-way doors, PDF)](https://s2.q4cdn.com/299287126/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF)
- [StarQube — Point-in-Time Data](https://starqube.com/point-in-time-data/) · [TEJ — Point-in-Time Audited Financial Database](https://www.tejwin.com/en/insight/tej-point-in-time-audited-financial-database/) — **arrival price 회복불가 논거**
- [Fill Probabilities in a Limit Order Book (arXiv 2403.02572)](https://arxiv.org/pdf/2403.02572) — 시뮬레이터가 체결을 과대평가하는 근거
- [토스증권 Open API — 주문](https://developers.tossinvest.com/docs/order) · [Open API 소개](https://home.tossinvest.com/ko/open-api) · [외부 정리 — 샌드박스 부재 확인](https://www.baseload.co.kr/blog/2026-07-07-toss-securities-open-api-guide/)

### 근거를 찾지 못해 비워둔 영역 (없다는 것이 findings)
- Ernest Chan의 페이퍼트레이딩 기간·라이브 전환 인프라 1차 텍스트 — 접근 실패(403), 2차 요약만 존재하여 **인용하지 않음**
- Andreas Clenow의 go-live 인프라 공개 발췌 — 검색되지 않음
- 소액 개인 API 사용자에 대한 브로커·거래소 사전 인증·컨포먼스 요건 — **존재하지 않음이 확인됨**
- r/algotrading — reddit.com 크롤러 차단으로 접근 불가
- ⚠️ *"2025 Stanford study, 58% of retail algo strategies collapse within 3 months"* — **원 출처 없음. 인용 금지**
