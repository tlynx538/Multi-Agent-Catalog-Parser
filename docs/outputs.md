# Output and evidence guide

The returned graph state contains product records under `ppv_results`, along with the document ID, chunk IDs, classification, processing status, and declared validation fields. The `ppv_results` name is a project-internal label for extracted Supplier Item Master Data: product identity with commercial offers and packaging. It does not mean that all fields belong to Product Master Data. See the [glossary](glossary.md). Each product can contain:

| Field | Meaning |
| --- | --- |
| Product code, product name, and `variant` (see the linked models for exact field names) | Source product identity. |
| `source.page`, `source.raw_text` | Product-level source evidence. |
| `offers` | Commercial / Purchasing Data: quoted unit price, currency, Incoterm, minimum quantity, and payment terms. |
| `packaging` | Logistics / Packaging Data: packaging dimensions, unit, cubic volume (CBM), and container quantity. |
| `warnings`, `confidence` | Extraction uncertainty and review signals. |

See [the extraction models](../src/llm/ppv_extractor.py) for the current schema. Packaging dimensions must not be treated as product dimensions. Evidence is currently represented at product level, rather than as independently verified provenance for every field.

The current schema is a subset of the broader onboarding domain. It does not yet provide a complete product master, lead-time fields, weights, or a full packaging hierarchy. Commercial offers should remain separate from stable product attributes when mapping to downstream systems.

Parser artifacts are written under `data/output/<document_id>/opendataloader/`; staged PDFs go under `data/input/`. Model caches and request accounting use `data/llm_cache/` and `data/runtime/`. The workflow returns its state in memory; the [setup example](getting-started.md) explicitly saves that state to JSON.

[Back to the README](../README.md)
