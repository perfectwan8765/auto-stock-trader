# 데이터 파이프라인 DAG + 편의 타깃.
#
# run_pipeline.py의 STEPS는 위상정렬이 아니라 하드코딩된 4단계 순서였고, Edge v2 쪽
# (gen_*·fetch_*·measure_*)의 실제 의존 그래프는 각 파일 docstring에만 있었다. 특히
# universe/microcap_tradable.txt가 scripts/toss_probe/ 산출물에 의존한다는 사실은
# data_pipeline만 봐서는 알 수 없다.
#
# 여기서는 "파일 → 파일" 관계를 그대로 선언한다. make가 mtime으로 필요한 선행만 돌리고,
# 규칙 없는 노드는 즉시 드러난다.

PY  := .venv/bin/python
DP  := scripts/data_pipeline
TP  := scripts/toss_probe

.PHONY: help test bundle-sp500 bundle-microcap check-dag clean-bundle

help:
	@echo "test             테스트 전량"
	@echo "bundle-sp500     S&P500 qlib 번들 재빌드"
	@echo "bundle-microcap  마이크로캡 qlib 번들 재빌드"
	@echo "check-dag        선언된 데이터 노드에 규칙이 다 있는지 확인"
	@echo "<파일경로>       해당 산출물과 그 선행만 생성 (예: make data/events_addv.csv)"

test:
	$(PY) -m pytest tests/ -q

# ---------------------------------------------------------------- qlib 번들
# QLIB_UNIVERSE/QLIB_DATASET 조합은 _common.py 주석에만 있던 암묵지다. 타깃으로 승격한다.
bundle-sp500:
	$(PY) $(DP)/run_pipeline.py

bundle-microcap:
	QLIB_UNIVERSE=microcap_tradable.txt QLIB_DATASET=_small $(PY) $(DP)/run_pipeline.py

clean-bundle:
	rm -rf data/qlib_us data/qlib_us_small

# ---------------------------------------------------------- Edge v2 데이터 DAG
DAG_NODES := \
  data/insider_events.csv \
  data/toss_stock_meta.csv \
  universe/microcap_tradable.txt \
  data/candidate_closes.csv \
  data/shares_outstanding.csv \
  data/insider_events_mcap.csv \
  data/events_addv.csv \
  data/events_spread.csv

check-dag:
	@fail=0; for n in $(DAG_NODES); do \
	  $(MAKE) -n "$$n" >/dev/null 2>&1 || { echo "규칙 없음: $$n"; fail=1; }; \
	done; \
	if [ $$fail -eq 0 ]; then echo "✅ 선언된 노드 $(words $(DAG_NODES))개 모두 규칙 있음"; fi; \
	exit $$fail

data/insider_events.csv universe/microcap_candidates.txt universe/microcap_candidates.csv: \
		$(DP)/gen_microcap_candidates.py
	$(PY) $<

# 교차 디렉터리 의존 — toss_probe가 만드는 노드다. data_pipeline만 봐서는 알 수 없다.
data/toss_stock_meta.csv: universe/microcap_candidates.txt $(TP)/06_microcap_coverage.py
	$(PY) $(TP)/06_microcap_coverage.py

universe/microcap_tradable.txt: data/toss_stock_meta.csv universe/microcap_candidates.txt \
		$(DP)/gen_microcap_tradable.py
	$(PY) $(DP)/gen_microcap_tradable.py

data/candidate_closes.csv: universe/microcap_candidates.txt $(DP)/fetch_candidate_closes.py
	$(PY) $(DP)/fetch_candidate_closes.py

data/shares_outstanding.csv: universe/microcap_candidates.csv $(DP)/fetch_shares_outstanding.py
	$(PY) $(DP)/fetch_shares_outstanding.py

data/insider_events_mcap.csv universe/microcap_by_mcap.txt: \
		data/insider_events.csv data/candidate_closes.csv data/shares_outstanding.csv \
		$(DP)/gen_universe_by_mcap.py
	$(PY) $(DP)/gen_universe_by_mcap.py

data/events_addv.csv: data/insider_events_mcap.csv universe/microcap_tradable.txt \
		$(DP)/measure_addv.py
	$(PY) $(DP)/measure_addv.py

data/events_spread.csv: data/events_addv.csv $(DP)/measure_edge_spread.py
	$(PY) $(DP)/measure_edge_spread.py
