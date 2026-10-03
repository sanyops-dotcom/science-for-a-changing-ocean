"""ORI Phase 3 - runs importance scoring, the confounding check, pattern compression and the
question engine, and writes records + a Markdown report."""
import json
from pathlib import Path

import pandas as pd

import config
from reasoning import baseline, confounding, importance, patterns, questions
from reasoning.common import RContext


def run_reasoning(station_level: pd.DataFrame, gate: dict, stat_records: list, out_dir: Path) -> dict:
    out = Path(out_dir) / "reasoning"
    ctx = RContext(st=station_level, stat_records=stat_records, gate=gate, tables_dir=out / "tables")

    imp_reg, imp_df = importance.run(ctx)
    conf_reg, conf_df = confounding.run(ctx)
    pat_reg = patterns.run(ctx, imp_df, conf_df)
    q_reg = questions.run(ctx, pat_reg)
    base = baseline.run(ctx, stat_records, config.LITERATURE_REGION_TAGS)

    out.mkdir(parents=True, exist_ok=True)
    bundle = {"importance": imp_reg.items, "confounding": conf_reg.items, "patterns": pat_reg.items,
             "questions": q_reg.items, "baseline_ranges": base["ranges"].items,
             "baseline_relationships": base["relationships"].items}
    (out / "reasoning_records.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "reasoning_report.md").write_text(build_report(ctx, imp_df, conf_df, pat_reg, q_reg, base), encoding="utf-8")
    return bundle


def build_report(ctx: RContext, imp_df, conf_df, pat_reg, q_reg, base) -> str:
    L = ["# ORI - Phase 3 report: reasoning (importance, confounding, patterns, questions)",
         "\nThis layer ranks, checks and groups Phase 2 statistical results. It adds no new "
         "oceanographic claims - only numbers about the numbers (scores, partial correlations, groupings) "
         "and questions. Oceanographic mechanisms are Phase 4 (not yet built).",
         "\n## 1. Importance scoring",
         f"Formula: score = 100 x ({__import__('config').IMPORTANCE_W_STRENGTH} x evidence_strength "
         f"+ {__import__('config').IMPORTANCE_W_EFFECT} x |effect size| "
         f"+ {__import__('config').IMPORTANCE_W_N} x (n / n_stations) "
         f"+ {__import__('config').IMPORTANCE_W_CORROBORATION} x corroboration). "
         "evidence_strength: STRONG=1, MODERATE=0.66, WEAK=0.33. corroboration: 0 if found by one module, "
         "0.5 by two, 1 by three or more. Every component is printed per record in tables/importance_scores.csv.",
         "\n### Top 10 by score"]
    top = imp_df.head(10)
    L.append("| stat_id | module | parameters | strength | score | band |")
    L.append("|---|---|---|---|---|---|")
    for r in top.itertuples():
        L.append(f"| {r.stat_id} | {r.module} | {r.parameters} | {r.evidence_strength} | {r.score} | {r.band} |")

    L.append("\n## 2. Spatial confounding check (partial correlation controlling for transect number)")
    if len(conf_df):
        L.append("| stat_id | pair | raw rho | partial rho | partial p | attenuates strongly |")
        L.append("|---|---|---|---|---|---|")
        for r in conf_df.itertuples():
            L.append(f"| {r.stat_id} | {r.a}-{r.b} | {r.raw_rho:.2f} | {r.partial_rho:.2f} | "
                     f"{'n/a' if pd.isna(r.partial_p) else f'{r.partial_p:.3f}'} | {r.attenuates_strongly} |")
        n_att = int(conf_df["attenuates_strongly"].sum())
        L.append(f"\n{n_att} of {len(conf_df)} statistically supported correlations attenuate strongly once transect "
                 f"number is controlled for - these are more consistent with a shared spatial gradient than with an "
                 f"independent pairwise relationship.")
    else:
        L.append("No relational results were eligible for this check.")

    L.append("\n## 3. Patterns")
    for p in pat_reg.items:
        L.append(f"\n- **{p['id']}** ({p['kind']}) {p['text']}")
        if p["caveats"]:
            L.append(f"  - caveats: {'; '.join(p['caveats'])}")

    L.append("\n## 4. Familiar vs. notable (baseline from user-provided literature)")
    L.append("Baseline ranges/relationships come from a literature synthesis the user supplied "
             "(input/literature/papers.json); this is a lookup comparison, not machine learning.")
    for item in base["ranges"].items:
        L.append(f"- {item['text']}")
    for item in base["relationships"].items:
        L.append(f"- {item['text']}")

    L.append("\n## 5. Questions")
    for q in q_reg.items:
        for line in q["detail"]["questions"]:
            L.append(f"- {line}")

    return "\n".join(L) + "\n"
