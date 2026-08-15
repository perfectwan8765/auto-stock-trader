"""(발행사, 공시일)당 고유 내부자 수 = 클러스터 분포 측정.

작업계획서 §5 단계 1(l) · §3.14(3). 사전등록의 클러스터 정의(대안 N #8) 근거다.

★ 반드시 `RPTOWNERCIK` **고유 수**로 세어야 한다.
하나의 Form 4에 복수 reporting owner가 실릴 수 있어(공동 제출) `ACCESSION_NUMBER` 수로 세면
공동매수 내부자를 **절반 이하로 과소계상**한다 — 실측 16.3%(accession) vs 38.5%(고유 내부자).
문서가 v3.2까지 "복수 내부자는 표본의 17%뿐"이라며 이 변형을 버릴 뻔한 원인이 이 오류였다.

산출: data/cluster_events.csv (이벤트별 고유 내부자 수·공시 수·금액·주가·지연)

구조 통계만 만든다 — 수익률은 계산하지 않는다(사전등록 오염 방지, 계획서 §9 서두).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DERA = ROOT / "data" / "dera"
OUT = ROOT / "data" / "cluster_events.csv"

DEFAULT_QUARTERS = [f"20{y}q{q}" for y in (23, 24) for q in (1, 2, 3, 4)] + ["2025q1"]


def _load(q: str) -> pd.DataFrame | None:
    d = DERA / q
    if not d.is_dir():
        print(f"  {q}: 없음 — 건너뜀", flush=True)
        return None
    keep_sub = {"ACCESSION_NUMBER", "FILING_DATE", "ISSUERCIK",
                "ISSUERTRADINGSYMBOL", "AFF10B5ONE"}
    keep_tr = {"ACCESSION_NUMBER", "TRANS_CODE", "TRANS_ACQUIRED_DISP_CD",
               "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_DATE"}
    keep_own = {"ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"}
    sub = pd.read_csv(d / "SUBMISSION.tsv", sep="\t", low_memory=False,
                      usecols=lambda c: c in keep_sub)
    tr = pd.read_csv(d / "NONDERIV_TRANS.tsv", sep="\t", low_memory=False,
                     usecols=lambda c: c in keep_tr)
    own = pd.read_csv(d / "REPORTINGOWNER.tsv", sep="\t", low_memory=False,
                      usecols=lambda c: c in keep_own)
    tr = tr[(tr.TRANS_CODE == "P") & (tr.TRANS_ACQUIRED_DISP_CD == "A")]
    m = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER", how="left")
    # AFF10B5ONE은 2023년경 이후 분기에만 있다 → 없는 분기는 필터를 끈다(§3.9)
    if "AFF10B5ONE" in m.columns:
        m = m[m.AFF10B5ONE != 1]
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarters", nargs="+", default=DEFAULT_QUARTERS,
                    help="⚠️ 기본값을 대체한다 — 전 구간을 열거할 것")
    ap.add_argument("--min-amount", type=float, default=10_000)
    ap.add_argument("--min-price", type=float, default=5)
    ap.add_argument("--max-price", type=float, default=50)
    ap.add_argument("--max-lag", type=int, default=5)
    args = ap.parse_args()

    parts = [x for q in args.quarters if (x := _load(q)) is not None]
    d = pd.concat(parts, ignore_index=True)
    print(f"P&A 거래행(10b5-1 제외): {len(d):,}", flush=True)

    d["FILING_DATE"] = pd.to_datetime(d.FILING_DATE, errors="coerce", format="mixed")
    d["TRANS_DATE"] = pd.to_datetime(d.TRANS_DATE, errors="coerce", format="mixed")
    d["lag"] = (d.FILING_DATE - d.TRANS_DATE).dt.days
    d["amt"] = d.TRANS_SHARES * d.TRANS_PRICEPERSHARE

    ev = d.groupby(["ISSUERCIK", "FILING_DATE"]).agg(
        symbol=("ISSUERTRADINGSYMBOL", "first"),
        amount_usd=("amt", "sum"),
        max_price=("TRANS_PRICEPERSHARE", "max"),
        filing_lag_days=("lag", "max"),
        n_owner=("RPTOWNERCIK", "nunique"),        # ★ 고유 내부자 수
        n_accession=("ACCESSION_NUMBER", "nunique"),
    ).reset_index()

    f = ev[(ev.amount_usd >= args.min_amount) & (ev.max_price >= args.min_price)
           & (ev.max_price <= args.max_price) & (ev.filing_lag_days <= args.max_lag)]
    f.to_csv(OUT, index=False)
    print(f"이벤트(필터 후): {len(f):,}\n")

    print("=== (발행사, 공시일)당 고유 내부자 수 ===")
    vc = f.n_owner.value_counts().sort_index()
    cum = 0
    for k, v in vc.items():
        cum += v
        if k <= 4 or v / len(f) >= 0.01:
            print(f"  {k:>2}명: {v:>6} ({v / len(f):>5.1%})   누적 {cum / len(f):>5.1%}")
    print(f"\n  ★ ≥2명: {(f.n_owner >= 2).sum():>6} (**{(f.n_owner >= 2).mean():.1%}**)  ← 클러스터 정의")
    print(f"    ≥3명: {(f.n_owner >= 3).sum():>6} ({(f.n_owner >= 3).mean():.1%})  ← 검정력 미달 예상")
    print(f"\n  (참고) accession ≥2건: {(f.n_accession >= 2).sum():>6} "
          f"({(f.n_accession >= 2).mean():.1%}) — **이 값으로 세면 안 된다**")
    print(f"\n[완료] {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
