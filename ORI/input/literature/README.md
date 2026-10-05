# Literature store (Phase 5)

`papers.json` is the only thing Phase 5 reads. It starts empty. ORI never adds a paper or a
claim to this file itself - you (or a checked import) do, so every citation ORI ever produces
traces back to something a person actually verified against the paper.

## Two ways to add papers

**A. Zotero CSV export (metadata only, offline, no API key needed)**
In Zotero: select items or a collection -> right-click -> *Export Items...* -> CSV.
Then, from the ORI root:
```python
from literature.zotero_csv import from_zotero_csv
from literature.store import load_store, save_store
import config

new_papers = from_zotero_csv("your_export.csv")
existing, _ = load_store(config.LITERATURE_STORE_PATH)
save_store(existing + new_papers, config.LITERATURE_STORE_PATH)
```
This gives you title/authors/year/tags as Zotero tags -> `region_tags`. It does NOT give you
claims - Zotero has no per-sentence data - so every imported paper starts with an empty
`claims` list and will not match anything until you add claims by hand (below).

**B. Edit `papers.json` directly.** Format:
```json
{
  "papers": [
    {
      "zotero_key": "ABC123",
      "title": "Full paper title",
      "authors": "Naqvi et al.",
      "year": 2006,
      "region_tags": ["Arabian Sea"],
      "claims": [
        {
          "claim": "A short paraphrase in your own words - not a copied sentence.",
          "source_location": "p.4, section 3.2",
          "region_tags": ["Arabian Sea"],
          "process_tags": ["bio_o2_consumption_n_cycle"],
          "parameter_tags": ["DO", "nitrite"]
        }
      ]
    }
  ]
}
```

## Tags that actually connect a claim to ORI's output

- `process_tags`: match these to the `process_key` values in `knowledge/library.py`
  (e.g. `bio_o2_consumption_n_cycle`, `respiration_linked_acidification`,
  `conservative_mixing_gradient`, `upwelling_influenced_water`). This is what lets a claim
  reach `MECHANISTIC` or `STRONG` in the Phase 5 report.
- `parameter_tags`: use the canonical keys from `config.PARAMETERS` (salinity, temperature, pH,
  nitrate, nitrite, ammonia, phosphate, silicate, DO).
- `region_tags`: free text (e.g. "Wadge Bank", "Gulf of Mannar", "Arabian Sea"). Set
  `config.LITERATURE_REGION_TAGS` to the region(s) relevant to your dataset so region-specific
  claims can reach `STRONG`.

A claim with no tags at all can never be matched - `store.py` will flag it as a validation error
when ORI loads the file, rather than silently ignoring it.

## Why claims, not PDFs

ORI does not read your PDFs and does not paraphrase them automatically. That is a deliberate
choice: a claim only enters the store when a person has actually read that part of the paper and
written down, in their own words, what it says - with the exact page or section so it can be
checked. This is slower than "just point it at a folder of PDFs", but it is the only way every
number and every citation Phase 6 (the writer) produces can be traced back to something real.
