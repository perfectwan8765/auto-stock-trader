"""Edge v2 단계 0: 마이크로캡 후보 티커 생성 → universe/microcap_candidates.txt

SEC DERA "Insider Transactions Data Sets"(Form 3/4/5 파싱본)에서 내부자 **공개시장 매수**
이벤트를 뽑아, 그 발행사를 마이크로캡 후보 유니버스로 삼는다.

왜 DERA인가: EDGAR XML 직접 파싱은 5.8M건(~6.7일)인데 DERA는 분기 zip 46개(몇 분)로 끝난다.
왜 코드 P만인가: 취득 코드 중 A(보상)·M(옵션행사)는 급여지 판단이 아니라 정보가치가 없다.
                2024Q1 실측 분포 = F 27,522 / S 27,191 / A 25,674 / M 17,653 / **P 5,954**.

필터는 작업계획서 §9 권장 조합(잠정):
  P & 취득(A) & 비파생 & 금액≥$10k & $5≤주가≤$50 & 공시지연≤5일 & 10b5-1 아님
  → 2024 기준 이벤트 잔존 약 46%.

이벤트 단위는 **(발행사, FILING_DATE)**. 거래행 기준으로 세면 2.6배 과대 계상된다.
진입 기준 시각은 TRANS_DATE(거래일)가 아니라 FILING_DATE(공시일) — 거래일 기준은 미래 누수다.

실행:  .venv/bin/python scripts/data_pipeline/gen_microcap_candidates.py
옵션:  --quarters 2023q1 2023q2 ...   (기본: 2023q1~2025q1)
"""
from __future__ import annotations

import sys

import argparse
import collections
import csv
import io
import re
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import EVENTS_CSV  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DERA_DIR = ROOT / "data" / "dera"
OUT = ROOT / "universe" / "microcap_candidates.txt"
# PIT 발행주식수(SEC XBRL) 조회는 티커가 아니라 CIK로 한다.
OUT_CSV = ROOT / "universe" / "microcap_candidates.csv"
# 이벤트 원본. 시총 밴드 산정·이벤트스터디가 소비한다.
OUT_EVENTS = EVENTS_CSV

# SEC는 이메일 포함 User-Agent를 요구한다(없으면 403).
UA = "qlib-toss research ax2team@didim.com"
BASE = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{}_form345.zip"

DEFAULT_QUARTERS = [f"{y}q{q}" for y in (2023, 2024) for q in (1, 2, 3, 4)] + ["2025q1"]

MIN_AMOUNT_USD = 10_000
MIN_PRICE, MAX_PRICE = 5.0, 50.0
MAX_FILING_LAG_DAYS = 5

# ISSUERTRADINGSYMBOL은 자유 텍스트라 오염이 많다(실측: 'N/A' '[ NONE ]' 'WLY, WLYB').
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,5}$")
# 정규식만으론 'NONE'이 통과한다. 'NA'는 실재 티커(Nano Labs)라 제외하지 않는다.
_SENTINELS = {"NONE", "N/A", "NULL", "NOSYMBOL"}


def _clean_ticker(raw: str) -> str | None:
    """유효한 미국 티커면 정규화해 반환, 아니면 None."""
    t = (raw or "").strip().upper()
    if t in _SENTINELS or not _TICKER_RE.match(t):
        return None
    return t


def _fetch(quarter: str) -> Path:
    """분기 zip을 data/dera/<quarter>/ 에 캐시. 이미 있으면 재다운로드하지 않는다."""
    d = DERA_DIR / quarter
    if (d / "SUBMISSION.tsv").exists():
        return d
    d.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(BASE.format(quarter), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as resp:
        zipfile.ZipFile(io.BytesIO(resp.read())).extractall(d)
    return d


def _parse_date(value: str) -> datetime | None:
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _rows(path: Path):
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        yield from csv.DictReader(f, delimiter="\t")


def collect(quarters: list[str]) -> tuple[collections.Counter, collections.Counter, dict, list]:
    """필터 통과 이벤트를 (발행사, 공시일) 단위로 집계.

    Returns:
        (events, stats, pair_events, rows) — events=ticker별 이벤트 수, stats=단계별 잔존 카운트,
        pair_events=(ticker, CIK)별 이벤트 수, rows=이벤트 원본 튜플 리스트.
    """
    # AFF10B5ONE(10b5-1 체크박스)은 2023년경 이후 분기에만 존재 → .get()으로 접근할 것.
    raw = collections.defaultdict(lambda: [0.0, 0.0, 10**9])  # (cik,ticker,공시일) -> [금액, 최대주가, 최소지연]
    stats = collections.Counter()

    for q in quarters:
        d = _fetch(q)
        sub = {r["ACCESSION_NUMBER"]: r for r in _rows(d / "SUBMISSION.tsv")}
        for r in _rows(d / "NONDERIV_TRANS.tsv"):
            stats["거래행"] += 1
            if r["TRANS_CODE"] != "P" or r["TRANS_ACQUIRED_DISP_CD"] != "A":
                continue
            stats["P&취득"] += 1
            s = sub.get(r["ACCESSION_NUMBER"])
            if s is None:
                continue
            if s.get("AFF10B5ONE") in ("1", "Y", "true", "TRUE"):
                continue
            stats["10b5-1 제외후"] += 1
            ticker = _clean_ticker(s["ISSUERTRADINGSYMBOL"])
            if ticker is None:
                continue
            stats["티커 정제후"] += 1
            try:
                price = float(r["TRANS_PRICEPERSHARE"])
                amount = float(r["TRANS_SHARES"]) * price
            except (ValueError, TypeError):
                continue
            filing_date = _parse_date(s["FILING_DATE"])
            trans_date = _parse_date(r["TRANS_DATE"])
            if filing_date is None:
                continue
            lag = (filing_date - trans_date).days if trans_date else 10**9
            key = (s["ISSUERCIK"], ticker, filing_date.date())
            acc = raw[key]
            acc[0] += amount
            acc[1] = max(acc[1], price)
            acc[2] = min(acc[2], lag)

    stats["이벤트(발행사·공시일)"] = len(raw)
    events = collections.Counter()
    # 티커는 재사용되므로(실측 10건) ticker 단위로 접으면 두 발행사의 이벤트가 합쳐진다.
    pair_events: collections.Counter = collections.Counter()
    rows: list[tuple] = []
    for (cik, ticker, filing_date), (amount, price, lag) in sorted(raw.items(), key=lambda x: x[0][2]):
        # 지연 하한 0 필수 — DERA에 TRANS_DATE > FILING_DATE 인 오기가 있고(주 표본 7건),
        # `lag > MAX`만 보면 음수가 통과한다. 거래단가가 공시 이후 거래의 것이 되어
        # 선택 규칙(price deviation)이 오염되고 단계 2 검증("미래 누수 0건")을 위반한다.
        if amount < MIN_AMOUNT_USD or not (MIN_PRICE <= price <= MAX_PRICE) \
                or not (0 <= lag <= MAX_FILING_LAG_DAYS):
            continue
        events[ticker] += 1
        pair_events[(ticker, cik)] += 1
        rows.append((ticker, cik, filing_date.isoformat(), round(amount, 2), price, lag))
    stats["필터 통과 이벤트"] = sum(events.values())
    return events, stats, pair_events, rows


def _tagged(path: Path, tag: str) -> Path:
    return path if not tag else path.with_name(f"{path.stem}{tag}{path.suffix}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarters", nargs="+", default=DEFAULT_QUARTERS)
    # 단계 2(45분기 전량)가 단계 1의 주 표본 산출물을 덮으면 사전등록 근거가 사라진다.
    ap.add_argument("--out-tag", default="",
                    help="산출 파일명 접미사. 예: --out-tag _full → insider_events_full.csv")
    args = ap.parse_args()
    out = _tagged(OUT, args.out_tag)
    out_csv = _tagged(OUT_CSV, args.out_tag)
    out_events = _tagged(OUT_EVENTS, args.out_tag)

    events, stats, pair_events, event_rows = collect(args.quarters)
    if not events:
        raise SystemExit("[오류] 필터를 통과한 이벤트가 없음 — 필터·분기 확인")

    for label in ("거래행", "P&취득", "10b5-1 제외후", "티커 정제후",
                  "이벤트(발행사·공시일)", "필터 통과 이벤트"):
        print(f"  {label:24s} {stats[label]:>8,}")
    print(f"  {'후보 티커':24s} {len(events):>8,}")

    symbols = [t for t, _ in events.most_common()]  # 이벤트 많은 종목부터
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join([
        f"# 마이크로캡 후보 — SEC DERA {args.quarters[0]}~{args.quarters[-1]} 내부자 공개시장 매수(P) 발행사.",
        f"# 필터: 금액>=${MIN_AMOUNT_USD:,} · ${MIN_PRICE:g}<=주가<=${MAX_PRICE:g} · 공시지연<={MAX_FILING_LAG_DAYS}일 · 10b5-1 제외.",
        f"# {len(events)}종목 / 필터통과 이벤트 {sum(events.values()):,}건. 이벤트 많은 순.",
        "# gen_microcap_candidates.py로 재생성. Toss 취급 여부는 06_microcap_coverage.py로 별도 확인.",
        *symbols,
    ]) + "\n")

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "cik", "events"])
        w.writerows([(s, c, n) for (s, c), n in pair_events.most_common()])

    dup = collections.Counter(s for s, _ in pair_events)
    n_dup = sum(1 for s in dup if dup[s] > 1)
    if n_dup:
        print(f"  ⚠️ 복수 CIK 티커 {n_dup}건 — 가격은 티커로만 조회되므로 시총 산정 시 UNKNOWN 처리됨")

    out_events.parent.mkdir(parents=True, exist_ok=True)
    with open(out_events, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "cik", "filing_date", "amount_usd", "max_price", "filing_lag_days"])
        w.writerows(event_rows)

    print(f"\n[완료] {out.relative_to(ROOT)} · {out_csv.relative_to(ROOT)} · {out_events.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
