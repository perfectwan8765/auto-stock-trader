# 리서치 — Optuna 도입 판단 (모델 비의존)

- 조사일: 2026-08-18
- 목적: **"이 저장소가 Optuna(또는 동류 하이퍼파라미터 탐색 프레임워크)를 도입해야 하는가"** 에
  답한다. 사용법이 아니라 **도입 판단**이 산출물이고, 그 판단이 선행 조사 2건과 충돌하는지를
  같이 적는다.
- 방법: 도구 API는 **스크래치패드의 별도 임시 venv에 `optuna 4.9.0` · `optuna-integration 4.9.0`을
  설치해 직접 introspect·실행**했다. 이 저장소 `.venv`와 `requirements.txt`는 **읽기만 했고 수정하지
  않았다.** 논문은 저자·출판사 배포 PDF를 내려받아 텍스트를 추출해 인용했고, 릴리스 노트는
  **GitHub API로 JSON 본문을 받아 문자열을 grep**했다(웹 요약 도구를 원문 확인으로 세지 않았다).
  확인 못 한 것은 §6에 적었다.
- 선행 조사(전제로 삼는다):
  [`training-gates.md`](training-gates.md) — "이 한 번의 학습이 성립했는가",
  [`trial-accounting.md`](trial-accounting.md) — "몇 번 시도했는가".
  이 문서는 셋째 축이다 — **"시도를 자동으로 늘리는 도구를 붙일 것인가."**
- 이 문서에 계좌번호·잔액·보유 종목은 없다. 수치는 백테스트 지표와 도구 introspect 결과뿐이다.

---

## 0. 요약

### 판정: **도입 반대.** 옵티마이저로도, 원장으로도 지금은 붙이지 않는다

한 줄 근거: **선행 조사가 확립한 두 사실 — ①정규화를 전 구간 쓸어도 OOS R²가 null 위로 올라오지
않았다([`training-gates.md`](training-gates.md) §1.2) ②183주로는 시행 예산을 이미 넘겼다
([`trial-accounting.md`](trial-accounting.md) §1.4) — 아래에서 Optuna가 싸게 만들어 주는 것은
정확히 "시도 횟수"이고, 그것이 이 저장소에서 지금 부족한 자원이 아니다.**

**확립된 것 — 확인해 봤다**

1. ★★★ **`optuna-integration`의 `MLflowCallback`은 v4.9.0에서 deprecated이고 v6.0.0 제거
   예정이며, 후속 구현이 아직 어디에도 없다.** 릴리스 노트 원문은
   *"`MLflowCallback`: This feature will be migrated to OptunaHub in the future."* 이고,
   OptunaHub 레지스트리 `package/callbacks/`에는 `terminator`·`trackio`·`wandb` 세 개뿐 —
   **`mlflow`가 없다**(GitHub API로 확인). 곧 **"Optuna로 탐색하고 MLflow로 기록한다"는 조합은
   지금 지원되는 경로가 아니다.** (§2.3)
2. ★★★ **qlib에는 이미 하이퍼파라미터 탐색 모듈이 있고, 방치돼 죽어 있다.**
   `qlib/contrib/tuner/`(449줄)는 `hyperopt`의 TPE로 `fmin`을 돌린다. 그런데 ①`hyperopt`가
   미설치라 import 즉시 실패하고 ②`subprocess.call("estimator -c ...")`가 호출하는 `estimator`
   CLI가 설치본 `bin/`에 없고(있는 것은 `qrun` 하나) ③결과를 `sacred/{}` 디렉터리에서 읽는데
   qlib은 MLflow 레코더로 옮겨간 뒤다. **그리고 실제 버그가 있다** — `if self.optim_config == "min"`
   은 config 객체를 문자열과 비교하므로 항상 거짓이고, 최대화 의도가 조용히 correlation 분기로
   흐른다. (§1.2)
3. ★★ **DSR을 독립 구현으로 재현했고**([`trial-accounting.md`](trial-accounting.md) §1.2의
   5개 값을 소수 4자리까지 일치), 그 위에서 Optuna 규모의 시행 수를 넣어 봤다 —
   **N=200이면 DSR 0.0081, N=223이면 0.0070**이다. 관례 기각선 0.95는 물론이고
   0.05조차 넘지 못한다. (§4.1)
4. ★★★ **금융 시계열에서 HPO 자체를 경고하는 1차 문헌이 있다.** Arnott·Harvey·Markowitz(2019)가
   익명 인용으로 못박는다 — *"[T]uning 10 different hyperparameters using k-fold cross-validation
   is a terrible idea if you are trying to predict returns with 50 years of data."* 그리고 같은
   논문이 앞 문단에서 *"cross-validation does not alleviate the curse of dimensionality"* 라고
   쓴다. **이 저장소가 가진 것은 50년이 아니라 3.52년이다.** (§3.1)
5. ★★ **pruner는 학습 게이트를 대체하지 못한다.** `MedianPruner`의 기준은 *"median of
   intermediate results of previous trials at the same step"* — **다른 trial과의 상대 비교**이고,
   [`training-gates.md`](training-gates.md) §2.1이 요구하는 **null 대비 절대 비교가 아니다.**
   전 trial이 똑같이 null 수준이면 절반은 통과한다. (§2.4 · §4.4)
6. ★★ **끊긴 trial은 원장에 값을 남긴다.** `PRUNED` trial의 `value`는 NaN이 아니라 **마지막
   중간값**이고 `trials_dataframe()`에 정상 행으로 들어온다(실측). 상태를 안 보고 세면
   **"실패 예정 시행"이 N에 섞이고**, 이는 PBO 논문이 금지한 것이다
   ([`trial-accounting.md`](trial-accounting.md) §7.2). (§2.1 · §4.4)
7. ★★ **무음 크래시는 `RUNNING`으로 영구히 남는다.** trial 실행 중 `SIGKILL`을 보내면 params는
   저장되고 state는 `RUNNING`에 멈춘다(실측). 이 저장소는 **macOS에서 torch↔lightgbm OpenMP
   충돌로 무음 크래시를 겪는 이력이 있으므로** 정확히 이 상태가 쌓인다. `len(study.trials)`에는
   들어가고 `COMPLETE` 필터에는 안 들어간다 — **N이 두 값을 갖는다.** (§2.6)
8. **재개(resume) 의미론은 깨끗하다.** 같은 `study_name`으로 `load_study`하면 trial 번호가
   14 → 15로 이어진다(실측). 곧 **번호 자체는 신뢰할 수 있는 누적 카운터**다. 이것이 Optuna가
   원장으로서 갖는 유일한 실질 장점이고, §4.5에서 그것만으로는 부족한 이유를 적었다.
9. **MLflow 부모-자식 런으로 충분하다.** 이 저장소가 지금 잃고 있는 것은 후보 이름과 시행
   경계뿐이고([`trial-accounting.md`](trial-accounting.md) §1.1.1), 그 둘은 `mlflow.start_run(nested=True)`
   과 태그로 해결된다. `mlflow 3.14.0` 설치본에 `start_run(..., nested, parent_run_id, tags)`가
   전부 있다. **의존성 추가가 0이다.** (§5.1)

**통설이지만 근거가 약하거나 틀린 것**

1. "탐색 프레임워크를 붙이면 시행이 원장에 자동으로 남는다" — 절반만 맞다. **Optuna storage에
   남고 `mlruns/`에는 안 남는다.** 원장이 둘로 갈리면 N 집계가 어느 쪽에서도 완결되지 않는다(§4.3).
2. "pruner가 무의미한 학습을 알아서 끊어 준다" — 끊는 기준이 **다른 trial의 중앙값**이다.
   [`training-gates.md`](training-gates.md) §1.1이 보여준 "19런 중 12런이 step 0" 같은 상황,
   즉 **전부 똑같이 학습이 안 된 상황에서는 pruner가 아무것도 못 잡는다**(§4.4).
3. "TPE 같은 유도탐색은 시행 1회로 세면 된다" — PBO 논문의 그 진술은 **CSCV 행렬 M의 열 정의**이고
   DSR의 N이 아니다([`trial-accounting.md`](trial-accounting.md) §7.2가 "섞지 마라"고 명시).
   그리고 Arnott 등의 parallel universe 논증은 **정반대 방향**을 가리킨다(§4.1).
4. "sklearn `GridSearchCV`를 쓰면 표준 방식이다" — 이 저장소에는 **구조적으로 못 붙는다.**
   `LGBModel.fit(dataset: DatasetH, ...)`은 `(X, y)`를 받지 않는다(설치본 시그니처). 억지로
   `PredefinedSplit`을 물려 단일 분할로 만들 수는 있지만, 그러면 `cv_results_`는 **후보 표
   하나**로 퇴화한다 — 지금 `tune_hyperparams.py`가 이미 만드는 그 표다(§5.2).
5. "Optuna를 옵티마이저 없이 원장으로만 쓰면 절충이 된다" — **반박된다.** `ask`/`tell`로
   sampler를 우회하는 순간 남는 것은 SQLite 테이블 13개짜리 스키마이고, 이 저장소는 이미
   SQLite 원장을 하나 설계해 뒀다([`ledger.md`](../project/ledger.md)). **원장이 셋이 된다**(§4.5).

**모델 비의존성 — 결론마다 다르다**

| 결론 | 근거의 성격 | 비의존? |
|---|---|---|
| 도입 반대 (탐색 자동화) | 표본길이 대비 시행 예산 · 문헌 | ✅ **완전** — 모델을 안 봄 |
| MLflow 부모-자식으로 대체 | 기록 구조 | ✅ **완전** |
| pruner가 게이트를 대체 못 함 | pruner의 비교 대상이 상대적 | ✅ **완전** |
| `GridSearchCV` 불가 | qlib `Model.fit(dataset)` 계약 | ⚠️ **qlib 의존** — 모델이 아니라 프레임워크에 묶임 |
| 학습곡선 기반 pruning의 적용 범위 | 중간값 `report()`가 필요 | ⚠️ **반복학습기 전용** — [`training-gates.md`](training-gates.md) §2.3의 게이트 C와 같은 제약 |

---

## 1. 대체 대상 — 지금 무엇을 하고 있나

### 1.1 `tune_hyperparams.py`의 실제 형태

`scripts/model_backtest/tune_hyperparams.py`는 `CANDIDATES` 딕셔너리에 **후보 6개를 손으로 적어
두고** 순회한다. 공통 축은 `COMMON = dict(loss="mse", num_threads=8, seed=2026,
early_stopping_rounds=50, num_boost_round=1000)`으로 고정이고, 후보별로 `num_leaves`·`max_depth`·
`learning_rate`·`lambda_l1`·`lambda_l2`·`colsample_bytree`·`subsample` 7개를 바꾼다.
선택은 `res.sort_values("valid_RankIC", ascending=False)` 뒤 `res.iloc[0]`이다.

★ **이 스크립트가 이미 갖고 있는 미덕 세 개를 먼저 세야 한다** — 도입 판단의 기준선이 여기다.

1. **N이 코드에 열거돼 있다.** 격자가 아니라 명시적 6개다. 그래서 세는 것이 자명하다.
   [`trial-accounting.md`](trial-accounting.md) §3이 인용한 MinBTL 논문의 `N = 2⁵ = 32` 계산법을
   그대로 쓰면 안 되는 이유가 바로 이것이고, 같은 문서가 그 점을 이미 지적했다.
2. **test 재관측 금지가 docstring에 규율로 적혀 있다** — *"⚠️ 규율: test는 ②에서 이미 1회 관측
   → 여기서 **재관측 금지**. valid 지표로만 후보 선택."* 그리고 실제로 백테스트를 실행하지 않는다.
   이는 `microcap-insider-prereg.md` §4.1의 "판정 단위" 규율과 같은 계열이다.
3. **dataset을 1회 빌드해 후보 간 재사용한다** — 피처 계산이 후보마다 반복되지 않는다.

빠진 것은 **기록 한 축뿐**이다. 후보 6개가 MLflow 런 1개로 접히고 후보 이름이 영구 소실된다
([`trial-accounting.md`](trial-accounting.md) §1.1.1). ★ **곧 대체 대상은 "탐색 알고리즘"이 아니라
"기록"이다.** 이 구분이 §4.3의 판단을 지배한다.

### 1.2 ★★★ qlib은 이미 HPO를 붙였다가 방치했다

설치본 `qlib/contrib/tuner/`(5파일 449줄)를 읽었다. 구조는 이렇다.

| 파일 | 역할 | 상태 |
|---|---|---|
| `tuner.py` | `Tuner` 추상클래스 + `QLibTuner`. `fmin(fn=self.objective, space=self.space, algo=tpe.suggest, max_evals=...)` | `from hyperopt import fmin, tpe` |
| `space.py` | 탐색공간 2개(`TopkAmountStrategySpace`·`QLibDataLabelSpace`) | `from hyperopt import hp` |
| `pipeline.py`·`config.py`·`launcher.py` | yaml 기반 CLI 진입점 | — |

**작동하지 않는 이유 세 개.**

1. **`hyperopt`가 미설치다.** 이 저장소 `.venv`에서 `import hyperopt` → `ModuleNotFoundError`
   (확인). `requirements.txt`에도 없다.
2. **`estimator` CLI가 없다.** `QLibTuner.objective`는 후보마다
   `subprocess.call("estimator -c {}".format(estimator_path), shell=True)`로 **외부 프로세스를
   띄운다.** 그런데 `.venv/bin/`에 있는 qlib 진입점은 **`qrun` 하나뿐**이다(확인).
   곧 모든 trial이 `sub_fails` 분기로 떨어져 `{"loss": np.nan, "status": STATUS_FAIL}`을 반환한다.
3. **결과 경로가 MLflow 이전 세대다.** `EXP_RESULT_DIR = "sacred/{}"`, `EXP_INFO_NAME =
   "exp_info.json"`을 읽는다. 지금 qlib은 `mlruns/`에 쓴다.

⚠️ **그리고 실제 버그가 하나 있다.** `fetch_result`의 마지막 분기다:

```python
if self.optim_config == "min":
    return res.values[0]
elif self.optim_config == "max":
    return -res.values[0]
else:
    # self.optim_config == 'correlation'
    return np.abs(res.values[0] - 1)
```

`self.optim_config`는 **config 객체**이고 위쪽 같은 함수에서 `self.optim_config.report_type` ·
`self.optim_config.report_factor`로 속성 접근한다. 곧 `self.optim_config == "min"`은 **항상 거짓**이고
`"max"`도 항상 거짓이므로, 최소화/최대화 의도가 **조용히 `abs(x − 1)` 분기로 흐른다.**
(바로 위 주석 처리된 줄 `# res = res.values[0] if self.optim_config.optim_type == 'min' else ...`이
원래 의도를 보여준다 — `.optim_type`을 봐야 했다.)

★★★ **이것이 도입 판단에 주는 정보는 코드 품질이 아니라 수명이다.** qlib은 HPO 프레임워크를
붙였고, 실행 경로(`estimator`)와 기록 백엔드(`sacred`)가 아래에서 바뀌자 **아무도 눈치채지
못한 채 죽었다.** 게이트가 없어서 죽은 것을 몰랐다는 점에서
[`training-gates.md`](training-gates.md) §3.2 *"검증 코드가 원리상 실패 불가일 수 있다"* 와 같은
형태다. **이 저장소가 Optuna를 붙이면 같은 종류의 두 번째 사례가 될 후보가 하나 늘어난다.**
그리고 §2.3이 보여주듯 **Optuna 쪽 MLflow 연결부는 이미 deprecated이므로 그 붕괴가 예정돼 있다.**

### 1.3 튜닝이 고치지 않는 것 — 분할 경계의 겹침 누수

`workflow_config_alpha158_lgb_sp500.yaml`의 라벨과 분할:

```
label:    [["Ref($close, -6)/Ref($close, -1) - 1"], ["LABEL0"]]
segments: train: [2015-01-02, 2021-06-30]
          valid: [2021-07-01, 2022-12-31]
          test:  [2023-01-01, 2026-07-16]
```

라벨이 t+1→t+6 수익률이므로 **train 마지막 며칠의 라벨은 valid 구간 가격을 본다.** 경계 갭이
0이므로 purge도 embargo도 없다(§3.3). 규모는 작다 — 1600영업일 남짓 중 5일이니 0.3% 수준이다.
그러나 방향이 중요하다: **valid는 early stopping과 후보 선택을 동시에 맡고 있고, 그 valid가
train과 살짝 붙어 있다.** 시행을 늘리는 것은 이 접합부와 valid 잡음에 대한 적합을 늘리는 일이다.

★ **곧 탐색 자동화는 "더 잘 찾기"이지 "덜 속기"가 아니다.** 순서가 있다면 경계 갭이 먼저다.
sklearn에 이미 도구가 있다 — `TimeSeriesSplit(n_splits, *, max_train_size, test_size, gap)`의
`gap` docstring이 *"Number of samples to exclude from the end of each train set before the test
set."* 다(설치본 1.7.2 확인). **Optuna와 무관하게 지금 쓸 수 있는 것이다.**

---

## 2. Optuna가 실제로 제공하는 것

> 아래는 스크래치패드 임시 venv(`optuna 4.9.0` · `optuna-integration 4.9.0` · Python 3.9)에서
> **직접 introspect하고 실제로 study를 돌려** 받아 적은 것이다. 이 저장소 `.venv`(Python 3.10.13,
> `mlflow 3.14.0`)는 **읽기만 했다.** ⚠️ 임시 venv의 mlflow는 3.1.4로 해결됐으므로,
> **MLflow 쪽 호환은 이 저장소 설치본 3.14.0에서 별도로 확인**했다(§2.3 끝).

### 2.1 ★★ Study / Trial 데이터 모델 — trial이 일급이다

```
optuna.create_study(*, storage=None, sampler=None, pruner=None, study_name=None,
                    direction=None, load_if_exists=False, directions=None) -> Study
optuna.load_study(*, study_name, storage, sampler=None, pruner=None) -> Study
```

`Study`의 공개 표면: `add_trial · add_trials · ask · best_params · best_trial · best_trials ·
best_value · direction(s) · enqueue_trial · get_trials · metric_names · optimize · set_metric_names ·
set_user_attr · stop · system_attrs · tell · trials · trials_dataframe · user_attrs`.

`TrialState`는 **5개**이고 docstring이 각각을 정의한다:

| state | 값 | docstring |
|---|---:|---|
| `RUNNING` | 0 | *"The Trial is running."* |
| `COMPLETE` | 1 | *"The Trial has been finished without any error."* |
| `PRUNED` | 2 | *"The Trial has been pruned with `optuna.exceptions.TrialPruned`."* |
| `FAIL` | 3 | *"The Trial has failed due to an uncaught error."* |
| `WAITING` | 4 | *"The Trial is waiting and unfinished."* |

`trials_dataframe`의 기본 컬럼은 시그니처에 그대로 있다:

```
Study.trials_dataframe(attrs=('number','value','datetime_start','datetime_complete',
                              'duration','params','user_attrs','system_attrs','state'),
                       multi_index=False)
```

**실제로 돌려 본 반환 형태** (15 trial, MedianPruner, `set_user_attr("candidate_name", ...)` 사용):

```
['number','value','datetime_start','datetime_complete','duration',
 'params_kind','params_num_leaves','params_x','user_attrs_candidate_name','state']
```

★ **`params_*` 와 `user_attrs_*` 가 열로 펼쳐진다.** 곧 `tune_hyperparams.py`가 지금 잃는 것
(후보 이름 ↔ 곡선 대응, [`trial-accounting.md`](trial-accounting.md) §1.1.1)은 Optuna 데이터
모델에서는 **원리상 잃을 수 없다.** 이것은 실제 이득이므로 정직하게 적어 둔다.

⚠️⚠️ **그런데 `state`를 안 보면 표가 거짓말을 한다.** 위 15 trial의 상태 분포는
`{'PRUNED': 10, 'COMPLETE': 5}`였고, **`PRUNED` 행에도 `value`가 채워져 있다.**
예: trial 3 → `state=PRUNED`, `value=4.162933667463691`, `intermediate_values={0: 4.162933667463691}`.
곧 **끊긴 trial의 `value`는 목적함수 값이 아니라 마지막 중간값**이다. `FAIL` 행은 다르다 —
`value=None`(DataFrame에서 `NaN`)이고 params는 남는다. §4.4가 이 비대칭을 다룬다.

### 2.2 영속 저장과 재개 — 여기는 깨끗하다

```
optuna.storages.RDBStorage(url, engine_kwargs=None, skip_compatibility_check=False, *,
    heartbeat_interval=None, grace_period=None, heartbeat_stale_trial_callback=None,
    failed_trial_callback=None, skip_table_creation=False)
optuna.storages.JournalStorage(log_storage: BaseJournalBackend)
optuna.storages.journal.JournalFileBackend(file_path, lock_obj=None)
```

`storage="sqlite:///study.db"` 문자열을 그대로 받는다. 만들어진 SQLite 파일의 테이블(실측):

```
alembic_version · studies · study_directions · study_system_attributes · study_user_attributes ·
trial_heartbeats · trial_intermediate_values · trial_params · trial_system_attributes ·
trial_user_attributes · trial_values · trials · version_info
```

`alembic_version`은 `v3.2.0.a`였다. 곧 **스키마 마이그레이션 체계를 갖춘 관계형 원장**이다.

`JournalStorage` docstring은 설계 의도를 밝힌다 — *"Journal storage writes a record of every
operation to the database as it is executed and at the same time, keeps a latest snapshot of the
database in-memory. If the database crashes for any reason, the storage can re-establish the
contents in memory by replaying the operations stored from the beginning."*

**재개 의미론 (실측).** 15 trial을 돌린 뒤 **프로세스를 끝내고** 새 프로세스에서
`optuna.load_study(study_name="s1", storage=DB)` 후 3 trial을 더 돌렸다:

```
resumed, existing trials: 15   last number: 14
after resume: 18               numbers: [14, 15, 16, 17]
states: {'PRUNED': 10, 'COMPLETE': 5, 'FAIL': 3}
```

★ **번호가 이어진다.** 그리고 `Study.get_trials(deepcopy=True, states=None)`로 상태 필터가 되므로
`get_trials(states=(TrialState.COMPLETE,))`는 5를, `len(study.trials)`는 18을 준다.
**"누적 시행 수"라는 질문에 이 원장은 두 개의 답을 갖고 있다** — 이것 자체가 나쁜 것은 아니지만
N을 세는 규칙이 어느 쪽을 뜻하는지 문서에 못박아야 한다(§7).

### 2.3 ★★★ MLflow 연동 — 여기가 함정이다. 이미 deprecated다

**import 경로는 세 가지가 다 살아 있다**(실측). 실제 클래스는 하나다:

```
optuna_integration.MLflowCallback        -> optuna_integration.mlflow.mlflow.MLflowCallback
optuna_integration.mlflow.MLflowCallback -> (같음)
optuna.integration.MLflowCallback        -> (같음, 하위호환 shortcut)
```

시그니처:

```
MLflowCallback(tracking_uri=None, metric_name='value', create_experiment=True,
               mlflow_kwargs=None, tag_study_user_attrs=False, tag_trial_user_attrs=True)
```

**★★★ 그런데 클래스에 `@deprecated_class("4.9.0", "6.0.0")`이 붙어 있다.** 인스턴스를 만들면
`FutureWarning`이 실제로 발화한다(실측, 원문 그대로):

> `MLflowCallback has been deprecated in v4.9.0. This feature will be removed in v6.0.0. See https://github.com/optuna/optuna/releases/tag/v4.9.0.`

**릴리스 노트 원문**(GitHub API `repos/optuna/optuna/releases/tags/v4.9.0`의 `body`를 받아 grep,
published 2026-06-01):

> ### Deprecate Several Features
>
> The following features are deprecated in v4.9.0 and scheduled for removal in v6.0.0.
> …
> **optuna-integration**
>
> * `PyCmaSampler`: Please use Optuna's native `CmaEsSampler` instead.
> * `CometCallback`: This feature will be migrated to OptunaHub in the future.
> * **`MLflowCallback`: This feature will be migrated to OptunaHub in the future.**
> * `TensorBoardCallback`: This feature will be migrated to OptunaHub in the future.
> * `TrackioCallback`: This feature will be migrated to OptunaHub in the future.
> * `WeightsAndBiasesCallback`: This class has already been migrated to OptunaHub.

그리고 같은 노트의 `optuna` 항목:

> * **`optuna.integration` module**
>     * The `optuna.integration` module currently acts as a shortcut to the external
>       `optuna_integration` package for backward compatibility. Please import directly from the
>       `optuna_integration` package going forward.

⚠️⚠️ **"will be migrated"와 "has already been migrated"의 차이가 결정적이다.** OptunaHub
레지스트리 `optuna/optunahub-registry`의 `package/callbacks/` 내용을 GitHub API로 확인했다:

```
['terminator', 'trackio', 'wandb']
```

★★★ **`wandb`는 있고 `mlflow`는 없다.** 곧 **W&B 쪽은 이사가 끝났고 MLflow 쪽은 이사 갈 곳이
아직 만들어지지 않았다.** 지금 `MLflowCallback`을 쓰기 시작하면 **후속 경로가 존재하지 않는 API에
의존하는 것**이고, 이 저장소는 이미 같은 종류의 사고를 겪었다 —
[`training-gates.md`](training-gates.md) §4.1의 *"`mlflow.evaluate()`에 baseline 비교가 있다"* 가
MLflow 2.18.0에서 이름이 바뀌어 `TypeError`가 나는 그 항목이다. **이번은 이름이 바뀌는 것이 아니라
사라지는 것이다.**

**콜백이 실제로 무엇을 기록하는가** (`__call__`·`_set_tags` 소스 확인):

- `mlflow.start_run(run_id=..., experiment_id=..., run_name=str(trial.number), nested=..., tags=...)`
  로 **trial마다 런 하나**를 연다. `run_name`은 기본값이 trial 번호 문자열이다.
- metric: `_log_metrics(trial.values)` → `mlflow.log_metrics({metric_name: value})`.
  ★ **`values is None`이면 즉시 `return`한다** — 곧 `FAIL` trial은 **MLflow에 metric이 하나도
  안 남는다.**
- tag: `number`·`datetime_start`·`datetime_complete`·`direction`·`{param}_distribution`, 그리고
  **`if trial.state.is_finished(): tags["state"] = trial.state.name`**.
  ★ **끝나지 않은 trial(=`RUNNING`)은 `state` 태그가 아예 없다.** §2.6의 크래시 시나리오가
  MLflow 쪽에서 침묵하는 경로다.
- `tag_trial_user_attrs=True`가 기본이므로 `trial.set_user_attr("candidate_name", ...)`이
  MLflow 태그로 넘어간다. **`tune_hyperparams.py`가 원하는 것이 정확히 이것이다.**
- ⚠️ 인자 이력 함정 하나가 docstring에 명시돼 있다 — *"`nest_trials` argument added in v2.3.0 is a
  part of `mlflow_kwargs` since v3.0.0. Anyone using `nest_trials=True` should migrate to
  `mlflow_kwargs={"nested": True}` to avoid raising `TypeError`."* 곧 **인터넷 예제 대부분이
  `TypeError`를 낸다.**

**호환성은 오늘 기준 문제없다** — 콜백이 부르는 MLflow API를 뽑아
이 저장소 설치본 `mlflow 3.14.0`에서 전부 확인했다: `set_tracking_uri` · `get_tracking_uri` ·
`set_experiment` · `start_run` · `log_metrics` · `log_params` · `set_tags` 존재,
`mlflow.utils.validation.MAX_TAG_VAL_LENGTH = 8000` 존재. **곧 "지금은 돌아간다. 다만 한쪽이
사라진다고 예고했다."**

### 2.4 Pruner — 기준이 상대적이다

`optuna.pruners`의 구현체: `MedianPruner` · `PercentilePruner` · `SuccessiveHalvingPruner` ·
`HyperbandPruner` · `PatientPruner` · `ThresholdPruner` · `WilcoxonPruner` · `NopPruner`.

```
MedianPruner(n_startup_trials=5, n_warmup_steps=0, interval_steps=1, *, n_min_trials=1)
```

docstring 원문:

> Prune if the trial's best intermediate result is worse than median of intermediate results of
> previous trials at the same step. It stops unpromising trials early based on the intermediate
> results compared against the median of previous completed trials.
>
> The pruner handles NaN values in the following manner:
>   1. If all intermediate values of the current trial are NaN, the trial will be pruned.
>   2. During the median calculation across completed trials, NaN values are ignored.

★★★ **비교 대상이 "previous trials"다.** 이것이 §4.4의 판정 근거 전부다.

**절대 기준을 걸 수 있는 pruner는 따로 있다:**

```
ThresholdPruner(lower=None, upper=None, n_warmup_steps=0, interval_steps=1)
```

docstring: *"Prune if a metric exceeds upper threshold, falls behind lower threshold or reaches
`nan`."* → **`NULL_MSE = 3.46**2 / 12`를 `upper`로 넣으면 "null보다 나쁘면 끊는다"가 된다.**
[`training-gates.md`](training-gates.md) §1.2의 상수 0.99763이 그대로 임계가 되고, 같은 문서
§6-2가 "게이트 A는 상수 하나로 끝난다"고 쓴 것이 여기서 그대로 성립한다.

```
PatientPruner(wrapped_pruner, patience, min_delta=0.0)
```

docstring: *"This pruner monitors intermediate values in a trial and prunes the trial if the
improvement in the intermediate values after a patience period is less than a threshold."*
→ [`training-gates.md`](training-gates.md) §2.3의 게이트 C(전 구간 개선폭 임계 미만)와 같은 축이다.

⚠️ **그러나 pruner는 "게이트"가 아니라 "예산 절약기"다.** 끊긴 trial은 실패로 보고되지 않고
`PRUNED` 상태로 정상 종료한다. `study.optimize`는 예외를 올리지 않고, best_trial 선정은 계속된다.
게이트는 `sys.exit(1)`이 필요하다(이 저장소 `_gates()` 규약). **둘은 다른 물건이다**(§4.4).

### 2.5 Sampler — 기본은 TPE, 시드는 있다

`optuna.create_study()`의 기본 sampler를 실제로 확인했다 → **`TPESampler`**.

```
TPESampler(*, consider_prior=None, prior_weight=None, consider_magic_clip=None,
    consider_endpoints=None, n_startup_trials=10, n_ei_candidates=24, gamma=None, weights=None,
    seed=None, multivariate=False, group=False, warn_independent_sampling=None,
    constant_liar=False, constraints_func=None, categorical_distance_func=None)
```

`seed` 인자가 있다. ⚠️ 단 v4.9.0 릴리스 노트가 `prior_weight`·`consider_magic_clip`·
`consider_endpoints`·`gamma`·`weights` 등 **여러 인자를 deprecated로 표시**했으므로
(§2.3의 같은 목록), TPE 세부 튜닝에 의존하는 코드는 수명이 짧다.

★★ **이 저장소 규율과 맞는 sampler는 TPE가 아니다.** 두 개가 따로 있다:

```
GridSampler(search_space: Mapping[str, Sequence[GridValueType]], seed=None)
BruteForceSampler(seed=None, avoid_premature_stop=False)
```

`GridSampler` docstring: *"Sampler that performs exhaustive search over the define-and-run
user-specified grids. With `GridSampler`, the trials suggest all combinations of parameters in the
given search space during the study."* 그리고 Note: *"`GridSampler` automatically stops the
optimization if all combinations in the passed `search_space` have already been evaluated,
internally invoking the `Study.stop` method."*

★★★ **이 둘만이 "N을 사전에 알 수 있는" sampler다.** `microcap-insider-prereg.md` §4가 하는 일이
정확히 그것이다 — **N=14를 표로 열거해 고정**한다. TPE는 적응적이므로 study를 시작하는 시점에
몇 번 돌 것인지가 `n_trials` 인자로만 정해지고, **탐색 경로는 앞선 결과의 함수**다. 곧
**사전등록 체제와 TPE는 원리상 어긋난다** — 세는 규칙을 사전에 쓸 수 없다.

### 2.6 ★★ 무음 크래시는 `RUNNING`으로 굳는다 (실측)

trial 안에서 `os.kill(os.getpid(), signal.SIGKILL)`을 호출해 프로세스를 죽이고, 별 프로세스에서
같은 study를 다시 열었다:

```
trials: [(0, 'RUNNING', None, {'x': 0.9887844665603179})]
len(study.trials) = 1   |   COMPLETE only = 0
```

★ **params는 저장됐고 state는 영구히 `RUNNING`이다.** 이 저장소는 macOS에서 torch↔lightgbm
OpenMP 충돌로 **무음 크래시를 겪는 이력**이 있고(`OMP_NUM_THREADS=1`이 그 대응이다), GRU 계열
trial은 정확히 이 상태를 남긴다.

**복구 수단이 없지는 않다** — `RDBStorage(heartbeat_interval=..., grace_period=...,
failed_trial_callback=...)`와 `optuna.storages.fail_stale_trials`가 있다(exports 확인).
⚠️ 그러나 **기본값이 `None`이므로 아무 설정 없이 쓰면 위 상태가 그대로 쌓인다.** 그리고 §2.3에서
본 대로 **MLflow 태그 쪽은 `state`를 아예 안 남긴다**(`is_finished()`가 거짓이므로).
곧 두 원장이 **같은 시행에 대해 서로 다른 침묵**을 한다.

---

## 3. 문헌 — 금융 시계열에서 탐색을 늘리는 것에 대해

### 3.1 ★★★ Arnott · Harvey · Markowitz — "10개 튜닝은 terrible idea"

> Arnott, R., Harvey, C.R., & Markowitz, H. (2019). "A Backtesting Protocol in the Era of Machine
> Learning." *The Journal of Financial Data Science*, 1(1), Winter 2019, 64–74.
> DOI [10.3905/jfds.2019.1.064](https://doi.org/10.3905/jfds.2019.1.064) ·
> [PDF (Harvey 배포본, Duke)](https://people.duke.edu/~charvey/Research/Published_Papers/P138_A_backtesting_protocol.pdf)
> 서지사항은 Crossref로 교차검증했고(권호·면수·저자 일치), PDF 쪽번호 헤더가
> `64 A Backtesting Protocol in the Era of Machine Learning Winter 2019`로 시작해 면수도 맞는다.
> 인용은 전부 이 PDF에서 텍스트를 추출한 것이다.

**서론의 문제 설정** — 데이터가 많은 분야와 금융을 가른다:

> In investment finance, apart from tick data, the data are much more limited in scope. Indeed, most
> equity-based strategies that purport to provide excess returns to a passive benchmark rely on
> monthly and quarterly data. **In this case, cross-validation does not alleviate the curse of
> dimensionality.** As a noted researcher remarked to one of us:
>
> > **[T]uning 10 different hyperparameters using k-fold cross-validation is a terrible idea if you
> > are trying to predict returns with 50 years of data (it might be okay if you had millions of
> > years of data). It is always necessary to impose structure, perhaps arbitrary structure, on the
> > problem you are trying to solve.**

★★★ **이것이 이 문서 전체에서 가장 직접적인 진술이다.** 그리고 이 저장소의 조건은 인용문보다
훨씬 나쁘다 — **50년이 아니라 3.52년(183주)이고**
([`trial-accounting.md`](trial-accounting.md) §1.4), 정규화 파라미터만 세어도 후보 축이 7개다(§1.1).
⚠️ 정직한 한계: 인용문은 **익명 연구자의 발언**이고 저자 3인의 직접 진술이 아니다. 저자들이
동의하는 문맥에 넣었지만, "AHM이 그렇게 말했다"가 아니라 "AHM이 그렇게 인용했다"로 써야 맞다.

**§CATEGORY #2: MULTIPLE TESTING AND STATISTICAL METHODS**의 세 항목이 이 저장소 원장 설계에
그대로 들어온다.

**(a) `Keep Track of What Is Tried`** — 원문:

> Given 20 randomly selected strategies, one strategy will likely exceed the two-sigma threshold
> (t-statistic of 2.0 or above) purely by chance. As a result, the t-statistic of 2.0 is not a
> meaningful benchmark if more than one strategy is tested. **Keeping track of the number of
> strategies tried is crucial, as is measuring their correlations** (Harvey 2017; López de Prado
> 2018). A bigger penalty in terms of threshold is applied to strategies that are relatively
> uncorrelated. For example, if the 20 strategies tested had a near 1.0 correlation, then the
> process is equivalent to trying only one strategy.

★ 마지막 문장이 [`trial-accounting.md`](trial-accounting.md) §7.3의 `N̂ = ρ̂ + (1−ρ̂)·M` 변환을
**독립적으로 같은 말로** 표현한다. 상관이 1이면 실효 시행이 1이다.

**(b) `Keep Track of Combinations of Variables`** — 원문:

> Suppose the researcher starts with 20 variables and experiments with some interactions, say
> (variable 1 × variable 2) and (variable 1 × variable 3). **This single interaction does not
> translate into only 22 tests (the original 20, plus two additional interactions) but into 190
> possible interactions.** Any declared significance should take the full range of interactions into
> account.

★★★ **이것이 Optuna 도입 판단에 직접 걸린다.** 저자들의 셈법은 **"실행한 것"이 아니라
"탐색 공간에 들어 있던 것"을 센다.** 곧 `suggest_int("num_leaves", 16, 256, log=True)` 한 줄은
`n_trials`가 몇이든 **그보다 큰 공간을 선언한 것**이고, 이 논문의 규칙대로면 신고할 N은
실행 수보다 크다. ⚠️ 단 저자들이 "격자 크기를 N으로 쓰라"고 명문화한 것은 아니다 —
*"should take the full range of interactions into account"* 까지다. 그리고
[`trial-accounting.md`](trial-accounting.md) §3이 MinBTL 논문의 `2⁵ = 32` 계산법에 대해
*"격자를 전부 탐색하지 않았으면 N은 격자 크기가 아니다"* 라고 판단한 것과 **긴장 관계에 있다.**
§4.1에서 이 긴장을 해소하지 않고 그대로 남긴다.

**(c) `Beware the Parallel Universe Problem`** — 원문:

> Another way to think about this is to suppose that (in a single universe) the researcher compiles
> a list of 20 variables to test for predictive ability. The first one "works." **The researcher
> stops and claims to have done a single test. True, but the outcome may be lucky.** Think of another
> researcher with the same 20 variables who tests in a different order, and only the last variable
> "works." In this case, a discovery at two sigma would be discarded because a two-sigma threshold
> is too low for 20 different tests.

★★★ **이것이 "Optuna study 1회는 N에 1인가"에 문헌이 주는 가장 강한 반대 근거다.** 유도탐색은
정의상 "좋은 것을 만나면 그쪽으로 더 뽑는" 절차이므로, **조기에 좋은 trial을 만나 멈춘 study는
위 인용문의 "The first one works. The researcher stops"와 구조가 같다.** §4.1에서 쓴다.

**§CATEGORY #3의 두 항목이 이 저장소 사전등록과 정면으로 대응한다.**

> **Select Winsorization Level before Constructing the Model** … the choice to winsorize, and at
> which level, should be decided before constructing the model. **An obvious sign of a faulty
> research process is a model that "works" at a winsorization level of 5% but fails at 1%, and the
> 5% level is then chosen.**

> **Do Not Arbitrarily Exclude Outliers** … Ideally, a solid economic case should be made for
> exclusion—before the model is estimated. In general, no influential observations should be deleted.

⚠️★ **이 두 항목은 [`trial-accounting.md`](trial-accounting.md) §7.4의 판정을 부분적으로 갱신한다.**
그 표는 `microcap-insider-prereg.md` §4.1의 *"이상치 규칙 변경은 재작성"* 항목에 대해
**"문헌에 대응물 없음"** 이라고 적었다. **규범 자체에는 대응물이 있다** — AHM이 "모델 구성 전에
정하라"와 "5%에서 되고 1%에서 안 되는데 5%를 고르면 결함"을 명문으로 쓴다. 다만
**"바꾸면 N+1인가 재작성인가"라는 회계 규칙은 여전히 문헌에 없다.** 곧 정정 범위는
"규범 근거 있음 / 회계 규칙 없음"이고, 사전등록 §4.1의 결론(재작성)은 그대로 유효하다.
⚠️ **선행 문서를 고치지 않았다.** 상호 링크와 정정은 사람이 판단할 몫으로 남긴다.

**§CATEGORY #6의 한 항목**은 [`training-gates.md`](training-gates.md) §3.1(ML Test Score Model 5)의
금융판이다:

> **Pursue Simplicity and Regularization** … It might be the case that a machine learning model
> decides that a linear regression is the best model. If, however, a more elaborate machine learning
> model beats the linear regression model, **it had better win by an economically significant amount
> before the switch to a more complex model is justified.**

★ 곧 *"단순 모델을 이겨야 한다"* 에 **"경제적으로 유의한 폭으로"** 라는 조건이 추가된다.
[`training-gates.md`](training-gates.md) §5가 *"게이트 임계값의 문헌 근거를 못 찾음"* 으로 남긴
칸에 대해, **이 문장은 "부호로는 부족하다"까지는 말한다**(구체적 임계는 여전히 안 준다).

✅ **모델 비의존**: 7개 카테고리 전부 모델 클래스를 언급하지 않는다. `CATEGORY #6`이 복잡도를
다루지만 특정 학습기가 아니라 차원 수를 본다.

### 3.2 ★★ Gu · Kelly · Xiu — 왜 k-fold CV를 쓰지 않는지 명시한다

> Gu, S., Kelly, B., & Xiu, D. (2020). "Empirical Asset Pricing via Machine Learning."
> *The Review of Financial Studies*, 33(5), 2223–2274.
> DOI [10.1093/rfs/hhaa009](https://doi.org/10.1093/rfs/hhaa009) ·
> [PDF (Xiu 배포본, Chicago Booth)](https://dachxiu.chicagobooth.edu/download/ML.pdf)
> 내려받은 PDF는 **RFS 조판본**이다(쪽 헤더 `The Review of Financial Studies / v 33 n 5 2020`,
> 본문 시작 2223). ⚠️ Crossref는 면수를 `2223-2273`으로, PDF 헤더는 `2223–2274`로 준다.
> **한 쪽 차이는 확정하지 못했다**(§6).

**§1.1 Sample splitting and tuning via validation** — 이 저장소 yaml의 `segments`와 같은 구조다:

> We follow the most common approach in the literature and select tuning parameters adaptively from
> the data in a validation sample. In particular, **we divide our sample into three disjoint time
> periods that maintain the temporal ordering of the data.** The first, or "training," subsample is
> used to estimate the model subject to a specific set of tuning parameter values.
>
> The second, or "validation," sample is used for tuning the hyperparameters. … **The validation
> sample fits are of course not truly out of sample, because they are used for tuning, which is in
> turn an input to the estimation.** Thus, the third, or "testing," subsample, which is used for
> neither estimation nor tuning, is truly out of sample …

그리고 각주 32 — 한 문장이 전부다:

> **We do not use cross-validation to maintain the temporal ordering of the data.**

★★★ **이것이 §5.2에서 `GridSearchCV`/`RandomizedSearchCV`를 배제하는 문헌 근거다.** 실증
자산가격 문헌의 표준 참조가 **k-fold를 쓰지 않고 시간 순서를 지키는 3분할**을 택했다고 명시한다.
그리고 **qlib의 `segments: train/valid/test`가 정확히 그 구조**다 — 곧 이 저장소는 이미 맞게
하고 있고, sklearn 탐색 클래스를 붙이는 것이 오히려 후퇴다.

**★ 그리고 R²의 크기 감각을 준다** — [`training-gates.md`](training-gates.md) §1.2가 계산한
`R²_oos`를 어디에 놓고 봐야 하는지의 외부 기준선이다. 원문:

> The OLS model using all 920 features produces an R²_oos of **−3.46%**, indicating it is **handily
> dominated by applying a naive forecast of zero to all stocks in all months.**

> … restricting OLS to a sparse parameterization … generates a substantial improvement over the full
> OLS model (R²_oos of **0.16%** and **0.11%** respectively).

> … raise the out-of-sample R² to **0.27%** and **0.26%**, respectively. [PLS·PCR]

> Boosted trees and random forests are competitive with PCR, producing fits of **0.34%** and
> **0.33%**, respectively.

> [R²]_oos is **0.33%** for NN1 and **peaks at 0.40%** for NN3.

★★ **두 가지를 동시에 준다.** ①GKX의 최선 모델도 R²_oos가 **0.40%**다 — 곧 이 영역에서 작은
R²는 정상이다. ②그런데 이 저장소 실측은 **+0.00002 ~ +0.00056**, 즉 **0.002% ~ 0.056%** 이고
([`training-gates.md`](training-gates.md) §1.2), README `+11.9%` 행의 근거였던 GRU 4런은
**음수**다. GKX의 최선 대비 한 자리에서 두 자리 규모가 작다. 그리고 GKX가 음수 R²에 붙인 표현이
정확히 **"naive forecast of zero에 handily dominated"** 다 —
[`training-gates.md`](training-gates.md) §2.1의 게이트 A와 같은 판정어다.

⚠️ **정직한 비교 한계:** GKX는 **월간** 개별주 수익률이고 이 저장소는 **주간 5일 fwd 라벨**에
`CSRankNorm`을 거친 랭킹 타깃이다. **분모가 다르므로 숫자를 직접 나란히 놓을 수 없다.**
쓸 수 있는 것은 부호와 규모의 감각까지다.

✅ **모델 비의존**: §1.1의 3분할 규율과 각주 32는 13개 모델 전부에 공통 적용된 설계다.

### 3.3 López de Prado — purged K-fold와 embargo (⚠️ 본문 미열람)

> López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.
> ISBN 978-1-119-48208-6.
> ⚠️⚠️ **본문을 열람하지 못했다.** 유료 도서이고 접근 가능한 1차 자료는
> **ETH Zürich 도서관이 호스팅하는 원본 목차 스캔**뿐이다
> ([TOC PDF](https://toc.library.ethz.ch/objects/pdf03/e01_978-1-119-48208-6_01.pdf), 12쪽).
> 이 PDF의 첫 쪽이 `Advances in Financial Machine Learning / MARCOS LOPEZ DE PRADO / Wiley`이므로
> **표제·저자·발행사는 1차 확인**이고, 아래는 **절 제목과 면수만** 옮긴 것이다.
> **본문 문장은 하나도 인용하지 않는다.**

목차가 확인해 주는 것:

| 장·절 | 제목 | 면 |
|---|---|---:|
| **7** | **Cross-Validation in Finance** | — |
| 7.3 | Why K-Fold CV Fails in Finance | 104 |
| 7.4 | A Solution: Purged K-Fold CV | 105 |
| 7.4.1 | Purging the Training Set | 105 |
| 7.4.2 | Embargo | 107 |
| 7.4.3 | The Purged K-Fold Class | 108 |
| 7.5 | **Bugs in Sklearn's Cross-Validation** | 109 |
| **9** | **Hyper-Parameter Tuning with Cross-Validation** | — |
| 9.2 | Grid Search Cross-Validation | 129 |
| 9.3 | Randomized Search Cross-Validation | 131 |
| 9.3.1 | Log-Uniform Distribution | 132 |
| 9.4 | Scoring and Hyper-parameter Tuning | 134 |
| **12** | **Backtesting through Cross-Validation** | 161 |
| 12.4 | The Combinatorial Purged Cross-Validation Method | 163 |

★★ **목차만으로도 도입 판단에 쓸 수 있는 사실이 세 개 나온다.**

1. **금융 ML의 표준 참조서가 HPO에 장 하나를 배정했는데, 그 방법이 `Grid Search` ·
   `Randomized Search`다.** 베이지안 최적화·TPE·Optuna에 해당하는 절이 목차에 없다.
   곧 **이 계열 문헌의 처방은 "탐색 알고리즘을 똑똑하게"가 아니라 "CV를 purge하라"** 다.
   ⚠️ 이는 목차의 부재로부터 추론한 것이므로 **"저자가 베이지안 최적화를 반대한다"는 주장이
   아니다.** 다루지 않았다는 사실까지다.
2. **§7.5가 `Bugs in Sklearn's Cross-Validation`이다.** sklearn CV를 그대로 신뢰하지 말라는
   신호가 절 제목 수준에 있다 — §5.2의 판단과 방향이 같다.
3. **§7.4.1/§7.4.2가 §1.3의 경계 누수에 이름을 준다** — purging(훈련셋에서 라벨이 겹치는 관측을
   제거)과 embargo(테스트 뒤에 간격을 둔다). 이 저장소 config의 경계 갭은 0이다.

⚠️ **[`trial-accounting.md`](trial-accounting.md)가 인용한 PBO/DSR/MinBTL 논문들은 같은 저자군의
1차 출처로 이미 확보돼 있다.** 여기서 그 인용을 반복하지 않는다. §4.1·§4.4에서 그 문서의 §4.4와
§7.2를 절 번호로 참조한다.

---

## 4. 도입 판단 — 다섯 질문에 대한 답

### 4.1 Optuna study 1회는 DSR의 N에 몇으로 들어가는가

**답: 문헌 미해결이다. 그리고 이 저장소가 고를 수 있는 보수적 선택지는 셋뿐이며, 어느 것을
골라도 도입 근거가 서지 않는다.**

**문헌 상태 (찾은 것 전부):**

| 진술 | 출처 | 무엇에 대한 것인가 |
|---|---|---|
| *"the columns of matrix M should be the final outcome of each guided search … and not the intermediate steps"* | PBO §5.2 ([`trial-accounting.md`](trial-accounting.md) §4.4·§7.2 인용) | ⚠️ **CSCV 행렬 M의 열 정의.** DSR의 N이 아니다 |
| *"we need to use judgment on an important input—the number of tests"* | Harvey & Liu ([`trial-accounting.md`](trial-accounting.md) §7.1) | **명시적 위임** |
| *"The researcher stops and claims to have done a single test. True, but the outcome may be lucky."* | AHM §Parallel Universe (§3.1) | **"1로 세면 안 된다"의 근거** |
| *"20 variables … does not translate into only 22 tests but into 190 possible interactions"* | AHM §Combinations (§3.1) | **탐색 공간을 세라는 방향** |

★★★ **곧 DSR의 N에 대한 직접 진술은 없고, 유도탐색을 "1"로 접으라는 진술은 CSCV 쪽에만 있다.**
그리고 **AHM의 두 항목은 반대 방향으로 압력을 준다.** 문헌은 이 질문에 답하지 않는다.

**보수적 선택지 세 개** (전부 이 저장소의 결정이며 문헌 인용이 아니다):

| 선택지 | N | 장점 | 문제 |
|---|---|---|---|
| **(a) trial 전부** | `len(study.trials)` | 세는 규칙이 자명. 은폐 불가 | `PRUNED`·`RUNNING`이 섞인다(§2.1·§2.6). PBO §5.2의 *"trials that are doomed to fail"* 금지 조항과 충돌(§4.4) |
| **(b) `COMPLETE`만** | `get_trials(states=(COMPLETE,))` | doomed-to-fail 조항과 정합 | **pruner가 N을 줄이는 손잡이가 된다** — 끊는 기준을 조이면 N이 내려가고 DSR이 올라간다. 이것이 PBO §5.2의 *"when a measure becomes a target"* 그 자체다 |
| **(c) 수렴결과 1** | 1 | CSCV M 열 정의와 정합 | **DSR에 그대로 쓰면 안 된다**(두 통계량의 N이 다름). 그리고 AHM parallel universe가 정면 반대 |

⚠️ **(a)와 (b) 어느 쪽에도 `N̂ = ρ̂ + (1−ρ̂)·M` 변환을 먼저 적용할 수 있다.** 그런데 그 변환은
**손익 계열이 있는 시행끼리만 상관을 계산할 수 있다.** `tune_hyperparams.py` 계열은 백테스트를
안 돌리므로 손익 계열이 없다([`trial-accounting.md`](trial-accounting.md) §1.1의 `Experiment`
7런이 정확히 그 상태다). 곧 **Optuna로 늘린 시행은 N에는 들어가고 ρ̂ 추정에는 못 들어간다** —
[`trial-accounting.md`](trial-accounting.md) §1.4가 *"실측 N̂ 4.86은 아래로 편향된 값"* 이라고
쓴 그 편향을 **키우는 방향**이다.

**★★ 그래서 숫자로 확인했다.** [`trial-accounting.md`](trial-accounting.md) §1.2가 공개한 입력
(`√V[{SR}] = 0.11158`, `T = 183`, `SR̂ = 0.13052`, `γ̂₃ = +0.097`, `γ̂₄ = 3.331`)으로 DSR을
**독립 구현**해 그 문서의 표를 먼저 재현했다:

| N | 내 구현 `SR₀` | 내 구현 DSR | [`trial-accounting.md`](trial-accounting.md) §1.2 |
|---:|---:|---:|---:|
| 1 | 0.00000 | **0.9611** | 0.9611 ✅ |
| 4.86 | 0.13114 | **0.4967** | 0.4968 ✅ |
| 9 | 0.16969 | **0.2984** | 0.2983 ✅ |
| 19 | 0.20955 | **0.1428** | 0.1428 ✅ |
| 23 | 0.21887 | **0.1163** | 0.1163 ✅ |

(0.13114 vs 0.13111의 차이는 `√V`를 5자리로 받아 쓴 반올림이다. `E[{SR̂ₙ}]` 항은 그 문서와 같이
0으로 두었고, 그렇게 해야 `N=4.86 → SR₀=0.1311`이 정확히 재현된다.)

**재현이 됐으므로 Optuna 규모로 확장한다:**

| 시나리오 | N | **DSR** |
|---|---:|---:|
| 지금 (`mlruns/` 전체) | 23 | 0.1163 |
| `tune_hyperparams.py` 후보 6개를 trial로 분리 | 29 | **0.0900** |
| 소규모 study 1회 (`n_trials=50`) 누적 | ~73 | (표 밖, 단조 감소) |
| 통상적 study 1회 (`n_trials=200`) | 200 | **0.0081** |
| 위 + 기존 23런 | 223 | **0.0070** |

★★★ **N=200이면 DSR 0.0081이다.** 관례 기각선 0.95는 물론이고 **0.05조차 못 넘는다.** 그리고
이 계산의 `SR̂ = 0.13052`는 **지금까지 나온 최선값**이므로, 새 study가 그보다 나은 값을 못 찾으면
DSR은 더 내려간다. **곧 "trial을 200번 돌려서 이긴다"는 경로는 산술적으로 닫혀 있다** —
`SR₀`가 N과 함께 올라가므로, 시행을 늘려 얻는 최선값 개선이 임계값 상승을 앞질러야 한다.

⚠️ **MinBTL은 재현하지 못했다.** [`trial-accounting.md`](trial-accounting.md) §1.4의 **상한
열(`2·ln N`)은 정확히 재현했다**(N=9 → 4.39, N=18 → 5.78, N=19 → 5.89, N=23 → 6.27, N=45 → 7.61,
N=46 → 7.66 전부 일치). 그러나 **MinBTL 본값 열(3.44 / 3.53 / 3.85 / 5.00년)은 구현하지 않았다.**
그래서 큰 N에 대한 MinBTL 값을 **새로 인용하지 않는다.** 필요한 결론은 새 계산 없이 나온다 —
같은 문서가 **N=45 → 5.00년**을 계산해 뒀고 이 저장소가 가진 것은 3.52년이며 MinBTL은 N에 대해
단조 증가한다. **곧 N ≥ 45인 어떤 시나리오도 예산 밖이다.** Optuna study 1회는 통상 그보다 크다.

### 4.2 탐색 자동화가 이 저장소에서 지금 방향이 맞는가

**답: 아니다. 도입하지 마라.** 근거 네 개를 두 선행 문서의 실측과 나란히 놓는다.

1. ★★★ **정규화 완화가 이미 시도됐고 R²가 안 움직였다.** `tune_hyperparams.py`의 후보 6개는
   `lambda_l1`을 205.7 → 0.0까지, `lambda_l2`를 580.98 → 0.0까지 쓸었다(§1.1의 `CANDIDATES`).
   결과: **best step은 풀렸지만(0 → 117·166) R²는 그대로 null 수준**이었다
   ([`training-gates.md`](training-gates.md) §1.1·§1.2). ★ **곧 이미 정규화 전 구간을 탐색했고
   답이 없었다.** Optuna가 하는 일은 이 축을 **더 촘촘히** 보는 것이다. 촘촘함이 부족했던 게
   아니다.
2. ★★ **예산이 소진됐다.** 183주 = 3.52년, 23런 실행,
   [`trial-accounting.md`](trial-accounting.md) §1.4의 판정이 *"독립시행 18회까지가 예산인데
   23런을 돌렸다"* 다. 같은 문서가 *"N 예산을 소진했다는 사실 자체가 「새 시행보다 데이터 확장이
   먼저」라는 신호"* 라고 쓴다. **Optuna는 정확히 반대 방향의 도구다.**
3. ★★ **문헌이 명시적으로 경고한다.** §3.1의 AHM 인용 — 50년으로 10개 튜닝이 terrible idea라면
   3.52년으로는 논의 대상이 아니다. 그리고 같은 논문의 `Refrain from Tweaking the Model`이
   *"Although these modifications are a natural response to failure, we should be fully aware that
   they will generally lead to further overfitting"* 라고 쓴다.
4. ★ **애초 진단이 하이퍼파라미터가 아닐 가능성이 남아 있다.** GRU S&P500 4런은 예측이
   종목별로 전부 다르고(고유비율 1.000) 셔플 재현율 100%인데도 **R²가 음수**다
   ([`training-gates.md`](training-gates.md) §1.2·§1.3). 정규화가 문제인 형태가 아니다.
   반대로 LightGBM 베이스라인은 499종목에 고유값 35개다. **두 실패의 형태가 다르므로 공통 처방이
   "탐색을 늘린다"일 이유가 없다.**

✅ **모델 비의존**: 1~4 전부 예측 벡터·수익률 계열·표본길이만 본다.

**그럼 지금 방향은 무엇인가** — 두 선행 문서가 이미 답했다. 학습 게이트 A·B·C를 `_gates()`에
붙이고([`training-gates.md`](training-gates.md) §6-1), 시행 원장을 세우고
([`trial-accounting.md`](trial-accounting.md) §10-1), **후보마다 런을 열어 이름을 남긴다**
(같은 문서 §10-2, "최우선 착지점"). ★ **셋 다 Optuna 없이 된다.** §5.1이 그 방법이다.

### 4.3 기록 문제만 놓고 보면 MLflow 부모-자식 대비 순이득이 있는가

**답: 없다. 이득은 하나, 비용은 셋이다.**

**이득 (하나, 실재한다):** §2.1이 확인한 대로 trial이 `params`·`user_attrs`·`state`를 **일급
스키마로** 갖는다. 후보 이름을 `set_user_attr`로 넣으면 `trials_dataframe()`에
`user_attrs_candidate_name` 열로 나온다. `tune_hyperparams.py`가 잃는 것이 정확히 이것이다.
**그러나 이건 MLflow 태그로도 되는 일이다** — `mlflow.set_tags({"candidate": name})` 한 줄이고,
질의는 `mlflow.search_runs(filter_string="tags.candidate = '...'")`다
([`trial-accounting.md`](trial-accounting.md) §6.2가 이미 확인한 API).

**비용 (셋):**

1. **의존성 두 개 추가.** `optuna` + `optuna-integration`. 그리고 후자의 공개 표면
   (`MLflowCallback`·`WeightsAndBiasesCallback`)이 **둘 다 deprecated이고 v6.0.0 제거 예정**이다
   (§2.3). ★ **추가하는 순간 만료일이 붙은 의존성이 하나 생긴다.**
2. ★★★ **원장이 갈린다.** 이 저장소는 이미 두 원장을 갖는다 — `mlruns/`(백테스트)와
   설계 확정된 `ledger.db`(실집행, [`ledger.md`](../project/ledger.md)). Optuna storage를 더하면
   **셋**이고, [`ledger.md`](../project/ledger.md)가 *"대시보드는 소스가 둘이 된다 … 이는
   정상이며 섞지 않는다"* 라고 명시한 경계 원칙에 **섞지 말아야 할 세 번째**가 생긴다.
3. **MLflow 쪽 마이그레이션 부채와 겹친다.** `mlflow 3.14.0`은 파일 백엔드를 유지보수 모드로
   넣었고([`training-gates.md`](training-gates.md) §4.1), 권장 경로는
   `mlflow migrate-filestore --target sqlite:///…`인데 **빈 DB만 받는 일회성**이다
   ([`trial-accounting.md`](trial-accounting.md) §6.1). 곧 원장을 정비하는 작업이 이미 대기 중이고,
   그 위에 별도 SQLite를 하나 더 얹는 순서는 뒤집혀 있다.

**★★ N 집계가 구체적으로 어떻게 깨지는가 — 네 경로.**

| 경로 | 무엇이 일어나나 | 결과 |
|---|---|---|
| **(i) 크래시** | trial이 `RUNNING`으로 굳고(§2.6), MLflow 태그에는 `state`가 아예 안 붙는다(§2.3의 `is_finished()` 분기) | Optuna는 "시행 있음, 결과 없음", MLflow는 "런 있음, 상태 없음". **어느 쪽도 N을 못 확정한다** |
| **(ii) FAIL** | Optuna에 params 남고 `value=None`. `_log_metrics`가 `values is None`에서 즉시 return하므로 **MLflow에 metric 0개** | `mlruns/`만 보면 실패 시행이 "지표 없는 런"으로 보인다 — [`trial-accounting.md`](trial-accounting.md) §1.1의 `Experiment` 7런과 **구별 불가** |
| **(iii) PRUNED** | Optuna에 `value`(=마지막 중간값)가 남고 MLflow에도 그 값이 metric으로 남는다 | ★ **"끊긴 시행"이 "값을 낸 시행"처럼 보인다.** state를 안 보면 N이 부풀고, PBO §5.2의 doomed-to-fail 조항 위반 |
| **(iv) 재실행** | Optuna는 `load_if_exists`면 번호를 잇고, 새 study 이름이면 1부터 시작 | **study 이름 규약이 N의 정의가 된다.** 규약을 어디에도 안 적으면 N이 사람마다 다르다 |

★ **(iv)가 가장 조용하다.** `create_study(study_name=...)`을 매번 새 이름으로 부르면 각 study의
`len(trials)`는 작고, 합계를 내는 코드는 아무도 안 쓴다. 결과는
[`trial-accounting.md`](trial-accounting.md) §1.1.1과 **같은 형태의 소실** — 도구만 바뀐다.

### 4.4 Pruner가 학습 게이트를 대체하는가

**답: 대체하지 못한다. 그리고 위험하게 상호작용한다.**

**대체 못 하는 이유 — 비교 대상이 다르다.**

| | [`training-gates.md`](training-gates.md) 게이트 A | `MedianPruner` |
|---|---|---|
| 비교 상대 | **상수 예측(null 모델)**. MSE 0.99763이라는 **데이터 무관 상수** | **다른 trial들의 같은 step 중간값** |
| 전 trial이 똑같이 나쁘면 | **전부 실패** | **절반이 통과** |
| 실패 시 동작 | `sys.exit(1)` (승격 차단) | `PRUNED`로 정상 종료, best_trial 선정 계속 |

★★★ **두 번째 행이 판정이다.** [`training-gates.md`](training-gates.md) §1.1의 실측 —
19런 중 12런이 step 0 최선, 나머지도 개선폭 0.004~0.074% — 는 **모든 후보가 균일하게 학습 실패한
분포**다. 그 분포에 `MedianPruner`를 걸면 **중앙값이 곧 null 수준이 되므로 절반이 "유망"으로
통과한다.** 게이트가 잡아야 하는 그 상황에서 pruner는 침묵한다.

⚠️ **`ThresholdPruner(upper=NULL_MSE)`는 다르다** — 절대 기준이므로 게이트 A와 **같은 축**이다
(§2.4). 그러나 그 경우 임계값은 `3.46**2/12`이고, **이 상수만 있으면 Optuna 없이도 게이트를 짤 수
있다.** [`training-gates.md`](training-gates.md) §6-2가 *"게이트 A는 상수 하나로 끝난다"* 고 쓴
그대로다. **곧 유용한 pruner는 Optuna를 도입할 이유가 아니라, Optuna 없이 이미 할 수 있는 일의
재확인이다.**

**★★ 위험한 상호작용 — 끊긴 trial이 N에 들어가는가.**

실측으로 정리한다(§2.1·§2.2):

- `PRUNED` trial은 `study.trials`에 **들어간다.** `len(study.trials)`가 센다.
- `PRUNED` trial의 `value`는 **채워져 있다**(마지막 중간값). `trials_dataframe()`에 정상 행.
- `get_trials(states=(COMPLETE,))`로 세면 **빠진다.**

곧 **N은 pruner 설정의 함수다.** 그리고 여기서 [`trial-accounting.md`](trial-accounting.md) §7.2가
인용한 PBO §5.2의 두 조항과 만난다:

> Likewise, **adding trials that are doomed to fail in order to make one particular model
> configuration succeed biases the result.** If a model configuration is obviously flawed, it should
> have never been tried in the first place.

**두 방향 다 문제가 된다:**

- **`PRUNED`를 N에 넣으면** — pruner가 끊은 것은 정의상 "유망하지 않은" 시행이므로,
  위 조항이 말하는 *"trials that are doomed to fail"* 에 가깝다. 넣으면 조항 위반 방향이다.
  ⚠️ 다만 조항의 취지는 **의도적으로 쓰레기를 추가하는 것**을 금하는 것이고, pruner가 끊은
  trial은 의도가 아니라 결과다. **문헌이 이 경우를 다루지 않는다.**
- **`PRUNED`를 N에서 빼면** — ★★★ **pruner 설정이 N을 낮추는 손잡이가 된다.**
  `n_startup_trials`·`n_warmup_steps`를 조이면 `PRUNED`가 늘고 `COMPLETE`가 줄어 N이 내려간다.
  N이 내려가면 `SR₀`가 내려가고 **DSR이 올라간다**(§4.1의 표에서 N 23 → 9면 DSR 0.1163 → 0.2984).
  곧 **보정 통계량을 좋게 만드는 설정 손잡이가 생긴다.** 이것이 PBO §5.2의
  *"when a measure becomes a target, it ceases to be a good measure"* 그 자체다.

★ 그리고 [`trial-accounting.md`](trial-accounting.md) §2.3이 식에서 유도한
*"중복 시행이 DSR을 부풀린다"* 와 **같은 종류의 함정이 하나 더 늘어나는 것**이다.
그 문서가 `study-pitfalls.md` §2.7로 넣으라고 권한 항목의 형제다.

**결론:** pruner는 **계산 예산 절약기**로만 분류한다. 게이트 자리에 놓지 않는다. 그리고
`PRUNED`/`FAIL`/`RUNNING`을 N에 어떻게 넣을지의 규칙이 **먼저 문서화되지 않으면 도입 자체가
새 자유도를 만든다.**

### 4.5 Optuna를 옵티마이저 없이 원장으로만 쓰는 것이 합리적인가

**답: 부자연스럽다는 판단이 맞다. 반박이 아니라 확인이다.** 이유 네 개.

1. ★★ **sampler를 비활성화하는 공식 경로가 없다.** `create_study(sampler=...)`는 sampler를 요구하고
   기본은 `TPESampler`다(§2.5). `ask`/`tell` API로 파라미터를 직접 넣을 수는 있지만, 그때 쓰는
   `study.tell(trial, value)`는 **여전히 study가 sampler를 갖고 있는 상태**다. 곧
   "탐색 없이 기록만"은 **설계된 사용법이 아니라 우회**다. ⚠️ `GridSampler`는 그중 가장 정직한
   선택이지만(N이 사전 확정, §2.5), `GridSampler` docstring의 Note가 *"This sampler with
   ask_and_tell raises `RuntimeError` just after evaluating the final grid"* 라고 경고한다 —
   곧 **정확히 그 조합에 알려진 함정이 있다.**
2. ★★★ **원장으로서의 스키마 이득이 이 저장소 필요보다 크다.** Optuna SQLite는 테이블 13개다
   (§2.2). 이 저장소가 필요한 것은 [`trial-accounting.md`](trial-accounting.md) §10-1이 열거한
   9개 열이다 — `시행ID · 날짜 · 커밋 · 설계축 · 판정단위 여부 · 손익계열 유무 ·
   confirmatory/exploratory · 결과 · N 누적`. ★ **이 중 Optuna 스키마가 주는 것은 앞의 두 개
   정도이고, 핵심 열 셋(`판정단위 여부` · `손익계열 유무` · `confirmatory/exploratory`)은
   `user_attrs`에 문자열로 밀어 넣어야 한다.** 그건 마크다운 표나 MLflow 태그로도 되는 일이고,
   전용 스키마를 얻는 대가로 **정작 필요한 필드는 여전히 자유 텍스트**다.
3. ★★ **`mlruns/`와의 연결부가 deprecated다**(§2.3). 원장 목적이라면 두 원장을 잇는 다리가
   필수인데, 그 다리가 유일하고 만료 예고돼 있으며 후속이 아직 없다. **원장 목적일 때 오히려
   치명적이다** — 옵티마이저로 쓸 때는 다리가 끊겨도 탐색은 돌지만, 원장으로 쓸 때는 다리가
   기능 전부다.
4. **크래시 처리가 기본값에서 열려 있다**(§2.6). 원장의 존재 이유는 "일어난 일을 빠짐없이
   남기는 것"인데, 기본 설정에서 무음 크래시가 `RUNNING`으로 굳는다. `heartbeat_interval`을
   설정해야 하고, 그건 **원장을 쓰기 위해 원장을 설정하는 일**이다.

★ **정직하게 적을 반대 근거 하나:** §2.2의 재개 의미론(번호가 이어진다)은 마크다운 원장보다
확실히 낫다 — 사람이 표에 줄을 안 적으면 마크다운은 침묵하지만, `load_study`는 자동으로 15를
16으로 만든다. **"세는 것을 사람 성실성에 맡기지 않는다"는 이득은 실재한다.**
그러나 그 이득은 §5.1의 MLflow 부모-자식 + `search_runs` 카운트로도 얻는다 —
**`mlflow.source.git.commit`이 이미 공짜로 남는다는 사실**까지 포함해서
([`trial-accounting.md`](trial-accounting.md) §1.1.1).

---

## 5. 대안·비교

### 5.1 ★★★ MLflow 부모-자식 런 — 이미 설치돼 있고, 이것으로 끝난다

`mlflow 3.14.0` 설치본 시그니처(확인):

```
mlflow.start_run(run_id=None, experiment_id=None, run_name=None, nested=False,
                 parent_run_id=None, tags=None, description=None,
                 log_system_metrics=None) -> ActiveRun
```

★ `nested`와 `parent_run_id`가 **둘 다** 있다. 자식 런 조회는
`mlflow.search_runs(filter_string="tags.mlflow.parentRunId = '<parent_run_id>'")`
([`trial-accounting.md`](trial-accounting.md) §6.2 확인).

**기록 축에서 Optuna와 무엇이 다른가:**

| 축 | MLflow 부모-자식 | Optuna storage |
|---|---|---|
| 시행 경계 | 자식 런 1개 = 시행 1회 | trial 1개 = 시행 1회 |
| 후보 이름 | `tags`/`params` (자유 스키마) | `user_attrs` (자유 스키마) |
| 상태 | ⚠️ **런 상태 3종**(`RUNNING`/`FINISHED`/`FAILED`) — `PRUNED` 개념 없음 | **5종**, `PRUNED` 별도 |
| 누적 카운터 | ⚠️ **없음.** `search_runs` 행 수를 세야 함 | ✅ `trial.number`가 자동 증가 |
| 커밋 | ✅ **`mlflow.source.git.commit` 자동** | ❌ 직접 `user_attr`로 넣어야 함 |
| 손익 계열 아티팩트 | ✅ 런 아티팩트에 `report_normal_*.pkl` | ❌ 아티팩트 개념 없음 — **DSR/PBO 입력을 담을 곳이 없다** |
| 의존성 | **0 (이미 설치)** | +2, 그중 연결부 deprecated |

★★★ **마지막에서 두 번째 행이 결정적이다.** [`trial-accounting.md`](trial-accounting.md) §1.1이
확립한 것은 *"손익 계열을 남기지 않은 12런은 DSR·PBO의 입력이 될 수 없는데도 N에는 들어가야
한다"* 이고, §10-2가 *"후보마다 `report_normal_*.pkl`을 남긴다. 없으면 그 시행은 **영구히**
보정 통계량 밖이다"* 라고 쓴다. **Optuna storage에는 아티팩트를 담을 자리가 없다.**
곧 Optuna를 원장으로 쓰면 **이 저장소가 겪은 소실을 구조적으로 반복한다.**

✅ **모델 비의존**: 런 구조는 모델을 안 본다.

### 5.2 sklearn `GridSearchCV` / `RandomizedSearchCV` — 이 저장소에는 못 붙는다

설치본 `scikit-learn 1.7.2` 확인:

```
GridSearchCV(estimator, param_grid, *, scoring=None, n_jobs=None, refit=True, cv=None,
             verbose=0, pre_dispatch='2*n_jobs', error_score=nan, return_train_score=False)
```

**못 붙는 이유 세 개, 무게 순.**

1. ★★★ **estimator 계약이 다르다.** 설치본 시그니처:
   `LGBModel.fit(self, dataset: qlib.data.dataset.DatasetH, num_boost_round=None,
   early_stopping_rounds=None, verbose_eval=20, evals_result=None, reweighter=None, **kwargs)`.
   **`(X, y)`를 받지 않는다.** `qlib.model.base.Model`의 공개 표면도 `fit`/`predict`뿐이고
   `get_params`/`set_params`가 없으므로 **sklearn estimator 규약을 만족하지 않는다.**
   `GridSearchCV`는 `clone(estimator)`를 하므로 `get_params`가 필수다. 곧 어댑터를 새로 써야 한다.
2. ★★ **`cv` 기본값이 시간 순서를 깬다.** docstring: *"None, to use the default 5-fold cross
   validation"* 이고 *"In all other cases, `KFold` is used. These splitters are instantiated with
   `shuffle=False`"*. ⚠️ **`shuffle=False`라 무작위 섞기는 아니지만**, k-fold는 정의상
   **테스트 폴드 뒤의 데이터가 훈련에 들어간다.** §3.2의 GKX 각주 32(*"We do not use
   cross-validation to maintain the temporal ordering of the data"*)가 배제하는 그것이고,
   §3.3의 AFML §7.3 절 제목(`Why K-Fold CV Fails in Finance`)이 가리키는 그것이다.
   그리고 이 저장소 라벨은 t+1→t+6이므로 **폴드 경계마다 겹침 누수가 생긴다**(§1.3).
3. **억지로 되지만 그러면 남는 게 없다.** `cv` docstring이 *"An iterable yielding (train, test)
   splits as arrays of indices"* 를 허용하고 `PredefinedSplit(test_fold)`도 있다(확인).
   곧 qlib의 `segments`를 인덱스 배열로 바꿔 **단일 분할**을 물릴 수 있다. 그러면
   `cv_results_`는 `param_*` 열 + `split0_test_score` + `rank_test_score`가 되어
   ★ **후보 표 하나로 퇴화한다** — `tune_hyperparams.py`가 이미 만드는
   `res = pd.DataFrame(rows, columns=["cand","valid_IC","valid_RankIC","valid_ICIR","best_iter"])`
   와 같은 물건이고, 오히려 IC·RankIC·ICIR 세 지표를 잃는다(`scoring` 하나만 순위를 정한다).

★ **다만 `TimeSeriesSplit(..., gap=N)`은 별개로 유용하다**(§1.3). 탐색 프레임워크가 아니라
분할기이고, 이 저장소가 지금 갖고 있지 않은 것(경계 embargo)을 준다.

⚠️ **모델 비의존 아님**: 1번 근거는 qlib `Model` 계약에 묶인다. 모델을 바꿔도 qlib을 쓰는 한 같다.

### 5.3 Ray Tune · Hyperopt · W&B Sweeps — 한 문단씩

**Ray Tune.** 공식 문서 제목이 `Ray Tune: Hyperparameter Tuning`이고, Ray 사이트 내비게이션이
스스로를 *"Ray Tune — Scale hyperparameter tuning"* 이라 소개한다
([docs.ray.io/en/latest/tune](https://docs.ray.io/en/latest/tune/index.html), 접속일 2026-08-18,
페이지 HTML을 받아 문자열로 확인). ★ **핵심어가 `Scale`이다.** 곧 이 도구가 해결하는 문제는
"많은 trial을 여러 머신에 뿌리는 것"이고, 이 저장소는 **1인·단일 M1 맥·23런**이다.
게다가 §4.1이 보여주듯 **trial을 늘리는 것이 문제를 악화시키는 방향**이므로, 늘리는 능력을
확장하는 도구는 순서가 거꾸로다. 미설치이고, 설치하지 않는다.

**Hyperopt.** 이 저장소에서 특별한 위치에 있다 — **qlib이 이미 이것으로 HPO를 구현했고 그 코드가
죽어 있다**(§1.2). 곧 Hyperopt 도입은 "새 도구 추가"가 아니라 "이미 있는 죽은 경로 되살리기"이고,
되살리려면 `estimator` CLI(존재하지 않음)와 `sacred` 결과 디렉터리(폐기됨)를 다시 만들어야 한다.
★ **`qlib/contrib/tuner/`를 고치는 비용이 처음부터 쓰는 비용보다 크다.** 그리고 §4.2에 따르면
어느 쪽도 하지 않는 것이 맞다.

**W&B Sweeps.** `wandb`는 미설치다. 그리고 §2.3에서 확인한 대로 **Optuna 쪽 W&B 연결부
(`WeightsAndBiasesCallback`)는 이미 OptunaHub로 이사했고**(레지스트리 `package/callbacks/wandb`
존재) **`optuna-integration` 쪽은 deprecated다.** 더 중요한 것은 성격이다 — W&B는 SaaS 백엔드가
기본이므로, 이 저장소의 원장을 **로컬 파일/SQLite로 유지한다는 결정**
([`ledger.md`](../project/ledger.md)의 *"RDB 서버(Postgres 등)·Docker는 이 규모에 과설계다"*)과
방향이 다르다. 백테스트 지표에 계좌값은 없지만, 원장을 외부로 내보내는 판단은 별건이므로
**공개 판단이 필요한 축이 하나 늘어난다.** 채택하지 않는다.

---

## 6. 확인 실패 / 미검증

| 대상 | 상태 | 대체 / 비고 |
|---|---|---|
| **AFML(2018) 본문** — Ch 7 purged K-fold·embargo, Ch 9 HPO | ⚠️ **미열람** (유료 도서) | ETH Zürich 도서관 호스팅 **원본 목차 스캔**으로 표제·저자·발행사·절 제목·면수만 확인. **본문 문장은 인용하지 않았다.** §3.3의 세 추론은 목차 근거임을 명시했다 |
| **López de Prado, "The 10 Reasons Most Machine Learning Funds Fail"** (SSRN 3104816) | **확인 실패** — SSRN Delivery.cfm HTTP 403 | 서지사항만 Crossref로 검증(DOI 10.2139/ssrn.3104816, 저자 Lopez de Prado, 2018). **본문을 인용하지 않았다** |
| **GKX 게재본 면수** | ⚠️ **불일치** | Crossref `2223-2273` vs PDF 쪽 헤더 `2223–2274`. **한 쪽 차이를 확정 못 했다.** §3.2는 PDF 헤더 표기를 따랐다 |
| **AHM의 "10 hyperparameters" 인용문의 원 발화자** | **확인 불가 (원문이 익명)** | 논문 원문이 *"As a noted researcher remarked to one of us"* 로만 쓴다. **"AHM이 말했다"로 인용하면 틀린다** |
| **OptunaHub 웹 UI**(`hub.optuna.org`)에 mlflow 패키지가 있는지 | **확인 실패** — JS SPA, 본문 미렌더(9KB, `mlflow` 0건) | **GitHub API로 대체 확보** — `optuna/optunahub-registry` 의 `package/callbacks/` = `['terminator','trackio','wandb']`. **mlflow 없음** |
| **MLflowCallback introspect 환경** | ⚠️ **버전 불일치** | 임시 venv가 Python 3.9 → `mlflow 3.1.4`로 해결됐다(이 저장소는 3.10.13 / 3.14.0). **콜백이 호출하는 MLflow API 7개 + `MAX_TAG_VAL_LENGTH`는 이 저장소 3.14.0에서 별도 확인**했으므로 호환 결론은 유효. 다만 **3.14.0 + optuna-integration 조합을 실제로 실행하지는 않았다** |
| **`optuna` 실제 학습 파이프라인 연동** | **미실시** | study는 합성 목적함수로만 돌렸다. `LGBModel.fit`을 objective 안에서 실행해 보지 않았다 — 판정이 "도입 반대"이므로 **의도적으로 하지 않았다** |
| **MinBTL 본값 재현** | **미구현** | [`trial-accounting.md`](trial-accounting.md) §1.4의 **상한 열 `2·ln N`은 6개 값 전부 재현**(4.39/5.78/5.89/6.27/7.61/7.66). **MinBTL 본값 열은 구현하지 않았고, 큰 N에 대한 MinBTL 값을 새로 인용하지 않았다**(§4.1) |
| **DSR 재현** | ✅ **성공** | §1.2의 5개 값을 소수 4자리까지 일치(§4.1 표). 확장값 N=29/50/100/200/223은 같은 구현 산출 |
| **`probe_models.py`·`probe_label_horizon.py` 상세** | 미조사 | 이 문서는 `tune_hyperparams.py`만 대체 대상으로 봤다. 세 스크립트의 시행 경계 문제는 [`trial-accounting.md`](trial-accounting.md) §1.1.1이 이미 다룬다 |
| **`qlib/contrib/tuner/` 버그의 상류 보고 여부** | 미조사 | `optim_config == "min"` 문자열 비교(§1.2)가 상류 qlib에 보고됐는지 확인하지 않았다. **이 저장소는 이 코드를 쓰지 않으므로 조치 대상 아님** |
| **`GridSampler` + `ask/tell` RuntimeError** | **미재현** | docstring의 Note로만 확인했다(§4.5). 실제로 발생시키지 않았다 |
| **`JournalStorage` 실사용** | **미실시** | 시그니처와 docstring만 확인. `RDBStorage`(SQLite)만 실제로 돌렸다 |
| **`fail_stale_trials` / heartbeat 동작** | **미검증** | exports에 존재하는 것만 확인했고, 크래시 후 실제로 `FAIL`로 전환되는지 돌려보지 않았다(§2.6) |

⚠️ **조사 방법 경고 (선행 두 문서 §5·§9와 같은 종류, 이번에도 발생했다).**
Optuna v4.9.0 릴리스 노트를 웹 페이지 요약 도구로 먼저 받았을 때, **deprecation 항목을
그럴듯하게 재구성해** 돌려주었다 — PR 번호와 문장 형태가 실제와 달랐다. 그래서 §2.3의 인용은
**GitHub API로 `body` 문자열을 받아 직접 grep한 것**이다. `MLflowCallback` deprecation은
**세 경로로 독립 확인**했다: ①클래스 데코레이터 `@deprecated_class("4.9.0", "6.0.0")` 소스
②인스턴스 생성 시 실제 발화한 `FutureWarning` 문자열 ③릴리스 노트 `body` 원문.
**요약본을 원문 확인으로 세지 말 것.**

★ 그리고 **"설치해서 introspect했다"가 "이 저장소에서 돌려봤다"는 아니다.** §2의 모든 실측은
합성 목적함수 기준이다. 학습 파이프라인 안에서의 동작은 **미검증**이며, 판정이 반대이므로
검증하지 않았다.

---

## 7. 이 저장소 착지점

착지점만 지목한다. 코드는 쓰지 않는다. **결론이 도입 반대이므로, 선행 문서가 PBO에 대해 쓴 방식
([`trial-accounting.md`](trial-accounting.md) §10-6, *"붙일 조건을 원장에 조건문으로 적어 둔다"*)을
그대로 따른다.**

1. ★★★ **원장에 조건문 3개를 쓴다. 셋이 동시에 참일 때만 재검토한다.**
   ([`trial-accounting.md`](trial-accounting.md) §10-1이 신설할 `docs/project/trial-ledger.md`의
   한 절로. 그 문서는 아직 없다 — `docs/project/ledger.md`는 실집행 원장이라 별건이다.)

   > **조건 A (학습):** `_gates()`에 게이트 A(null 대비 R²)가 붙어 있고, **어떤 설정이든
   > `R²_oos > 0`을 한 번이라도 통과한 이력이 원장에 있을 때.**
   > 근거: 지금은 정규화 전 구간에서 R²가 null 위로 안 올라갔다
   > ([`training-gates.md`](training-gates.md) §1.2). **탐색으로 찾을 것이 있다는 증거가 먼저다.**
   >
   > **조건 B (예산):** **표본이 늘어 MinBTL 예산이 남아 있을 때.**
   > 지금은 183주(3.52년)에 23런으로 예산 근처~초과다
   > ([`trial-accounting.md`](trial-accounting.md) §1.4). 같은 문서가 N=45 → 5.00년으로 계산했고,
   > MinBTL은 N에 단조 증가하므로 **study 1회 규모(≥45)를 감당하려면 최소 5년 이상**이 필요하다.
   >
   > **조건 C (도구):** **`MLflowCallback`의 후속이 OptunaHub에 실재할 때.**
   > 지금은 deprecated이고 후속이 없다(§2.3). 확인 방법까지 적어 둔다 —
   > `optuna/optunahub-registry` 의 `package/callbacks/` 에 `mlflow`가 있는가.

   ⚠️ **조건 A·B가 참이어도 C가 거짓이면 도입하지 않는다** — 기록이 끊기면 시행이 원장 밖으로
   나가고, 그건 이 저장소가 이미 한 번 겪은 손실이다.
   ✅ **모델 비의존**: 세 조건 전부 모델 클래스를 안 본다.

2. ★★★ **대신 [`trial-accounting.md`](trial-accounting.md) §10-2를 그대로 실행한다 — 부모-자식
   런.** 이 문서의 §5.1이 확인한 것: `mlflow.start_run(..., nested=True, parent_run_id=...)`이
   설치본에 있고, `mlflow.source.git.commit`은 공짜이고, **아티팩트를 담을 자리가 있다**(Optuna에는
   없다). ★ **곧 §10-2는 새 의존성 없이 지금 할 수 있고, Optuna로 하면 더 나빠지는 항목이다.**
   ✅ **모델 비의존.**

3. ★★ **`tune_hyperparams.py`의 `CANDIDATES`는 손으로 적힌 상태로 남긴다 — 이것이 기능이다.**
   §2.5가 확인한 대로 **N을 사전에 알 수 있는 sampler는 `GridSampler`·`BruteForceSampler`뿐**이고,
   기본 `TPESampler`는 적응적이라 탐색 경로가 앞선 결과의 함수다. `microcap-insider-prereg.md`
   §4가 **N=14를 표로 열거해 고정**하는 방식과 TPE는 원리상 어긋난다.
   → **원장 문서에 한 줄로 남길 것: "후보는 열거한다. 적응적 sampler는 세는 규칙을 사전에 쓸 수
   없으므로 사전등록 체제와 어긋난다."**
   ✅ **모델 비의존.**

4. ★★ **`ThresholdPruner`가 아니라 `NULL_MSE` 상수를 가져온다.** §2.4가 확인한
   `ThresholdPruner(upper=...)`의 절대 기준은 유용하지만, 그 유용함의 실체는 **임계 상수
   `3.46**2/12`** 이고 그건 [`training-gates.md`](training-gates.md) §6-2가 이미 지목한 것이다.
   → **`_gates()`의 게이트 A로 넣는다. Optuna는 필요 없다.**
   ⚠️ **`MedianPruner`류를 게이트로 쓰지 말라는 근거를 `study-pitfalls.md`에 한 항목으로 남긴다** —
   비교 대상이 다른 trial의 중앙값이므로 **전 후보가 균일하게 실패한 분포에서는 절반이 통과한다**
   (§4.4). 이 저장소 19런이 정확히 그 분포였다.
   ✅ **모델 비의존** (단 pruning 자체는 반복학습기 전용 —
   [`training-gates.md`](training-gates.md) §2.3의 게이트 C와 같은 제약).

5. ★★ **분할 경계에 embargo를 넣는 것을 탐색보다 먼저 놓는다.** 지금 config는
   train `…2021-06-30` / valid `2021-07-01…`으로 갭 0이고 라벨이 t+1→t+6이다(§1.3).
   sklearn `TimeSeriesSplit(..., gap=N)`의 `gap`이 *"Number of samples to exclude from the end of
   each train set before the test set"* 다(설치본 확인). qlib `segments`를 쓰는 이 저장소에서는
   **yaml에서 train 종료일을 6영업일 앞으로 당기는 것으로 끝난다.**
   → ⚠️ **이건 판정을 바꿀 수 있는 변경이므로 시행 1회로 계상해야 한다.**
   `microcap-insider-prereg.md` §4.1의 "세는 것" 규칙 대상이다.
   ✅ **모델 비의존.**

6. ★ **`qlib/contrib/tuner/`를 "쓰지 않는다"고 명시해 둔다.** 설치본에 HPO 모듈이 있으므로,
   나중에 누군가(사람이든 에이전트든) 발견하고 되살리려 할 수 있다. §1.2의 세 가지 이유
   (`hyperopt` 미설치 · `estimator` CLI 부재 · `sacred` 경로)와 `optim_config == "min"` 버그를
   **한 줄 근거로 남긴다.** 상류에 보고하지 않는다 — 이 저장소가 쓰지 않는 코드다.
   ✅ **모델 비의존.**

7. ★ **README 성능 표에 `N` 열을 넣을 때 "세는 규칙"을 각주로 붙인다.**
   [`trial-accounting.md`](trial-accounting.md) §10-3이 `N`·`DSR` 열을 권했다. 여기에 더할 것 —
   §4.3의 (iv) 경로가 보여주듯 **`N`은 정의를 안 적으면 사람마다 다른 값이 된다.**
   `mlruns/` 전체인가, 손익 계열이 있는 런인가, 판정 단위인가.
   → **표 각주에 "N = (정의)"를 한 줄로.** 지금 [`trial-accounting.md`](trial-accounting.md) §1.2가
   N을 1 / 4.86 / 9 / 19 / 23 다섯 값으로 병기한 것이 좋은 선례다.
   ✅ **모델 비의존.**

8. **§3.1이 AHM에서 새로 확보한 두 항목을 사전등록 쪽에 반영할지는 사람이 판단한다.**
   `Select Winsorization Level before Constructing the Model`과 `Do Not Arbitrarily Exclude
   Outliers`는 `microcap-insider-prereg.md` §4.1의 winsor 규칙에 **규범 근거**를 준다.
   ⚠️ 그러나 [`trial-accounting.md`](trial-accounting.md) §7.4의 표는 그 항목을 *"문헌에 대응물
   없음"* 으로 적어 뒀다. **정확한 정정 범위는 "규범 근거 있음 / 회계 규칙(N+1인가 재작성인가)은
   여전히 없음"** 이다. 그 문서는 완성본이므로 **이 문서에서 고치지 않았다.**
   → **선행 문서를 손대는 판단과 상호 링크는 사람에게 남긴다.**
