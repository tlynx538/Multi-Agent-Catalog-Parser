# Setup guide

### Requirements

- Python 3.12 or newer; the repository pins the local interpreter to 3.12.
- `uv` for dependency installation and execution.
- Java 11 or newer on `PATH` for the installed OpenDataLoader PDF parser.
- A PDF you are permitted to process, up to 100 MB with the default importer settings.
- For the full graph: a reachable Qdrant instance and OpenRouter credentials.

From the repository root:

```bash
uv sync
java -version
```

### Parse a PDF without Qdrant or LLM calls

Replace the example path with your PDF. This runs the document-processing layer and prints the generated artifact paths:

```bash
uv run python - <<'PY'
from src.document_pipeline import process_document

result = process_document(
    "data/source_pdfs/sample-catalog.pdf",
    index_in_qdrant=False,
)

print("Document:", result.imported_pdf.document_id)
print("Pages:", result.parsed_document.number_of_pages)
print("Chunks:", len(result.chunks))
print("Markdown:", result.parsed_document.markdown_path)
print("JSON:", result.parsed_document.json_path)
print("Fallback pages:", [page.page_number for page in result.fallback_pages])
PY
```

### Run the full workflow

Create a `.env` file in the repository root and replace the placeholders:

```dotenv
QDRANT_URL=https://your-qdrant-endpoint
QDRANT_API_KEY=your-qdrant-api-key
QDRANT_COLLECTION=catalog_chunks

OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=your-model-id
ENABLE_LLM_CALLS=true
ENABLE_CLASSIFIER_LLM=false

MAX_LLM_REQUESTS_PER_RUN=3
MAX_LLM_REQUESTS_PER_DAY=20
```

The graph always enables Qdrant indexing for new documents, and its client requires both the URL and API key. Choose a model available to your OpenRouter account. Document text is sent to that provider during live extraction, and chunk text is stored in your configured Qdrant instance.

Invoke the graph from the repository root:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
from uuid import uuid4

from src.workflow.catalog_graph import build_catalog_graph

final_state = build_catalog_graph().invoke({
    "event_type": "new_document",
    "run_id": str(uuid4()),
    "pdf_path": "data/source_pdfs/sample-catalog.pdf",
    "processing_status": "received",
    "warnings": [],
})

output = Path("data/output/result.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(
    json.dumps(final_state, indent=2, ensure_ascii=False),
    encoding="utf-8",
)
print("Status:", final_state.get("processing_status"))
print("Result:", output)
PY
```

Alternatively, update `PDF_PATH` in [main.py](../main.py) and run `uv run python main.py` for a console summary. The script has a local example path and does not accept a PDF command-line argument.

The three-request default suits small experiments. Larger documents may exceed it because quotations can require one or more calls per page. Cached responses are reused before checking the request budget; disabling live calls does not provide a mock product extractor.

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ENABLE_LLM_CALLS` | `false` | Allow uncached model requests. |
| `ENABLE_CLASSIFIER_LLM` | `false` | Use the LLM classifier instead of local rules. |
| `OPENROUTER_API_KEY` | Required for live calls | Authenticate model requests. |
| `OPENROUTER_MODEL` | See the extractor/classifier source | Override the model for both operations. |
| `MAX_LLM_REQUESTS_PER_RUN` | `3` | Request limit per guard instance. |
| `MAX_LLM_REQUESTS_PER_DAY` | `20` | Daily limit recorded in a local ledger. |
| `QDRANT_URL` / `QDRANT_API_KEY` | Required for indexing | Connect to Qdrant. |
| `QDRANT_COLLECTION` | `catalog_chunks` | Collection used for document chunks. |
| `PPV_MAX_ATTEMPTS_PER_PAGE` | `1` | Maximum quotation extraction attempts per page. |
| `PPV_MAX_OUTPUT_TOKENS` | `6000` | Output-token limit per extraction request. |
| `PPV_CACHE_VERSION` | `ppv-v1` | Namespace for extraction cache entries. |
| `CATALOG_EXTRACTION_BATCH_SIZE` | `3` | Requested number of chunks per catalog batch. |

The request guard is shared at module scope, so its “per-run” counter currently lasts for the process's guard instance, even across multiple graph invocations. The local ledger is not a distributed rate limiter.

[Back to the README](../README.md)
