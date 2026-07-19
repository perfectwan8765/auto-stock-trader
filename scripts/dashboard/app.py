"""백테스트·주문 대시보드 — mlruns pkl과 execution_logs를 웹 화면으로 렌더.

실행:  .venv/bin/streamlit run scripts/dashboard/app.py

두 탭:
  · 백테스트: 자산곡선·성과지표·주차별 보유·매매내역(포지션 diff 복원)·회전율
  · 주문로그: dry_run_rebalance가 남긴 발주계획(execution_logs/*.json)
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pickle
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
MLRUNS = ROOT / "mlruns"
EXEC_LOGS = ROOT / "execution_logs"
NAMES_CSV = ROOT / "universe" / "sp500_names.csv"  # symbol → 회사명(gen_sp500_universe.py 생성)

PA = "portfolio_analysis"
REPORT = f"{PA}/report_normal_1week.pkl"
POSITIONS = f"{PA}/positions_normal_1week.pkl"
RISK = f"{PA}/port_analysis_1week.pkl"
INDICATORS = f"{PA}/indicators_normal_1week.pkl"

# 색 팔레트(dataviz 검증): 포트=blue 주역, 벤치=neutral gray 기준선(점선으로 이중부호화).
# BUY/SELL은 status good/critical + 텍스트 라벨 동반(색 단독 금지 규칙 충족).
C_PORT, C_BENCH = "#2a78d6", "#898781"
C_BUY, C_SELL = "#0ca30c", "#d03b3b"

# 요약 KPI 카드 — st.metric은 델타를 값 아래에 넣어 카드 높이가 달라진다.
# 값(좌)·chip(우)을 한 줄에 두어 델타 유무와 무관하게 높이를 통일.
KPI_CSS = """
<style>
.kpi{border:1px solid rgba(128,128,128,.25);border-radius:.5rem;padding:.7rem .9rem;}
.kpi-label{font-size:.78rem;color:rgba(128,128,128,.95);margin-bottom:.35rem;white-space:nowrap;}
.kpi-row{display:flex;align-items:baseline;justify-content:space-between;gap:.5rem;}
.kpi-value{font-size:1.8rem;font-weight:600;line-height:1.15;}
.kpi-chip{font-size:.75rem;font-weight:600;padding:.1rem .45rem;border-radius:1rem;white-space:nowrap;}
.chip-up{color:#0ca30c;background:rgba(12,163,12,.12);}
.chip-down{color:#d03b3b;background:rgba(208,59,59,.12);}
.meta-row{display:flex;flex-wrap:wrap;gap:.4rem;margin:.1rem 0 .7rem;}
.meta-chip{font-size:.75rem;color:rgba(128,128,128,.95);background:rgba(128,128,128,.12);
           padding:.18rem .6rem;border-radius:1rem;white-space:nowrap;}
.meta-chip b{color:inherit;font-weight:600;}
</style>
"""

# 성과지표(risk) 영문 인덱스 → 한글 라벨.
PERF_GROUP = {
    "excess_return_without_cost": "초과수익 (비용 제외)",
    "excess_return_with_cost": "초과수익 (비용 포함)",
}
PERF_ITEM = {
    "mean": "평균",
    "std": "표준편차",
    "annualized_return": "연환산 수익률",
    "information_ratio": "정보비율 (IR)",
    "max_drawdown": "최대낙폭 (MDD)",
}
PERF_ITEM_ORDER = ["평균", "표준편차", "연환산 수익률", "정보비율 (IR)", "최대낙폭 (MDD)"]

# 주문 사유(OrderIntent.reason) · 스킵 사유 → 한글.
ORDER_REASON = {"exit": "청산", "trim": "축소", "enter": "신규", "add": "추가"}
SKIP_REASON = {
    "below_min_order": "최소주문금액 미달",
    "insufficient_buying_power": "매수여력 부족",
    "partial_insufficient_buying_power": "매수여력 부족(부분)",
    "excluded_manual": "수동보유 제외",
}


def equity_chart(report: pd.DataFrame) -> alt.Chart:
    """포트폴리오 vs 벤치 누적수익(시작=1.0) 라인차트. 포트=실선 blue, 벤치=점선 gray."""
    df = pd.DataFrame({
        "date": report.index,
        "포트폴리오": (1 + report["return"]).cumprod().values,
        "벤치마크": (1 + report["bench"]).cumprod().values,
    }).melt("date", var_name="계열", value_name="누적")
    dom = ["포트폴리오", "벤치마크"]
    return alt.Chart(df).mark_line(strokeWidth=2).encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("누적:Q", title="누적수익(시작=1.0)", scale=alt.Scale(zero=False)),
        color=alt.Color("계열:N", scale=alt.Scale(domain=dom, range=[C_PORT, C_BENCH]),
                        legend=alt.Legend(title=None, orient="top")),
        strokeDash=alt.StrokeDash("계열:N", scale=alt.Scale(domain=dom, range=[[1, 0], [5, 3]]),
                                  legend=None),
        tooltip=[alt.Tooltip("date:T", title="주차"), alt.Tooltip("계열:N"),
                 alt.Tooltip("누적:Q", format=".3f")],
    ).properties(height=300)


def kpi_card(label: str, value: str, chip: str | None = None, chip_dir: str = "up", title: str = "") -> str:
    """요약 KPI 카드 HTML. chip은 값 오른쪽에 같은 줄로 배치(높이 불변). title은 hover 설명."""
    chip_html = f'<span class="kpi-chip chip-{chip_dir}">{chip}</span>' if chip else ""
    t = f' title="{title}"' if title else ""
    return (f'<div class="kpi"><div class="kpi-label"{t}>{label}</div>'
            f'<div class="kpi-row"><span class="kpi-value">{value}</span>{chip_html}</div></div>')


def style_gubun(df: pd.DataFrame):
    """'구분' 컬럼(▲ 매수/▼ 매도) 색칠 — 매수 녹색·매도 적색(모양+글자 병행이라 색 단독 아님)."""
    return df.style.apply(
        lambda col: [f"color: {C_BUY if '매수' in v else C_SELL}" for v in col], subset=["구분"])


def bar_chart(series: pd.Series, title: str, fmt: str) -> alt.Chart:
    """단일계열 주간 바차트(blue). dual-scale 회피 위해 지표별 개별 차트로 분리."""
    df = pd.DataFrame({"date": series.index, "v": series.values})
    return alt.Chart(df).mark_bar(color=C_PORT, cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("v:Q", title=title),
        tooltip=[alt.Tooltip("date:T", title="주차"), alt.Tooltip("v:Q", title=title, format=fmt)],
    ).properties(height=200)


# ---------- mlruns 탐색·로딩 ----------

def _yaml_get(path: Path, key: str) -> str | None:
    """meta.yaml에서 key: value 한 줄 파싱(의존성 없이)."""
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return None


@st.cache_data(show_spinner=False)
def discover_runs() -> list[dict]:
    """portfolio_analysis 산출물이 있는 run만 수집. 최신순."""
    runs = []
    # 매치 경로: <exp>/<run>/artifacts/portfolio_analysis/report_normal_1week.pkl
    for report in MLRUNS.glob(f"*/*/artifacts/{REPORT}"):
        artifacts = report.parents[1]         # .../<run>/artifacts
        run_dir = report.parents[2]           # .../<run_id>
        exp_dir = report.parents[3]           # .../<experiment_id>
        exp_name = _yaml_get(exp_dir / "meta.yaml", "name") or exp_dir.name
        start = _yaml_get(run_dir / "meta.yaml", "start_time") or "0"

        strat = exp_name.replace("workflow_config_", "").replace("phase3_", "")
        idx = pickle.load(open(report, "rb")).index  # 백테스트 기간·주수(라벨용)
        d0, d1, n = idx[0].date(), idx[-1].date(), len(idx)
        exec_d = (dt.datetime.fromtimestamp(int(start) / 1000).strftime("%Y-%m-%d %H:%M")
                  if start.isdigit() else None)
        runs.append({
            "label": f"{strat} · {d0}~{d1} ({n}주) · 실행 {exec_d}",
            "artifacts": artifacts,
            "start": int(start) if start.isdigit() else 0,
            "d0": d0, "d1": d1, "n": n, "exec": exec_d,
        })
    return sorted(runs, key=lambda r: r["start"], reverse=True)


@st.cache_data(show_spinner=False)
def load_pkl(artifacts: str, rel: str):
    """artifacts 디렉토리 하위 rel 경로의 pickle을 로드해 반환(캐시)."""
    with open(Path(artifacts) / rel, "rb") as f:
        return pickle.load(f)


@st.cache_data(show_spinner=False)
def load_names() -> dict[str, str]:
    """symbol → 회사명 매핑. 파일 없거나 폐지·개명 티커면 심볼로 폴백."""
    if not NAMES_CSV.exists():
        return {}
    with NAMES_CSV.open() as f:
        return {r["symbol"]: r["name"] for r in csv.DictReader(f)}


@st.cache_data(show_spinner=False)
def fetch_krw_rate(date_str: str) -> float | None:
    """해당일자(≤) USD/KRW 종가를 yfinance KRW=X로 조회. 평가액 시점과 환율 일자를 일치시킴.

    실패(네트워크·데이터 없음) 시 None → 호출부가 수동 기본값으로 폴백.
    """
    try:
        import yfinance as yf
        d = pd.Timestamp(date_str)
        h = yf.Ticker("KRW=X").history(
            start=(d - pd.Timedelta(days=6)).strftime("%Y-%m-%d"),
            end=(d + pd.Timedelta(days=2)).strftime("%Y-%m-%d"))
        if h.empty:
            return None
        asof = h[h.index.tz_localize(None) <= d]  # 종료일 이하 마지막 종가
        s = asof if not asof.empty else h
        return float(s["Close"].iloc[-1])
    except Exception:
        return None


# ---------- 매매내역 복원 (포지션 주차간 diff) ----------

def reconstruct_trades(positions: dict) -> pd.DataFrame:
    """주차별 보유수량 변화 → BUY/SELL 내역. positions: {Timestamp: qlib Position}."""
    weeks = sorted(positions)
    rows = []
    prev: dict[str, float] = {}
    for wk in weeks:
        cur = positions[wk].get_stock_amount_dict()
        for sym in sorted(set(cur) | set(prev)):
            delta = cur.get(sym, 0.0) - prev.get(sym, 0.0)
            if abs(delta) < 1e-9:
                continue
            rows.append({
                "week": wk.date(),
                "symbol": sym,
                "side": "BUY" if delta > 0 else "SELL",
                "shares": round(abs(delta), 4),
                "held_after": round(cur.get(sym, 0.0), 4),
            })
        prev = cur
    # rows가 비어도 컬럼 유지 — 호출부의 trades["week"] 접근이 KeyError로 깨지지 않게.
    return pd.DataFrame(rows, columns=["week", "symbol", "side", "shares", "held_after"])


# ---------- 백테스트 탭 ----------

def render_backtest():
    """백테스트 탭: run 선택 → 요약지표·자산곡선·성과·회전율·매매내역·보유종목 렌더."""
    runs = discover_runs()
    if not runs:
        st.warning("portfolio_analysis 산출물이 있는 mlruns run이 없습니다. 먼저 run_backtest.py를 실행하세요.")
        return

    st.markdown(KPI_CSS, unsafe_allow_html=True)
    labels = [r["label"] for r in runs]
    pick = st.sidebar.selectbox("백테스트 (전략 · 기간)", labels)
    run = runs[labels.index(pick)]
    art = str(run["artifacts"])
    meta = [f"<b>기간</b> {run['d0']} ~ {run['d1']}", f"<b>{run['n']}주</b> · 주간 리밸런싱"]
    if run["exec"]:
        meta.append(f"<b>실행</b> {run['exec']}")
    st.markdown('<div class="meta-row">' + "".join(f'<span class="meta-chip">{m}</span>' for m in meta)
                + "</div>", unsafe_allow_html=True)

    report = load_pkl(art, REPORT)
    risk = load_pkl(art, RISK)
    positions = load_pkl(art, POSITIONS)
    indicators = load_pkl(art, INDICATORS)

    equity = report["account"]
    start_usd, final_usd = equity.iloc[0], equity.iloc[-1]
    total_ret = final_usd / start_usd - 1
    bench_ret = (1 + report["bench"]).prod() - 1
    ex = risk["risk"]
    ann_ex = ex.get(("excess_return_with_cost", "annualized_return"), float("nan"))
    mdd = ex.get(("excess_return_with_cost", "max_drawdown"), float("nan"))
    end_date = str(equity.index[-1].date())
    auto = fetch_krw_rate(end_date)
    krw = st.sidebar.number_input("USD/KRW 환율", min_value=0.0, value=float(auto or 1380.0), step=10.0,
                                  help=f"기본값 = 백테스트 종료일({end_date}) KRW=X 자동조회. 직접 조정 가능.")
    rate_src = f"{end_date} 종가 자동조회" if auto else "자동조회 실패 → 수동 기본값"

    diff = (total_ret - bench_ret) * 100  # 벤치 대비 초과/미달 %p
    up = diff >= 0
    cards = [
        kpi_card("최종 평가액", f"${final_usd:,.0f}", title=f"시작 ${start_usd:,.0f} → 종료 ${final_usd:,.0f}"),
        kpi_card("원화 환산", f"₩{final_usd * krw:,.0f}", title=f"{end_date} 환율 {krw:,.0f}원/$ 적용"),
        kpi_card("총수익률", f"{total_ret*100:.2f}%", chip=f"{'▲' if up else '▼'} {diff:+.2f}%p",
                 chip_dir="up" if up else "down", title="같은 기간 벤치(SPY) 대비 초과/미달 (%p). 음수=벤치 하회"),
        kpi_card("연환산 초과수익(비용後)", f"{ann_ex*100:.2f}%", title="벤치(SPY) 대비 연환산 초과수익. 음수=벤치 하회"),
        kpi_card("최대낙폭(비용後)", f"{mdd*100:.2f}%", title="고점 대비 최대 하락폭(초과수익 기준)"),
    ]
    for col, html in zip(st.columns(5), cards):
        col.markdown(html, unsafe_allow_html=True)
    st.caption(
        f"**원화 환산** — 백테스트 종료일({end_date})의 USD/KRW {krw:,.0f}원 적용({rate_src}). "
        "평가액 시점과 환율 일자를 맞췄으며, 환율은 사이드바에서 조정할 수 있습니다.  \n"
        "**자산곡선·성과지표** — 환차손익이 전략 성과에 섞이지 않도록 USD·비율 기준을 유지합니다.")

    st.subheader("자산곡선 (누적수익, 시작=1.0)")
    st.altair_chart(equity_chart(report), width="stretch")

    st.subheader("성과지표")
    perf = ex.reset_index()
    perf.columns = ["구분", "항목", "값"]
    perf["구분"] = perf["구분"].map(lambda x: PERF_GROUP.get(x, x))
    perf["항목"] = perf["항목"].map(lambda x: PERF_ITEM.get(x, x))
    wide = perf.pivot(index="항목", columns="구분", values="값").reindex(PERF_ITEM_ORDER)
    wide.columns.name = None
    st.dataframe(wide.style.format("{:.4f}"), width="stretch")
    st.caption("초과수익 = 벤치(SPY) 대비. IR=정보비율(초과수익÷변동성, 높을수록 좋음), "
               "MDD=최대낙폭(고점 대비 최대 하락, 음수). 평균·표준편차·연환산은 주간 초과수익 기준.")

    # 비율(회전율)과 USD(체결금액)는 스케일이 달라 개별 차트로 분리(dual-scale 회피).
    st.subheader("주간 회전율 · 체결금액")
    cc1, cc2 = st.columns(2)
    cc1.altair_chart(bar_chart(report["turnover"], "회전율", ".2f"), width="stretch")
    cc2.altair_chart(bar_chart(indicators["deal_amount"], "체결금액(USD)", "$,.0f"),
                     width="stretch")

    st.subheader("매매내역 (포지션 diff 복원)")
    st.caption("주차간 보유수량 변화로 복원한 근사치 — qlib이 개별 체결로그를 남기지 않음. "
               "같은 주 매도후 동수 재매수(net 0)는 잡히지 않음.")
    trades = reconstruct_trades(positions)
    names = load_names()

    f1, f2 = st.columns([2, 1])
    weeks = ["(전체)"] + [str(w) for w in sorted(trades["week"].unique())]
    wk = f1.selectbox("주차", weeks, key="trade_wk")
    side_f = f2.radio("구분", ["전체", "매수", "매도"], horizontal=True, key="trade_side")
    view = trades if wk == "(전체)" else trades[trades["week"].astype(str) == wk]
    if side_f != "전체":
        view = view[view["side"] == ("BUY" if side_f == "매수" else "SELL")]

    n_buy, n_sell = int((view["side"] == "BUY").sum()), int((view["side"] == "SELL").sum())
    s1, s2, s3 = st.columns(3)
    s1.metric("총 거래", f"{len(view)}건", border=True)
    s2.metric("매수", f"{n_buy}건", border=True)
    s3.metric("매도", f"{n_sell}건", border=True)

    disp = pd.DataFrame({
        "주차": view["week"].astype(str),
        "종목": view["symbol"],
        "종목명": view["symbol"].map(lambda s: names.get(s, s)),
        "구분": view["side"].map({"BUY": "▲ 매수", "SELL": "▼ 매도"}),
        "수량": view["shares"],
        "보유(후)": view["held_after"],
    })
    st.dataframe(style_gubun(disp) if not disp.empty else disp, width="stretch", hide_index=True)

    st.subheader("보유종목 (주차 선택)")
    held_weeks = [str(w.date()) for w in sorted(positions)]
    hw = st.select_slider("주차", held_weeks, value=held_weeks[-1])
    pos = positions[[w for w in sorted(positions) if str(w.date()) == hw][0]]
    amt, wt = pos.get_stock_amount_dict(), pos.get_stock_weight_dict()
    names = load_names()
    hold = pd.DataFrame([
        {"symbol": s, "name": names.get(s, s), "shares": round(amt[s], 4),
         "price": round(pos.position[s]["price"], 4), "weight": round(wt.get(s, 0.0), 4)}
        for s in sorted(amt)
    ])
    st.caption(f"현금 ${pos.get_cash():,.2f} · 평가액 ${pos.calculate_value():,.2f} · {len(hold)}종목")
    st.dataframe(hold, width="stretch", hide_index=True)


# ---------- 주문로그 탭 ----------

def render_orders():
    """주문로그 탭: execution_logs/*.json 선택 → 발주계획(orders·skipped) 렌더."""
    if not EXEC_LOGS.exists() or not any(EXEC_LOGS.glob("rebalance_*.json")):
        st.info("주문로그 없음. `dry_run_rebalance.py` 실행 시 execution_logs/에 생성됩니다.")
        return
    logs = sorted(EXEC_LOGS.glob("rebalance_*.json"), reverse=True)

    def _label(p: Path) -> str:
        d = json.loads(p.read_text())
        ymd = f"{d['date'][:4]}-{d['date'][4:6]}-{d['date'][6:]}"
        return f"{ymd} · {'dry-run' if d['dry_run'] else '실발주'} · {len(d['orders'])}건"

    by_label = {_label(p): p for p in logs}
    pick = st.sidebar.selectbox("주문로그 (날짜)", list(by_label))
    data = json.loads(by_label[pick].read_text())

    ymd = f"{data['date'][:4]}-{data['date'][4:6]}-{data['date'][6:]}"
    st.subheader(f"발주계획 · {ymd}")
    st.caption(f"시그널 {data.get('signal')} · {'DRY-RUN (모의)' if data['dry_run'] else '실발주'}"
               + (f" · 중단사유 {data['aborted_reason']}" if data.get("aborted_reason") else ""))

    names = load_names()
    orders = pd.DataFrame(data["orders"])
    if orders.empty:
        st.info("주문 없음.")
    else:
        n_buy, n_sell = int((orders["side"] == "BUY").sum()), int((orders["side"] == "SELL").sum())
        buy_usd = orders.loc[(orders["side"] == "BUY") & (orders["kind"] == "amount"), "value"].sum()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 주문", f"{len(orders)}건", border=True)
        m2.metric("매수", f"{n_buy}건", delta=f"${buy_usd:,.0f}", delta_color="off", border=True)
        m3.metric("매도", f"{n_sell}건", border=True)
        m4.metric("스킵", f"{len(data['skipped'])}건", border=True)

        disp = pd.DataFrame({
            "종목": orders["symbol"],
            "종목명": orders["symbol"].map(lambda s: names.get(s, s)),
            "구분": orders["side"].map({"BUY": "▲ 매수", "SELL": "▼ 매도"}),
            "금액/수량": [f"${v:,.2f}" if k == "amount" else f"{v:g}주"
                      for v, k in zip(orders["value"], orders["kind"])],
            "사유": orders["reason"].map(lambda r: ORDER_REASON.get(r, r)),
            "주문ID": orders["client_order_id"],
        })
        st.dataframe(style_gubun(disp), width="stretch", hide_index=True)
        st.caption("금액/수량: 매수는 USD 금액, 매도는 주식수. 주문ID = 결정적 멱등키(중복 발주 방지).")

    if data["skipped"]:
        st.markdown("**스킵된 주문**")
        sk = pd.DataFrame(data["skipped"], columns=["symbol", "reason"])
        st.dataframe(pd.DataFrame({
            "종목": sk["symbol"],
            "종목명": sk["symbol"].map(lambda s: names.get(s, s)),
            "사유": sk["reason"].map(lambda r: SKIP_REASON.get(r, r)),
        }), width="stretch", hide_index=True)


# ---------- 메인 ----------

st.set_page_config(page_title="qlib 대시보드", layout="wide")
st.title("qlib 백테스트 · 주문 대시보드")
tab_bt, tab_ord = st.tabs(["백테스트", "주문로그"])
with tab_bt:
    render_backtest()
with tab_ord:
    render_orders()
