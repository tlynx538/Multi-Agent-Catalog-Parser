from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


BoundingBox = tuple[float, float, float, float]


@dataclass
class DocumentElement:
    element_id: int | None
    element_type: str
    page_number: int
    content: str | None = None
    source: str | None = None
    bounding_box: BoundingBox | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    document_id: str
    source_path: Path
    markdown_path: Path
    json_path: Path
    markdown_text: str
    number_of_pages: int
    title: str | None
    author: str | None
    elements: list[DocumentElement]
    warnings: list[str] = field(default_factory=list)


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    text: str
    page_numbers: list[int]
    section_title: str | None
    element_types: list[str]
    image_references: list[str]
    source_file: str
    metadata: dict[str, Any] = field(default_factory=dict)