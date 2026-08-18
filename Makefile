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
RUFF := .venv/bin/ruff
DP  := scripts/data_pipeline
TP  := scripts/toss_probe

.PHONY: help test lint lint-fix check-docrefs bundle-sp500 bundle-microcap check-dag clean-bundle

help:
	@echo "test             테스트 전량"
	@echo "lint             주석·docstring 린트 (설정 근거는 pyproject.toml)"
	@echo "lint-fix         린트 자동수정 가능분만 적용"
	@echo "check-docrefs    주석·docstring이 가리키는 .md가 실재하는지 확인"
	@echo "bundle-sp500     S&P500 qlib 번들 재빌드"
	@echo "bundle-microcap  마이크로캡 qlib 번들 재빌드"
	@echo "check-dag        선언된 데이터 노드에 규칙이 다 있는지 확인"
	@echo "<파일경로>       해당 산출물과 그 선행만 생성 (예: make data/events_addv.csv)"

test:
	$(PY) -m pytest tests/ -q

# ------------------------------------------------------------------- 주석·docstring
lint:
	$(RUFF) check src scripts tests

lint-fix:
	$(RUFF) check --fix src scripts tests

# 주석 속 파일명은 산문이라 문서를 개명해도 따라오지 않는다 — 실제로 5곳이 끊겨 있었다
# (커밋 8f5f135). 마크다운 링크와 달리 린터가 잡지 않으므로(ruff 969개 규칙 중 없음) 직접 본다.
#
# docs/plans/·docs/findings/를 일부러 후보에서 뺐다. 그쪽은 추적 밖이라 로컬에서는 통과하고
# 클론에서만 실패한다 — check-dag가 기록한 것과 같은 함정이다. 여기서는 추적 밖 문서를
# 가리키는 것 자체를 위반으로 취급한다.
check-docrefs:
	@grep -rno '[A-Za-z0-9_./-]*\.md' --include='*.py' src scripts tests \
	  | { fail=0; \
	      while IFS=: read -r f l ref; do \
	        test -f "$$ref" -o -f "docs/project/$$ref" -o -f "docs/research/$$ref" \
	          || { echo "죽은 문서 참조: $$f:$$l -> $$ref"; fail=1; }; \
	      done; \
	      test $$fail -eq 0 && echo "✅ 문서 참조 전량 해소"; \
	      exit $$fail; }

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

# `make -n <node>`로는 확인이 안 된다 — 규칙이 없어도 파일이 이미 있으면 "Nothing to be
# done"과 함께 exit 0이다. DAG_NODES는 전부 gitignore된 데이터 파일이라 파이프라인을 한 번
# 돌린 머신에서는 무조건 통과하고, 정작 신규 클론에서만 실패하는 정반대 동작이 된다.
# 규칙 데이터베이스(`make -p`)를 직접 조회한다.
check-dag:
	@db=$$($(MAKE) -p -n -f $(firstword $(MAKEFILE_LIST)) 2>/dev/null); fail=0; \
	for n in $(DAG_NODES) $(STAMPS); do \
	  echo "$$db" | grep -qE "^$$n( |:)" || { echo "규칙 없음: $$n"; fail=1; }; \
	done; \
	if [ $$fail -eq 0 ]; then echo "✅ 노드 $(words $(DAG_NODES))개 + stamp $(words $(STAMPS))개 규칙 확인"; fi; \
	exit $$fail

# 이 머신의 GNU Make는 3.81이라 grouped target(`&:`)이 없다. 다중 타깃을 그냥 나열하면
# 각 타깃이 같은 레시피를 가진 독립 규칙으로 취급돼, 둘 다 낡았을 때 스크립트가 두 번 돈다
# — gen_microcap_candidates는 SEC DERA 전량 다운로드 + 340만 행 파싱이라 두 배는 비싸다.
# stamp 파일 하나를 실제 산출물들의 선행으로 두어 한 번만 돌게 한다.
STAMPS := .make/candidates.stamp .make/mcap.stamp

.make:
	@mkdir -p $@

.make/candidates.stamp: $(DP)/gen_microcap_candidates.py | .make
	$(PY) $<
	@touch $@

data/insider_events.csv universe/microcap_candidates.txt universe/microcap_candidates.csv: \
		.make/candidates.stamp
	@test -f $@ || { echo "[오류] $@ 가 생성되지 않았다"; exit 1; }

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

.make/mcap.stamp: data/insider_events.csv data/candidate_closes.csv \
		data/shares_outstanding.csv $(DP)/gen_universe_by_mcap.py | .make
	$(PY) $(DP)/gen_universe_by_mcap.py
	@touch $@

data/insider_events_mcap.csv universe/microcap_by_mcap.txt: .make/mcap.stamp
	@test -f $@ || { echo "[오류] $@ 가 생성되지 않았다"; exit 1; }

data/events_addv.csv: data/insider_events_mcap.csv universe/microcap_tradable.txt \
		$(DP)/measure_addv.py
	$(PY) $(DP)/measure_addv.py

data/events_spread.csv: data/events_addv.csv $(DP)/measure_edge_spread.py
	$(PY) $(DP)/measure_edge_spread.py
