from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from src.workflow.catalog_graph import build_catalog_graph


PDF_PATH = (
    "data/source_pdfs/"
    "Price Information IFEX 2026 for Global Sourcing "
    "by Alex Nia. 15.04.2026 pdf.pdf"
)


def print_document_summary(
    final_state: dict[str, Any],
) -> None:
    print("\nGraph completed")
    print(f"Run ID: {final_state.get('run_id')}")
    print(
        f"Document ID: "
        f"{final_state.get('document_id')}"
    )
    print(
        f"Pages: "
        f"{final_state.get('page_count', 0)}"
    )
    print(
        f"Chunks: "
        f"{len(final_state.get('chunk_ids', []))}"
    )
    print(
        f"Fallback pages: "
        f"{final_state.get('fallback_pages', [])}"
    )


def print_classification(
    final_state: dict[str, Any],
) -> None:
    print("\nClassification")
    print(
        f"Type: "
        f"{final_state.get('document_type', 'unknown')}"
    )
    print(
        f"Reason: "
        f"{final_state.get(
            'classification_reason',
            'No reason provided',
        )}"
    )
    print(
        f"Confidence: "
        f"{final_state.get(
            'classification_confidence',
            0.0,
        )}"
    )


def print_vendor_information(
    final_state: dict[str, Any],
) -> None:
    vendor = final_state.get(
        "vendor_result",
        {},
    )

    print("\nVendor information")

    if not vendor:
        print("No vendor information was extracted.")
        return

    print(
        json.dumps(
            vendor,
            indent=2,
            ensure_ascii=False,
        )
    )


def print_extracted_products(
    final_state: dict[str, Any],
) -> None:
    products = final_state.get(
        "ppv_results",
        [],
    )

    print("\nExtracted products")
    print(f"Product count: {len(products)}")

    if not products:
        print("No products were extracted.")
        return

    for index, product in enumerate(
        products,
        start=1,
    ):
        print("\n" + "=" * 80)
        print(f"Product {index}")
        print(
            json.dumps(
                product,
                indent=2,
                ensure_ascii=False,
            )
        )


def print_ppv_validation(
    final_state: dict[str, Any],
) -> None:
    if "ppv_valid" not in final_state:
        return

    print("\nPPV validation")
    print(
        f"Valid: "
        f"{final_state.get('ppv_valid')}"
    )
    print(
        f"Validation warnings: "
        f"{final_state.get(
            'ppv_validation_warnings',
            [],
        )}"
    )

    backlog_id = final_state.get("backlog_id")

    if backlog_id:
        print(f"Backlog ID: {backlog_id}")
        print(
            f"Backlog status: "
            f"{final_state.get('backlog_status')}"
        )
    expected_skus = final_state.get(
    "ppv_expected_skus",
    [],
    )
    extracted_skus = final_state.get(
        "ppv_extracted_skus",
        [],
    )
    missing_skus = final_state.get(
        "ppv_missing_skus",
        [],
    )

    print("\nSKU coverage")
    print(f"Expected SKUs: {len(expected_skus)}")
    print(f"Extracted SKUs: {len(extracted_skus)}")
    print(f"Missing SKUs: {len(missing_skus)}")

    if missing_skus:
        print(f"Missing SKU list: {missing_skus}")

    print(
        "Quotation extraction warnings: "
        f"{final_state.get(
            'quotation_extraction_warnings',
            [],
        )}"
)


def print_vlm_processing(
    final_state: dict[str, Any],
) -> None:
    if "vlm_results" not in final_state:
        return

    print("\nVLM processing")
    print(
        f"VLM products: "
        f"{len(final_state.get('vlm_results', []))}"
    )
    print(
        f"Structurally valid: "
        f"{final_state.get('vlm_valid')}"
    )
    print(
        f"Visual review required: "
        f"{final_state.get(
            'visual_review_required'
        )}"
    )
    print(
        f"Validation warnings: "
        f"{final_state.get(
            'vlm_validation_warnings',
            [],
        )}"
    )


def print_final_status(
    final_state: dict[str, Any],
) -> None:
    print("\nFinal workflow state")
    print(
        f"Status: "
        f"{final_state.get('processing_status')}"
    )
    print(
        f"Warnings: "
        f"{final_state.get('warnings', [])}"
    )
    print(
    "Catalog extraction warnings: "
        f"{final_state.get(
            'catalog_extraction_warnings',
            [],
        )}"
    )


def main() -> None:
    graph = build_catalog_graph()

    initial_state: dict[str, Any] = {
        "event_type": "new_document",
        "run_id": str(uuid4()),
        "pdf_path": PDF_PATH,
        "processing_status": "received",
        "warnings": [],
    }

    final_state = graph.invoke(initial_state)

    print_document_summary(final_state)
    print_classification(final_state)
    print_vendor_information(final_state)
    print_extracted_products(final_state)

    document_type = final_state.get(
        "document_type",
        "unknown",
    )

    if document_type == "quotation":
        print_ppv_validation(final_state)

    elif document_type == "catalog":
        print_vlm_processing(final_state)

    else:
        print(
            "\nThe document requires manual "
            "classification review."
        )

    print_final_status(final_state)


if __name__ == "__main__":
    main()