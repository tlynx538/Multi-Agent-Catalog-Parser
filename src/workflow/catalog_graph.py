# src/workflow/catalog_graph.py
# Final page-aware extraction with opt-in missing-SKU completion retries.
from __future__ import annotations

import os
import re
from typing import Literal

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from src.document_pipeline import process_document
from src.llm.document_classifier import (
    classify_document_locally,
    classify_document_with_llm,
)
from src.llm.ppv_extractor import (
    PPVExtraction,
    extract_ppv_with_llm,
    find_expected_skus,
    normalize_sku,
    validate_ppv_extraction,
)
from src.llm.request_guard import LLMRequestGuard
from src.workflow.state import CatalogPipelineState
from src.pim.backlog_store import BacklogStore
from src.llm.vlm_enrichment import (
    VLMProductResult,
    create_mock_vlm_results,
    validate_vlm_results,
)

load_dotenv()

_request_guard = LLMRequestGuard()
_backlog_store = BacklogStore()


def reconstruct_chunks_from_document_text(
    document_text: str,
) -> list[dict]:
    """Recover serialized chunks if LangGraph state omitted the list."""
    header_pattern = re.compile(
        r"\[Chunk ID:\s*(?P<chunk_id>[^\]]+)\]\n"
        r"\[Pages:\s*(?P<pages>[^\n]+)\]\n"
    )
    matches = list(header_pattern.finditer(document_text))
    recovered: list[dict] = []

    for index, match in enumerate(matches):
        content_start = match.end()
        content_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(document_text)
        )
        page_numbers = [
            int(value)
            for value in re.findall(r"\d+", match.group("pages"))
        ]
        text = document_text[content_start:content_end].strip()
        recovered.append(
            {
                "chunk_id": match.group("chunk_id").strip(),
                "page_numbers": page_numbers,
                "text": text,
            }
        )

    return recovered

def route_event(
    state: CatalogPipelineState,
) -> Literal[
    "process_new_document",
    "load_backlog_product",
]:
    event_type = state.get("event_type")

    if event_type == "new_document":
        return "process_new_document"

    if event_type == "reprocess_product":
        return "load_backlog_product"

    raise ValueError(
        f"Unsupported event type: {event_type}"
    )


def process_new_document(
    state: CatalogPipelineState,
) -> dict:
    pdf_path = state.get("pdf_path")

    if not pdf_path:
        raise ValueError(
            "pdf_path is required for a new-document event"
        )

    result = process_document(
        pdf_path,
        max_chunk_chars=2500,
        index_in_qdrant=True,
    )

    fallback_page_numbers = [
        page.page_number
        for page in result.fallback_pages
    ]

    document_text = "\n\n".join(
    (
        f"[Chunk ID: {chunk.chunk_id}]\n"
        f"[Pages: {chunk.page_numbers}]\n"
        f"{chunk.text}"
    )
        for chunk in result.chunks
    )

    document_excerpt = document_text[:8000]

    document_chunks = [
        {
            "chunk_id": chunk.chunk_id,
            "page_numbers": list(chunk.page_numbers),
            "text": chunk.text,
        }
        for chunk in result.chunks
    ]

    return {
    "document_id": result.imported_pdf.document_id,
    "page_count": result.parsed_document.number_of_pages,
    "chunk_ids": [
        chunk.chunk_id
        for chunk in result.chunks
    ],
    "fallback_pages": fallback_page_numbers,
    "document_chunks": document_chunks,
    "document_text": document_text,
    "document_excerpt": document_excerpt,
    "processing_status": "document_processed",
}


def load_backlog_product(
    state: CatalogPipelineState,
) -> dict:
    backlog_id = state.get("backlog_id")

    if not backlog_id:
        raise ValueError(
            "backlog_id is required for reprocessing"
        )

    record = _backlog_store.load_record(
        backlog_id
    )

    return {
        "backlog_id": record["backlog_id"],
        "document_id": record["document_id"],
        "chunk_ids": record["chunk_ids"],
        "ppv_source_text": record["source_text"],
        "ppv_results": record["ppv_results"],
        "rejection_reasons": record["rejection_reasons"],
        "backlog_status": record["status"],
        "processing_status": "backlog_product_loaded",
        "warnings": record["rejection_reasons"],
    }


def classify_document(
    state: CatalogPipelineState,
) -> dict:
    document_excerpt = state.get(
        "document_excerpt",
        "",
    ).strip()

    if not document_excerpt:
        return {
            "document_type": "unknown",
            "classification_reason": (
                "No document content was available "
                "for classification."
            ),
            "classification_confidence": 0.0,
            "processing_status": "document_classified",
        }

    use_live_model = (
        os.getenv(
            "ENABLE_CLASSIFIER_LLM",
            "false",
        ).lower()
        == "true"
    )

    if use_live_model:
        classification = classify_document_with_llm(
            document_excerpt,
            _request_guard,
        )
    else:
        classification = classify_document_locally(
            document_excerpt
        )

    return {
        "document_type": classification.document_type,
        "classification_reason": classification.reason,
        "classification_confidence": (
            classification.confidence
        ),
        "processing_status": "document_classified",
    }


def route_document_type(
    state: CatalogPipelineState,
) -> Literal[
    "prepare_catalog",
    "prepare_quotation",
    "handle_unknown_document",
]:
    document_type = state.get(
        "document_type",
        "unknown",
    )

    if document_type == "catalog":
        return "prepare_catalog"

    if document_type == "quotation":
        return "prepare_quotation"

    return "handle_unknown_document"


def prepare_catalog(
    state: CatalogPipelineState,
) -> dict:
    return {
        "processing_status": "catalog_ready_for_enrichment",
    }


def prepare_quotation(
    state: CatalogPipelineState,
) -> dict:
    return {
        "processing_status": (
            "quotation_ready_for_ppv_extraction"
        ),
    }


def handle_unknown_document(
    state: CatalogPipelineState,
) -> dict:
    existing_warnings = state.get("warnings", [])

    return {
        "processing_status": "document_requires_review",
        "warnings": [
            *existing_warnings,
            "Document type could not be determined",
        ],
    }


def extract_ppv(
    state: CatalogPipelineState,
) -> dict:
    corrected_source = state.get("ppv_source_text", "").strip()
    chunks = state.get("document_chunks", [])

    # Backlog corrections already represent a targeted product payload,
    # so they intentionally remain a single extraction unit.
    if corrected_source:
        extraction = extract_ppv_with_llm(
            corrected_source,
            _request_guard,
        )
        return {
            "vendor_result": extraction.vendor.model_dump(),
            "ppv_results": [
                product.model_dump()
                for product in extraction.products
            ],
            "quotation_extraction_warnings": [],
            "processing_status": "ppv_extracted",
        }

    if not chunks:
        fallback_text = (
            state.get("document_text")
            or state.get("document_excerpt", "")
        ).strip()
        if fallback_text:
            chunks = reconstruct_chunks_from_document_text(
                fallback_text
            )
            if not chunks:
                chunks = [
                    {
                        "chunk_id": "document_fallback",
                        "page_numbers": [],
                        "text": fallback_text,
                    }
                ]

    if not chunks:
        raise ValueError(
            "No source text is available for PPV extraction"
        )

    # Reassemble chunks by page before inference. This prevents a large
    # table from being split across independent model calls.
    page_groups: dict[int, list[dict]] = {}
    unpaged_chunks: list[dict] = []

    for chunk in chunks:
        page_numbers = chunk.get("page_numbers", [])
        if page_numbers:
            page_number = int(page_numbers[0])
            page_groups.setdefault(page_number, []).append(chunk)
        else:
            unpaged_chunks.append(chunk)

    extraction_units: list[tuple[list[int], list[dict]]] = [
        ([page_number], page_groups[page_number])
        for page_number in sorted(page_groups)
    ]
    if unpaged_chunks:
        extraction_units.append(([], unpaged_chunks))

    all_products: list[dict] = []
    vendor_candidates: list[dict] = []
    extraction_warnings: list[str] = []

    for pages, page_chunks in extraction_units:
        page_text = "\n\n".join(
            chunk.get("text", "")
            for chunk in page_chunks
            if chunk.get("text", "").strip()
        ).strip()

        if not page_text:
            extraction_warnings.append(
                f"No extractable text was available for pages {pages}"
            )
            continue

        page_input = f"[Pages: {pages}]\n{page_text}"
        expected_page_skus = find_expected_skus(page_input)
        max_attempts = max(
            1,
            int(os.getenv("PPV_MAX_ATTEMPTS_PER_PAGE", "1")),
        )
        products_by_sku: dict[str, dict] = {}
        products_without_sku: list[dict] = []
        missing_page_skus = list(expected_page_skus)
        previous_missing_count = len(missing_page_skus)

        for attempt in range(1, max_attempts + 1):
            target_skus = (
                missing_page_skus
                if expected_page_skus
                else []
            )
            attempt_input = (
                f"{page_input}\n\n"
                "<completion_request>\n"
                f"Attempt: {attempt} of {max_attempts}\n"
                "Return one complete product record for every SKU "
                "listed below. Do not return records for SKUs that "
                "are not listed. Do not return an empty products "
                "array when these SKUs are present in the page.\n"
                f"Required SKUs: {target_skus}\n"
                "</completion_request>"
            )

            extraction = extract_ppv_with_llm(
                attempt_input,
                _request_guard,
            )

            attempt_products = [
                product.model_dump()
                for product in extraction.products
            ]

            for product in attempt_products:
                vendor_sku = product.get("vendor_sku")
                if vendor_sku:
                    normalized_sku = normalize_sku(vendor_sku)
                    if (
                        not expected_page_skus
                        or normalized_sku in expected_page_skus
                    ):
                        products_by_sku[normalized_sku] = product
                elif not expected_page_skus:
                    products_without_sku.append(product)

            vendor = extraction.vendor.model_dump()
            if any(
                vendor.get(field)
                for field in (
                    "vendor_name",
                    "legal_name",
                    "website",
                    "email",
                    "phone",
                    "address",
                )
            ):
                vendor_candidates.append(vendor)

            missing_page_skus = [
                sku
                for sku in expected_page_skus
                if sku not in products_by_sku
            ]

            if not missing_page_skus:
                break

            current_missing_count = len(missing_page_skus)
            if (
                attempt > 1
                and current_missing_count >= previous_missing_count
            ):
                extraction_warnings.append(
                    f"No SKU coverage progress for pages {pages} "
                    f"on attempt {attempt}"
                )
            previous_missing_count = current_missing_count

        page_products = [
            products_by_sku[sku]
            for sku in expected_page_skus
            if sku in products_by_sku
        ]
        page_products.extend(products_without_sku)

        if missing_page_skus:
            raise ValueError(
                f"Incomplete PPV extraction for pages {pages} after "
                f"{max_attempts} attempts: expected "
                f"{len(expected_page_skus)} SKUs, extracted "
                f"{len(products_by_sku)}; missing "
                + ", ".join(missing_page_skus)
                + ". Raw responses are cached."
            )

        all_products.extend(page_products)

        if not page_products:
            extraction_warnings.append(
                f"No products were extracted from pages {pages}"
            )

    def vendor_score(candidate: dict) -> tuple[float, int]:
        populated_fields = sum(
            bool(candidate.get(field))
            for field in (
                "vendor_name",
                "legal_name",
                "website",
                "email",
                "phone",
                "address",
                "country_code",
            )
        )
        return (
            float(candidate.get("confidence") or 0.0),
            populated_fields,
        )

    vendor_result = (
        max(vendor_candidates, key=vendor_score)
        if vendor_candidates
        else {}
    )

    return {
        "vendor_result": vendor_result,
        "ppv_results": all_products,
        "quotation_extraction_warnings": extraction_warnings,
        "processing_status": "ppv_extracted",
    }


def validate_ppv(
    state: CatalogPipelineState,
) -> dict:
    source_text = (
        state.get("ppv_source_text")
        or state.get("document_text")
        or state.get("document_excerpt", "")
    ).strip()

    extraction = PPVExtraction(
        schema_version="ppv-mini-1.0",
        vendor=state.get("vendor_result", {}),
        products=state.get("ppv_results", []),
    )

    validation = validate_ppv_extraction(
        source_text,
        extraction,
    )

    return {
        "ppv_valid": validation.valid,
        "ppv_expected_skus": validation.expected_skus,
        "ppv_extracted_skus": validation.extracted_skus,
        "ppv_missing_skus": validation.missing_skus,
        "ppv_validation_warnings": (
            validation.warnings
        ),
        "processing_status": "ppv_validated",
    }


def route_ppv_validation(
    state: CatalogPipelineState,
) -> Literal[
    "publish_ppv_review",
    "send_to_backlog",
]:
    if state.get("ppv_valid", False):
        return "publish_ppv_review"

    return "send_to_backlog"


def publish_ppv_review(
    state: CatalogPipelineState,
) -> dict:
    return {
        "processing_status": "awaiting_pim_ppv_review",
    }


def send_to_backlog(
    state: CatalogPipelineState,
) -> dict:
    existing_warnings = state.get("warnings", [])
    validation_warnings = state.get(
        "ppv_validation_warnings",
        [],
    )

    all_warnings = [
        *existing_warnings,
        *validation_warnings,
    ]

    run_id = state.get("run_id")
    document_id = state.get("document_id")

    if not run_id or not document_id:
        raise ValueError(
            "run_id and document_id are required "
            "to create a backlog record"
        )

    source_text = (
        state.get("ppv_source_text")
        or state.get("document_text")
        or state.get("document_excerpt", "")
    )

    record = _backlog_store.create_record(
        run_id=run_id,
        document_id=document_id,
        chunk_ids=state.get("chunk_ids", []),
        source_text=source_text,
        ppv_results=state.get("ppv_results", []),
        rejection_reasons=validation_warnings,
    )

    return {
        "backlog_id": record["backlog_id"],
        "backlog_status": record["status"],
        "rejection_reasons": (
            record["rejection_reasons"]
        ),
        "processing_status": "ppv_rejected_to_backlog",
        "warnings": all_warnings,
    }

def route_loaded_backlog(
    state: CatalogPipelineState,
) -> Literal[
    "apply_backlog_corrections",
    "await_supplier_data",
]:
    if state.get("corrected_ppv_results"):
        return "apply_backlog_corrections"

    return "await_supplier_data"

def apply_backlog_corrections(
    state: CatalogPipelineState,
) -> dict:
    corrected_results = state.get(
        "corrected_ppv_results",
        [],
    )

    corrected_source = (
        state.get("corrected_ppv_source_text")
        or state.get("ppv_source_text", "")
    )

    return {
        "ppv_source_text": corrected_source,
        "ppv_results": corrected_results,
        "processing_status": (
            "backlog_corrections_applied"
        ),
    }


def await_supplier_data(
    state: CatalogPipelineState,
) -> dict:
    return {
        "processing_status": "awaiting_supplier_data",
    }

def run_vlm_enrichment(
    state: CatalogPipelineState,
) -> dict:
    results = create_mock_vlm_results()

    return {
        "vlm_results": [
            result.model_dump()
            for result in results
        ],
        "processing_status": "vlm_enrichment_completed",
    }


def validate_vlm(
    state: CatalogPipelineState,
) -> dict:
    results = [
        VLMProductResult.model_validate(result)
        for result in state.get("vlm_results", [])
    ]

    validation = validate_vlm_results(results)

    return {
        "vlm_valid": validation.valid,
        "visual_review_required": (
            validation.review_required
        ),
        "vlm_validation_warnings": (
            validation.warnings
        ),
        "processing_status": "vlm_validated",
    }


def publish_visual_review(
    state: CatalogPipelineState,
) -> dict:
    existing_warnings = state.get("warnings", [])
    validation_warnings = state.get(
        "vlm_validation_warnings",
        [],
    )

    return {
        "processing_status": "awaiting_pim_visual_review",
        "warnings": [
            *existing_warnings,
            *validation_warnings,
        ],
    }

def extract_catalog_products(
    state: CatalogPipelineState,
) -> dict:
    chunks = state.get("document_chunks", [])

    if not chunks:
        fallback_text = (
            state.get("document_text")
            or state.get("document_excerpt", "")
        ).strip()
        if fallback_text:
            chunks = [
                {
                    "chunk_id": "document_fallback",
                    "page_numbers": [],
                    "text": fallback_text,
                }
            ]

    if not chunks:
        raise ValueError(
            "No document text is available for product extraction"
        )

    batch_size = max(
        1,
        int(os.getenv("CATALOG_EXTRACTION_BATCH_SIZE", "3")),
    )

    all_products: list[dict] = []
    vendor_candidates: list[dict] = []
    extraction_warnings: list[str] = []

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        batch_number = (start // batch_size) + 1
        batch_text = "\n\n".join(
            (
                f"[Chunk ID: {chunk.get('chunk_id')}]\n"
                f"[Pages: {chunk.get('page_numbers', [])}]\n"
                f"{chunk.get('text', '')}"
            )
            for chunk in batch
        ).strip()

        if not batch_text:
            extraction_warnings.append(
                f"Catalog batch {batch_number} contained no text"
            )
            continue

        extraction = extract_ppv_with_llm(
            batch_text,
            _request_guard,
        )
        batch_products = [
            product.model_dump()
            for product in extraction.products
        ]
        all_products.extend(batch_products)

        if not batch_products:
            extraction_warnings.append(
                f"No products were extracted from catalog batch "
                f"{batch_number}"
            )

        vendor = extraction.vendor.model_dump()
        if any(
            vendor.get(field)
            for field in (
                "vendor_name",
                "legal_name",
                "website",
                "email",
                "phone",
                "address",
            )
        ):
            vendor_candidates.append(vendor)

    def vendor_score(candidate: dict) -> tuple[float, int]:
        populated_fields = sum(
            bool(candidate.get(field))
            for field in (
                "vendor_name",
                "legal_name",
                "website",
                "email",
                "phone",
                "address",
                "country_code",
            )
        )
        return (
            float(candidate.get("confidence") or 0.0),
            populated_fields,
        )

    vendor_result = (
        max(vendor_candidates, key=vendor_score)
        if vendor_candidates
        else {}
    )

    return {
        "vendor_result": vendor_result,
        "ppv_results": all_products,
        "catalog_extraction_warnings": extraction_warnings,
        "processing_status": "catalog_products_extracted",
    }

def build_catalog_graph():
    builder = StateGraph(CatalogPipelineState)

    # Nodes
    builder.add_node(
        "process_new_document",
        process_new_document,
    )
    builder.add_node(
        "load_backlog_product",
        load_backlog_product,
    )
    builder.add_node(
        "classify_document",
        classify_document,
    )
    builder.add_node(
        "prepare_catalog",
        prepare_catalog,
    )
    builder.add_node(
        "prepare_quotation",
        prepare_quotation,
    )
    builder.add_node(
        "handle_unknown_document",
        handle_unknown_document,
    )
    builder.add_node(
        "extract_ppv",
        extract_ppv,
    )
    builder.add_node(
        "validate_ppv",
        validate_ppv,
    )
    builder.add_node(
        "publish_ppv_review",
        publish_ppv_review,
    )
    builder.add_node(
        "send_to_backlog",
        send_to_backlog,
    )
    builder.add_node(
        "run_vlm_enrichment",
        run_vlm_enrichment,
    )
    builder.add_node(
        "validate_vlm",
        validate_vlm,
    )
    builder.add_node(
        "publish_visual_review",
        publish_visual_review,
    )
    builder.add_node(
        "extract_catalog_products",
        extract_catalog_products,
    )
    builder.add_node(
        "apply_backlog_corrections",
        apply_backlog_corrections,
    )
    builder.add_node(
        "await_supplier_data",
        await_supplier_data,
    )

    # Entry routing
    builder.add_conditional_edges(
        START,
        route_event,
        {
            "process_new_document": "process_new_document",
            "load_backlog_product": "load_backlog_product",
        },
    )

    # New-document workflow
    builder.add_edge(
        "process_new_document",
        "classify_document",
    )

    builder.add_conditional_edges(
        "classify_document",
        route_document_type,
        {
            "prepare_catalog": "prepare_catalog",
            "prepare_quotation": "prepare_quotation",
            "handle_unknown_document": (
                "handle_unknown_document"
            ),
        },
    )
    # Catalog branch. Keep this strictly sequential: allowing both
    # prepare_catalog -> run_vlm_enrichment and prepare_catalog ->
    # extract_catalog_products would create concurrent writes to the
    # single-value processing_status channel.
    builder.add_edge(
        "prepare_catalog",
        "extract_catalog_products",
    )
    builder.add_edge(
        "extract_catalog_products",
        "run_vlm_enrichment",
    )
    builder.add_edge(
        "run_vlm_enrichment",
        "validate_vlm",
    )
    builder.add_edge(
        "validate_vlm",
        "publish_visual_review",
    )
    builder.add_edge(
        "publish_visual_review",
        END,
    )

    # Quotation/PPV branch
    builder.add_edge(
        "prepare_quotation",
        "extract_ppv",
    )
    builder.add_edge(
        "extract_ppv",
        "validate_ppv",
    )

    builder.add_conditional_edges(
        "validate_ppv",
        route_ppv_validation,
        {
            "publish_ppv_review": "publish_ppv_review",
            "send_to_backlog": "send_to_backlog",
        },
    )

    builder.add_edge(
        "publish_ppv_review",
        END,
    )
    builder.add_edge(
        "send_to_backlog",
        END,
    )

    # Other terminal paths
    builder.add_edge(
        "handle_unknown_document",
        END,
    )

    builder.add_conditional_edges(
        "load_backlog_product",
        route_loaded_backlog,
        {
            "apply_backlog_corrections": (
                "apply_backlog_corrections"
            ),
            "await_supplier_data": "await_supplier_data",
        },
    )

    builder.add_edge(
        "apply_backlog_corrections",
        "validate_ppv",
    )
    builder.add_edge(
        "await_supplier_data",
        END,
    )

    return builder.compile()