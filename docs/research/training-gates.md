# 리서치 — 학습 건전성 게이트 (모델 비의존)

- 조사일: 2026-08-17
- 목적: "모델이 null 대비 실제로 학습됐는가"를 승격 조건으로 거는 관행을 찾고, **모델 클래스와
  무관하게(GBDT·NN·선형·앙상블) 성립하는 게이트**만 추린다.
- 방법: 논문은 1차 출처(원문 PDF·학회 proceedings)만 인용한다. **도구 API는 이 저장소 `.venv`에
  설치된 실제 버전을 introspect해 확인했다** — 검색 요약이 아니라 설치본의 시그니처·docstring이다.
  확인 못 한 것은 §5에 따로 적었다.
- 저장소 실측은 전부 `mlruns/`(로컬)에서 뽑았다. 계좌 관련 값은 없다.
- 자매 문서: [`trial-accounting.md`](trial-accounting.md) — 시행 횟수 N·다중검정·음성 결과 기록.
  이쪽은 **"이 한 번의 학습이 성립했는가"**, 저쪽은 **"몇 번 시도했는가"** 를 다룬다.
- 후속 문서: [`optuna-adoption.md`](optuna-adoption.md) — 하이퍼파라미터 탐색 프레임워크 도입 판단.
  §1.2의 "정규화 전 구간에서 R²가 null 위로 안 올라간다"가 그쪽 도입 반대 근거 중 하나다.
  §2.3의 게이트 C를 `MedianPruner`로 대체하면 안 되는 이유도 그쪽에 있다(비교 대상이 **다른
  trial의 중앙값**이라, 균일하게 실패한 분포에서는 절반이 통과한다).
- 구현: 게이트 A·C는 [`_common.py`](../../scripts/model_backtest/_common.py) `check_learning`이고
  두 러너(`run_backtest`·`run_experiment`)가 공유한다. 판정 기록은
  [`trial-ledger.md`](../project/trial-ledger.md).

---

## 0. 요약

**확립된 것**

1. 이 저장소 `mlruns/`의 학습 런 **19개 중 12개는 검증손실 최선점이 step 0**이었다.
   나머지 7개도 전 학습 구간 통틀어 검증 MSE 개선폭이 **0.004%~0.074%** 다. (§1.1)
2. 라벨이 `CSRankNorm`을 거치므로 **상수 예측의 MSE는 데이터와 무관한 구조 상수 0.99763**이다
   (실측 0.9976316, 이론 3.46²/12 = 0.9976333). 즉 **null 기준선을 데이터 없이 미리 알 수 있고,
   게이트 구현 비용이 사실상 0이다.** (§1.2)
3. 그 기준으로 계산한 OOS R²는 전 런에서 |R²| < 0.001이고, **README `+11.9%` 행의 근거인
   GRU S&P500 4런은 R²가 전부 음수**(−0.00054 ~ −0.00071)다. 상수 예측보다 나쁘다. (§1.2)
4. README 베이스라인 행(Alpha158+LightGBM, S&P500)의 예측은 **499종목에 서로 다른 값이 35개뿐**이다.
   입력 행 순서만 섞으면 **거래일의 78.9%에서 top-20 포트폴리오가 바뀐다.** (§1.3)
5. **IC로는 이걸 못 잡는다.** 예측이 완전 상수면 Pearson IC는 NaN이 아니라 ~1e-18이 나오고,
   3개 값만 갖는 예측도 Spearman IC 0.033을 낸다. IC 0.0121은 "약한 신호"가 아니라
   **동점 처리 결과일 수 있다.** (§2.2)
6. **세 분야가 독립적으로 같은 최소 요건에 도달했다** — Google의 ML Test Score는 `Model 5:
   A simpler model is not better`를 채점 항목으로 두고(§3.1), 예측 교과서는
   *"If not, the new method is not worth considering"* 까지 못박고(§3.2), scikit-learn User Guide는
   같은 것을 *"a simple sanity check"* 라 부른다(§3.3). **셋 다 모델 클래스를 언급하지 않는다.**
7. **도구도 이미 있다.** `mlflow.validate_evaluation_results(validation_thresholds,
   candidate_result, baseline_result=None)`가 baseline 대비 최소 개선을 예외로 강제한다
   (설치본 3.14.0 docstring으로 확인). 단 **`mlflow.evaluate()`에 있다고 알려진 이름이 아니다** — §4.1.

**모델 비의존성 — 게이트마다 다르다 (이게 이 문서의 핵심)**

| 게이트 | 무엇을 잡나 | 비의존? |
|---|---|---|
| A. null 모델 대비 (§2.1) | "아무것도 학습 안 됨" | ✅ **완전** — 예측 벡터만 있으면 됨 |
| B. 예측 분산·동점 (§2.2) | 이산 출력 붕괴, 동점 기반 임의 선택 | ⚠️ **부분** — GBDT·트리는 잡고 NN·선형은 못 잡음 |
| C. 학습곡선 퇴화 (§2.3) | early-stop 1회차, 단조 악화 | ⚠️ **반복학습기 전용** — GBDT·NN만. 선형회귀엔 곡선이 없음 |
| D. 라벨 셔플 순열검정 (§2.4) | 파이프라인 누수·가짜 신호 | ✅ **완전** — 다만 학습을 n번 반복해야 함 |

**게이트 B가 실제로 비의존이 아님을 이 저장소 데이터가 보여준다** — 같은 진단을 LightGBM과
GRU 예측에 걸면 LightGBM은 걸리고(재현율 82.5%) GRU는 100% 통과한다(§1.3). 그런데 GRU 쪽이
R²는 더 나쁘다. **하나만 걸면 반드시 뚫린다.**

**통설이지만 근거가 약하거나 틀린 것**

1. "IC가 양수면 신호가 있는 것" — 아니다. 동점 다수 예측의 IC는 tie-break 순서의 함수다(§2.2).
2. "early stopping이 알아서 처리한다" — early stopping은 **1회차에서 멈추는 것도 정상 종료로
   보고한다.** 그게 이 저장소에서 9번 일어났다(§1.1).
3. "`mlflow.evaluate()`에 baseline 비교가 있다" — **MLflow 3.x에는 없다.** 2.18.0에서 별도 함수로
   분리됐고 이름이 바뀌었다(§4.1). 옛 이름으로 코드를 짜면 `TypeError`가 난다.

---

## 1. 이 저장소에서 실제로 일어난 일 (측정)

측정 대상: `mlruns/` 전체(6개 experiment, 23런). 이 중 검증곡선을 남긴 학습 런이 19개다.

### 1.1 ★★★ 19런 중 12런이 "step 0이 최선"이었다

`qlib.contrib.model.gbdt.LGBModel.fit`은 `lgb.record_evaluation` 콜백 결과를
`R.log_metrics(step=epoch)`로 흘리고, `pytorch_gru.GRU.fit`도 epoch별 `valid`를 남긴다.
곧 **검증곡선은 이미 전부 기록돼 있었다.** 아무도 읽지 않았을 뿐이다.

⚠️ **두 모델의 부호 규약이 반대다.** LightGBM은 `l2.valid`에 **MSE**를 그대로 쓰고,
qlib의 pytorch 모델은 `metric_fn`이 `-loss_fn`을 반환해 `valid`에 **음수 MSE**를 쓴다
(`pytorch_gru.py`의 `return -self.loss_fn(...)`, `best_score = -np.inf`에서 최대값 탐색).
**최선점을 min으로 찾으면 GRU는 정확히 거꾸로 읽힌다.** 게이트를 짤 때 첫 번째 함정.

| 모델 | experiment | 런 수 | best step | 전 구간 검증 MSE 개선폭 |
|---|---|---:|---|---|
| LightGBM | `phase3_smoke_alpha158_lgb_pilot` | 4 | **전부 0** | **0.0000%** |
| LightGBM | `Experiment` (튜닝·프로브) | 6 | 0·0·5·5·117·166 | 0.0000%~0.0290% |
| LightGBM | `workflow_config_alpha158_lgb_sp500` | 2 | **전부 0** | **0.0000%** |
| LightGBM | `phase3_workflow_config_alpha158_lgb_sp500` | 1 | **0** | **0.0000%** |
| GRU | `workflow_config_alpha360_gru_sp500` | 4 | 0·2·2·3 | 0.0000%~0.0738% |
| GRU | `workflow_config_alpha360_gru_bear2022` | 2 | **전부 0** | **0.0000%** |

**"개선폭"은 어떤 null 가정도 필요 없는 통계량이다** — 첫 스텝 값과 최선값의 차이일 뿐이다.
그래서 라벨 정규화가 바뀌어도, 손실함수가 바뀌어도 그대로 쓸 수 있다. 게이트로 걸기 가장 싸다.

`tune_hyperparams.py`의 주석은 이미 문제를 알고 있었다 — *"L1/L2를 크게 낮춰 즉시 early-stop 해소"*.
그리고 실제로 해소됐다(best step 0 → 117·166). **그런데 §1.2가 보여주듯 그래도 학습은 안 됐다.**
증상만 고치고 게이트를 안 만들었기 때문에 "해소됐다"가 "학습됐다"로 조용히 승격됐다.

### 1.2 ★★★ null 기준선은 데이터와 무관한 상수다

`qlib/data/dataset/processor.py::CSRankNorm.__call__`은 일자별로
`rank(pct=True) → −0.5 → ×3.46`을 한다. 결과 분포는 종목 수와 무관하게 분산이 정해진다:

```
Var[CSRankNorm(label)] = 3.46² / 12 = 0.9976333…      (이론)
                       = 0.9976316                    (실측, label.pkl로 검산)
```

곧 **상수 0을 예측하는 null 모델의 MSE = 0.99763**이고, 이 값은 종목·기간·시장이 바뀌어도
같다. **게이트에 하드코딩할 수 있는 상수다.**

이제 `R²_oos = 1 − MSE_valid / 0.99763`:

| 실험 | 런 | best 검증 MSE | **R²_oos** |
|---|---:|---:|---:|
| `phase3_smoke_alpha158_lgb_pilot` (LGB, 41종목) | 4 | 0.99708 | **+0.00056** |
| `Experiment` (LGB 튜닝 6종) | 6 | 0.99732~0.99761 | **+0.00002 ~ +0.00031** |
| `workflow_config_alpha158_lgb_sp500` (LGB, README 베이스라인) | 3 | 0.99761 | **+0.00002** |
| `workflow_config_alpha360_gru_bear2022` (GRU) | 2 | 0.99741~0.99762 | +0.00002 ~ +0.00022 |
| **`workflow_config_alpha360_gru_sp500` (GRU, README `+11.9%`의 근거)** | 4 | 0.99817~0.99834 | **−0.00054 ~ −0.00071** |

★ **README의 "GRU/Alpha360이 무언가를 잡는다"는 결론이 나온 그 4런은 검증셋에서 상수 예측보다
나빴다.** 최종 판정(고베타·모멘텀 틸트)은 옳았지만, **그 결론에 도달하기 위해 약세장 재실험과
CAPM 분해까지 갈 필요가 없었다.** 학습 직후 R² 한 줄로 끝났을 문제다.

⚠️ 정직한 한계: `l2.valid`는 valid 구간이고 위 상수 검산은 test 구간 `label.pkl`로 했다.
`CSRankNorm` 출력 분산이 rank 기반이라 구간 무관인 것은 유도로 확인했지만, 실제 valid 라벨에
직접 대보지는 않았다. 다만 R²가 ±0.001 규모라 **부호를 뒤집으려면 null이 0.1% 틀려야 하는데
실측 오차는 2e-6이었다.** 결론은 안 바뀐다.

### 1.3 ★★ 예측이 동점투성이라 top-k가 tie-break로 정해진다

각 런의 `artifacts/pred.pkl`에서 **일자별 고유 예측값 개수 / 종목 수**:

| 실험 | 종목/일 | 고유 예측값/일 | 고유비율 | 횡단면 std |
|---|---:|---:|---:|---:|
| `workflow_config_alpha158_lgb_sp500` (README 베이스라인) | 499 | **35** | **0.071** | 0.00236 |
| `phase3_smoke_alpha158_lgb_pilot` | 41 | 8 | 0.183 | 0.00320 |
| `workflow_config_alpha360_gru_sp500` | 499 | 499 | **1.000** | 0.0174~0.0348 |
| `workflow_config_alpha360_gru_bear2022` | 494 | 494 | **1.000** | 0.0148~0.0187 |

`qlib/contrib/strategy/signal_strategy.py::TopkDropoutStrategy`는 `pred_score.sort_values(ascending=False)`로
top-k를 고른다. pandas 기본 `kind='quicksort'`는 **stable이 아니고**, 어느 정렬을 쓰든 **동점의
순서는 신호가 아니라 입력 행 순서가 정한다.**

실측 — 같은 예측을 **값은 그대로 두고 행 순서만 섞은 뒤** top-20을 다시 뽑았을 때 재현율:

| 예측 | top-20 재현율 중앙 | 평균 | 최소 | 100% 재현된 날 |
|---|---:|---:|---:|---:|
| LightGBM S&P500 (베이스라인) | 0.900 | **0.825** | 0.100 | **21.1%** |
| GRU S&P500 | 1.000 | 1.000 | 1.000 | 100.0% |

★ **거래일의 78.9%에서 보유 종목이 바뀐다.** 어떤 날은 20종목 중 18종목이 바뀐다(최소 0.100).
README 베이스라인 행의 `IC 0.0121 · 초과 −5.6% · IR −0.35`는 **부분적으로 동전던지기의 성적**이다.

★★ 그리고 **GRU는 이 검사를 100% 통과한다.** §1.2에서 R²가 더 나쁜 쪽인데도. 이것이
"게이트 하나로는 안 된다"의 실증이고, **왜 분산·동점 진단을 모델 비의존이라고 부르면 안 되는지**의
근거다. 연속 출력 모델(NN·선형·회귀)에서 이 게이트는 원리상 절대 발화하지 않는다.

### 1.4 이 전부가 "PASS"로 기록됐다

`scripts/model_backtest/run_backtest.py::_gates()`의 4개 게이트는 각각
① 피처 158개 ② 라벨이 주간 5일 fwd ③ 백테스트가 주간 스텝 ④ IC/지표가 유한값 산출
을 본다. **네 개 전부 "배선이 맞나"이지 "학습이 됐나"가 아니다.** 게이트 ④는
`np.isfinite(ic.mean()) and not risk.empty`이므로 **상수 예측도 통과한다**(§2.2 참조).

---

## 2. 모델 비의존 게이트 4종

### 2.1 게이트 A — null 모델 대비 (✅ 완전 비의존)

**원리**: 학습된 모델의 검증 성능이 *자명한 기준선*을 못 이기면 실패로 처리한다.
기준선은 회귀에서 **훈련셋 평균 상수 예측**, 분류에서 **최빈 클래스**, 시계열에서 **naive(직전값)**.

이 게이트가 완전 비의존인 이유는 **모델 내부를 전혀 보지 않기 때문**이다. 필요한 건
`(예측 벡터, 라벨 벡터, 지표)` 세 개뿐이고, 이건 GBDT든 트랜스포머든 선형회귀든 똑같이 있다.

**퀀트 형태로 쓸 때**: 회귀 R²(= `1 − MSE/Var[y]`)가 그대로 null 대비 지표다. `Var[y]`가
알려진 상수면(§1.2) 계산이 공짜다. 임계는 `R²_oos > 0`이 최소선이고, 실무 임계는 별도 근거가
필요하다 — 주식 일간/주간 수익률 예측의 OOS R²는 원래 매우 작으므로 **"0보다 크다"를 유의성으로
바꾸려면 Diebold-Mariano류 검정이 필요하다**(§3.3).

⚠️ **IC는 null 대비 지표가 아니다.** IC는 스케일 불변이라 예측을 상수배해도 안 변하고,
분산이 붕괴해도 tie-break가 만들어낸 순서에서 값이 나온다. §2.2 참조.

### 2.2 게이트 B — 예측 분산 붕괴·동점 (⚠️ 부분 비의존)

**IC만으로 상수 예측을 못 거른다는 것을 직접 확인했다** (n=500 횡단면, 난수 라벨):

| 예측 | Pearson IC | Spearman IC |
|---|---:|---:|
| 완전 상수 (모든 종목 0.3) | **6.9e-18** (NaN 아님) | NaN (`ConstantInputWarning`) |
| 서로 다른 값 3개만 | — | **+0.0334** |

★ 완전 상수는 Pearson에서 **0이 아니라 부동소수점 잔차**로 나온다. `np.isfinite(ic.mean())`
검사를 통과한다. 그리고 "3개 값" 케이스는 **IC 0.033**을 낸다 — 이 저장소 베이스라인의
IC 0.0121보다 큰 값이 순전히 동점에서 나올 수 있다는 뜻이다.

**대신 봐야 할 것 (전부 예측 벡터만으로 계산됨)**:

1. **횡단면 std의 시계열** — 0에 붙거나 시간에 따라 붕괴하는지
2. **고유 예측값 수 / 종목 수** (§1.3) — 이산 출력 모델의 붕괴를 직접 잡는다
3. **행 순서 셔플 하 top-k 재현율** (§1.3) — 가장 강력하다. 선택이 신호가 아니라 정렬 순서로
   정해지고 있으면 100% 미만이 나온다. **원인 진단이 아니라 결과 진단이라, 왜 동점이 생겼는지와
   무관하게 발화한다.**

**비의존이 아닌 이유**: 1·2·3 전부 연속 출력 모델에서는 발화하지 않는다(§1.3의 GRU 열).
**이 게이트는 "통과했으니 괜찮다"의 근거로 쓰면 안 되고, "걸렸으면 확실히 문제"로만 써야 한다.**

### 2.3 게이트 C — 학습곡선 퇴화 (⚠️ 반복학습기 전용)

발화 조건 (셋 다 검증곡선만 있으면 계산됨):

1. **`best_step == 0`** — early stopping이 1회차에 걸렸다. LightGBM에서는
   `lightgbm.early_stopping(stopping_rounds, first_metric_only=False, verbose=True, min_delta=0.0)`이
   `Booster.best_iteration`에 최선 회차를 남긴다(공식 API 문서 확인). qlib GRU는
   `best_epoch`를 로그 문자열로만 남기므로 **`evals_result`에서 argmax로 다시 구해야 한다.**
2. **전 구간 개선폭이 임계 미만** — §1.1의 통계량. null 가정이 필요 없다.
3. **단조 악화** — 첫 스텝이 최선이고 이후 계속 나빠지는 형태. 이 저장소 파일럿 4런이 정확히
   이 모양이다(0.99708 → 1.00400, 51스텝 단조 증가).

**비의존이 아닌 이유**: 선형회귀·정규방정식 해·closed-form 추정량에는 학습곡선이 없다.
`n_estimators`가 고정된 RandomForest에도 의미 있는 검증곡선이 없다.
**반복 학습기(GBDT·NN)에만 적용된다고 명시해야 한다.**

### 2.4 게이트 D — 라벨 셔플 순열검정 (✅ 완전 비의존, 비쌈)

라벨을 무작위로 섞고 **같은 파이프라인을 처음부터 다시 돌려** 지표 분포를 만든 뒤, 실제 지표가
그 분포의 어디에 있는지 본다. `scikit-learn 1.7.2` 설치본에서 시그니처 확인:

```
sklearn.model_selection.permutation_test_score(
    estimator, X, y, *, groups=None, cv=None, n_permutations=100,
    n_jobs=None, random_state=0, verbose=0, scoring=None, fit_params=None, params=None)
```

공식 문서가 밝히는 귀무가설
([URL](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.permutation_test_score.html)):

> Permutes targets to generate 'randomized data' and compute the empirical p-value against **the
> null hypothesis that features and targets are independent**.

**완전 비의존**인 이유: `estimator`는 `fit`/`predict`만 있으면 되는 duck type이다.

⚠️⚠️ **그런데 sklearn User Guide가 이 검정의 문턱이 낮다고 직접 못박는다:**

> It is important to note that this test has been shown to produce low p-values even if there is
> only weak structure in the data because in the corresponding permutated datasets there is
> absolutely no structure. **This test is therefore only able to show whether the model reliably
> outperforms random guessing.**

★ 곧 이 검정을 통과해도 **"무작위 추측보다는 낫다"까지만 말한 것**이고, §2.1의 null(상수 예측)
게이트를 대체하지 못한다. **상수 예측은 무작위 추측이 아니다** — 라벨 분포를 알고 있는 최적
상수라서 훨씬 강한 상대다. 순열검정은 게이트 A의 상위 호환이 아니라 **다른 축**(누수 탐지)이다.

**단점**: `n_permutations`번 재학습한다. 이 저장소 GRU 1런이 수십 분이면 100회는 비현실적이다.
→ **채택한다면 `n_permutations`를 20 이하로 줄이고 LightGBM에만, 신호 정의가 바뀔 때만 돌린다.
그리고 이건 "학습됐나" 게이트가 아니라 "누수 있나" 진단으로 분류한다.**

⚠️ **횡단면 랭킹 문제에서는 셔플 축을 정해야 한다.** 라벨 전체를 섞으면 일자 구조까지 파괴돼
너무 쉬운 귀무가설이 된다. **일자 내에서만 섞어야** "피처가 이 종목의 이 날 순위를 아는가"라는
올바른 귀무가설이 된다. sklearn 기본 동작은 전역 셔플이므로 그대로 쓰면 틀린다.

---

## 3. 문헌 — 승격 조건으로서의 baseline 비교

### 3.1 ★★★ ML Test Score — "더 단순한 모델이 더 낫지 않다"가 채점 항목이다

> Breck, E., Cai, S., Nielsen, E., Salib, M., & Sculley, D. (2017).
> "The ML Test Score: A Rubric for ML Production Readiness and Technical Debt Reduction."
> *2017 IEEE International Conference on Big Data (Big Data)*, pp. 1123–1132.
> DOI [10.1109/BigData.2017.8258038](https://doi.org/10.1109/BigData.2017.8258038) ·
> [PDF (Google Research)](https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/aad9f93b86b7addfea4c419b9100c6cdd26cacea.pdf)

Model 섹션 7항목 중 **Model 5**가 정확히 우리가 찾던 항목이다. 원문:

> **Model 5: A simpler model is not better:** Regularly testing against a very simple baseline model,
> such as a linear model with very few features, is an effective strategy both for confirming the
> functionality of the larger pipeline and for helping to assess the cost to benefit tradeoffs of
> more sophisticated techniques.

★ 근거가 **두 갈래**라는 게 중요하다. 성능 비교(cost/benefit)보다 **"파이프라인이 실제로
작동하는지 확인"(confirming the functionality of the larger pipeline)이 앞에 온다.** 곧 이건
모델 선택 조언이 아니라 **배선 검증 도구**로 제시됐다. 이 저장소 `_gates()`의 4개 게이트가
바로 그 배선 검증인데, **null 비교라는 가장 강력한 배선 검증만 빠져 있다.**

같은 표의 나머지 Model 항목 (전부 원문 제목):

| # | 항목 |
|---:|---|
| 1 | Model specs are reviewed and submitted. |
| 2 | Offline and online metrics correlate. |
| 3 | All hyperparameters have been tuned. |
| 4 | The impact of model staleness is known. |
| **5** | **A simpler model is not better.** |
| 6 | Model quality is sufficient on important data slices. |
| 7 | The model is tested for considerations of inclusion. |

Infrastructure 섹션의 **4번이 `Model quality is validated before serving.`** 이다 —
"승격 전 검증"이 별도 항목으로 있다.

**Model 6(data slices)은 퀀트에 그대로 이식된다.** 원문:

> Slicing a data set along certain dimensions of interest can improve fine-grained understanding of
> model quality. … Examining sliced data avoids having fine-grained quality issues masked by a
> global summary metric, e.g. global accuracy improved by 1% but accuracy for one country dropped
> by 50%.

이 저장소가 GRU에서 실제로 겪은 일이다 — 불장 전체 IC는 +0.020인데 약세장 슬라이스는 −0.007이었다
(README). **슬라이스를 사후 확인이 아니라 릴리스 조건으로 넣으라**는 게 Model 6의 권고다:

> Consider including these tests in your release process, e.g. release tests for models can impose
> absolute thresholds (e.g., error for slice x must be <5%), to catch large drops in quality …

**채점 규칙 (§VI.A, 원문):**

> • For each test, half a point is awarded for executing the test manually, with the results
>   documented and distributed.
> • A full point is awarded if there is a system in place to run that test automatically on a
>   repeated basis.
> • Sum the score for each of the 4 sections individually.
> • **The final ML Test Score is computed by taking the minimum of the scores aggregated for each
>   of the 4 sections.**

★ **최솟값을 쓴다.** 저자들의 이유: *"We choose the minimum because we believe all four sections
are important, and so a system must consider all in order to raise the score."*
곧 **한 축이 0이면 나머지가 만점이어도 0**이다. 배선 게이트 4개가 잘 돌아도 학습 검증이 없으면
전체가 0이라는 뜻이 된다.

**Table V — 점수 해석 (원문):**

| Points | Description |
|---|---|
| 0 | More of a research project than a productionized system. |
| (0,1] | Not totally untested, but it is worth considering the possibility of serious holes in reliability. |
| (1,2] | There's been first pass at basic productionization, but additional investment may be needed. |
| (2,3] | Reasonably tested, but it's possible that more of those tests and procedures may be automated. |
| (3,5] | Strong levels of automated testing and monitoring, appropriate for mission-critical systems. |
| > 5 | Exceptional levels of automated testing and monitoring. |

✅ **모델 비의존**: 루브릭 전체가 모델 클래스를 언급하지 않는다. Model 5의 "simple baseline"도
"linear model with very few features"를 *예시로만* 든다.

### 3.2 ★★ 예측 검증의 규범 형태 — "못 이기면 고려 대상이 아니다"

> Hyndman, R.J., & Athanasopoulos, G. (2021). *Forecasting: principles and practice*, 3rd edition.
> OTexts: Melbourne, Australia. [OTexts.com/fpp3](https://otexts.com/fpp3) ·
> §5.2 [Some simple forecasting methods](https://otexts.com/fpp3/simple-methods.html)

이 책은 mean / naïve / seasonal naïve / drift 네 방법을 **책 전체의 벤치마크로 선언**한다:
*"We will use four simple forecasting methods as benchmarks throughout this book."*
그리고 §5.2 마지막 문단이 이 문서에서 가장 강한 규범 진술이다 (원문 그대로, 문장 중간부터라
`That is,`를 포함해 인용):

> Sometimes one of these simple methods will be the best forecasting method available; but in many
> cases, these methods will serve as benchmarks rather than the method of choice. **That is, any
> forecasting methods we develop will be compared to these simple methods to ensure that the new
> method is better than these simple alternatives. If not, the new method is not worth considering.**

★ 그리고 이 책은 **주식에 대해 명시적으로** 말한다 (§5.4
[Residual diagnostics](https://otexts.com/fpp3/diagnostics.html)):

> For stock market prices and indexes, **the best forecasting method is often the naïve method.**

⚠️ 다만 "효율적 시장이라 naive가 최적"이라는 **단일 문장은 원문에 없다.** random walk 최적성(§5.2·§9.1)과
효율적 시장 가설(§1.1)은 책 안에서 서로 다른 위치에 있고 저자가 직접 잇지 않는다. 이어 붙여
인용하면 원문에 없는 주장이 된다.

✅ **모델 비의존**: 벤치마크는 예측값 계열로만 정의되므로 어떤 학습기든 같은 잣대가 적용된다.

⚠️ **퀀트 이식 주의**: 이 저장소는 횡단면 랭킹이지 시계열 예측이 아니다. naive(직전값)의 대응물은
"직전 기 수익률 순위" 또는 "직전 기 예측 순위"이고, mean의 대응물이 §2.1의 상수 예측이다.
**mean은 그대로 쓸 수 있고, naive는 번역이 필요하다.**

### 3.3 정규화된 null 비교 지표 — R²와 그 한계

`sklearn.metrics.r2_score` 공식 문서
([URL](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.r2_score.html))가
§2.1의 게이트를 그대로 정의한다:

> Best possible score is 1.0 and it can be negative (because the model can be arbitrarily worse).
> **In the general case when the true y is non-constant, a constant model that always predicts the
> average y disregarding the input features would get a R² score of 0.0.**

`DummyRegressor` 문서
([URL](https://scikit-learn.org/stable/modules/generated/sklearn.dummy.DummyRegressor.html)) —
"실전에 쓰지 말라"는 경고까지 붙어 있다:

> This regressor is useful as a simple baseline to compare with other (real) regressors.
> **Do not use it for real problems.**

⚠️ `DummyClassifier`의 문구는 다르다 — *"This classifier serves as a simple baseline to compare
against other more complex classifiers."* 이고 "Do not use it for real problems."가 **없다.**
둘을 섞어 인용하지 말 것.

sklearn User Guide(`model_evaluation`)의 위치 규정:

> When doing supervised learning, **a simple sanity check** consists of comparing one's estimator
> against simple rules of thumb. … when the accuracy of a classifier is too close to random, it
> probably means that something went wrong: features are not helpful, a hyperparameter is not
> correctly tuned, the classifier is suffering from class imbalance, etc...

★ 세 출처(Breck Model 5 / FPP3 §5.2 / sklearn User Guide)가 **같은 것을 각각 "테스트 항목",
"규범", "sanity check"로 부른다.** 우연이 아니라 세 분야가 독립적으로 도달한 최소 요건이다.

### 3.4 "R² > 0"을 유의성으로 바꾸려면 — 그리고 왜 조심해야 하는가

> Diebold, F.X., & Mariano, R.S. (1995). "Comparing Predictive Accuracy."
> *Journal of Business & Economic Statistics*, 13(3), 253–263.
> DOI [10.1080/07350015.1995.10524599](https://doi.org/10.1080/07350015.1995.10524599) ·
> [PDF (저자 배포본)](https://www.sas.upenn.edu/~fdiebold/papers/paper68/pa.dm.pdf)

DM 검정의 귀무가설이 정확히 §2.1이 필요로 하는 것이다:

> Thus, the "equal accuracy" null hypothesis is equivalent to the null hypothesis that the
> population mean of the loss-differential series is 0.

곧 `loss_model − loss_null` 계열의 평균이 0인지를 검정한다. 손실함수가 이차형일 필요도, 오차가
정규일 필요도 없다(초록: *"the loss function need not be quadratic and need not even be
symmetric, and forecast errors can be non-Gaussian, nonzero mean, serially correlated, and
contemporaneously correlated"*). **겹침 라벨로 자기상관이 있는 이 저장소 상황에 맞는다.**

⚠️⚠️ **그런데 저자 본인이 20년 뒤에 오용을 경고했다.**

> Diebold, F.X. (2015). "Comparing Predictive Accuracy, Twenty Years Later: A Personal Perspective
> on the Use and Abuse of Diebold-Mariano Tests." *Journal of Business & Economic Statistics*,
> 33(1), 1–9. DOI [10.1080/07350015.2014.983236](https://doi.org/10.1080/07350015.2014.983236) ·
> [PDF (저자 배포본)](https://www.sas.upenn.edu/~fdiebold/papers/paper113/Diebold_DM%20Test.pdf)

초록 원문:

> **The Diebold-Mariano (DM) test was intended for comparing forecasts; it has been, and remains,
> useful in that regard. The DM test was not intended for comparing models.** Much of the large
> ensuing literature, however, uses DM-type tests for comparing models, in pseudo-out-of-sample
> environments.

그리고 결정적인 기술적 함정:

> Asymptotic normality holds, for example, when **nonnested** models are compared, but **not when
> nested models are compared.**

⚠️ **우리 용법은 중첩이다.** "학습된 모델 vs 상수 예측"에서 상수 예측은 학습된 모델이 표현할 수
있는 특수 경우다. 따라서 **DM 통계량의 N(0,1) 임계값을 그대로 쓰면 안 된다.**
→ **실용 결론: R²의 부호는 게이트로 쓰되, DM p-value를 유의성 주장으로 승격시키지 마라.**
`R²_oos ≤ 0`이면 실패, `> 0`이면 "실패는 아님"까지가 이 게이트가 말할 수 있는 전부다.
"유의하게 낫다"는 별개 문제이며 시행 횟수 보정이 먼저다 →
[`trial-accounting.md`](trial-accounting.md).

### 3.5 config가 코드보다 길어진다 — 이 저장소 yaml의 위치

> Sculley, D., Holt, G., Golovin, D., Davydov, E., Phillips, T., Ebner, D., Chaudhary, V.,
> Young, M., Crespo, J.-F., & Dennison, D. (2015). "Hidden Technical Debt in Machine Learning
> Systems." *Advances in Neural Information Processing Systems 28 (NIPS 2015)*, pp. 2503–2511.
> [PDF (NeurIPS proceedings)](https://papers.nips.cc/paper_files/paper/2015/file/86df7dcfd896fcaf2674f757a2463eba-Paper.pdf)
> ⚠️ **arXiv 판은 존재하지 않는다.** proceedings PDF가 유일한 1차 출처다.

§6 Configuration Debt 원문:

> We have observed that both researchers and engineers may treat configuration (and extension of
> configuration) as an afterthought. Indeed, verification or testing of configurations may not even
> be seen as important. **In a mature system which is being actively developed, the number of lines
> of configuration can far exceed the number of lines of the traditional code. Each configuration
> line has a potential for mistakes.**

저자들이 제시한 좋은 config 시스템의 6원칙 (원문):

> • It should be easy to specify a configuration as a small change from a previous configuration.
> • It should be hard to make manual errors, omissions, or oversights.
> • It should be easy to see, visually, the difference in configuration between two models.
> • **It should be easy to automatically assert and verify basic facts about the configuration:
>   number of features used, transitive closure of data dependencies, etc.**
> • It should be possible to detect unused or redundant settings.
> • Configurations should undergo a full code review and be checked into a repository.

★ 네 번째 원칙이 `workflow_config_alpha158_lgb_sp500.yaml`의 `lambda_l1: 205.6999` 문제를
정확히 겨눈다 — **"config에 대한 기본 사실을 자동으로 assert하라."** 이 저장소에는 config가
커밋돼 있고(6원칙 중 마지막은 충족) diff도 보이지만, **어떤 값도 assert되지 않는다.**
CSI300용 정규화 강도가 S&P500 config에 상속돼도 아무것도 울지 않는다.

✅ **모델 비의존**: config debt은 모델 종류와 무관하다. 오히려 모델을 바꿀 때(LGB→GRU→XGB)
가장 크게 터진다 — §1.1의 부호 규약 함정이 그 사례다.

---

## 4. 도구가 실제로 제공하는 것

> 아래 시그니처는 **이 저장소 `.venv`에 설치된 버전에서 직접 introspect**해 받아 적었다.
> 버전은 `mlflow 3.14.0`, `scikit-learn 1.7.2`.

### 4.1 ★★ MLflow — baseline 비교는 있다. 단 이름이 바뀌었다

**`mlflow.evaluate()`에는 `baseline_model`도 `validation_thresholds`도 없다.** MLflow 3.14.0 설치본
시그니처:

```
mlflow.evaluate(model=None, data=None, *, model_type=None, targets=None, predictions=None,
                dataset_path=None, feature_names=None, evaluators=None, evaluator_config=None,
                extra_metrics=None, custom_artifacts=None, env_manager='local',
                model_config=None, inference_params=None, model_id=None, ...)
```

기능은 **별도 함수로 분리됐다.** 공식 문서 서술: *"MLflow 2.18.0 moved model validation from
mlflow.models.evaluate() to mlflow.validate_evaluation_results()"*
([Model Evaluation](https://mlflow.org/docs/latest/ml/evaluation/)).
설치본에서 확인한 실제 API:

```
mlflow.validate_evaluation_results(
    validation_thresholds: dict[str, MetricThreshold],
    candidate_result: EvaluationResult,
    baseline_result: EvaluationResult | None = None)

mlflow.models.MetricThreshold(
    threshold=None, min_absolute_change=None, min_relative_change=None, greater_is_better=None)
```

docstring 원문(설치본):

> *"Validate the evaluation result from one model (candidate) against another model (baseline).
> If the candidate results do not meet the validation thresholds, an ModelValidationFailedException
> will be raised."*
> *"baseline_result: The evaluation result of the baseline model. … If set to None, the candidate
> model result will be compared against the threshold values directly."*
> *"This API is a replacement for the deprecated model validation functionality in the
> `mlflow.evaluate` API."*

**즉 "null 모델 대비 최소 개선"을 예외로 강제하는 기능이 1차 문서 수준으로 존재한다.**
`min_absolute_change` / `min_relative_change`가 정확히 §2.1이 요구하는 축이다.

⚠️ **그런데 이 저장소에 그대로는 못 쓴다. 세 가지 이유:**

1. `mlflow.evaluate()`의 `model_type`은 `'classifier' | 'regressor' | 'question-answering' |
   'text-summarization' | 'text' | 'retriever'`뿐이다(설치본 docstring). **횡단면 랭킹 타입이 없다.**
   `regressor`로 부르면 내장 지표는 `mean_squared_error`·`r2_score` 등 pooled 지표이고,
   **일자별 IC·Rank IC는 안 나온다.** `extra_metrics`로 직접 넣어야 한다.
2. 다만 **정적 데이터셋 평가는 지원한다** — `model`을 비우고 `data`(DataFrame) + `predictions`
   (열 이름)만 주면 된다. 곧 `pred.pkl`을 그대로 먹일 수 있다.
   *"the static dataset will be used for evaluation instead of a model."*
3. ★ **파일 백엔드가 유지보수 모드로 들어갔다.** `mlflow 3.14.0`에서 `./mlruns`를 그냥 읽으면
   예외가 난다:
   > *"The filesystem tracking backend (e.g., './mlruns') is in maintenance mode and will not
   > receive further updates. … set `MLFLOW_ALLOW_FILE_STORE=true` to opt out of this exception."*

   공식 마이그레이션 문서([migrate-from-file-store](https://mlflow.org/docs/latest/self-hosting/migrate-from-file-store))는
   `mlflow migrate-filestore --source /path/to/mlruns --target sqlite:///path/to/mlflow.db`를
   권한다. **원장을 만들기로 하면 이건 선결 조건이다** — 자세히는
   [`trial-accounting.md`](trial-accounting.md) §6.

**Model Registry 쪽 승격 패턴**도 1차 문서에 있다
([Model Registry](https://mlflow.org/docs/latest/ml/model-registry/)):

> *"At the model version level, you could tag versions undergoing pre-deployment validation with
> `validation_status:pending` and those cleared for deployment with `validation_status:approved`."*

설치본 확인 API: `MlflowClient.set_model_version_tag(name, version, key, value, stage=None)`,
`MlflowClient.set_registered_model_alias(name, alias, version)`,
`MlflowClient.search_model_versions(filter_string, ...)`.

### 4.2 scikit-learn — null 기준선의 표준 구현 (✅ 완전 비의존)

설치본 `scikit-learn 1.7.2` 확인:

```
sklearn.dummy.DummyRegressor(*, strategy='mean', constant=None, quantile=None)
    strategy: {"mean", "median", "quantile", "constant"}, default="mean"
      * "mean": always predicts the mean of the training set
      * "median": always predicts the median of the training set
      ...
sklearn.inspection.permutation_importance(estimator, X, y, *, scoring=None, n_repeats=5, ...)
sklearn.model_selection.permutation_test_score(estimator, X, y, *, cv=None, n_permutations=100, ...)
```

세 개 다 `estimator`를 duck type으로만 요구하므로 **모델 클래스와 무관**하다.
`permutation_importance`는 "피처 중요도 전멸" 탐지의 모델 비의존 버전이다 — GBDT의 `feature_importance_`나
선형모형의 `coef_` 같은 모델 고유 속성을 안 본다.

### 4.3 deepchecks — null 대비를 "조건"으로 만들어 둔 사례

공식 문서 확인 ([Simple Model Comparison](https://docs.deepchecks.com/stable/tabular/auto_checks/model_evaluation/plot_simple_model_comparison.html)):

- 클래스: `deepchecks.tabular.checks.SimpleModelComparison`
- 문서 원문: *"The simple model is designed to produce the best performance achievable using very
  simple rules. The goal of the simple model is to provide a baseline of minimal model performance
  for the given task, to which the user model may be compared."*
- 기준선 종류: `most_frequent`(기본) / `uniform` / `stratified` / `tree`
- **조건 API: `add_condition_gain_greater_than(threshold)`** — 곧 "단순 모델 대비 성능 이득이
  임계 이상"이 **통과/실패를 가르는 조건 객체**로 존재한다.

★ 여기서 가져올 것은 라이브러리가 아니라 **형식**이다 — "baseline 대비 이득"을 지표가 아니라
**조건(condition)** 으로 두어 실패시키는 구조. 이 저장소 `_gates()`가 이미 같은 모양(불리언 리스트 →
`sys.exit(1)`)이라 붙이기 쉽다. **deepchecks를 의존성으로 추가할 필요는 없다.**

⚠️ deepchecks는 tabular 표준 지도학습 전제라 **횡단면·일자 패널 구조를 모른다.** 그대로 쓰면
pooled 평가가 되어 이 저장소의 문제(일자 내 랭킹)를 못 본다.

### 4.4 Evidently — "reference 없으면 dummy와 비교"가 기본값

공식 문서 ([Regression preset](https://docs.evidentlyai.com/metrics/preset_regression)) 원문:

> *"If there is no reference, Evidently will create a dummy regression model as a baseline and run
> checks against it."*

클래스명 `RegressionPreset`. **null 비교가 옵션이 아니라 기본 동작**이라는 점이 참고할 설계다.

⚠️ Evidently는 v0.7 전후로 API가 크게 바뀌었다(구 `RegressionTestPreset` → 현 `RegressionPreset`).
**버전 고정 없이 인용하면 낡는다.**

### 4.5 Great Expectations — 이 용도에는 해당 없음

공식 문서 원문: *"Great Expectations (GX) is a framework for describing data using expressive tests
and then validating that the data meets test criteria."*
**데이터 검증 프레임워크이고 학습된 모델·모델 성능 지표를 검증하지 않는다.**
"학습 게이트를 GX로 건다"는 후보에서 뺀다. (데이터 파이프라인 검증에는 별개로 유효하다.)

---

## 5. 확인 실패 / 미검증

| 대상 | 상태 | 대체 |
|---|---|---|
| `ieeexplore.ieee.org/document/8258038` (ML Test Score 게재본) | **확인 실패** — 봇 차단 | Google Research 배포 PDF 전문 + DOI 해석 + DBLP로 면수 확인 |
| `tandfonline.com`의 DM 1995 / DM 2015 | **확인 실패** — HTTP 403 | Diebold 본인 배포 PDF(게재본 스캔) |
| DM 1995 **원판 조판** 스캔 | 미확보 | 2002 JBES 20주년 재수록본. 본문 동일, 면수는 헤더로 간접 확인 |
| Hidden Technical Debt의 arXiv 판 | **존재하지 않음** | NIPS 2015 proceedings PDF가 유일 1차 출처 |
| `l2.valid`의 **valid 구간 라벨 분산 직접 측정** | 미측정 | test 구간 `label.pkl`로 검산(오차 2e-6). §1.2의 한계 참조 |
| MLflow의 **횡단면 랭킹용 model_type** | **존재하지 않음** | `extra_metrics`로 직접 넣어야 함 (§4.1) |
| 게이트 임계값(“R²가 얼마 이상이어야 하나”)의 문헌 근거 | **못 찾음** | 문헌은 전부 부호(`> null`)만 말한다. 임계는 이 저장소가 정해야 하고 **정한 순간 연구자 자유도가 된다** — [`study-pitfalls.md`](../project/study-pitfalls.md) §2.1과 같은 함정 |

⚠️ **조사 방법에 관한 경고 하나.** 이 조사 중 웹 페이지 요약 도구가 ML Test Score PDF에 대해
**저자·학회·연도·항목 내용을 통째로 지어냈다.** 실재하지 않는 저자명과 학회명이 그럴듯하게
나왔다. 그래서 위 인용은 전부 PDF 텍스트를 직접 추출해 재검증한 것이다.
**요약본을 원문 확인으로 세지 말 것** — 이 저장소에서 가장 해로운 오류 유형이다.

---

## 6. 이 저장소에 어디에 붙이나

착지점만 지목한다. 코드는 쓰지 않는다.

1. **`scripts/model_backtest/run_backtest.py::_gates()`에 게이트 A·B·C 3개를 추가한다.**
   기존 4개는 배선 검증이고 새 3개는 학습 검증이다 — **섞지 말고 절을 나눠 출력**해야
   "배선은 맞는데 학습이 안 됐다"가 한눈에 보인다. 실패 시 `sys.exit(1)`은 기존 규약 그대로.
2. **게이트 A는 상수 하나로 끝난다** — `NULL_MSE = 3.46**2 / 12`. `recorder.load_object`로
   검증 손실을 못 읽으면 `pred.pkl`과 `label.pkl`로 직접 R²를 계산한다.
   ⚠️ `run_backtest.py`는 `SigAnaRecord`만 만들고 검증구간 예측은 안 남기므로,
   **`model.fit()` 직후 `evals_result`를 받아 두는 편이 싸다**(LGBModel·GRU 둘 다 `evals_result`
   인자를 받는다).
3. **게이트 C의 부호 규약을 함수 하나로 격리한다.** LightGBM `l2.valid`(MSE, min이 최선)와
   qlib pytorch `valid`(−MSE, max가 최선)가 반대다(§1.1). 모델을 늘릴 때마다 밟을 함정이므로
   **"이 모델의 검증지표는 클수록 좋은가"를 모델 어댑터가 선언하게** 만들어야 한다.
4. **`workflow_config_alpha158_lgb_sp500.yaml`의 `lambda_l1: 205.6999` / `lambda_l2: 580.9768`은
   CSI300 튜닝값이다.** §1.1이 보여주듯 이 값에서 best step이 0으로 고정된다.
   게이트 C를 붙이면 **이 config는 즉시 실패한다** — 그게 정상 동작이다.
   (`tune_hyperparams.py`의 완화 후보들은 best step은 풀었지만 R²는 그대로였다. §1.2)
5. **README의 성능 표에 `R²_oos`(또는 best step) 열을 넣는다.** IC만 있는 표는 §2.2가 보여주듯
   상수 예측과 구별되지 않는다. 게이트를 통과하지 못한 행은 숫자를 싣지 말고
   **"학습 실패"로 적는 편이 정직하다.**
6. **슬라이스 게이트(ML Test Score Model 6, §3.1)를 레짐 축으로 하나만 넣는다.** 이 저장소는
   불장/약세장 슬라이스에서 결론이 뒤집힌 전례가 있고(README), 그걸 *사후 실험*으로 발견했다.
   `_gates()`에 넣기엔 test 구간이 하나뿐이라 무리이므로, **`probe_*.py` 계열이 레짐별 IC를
   나란히 내도록** 하는 편이 현실적이다.
7. `docs/project/study-pitfalls.md`에 **"§2.7 검증손실이 null과 같은데 IC가 양수로 나온다"**
   한 항목을 추가한다. §2.2의 IC 0.033 실측이 근거다.
   (같은 문서 §3.2 *"검증 코드가 원리상 실패 불가일 수 있다"* 의 정확한 후속 사례다 —
   이번엔 검사가 실패 불가였던 게 아니라 **검사가 아예 없었다.**)
