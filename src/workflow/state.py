from __future__ import annotations

from typing import Any, Literal
from typing_extensions import TypedDict


class CatalogPipelineState(TypedDict, total=False):
    event_type: Literal[
        "new_document",
        "reprocess_product",
    ]

    run_id: str
    pdf_path: str
    document_id: str
    product_id: str

    page_count: int
    chunk_ids: list[str]
    fallback_pages: list[int]

    document_type: Literal[
        "catalog",
        "quotation",
        "unknown",
    ]

    vendor: dict[str, Any]
    products: list[dict[str, Any]]
    ppv_source_text: str
    ppv_valid: bool
    ppv_validation_warnings: list[str]
    ppv_results: list[dict[str, Any]]
    vlm_results: list[dict[str, Any]]
    consolidated_products: list[dict[str, Any]]

    processing_status: str
    warnings: list[str]
    document_excerpt: str
    classification_reason: str
    classification_confidence: float
    backlog_id: str
    backlog_status: str
    rejection_reasons: list[str]
    corrected_ppv_source_text: str
    corrected_ppv_results: list[dict[str, Any]]
    vlm_results: list[dict[str, Any]]
    vlm_valid: bool
    vlm_validation_warnings: list[str]
    visual_review_required: bool
    document_text: str