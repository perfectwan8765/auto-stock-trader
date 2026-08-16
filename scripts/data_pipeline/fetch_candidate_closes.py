"""후보 종목 종가 행렬 수집 → data/candidate_closes.csv

이 26MB 산출물은 원래 gen_universe_by_mcap.py("이벤트 시점 PIT 시가총액 산정")의 **부수효과**로
만들어졌다. 소비자 5개(verify_stage2 · measure_coverage · measure_power · measure_exit_timing ·
classify_missing_reason)는 자기 입력을 누가 만드는지 코드로 알 수 없었고, 종가만 필요한데도
캐시를 다시 만들려면 PIT 시총 산정 전체를 돌려야 했다.

생산 책임만 옮긴 것이며 산출물 내용은 같다.

실행:  .venv/bin/python scripts/data_pipeline/fetch_candidate_closes.py
옵션:  --start 2015-01-01  --end 2026-08-14  --refresh(캐시 무시)
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CANDIDATE_CLOSES_CSV, CANDIDATES_TXT, write_csv_atomic  # noqa: E402

PRICES = CANDIDATE_CLOSES_CSV


def fetch_closes(symbols: list[str], start: str, end: str,
                 use_cache: bool = True) -> pd.DataFrame:
    """종가 패널을 받아 캐시. 재수집 시 adjclose가 소급 변경되므로 캐시를 우선 재사용한다.

    캐시 유효성은 컬럼뿐 아니라 날짜 범위도 본다 — 컬럼만 보면 `--quarters` 확장 시
    캐시 끝 이후 이벤트가 전부 캐시 마지막 종가를 쓰게 되어 시총이 조용히 틀린다.
    """
    df = pd.DataFrame()
    if use_cache and PRICES.exists():
        cached = pd.read_csv(PRICES, index_col=0, parse_dates=True)
        covers_range = (not cached.empty
                        and cached.index.min() <= pd.Timestamp(start)
                        and cached.index.max() >= pd.Timestamp(end) - pd.Timedelta(days=10))
        missing = [s for s in symbols if s not in cached.columns]
        if covers_range and not missing:
            return cached
        if covers_range:
            print(f"  캐시 재사용 + 없는 {len(missing)}종목만 추가 수집")
            df, symbols = cached, missing
        else:
            rng = "(빈 캐시)" if cached.empty else f"{cached.index.min():%Y-%m-%d}~{cached.index.max():%Y-%m-%d}"
            print(f"  캐시 날짜범위 부족 {rng} < 요청 {start}~{end} → 전체 재수집")

    frames, failed, thin = [], [], 0
    for i in range(0, len(symbols), 100):
        chunk = symbols[i : i + 100]
        raw = yf.download(chunk, start=start, end=end, progress=False,
                          auto_adjust=False, threads=True, group_by="ticker")
        for s in chunk:
            # group_by="ticker"면 종목이 1개여도 컬럼이 MultiIndex다(yfinance 1.5.1).
            try:
                col = raw[s]["Close"].dropna()
            except (KeyError, TypeError):
                failed.append(s)
                continue
            if col.empty:
                failed.append(s)
                continue
            # 관측이 적어도 버리지 않는다 — 상장직후·조기폐지가 곧 생존편향 모집단이다.
            thin += len(col) < 20
            frames.append(col.rename(s))
        print(f"  ...{min(i + 100, len(symbols))}/{len(symbols)}")

    if frames:
        df = pd.concat([df] + frames, axis=1) if len(df) else pd.concat(frames, axis=1)
    print(f"  수집 실패 {len(failed):,}종목 · 관측 20일 미만 {thin:,}종목(유지)")
    if failed[:5]:
        print(f"  실패 예: {', '.join(failed[:5])}")
    PRICES.parent.mkdir(parents=True, exist_ok=True)
    # 전량 실패(yfinance 스로틀 등) 시 빈 프레임으로 캐시를 덮으면 수 시간치 수집이 날아가고
    # 하류가 전부 "결측"으로 읽어 **가짜 kill 판정**을 만든다. 받은 게 없으면 캐시를 건드리지 않는다.
    if df.empty:
        raise SystemExit("[중단] 수집 결과가 비어 있다 — 기존 캐시를 보존한다. 재시도할 것")
    write_csv_atomic(df, PRICES)
    return df


def read_candidates() -> list[str]:
    if not CANDIDATES_TXT.exists():
        raise SystemExit(f"[오류] {CANDIDATES_TXT} 없음 — gen_microcap_candidates.py 먼저 실행")
    return [s.strip().upper() for s in CANDIDATES_TXT.read_text().splitlines()
            if s.strip() and not s.startswith("#")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--refresh", action="store_true", help="캐시를 읽지 않고 전체 재수집(기존 파일은 성공 시에만 교체)")
    args = ap.parse_args()

    symbols = read_candidates()
    print(f"후보 {len(symbols):,}종목 종가 수집 → {PRICES.relative_to(PRICES.parents[2])}")
    # 삭제하지 않는다. 지운 뒤 전량 실패하면 "기존 캐시를 보존한다"는 가드가 이미 없어진
    # 캐시를 지키겠다고 중단하는 꼴이 된다 — 26MB와 수 시간치가 날아간다.
    # 읽지 않기만 하면 충분하다. 쓰기는 write_csv_atomic이 성공 시에만 교체한다.
    df = fetch_closes(symbols, args.start, args.end, use_cache=not args.refresh)
    print(f"완료: {df.shape[0]:,}행 × {df.shape[1]:,}종목")


if __name__ == "__main__":
    main()
