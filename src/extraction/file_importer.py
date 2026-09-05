from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path



class PDFImportError(Exception):
    """Raised when a PDF cannot be imported."""


@dataclass(frozen=True)
class ImportedPDF:
    document_id: str
    original_path: Path
    staged_path: Path
    original_filename: str
    file_size_bytes: int
    sha256: str


class PDFFileImporter:
    def __init__(
        self,
        input_directory: str | Path = "data/input",
        max_file_size_mb: int = 100,
    ) -> None:
        self.input_directory = Path(input_directory)
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    def import_pdf(self, file_path: str | Path) -> ImportedPDF:
        source_path = Path(file_path).expanduser().resolve()

        self._validate_file(source_path)

        sha256 = self._calculate_sha256(source_path)
        document_id = f"doc_{sha256[:16]}"

        document_directory = self.input_directory / document_id
        document_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        staged_path = document_directory / source_path.name

        if not staged_path.exists():
            shutil.copy2(source_path, staged_path)
        else:
            staged_hash = self._calculate_sha256(staged_path)

            if staged_hash != sha256:
                raise PDFImportError(
                    f"Staged file has unexpected content: {staged_path}"
                )

        return ImportedPDF(
            document_id=document_id,
            original_path=source_path,
            staged_path=staged_path.resolve(),
            original_filename=source_path.name,
            file_size_bytes=source_path.stat().st_size,
            sha256=sha256,
        )

    def _validate_file(self, file_path: Path) -> None:
        if not file_path.exists():
            raise PDFImportError(f"File does not exist: {file_path}")

        if not file_path.is_file():
            raise PDFImportError(f"Path is not a file: {file_path}")

        if file_path.suffix.lower() != ".pdf":
            raise PDFImportError(
                f"Only PDF files are supported: {file_path.name}"
            )

        file_size = file_path.stat().st_size

        if file_size == 0:
            raise PDFImportError(f"PDF is empty: {file_path.name}")

        if file_size > self.max_file_size_bytes:
            size_mb = file_size / (1024 * 1024)
            limit_mb = self.max_file_size_bytes / (1024 * 1024)

            raise PDFImportError(
                f"PDF is {size_mb:.2f} MB; limit is {limit_mb:.2f} MB"
            )

        # Checking the extension alone is insufficient. Most valid PDFs begin
        # with the PDF signature, although some may contain a short preamble.
        with file_path.open("rb") as pdf_file:
            header = pdf_file.read(1024)

        if b"%PDF-" not in header:
            raise PDFImportError(
                f"File does not contain a valid PDF signature: {file_path.name}"
            )

    @staticmethod
    def _calculate_sha256(file_path: Path) -> str:
        digest = hashlib.sha256()

        with file_path.open("rb") as pdf_file:
            for block in iter(lambda: pdf_file.read(1024 * 1024), b""):
                digest.update(block)

        return digest.hexdigest()