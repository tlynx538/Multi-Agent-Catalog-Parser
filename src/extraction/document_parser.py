from __future__ import annotations

from pathlib import Path

import opendataloader_pdf

from src.extraction.file_importer import ImportedPDF


class DocumentParsingError(Exception):
    """Raised when document parsing fails."""


def parse_with_opendataloader(
    imported_pdf: ImportedPDF,
    output_root: str | Path = "data/output",
) -> Path:
    output_directory = (
        Path(output_root)
        / imported_pdf.document_id
        / "opendataloader"
    )
    output_directory.mkdir(parents=True, exist_ok=True)

    try:
        opendataloader_pdf.convert(
            input_path=str(imported_pdf.staged_path),
            output_dir=str(output_directory),
            format="markdown,json",
        )
    except Exception as error:
        raise DocumentParsingError(
            f"OpenDataLoader failed for {imported_pdf.original_filename}"
        ) from error

    return output_directory.resolve()