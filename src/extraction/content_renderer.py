from __future__ import annotations

from typing import Any

from src.extraction.models import DocumentElement


def collect_nested_content(value: Any) -> list[str]:
    """
    Recursively collect values stored under `content` keys.

    This handles content nested inside table rows, cells and kids.
    """
    collected: list[str] = []

    if isinstance(value, dict):
        content = value.get("content")

        if isinstance(content, str) and content.strip():
            collected.append(content.strip())

        for key, nested_value in value.items():
            if key != "content":
                collected.extend(
                    collect_nested_content(nested_value)
                )

    elif isinstance(value, list):
        for item in value:
            collected.extend(collect_nested_content(item))

    return collected

def render_table_cell(cell: dict[str, Any]) -> str:
    values = collect_nested_content(cell)
    return " ".join(values).strip()

def render_table(element: DocumentElement) -> str:
    rows = element.metadata.get("rows", [])

    if not isinstance(rows, list) or not rows:
        return ""

    rendered_rows: list[list[str]] = []

    for row in rows:
        cells = row.get("cells", [])

        if not isinstance(cells, list):
            continue

        ordered_cells = sorted(
            cells,
            key=lambda cell: cell.get("column number", 0),
        )

        rendered_rows.append(
            [render_table_cell(cell) for cell in ordered_cells]
        )

    if not rendered_rows:
        return ""

    column_count = max(len(row) for row in rendered_rows)

    normalized_rows = [
        row + [""] * (column_count - len(row))
        for row in rendered_rows
    ]

    markdown_lines = [
        "| " + " | ".join(row) + " |"
        for row in normalized_rows
    ]

    separator = (
        "| "
        + " | ".join(["---"] * column_count)
        + " |"
    )

    markdown_lines.insert(1, separator)

    return "\n".join(markdown_lines)

def render_element(element: DocumentElement) -> str:
    if element.element_type == "table":
        return render_table(element)

    if element.element_type == "heading":
        content = (element.content or "").strip()
        return f"# {content}" if content else ""

    if element.element_type in {
        "paragraph",
        "list",
        "list item",
        "caption",
    }:
        return (element.content or "").strip()

    # Images are attached to chunk metadata rather than injected
    # into the embedding text.
    if element.element_type in {"image", "picture"}:
        return ""

    return (element.content or "").strip()