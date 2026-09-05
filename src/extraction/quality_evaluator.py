from __future__ import annotations

from dataclasses import dataclass

from src.extraction.content_renderer import render_element
from src.extraction.models import DocumentElement, ParsedDocument


@dataclass
class PageQuality:
    page_number: int
    text_characters: int
    heading_count: int
    paragraph_count: int
    table_count: int
    image_count: int
    status: str
    fallback_required: bool
    fallback_reason: str | None

def evaluate_page(
    page_number: int,
    elements: list[DocumentElement],
) -> PageQuality:
    rendered_parts = [
        render_element(element).strip()
        for element in elements
        if element.element_type not in {"image", "picture"}
    ]

    text = "\n".join(
        part for part in rendered_parts if part
    )

    heading_count = sum(
        element.element_type == "heading"
        for element in elements
    )

    paragraph_count = sum(
        element.element_type == "paragraph"
        for element in elements
    )

    table_count = sum(
        element.element_type == "table"
        for element in elements
    )

    image_count = sum(
        element.element_type in {"image", "picture"}
        for element in elements
    )

    text_characters = len(text.strip())

    fallback_required = False
    fallback_reason: str | None = None

    if text_characters == 0:
        status = "empty"
        fallback_required = True
        fallback_reason = "No usable text was extracted"

    elif (
        text_characters < 80
        and table_count == 0
        and image_count > 0
    ):
        status = "sparse"
        fallback_required = True
        fallback_reason = (
            "Image-bearing page contains very little extracted text"
        )

    else:
        status = "usable"

    return PageQuality(
        page_number=page_number,
        text_characters=text_characters,
        heading_count=heading_count,
        paragraph_count=paragraph_count,
        table_count=table_count,
        image_count=image_count,
        status=status,
        fallback_required=fallback_required,
        fallback_reason=fallback_reason,
    )

def evaluate_document(
    document: ParsedDocument,
) -> list[PageQuality]:
    pages: dict[int, list[DocumentElement]] = {
        page_number: []
        for page_number in range(
            1,
            document.number_of_pages + 1,
        )
    }

    for element in document.elements:
        pages.setdefault(element.page_number, []).append(element)

    return [
        evaluate_page(page_number, elements)
        for page_number, elements in sorted(pages.items())
    ]
