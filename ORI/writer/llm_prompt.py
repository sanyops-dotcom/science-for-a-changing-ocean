"""ORI Phase 6 - llm_prompt.py: builds a strict prompt for an LLM prose pass.

This is NOT executed automatically - this sandbox has no API credentials, and even with them,
an LLM call should be something you explicitly choose to run (and review). The deterministic
writer (render.py) is what ORI ships by default; this is for when you want smoother prose and
are willing to run it through Claude yourself (API, or by pasting into claude.ai) and then
number-check the result with verify.verify_text() before accepting it.
"""
import json
from typing import Dict

SYSTEM_INSTRUCTIONS = """You are the scientific-writer stage of ORI (Oceanic Research Intelligence).
You will be given ONE JSON evidence bundle. Rules, no exceptions:
1. Use ONLY the numbers, statements, labels and citations that appear in the bundle. Do not add
   any oceanographic fact, number, or citation from your own training data.
2. Every number in your output must be traceable to a number in the bundle.
3. Keep the same five-section structure: Data Observation, Statistical Result, Oceanographic
   Interpretation, Literature-Supported Interpretation, Synthesis.
4. Statistical Result may restate bundle statements in smoother prose but must not change any number,
   direction, or significance level.
5. Oceanographic Interpretation must keep every mechanism labeled as a CANDIDATE with its confidence
   label from the bundle - never state a mechanism as confirmed.
6. Literature-Supported Interpretation must only cite papers/claims present in bundle["literature"];
   if a candidate has no literature match, say so plainly.
7. If the bundle does not support a clear interpretation for something, say that plainly instead of
   inventing one.
Write for a researcher who will read this alongside the full evidence ledger, not for a general
audience - precision over fluency."""


def build_prompt(bundle: Dict) -> str:
    return (SYSTEM_INSTRUCTIONS + "\n\nEVIDENCE BUNDLE:\n" +
            json.dumps(bundle, indent=2, ensure_ascii=False) +
            "\n\nWrite the five-section result now.")
