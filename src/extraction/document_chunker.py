from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from src.extraction.content_renderer import render_element
from src.extraction.models import (
    DocumentChunk,
    DocumentElement,
    ParsedDocument,
)


@dataclass
class RenderedBlock:
    text: str
    element_type: str
    section_title: str | None

def group_elements_by_page(
    elements: list[DocumentElement],
) -> dict[int, list[DocumentElement]]:
    pages: dict[int, list[DocumentElement]] = defaultdict(list)

    for element in elements:
        pages[element.page_number].append(element)

    return dict(sorted(pages.items()))

def build_page_blocks(
    elements: list[DocumentElement],
) -> tuple[list[RenderedBlock], list[str]]:
    blocks: list[RenderedBlock] = []
    image_references: list[str] = []
    current_section: str | None = None

    for element in elements:
        if element.element_type in {"image", "picture"}:
            if element.source:
                image_references.append(element.source)
            continue

        rendered_text = render_element(element).strip()

        if not rendered_text:
            continue

        if element.element_type == "heading":
            current_section = (element.content or "").strip() or None

        blocks.append(
            RenderedBlock(
                text=rendered_text,
                element_type=element.element_type,
                section_title=current_section,
            )
        )

    return blocks, image_references

def pack_blocks(
    blocks: list[RenderedBlock],
    max_chars: int,
) -> list[list[RenderedBlock]]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")

    groups: list[list[RenderedBlock]] = []
    current_group: list[RenderedBlock] = []
    current_size = 0

    for block in blocks:
        separator_size = 2 if current_group else 0
        proposed_size = (
            current_size
            + separator_size
            + len(block.text)
        )

        if current_group and proposed_size > max_chars:
            groups.append(current_group)
            current_group = []
            current_size = 0

        current_group.append(block)

        current_size += (
            (2 if current_size else 0)
            + len(block.text)
        )

    if current_group:
        groups.append(current_group)

    return groups

def chunk_document(
    document: ParsedDocument,
    max_chars: int = 2500,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    elements_by_page = group_elements_by_page(
        document.elements
    )

    for page_number, elements in elements_by_page.items():
        blocks, image_references = build_page_blocks(elements)
        block_groups = pack_blocks(blocks, max_chars=max_chars)

        for page_chunk_index, block_group in enumerate(
            block_groups,
            start=1,
        ):
            text = "\n\n".join(
                block.text for block in block_group
            )

            section_titles = [
                block.section_title
                for block in block_group
                if block.section_title
            ]

            section_title = (
                section_titles[0]
                if section_titles
                else None
            )

            element_types = list(
                dict.fromkeys(
                    block.element_type
                    for block in block_group
                )
            )

            chunk_id = (
                f"{document.document_id}"
                f"_page_{page_number}"
                f"_chunk_{page_chunk_index}"
            )

            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    text=text,
                    page_numbers=[page_number],
                    section_title=section_title,
                    element_types=element_types,
                    image_references=image_references,
                    source_file=document.source_path.name,
                    metadata={
                        "page_chunk_index": page_chunk_index,
                        "parser": "opendataloader",
                        "document_title": document.title,
                        "document_author": document.author,
                    },
                )
            )

    return chunks