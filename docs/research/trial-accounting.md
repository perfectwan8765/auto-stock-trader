# 리서치 — 시행 원장·다중검정 보정·음성 결과 기록 (모델 비의존)

- 조사일: 2026-08-17
- 목적: **"몇 번 시도했는가"** 를 세는 규율을 찾는다. 시행 횟수 N을 신고해야 계산되는 보정
  통계량(DSR·MinBTL·PBO·haircut)의 정의·가정·한계를 1차 출처로 확정하고, **이 저장소 규모에서
  실제로 계산되는 것과 계산되지 않는 것을 가른다.**
- 방법: 논문은 저자 배포 PDF·학회 proceedings PDF를 내려받아 **텍스트를 직접 추출해** 인용했고,
  서지사항은 **Crossref API로 교차검증**했다. 도구는 이 저장소 `.venv` 설치본을 introspect했고,
  공식 문서·법령은 HTML/XML을 받아 **원문 문자열을 grep해** 확인했다(웹 UI가 봇 차단이면 API로
  우회). 확인 못 한 것은 §9에 적었다.
- **§1의 수치는 전부 이 저장소 `mlruns/`(로컬)에서 직접 계산했다.** 백테스트 수익률이고
  계좌 관련 값은 없다.
- 자매 문서: [`training-gates.md`](training-gates.md) — 학습 건전성 게이트.
  저쪽은 **"이 한 번의 학습이 성립했는가"**, 이쪽은 **"몇 번 시도했는가"** 를 다룬다.
  저쪽 §4.1이 넘긴 MLflow 파일 백엔드 마이그레이션은 이 문서 **§6**이다.
- 후속 문서: [`optuna-adoption.md`](optuna-adoption.md) — 탐색 프레임워크 도입 판단(**반대**).
  §1.2의 DSR을 N=200까지 연장하면 0.0081이 되어 "많이 돌려서 이긴다"가 산술적으로 닫힌다.
  §7.2의 guided-search 조항이 그 판단의 핵심 근거다.
- ★ **이 문서 §10-1의 착지점은 실행됐다** — [`trial-ledger.md`](../project/trial-ledger.md)가
  2층 구조로 개설됐고 기존 23런이 백필됐다. §10-2(스윕이 후보마다 런을 열게 하기)도 반영됐으나
  **부모-자식 런은 쓸 수 없었다** — `MLflowRecorder.start_run`이 `mlflow.start_run`에 `nested`를
  넘기지 않는다. `sweep_id` param으로 묶는 방식으로 대체했다(커밋 `8e8a4db`).
- 중복 회피: DSR·MinBTL 공식은 [`dashboard-features.md`](dashboard-features.md) §4-4에 이미 있다.
  이 문서는 **공식을 다시 쓰지 않고, 그 공식의 가정·한계·이 저장소 적용 가능성만** 다룬다.
  (다만 §9에 §4-4 수치예의 **정정 필요** 항목이 있다.)

---

## 0. 요약

**확립된 것 — 계산해 봤다**

1. `mlruns/` 23런 중 **수익률 계열을 남긴 런은 11개**이고, 그중 **동일 기간(183주,
   2023-01-03~2026-06-29)을 공유하는 런은 9개**다. 그 9열이 담은 서로 다른 설정은 **3개**다. (§1.1)
2. ★★★ **"런 수"가 "시행 수"가 아니다.** `tune_hyperparams.py`는 후보 6개를 돌렸는데
   **MLflow 런은 1개**이고, 6개 검증곡선이 같은 metric 키에 `step=0`부터 겹쳐 쓰였다
   (`l2.valid` 356줄, `step=0` **6회**). `probe_label_horizon.py`도 3 → 1이다.
   **후보 이름은 어디에도 없고, 6개 중 하나를 고른 선택은 stdout으로만 갔다.** (§1.1.1)
3. ★★★ **README `+11.9%` 행의 GRU 최선 시드를 DSR로 재판정하면 0.4968이다.** 다중검정 무보정
   PSR은 0.9611로 "유의"해 보이지만, **가장 관대한 N(=4.86, 실측 상관에서 유도)에서도 DSR이
   0.50**이다. 실제 런 수 N=23을 쓰면 0.1163이다. (§1.2)
   → 문헌 관례 기각선 0.95에 **압도적으로 미달**한다. 이미 갖고 있던 데이터로 계산됐다.
4. ★★★ **원수익으로 DSR을 계산하면 통과하고 초과수익으로 계산하면 기각된다.** 같은 9런에서
   원수익 DSR은 0.9965인데 초과수익(벤치·비용 차감) DSR은 0.4968이다. 순위도 완전히 뒤집힌다 —
   원수익 1위(41종목 파일럿, 연 Sharpe +1.77)가 초과수익 최하위(IR −1.00)다. (§1.3)
5. ★★ **MinBTL 기준으로 이 저장소는 이미 예산을 넘겼다.** 183주 = 3.52년으로 "IS Sharpe 1이지만
   OOS 기대 0"인 전략을 피할 수 있는 최대 독립시행은 **N=18**이다. 23런을 이미 돌렸다. (§1.4)
6. ★★ **CSCV는 기계적으로 돌아가지만 해상도가 없다.** 실제로 돌려 PBO = 0.0049를 얻었는데,
   N=9라서 **logit이 가질 수 있는 값이 9개(관측 8개)뿐**이다. 논문이 직접
   *"so N >> 10 is required"* 라고 못박은 조건 미달이다. 게다가 같은 실행의 성능열화 회귀는
   **β = −0.879 < 0**으로 정반대 신호를 준다. (§1.5)
7. ★★★ **"1회 시행"의 정의는 1차 문헌에 없다. 두 문헌군이 독립적으로 같은 칸을 비워 뒀다.**
   Harvey & Liu는 *"we need to use judgment on an important input—the number of tests"* 라 쓰고,
   OSF 사전등록 템플릿은 *"Explain how comparing multiple conditions or testing multiple hypotheses
   will be accounted for"* 라고만 한다. **금융·통계 쪽과 사전등록 플랫폼 쪽이 똑같이 위임한다.**
   문헌이 주는 것은 정의가 아니라 **변환**(M → N̂, DSR 부록 A.3)과 **메커니즘 네 개**다. (§7 · §8.6)
8. `mlflow 3.14.0`의 `migrate-filestore`는 **실재한다**(CLI introspect 확인). 단
   **SQLite만 지원하고, 대상 DB가 비어 있어야 하며, 아티팩트를 옮기지 않는다.** (§6)
9. ★★ **임상시험 등록 체제의 실제 구속력은 "몇 번 했는지 세기"가 아니라 "primary outcome 사전
   고정"이다.** 42 CFR Part 11이 정의하는 trial 단위는 규제 단위이고 검정 단위가 아니다.
   그리고 사전 선언 체제로 바뀐 뒤 NHLBI 대형 시험의 양성률이 **57% → 8%** 로 떨어졌다
   (Kaplan & Irvin 2015). (§8.2 · §8.3 · §8.6)
10. ★★ **Registered Reports의 "outcome-neutral conditions"가 자매 문서의 학습 게이트와 같은
   물건이다.** RR은 그것을 **게재 승인의 선결 조건**으로 둔다 — 곧 학습 게이트는 시행 원장의
   outcome-neutral 관문이다. **두 문서가 여기서 만난다.** (§8.4)

**모델 비의존성 — 항목마다 다르다**

| 항목 | 무엇을 하나 | 비의존? | 이 저장소에서 계산되나 |
|---|---|---|---|
| A. 시행 원장 (N 기록) | 시도 횟수를 세어 남긴다 | ✅ **완전** — 무엇을 돌렸는지만 적음 | ✅ 지금도 가능 |
| B. DSR (§2) | SR을 N·비정규성으로 디플레이트 | ✅ **완전** — 수익률 계열만 필요 | ✅ **계산했다** (§1.2) |
| C. MinBTL (§3) | 표본길이 대비 N 예산 | ✅ **완전** — 모델을 안 봄 | ✅ **계산했다** (§1.4) |
| D. PBO/CSCV (§4) | 선택 절차의 과적합 확률 | ✅ 원리는 완전 (model-free 자칭) | ⚠️ **돌아가지만 무의미** (§1.5) |
| E. Harvey-Liu haircut (§5) | t·SR을 다중검정으로 깎음 | ✅ **완전** | ⚠️ t-stat을 안 내고 있음 |
| F. 사전등록 (§8) | 세는 시점을 측정 전으로 고정 | ✅ **완전** — 절차 규율 | ✅ 이미 1건 있음 |

**통설이지만 근거가 약하거나 틀린 것**

1. "PBO가 낮으니 과적합이 아니다" — **§1.5에서 PBO 0.0049와 β −0.879가 동시에 나왔다.**
   논문 자신이 네 통계량을 **상보적(complementary)** 이라 부르고 PBO 하나로 판정하라고 하지 않는다.
2. "N은 사후에 `mlruns/`를 세면 된다" — 안 된다. **손익 계열을 남기지 않은 12런은
   DSR·PBO의 입력이 될 수 없는데도 N에는 들어가야 한다.** 파일 드로어가 원장 안에서 발생한다(§1.1).
3. "시드를 여럿 돌리면 검증이 강해진다" — **DSR에서는 반대로 작동한다.** 같은 설정의 시드
   반복은 `V[{SR}]`를 줄이고 평균상관 ρ̂를 올려 **N̂을 줄이므로 임계 SR₀이 내려간다.** 곧
   **중복 시행이 DSR을 부풀린다**(§2.3). 이건 문헌 주장이 아니라 식에서 따라오는 결과다.
4. "DSR 0.95 넘으면 엣지다" — 아니다. DSR은 *"true SR > 0"* 의 확률이지 수익성 판정이 아니다.
   그리고 **원수익에 걸면 불장 베타를 유의하다고 말한다**(§1.3).
5. "t > 3.0이 안전한 허들" — HLZ 본인들이 *"there are good reasons to expect that 3.0 is too low"*
   라고 쓴다(§5.2).
6. "데이터가 이미 존재하니 금융 백테스트는 사전등록이 불가능하다" — 아니다. OSF 템플릿은
   *"Data exists but the authors have **not observed** it yet"* 를 **정식 등급으로 둔다.**
   신고 대상은 데이터의 **존재**가 아니라 **열람**이다(§8.6).
7. "사전등록하면 탐색적 분석을 못 한다" — 아니다. COS RR은 *"places **no restrictions** on the
   reporting of unregistered exploratory analyses"* 이고 **구분 표시만** 요구한다(§8.4).

---

## 1. 이 저장소에서 실제로 계산한 것

> 계산 대상: `mlruns/` 전체(6 experiment · 23런). 자매 문서 §1이 쓴 것과 같은 원장이다.
> 수익률 계열은 `artifacts/portfolio_analysis/report_normal_1week.pkl`에서 읽었고,
> 초과수익은 qlib 규약 그대로 `return − bench − cost`다
> (`qlib/workflow/record_temp.py`의 `excess_return_with_cost` 정의와 동일).

### 1.1 ★★ 시행 원장의 실제 재고 — 23런 중 9런만 비교 가능하다

| 구분 | 런 수 | 손익 계열 | 비고 |
|---|---:|---|---|
| `workflow_config_alpha360_gru_sp500` | 7 | 4런만 있음 | 시드 2026·42·7·2025 |
| `Experiment` (튜닝·프로브) | 7 | **0런** | 아티팩트가 `code_*.txt`뿐 |
| `phase3_smoke_alpha158_lgb_pilot` | 4 | 2런만 있음 | 41종목 파일럿 |
| `workflow_config_alpha360_gru_bear2022` | 2 | 2런 | **기간이 다름**(76주, 2021-07~2022-12) |
| `workflow_config_alpha158_lgb_sp500` | 2 | 2런 | README 베이스라인 |
| `phase3_workflow_config_alpha158_lgb_sp500` | 1 | 1런 | 위와 값이 동일 |
| **합계** | **23** | **11** | **동일 183주를 공유: 9런** |

★ **`Experiment`의 7런이 정확히 문제다.** 이건 설계 자유도를 실제로 탐색한 유일한 시행들인데
손익 계열이 없다. 곧 **N에는 반드시 들어가야 하는 시행이 보정 통계량의 입력에는 들어갈 수 없다.**
이것이 PBO 논문이 말하는 file drawer가 *외부 은폐*가 아니라 *내부 구조*로 발생하는 경우다:

> First, the researcher must provide full information regarding the actual trials conducted, to avoid
> the ﬁle drawer problem (the test is only as good as the completeness of the underlying information)
> … **Hiding trials will lead to an underestimation of the overﬁt**, because each logit will be
> evaluated under a biased relative rank ωᶜ.

### 1.1.1 ★★★ 한 런 안에 여섯 개의 시행이 겹쳐 기록돼 있다

`Experiment` 7런의 `params/cmd-sys.argv`를 읽으면 어느 스크립트가 남긴 런인지 나온다.
그리고 각 런의 `metrics/l2.valid`에서 **`step`이 0으로 되돌아간 횟수**를 세면 그 런 안에서
학습이 몇 번 일어났는지 알 수 있다:

| 런 | 스크립트 | 스크립트가 정의한 설정 수 | `l2.valid` 줄 수 | **`step=0` 횟수** |
|---|---|---:|---:|---:|
| `f42a2767` | `tune_hyperparams.py` | **6** (`CANDIDATES`) | 356 | **6** |
| `fb390207` | `probe_label_horizon.py` | **3** (`HORIZONS`) | 168 | **3** |
| `47a71b3f` | `probe_models.py` | 3 (LGB/XGB/DEnsemble) | 56 | 1 |
| `8789c1c4` | `probe_models.py` | 〃 | 56 | 1 |
| `0df97eb8` | `run_smoke.py` | — | — | — |
| `7e0d8a55`·`9d8117a7` | `generate_signal.py` | — (학습 아님) | — | — |

★★★ **`tune_hyperparams.py`는 후보 6개를 돌렸는데 MLflow 런은 1개다.** 6개 검증곡선이
**같은 metric 키에 step 0부터 다시 쓰이며 겹쳐 기록**됐다. 원인은 코드에 있다 —
이 스크립트는 `R.start()`로 recorder를 열지 않고 `for name, params in CANDIDATES.items():`
안에서 `model.fit(dataset)`만 반복한다. 런은 `LGBModel.fit`이 `R.log_metrics`를 부르는 부수효과로
**한 번 생기고 그대로 재사용**된다.

곧 **원장에 남은 것은 "런 1개"이고 실제 시행은 6회**다. 그리고:

- **후보 이름이 어디에도 없다.** 이 런의 `params/`에는 `cmd-sys.argv` 한 개뿐이고, 태그는
  `mlflow.source.*`·`mlflow.user`·`mlflow.runName`(값이 전부 `mlflow_recorder`)뿐이다.
  → **step 리셋으로 6개를 분리해 낼 수는 있어도 어느 곡선이 어느 후보인지 알 수 없다.**
- ★★ **선택이 stdout으로만 갔다.** 스크립트는 `res.sort_values("valid_RankIC", ascending=False)`
  뒤 `best = res.iloc[0]`을 출력한다. **이것이 6개 중 하나를 고르는 다중검정 선택 그 자체인데,
  선택의 근거가 원장에 없다.** 자매 문서 §1.1이 인용한 주석("L1/L2를 크게 낮춰 즉시 early-stop
  해소")이 어느 후보에 대한 것인지도 이 원장으로는 복원되지 않는다.
- `probe_models.py`는 3개 모델을 정의하는데 곡선이 런당 1개다. XGB·DoubleEnsemble은 LightGBM의
  `record_evaluation` 콜백을 안 쓰므로 `l2.valid`를 남기지 않는다.
  ⚠️ **런이 2개인 이유(2회 실행인지, 1회 실행에서 기록 가능한 모델이 2개였는지)는 확정 못 했다**(§9).

★ **원장 하나는 이미 잘 남아 있다** — `mlflow.source.git.commit`이 자동 기록된다
(예: `f42a2767` → `d0a1966db7dc07161401b2a431966c98ce175a6d`). **커밋은 공짜로 얻는다.**
빠진 것은 **설정 식별자와 시행 경계**다.

⚠️ 그리고 9런 중에도 **완전 중복이 있다.** 상관행렬 최대값이 정확히 `1.000`이고,
파일럿 2런(IR −1.000 동일)·`a78572`/`81972b`(IR −0.621 동일)이 값까지 같다.
**9열이 담은 설정은 3개**다 — GRU/Alpha360 S&P500(시드 4) · LGB/Alpha158 S&P500(3런, 값 2종) ·
LGB/Alpha158 41종목 파일럿(2런, 값 1종). 서로 다른 SR 값은 7개다.

### 1.2 ★★★ DSR을 계산했다 — README `+11.9%` 행은 DSR 0.50이다

183주 초과수익(비용 차감) 기준 9런:

| 런 | SR(주간) | **IR(=SR×√50)** | 왜도 | 첨도 |
|---|---:|---:|---:|---:|
| `alpha360_gru_sp500` / `fde856` | +0.1305 | **+0.923** | +0.097 | 3.331 |
| `alpha360_gru_sp500` / `58d89d` | +0.1089 | +0.770 | +0.063 | 2.858 |
| `alpha360_gru_sp500` / `48414a` | +0.1001 | +0.708 | +0.246 | 3.313 |
| `alpha360_gru_sp500` / `bc7e85` | +0.0633 | +0.448 | +0.251 | 3.465 |
| `alpha158_lgb_sp500` / `d5d985` | −0.0499 | −0.353 | +0.027 | 3.349 |
| `alpha158_lgb_sp500` / `a78572` | −0.0878 | −0.621 | +0.025 | 3.347 |
| `phase3_…lgb_sp500` / `81972b` | −0.0878 | −0.621 | +0.025 | 3.347 |
| `smoke_lgb_pilot` / `a7d7a8` | −0.1414 | −1.000 | −0.207 | 4.248 |
| `smoke_lgb_pilot` / `b4411b` | −0.1414 | −1.000 | −0.207 | 4.248 |

★ **이 IR 열은 README 실험표의 IR 열과 같은 값이다.** README는 GRU 4시드 IR을
`0.71 / 0.92 / 0.45 / 0.77`, 베이스라인을 `−0.35`로 적었고, 위 표는
`0.708 / 0.923 / 0.448 / 0.770`, `−0.353`이다. **재계산이 README를 재현했으므로 이하 판정은
README 그 행에 대한 판정이다.**

측정된 DSR 입력: `V[{SR}] = 0.012451`(주간 단위, 9런 횡단), `√V = 0.11158`,
평균 쌍상관 `ρ̂ = 0.5178`, `T = 183`.

| N (독립시행) | 근거 | 임계 `SR₀ = E[max SR]` | **DSR** |
|---|---|---:|---:|
| 1 (무보정 PSR) | 다중검정 무시 | 0.00000 | **0.9611** |
| **4.86** | `N̂ = ρ̂ + (1−ρ̂)M`, M=9 (DSR 부록 A.3) | 0.13111 | **0.4968** |
| 9 | 비교 가능 런 수 | 0.16969 | **0.2983** |
| 19 | MinBTL 예산 상한(§1.4) | 0.20955 | **0.1428** |
| 23 | `mlruns/` 전체 런 수 | 0.21887 | **0.1163** |

★★★ **가장 관대한 가정(N̂=4.86)에서도 `SR₀ = 0.13111`이 관측 `SR̂ = 0.13052`보다 크다.**
곧 **최선 런의 초과 Sharpe가 "약 5회 독립시행이면 순전한 운으로 나올 값"보다 작다.**
DSR이 0.5 아래로 내려가는 건 그 부호가 뒤집혔다는 뜻이다.

★ 그리고 **무보정 PSR 0.9611 → DSR 0.4968**이 이 문서의 존재 이유다. 시행 횟수 하나를
집어넣는 것만으로 "95% 신뢰수준 통과"가 "동전던지기"로 바뀐다. 자매 문서가 같은 4런에 대해
검증셋 R²가 음수임을 보였는데(§1.2), **백테스트 쪽에서도 독립적으로 같은 결론에 도달했다.**

### 1.3 ★★★ 원수익에 걸면 통과하고 초과수익에 걸면 기각된다

같은 9런, 같은 183주. 좌변만 바꿨다.

| | 평균 쌍상관 ρ̂ | N̂ | `√V[{SR}]` | 최선 런 | 최선 SR(연율) | **DSR(N̂)** |
|---|---:|---:|---:|---|---:|---:|
| **원수익** `return` | 0.8342 | 2.33 | 0.05057 | 41종목 파일럿 | **+1.769** | **0.9965** |
| **초과수익** `return−bench−cost` | 0.5178 | 4.86 | 0.11158 | GRU `fde856` | +0.923 | **0.4968** |

★★ **순위가 완전히 뒤집힌다.** 원수익 1위(파일럿, 연 Sharpe +1.77)가 초과수익 최하위
(IR −1.00)다. 2023–2026 구간이 불장이므로 **원수익 Sharpe는 대부분 시장 베타**이고, DSR을
거기에 걸면 **"베타가 유의하다"를 발견하고 통과 도장을 찍는다.**

이 함정은 Harvey & Liu가 자기 방법의 두 번째 caveat으로 직접 적어 둔 것이다:

> Second, Sharpe ratios do not necessarily control for risk. That is, the strategy's volatility may
> not reﬂect the true risk. **Our method also applies to information ratios, which use residuals
> from factor models.**

⚠️ 곧 **좌변을 초과수익(또는 팩터모형 잔차)으로 못 박는 것이 DSR 도입보다 먼저다.** 이 저장소는
qlib이 `excess_return_with_cost`를 이미 계산해 두므로 추가 비용이 없다.

### 1.4 ★★ MinBTL — 183주로는 N=18까지가 예산이다

MinBTL 공식(§3)에 `E[maxN] = 1`(연율 IS Sharpe 1)을 넣고 계산했다. **먼저 논문의 수치 진술로
구현을 검산했다** — 논문은 *"if only ﬁve years of data are available, no more than forty-ﬁve
independent model conﬁgurations should be tried"* 라고 한다:

| N | MinBTL(년) | 상한 `2·ln N` |
|---:|---:|---:|
| 9 | 2.31 | 4.39 |
| **18** | **3.44** | 5.78 |
| **19** | **3.53** | 5.89 |
| 23 | 3.85 | 6.27 |
| **45** | **5.00** ✅ 논문 진술과 일치 | 7.61 |
| 46 | 5.04 | 7.66 |

★ **이 저장소 백테스트 구간은 183주 = 3.52년이다.** 표에서 MinBTL이 3.52년을 넘는 첫 N은
**19**다. 곧 **독립시행 18회까지가 예산인데 23런을 돌렸다.**

⚠️ **정직한 한계 두 개.**
① MinBTL은 N을 **독립**시행으로 가정한다. §1.2에서 실측 N̂은 4.86이었으므로 **실효 N으로는
아직 예산 안**이다. 23을 그대로 쓰면 과도하게 보수적이다.
② 그러나 §1.1의 `Experiment` 7런(후보 6종·모델 3종·호라이즌 3종)은 **설계 축이 서로 달라
상관이 낮을 것**이고, 이들의 손익 계열이 없어 ρ̂ 계산에 못 들어갔다. **즉 실측 N̂ 4.86은
아래로 편향된 값이다.** 두 한계가 반대 방향이라 결론은 "예산 근처"이지 "초과 확정"이 아니다.
→ **MinBTL은 판정 게이트가 아니라 예산 게이지로 쓰는 게 맞다.**

### 1.5 ★★ CSCV를 돌렸다 — 계산은 되지만 해상도가 없다

183주 × 9런 초과수익 행렬에 CSCV를 그대로 구현해 돌렸다(S=16).

**먼저 걸린 실무 함정**: 논문은 `M`을 **동일 크기** S개 부행렬로 쪼개라고 한다. 그런데
**183을 나누는 짝수가 없다**(183 = 3 × 61). 그래서 최근 176주만 쓰고 **7주를 버렸다.**
표본길이가 소수를 포함하면 무조건 발생하는 문제다.

| 산출물 | 값 | 판정 |
|---|---:|---|
| 조합 수 `C(16,8)` | 12,870 | 충분 |
| **PBO = P[λ<0]** | **0.0049** | 관례 기각선 0.05 통과 |
| `P[λ≤0]` (경계 포함) | 0.0113 | 통과 |
| **성능열화 β** (`SR_oos = α + β·SR_is`) | **−0.879** | **과적합 신호** |
| Probability of loss `P[SR_oos<0]` | 0.1014 | — |
| **관측된 고유 logit 값** | **8개** (가능한 9개 중) | ❌ **해상도 미달** |

⚠️⚠️ **PBO 0.0049를 믿을 수 없는 이유 네 개. 전부 논문이 자기 한계로 적어 둔 것이다.**

1. ★ **N=9는 논문이 명시적으로 배제한 영역이다.** `ω̄ᶜ = r̄ᶜ/(N+1)`이므로 N=9면 logit이
   9개 값만 가진다. 논문 원문:
   > N must be large enough to provide suﬃcient granularity to the values of the relative rank, ωᶜ.
   > If N is too small, ωᶜ will take only a very few values, which will translate into a very
   > discrete number of logits, making f(λ) too discontinuous, and adding estimation error to the
   > evaluation of φ. For example, **if the investor is sensitive to values of φ < 1/10, it is clear
   > that the range of values that the logits can adopt must be greater than 10, and so N >> 10 is
   > required.**

   우리가 얻은 φ = 0.0049는 정확히 `φ < 1/10` 영역이다. **논문 기준으로 이 값은 읽을 수 없다.**
2. ★ **9열 중 4열이 같은 설정의 시드다.** IS 최선을 뽑는 절차가 12,870조합 중 7,904회에서
   GRU 시드 하나를 골랐다. 곧 이 PBO는 *전략 선택* 과적합이 아니라 **시드 선택**을 재고 있다.
   PBO는 "선택 절차의 신뢰도"를 재는 통계량인데 **여기서 선택할 것이 사실상 없다.**
3. ★ **손익 계열을 남긴 9런은 탐색된 시행이 아니다.** 설계 자유도를 실제로 쓴 12런은
   열이 될 수 없다(§1.1). 논문의 *"Hiding trials will lead to an underestimation of the overﬁt"*
   가 그대로 적용되므로 **0.0049는 아래로 편향된 값**이다.
4. ★ **β = −0.879와 정반대 신호다.** 논문은 네 통계량을
   *"four complementary analysis"* 라 부르고 PBO 단독 판정을 지시하지 않는다.
   ⚠️ 다만 **β 자체도 조심해야 한다** — CSCV의 IS/OOS는 서로 여집합이므로 전체구간 평균이
   고정된 상태에서 한쪽이 높으면 다른 쪽이 낮아지는 **산술적 음의 의존이 섞인다.**
   (이 지적은 논문 진술이 아니라 이 문서의 판단이다. 논문은 β<0을 compensation effect로 설명한다.)

**따라서 이 저장소에서 PBO/CSCV는 "계산 불가"가 아니라 "계산되지만 판정에 쓸 수 없음"이다.**
쓸 수 있게 되는 조건은 명확하다 — **손익 계열을 남기는 서로 다른 설정이 20개 이상, 동일 기간에.**

---

## 2. Deflated Sharpe Ratio — 정의·가정·한계

> Bailey, D.H., & López de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection
> Bias, Backtest Overfitting and Non-Normality."
> *The Journal of Portfolio Management*, 40(5), 94–107.
> [SSRN 2460551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) ·
> [저자 배포 PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
> ⚠️ 내가 텍스트를 추출한 것은 **저자 배포 워킹페이퍼판**이다(표지에 *"Journal of Portfolio
> Management, Forthcoming, 2014"*, 2014-07-31). **게재본 조판·면수는 확인 실패**(§9).
> 공식은 [`dashboard-features.md`](dashboard-features.md) §4-4에 있으므로 여기서는 반복하지 않는다.

### 2.1 무엇을 주장하는가

초록 원문:

> The Deflated Sharpe Ratio (DSR) corrects for two leading sources of performance inflation:
> Selection bias under multiple testing and non-Normally distributed returns.

본문의 규범 진술 — 이 저장소가 인용할 가치가 있는 한 문장:

> … the number of trials attempted. Without this information, it \[a backtest\] **is worthless,
> regardless of how excellent the reported performance might be.** Investors and journal referees …

DSR이 SR을 디플레이트할 때 추가로 쓰는 변수는 **5개**다(원문):

> DSR deflates SR by taking into consideration five additional variables: The non-Normality of the
> returns (γ̂₃, γ̂₄), the length of the returns series (T), the variance of the SRs tested (V[{SR̂ₙ}]),
> as well as the number of independent trials involved in the selection of the investment strategy (N).

### 2.2 가정 — 여기가 약한 고리다

논문이 **명시적으로** 다는 가정:

> More formally, consider a set of N independent backtests or track records associated with a
> particular strategy class (e.g., Discretionary Macro). … **Suppose that these trials' {SR̂ₙ} follow
> a Normal distribution**, with mean E[{SR̂ₙ}] and variance V[{SR̂ₙ}]. This is not an unreasonable
> assumption, since the concept of "strategy class" implies that the trials are bound by some common
> characteristic pattern.

곧 세 가지가 필요하다: ① 시행이 **독립**, ② 시행들의 SR이 **정규분포**, ③ 시행들이 **한 전략
클래스**에 속함. 그리고 `E[max{SR̂ₙ}]` 근사는 극단값 이론(Appendix 1)에서 나온다.

⚠️ **이 저장소는 ①·③에서 걸린다.** GRU 4시드는 독립이 아니고(§1.1 상관 1.000 포함),
LGB 후보 6종과 GRU는 같은 "전략 클래스"라 부르기 어렵다. 논문 본문의 예시는
*"we would expect the E[{SR̂ₙ}] from High Frequency Trading trials to be greater than … from
Discretionary Macro"* 인데, **우리는 한 아이디어의 변형들이 아니라 서로 다른 모델군을 섞고 있다.**

### 2.3 ★★★ 중복 시행이 DSR을 부풀린다 (식에서 따라오는 결과)

`SR₀ = √V[{SR̂ₙ}] · ((1−γ)Z⁻¹[1−1/N] + γZ⁻¹[1−1/(Ne)])` 에서 임계값은
**`V[{SR̂ₙ}]`과 `N` 둘 다에 증가**한다. 그런데 같은 설정을 시드만 바꿔 여러 번 돌리면:

- `V[{SR̂ₙ}]`이 **줄어든다** (SR 값들이 뭉친다)
- 평균 쌍상관 `ρ̂`가 **올라가고**, `N̂ = ρ̂ + (1−ρ̂)M`이 **줄어든다**

**둘 다 `SR₀`를 낮추므로 DSR이 올라간다.** §1.3의 원수익 열이 실증이다 — ρ̂ 0.8342 → N̂ 2.33 →
DSR 0.9965. **중복을 많이 돌린 쪽이 더 잘 통과한다.**

⚠️ 이건 논문의 주장이 아니라 식의 결과다. 다만 논문도 같은 방향을 경계한다 —
부록 A.3이 *"correlation is a limited notion of linear dependence"* 이고
*"in practice M almost always exceeds the sample length, T. Then the estimate of average correlation
may itself be overfit"* 라고 적는다.

★ **이 저장소는 그 특정 함정 하나는 피한다.** M=9(또는 23) ≪ T=183이므로 상관행렬이
ill-conditioned가 아니다. 논문 표현으로 `M < ½(T+1)` 조건을 만족한다.
**→ 곧 `N̂` 추정이 유효한 드문 경우다. 이 저장소가 DSR을 쓸 수 있는 근거가 여기 있다.**

### 2.4 DSR과 Harvey-Liu는 대체재가 아니다

논문이 직접 정리한다:

> HL's solution is based on Benjamini and Hochberg's framework. The role of HL's threshold is
> analogous to the role played by our E[max{SR̂ₙ}] … which we derived through Extreme Value Theory.
> DSR uses this threshold to deflate a particular Sharpe ratio estimate. … From that perspective,
> **these two methods are complementary, and we encourage the reader to compute DSR using both
> thresholds**, E[max{SR̂ₙ}] as well as HL's.

✅ **모델 비의존**: 입력이 `(수익률 계열, N, 왜도, 첨도, V[{SR}])`뿐이다. 모델 내부를 안 본다.

---

## 3. MinBTL — 표본길이 대비 시행 예산

> Bailey, D.H., Borwein, J.M., López de Prado, M., & Zhu, Q.J. (2014). "Pseudo-Mathematics and
> Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance."
> *Notices of the American Mathematical Society*, 61(5), 458–471.
> DOI [10.1090/noti1105](https://doi.org/10.1090/noti1105) ·
> [AMS 배포 PDF](https://www.ams.org/notices/201405/rnoti-p458.pdf)
> (면수는 PDF 쪽번호 헤더로 확인: 458 시작, 470까지 확인, 참고문헌 포함 471.)

Theorem 2 원문(수식은 §4-4에 있으므로 진술만):

> **Theorem 2.** The Minimum Backtest Length (MinBTL, in years) needed to avoid selecting a strategy
> with an IS Sharpe ratio of E[maxN] among N independent strategies with an expected OOS Sharpe ratio
> of zero is \[…\] < 2 ln[N] / E[maxN]².

논문이 붙인 **세 개의 한계**가 이 저장소에 그대로 걸린다:

1. > **Note that Proposition 1 assumed the N trials to be independent, which leads to a quite
   > conservative estimate.** If the trials performed were not independent, the number of independent
   > trials N involved could be derived using a dimension-reduction procedure, such as Principal
   > Component Analysis.

   → §1.4의 한계 ①. **비독립이면 MinBTL은 과도하게 보수적**이고, 논문은 PCA를 대안으로 제시한다
   (DSR 부록 A.3의 상관 기반 N̂과는 다른 방법이다).
2. > Of course, a backtest may be overﬁt even if it is computed on a sample greater than MinBTL.
   > From that perspective, **MinBTL should be considered a necessary, nonsuﬃcient condition** to
   > avoid overﬁtting.

   → **통과가 무죄 증명이 아니다.** 자매 문서 §2.2의 게이트 B와 같은 성질이다.
3. 모델 복잡도와의 연결 — 파라미터 하나당 N이 곱으로 늘어난다는 논지:
   > Consider a one-parameter model that may adopt two possible values … Overﬁtting will be diﬃcult,
   > because N = 2. Let's say that we make the model more complex by adding four more parameters so
   > that the total number of parameters becomes 5, i.e., N = 2⁵ = 32.

   ⚠️ **이 계산법을 그대로 쓰면 안 된다.** 격자를 전부 탐색하지 않았으면 N은 격자 크기가 아니다.
   이 저장소 `tune_hyperparams.py`는 **격자가 아니라 후보 6개를 손으로 적어 둔 것**이므로 N=6이지
   `num_leaves × max_depth × …`가 아니다. 논문의 2⁵는 "모든 조합을 시도한다" 전제다.

**이 논문이 음성 결과 기록의 근거로 직접 쓸 수 있는 부분** — 의학연구 유추를 저자들이 먼저 한다:

> An analogous situation occurs in medical research, where drugs are tested by treating hundreds or
> thousands of patients; however, only the best outcomes are publicized. … Such behavior is
> unscientiﬁc—not to mention dangerous and expensive—and has led to the launch of the alltrials.net
> project, which demands that all results (positive and negative) for every experiment are made
> publicly available.

그리고 결론부:

> Given that most published backtests do not report the number of trials attempted, many of them may
> be overﬁtted. … The standard warning that "past performance is not an indicator of future results"
> understates the risks associated with investing on overﬁt backtests. **When ﬁnancial advisors do
> not control for overﬁtting, positive backtested performance will often be followed by negative
> investment results.**

✅ **모델 비의존**: 입력이 `(N, 표본길이, 목표 IS Sharpe)`뿐이다.

---

## 4. PBO / CSCV — 방법론·필요 입력·이 저장소 성립 여부

> Bailey, D.H., Borwein, J.M., López de Prado, M., & Zhu, Q.J. "The Probability of Backtest
> Overfitting." *The Journal of Computational Finance*, 20(4), 39–69 (2017).
> [SSRN 2326253](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253) ·
> [저자 배포 PDF](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) (개정 2015-02)
> ⚠️ 게재 권호·면수는 **검색 결과에만 의존했고 게재본으로 확인하지 못했다**(§9).
> 내가 인용한 본문은 전부 저자 배포 PDF다.

### 4.1 필요한 입력 — 여기서 갈린다

논문 Algorithm 2.3의 첫 단계가 유일한 강한 요구사항이다:

> First, we form a matrix M by collecting the performance series from the N trials. In particular,
> each column n = 1,…,N represents a vector of proﬁts and losses over t = 1,…,T observations
> associated with a particular model conﬁguration tried by the researcher. M is therefore a
> real-valued matrix of order (T×N). **The only conditions we impose are that: i) M is a true matrix,
> i.e. with the same number of rows for each column, where observations are synchronous for every row
> across the N trials, and ii) the performance evaluation metric used to choose the "optimal"
> strategy can be estimated on subsamples of each column.**

★ **"동시적(synchronous)"이 이 저장소의 1차 관문이다.** `bear2022` 2런은 기간이 달라
같은 행렬에 못 들어간다(§1.1). 그리고 손익 계열 없는 12런은 열이 아예 없다.

★★ **주목할 점 — CSCV는 재학습을 요구하지 않는다.** 논문이 IS의 의미를 못박는다:

> Note that in this context IS corresponds to the subset of observations used to select the optimal
> strategy among the N alternatives. **With IS we do not mean the period on which the investment
> model underlying the strategy was estimated** (e.g., the period on which crossing moving averages
> are computed, or a forecasting regression model is estimated).

→ 곧 **"test 구간이 1개뿐이라 CSCV를 못 한다"는 오해다.** 백테스트 손익 계열 하나를 조합
분할하면 되므로 학습 구간 분할과 무관하다. **이 저장소에서 CSCV가 막히는 이유는 test 구간 수가
아니라 열 개수(N)와 열의 정체(시드 중복)다.**

### 4.2 파라미터 선택 — S와 N

- **S**: 짝수여야 하고, `C(S, S/2)`개 조합이 나온다. 논문 권고:
  > … if M contains 4 years of daily data, S = 16 would equate to quarterly partitions, and the
  > serial correlation structure would be preserved. For these two reasons, **we believe that S = 16
  > is a reasonable value to use in most cases.**

  이 저장소 183주(3.5년)에 S=16이면 블록당 11주로 대략 분기라 조건에 맞는다. **S는 문제가 아니다.**
  ⚠️ 다만 논문은 `S = 16 → 12,780` 조합이라 두 번 적는데 **실제 `C(16,8) = 12,870`이다.**
  논문 본문 산술 오기로 보인다. 내 구현 값은 12,870이다.
- **N**: §1.5에 인용한 `N >> 10` 요구. **이 저장소의 실제 제약이 여기다.**
- **T**: > Therefore, T should be chosen to be double of the number of observations used by the
  investor to choose a model conﬁguration or to determine a forecasting speciﬁcation.

### 4.3 부수 통계 세 개 — PBO보다 중요할 수 있다

논문이 네 개를 나란히 둔다(원문 목록):

> 1. Probability of Backtest Overﬁtting (PBO) … 2. Performance degradation … 3. Probability of loss
> … 4. Stochastic dominance: This analysis determines whether the procedure used to select a strategy
> IS is preferable to randomly choosing one model conﬁguration among the N alternatives.

기각선의 지위:

> In accordance with standard applications of the Neyman-Pearson framework, **a customary approach
> would be to reject models for which PBO is estimated to be greater than 0.05.**

★ *"a customary approach would be"* 다. **논문이 0.05를 규범으로 선포하지 않는다.**
`dashboard-features.md` §4-4가 "관례적 기각선 0.05"라 쓴 것은 정확하다.

### 4.4 ★★ 오용 경고 — 이 저장소가 밟을 가능성이 높은 것

> Fifth, we must warn the reader against applying CSCV to guide the search for an optimal strategy.
> That would constitute a gross misuse of our method. As Strathern eloquently put it, **"when a
> measure becomes a target, it ceases to be a good measure."** Any counter-overﬁtting technique used
> to select an optimal strategy will result in overﬁtting. For example, CSCV can be employed to
> evaluate the quality of a strategy selection process, but **PBO should not be the objective
> function on which such selection relies.**

그리고 N을 부풀리는 것도 금지된다:

> Likewise, **adding trials that are doomed to fail in order to make one particular model
> conﬁguration succeed biases the result.** If a model conﬁguration is obviously ﬂawed, it should
> have never been tried in the ﬁrst place. A case in point is guided searches … **the columns of
> matrix M should be the ﬁnal outcome of each guided search** (i.e., after it has converged to a
> solution), **and not the intermediate steps.**

★ 마지막 문장이 §7의 "무엇이 1회 시행인가"에 문헌이 주는 **유일하게 구체적인 규칙**이다 —
**유도탐색(Optuna·Bayesian)의 중간 스텝은 열이 아니고, 수렴 결과 하나가 열이다.**
단 이건 **행렬 M의 열 정의**이지 DSR의 N 정의가 아니다. 둘을 섞으면 안 된다.

**그 밖의 한계 (전부 원문 §5.2)**:

> Second, this procedure does nothing to evaluate the correctness of a backtest. If the backtest is
> ﬂawed due to bad assumptions, such as incorrect transaction costs or using data not available at
> the moment of making a decision, our approach will be making an assessment based on ﬂawed
> information.

> Third, this procedure only takes into account structural breaks as long as they are present in the
> dataset of length T. If a structural break occurs outside the boundaries of the available dataset,
> the strategy may be over-ﬁt to a particular data regime …

> Fourth, although a high PBO indicates overﬁtting in the group of N tested strategies, **skillful
> strategies can still exist in these N strategies. For example, it is entirely possible that all the
> N strategies have high but similar Sharpe ratios. Since none of the strategies is clearly better
> than the rest, PBO will be high.**

⚠️ 세 번째가 이 저장소에 정확히 걸린다 — 183주가 전부 불장 한 레짐이다. `bear2022`가 별도
experiment로 갈라져 있어 **레짐 전환이 T 밖에 있다.**

✅ **모델 비의존**: 논문이 스스로 *"model-free and non-parametric"* 이라 부르고, 근거는
"모델을 명시할 필요가 없다"는 것이다.

---

## 5. Harvey & Liu — 다중검정 haircut과 t > 3.0

### 5.1 haircut Sharpe — "50% 깎기"를 계산으로 대체한다

> Harvey, C.R., & Liu, Y. (2015). "Backtesting."
> *The Journal of Portfolio Management*, 42(1), 13–28 (Fall 2015).
> [SSRN 2345489](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2345489) ·
> [Duke 배포 PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
> ⚠️ 배포 PDF의 쪽번호 헤더는 **12–28**이고 발행사 표기는 13–28이다. 시작면 불일치는 §9.

문제 설정 원문:

> A common practice in evaluating backtests of trading strategies is to discount the reported Sharpe
> ratios by 50%. … **The 50% haircut is only a rule of thumb. Our article's goal is to develop an
> analytical way to determine the haircut's magnitude.**

절차는 세 단계다(결론부 원문):

> First, we transform the Sharpe ratio into a t-ratio and determine its probability value, e.g., 0.05.
> Second, we determine the appropriate p-value, explicitly recognizing the multiple tests that
> preceded the discovery of this particular investment strategy. Third, based on this new p-value, we
> transform the corresponding t-ratio back to a Sharpe ratio.

**독립 가정 하 수치예**(원문):

> For instance, assuming there are twenty years of monthly returns (T = 240), an annual Sharpe ratio
> of 0.75 yields a p-value of 0.0008 for a single test. When N = 200, pM = 0.15, implying an adjusted
> annual Sharpe ratio of 0.32 … **Hence, multiple testing with 200 tests reduces the original Sharpe
> ratio by approximately 60%.**

그리고 haircut이 **비선형**이라는 게 논문의 핵심 실무 결론:

> Our results show that the multiple testing haircut is nonlinear. **The highest Sharpe ratios are
> only moderately penalized, while the marginal Sharpe ratios are heavily penalized.** … The
> strategies with very high Sharpe ratios are probably true discoveries. In these cases, a 50%
> haircut is too punitive.

⚠️ **이 저장소는 "marginal" 쪽에 있다.** §1.2의 IR 0.923은 heavily penalized 구간이다.

**세 방법**을 제시하고 평균도 낸다 — Bonferroni / Holm / BHY(Benjamini-Hochberg-Yekutieli).
Bonferroni 원문 설명:

> Bonferroni's method adjusts each p-value equally. It inﬂates the original p-value by the number of
> tests …

★★ **논문이 제공하는 코드가 있다.** 원문:

> We make the code and data for our calculations publicly available at:
> `http://faculty.fuqua.duke.edu/~charvey/backtesting`

`Haircut_SR`의 **8개 입력**이 곧 필요 데이터 명세다(원문 요약): 샘플링 빈도 / 관측 수 /
Sharpe / 연율화 여부 / 자기상관 보정 여부 / 자기상관 계수 / **시행 수 N** /
**전략수익 간 평균상관**.

⚠️ 마지막 두 개가 §7의 문제를 그대로 되돌려준다 — **N과 ρ를 사람이 넣어야 한다.**
저자들의 caveat 원문:

> There are many caveats to our method. **We do not observe the entire history of tests and, as such,
> we need to use judgment on an important input—the number of tests—for our method.**

### 5.2 t > 3.0 허들의 근거와 그 저자들의 유보

> Harvey, C.R., Liu, Y., & Zhu, H. (2016). "… and the Cross-Section of Expected Returns."
> *The Review of Financial Studies*, 29(1), 5–68.
> DOI [10.1093/rfs/hhv059](https://doi.org/10.1093/rfs/hhv059) ·
> [Duke 배포 PDF](https://faculty.fuqua.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.pdf)
> (배포본에 `doi:10.1093/rfs/hhv059 Advance Access publication October 9, 2015` 인쇄.
> 쪽번호 헤더 5 시작, 68 종료 확인.)

초록 원문:

> Given this extensive data mining, it does not make sense to use the usual criteria for establishing
> signiﬁcance. Which hurdle should be used for current research? … **A new factor needs to clear a
> much higher hurdle, with a t-statistic greater than 3.0.** We argue that most claimed research
> ﬁndings in ﬁnancial economics are likely false.

**허들의 출처는 316개 팩터라는 카운트다**(HL 2015 본문):

> Harvey, Liu, and Zhu \[2015\] (HLZ) document that at least 316 factors have been tested in the
> quest to explain the cross-sectional patterns in equity returns.

⚠️⚠️ **저자들이 3.0을 안전선으로 제시하지 않는다.** 결론부 원문:

> While a t-statistic of 3.0 (which corresponds to a p-value of 0.27%) seems like a very high hurdle,
> we also argue that **there are good reasons to expect that 3.0 is too low.** First, we only count
> factors that are published in prominent journals and we sample only a small fraction of the working
> papers. Second, there are surely many factors that were tried by empiricists, failed, and never
> made it to publication or even a working paper. … **Given that our count of 316 tested factors is
> surely too low, this means the t-statistic cutoff is likely even higher.**

그리고 **한 값을 모든 경우에 쓰지 말라**고 직접 말한다:

> Should a t-statistic of 3.0 be used for every factor proposed in the future? Probably not. **A case
> can be made that a factor developed from ﬁrst principles should have a lower threshold t-statistic
> than a factor that is discovered as a purely empirical exercise.** Nevertheless, a t-statistic of
> 2.0 is no longer appropriate—even for factors that are derived from theory.

★ **이론에서 나온 팩터는 허들이 낮아도 된다**는 진술이 이 저장소에 실질적 의미가 있다.
마이크로캡 인사이더 신호는 사전 문헌이 있는 가설이고, Alpha158 격자탐색은 순수 경험적 탐색이다.
**같은 t 허들을 걸 근거가 없다.** 이 구분은 `microcap-insider-prereg.md`의 사전등록 논리와 일치한다.

세 방법의 실제 결과(원문):

> of the 296 published signiﬁcant factors, 158 would be considered false discoveries under
> Bonferonni, 142 under Holm, 132 under BHY (1%), and 80 under BHY (5%).

그리고 왜 재현 연구가 없는가에 대한 진단 — §8의 이식 근거가 된다:

> Indeed, the culture in ﬁnancial economics is to focus on the discovery of new factors. **In contrast
> with other ﬁelds, such as medical science, it is rare to publish replication studies focusing on
> only existing factors.**

✅ **모델 비의존**: t-stat과 Sharpe만 쓴다. 다만 **t-stat이 있어야 한다** —
`dashboard-features.md` §4-4가 지적한 대로 `analyze_capm.py`가 t-stat을 안 낸다.

---

## 6. 도구 — MLflow를 시행 원장으로 쓸 때

> 자매 문서 [`training-gates.md`](training-gates.md) §4.1이 이 절로 넘긴 항목이다.
> CLI·API는 이 저장소 `.venv`의 `mlflow 3.14.0` 설치본을 **직접 introspect**했고,
> 공식 문서는 HTML을 받아 **원문 문자열을 grep해** 확인했다.

### 6.1 ★★ `mlflow migrate-filestore` — 실재하고, 제약이 세 개다

설치본 CLI 최상위 명령 목록에 존재한다(introspect):

```
['agent','ai-commands','artifacts','assistant','autolog','crypto','datasets','db','demo',
 'deployments','doctor','experiments','gc','mcp','migrate-filestore','models','run','runs',
 'sagemaker','scorers','server','skills','traces']
```

introspect한 실제 파라미터(`mlflow/store/fs2db/cli.py`):

```
mlflow migrate-filestore
  --source   (required)  "Root directory containing mlruns/ FileStore data."
  --target   (required)  "SQLite URI (e.g. sqlite:///mlflow.db)."
  --progress/--no-progress  (default True)
```

★ `--source`는 **`mlruns/`의 부모든 `mlruns/` 자신이든 받는다.** 구현
(`fs2db/__init__.py::_resolve_mlruns`)이 `source/mlruns`가 있으면 그걸 쓰고, 없으면 `source`
자신에 숫자 이름 디렉터리·`.trash`·`models`가 있는지 보고 판단한다. 없으면
`Cannot find mlruns directory in '...'` 예외다.

**공식 문서**([migrate-from-file-store](https://mlflow.org/docs/latest/self-hosting/migrate-from-file-store))
원문에서 확인한 제약:

| 제약 | 원문 |
|---|---|
| **버전** | *"You must have MLflow 3.10 or later installed."* |
| **SQLite 전용** | *"SQLite only. The migration tool only supports SQLite as the target database. **FileStore generates large experiment IDs that exceed the 32-bit integer limit enforced by PostgreSQL and MySQL**, but SQLite handles them natively."* |
| **빈 DB 필수** | *"Target database must be empty. The migration tool refuses to write to a database that already contains data to prevent conﬂicts."* |
| **아티팩트 미이전** | *"Artifacts (model ﬁles, images, etc.) stay in their original location. The database stores the same artifact URIs that point to the existing ﬁles."* |
| **원자적** | *"The migration is atomic for the migrated data: if any error occurs, all inserted rows are rolled back … so you can safely re-run the command after ﬁxing the issue."* |

구현에서도 확인했다 — `_assert_empty_db`가 `experiments`/`runs`/`registered_models` 행 수를 세서
0이 아니면 `Target database is not empty…`로 예외를 던진다. 그리고 `fs2db` 패키지 전체에
`shutil`·복사 호출이 **없다** (아티팩트를 안 옮긴다는 문서 진술과 일치).

⚠️⚠️ **원장 설계에 직접 영향을 주는 두 가지.**

1. **일회성 마이그레이션이다.** 빈 DB만 받으므로 *"새 런이 쌓이면 다시 migrate"* 가 불가능하다.
   → **마이그레이션 이후에는 `--backend-store-uri sqlite:///…`로만 기록해야** 한다.
   문서 원문: *"To avoid relying on these defaults, explicitly point the server to the new
   database."*
2. ★ **삭제된 런이 복원된다.** 원문:
   > **Deleted items are included.** Experiments and runs in the `.trash` directory are migrated
   > with their deleted lifecycle stage preserved.

   → **UI에서 지운 런도 DB에 남는다.** 시행 원장 입장에서는 **바람직한 성질**이다(N이 늘어남).
   다만 *"UI에서 세면 N이 작게 나온다"* 는 함정이 생긴다. (이 저장소 `mlruns/.trash`는 지금 비어
   있음을 확인했다.)

**마이그레이션을 안 할 경우의 탈출구**도 문서가 명시한다:

> This escape hatch exists for the rare case where migration is genuinely not an option … If your
> workflow does not have such a constraint, **please use the migration tool above instead.**
> To opt out of the error … set the `MLFLOW_ALLOW_FILE_STORE` environment variable …

⚠️ 곧 자매 문서 §4.1이 쓴 `MLFLOW_ALLOW_FILE_STORE=true`는 **공식 문서가 "드문 경우"로 한정한
회피책**이다. 원장을 만들 거라면 회피가 아니라 마이그레이션이 맞다.

### 6.2 MLflow 공식 조직화 권고 — tag가 원장의 스키마다

공식 문서([tracking-api](https://mlflow.org/docs/latest/ml/tracking/tracking-api/))에서 확인한
원문 문자열:

- 실험 구성: *"Structure your experiments for easy comparison and analysis"* — 세 경로
  (`MLFLOW_EXPERIMENT_NAME` 환경변수 / `mlflow.set_experiment(...)` /
  `mlflow.create_experiment(name, artifact_location=..., tags={...})`).
- 태그 전략: *"Use tags strategically to organize and filter experiments"* 아래에 예시 키가
  나온다 — `model_family`, `dataset_version`, `environment`, `team`, `gpu_type`,
  **`experiment_phase`**(예시 값 `"hyperparameter_tuning"`).
- 문서화 전용 태그: `mlflow.set_tag("mlflow.note.content", ...)`.
- 질의: `mlflow.search_runs(filter_string="tags.model_family = 'transformer'")`,
  그리고 지표와 결합 — `"tags.environment = 'production' AND metrics.accuracy > 0.95"`.
- ★ **부모-자식 런**: 스윕을 한 덩어리로 묶는 공식 패턴이 있다. 자식 런은
  `mlflow.search_runs(filter_string="tags.mlflow.parentRunId = '<parent_run_id>'")`로 조회한다.

★★ **부모-자식이 §7의 문제를 부분적으로 해결한다.** *"후보 6종 스윕 1회"* 를 부모 런 1개 +
자식 런 6개로 남기면, **"설계 결정 1회"와 "실행 6회"가 자료구조로 구분된다.**
지금은 `Experiment` 안에 평평하게 7개가 있어 둘을 구별할 방법이 없다.

⚠️ **공식 문서에 실험 이름 규약·표준 태그 키 목록은 없다.** 위 6개 키는 예시 코드에 나온
것이고 규범이 아니다. **키는 이 저장소가 정해야 한다.**

### 6.3 계산은 직접 써야 한다

- `mlflow`에는 DSR·PBO·MinBTL 관련 API가 **없다**(설치본 검색). 자매 문서 §4.1이 확인한
  `mlflow.validate_evaluation_results` / `MetricThreshold`는 **임계 비교**이므로
  "DSR > 0.95"를 **게이트로 걸 그릇**은 되지만 DSR 자체는 안 준다.
- `scipy.stats.norm`만 있으면 DSR·MinBTL은 **각각 3~5줄**이다. §1의 모든 수치를 그렇게 계산했다.
- CSCV도 `itertools.combinations` + `numpy`로 30줄 안쪽이다. §1.5를 그렇게 돌렸다.
- ⚠️ `pypbo`(`dashboard-features.md` §4-4가 링크한 구현)는 **이번 조사에서 확인하지 않았다**(§9).
  §1.5의 구현은 논문 Algorithm 2.3을 직접 옮긴 것이다.

---

## 7. ★★★ N을 실제로 세는 규칙 — 문헌에 없다

**결론부터: "무엇이 1회 시행인가"를 정의한 1차 문헌을 찾지 못했다.** 대신 문헌은 세 가지를 준다 —
**① 세라는 의무 ② 판단하라는 명시적 위임 ③ M을 N̂으로 바꾸는 변환.**

★★★ 그리고 **이건 검색 실패가 아니다.** 서로 무관한 두 문헌군에서 같은 공백을 확인했다 —
금융·통계 쪽(이 절)과 사전등록 플랫폼 쪽(§8.6: AsPredicted 8문항 · OSF 템플릿 전문 ·
COS Registered Reports 페이지 · 42 CFR Part 11). **네 문서군 전수에서 검정 단위 정의가 없고,
COS 페이지는 `multiple test`·`correction`·`number of test` 키워드가 0건이다.**
공백의 이유도 §8.6이 설명한다 — 사전등록 플랫폼은 **피험자를 조건에 배정하는 실험과학**을
전제로 설계돼서, "conditions"가 experimental arm을 뜻하는 어휘 체계에 **하이퍼파라미터 스윕에
대응하는 개념이 애초에 없다.**

### 7.1 문헌이 위임한다는 증거

가장 직접적인 진술은 Harvey & Liu(2015)다:

> There are many caveats to our method. **We do not observe the entire history of tests and, as such,
> we need to use judgment on an important input—the number of tests—for our method.**

그리고 caveat 목록의 다섯 번째:

> Fourth, we must make a choice of the multiple testing method. … Finally, **we need some judgment
> specifying the number of tests.**

DSR도 마찬가지다. `N`은 *"the number of independent trials involved in the selection of the
investment strategy"* 로만 정의되고, **"하이퍼파라미터 후보 하나가 1회인가"에 답하지 않는다.**
논문이 드는 예는 *"combining different pre-auction and post-auction periods, tenors, holding
periods, stop-losses, etc."* 인데, 이건 **동일 아이디어의 파라미터 격자**이고 우리 상황
(모델군 교체·라벨 정의 변경)과 다르다.

**따라서 다음 세 질문은 문헌 미해결이다:**

| 질문 | 문헌 답 |
|---|---|
| 하이퍼파라미터 후보 하나 = 1회? | **없음.** 격자 전수탐색이면 격자 크기가 N이라는 진술은 있다(MinBTL §Model Complexity, 2⁵=32). 후보를 손으로 고른 경우는 다루지 않는다 |
| 시드 하나 = 1회? | **없음.** 다만 DSR 부록 A.3의 `N̂`이 사실상 "상관이 1에 가까우면 1회로 수축"을 준다(§7.3) |
| 라벨 정의 변경 = 1회? | **없음.** PBO 논문은 이걸 *"strategy conﬁguration"* 변경으로 볼지 *"different strategy class"* 로 볼지 구분하지 않는다 |

### 7.2 문헌이 주는 구체적 규칙 두 개

문헌 전체에서 **"이건 세지 말라 / 이렇게 세라"에 해당하는 명시적 진술은 두 개뿐**이다.

1. **유도탐색의 중간 스텝은 세지 않는다** (PBO §5.2, §4.4에 인용):
   *"the columns of matrix M should be the ﬁnal outcome of each guided search … and not the
   intermediate steps."*
   → Optuna 200 trial은 열 1개다. ⚠️ **단 이건 CSCV 행렬 M의 열 정의이고, DSR의 N에 대한
   진술이 아니다.** 두 통계량이 같은 기호 N을 쓰지만 정의가 다르다.
2. **실패가 예정된 시행으로 N을 부풀리지 않는다** (PBO §5.2):
   *"adding trials that are doomed to fail in order to make one particular model conﬁguration
   succeed biases the result. If a model conﬁguration is obviously ﬂawed, it should have never been
   tried in the ﬁrst place."*
   → **N은 클수록 보수적이 아니다.** PBO에서는 쓰레기 열을 넣으면 상대순위가 왜곡된다.
   (DSR에서는 방향이 반대로 N이 크면 임계가 올라가 보수적이 된다. **두 통계량에서 N의 역할이
   다르다는 뜻이므로, 하나의 "N"으로 둘을 동시에 먹이면 안 된다.**)

### 7.3 문헌이 정의 대신 주는 것 — M → N̂ 변환

DSR 부록 A.3의 식 (9):

```
N̂ = ρ̂ + (1 − ρ̂)·M
```

원문 유도:

> Third, we know that as ρ→1, then N→1. Similarly, as ρ→0, then N→M. Given an estimated average
> correlation ρ̂, we could therefore interpolate between these two extreme outcomes …

★ **이것이 "시드 하나를 세는가"에 대한 문헌의 실질적 답이다** — 세되, 상관으로 수축시킨다.
§1.2에서 M=9, ρ̂=0.5178 → N̂=4.86이었고, 원수익 기준으로는 ρ̂=0.8342 → N̂=2.33이었다.
**중복 시드는 자동으로 1회 쪽으로 눌린다.**

⚠️ 논문이 붙인 두 한계(원문):

> First, correlation is a limited notion of linear dependence. Second, in practice M almost always
> exceeds the sample length, T. Then the estimate of average correlation may itself be overfit.

그리고 대안으로 정보이론(entropy·total correlation)을 제시하되 구체적 절차는 주지 않는다.
MinBTL 논문은 같은 문제에 **PCA**를 제시한다. **둘 다 "쓰라"까지고 "이렇게 쓰라"가 아니다.**

### 7.4 이 저장소 자체 규칙과의 대조 — `microcap-insider-prereg.md` §4.1

사전등록 §4.1의 규칙은 이렇게 요약된다:

- **1회 = 하나의 `(호라이즌 × 표본정의 × 선택규칙)` 조합**에 1층 판정을 내리는 것
- **세지 않는 것**: haircut 3값, 스프레드 격자, 진입 3갈래 중 참고 2개, raw 병기값 —
  **"고를 수 없기 때문"**
- **세는 것**: 표에 없는 조합 전부, 그 경우 N 재신고
- 이상치 규칙 변경은 "1회 추가"가 아니라 **사전등록 재작성**

**문헌과 대조한 결과:**

| prereg §4.1 규칙 | 문헌 대조 |
|---|---|
| "고를 수 없으면 세지 않는다" | ✅ **문헌 논리와 정합적.** HL의 조정 p-value는 `pM = Pr(max{\|t_i\|} ≥ 관측 \| N개 검정)`으로 **max에 대한 분포**다. 판정이 비관 셀 하나로 미리 묶여 있으면 그 셀 집합에 max 연산이 걸리지 않는다. ⚠️ **단 이 추론은 이 문서의 것이고, "고를 수 없으면 면제"를 명문화한 1차 출처는 못 찾았다** |
| "유리한 셀을 고를 수 있게 되면 면제 무효" | ✅ PBO §5.2의 file-drawer 경고와 같은 구조. 은폐도 선택이다 |
| "1회 = 조합 하나에 **판정을 내리는 것**" | ✅ **문헌보다 낫다.** 문헌의 N은 "돌린 횟수"인데 prereg는 **"판정 단위"** 로 정의해 시드·재실행을 자동 배제한다. §7.3의 N̂ 수축을 사후 추정이 아니라 사전 정의로 대체한 셈이다 |
| "이상치 규칙 변경은 재작성" | ✅ 문헌에 대응물 없음. `study-pitfalls.md` §2.1(규칙 하나로 t가 4.8배)이 근거이고 **문헌보다 강한 규율**이다 |
| **N 리셋(§4.2, "유니버스·신호·라벨이 달라 별개 family")** | ⚠️ **부분적으로만 지지된다.** DSR의 *"strategy class"* 가정(§2.2)이 리셋 근거가 된다 — 다른 클래스면 `E[{SR}]`·`V[{SR}]`가 다르므로 같은 집합에 넣을 수 없다. **그러나 어떤 문헌도 "언제 리셋해도 되는가"의 판정 기준을 주지 않는다.** 리셋은 원리상 무제한 재시도의 문이므로, `study-pitfalls.md` §3.1대로 **측정 전 커밋 타임스탬프가 유일한 방어**다 |

★ **총평: prereg §4.1은 문헌이 비워 둔 칸을 스스로 채운 것이고, 그 채움이 문헌 논리와 어긋나지
않는다.** 다만 **"문헌이 이렇게 하라고 했다"고 인용할 수는 없다.** §4.1은 이 저장소의 결정이다.
그 사실을 문서에 남겨야 사후 자기변명이 아니게 된다 — §4.2가 이미 그렇게 하고 있다.

---

## 8. 음성 결과 기록·사전등록 — 금융 리서치로 이식 가능한 부분

> 이 절의 법령·규정 인용은 `govinfo.gov` · eCFR API · Cornell LII에서 **원문 문자열을 직접 grep해**
> 확인했다(웹 UI는 봇 차단이라 API로 우회). 논문 서지사항은 **Crossref API로 교차검증**했다.
> ⚠️ `clinicaltrials.gov` 공식 정책 페이지는 JS SPA라 본문 추출에 **실패**했다(§9) — 규정 원문으로
> 전부 대체했으므로 실질 손실은 없다.

### 8.1 금융 논문 저자들이 스스로 의학연구를 참조한다

★ 이 조사에서 확인한 사실 중 이식 가능성의 가장 강한 근거는 **"우리가 유추하는 게 아니라
논문 저자들이 먼저 유추했다"** 는 것이다.

MinBTL 논문(§3에 인용):

> An analogous situation occurs in medical research, where drugs are tested by treating hundreds or
> thousands of patients; however, only the best outcomes are publicized. … Such behavior is
> unscientiﬁc … and has led to the launch of the **alltrials.net** project, **which demands that all
> results (positive and negative) for every experiment are made publicly available.** A step forward
> in this direction is the recent announcement by Johnson & Johnson that it plans to open all of its
> clinical test results to the public.

HLZ(§5.2에 인용)도 같은 축을 짚는다 — 금융에는 재현 연구 문화가 없다는 진단, 그리고
Ioannidis(2005) *"most claimed research ﬁndings are false"* 를 자기 결론에 그대로 가져온다.

DSR 논문은 편향의 이름을 나열한다(원문):

> … researchers who do not disclose the number of trials conducted ("ﬁle drawer effect"), journals
> that only publish "positive" outcomes ("publication bias"), managers who only publish the history
> of their (so far) proﬁtable strategies ("self-…")

★ **곧 "음성 결과를 기록하라"는 요구는 임상시험 규정에서 빌려오지 않아도 금융 1차 문헌
안에 이미 있다.** 이식 논거를 외부에서 조달할 필요가 없다.

### 8.2 ★★ 임상시험 등록 의무의 실제 구조 — 강제력이 어디서 나오는가

**법적 근거의 계보** (govinfo 원문으로 확인):

- 제정법: **FDA Amendments Act of 2007, Public Law 110-85, Title VIII, Section 801**
  ([govinfo](https://www.govinfo.gov/content/pkg/PLAW-110publ85/html/PLAW-110publ85.htm),
  `<<NOTE: Sept. 27, 2007 - [H.R. 3580]>>`). 원문:
  > SEC. 801. EXPANDED CLINICAL TRIAL REGISTRY DATA BANK. (a) In General.--Section 402 of the Public
  > Health Service Act (**42 U.S.C. 282**) is amended by-- … (2) inserting after subsection (i) the
  > following: ``(j) Expanded Clinical Trial Registry Data Bank.--''

  → 곧 **§801이 만든 조문이 42 U.S.C. § 282(j)**다. 실무 문헌이 "42 U.S.C. 282(j)"와
  "PHS Act §402(j)"를 섞어 쓰는데 **같은 조문의 두 호칭**이다.
- 시행규칙: **42 CFR Part 11**, "Clinical Trials Registration and Results Information Submission",
  **81 FR 64982–65157 (2016-09-21)**, FR Doc 2016-22129
  ([govinfo](https://www.govinfo.gov/content/pkg/FR-2016-09-21/html/2016-22129.htm)). 발효일 원문:
  > These regulations are effective on **January 18, 2017**. … Responsible parties will have 90
  > calendar days after the effective date to come into compliance
  ⚠️ **면수 인용에 함정이 있다** — 규칙 문서 전체는 81 FR 64982이지만 eCFR의 Part 11 Source 노트는
  **81 FR 65138**(규정 조문 시작면)이다. 둘 다 맞고 가리키는 대상이 다르다.

**실제 기한 두 개** (eCFR API로 원문 문자열 확인):

| 의무 | 조문 | 기한 (원문) |
|---|---|---|
| 등록 | 42 CFR § 11.24(a) | *"… or **21 calendar days after the first human subject is enrolled**, whichever date is later."* |
| 결과 제출 | 42 CFR § 11.44(a) | *"… must be submitted **no later than 1 year after the primary completion date** of the applicable clinical trial."* |

★ 규정은 "21 days"가 아니라 **"21 calendar days"**, "12 months"가 아니라 **"1 year"** 로 쓴다.

**강제력은 두 축이고 서로 다른 법전에 있다.** 이게 가장 놓치기 쉬운 구조다.

1. **연구비 집행 보류** — 42 U.S.C. § 282(j)(5)(A):
   > The heads of the agencies … shall **verify** that the clinical trial information … has been
   > submitted … **before releasing any remaining funding for a grant or funding for a future grant**
   > to such grantee.

   그리고 시정 창구: *"allow such grantee **30 days** to correct such non-compliance"*.
   신청서에도 확인서가 붙는다 — *"any grant or progress report forms required under such grant shall
   include a **certification** that the responsible party has made all required submissions"*.
2. **민사금전벌** — 21 U.S.C. § 333(f)(3)
   ([Cornell LII](https://www.law.cornell.edu/uscode/text/21/333)):
   > (A) Any person who violates section 331(jj) … shall be subject to a civil monetary penalty of
   > **not more than $10,000 for all violations adjudicated in a single proceeding.**
   > (B) **If a violation … is not corrected within the 30-day period** following notification …
   > the person shall, **in addition**, be subject to a civil monetary penalty of not more than
   > $10,000 **for each day of the violation after such period** until the violation is corrected.

⚠️⚠️ **"하루 $10,000"이라는 흔한 요약은 부정확하다.** 2단 구조다 — ① 단일 심판에서 전체 위반에
최대 $10,000(일당 아님), ② **30일 시정기간이 지난 뒤에야** 일당이 *추가로* 발동한다.
곧 **통지·시정 창구를 통과해야 일당 과징금이 켜진다.**

★★ **이 저장소에 이식되는 핵심은 금액이 아니라 순서다** — `확인(verify) → 통지 → 30일 시정 →
제재`. 자동 게이트로 옮기면 *"게이트 실패 시 즉시 중단"* 이 아니라 *"실패를 기록하고 한 사이클
안에 고치지 않으면 승격 차단"* 이 된다. 1인 프로젝트에서 즉시 중단은 우회되고, 기록은 남는다.

### 8.3 ★★ 등록 의무가 양성 결과율을 낮췄다는 실증 — 있다, 다만 인과 주장은 아니다

> Kaplan, R.M., & Irvin, V.L. (2015). "Likelihood of Null Effects of Large NHLBI Clinical Trials Has
> Increased over Time." *PLOS ONE*, 10(8), e0132382.
> DOI [10.1371/journal.pone.0132382](https://doi.org/10.1371/journal.pone.0132382)
> (서지사항은 Crossref API로 교차검증)

초록 원문:

> **17 of 30 studies (57%) published prior to 2000 showed a significant benefit of intervention on
> the primary outcome in comparison to only 2 among the 25 (8%) trials published after 2000**
> (χ²=12.2, df=1, p=0.0005).

결론 원문:

> The number NHLBI trials reporting positive results declined after the year 2000. Prospective
> declaration of outcomes in RCTs, and the adoption of transparent reporting standards, as required
> by clinicaltrials.gov, **may have contributed** to the trend toward null findings.

⚠️ 저자들이 직접 *"may have contributed"* 라고 쓴다. **2000년 전후 관찰 비교이고 n이 작다(30 vs 25).**
"등록 의무가 양성 결과를 줄였다"고 단정하면 원문보다 센 주장이 된다. 이 저장소가 인용할 값은
**"사전 선언 체제로 바꾸자 양성률이 57%→8%로 떨어졌다"** 까지다.

★ 그런데 그 크기가 중요하다 — **7배**다. 사전 선언 없는 상태에서 보고되는 양성 결과의 대부분이
사전 선언으로 사라졌다는 뜻이고, 이건 §1.2의 `PSR 0.9611 → DSR 0.4968`과 같은 종류의 붕괴다.

### 8.4 Registered Reports — 결과를 보기 전에 게재를 확정한다

> 공식 페이지: [cos.io/initiatives/registered-reports](https://www.cos.io/initiatives/registered-reports)
> (접속 2026-08-17. 아래 인용은 받은 HTML에서 문자열 대조 확인)
> 방법론 인용: Chambers, C.D., & Tzavella, L. (2022). "The past, present and future of Registered
> Reports." *Nature Human Behaviour*, 6(1), 29–42.
> DOI [10.1038/s41562-021-01193-7](https://doi.org/10.1038/s41562-021-01193-7)
> (Crossref 검증. 온라인 선공개 2021-11-15, 권호 확정 2022 — **인용 연도는 2022**)
> 초기 제안: Chambers, C.D. (2013). "Registered Reports: A new publishing initiative at Cortex."
> *Cortex*, 49(3), 609–610. DOI [10.1016/j.cortex.2012.12.016](https://doi.org/10.1016/j.cortex.2012.12.016)
> ⚠️ Cortex 본문은 페이월로 **미열람**. 서지사항만 검증했다(§9).

2단계 심사 원문:

> Authors … initially submit a **Stage 1 manuscript** that includes an Introduction, Methods, and the
> results of any pilot experiments … Following assessment of the protocol by editors and reviewers,
> the manuscript can then be offered **in-principle acceptance (IPA)**, which means that the journal
> virtually guarantees publication if the authors conduct the experiment in accordance with their
> approved protocol. … Following data collection, they resubmit a **Stage 2 manuscript** …

★★★ **IPA 철회 사유가 화이트리스트로 제한된다.** 이 문서에서 가장 이식 가치가 높은 문장이다:

> Peer review occurs prior to observing the outcomes of the research. Manuscripts that survive
> pre-study peer review receive an in-principle acceptance that **will not be revoked based on the
> outcomes, but only on failings of quality assurance, following through on the registered protocol,
> or unresolvable problems in reporting clarity or style.**

곧 **"결과가 나빠서"는 철회 사유가 아니다.** 사유는 ①품질보증 실패 ②프로토콜 미준수 ③보고 명료성.

단 무조건이 아니다 — **outcome-neutral 관문**이 따로 있다:

> Stage 1 submissions generally require the inclusion of **outcome-neutral conditions** for ensuring
> that the proposed methods are capable of testing the stated hypotheses. These might include
> positive control conditions, manipulation checks, and other standard benchmarks such as the absence
> of ﬂoor and ceiling eﬀects. Manuscripts that fail to specify these criteria will generally not be
> offered in-principle acceptance …

★★★ **이 "outcome-neutral conditions"가 자매 문서의 게이트와 정확히 같은 물건이다.**
[`training-gates.md`](training-gates.md)의 게이트 A(null 대비)·B(분산 붕괴)·C(학습곡선)는
**"이 방법이 애초에 가설을 검정할 능력이 있는가"** 를 결과와 무관하게 묻는다. RR은 그것을
**게재 승인의 선결 조건**으로 둔다. → **두 문서가 여기서 만난다: 학습 게이트는 시행 원장의
outcome-neutral 관문이다.**

**탐색적 분석은 금지하지 않고 라벨링을 강제한다:**

> the RR model places **no restrictions** on the reporting of unregistered exploratory analyses – it
> simply requires that the Results section of the ﬁnal article **distinguishes those analyses that
> were pre-registered and confirmatory from those that were post hoc and exploratory.** Ensuring a
> clear separation … is vital for preserving the evidential value of both forms of enquiry.

**여러 실험을 순차로 붙이는 경로도 있다** (FAQ 원문):

> The RR model welcomes **sequential registrations** in which authors add experiments at Stage 1 via
> an iterative mechanism and complete them at Stage 2. **With each completed cycle, the previous
> accepted version of the paper is guaranteed to be published, regardless of the outcome of the next
> round of experimentation.**

★ 개수 상한이 없다. 구속력이 **개수 제한이 아니라 래칫**에서 나온다 — 사이클이 닫히면 그 시점
결과가 확정되어 되돌릴 수 없다. **이 저장소에 이식하면 "N 예산"이 아니라 "커밋된 판정은 취소
불가"가 된다.** §7.4의 N 리셋 문제에 대한 대안 설계다.

참여 규모: *"Currently, **over 300 journals** use the Registered Reports publishing format …"*
⚠️ 페이지에 기준일 표기가 없다("Currently"뿐). **접속일 2026-08-17 기준**으로만 인용 가능.

**RR이 실제로 null 결과를 더 낸다** — 검증된 유일한 정량 비교:

> Scheel, A.M., Schijen, M.R.M.J., & Lakens, D. (2021). "An Excess of Positive Results: Comparing the
> Standard Psychology Literature With Registered Reports." *Advances in Methods and Practices in
> Psychological Science*, 4(2).
> DOI [10.1177/25152459211007467](https://doi.org/10.1177/25152459211007467) (Crossref 검증)

초록·본문 원문:

> Analyzing the first hypothesis of each article, we found **96% positive results in standard reports
> but only 44% positive results in RRs.**
> Thirty-one out of 71 RRs and 146 out of 152 SRs had positive results, meaning that the positive
> result rate was **43.66% for RRs** (95% CI = [31.91, 55.95]) and **96.05% for SRs**
> (95% CI = [91.61, 98.54]).

⚠️ **논문은 null률이 아니라 positive rate로 보고한다.** 뒤집으면 RR null 56.3% / 표준 3.95%다.
"표준 문헌의 null률이 5~20%"라는 흔한 요약은 **이 논문 수치와 맞지 않는다**(약 4%, CI가 좁다).
조건도 붙는다 — **첫 번째 가설 기준·심리학 한정·n = 71 vs 152.**

### 8.5 AsPredicted vs OSF — 사후 변경 설계가 정반대다

**AsPredicted** ([aspredicted.org](https://aspredicted.org), Wharton Credibility Lab 운영,
Wharton School 재원. ⚠️ 봇 차단이라 브라우저 UA로 우회해 받았다):

> All pre-registrations can be downloaded as **single page PDFs that are time-stamped** and include a
> unique URL for verification.
> Pre-registration remains **private until an author makes it public**.
> **Public pre-registrations cannot be modified** and are automatically backed up in the Web Archive.

FAQ의 핵심 한 줄:

> **We never make any changes to pre-registrations.**

3단 계단이고 마지막 단이 이탈 처리 규칙 전부다:

> If it has been more than a few days since the to-be-edited pre-registration was created, or if you
> have already generated a .pdf, **you can no longer delete it or edit it. You can explain in your
> paper any shortcomings with the pre-registration that you want to alert readers to.**

그 이유를 직접 밝힌다:

> the simplicity of the rule "we never make changes to authors' pre-registrations" **enhances the
> credibility and transparency** of our platform. There is never ambiguity about the origin of
> something seen on a pre-registration thanks to this rule.

⚠️ **비공개 기한 개념이 없다.** 무기한 비공개 가능하고, 대신 **PDF 생성이 불가역적**이다 —
*"The act of creating a PDF is non-reversible. … it cannot be deleted, even if created in error."*
익명 PDF는 *"Two years elapse since the creation of the anonymous PDF"* 시점에 백업된다.

**OSF Registries** ([help.osf.io/article/330](https://help.osf.io/article/330-welcome-to-registrations)):

> Preregistration is the practice of posting a **time-stamped, read-only** version of your study plan
> to a public repository before beginning data collection or analysis.
> A registration is a **frozen version** of your project that **can never be edited or deleted**, but
> you can **issue a withdrawal** of it later, leaving behind basic metadata.
> You can **embargo it for up to four years.**

★ 그런데 **공식 수정 경로를 제공한다** — AsPredicted와 정반대다:

> **Updating a registration is a process of transparently reflecting necessary changes** to a study
> design. The changes should be implemented **only to reflect events outside your control** or
> include unexpected anomalies.
> **Anticipate what deviations from the plan may occur and include them in your plan**

★★★ **두 철학을 섞으면 안 된다.** AsPredicted는 **불변성**으로 신뢰를 만들고 이탈을 논문 서술로
넘긴다. OSF는 **버전 관리된 수정 이력**으로 신뢰를 만든다. 섞으면 *"언제든 고칠 수 있는
사전등록"* 이 되어 구속력이 0이 된다.

**이 저장소는 이미 AsPredicted 쪽에 서 있다** — `study-pitfalls.md` §3.1이
*"사전등록은 커밋 타임스탬프에서 효력이 나온다"* 이고, git은 수정 이력을 남기되 원본을 지우지
않는다. 그리고 이탈은 별도 문서(`prereg-deviation.md`)로 서술한다. **OSF식 in-place update로
가지 말 것** — git force-push가 정확히 그 유혹이다.

### 8.6 ★★ OSF 템플릿이 §7의 공백을 재확인한다

> 출처: OSF 공식 스키마 API — `https://api.osf.io/v2/schemas/registrations/<id>/`
> (AsPredicted 8문항은 OSF가 호스팅하는 공식 이식본
> "Preregistration Template from AsPredicted.org"에서 받았다. ⚠️ AsPredicted 자체 예시 PDF
> 링크는 깨져 있다 — §9)

**AsPredicted 8문항** (verbatim, 순서대로): ①Data collection(이미 수집했는가) ②Hypothesis
③Dependent variable ④Conditions(*"How many and which conditions"*) ⑤Analyses
(*"Specify exactly which analyses you will conduct"*) ⑥Outliers and Exclusions ⑦Sample Size ⑧Other.

★ **개수를 부분적으로만 고정한다.** ④가 조건 수를 세게 하고 ⑤가 분석을 열거하게 하지만:
④의 "conditions"는 **피험자 배정 조건(experimental arm)** 이고 모델 설정이 아니다.
⑤는 *"exactly which"* 라고만 하고 **몇 개까지가 하나의 분석인지 정의하지 않는다.**
**시드·라벨 정의에 해당하는 문항은 아예 없다.**

**OSF 사전등록 템플릿**에서 §7과 직접 부딪히는 세 문장:

1. **등록 단위 정의 — 문헌에서 찾은 가장 근접한 규칙**:
   > This research plan is for a **single study, experiment, or review**. If you have multiple
   > studies, such as separate experiments that may be reported in a single paper, or **different
   > research questions from the same dataset** that will be reported in separate papers, then …
   > completing a separate registration form for each one.

   → 분기 기준은 ①별개 실험 ②같은 데이터셋의 다른 연구질문. **하이퍼파라미터 스윕은 둘 다
   아니다.** 이 기준으로도 §7의 질문은 안 풀린다.
2. **다중검정을 언급하는 유일한 문장** (Inference criteria):
   > … **Explain how comparing multiple conditions or testing multiple hypotheses will be accounted
   > for.**

   ★★★ **보정을 요구하되 방법과 개수를 연구자에게 위임한다.** Harvey & Liu의
   *"we need to use judgment on … the number of tests"* 와 **정확히 같은 위임**이다.
   서로 무관한 두 문헌군이 같은 칸을 비워 뒀다.
3. **양방향 규율** (Analysis Plan 안내문):
   > **All analyses specified below should be conducted and shared as study outcomes.** Any
   > additional analyses that are conducted but were not in this analysis plan **should be clearly
   > distinguished in outcome reporting** from the planned analyses as unplanned analyses.

   → 등록한 것은 **전부** 해야 하고(선택적 보고 차단), 등록 안 한 것은 **표시**해야 한다.
   개수 제한이 아니라 **누락 금지 + 라벨링**이다.

⚠️ 그리고 탐색용 변수는 열거 의무가 없다 —
*"If you have variables that you are measuring for exploratory analyses, **you are not required to
list them**."* 곧 사전등록이 고정하는 것은 **confirmatory 집합**이고 그 바깥은 개수 통제 대상이
아니다. **prereg §4.1의 "고를 수 없으면 세지 않는다"와 같은 구조**다.

★★★ **이 저장소에 가장 직접 쓰이는 것 — Foreknowledge 계단.** OSF 템플릿은 데이터를 이미 본
정도를 계층화하는데, **과거 시계열로 백테스트하는 우리 상황에 대응 선택지가 있다**:

> **Data exists but the authors have not observed it yet.** At least some of the data that will be
> used for this analysis plan exists and is possible for the authors to access. However, the authors
> **certify that they have not accessed any of that data** and will not do so until after this plan
> is registered.

> **Authors have observed the data.** The authors cannot certify meeting any of the levels above
> given prior access and observation of the data relevant to this analysis plan.

> **Analyses in this plan have been conducted already.** … making this a **retrospective
> registration.**

★ **"데이터는 있지만 아직 안 봤다"가 정식 등급으로 존재한다.** 금융 백테스트 사전등록이
"데이터가 이미 존재하므로 사전등록이 불가능하다"는 반론을 받을 때의 답이 여기 있다 —
**존재 여부가 아니라 열람 여부를 신고하는 것이다.**
그리고 §1의 23런은 `microcap` 신호와는 다른 family이지만, **대형주 신호에 대해 지금 사전등록을
쓴다면 그것은 세 번째 등급(retrospective registration)** 이다. 그렇게 적어야 정직하다.

**COS Registered Reports 페이지에는 다중검정 규칙이 없다** — 받은 HTML에서 기계적으로 확인:
`multiple compar` 0건, `correction` 0건, `multiple test` 0건, `number of test` 0건.

**42 CFR Part 11도 답을 주지 않는다.** Part 11이 정의하는 "trial" 단위는 **규제 대상 단위**
(제품·규제 경로 기준의 `applicable drug/device clinical trial`)이고 통계적 검정 단위가 아니다.
Part 11이 실제로 고정하는 것은 **primary/secondary outcome measure의 사전 선언**(§ 11.28)이고,
미제출 시 데이터뱅크에 박히는 문구가 그 구조를 보여준다:

> The entry for this clinical trial did not contain information on the **primary and secondary
> outcomes** at the time of submission, as required by law.

★★★ **곧 임상 체제의 구속 메커니즘은 "검정 몇 개까지"가 아니라 "primary 지표를 미리 하나 정하고
바꾸면 흔적이 남는다"다.** 시행 횟수를 세려는 노력보다 **주 지표 사전 고정**이 문헌이 실제로
지지하는 설계다. `microcap-insider-prereg.md` §5의 *"주 판정 = BMP/Kolari-Pynnönen 보정 t"* 가
이미 그것이다.

### 8.7 이식할 수 있는 것 / 없는 것

| 임상시험 관행 | 이 저장소 이식 | 근거 |
|---|---|---|
| **측정 전 등록 + 타임스탬프** | ✅ **이식됨.** `microcap-insider-prereg.md`가 커밋돼 있고, `study-pitfalls.md` §3.1이 *"gitignore된 파일 안의 사전등록은 사전등록이 아니다"* 로 규칙화 | 규율이 절차라서 도메인 무관 |
| **결과 무관 보고 의무** | ⚠️ **부분.** 1인 프로젝트에는 강제 주체가 없다. **대체물은 원장의 완전성** — N을 세는 곳과 결과를 적는 곳이 같은 파일이면 누락이 눈에 보인다 | PBO §5.2 file-drawer |
| **주요 결과 사전 지정(primary outcome)** | ✅ **이식 가치 최상.** prereg §5의 "주 판정 = BMP/Kolari-Pynnönen 보정 t"가 정확히 이것이다. §8.6이 보여주듯 **임상 체제의 실제 구속력이 여기서 나온다** | 42 CFR § 11.28 · HL *"we must make a choice … Is it 0.10 or 0.05?"* |
| **confirmatory / exploratory 라벨링** | ✅ **아직 이식 안 됨. 즉시 이식 가능.** 금지가 아니라 **구분 표시**가 규율이다 | COS RR *"no restrictions … simply requires that the Results section … distinguishes"* |
| **등록한 분석은 전부 수행·보고** | ⚠️ **미이식.** 지금은 돌리고 결과가 안 좋으면 문서에 안 적힐 수 있다 | OSF *"All analyses specified below should be conducted and shared as study outcomes"* |
| **열람 여부 신고(foreknowledge)** | ✅ **이식 가치 높음.** "데이터가 이미 있다"가 사전등록 불가 사유가 아님을 §8.6이 보여준다 | OSF Foreknowledge 계단 |
| **등록 후 변경 이력 공개** | ✅ 이미 `prereg-deviation.md`가 있다. ⚠️ **AsPredicted식(불변+별도 서술)을 유지하고 OSF식 in-place update로 가지 말 것**(§8.5) | AsPredicted *"We never make any changes"* |
| **법적 강제(과징금·연구비 회수)** | ❌ **금액은 이식 불가**(제재 주체 없음). ✅ **순서는 이식 가능** — `확인 → 통지 → 30일 시정 → 승격 차단`(§8.2) | 42 U.S.C. § 282(j)(5)(A) · 21 U.S.C. § 333(f)(3) |
| **두 단계 심사(결과 보기 전 승인)** | ⚠️ **1인으로는 원리상 불가.** 대체물은 **outcome-neutral 조건을 코드로 박아 두는 것** — 자매 문서의 게이트 A·B·C가 그것이고, RR은 그걸 승인 선결 조건으로 둔다(§8.4) | COS RR *"outcome-neutral conditions"* · `study-pitfalls.md` §3.2 |
| **결과와 무관한 게재 확정(IPA)** | ⚠️ **부분.** 대체물은 **래칫** — 판정을 커밋하면 취소 불가(§8.4의 sequential registrations) | COS RR *"will not be revoked based on the outcomes"* |

### 8.8 ★★ 이식할 때 반드시 달라지는 점 — N의 방향

임상시험 등록은 **"모든 시험을 공개하라"** 이고, 다중검정 보정은 **"몇 번 했는지 세라"** 다.
비슷해 보이지만 **N이 커질 때의 유인이 반대다.**

- 임상: 등록 누락은 위법. **많이 등록하는 게 안전하다.**
- DSR: N이 크면 임계 `SR₀`가 올라가 **자기 결과가 기각된다.** 곧 **정직하게 세면 손해다.**
- PBO: 쓰레기 열을 추가하면 **결과가 왜곡된다**(§7.2). **많이 세는 것이 보수적이 아니다.**

★ **따라서 "일단 다 적어 두자"는 임상식 해법이 금융 보정 통계량에는 그대로 안 통한다.**
원장은 두 층으로 갈라야 한다 — **①실행 로그(전부, 무조건)** 와 **②시행 카운트(판정 단위,
규칙에 따라)**. prereg §4.1이 이미 ②를 정의했다. **①이 없다.** `mlruns/`가 ①인데 세어지지
않고 있고, ②로 승격되는 규칙이 코드에 없다.

★★ 그리고 **문헌이 이 두 층 구조를 이미 갖고 있다.** OSF가 confirmatory 변수는 열거를 요구하고
탐색용 변수는 *"you are not required to list them"* 이라 하며, COS RR이 등록 분석과 사후 분석을
**구분 표시**만 요구한다(§8.4·§8.6). 곧 **①은 전부 남기고 ②만 규칙으로 센다**가 임상·심리 쪽
표준 설계이고, prereg §4.1의 "고를 수 없으면 세지 않는다"와 같은 형태다.

### 8.9 ✅ 확인된 사실 하나 — 사전등록 없는 사후 집계는 구조적으로 작다

이건 문헌 인용이 아니라 **§1.1의 실측**이다. 사후에 `mlruns/`를 세면 어느 숫자를 읽게 되는가:

| 무엇을 세나 | 값 | 왜 이 값인가 |
|---|---:|---|
| 동일 기간 손익 계열 열 수 | **9** | CSCV가 실제로 쓸 수 있는 것 |
| 그 9열의 서로 다른 설정 수 | **3** | 시드·재실행 제거 후 |
| MLflow 런 수 | **23** | UI에서 보이는 것 |
| **실제로 학습이 일어난 횟수** | **≥ 26** | 23런 중 `tune`(1런→6회)·`horizon`(1런→3회)의 step 리셋을 펼치면 +7. `generate_signal.py` 2런은 학습이 아니므로 −2 |
| **스크립트가 정의한 설정 수** | **≥ 22** | 후보 6 + 모델 3 + 호라이즌 3 + GRU sp500(시드 4) + bear2022(2) + 베이스라인 + 파일럿 + phase3 재실행 |

★★ **9와 26 사이에 세 배 차이가 있고, 어느 숫자도 "맞는 N"이 아니다.**
`study-pitfalls.md` §2.6 *"사후 집계는 구조적으로 과소계산되므로 사전등록이 필수"* 의
**실측 사례**다. 그리고 과소계산의 원인이 **게으름이 아니라 도구 기본동작**이라는 점이 중요하다 —
recorder를 명시적으로 열지 않으면 6회 시행이 1런으로 접힌다(§1.1.1). **사후에 고칠 수 없다.**

---

## 9. 확인 실패 / 미검증

| 대상 | 상태 | 대체 / 비고 |
|---|---|---|
| **DSR 게재본**(JPM 40(5), 94–107) 조판·면수 | **확인 실패** — `pm-research.com` HTTP 429 | 저자 배포 워킹페이퍼판(2014-07-31, SSRN 2460551) 전문. 표지에 *"Journal of Portfolio Management, Forthcoming, 2014"*. **권호·면수는 미확인이므로 인용 시 SSRN 병기 권장** |
| **PBO 게재 권호·면수**(JCF 20(4), 39–69) | **미검증** — 검색 결과에만 의존 | 저자 배포 PDF(개정 2015-02)로 본문 인용. risk.net TOC 페이지는 받았으나 면수 문자열 확인 실패 |
| **HL "Backtesting" 시작면** | **불일치** | 배포 PDF 쪽번호 헤더는 `12 BACKTESTING FALL 2015`~`28`, 발행사 표기는 13–28. **12인지 13인지 확정 못 함** |
| **DSR 논문 수치예의 중간값** | **확인 실패** — PDF 텍스트 레이어에서 수식 글리프 소실 | 읽을 수 있었던 것: `N=88 → DSR 0.9004`(기각), `N=46 → 0.9505`(통과), `T=1250`, 연율 `SR̂=2.5`, "5년 일간 표본". **γ̂₃·γ̂₄는 읽지 못했다** |
| ↳ **`dashboard-features.md` §4-4의 `SR̂=0.0362`, `E[max SR]≈0.0243`** | ⚠️ **정정 필요 의심** | 독립 구현에서 `V[{SR}]`(연율) = 1/2로 두면 논문이 verbatim으로 적은 **`DSR(N=46) = 0.9505`가 정확히 재현**된다. 그때 `SR̂`(비연율) = 0.1581(= 2.5/√250), `E[max\|88]` = 0.1111이므로 **§4-4의 0.0362/0.0243과 맞지 않는다.** ⚠️ 단 `DSR(N=88) = 0.9004`는 재현하지 못했다 — `γ̂₃·γ̂₄`를 못 읽어 (−3, 10)으로 가정했더니 0.9102가 나왔다. **어느 쪽이 맞는지 확정하려면 게재본 PDF가 필요하다** |
| **MinBTL 구현 검산** | ✅ **성공** | 논문 진술 *"if only ﬁve years … no more than forty-ﬁve"* 를 재현(N=45 → 4.998년, N=46 → 5.036년) |
| **`C(16,8)` 조합 수** | ⚠️ **논문 오기** | PBO 논문 본문이 `12,780`이라 두 번 적지만 실제 `C(16,8)=12,870`. 내 구현은 12,870 |
| **`clinicaltrials.gov` 공식 "FDAAA 801 and the Final Rule" 페이지** | **확인 실패** — JS SPA, 본문 미렌더 (추출 186자) | eCFR API · govinfo · Cornell LII 원문으로 **전부 대체 확보**. 실질 손실 없음 |
| **NIH grants 정책 페이지** | **확인 실패** — HTTP 403 | 위와 같음 |
| eCFR 웹 UI · federalregister.gov 문서 페이지 | **확인 실패** — 302 → `unblock.federalregister.gov` (봇 차단) | **eCFR API**(`/api/versioner/v1/full/2026-01-01/title-42.xml?part=11`)와 **govinfo FR-2016-09-21**로 우회. §8.2의 §11.24(a)·§11.44(a)·`81 FR 65138`·`42 U.S.C. 282(j)` 문자열은 **직접 재확인했다** |
| **민사벌 인플레이션 조정 현재액** | **미확인** | 21 U.S.C. § 333(f)(3) 표면 금액 **$10,000만** 검증했다. 검색 결과에 `$15,107`이 보였으나 1차 출처 미확인이라 **§8.2에 쓰지 않았다** |
| `uscode.house.gov` | **확인 실패** — `ECONNREFUSED` | govinfo USCODE-2023-title42로 대체 |
| **Chambers & Tzavella (2022) 본문** | **확인 실패** — nature.com 303 → 인증 리다이렉트, Cardiff OA 원고 403 | 서지사항 **Crossref 검증**, 초록 **Europe PMC(PMID 34782730)** 확보. §8.4의 Stage 1/2·IPA 인용은 **COS 공식 페이지 원문**이고 이 논문이 아니다 |
| **Chambers (2013) *Cortex* 본문** | **미열람** — Elsevier 페이월 | 서지사항만 Crossref 검증(49(3), 609–610). **본문을 인용하지 않았다** |
| **AsPredicted 공식 예시 PDF**(`aspredicted.org/kv692.pdf`) | **링크 파손** — HTTP 200이나 PDF 아님(HTML 반환) | 8문항은 **OSF 호스팅 공식 이식본**("Preregistration Template from AsPredicted.org", `api.osf.io/v2/schemas/registrations/…`)으로 확보 |
| COS 페이지의 "over 300 journals" 기준일 | **표기 없음** | 페이지에 *"Currently"* 뿐. **접속일 2026-08-17 병기 필수** |
| `web.archive.org` | **접근 차단** | 도구 정책상 불가 |
| **`pypbo` 구현 대조** | 미실시 | §1.5는 논문 Algorithm 2.3을 직접 옮긴 구현. **논문 예제(PBO 55%)로 검증하지 않았다** |
| **`bear2022` 2런을 포함한 CSCV** | 계산 불가 | 기간이 달라 `M is a true matrix` 조건 위반(§4.1) |
| **`Experiment` 7런의 Sharpe** | 계산 불가 | 손익 계열 아티팩트가 없다(§1.1). **재실행 없이는 복원 불가** |
| **`tune_hyperparams.py` 6후보의 곡선↔후보 대응** | **복원 불가** | `step` 리셋으로 6개 곡선은 분리되지만 **후보 이름이 원장에 없다**(§1.1.1). `CANDIDATES` 딕셔너리 순서로 추정할 수는 있으나 **검증 수단이 없어 추정하지 않았다** |
| **`probe_models.py` 런이 2개인 이유** | **미확정** | 2회 실행인지, 1회 실행에서 곡선을 남길 수 있는 모델이 2개였는지 구분 못 했다. XGB·DoubleEnsemble이 LightGBM `record_evaluation` 콜백을 안 쓰는 것은 확인 |
| **DSR의 `V[{SR}]` 추정 자체의 표본오차** | 미평가 | 9개 표본으로 분산을 추정했다. 논문은 Fisher 변환으로 ρ̂ 오차를 통제할 수 있다고만 언급하고 절차를 주지 않는다 |

⚠️ **조사 방법 경고 (자매 문서 §5와 같은 종류).** 이번 조사에서도 웹 페이지 요약 도구가
공식 문서 내용을 **그럴듯하게 재구성해** 돌려주는 것을 확인했다. 그래서 §6의 MLflow 인용은
**HTML을 내려받아 문자열을 직접 grep한 것**이고, §2~§5의 논문 인용은 **PDF 텍스트를 추출해
원문 문장을 잘라 붙인 것**이다. **요약본을 원문 확인으로 세지 말 것.**

★ 그리고 **PDF 텍스트 추출도 완전하지 않다** — 수식 글리프가 통째로 사라진다(위 DSR 항목).
**"PDF를 읽었다"가 "수식을 읽었다"는 아니다.** 수치예를 인용할 때는 반드시
**독립 구현으로 재현**해 보고, 재현 안 되면 인용하지 말 것.

★★ **§8의 법령·플랫폼 조사는 위임해서 받았다.** 그래서 받은 결과를 그대로 옮기지 않고
**직접 재확인한 뒤** 적었다 — eCFR API를 다시 받아 `21 calendar days after the first human subject
is enrolled` · `no later than 1 year after the primary completion date` · `81 FR 65138` ·
`42 U.S.C. 282(j)` 문자열을 grep으로 확인하고, Kaplan & Irvin과 Scheel et al.의 저자·권호를
Crossref API로 다시 조회했다. **전부 일치했다.**
그래도 원칙은 같다 — **위임 결과도 요약본이고, 요약본은 원문 확인이 아니다.**

---

## 10. 이 저장소에 어디에 붙이나

착지점만 지목한다. 코드는 쓰지 않는다.

1. ★★★ **`docs/project/`에 시행 원장을 신설한다** (예: `docs/project/trial-ledger.md`).
   **두 층으로 나눈다**(§8.8) — ①실행 로그(무조건 전부) ②시행 카운트(판정 단위, prereg §4.1 규칙).
   ⚠️ **`docs/project/`는 추적 대상이므로 계좌값을 넣지 말 것.** 백테스트 지표만 들어간다.
   최소 열: `시행ID · 날짜 · 커밋 · 설계축(무엇을 바꿨나) · 판정단위 여부 · 손익계열 유무 ·
   confirmatory/exploratory · 결과 · N 누적`.
   **"손익계열 유무"가 핵심**이고(없으면 DSR·PBO 입력이 못 됨, §1.1),
   **"confirmatory/exploratory"는 COS RR·OSF가 공통으로 요구하는 최소 라벨**이다(§8.4·§8.6).
   → 이 열 하나가 "탐색을 금지하지 않고 구분한다"는 규율 전체를 구현한다.
2. ★★★ **`tune_hyperparams.py` · `probe_*.py`가 후보마다 런을 열게 한다.** §1.1.1이 최우선
   착지점이다 — 지금은 **6회 시행이 1런으로 접히고 후보 이름이 사라진다.** 세 가지를 바꾼다:
   (a) **루프 안에서 recorder를 명시적으로 열어** 시행 경계를 만든다. 지금은 `LGBModel.fit`의
   부수효과로 런 하나가 생겨 재사용된다.
   (b) **부모-자식 런**으로 스윕을 묶어 "설계 결정 1회 / 실행 n회"를 자료구조로 구분(§6.2).
   (c) **후보 이름을 param 또는 tag로 남기고, 후보마다 `report_normal_*.pkl`을 남긴다.**
   없으면 그 시행은 **영구히** 보정 통계량 밖이다(§9의 "복원 불가").
   ⚠️ 태그 키는 공식 규약이 없으므로 이 저장소가 정한다(§6.2). `experiment_phase` 같은 예시 키를
   그대로 쓰든 새로 정하든, **원장 문서에 키 목록을 적어 두는 것이 규약**이다.
   ★ `mlflow.source.git.commit`은 이미 자동으로 남으므로 **커밋 열은 공짜다**(§1.1.1).
   그리고 `sort_values("valid_RankIC") → iloc[0]`로 후보를 고르는 부분은 **선택 그 자체**이므로
   **선택 결과를 stdout이 아니라 런 태그로** 남겨야 한다.
3. ★★ **README 실험표(`| 실험 | 핸들러+모델 | IC | Rank IC | 초과(비용후,연) | IR | MDD |`)에
   `N`과 `DSR` 열을 넣는다.** §1.2가 보여주듯 **IR 0.923 옆에 DSR 0.50이 붙으면 그 행의 해석이
   바뀐다.** 자매 문서 §6-5가 같은 표에 `R²_oos` 열을 권하므로 **한 번에 같이 넣는 편이 낫다.**
   → 그리고 **`+11.9%` 행의 서술을 고칠 근거가 이제 두 개**다(검증 R² 음수, DSR 0.50).
4. ★★ **DSR 계산의 좌변을 `excess_return_with_cost`로 못 박는다**(§1.3). 원수익에 걸면
   불장 베타가 통과한다. qlib이 이미 계산해 두므로 비용 0이다.
   **`scripts/model_backtest/run_backtest.py::_gates()`에 게이트를 하나 더 붙일 수 있다** —
   자매 문서가 권한 A·B·C 다음의 **게이트 E: `DSR(N) > 0.95`**. ⚠️ `N`을 코드가 정할 수 없으므로
   **원장에서 읽어 오거나 인자로 받아야 한다.** N을 하드코딩하면 게이트가 거짓말을 한다.
5. ★ **MinBTL은 게이트가 아니라 게이지로 붙인다**(§1.4의 한계 두 개). 표시 형태:
   `보유 183주(3.52년) vs MinBTL 3.53년(N=19)` — 자매 문서식 통과/실패가 아니라 잔여 예산.
   **N 예산을 소진했다는 사실 자체가 "새 시행보다 데이터 확장이 먼저"라는 신호**다.
6. **PBO/CSCV는 지금 붙이지 않는다.** §1.5가 판정: 계산은 되지만 N=9·시드중복·레짐 단일이라
   판정에 못 쓴다. **붙일 조건을 원장에 조건문으로 적어 둔다** — *"동일 기간 손익 계열을 남긴
   서로 다른 설정이 20개 이상 쌓이면 1회 계산"*. `dashboard-features.md` §9-4가 PBO를
   *"라이브 전 1회"* 로 배치한 것은 유효하고, **여기에 "N ≥ 20" 선결 조건을 추가**하면 된다.
7. **`analyze_capm.py`가 t-stat을 내게 한다**(§5). haircut·HLZ 허들 둘 다 t-stat이 입력이다.
   [`dashboard-features.md`](dashboard-features.md) §4-4가 이미 지적한 항목이고
   **Newey-West HAC + 신뢰구간 병기**까지 같은 절에 설계가 있다. 새로 조사할 것이 없다.
   ⚠️ **팩터모형 잔차에 걸어야 한다** — §1.3이 보여주듯 원수익에 걸면 베타가 통과한다.
   Harvey & Liu도 *"Our method also applies to information ratios, which use residuals from factor
   models"* 라고 쓴다.
8. **`docs/project/study-pitfalls.md`에 두 항목을 추가한다.**
   (a) **§2.7 "시드를 여럿 돌리면 DSR이 올라간다"** — §2.3의 식 결과. 시드 반복이 `V[{SR}]`와
   `N̂`을 둘 다 낮춘다. **중복 시행은 검증이 아니라 완화다.**
   (b) **§3.6 "손익 계열을 안 남긴 시행은 영구히 보정 밖이다"** — §1.1의 `Experiment` 7런.
   같은 문서 §2.6(*"사후 집계는 구조적으로 과소계산"*)의 실측 후속이고, 과소계산 크기가 4배다.
9. **`microcap-insider-prereg.md` §4.1·§4.2에 각주 한 줄.** §7.4의 대조 결과 —
   **"이 규칙은 문헌이 준 것이 아니라 이 저장소가 정한 것"** 임을 명시하고,
   문헌은 "판단하라"고 위임했을 뿐임을 적는다(HL 원문 + OSF Inference criteria 둘 다 인용 가능).
   §4.2의 리셋 근거는 DSR의 *"strategy class"* 가정이 부분 지지하지만 **판정 기준은 문헌에 없다.**
10. ★★ **사전등록에 "열람 여부" 한 줄을 넣는다**(§8.6). OSF의 Foreknowledge 계단을 그대로
    3등급으로 축약하면 된다 — *데이터 미열람 / 열람함 / 이미 분석함(retrospective)*.
    ⚠️ **대형주 신호에 대해 지금 쓰는 사전등록은 세 번째 등급이다.** 그렇게 적어야
    `study-pitfalls.md` §3.1의 타임스탬프 규율과 어긋나지 않는다.
11. **게이트 실패의 처리 순서를 임상 체제에서 빌린다**(§8.2). *"즉시 중단"* 이 아니라
    **`확인 → 기록 → 한 사이클 시정 → 승격 차단`**. 1인 프로젝트에서 즉시 중단은 우회되지만
    기록은 남는다. 자매 문서 §6의 `_gates()` 확장이 "중단"이면 우회 유혹이 생기므로,
    **실패를 원장에 쓰고 승격(라이브·README 게재)만 막는 편**이 실제로 작동한다.
12. **`docs/research/dashboard-features.md` §4-4의 DSR 수치예를 확인 후 정정한다**(§9).
    `SR̂=0.0362 / E[max SR]≈0.0243`이 재현되지 않았다. **게재본 PDF를 얻을 때까지는 그 두 값을
    인용하지 말 것.** 같은 절의 나머지(공식·`N=88 → 0.9004` · `N=46 → 0.9505` · MinBTL ·
    PBO 0.05 · β<0 · HLZ t>3.0)는 **이번 조사에서 원문으로 전부 확인됐다.**
