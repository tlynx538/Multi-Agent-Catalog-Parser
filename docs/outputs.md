# Output and evidence guide

The returned graph state contains product records under `ppv_results`, along with the document ID, chunk IDs, classification, processing status, and declared validation fields. Here, PPV refers to the product/commercial extraction stage. Each product can contain:

| Field | Meaning |
| --- | --- |
| Product code, product name, and `variant` (see the linked models for exact field names) | Source product identity. |
| `source.page`, `source.raw_text` | Product-level source evidence. |
| `offers` | Price, currency, Incoterm, minimum quantity, and payment terms. |
| `packaging` | Packaging dimensions, unit, CBM, and container quantity. |
| `warnings`, `confidence` | Extraction uncertainty and review signals. |

See [the extraction models](../src/llm/ppv_extractor.py) for the current schema. Packaging dimensions must not be treated as product dimensions. Evidence is currently represented at product level, rather than as independently verified provenance for every field.

Parser artifacts are written under `data/output/<document_id>/opendataloader/`; staged PDFs go under `data/input/`. Model caches and request accounting use `data/llm_cache/` and `data/runtime/`. The workflow returns its state in memory; the example above explicitly saves that state to JSON.

[Back to the README](../README.md)
