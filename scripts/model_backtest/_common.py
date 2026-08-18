"""model_backtest 공통: config 로딩·qlib.init 준비.

live 스크립트(run_backtest·generate_signal)가 공유. `import qlib`보다 위에서 import 할 것
(MLFLOW 환경변수를 qlib 로드 전 설정).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

# 신버전 mlflow는 파일스토어 tracking 백엔드를 기본 차단 → 로컬 실험 기록에 opt-in.
# qlib import 전에 설정돼야 하므로 이 모듈 로드 시점(=qlib import 전)에 실행.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import ruamel.yaml as yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(config_arg: str) -> tuple[dict, Path]:
    """config 경로 해석(절대/상대/파일명) + YAML 파싱. (cfg, 해석된 경로) 반환."""
    p = Path(config_arg)
    if not p.is_absolute() and not p.exists():
        p = Path(__file__).with_name(config_arg)
    with p.open() as f:
        return yaml.YAML(typ="safe", pure=True).load(f), p


def qlib_init_kwargs(cfg: dict) -> tuple[dict, Path]:
    """cfg['qlib_init']의 provider_uri를 ROOT 기준 절대경로화. (qlib.init kwargs, provider_uri) 반환.

    provider_uri를 별도로 돌려줘 호출부가 qlib.init 전에 쓸 수 있게 한다
    (run_backtest는 init 전 instruments 파일 생성에 필요)."""
    kw = dict(cfg["qlib_init"])
    provider_uri = ROOT / kw["provider_uri"]
    kw["provider_uri"] = str(provider_uri)
    return kw, provider_uri


# ------------------------------------------------------- 학습 건전성 게이트 (게이트 A)

# CSRankNorm 라벨에 대한 **상수 예측의 MSE**. 이 값은 데이터가 필요 없다 —
# CSRankNorm이 `rank(pct=True) → -0.5 → ×3.46`이므로 출력 분산이 종목수·기간·시장과
# 무관하게 정해진다(3.46 = 1/std[uniform], qlib CSRankNorm docstring).
#   Var = 3.46² / 12 = 0.9976333…   (test 구간 label.pkl 실측 0.9976316)
# 곧 "아무것도 학습하지 않은 모델"의 검증손실을 미리 알 수 있고, 게이트 비용이 0이다.
NULL_MSE_CSRANKNORM = 3.46**2 / 12

# 모델별 검증지표 규약: 모델클래스 → (지표가 클수록 좋은가, 지표값 → MSE 변환).
# ★ 이 표가 있어야 하는 이유는 **부호가 모델마다 반대**라는 것이다 — LightGBM은 `l2`에
#   MSE를 그대로 담고(작을수록 좋음), qlib pytorch 모델은 metric_fn이 `-loss_fn`을 반환해
#   음수 MSE를 담는다(클수록 좋음). 최선점을 min으로 찾으면 GRU는 정확히 거꾸로 읽힌다.
#   모델을 추가할 때마다 밟을 함정이므로 규약을 여기 한 곳에 선언한다.
_VALID_METRIC = {
    "LGBModel": (False, lambda v: v),
    "GRU": (True, lambda v: -v),
}


def valid_curve(model, evals_result: dict) -> list[float]:
    """검증곡선을 **MSE 단위·작을수록 좋은 방향**으로 정규화해 돌려준다.

    모델별 부호 규약을 여기서 흡수하는 것이 요점이다 — 호출부가 min/max를 고르게 하면
    모델을 추가할 때마다 그 선택을 다시 해야 하고, 틀려도 조용히 통과한다.

    Raises:
        SystemExit: 모델 규약 미등록·곡선 없음. **추측하지 않는다.**
    """
    name = type(model).__name__
    if name not in _VALID_METRIC:
        raise SystemExit(
            f"[게이트 중단] 모델 '{name}'의 검증지표 부호 규약이 미등록이다.\n"
            f"  _common.py의 _VALID_METRIC에 (클수록 좋은가, MSE 변환)을 추가할 것.\n"
            f"  추측으로 통과시키면 부호를 거꾸로 읽어도 조용히 PASS가 된다."
        )
    _, to_mse = _VALID_METRIC[name]

    curve = evals_result.get("valid")
    if isinstance(curve, dict):  # LightGBM: 지표명으로 한 겹 더 감싼다
        if len(curve) != 1:
            raise SystemExit(f"[게이트 중단] valid 지표가 {list(curve)} — 1개여야 한다")
        curve = next(iter(curve.values()))
    if not curve:
        raise SystemExit(
            "[게이트 중단] 검증곡선이 비었다. valid 세그먼트가 있는지, "
            "model.fit(dataset, evals_result=...)로 받았는지 확인할 것."
        )
    return [to_mse(v) for v in curve]


def best_valid_mse(model, evals_result: dict) -> tuple[float, int]:
    """검증 MSE의 최선값과 그 스텝. 모델별 부호 규약을 여기서 흡수한다.

    Args:
        model: 학습이 끝난 qlib 모델 인스턴스. 클래스명으로 규약을 찾는다.
        evals_result: `model.fit(dataset, evals_result=...)`로 받은 학습곡선.
            LightGBM은 `{"valid": {"l2": [...]}}`, qlib pytorch는 `{"valid": [...]}`.

    Returns:
        (최선 검증 MSE, 그 스텝 인덱스).

    Raises:
        SystemExit: 모델 규약이 미등록이거나 곡선이 비었을 때. **추측하지 않는다** —
            부호를 잘못 읽은 게이트는 게이트가 없는 것보다 나쁘다.
    """
    curve = valid_curve(model, evals_result)
    best = min(curve)                      # 정규화 후에는 항상 작을수록 좋다
    return best, curve.index(best)


def check_learning(cfg: dict, model, evals_result: dict) -> bool:
    """학습 게이트 — 모델이 실제로 학습됐는가. 두 축을 따로 본다.

    기존 배선 게이트가 "설정이 의도대로 배선됐나"를 보는 것과 달리 이쪽은 "학습이 됐나"를
    본다. **IC로는 대체되지 않는다** — 상수 예측도 유한한 IC를 내므로 배선 게이트를 통과한다.

    두 축이 필요한 이유:

    - **A (수준)** — 검증손실이 null 기준선보다 나은가. 임계는 `R² > 0`뿐이다. 문헌은
      "null보다 나아야 한다"까지만 말하고 구체적 하한을 주지 않으므로 값을 정하면 그 자체가
      연구자 자유도가 된다. 유의성으로 올리려면 Diebold-Mariano류가 필요한데 "학습모델 vs
      상수예측"은 **중첩 모델**이라 정규근사가 성립하지 않는다(Diebold 2015). 따라서 A가
      말할 수 있는 것은 `≤ 0`이면 실패, `> 0`이면 **"실패는 아님"** 까지다.
    - **C (진행)** — 최선 스텝이 0이면 첫 반복 이후 모든 반복이 검증을 악화시켰다는 뜻이고,
      그건 학습이 진행되지 않았다는 것이다. **임계가 필요 없어** A의 자유도 문제를 겪지 않는다.
      A는 수준이 null 근처(R² ~1e-5)여도 통과하므로 이 축이 없으면 게이트가 아무것도 못 막는다.

    ⚠️ C는 반복학습기(GBDT·NN)에만 적용된다 — 선형회귀엔 학습곡선이 없다. `_VALID_METRIC`이
    미등록 모델에서 중단하므로 그 범위를 벗어나면 조용히 통과하는 일은 없다.
    """
    procs = cfg["task"]["dataset"]["kwargs"]["handler"]["kwargs"].get("learn_processors", [])
    if not any(p.get("class") == "CSRankNorm" for p in procs if isinstance(p, dict)):
        raise SystemExit(
            "[게이트 중단] learn_processors에 CSRankNorm이 없다 → NULL_MSE 상수가 성립하지 않는다.\n"
            "  라벨 정규화를 바꿨다면 null 기준선을 학습 라벨 분산으로 직접 재계산할 것."
        )

    curve = valid_curve(model, evals_result)
    mse, step = min(curve), curve.index(min(curve))
    r2 = 1 - mse / NULL_MSE_CSRANKNORM

    ok_a = r2 > 0
    print(f"   {'✅' if ok_a else '❌'} [A 수준] null 대비: R²_oos={r2:+.5f} "
          f"(검증MSE {mse:.6f} vs null {NULL_MSE_CSRANKNORM:.6f})")
    if not ok_a:
        print("      → 상수 예측보다 나쁘다. IC가 양수여도 신호가 아니라 동점 처리 결과일 수 있다.")

    ok_c = step > 0
    gain = curve[0] - mse
    print(f"   {'✅' if ok_c else '❌'} [C 진행] 최선 step={step}/{len(curve) - 1} "
          f"· 개선폭 {gain:.2e} ({gain / NULL_MSE_CSRANKNORM:+.4%})")
    if not ok_c:
        print("      → 첫 반복 이후 모든 반복이 검증을 악화시켰다 = 학습이 진행되지 않았다.")

    return ok_a and ok_c


# ------------------------------------------------------------------ 스윕 시행 경계

def sweep_id(tag: str) -> str:
    """스윕 하나를 식별하는 ID. 같은 스윕의 시행들을 나중에 묶어 세는 열쇠다."""
    from datetime import datetime
    return f"{tag}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


@contextmanager
def trial_run(experiment_name: str, sweep: str, trial: str, **params):
    """스윕의 **한 시행을 독립 런으로** 연다.

    이게 필요한 이유는 도구 기본동작이다 — recorder를 명시적으로 열지 않으면 `LGBModel.fit`이
    `R.log_metrics`를 부르는 부수효과로 런이 **한 번 생기고 그대로 재사용**된다. 그러면 후보
    n개의 검증곡선이 같은 metric 키에 step 0부터 겹쳐 쓰이고, **어느 곡선이 어느 후보인지
    사후에 복원할 수 없다.** 실제로 tune_hyperparams 6후보·probe_label_horizon 3후보가 그렇게
    1런으로 접혔다(trial-accounting.md §1.1.1).

    ⚠️ **부모-자식 런은 쓰지 않는다.** `MLflowRecorder.start_run`이 `mlflow.start_run`에
    `nested`를 넘기지 않으므로(위치인자 3개만) qlib 경로로는 중첩이 불가능하다. 대신 `sweep`
    태그로 묶는다 — 그룹핑이라는 목적은 같고 프레임워크와 싸우지 않는다.

    Args:
        experiment_name: MLflow experiment 이름. 스윕 종류별로 갈라 둘 것.
        sweep: `sweep_id()`가 만든 스윕 식별자.
        trial: 후보 이름. **이것이 남지 않으면 시행이 익명이 된다.**
        **params: 그 후보를 재현하는 데 필요한 값 전부.
    """
    from qlib.workflow import R
    with R.start(experiment_name=experiment_name, recorder_name=f"{sweep}::{trial}"):
        R.log_params(sweep_id=sweep, trial_name=trial, kind="trial", **params)
        yield R.get_recorder()


def log_selection(experiment_name: str, sweep: str, ranking, picked: str, criterion: str) -> None:
    """스윕의 **선택 자체**를 원장에 남긴다. 이게 다중검정의 실체다.

    후보 n개를 돌린 뒤 하나를 고르는 행위는 시행 n회를 소비한 선택인데, 종전에는 그 선택이
    stdout으로만 갔다 — 원장에는 "런 1개"만 남아 몇 개 중에서 골랐는지 알 수 없었다.

    선택은 시행이 아니므로 `kind="selection"`으로 갈라 둔다. 시행 카운트에 이 런을 세면
    이중계상이다(trial-ledger.md 층② 규칙).

    Args:
        ranking: 후보 이름을 선택 기준 내림차순으로 담은 순서열.
        picked: 실제로 고른 후보.
        criterion: 무엇을 기준으로 골랐는가(예: `"valid_RankIC"`).
    """
    from qlib.workflow import R
    with R.start(experiment_name=experiment_name, recorder_name=f"{sweep}::_selection"):
        R.log_params(sweep_id=sweep, kind="selection", criterion=criterion,
                     n_candidates=len(ranking), picked=picked,
                     ranking=",".join(map(str, ranking)))


# ------------------------------------------------- 게이트 B: 예측이 포트폴리오를 정하는가

_SHUFFLES = 3          # 순열 수. 연속 출력 모델은 몇 번을 섞어도 1.0이라 적어도 된다
_SHUFFLE_SEED = 2026   # 고정 — 게이트 판정이 실행마다 달라지면 안 된다


def check_prediction_shape(cfg: dict, pred, *, top_k: int | None = None) -> bool:
    """게이트 B — 예측이 top-k 포트폴리오를 **실제로 결정하는가**.

    ⚠️⚠️ **단방향 게이트다. 통과를 근거로 쓰면 안 된다.** 이 진단은 이산 출력(트리)에서만
    발화하고 연속 출력(NN·선형)에서는 원리상 절대 발화하지 않는다. 실증도 있다 — 같은 검사에서
    LightGBM은 걸리고 GRU는 100% 통과하는데, R²는 GRU가 더 나쁘다
    (`docs/research/training-gates.md` §1.3). **"걸렸으면 확실히 문제"로만 쓴다.**

    **왜 IC로 대체되지 않는가**: IC는 스케일 불변이고 동점이 만들어낸 순서에서도 값이 나온다.
    완전 상수 예측의 Pearson IC는 NaN이 아니라 부동소수점 잔차(~7e-18)이므로
    `np.isfinite(ic.mean())` 검사를 통과하고, 서로 다른 값이 3개뿐인 예측이 IC 0.033을 낸다 —
    이 저장소 베이스라인 IC 0.0121보다 크다.

    **판정**: 값은 그대로 두고 **행 순서만 섞어** top-k를 다시 뽑는다. 신호가 포트폴리오를
    결정한다면 결과가 같아야 한다. 하나라도 달라지면 그 날의 보유는 신호가 아니라 정렬 순서가
    정한 것이다. `TopkDropoutStrategy`가 `sort_values(ascending=False)`로 고르고 pandas 기본
    quicksort는 stable이 아니므로, 동점의 순서는 입력 행 순서가 정한다.

    임계가 없다는 점이 이 게이트의 장점이다 — 고유값 비율에 하한을 정하면 그게 연구자
    자유도가 되지만, "섞으면 바뀌는가"는 이산/연속을 임계 없이 가른다.

    Args:
        cfg: workflow config. `port_analysis_config.strategy.kwargs.topk`에서 k를 읽는다.
        pred: `recorder.load_object("pred.pkl")` 결과. (datetime, instrument) MultiIndex.
        top_k: k를 직접 줄 때. 생략하면 cfg에서 읽는다.

    Returns:
        통과 여부. **계산 불가면 `True`를 돌려주되 그 사실을 출력한다** — 단방향 게이트이므로
        "돌리지 못했다"는 문제의 증거가 아니다. 다만 조용히 넘기지는 않는다.
    """
    import numpy as np
    import pandas as pd

    if top_k is None:
        try:
            top_k = int(cfg["port_analysis_config"]["strategy"]["kwargs"]["topk"])
        except (KeyError, TypeError, ValueError):
            print("   ⚠️ [B 결정성] 계산 불가 — config에 strategy.kwargs.topk가 없다. "
                  "단방향 게이트라 이것이 통과 근거는 아니다.")
            return True

    s = pred.iloc[:, 0] if isinstance(pred, pd.DataFrame) else pred
    if not isinstance(s.index, pd.MultiIndex) or "datetime" not in (s.index.names or []):
        print(f"   ⚠️ [B 결정성] 계산 불가 — 예측 인덱스가 (datetime, instrument)가 아니다: "
              f"{list(s.index.names or [])}")
        return True

    rng = np.random.default_rng(_SHUFFLE_SEED)
    recalls, uniq_ratio = [], []
    for _, g in s.groupby(level="datetime"):
        if len(g) < top_k:
            continue
        uniq_ratio.append(g.nunique() / len(g))
        base = set(g.sort_values(ascending=False).head(top_k).index.get_level_values("instrument"))
        worst = 1.0
        for _ in range(_SHUFFLES):
            shuffled = g.iloc[rng.permutation(len(g))]   # 값 불변, 행 순서만 교체
            got = set(shuffled.sort_values(ascending=False)
                      .head(top_k).index.get_level_values("instrument"))
            worst = min(worst, len(base & got) / top_k)
        recalls.append(worst)

    if not recalls:
        print(f"   ⚠️ [B 결정성] 계산 불가 — top{top_k}를 뽑을 수 있는 날이 없다.")
        return True

    r, u = pd.Series(recalls), pd.Series(uniq_ratio)
    ok = r.min() >= 1.0
    print(f"   {'✅' if ok else '❌'} [B 결정성] top{top_k} 재현율 "
          f"중앙 {r.median():.3f} · 최소 {r.min():.3f} · 100%인 날 {(r == 1).mean():.1%} "
          f"(고유값비율 중앙 {u.median():.3f}, {len(r)}일)")
    if not ok:
        n_bad = int((r < 1).sum())
        print(f"      → 거래일 {n_bad}일({n_bad / len(r):.1%})에서 보유가 바뀐다. 그 날의 top{top_k}는 "
              f"신호가 아니라 **입력 행 순서**가 정했다. 초과수익·IR은 그만큼 추첨 결과다.")
    else:
        print("      (참고: 이 게이트는 연속 출력 모델에서 원리상 발화하지 않는다. 통과 근거로 쓰지 말 것.)")
    return ok
