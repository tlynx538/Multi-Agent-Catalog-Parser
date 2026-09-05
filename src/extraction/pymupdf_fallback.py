from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf4llm

from src.extraction.file_importer import ImportedPDF


class FallbackParsingError(Exception):
    """Raised when supplementary parsing fails."""


@dataclass
class FallbackPage:
    page_number: int
    markdown: str
    metadata: dict
    images: list
    words: list

def parse_fallback_pages(
    imported_pdf: ImportedPDF,
    page_numbers: list[int],
) -> list[FallbackPage]:
    if not page_numbers:
        return []

    invalid_pages = [
        page
        for page in page_numbers
        if page < 1
    ]

    if invalid_pages:
        raise ValueError(
            f"Page numbers must be 1-indexed: {invalid_pages}"
        )

    zero_indexed_pages = [
        page_number - 1
        for page_number in page_numbers
    ]

    try:
        raw_pages = pymupdf4llm.to_markdown(
            str(imported_pdf.staged_path),
            pages=zero_indexed_pages,
            page_chunks=True,
            extract_words=True,
            write_images=False,
            use_ocr=True,
            force_ocr=False,
            show_progress=True,
        )
    except Exception as error:
        raise FallbackParsingError(
            f"PyMuPDF4LLM failed for pages {page_numbers}"
        ) from error

    if not isinstance(raw_pages, list):
        raise FallbackParsingError(
            "Expected page-chunk output from PyMuPDF4LLM"
        )

    fallback_pages: list[FallbackPage] = []

    for requested_page, raw_page in zip(
        page_numbers,
        raw_pages,
        strict=True,
    ):
        fallback_pages.append(
            FallbackPage(
                page_number=requested_page,
                markdown=str(
                    raw_page.get("text", "")
                ).strip(),
                metadata=raw_page.get("metadata", {}),
                images=raw_page.get("images", []),
                words=raw_page.get("words", []),
            )
        )

    return fallback_pages