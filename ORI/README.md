# ORI - Oceanic Research Intelligence (Phases 1-2: data foundation + statistical brain)

Run:  `pip install -r requirements.txt`  then  `python main.py`  (or `--file your.xlsx`)

Pipeline: Excel (Master sheet) -> normalized table -> QC -> analysis eligibility gate -> outputs

Outputs (output/):
- data/normalized_long.csv   one row per Excel row x parameter (obs_id traces back to the Excel row)
- data/station_level.csv     one row per station = unit of analysis (raw + BDL-aware values)
- data/dataset_manifest.json dataset description
- qc/qc_report.md|json       findings with stable ids (QC-001 ...)
- qc/eligibility.json        which analyses the data can support, and why

Rules: observations are never modified. Nutrient values <= 0 are BDL (user decision), excluded from statistics, raw kept.
Only the Master sheet is analysed; Transect_*/Station_* sheets are cross-checked copies.
Tests: python tests/test_phase1.py

## Phase 2 - statistics (stats/)
Six modules, one shared record type (stats/common.py): descriptive, spatial (station-wise, transect-wise, geographic
gradients + Moran's I), vertical, temporal, relational, anomaly. Each result is a *statement record* with an id
(STAT-DO-003), the exact numbers, caveats, the QC ids that affect it and its gate status.
- The eligibility gate is obeyed: unsupported analyses (vertical, temporal for the current file) write a `not_run` record, never numbers.
- Unit of analysis = station. BDL values excluded, never substituted. p-values FDR-adjusted (Benjamini-Hochberg).
- Statements describe numbers only (a test forbids mechanism words such as remineralization/upwelling/because).
- Outputs: output/stats/stat_records.json|csv, stats_report.md, tables/*.csv
- Folder is `stats/` (not `statistics/`, which would shadow Python's standard library module).
Tests: python tests/test_phase1.py ; python tests/test_phase2.py

## Phase 3 - reasoning (reasoning/)
Ranks, checks and groups Phase 2 results. Adds NO new oceanographic claims.
- importance.py: transparent 0-100 score per statistical_result (formula in the report; weights in config.py).
- confounding.py: partial Spearman correlation controlling for transect number, to flag correlations that are
  probably driven by a shared spatial gradient rather than a pairwise relationship.
- patterns.py: groups correlated parameters into correlation_cluster patterns (transitive), and re-exposes
  Phase 2 co-occurring anomalies (STAT-ANO-*) as anomaly_cooccurrence patterns.
- questions.py: 2-4 grounded diagnostic questions per pattern, each citing its stat/pattern ids.
Outputs: output/reasoning/reasoning_records.json, reasoning_report.md, tables/importance_scores.csv,
tables/confounding_checks.csv
Tests: python tests/test_phase3.py

## Phase 4 - oceanographic knowledge (knowledge/)
Matches a small, curated process library against Phase 2 relational results and the Phase 3
confounding check. Every result is a CANDIDATE explanation, never a conclusion.
- library.py: ProcessSpec entries (pairwise signature = parameter pair + expected sign, or a combo
  that requires several pairwise specs to all match). Extend the library here, by adding entries -
  no code path lets an LLM write into this file.
- match.py: signature matching; confidence is CANDIDATE - PLAUSIBLE / CANDIDATE - WEAK (SPATIAL CONFOUND)
  depending on whether the Phase 3 confounding check attenuated the correlation; combos are
  CANDIDATE - PLAUSIBLE (COMBINED EVIDENCE) / CANDIDATE - MIXED EVIDENCE. A relational result with no
  library match is recorded as NOT ASSESSED (a gap, not a rejection). Anomaly co-occurrence patterns get an
  explicit "localized event vs analytical artifact" template, always CANDIDATE - UNRANKED.
Outputs: output/knowledge/knowledge_records.json, knowledge_report.md
Tests: python tests/test_phase4.py

## Phase 5 - literature (literature/, input/literature/)
Connects Phase 4 candidate mechanisms to claims that already exist in a local store
(input/literature/papers.json). ORI never reads a PDF or invents a citation - every claim is
entered by a person, with a page/section reference, tagged with process_tags (matching
knowledge/library.py process keys), parameter_tags and region_tags.
- schema.py: Paper / Claim dataclasses + validation (untagged or unlocated claims are flagged, not dropped).
- store.py: load/save the JSON store; duplicate zotero_keys and bad entries are flagged as errors, not silently skipped.
- zotero_csv.py: offline import of Zotero CSV exports (metadata + tags only - Zotero has no per-claim
  data, so imported papers start with an empty claims list until you add claims by hand).
- match.py: STRONG (process + region tag both match) / MECHANISTIC (process only) / REGIONAL
  (region + parameter, no process) / NOT_CHECKED (nothing in the store yet - a gap, not a contradiction).
- The real store (input/literature/papers.json) ships EMPTY. Add your own papers - see input/literature/README.md.
- config.LITERATURE_REGION_TAGS: set this to your region(s) (e.g. ["Wadge Bank"]) to enable STRONG matches.
Outputs: output/literature/literature_records.json, literature_report.md
Tests: python tests/test_phase5.py (uses clearly-labeled [SYNTHETIC TEST FIXTURE] papers only - never real citations)

## Phase 6 - scientific writer (writer/)
Turns everything from Phases 1-5 into one traceable result document. No LLM is called in this
sandbox (no credentials, and a call should be an explicit choice you make and review).
- bundle.py: assembles ONE evidence bundle (data + eligibility + statistics + reasoning + knowledge
  + literature) - nothing is trimmed, so every number in the final text can be traced to a source record.
- render.py: the DEFAULT writer. Deterministic, no LLM - composes the result almost entirely by
  joining statement strings already generated (and already number-checked) by Phases 2-5, in the
  five sections your plan specified: Data Observation / Statistical Result / Oceanographic
  Interpretation / Literature-Supported Interpretation / Synthesis.
- verify.py: the number check. Extracts every number in the rendered text and rejects it unless it
  matches a number somewhere in the evidence bundle (small allowlist for standard thresholds like
  p < 0.001). run_all.py refuses to ship a result with violations - it writes
  UNVERIFIED_ori_result.md + verification_failed.json instead.
- llm_prompt.py: builds a strict prompt (bundle + rules) for an OPTIONAL smoother-prose pass through
  Claude - not run automatically. Run it yourself (API or paste into claude.ai), then verify the
  output with verify.verify_text() before trusting it.
Outputs: output/writer/ori_result.md (the final result), evidence_bundle.json, llm_prompt.txt
Tests: python tests/test_phase6.py (includes a deliberately fabricated number to prove the check catches it)

## Running everything
python main.py   runs all six phases end to end. On the sample data it currently ships an
ori_result.md with zero verification violations and an honest "no literature yet" section, since
input/literature/papers.json starts empty.

## Running from a fresh checkout
Run as a module so `config` and the other top-level packages resolve, e.g. `python -m main` or
`PYTHONPATH=. python main.py` if running `main.py` directly from another folder.

## Word (.docx) output
`python writer/make_docx.py` converts the shipped output/writer/ori_result.md into
output/writer/ori_result.docx via pandoc. Only run it after main.py reports `shipped=True`.

## Phase 3 baseline / familiar-vs-notable (reasoning/baseline.py)
Compares Phase 2 descriptive ranges and relational signs against a small literature-derived
baseline (ranges + expected relationship directions), built from input/literature/papers.json.
Classifications: FAMILIAR / NOTABLE / NO_BASELINE for ranges, FAMILIAR / CONTRADICTS_BASELINE /
NOT_IN_BASELINE for relationships. This is a lookup table, not machine learning - extend
reasoning/baseline.py's RANGES/RELATIONSHIPS dicts as more literature is added.
Tests: python tests/test_phase3_baseline.py

## Literature store status
input/literature/papers.json now has 6 real papers (desousa1996, naik2020, chakraborty2020,
kumar2009, kumargeetha2012, balakrishnan2017) with claims drawn from a user-supplied literature
review paragraph. IMPORTANT: every claim's source_location notes it was extracted from a
secondary, AI-assisted (Consensus) literature review, not read directly from the primary paper -
verify each claim against the actual source before using it in anything formal. The region match
(Gulf of Mannar / southeastern Arabian Sea) is based on station coordinates, not a confirmed
cruise region - confirm before treating STRONG matches as region-specific.
