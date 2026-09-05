from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.extraction.file_importer import ImportedPDF
from src.extraction.models import (
    BoundingBox,
    DocumentElement,
    ParsedDocument,
)


class NormalizationError(Exception):
    """Raised when parser output cannot be normalized."""


def _find_single_file(
    directory: Path,
    pattern: str,
) -> Path:
    matches = list(directory.glob(pattern))

    if len(matches) != 1:
        raise NormalizationError(
            f"Expected one {pattern} file in {directory}, "
            f"found {len(matches)}"
        )

    return matches[0]


def _parse_bounding_box(
    value: Any,
) -> BoundingBox | None:
    if not isinstance(value, list) or len(value) != 4:
        return None

    try:
        return (
            float(value[0]),
            float(value[1]),
            float(value[2]),
            float(value[3]),
        )
    except (TypeError, ValueError):
        return None


def normalize_opendataloader_output(
    imported_pdf: ImportedPDF,
    output_directory: str | Path,
) -> ParsedDocument:
    output_directory = Path(output_directory)

    json_path = _find_single_file(output_directory, "*.json")
    markdown_path = _find_single_file(output_directory, "*.md")

    try:
        raw_document = json.loads(
            json_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise NormalizationError(
            f"Unable to read parser JSON: {json_path}"
        ) from error

    markdown_text = markdown_path.read_text(encoding="utf-8")

    elements: list[DocumentElement] = []
    warnings: list[str] = []

    for index, raw_element in enumerate(
        raw_document.get("kids", [])
    ):
        if not isinstance(raw_element, dict):
            warnings.append(
                f"Skipped non-object element at index {index}"
            )
            continue

        page_number = raw_element.get("page number")

        if not isinstance(page_number, int):
            warnings.append(
                f"Element at index {index} has no valid page number"
            )
            continue

        element_type = raw_element.get("type", "unknown")

        excluded_fields = {
            "id",
            "type",
            "page number",
            "bounding box",
            "content",
            "source",
        }

        metadata = {
            key: value
            for key, value in raw_element.items()
            if key not in excluded_fields
        }

        elements.append(
            DocumentElement(
                element_id=raw_element.get("id"),
                element_type=str(element_type),
                page_number=page_number,
                content=raw_element.get("content"),
                source=raw_element.get("source"),
                bounding_box=_parse_bounding_box(
                    raw_element.get("bounding box")
                ),
                metadata=metadata,
            )
        )

    return ParsedDocument(
        document_id=imported_pdf.document_id,
        source_path=imported_pdf.staged_path,
        markdown_path=markdown_path.resolve(),
        json_path=json_path.resolve(),
        markdown_text=markdown_text,
        number_of_pages=int(
            raw_document.get("number of pages", 0)
        ),
        title=raw_document.get("title"),
        author=raw_document.get("author"),
        elements=elements,
        warnings=warnings,
    )