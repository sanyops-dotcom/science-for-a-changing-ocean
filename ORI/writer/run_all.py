"""ORI Phase 6 - runs the writer: bundle -> render -> verify -> outputs.

If verify.verify_text finds any violation, the deterministic paragraph is NOT shipped as-is -
the violation is reported instead, and the raw (unverified) text is kept only in a side file
for debugging. This is the code-level enforcement of "no number the evidence ledger can't back."
"""
import json
from pathlib import Path

from writer.bundle import build_bundle
from writer.llm_prompt import build_prompt
from writer.render import render
from writer.verify import verify_text


def run_writer(manifest: dict, gate: dict, stat_records: list, reasoning: dict, knowledge: dict,
              literature: dict, out_dir: Path) -> dict:
    bundle = build_bundle(manifest, gate, stat_records, reasoning, knowledge, literature)
    text = render(bundle)
    violations = verify_text(text, bundle)

    out = Path(out_dir) / "writer"
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidence_bundle.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "llm_prompt.txt").write_text(build_prompt(bundle), encoding="utf-8")
    if violations:
        (out / "UNVERIFIED_ori_result.md").write_text(text, encoding="utf-8")
        (out / "verification_failed.json").write_text(json.dumps(violations, indent=2), encoding="utf-8")
    else:
        (out / "ori_result.md").write_text(text, encoding="utf-8")
    return {"bundle": bundle, "text": text, "violations": violations, "shipped": not violations}
