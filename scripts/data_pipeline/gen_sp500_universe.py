"""S&P500 현 구성원 티커 목록 생성 → universe/sp500_full.txt

Wikipedia 'List of S&P 500 companies'의 constituents 표에서 Symbol 열을 추출한다.
현 구성 고정이라 과거 시점 구성원이 아님 → 생존편향(개선3) 한계로 유지.

- 클래스주 티커 보정: yfinance는 'BRK-B' 형식(Wikipedia는 'BRK.B') → '.'→'-'.
- 벤치마크용 SPY를 맨 끝에 추가(매매 유니버스에서는 dump 후 instruments/sp500.txt로 제외).

실행:  .venv/bin/python scripts/data_pipeline/gen_sp500_universe.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import requests
from bs4 import BeautifulSoup

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
UNIV_DIR = Path(__file__).resolve().parents[2] / "universe"
OUT = UNIV_DIR / "sp500_full.txt"
NAMES_OUT = UNIV_DIR / "sp500_names.csv"  # symbol → 회사명(대시보드 표시용)
BENCHMARK = "SPY"


def fetch_constituents() -> list[tuple[str, str]]:
    """Wikipedia constituents 표에서 (Symbol, Security 회사명) 쌍 추출."""
    resp = requests.get(WIKI_URL, headers={"User-Agent": "Mozilla/5.0 (qlib-toss universe builder)"}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "constituents"})
    if table is None:
        raise SystemExit("[오류] constituents 표를 찾지 못함 (Wikipedia 구조 변경 가능)")

    rows: list[tuple[str, str]] = []
    for row in table.find_all("tr"):  # find_all은 tbody 유무 무관. 헤더 행은 td 없어 자동 스킵.
        tds = row.find_all("td")
        if len(tds) < 2:
            continue
        sym = tds[0].get_text(strip=True).upper().replace(".", "-")  # BRK.B → BRK-B
        name = tds[1].get_text(strip=True)
        if sym:
            rows.append((sym, name))
    return rows


def main() -> None:
    rows = fetch_constituents()
    if len(rows) < 480:  # 정상 S&P500이면 ~503
        raise SystemExit(f"[오류] 추출된 종목이 너무 적음({len(rows)}) — 파싱 확인")

    symbols = [sym for sym, _ in rows]
    lines = [
        "# S&P500 현 구성원 (Wikipedia 스크랩). 생존편향(개선3): 현 구성 고정, 과거 시점 구성 아님.",
        f"# {len(symbols)}종목 + 벤치마크 {BENCHMARK}(맨 끝). {BENCHMARK}는 dump 후 instruments/sp500.txt에서 제외(벤치 전용).",
        f"# gen_sp500_universe.py로 재생성.",
        *symbols,
        BENCHMARK,
    ]
    OUT.write_text("\n".join(lines) + "\n")

    with NAMES_OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "name"])
        w.writerows(rows)
        w.writerow([BENCHMARK, "SPDR S&P 500 ETF Trust"])
    print(f"✅ {len(symbols)}종목 + {BENCHMARK} → {OUT}\n✅ 회사명 매핑 → {NAMES_OUT}")


if __name__ == "__main__":
    main()
