from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.extraction.document_chunker import chunk_document
from src.extraction.document_parser import parse_with_opendataloader
from src.extraction.file_importer import ImportedPDF, PDFFileImporter
from src.extraction.models import DocumentChunk, ParsedDocument
from src.extraction.opendataloader_normalizer import (
    normalize_opendataloader_output,
)
from src.extraction.pymupdf_fallback import (
    FallbackPage,
    parse_fallback_pages,
)
from src.extraction.quality_evaluator import (
    PageQuality,
    evaluate_document,
)
from src.qdrant_index import (
    create_qdrant_client,
    ensure_collection,
    get_collection_name,
    index_chunks,
)


@dataclass
class DocumentProcessingResult:
    imported_pdf: ImportedPDF
    parsed_document: ParsedDocument
    page_quality: list[PageQuality]
    fallback_pages: list[FallbackPage]
    chunks: list[DocumentChunk]
    indexed: bool

def process_document(
    pdf_path: str | Path,
    *,
    input_directory: str | Path = "data/input",
    output_directory: str | Path = "data/output",
    max_chunk_chars: int = 2500,
    index_in_qdrant: bool = True,
) -> DocumentProcessingResult:
    importer = PDFFileImporter(
        input_directory=input_directory,
    )

    imported_pdf = importer.import_pdf(pdf_path)

    parser_output = parse_with_opendataloader(
        imported_pdf,
        output_root=output_directory,
    )

    parsed_document = normalize_opendataloader_output(
        imported_pdf,
        parser_output,
    )

    page_quality = evaluate_document(parsed_document)

    fallback_page_numbers = [
        quality.page_number
        for quality in page_quality
        if quality.fallback_required
    ]

    fallback_pages = parse_fallback_pages(
        imported_pdf,
        fallback_page_numbers,
    )

    chunks = chunk_document(
        parsed_document,
        max_chars=max_chunk_chars,
    )

    indexed = False

    if index_in_qdrant and chunks:
        client = create_qdrant_client()
        collection_name = get_collection_name()

        ensure_collection(client, collection_name)

        index_chunks(
            client,
            collection_name,
            chunks,
        )

        indexed = True

    return DocumentProcessingResult(
        imported_pdf=imported_pdf,
        parsed_document=parsed_document,
        page_quality=page_quality,
        fallback_pages=fallback_pages,
        chunks=chunks,
        indexed=indexed,
    )