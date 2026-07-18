"""Phase 3 A1+ — 라벨 horizon valid 프로브 (주간 vs 격주 vs 월간).

②·A1 결론: 주간(5일 fwd) 신호가 노이즈급(valid RankIC ~0.005, Vadim 블로그와 동급).
웹 리서치 시사: 비용이 지배 + 긴 horizon이 신호대잡음↑ 가능. 여기선 **라벨 horizon만** 바꿔
valid IC/RankIC가 개선되는지 본다. 모델은 A1의 안전 후보(med_reg) 고정.

⚠️ 규율: test 미관측(②서 1회 봄). valid 지표로만 판정. 백테스트/PortAnaRecord 없음.
   회전율·비용 이득(월간 리밸)은 별개(백테스트 사안) — 여기선 순수 '신호 예측력'만 비교.

실행:  .venv/bin/python scripts/model_backtest/probe_label_horizon.py [--config <yaml>]
"""
from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path

os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import pandas as pd
import ruamel.yaml as yaml

import qlib
from qlib.contrib.model.gbdt import LGBModel
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP
from qlib.utils import init_instance_by_config

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = "workflow_config_alpha158_lgb_sp500.yaml"

# fwd h거래일 라벨: Ref($close, -(h+1))/Ref($close,-1)-1
HORIZONS = {"weekly_5d": 5, "biweekly_10d": 10, "monthly_21d": 21}

# A1 안전 후보(med_reg): 정규화 있음, valid 거의 최상. 무정규화 very_light보다 일반화 안전.
MODEL = dict(loss="mse", num_threads=8, seed=2026, early_stopping_rounds=50, num_boost_round=1000,
             num_leaves=128, max_depth=8, learning_rate=0.02,
             lambda_l1=10.0, lambda_l2=50.0, colsample_bytree=0.8, subsample=0.8)


def _load_config(path: Path) -> dict:
    with path.open() as f:
        return yaml.YAML(typ="safe", pure=True).load(f)


def calc_valid_ic(pred: pd.Series, label: pd.Series) -> tuple[float, float, float]:
    df = pd.concat([pred.rename("pred"), label.rename("label")], axis=1).dropna()
    g = df.groupby(level="datetime")
    ic = g.apply(lambda x: x["pred"].corr(x["label"]))
    ric = g.apply(lambda x: x["pred"].corr(x["label"], method="spearman"))
    return ic.mean(), ric.mean(), ic.mean() / ic.std()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    args = ap.parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute() and not cfg_path.exists():
        cfg_path = Path(__file__).with_name(args.config)
    cfg = _load_config(cfg_path)

    init_kwargs = dict(cfg["qlib_init"])
    init_kwargs["provider_uri"] = str(ROOT / init_kwargs["provider_uri"])
    qlib.init(**init_kwargs)

    rows = []
    for name, h in HORIZONS.items():
        ds_cfg = copy.deepcopy(cfg["task"]["dataset"])
        ds_cfg["kwargs"]["handler"]["kwargs"]["label"] = [[f"Ref($close, -{h + 1})/Ref($close, -1) - 1"], ["LABEL0"]]
        print(f"🔧 {name}: dataset 빌드 (fwd {h}일)...")
        dataset: DatasetH = init_instance_by_config(ds_cfg)
        label = dataset.prepare("valid", col_set="label", data_key=DataHandlerLP.DK_R).iloc[:, 0]

        model = LGBModel(**MODEL)
        model.fit(dataset)
        pred = model.predict(dataset, segment="valid")
        ic, ric, icir = calc_valid_ic(pred, label)
        rows.append((name, h, ic, ric, icir, model.model.best_iteration))
        print(f"   {name:14s} IC={ic:+.4f} RankIC={ric:+.4f} ICIR={icir:+.3f} best_iter={model.model.best_iteration}")

    res = pd.DataFrame(rows, columns=["horizon", "fwd_days", "valid_IC", "valid_RankIC", "valid_ICIR", "best_iter"])
    print("\n" + "=" * 60 + "\nhorizon별 valid 신호 (test 미관측)\n" + "=" * 60)
    print(res.to_string(index=False))
    base = res[res.horizon == "weekly_5d"]["valid_RankIC"].iloc[0]
    best = res.sort_values("valid_RankIC", ascending=False).iloc[0]
    lift = (best["valid_RankIC"] - base) / abs(base) if base else float("nan")
    print(f"\n👉 최고 horizon: {best['horizon']} (RankIC={best['valid_RankIC']:+.4f}), 주간대비 {lift:+.0%}")
    print("   유의미↑(예: RankIC>0.015 & 주간대비 큰 개선)면 월간 전략 grilling 가치.")
    print("   여전히 노이즈급이면 신호원에 여지 없음 → 배관(Phase 5 mock)+Phase 0 실측 대기로 전환.")


if __name__ == "__main__":
    main()
