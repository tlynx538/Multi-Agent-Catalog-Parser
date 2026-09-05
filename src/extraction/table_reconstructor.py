# src/extraction/table_reconstructor.py
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


CellOrigin = Literal[
    "explicit",
    "row_span",
    "column_span",
    "row_and_column_span",
    "forward_fill",
    "missing",
]


SKU_PATTERN = re.compile(
    r"\b[A-Z]{1,6}[ -]?\d[A-Z0-9 ._/-]{1,40}\b",
    flags=re.IGNORECASE,
)

DEFAULT_INHERITABLE_HEADER_PATTERNS = (
    "vendor",
    "supplier",
    "product family",
    "collection",
    "category",
    "material",
    "finish",
    "currency",
    "incoterm",
    "packaging type",
    "package type",
    "image",
)

NEVER_FORWARD_FILL_HEADER_PATTERNS = (
    "sku",
    "model",
    "item code",
    "product code",
    "product name",
    "description",
    "price",
    "quantity",
    "moq",
    "minimum",
    "length",
    "width",
    "height",
    "dimension",
    "weight",
    "cbm",
    "40hq",
    "container",
)


@dataclass(frozen=True)
class CellProvenance:
    origin: CellOrigin
    source_row: int | None
    source_column: int | None
    source_cell_id: str | int | None = None
    inherited_from_row: int | None = None


@dataclass(frozen=True)
class ReconstructedCell:
    value: str | None
    provenance: CellProvenance


@dataclass
class ReconstructedProductRow:
    row_id: str
    document_id: str
    table_id: str
    page_number: int | None
    source_row: int
    values: dict[str, str | None]
    cells: dict[str, ReconstructedCell]
    image_references: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReconstructedTable:
    table_id: str
    page_number: int | None
    headers: list[str]
    header_row_count: int
    rows: list[ReconstructedProductRow]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReconstructedDocumentTables:
    document_id: str
    source_json_path: str
    tables: list[ReconstructedTable]
    warnings: list[str] = field(default_factory=list)

    @property
    def product_rows(self) -> list[ReconstructedProductRow]:
        return [row for table in self.tables for row in table.rows]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_json_path": self.source_json_path,
            "tables": [table.to_dict() for table in self.tables],
            "warnings": self.warnings,
        }


def _node_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node.strip()
    if isinstance(node, list):
        parts = [_node_text(item) for item in node]
        return " ".join(part for part in parts if part).strip()
    if not isinstance(node, dict):
        return str(node).strip()

    direct = node.get("content")
    if direct not in (None, ""):
        return _node_text(direct)

    parts = []
    for key in ("kids", "cells", "rows"):
        if key in node:
            value = _node_text(node[key])
            if value:
                parts.append(value)
    return " ".join(parts).strip()


def _cell_image_references(cell: Any) -> list[str]:
    references: list[str] = []
    if isinstance(cell, list):
        for item in cell:
            references.extend(_cell_image_references(item))
    elif isinstance(cell, dict):
        if cell.get("type") == "image" and cell.get("source"):
            references.append(str(cell["source"]))
        for key in ("kids", "cells", "rows"):
            if key in cell:
                references.extend(_cell_image_references(cell[key]))
    return list(dict.fromkeys(references))


def _positive_int(value: Any, default: int = 1) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _zero_based_index(value: Any, observed_values: list[int]) -> int:
    numeric = int(value or 0)
    # OpenDataLoader documents can be zero- or one-based. A zero anywhere
    # in the observed coordinates makes the table zero-based.
    return numeric if 0 in observed_values else max(0, numeric - 1)


def _unique_header(base: str, column_index: int, used: set[str]) -> str:
    candidate = re.sub(r"\s+", " ", base).strip(" |")
    if not candidate:
        candidate = f"column_{column_index + 1}"
    original = candidate
    suffix = 2
    while candidate.lower() in used:
        candidate = f"{original}_{suffix}"
        suffix += 1
    used.add(candidate.lower())
    return candidate


def _looks_like_data_row(values: list[str | None]) -> bool:
    populated = [value.strip() for value in values if value and value.strip()]
    if not populated:
        return False
    if populated[0].isdigit():
        return True
    return any(SKU_PATTERN.search(value) for value in populated[:4])


def _detect_header_row_count(grid: list[list[ReconstructedCell]]) -> int:
    for index, row in enumerate(grid):
        if _looks_like_data_row([cell.value for cell in row]):
            return max(1, index)
    return 1 if grid else 0


def _flatten_headers(
    grid: list[list[ReconstructedCell]],
    header_row_count: int,
    column_count: int,
) -> list[str]:
    headers: list[str] = []
    used: set[str] = set()
    for column in range(column_count):
        levels: list[str] = []
        for row in range(header_row_count):
            value = grid[row][column].value
            if value:
                normalized = re.sub(r"\s+", " ", value).strip()
                if normalized and normalized not in levels:
                    levels.append(normalized)
        headers.append(
            _unique_header(" / ".join(levels), column, used)
        )
    return headers


def _is_inheritable_header(header: str) -> bool:
    lowered = header.lower()
    if any(pattern in lowered for pattern in NEVER_FORWARD_FILL_HEADER_PATTERNS):
        return False
    return any(
        pattern in lowered
        for pattern in DEFAULT_INHERITABLE_HEADER_PATTERNS
    )


def _is_probable_product_row(
    values: dict[str, str | None],
) -> bool:
    populated = [value for value in values.values() if value]
    if not populated:
        return False
    joined = " | ".join(populated)
    if SKU_PATTERN.search(joined):
        return True
    lowered_headers = " ".join(values).lower()
    has_name_column = any(
        marker in lowered_headers
        for marker in ("product", "item", "description", "model")
    )
    return has_name_column and len(populated) >= 2


def reconstruct_table(
    table: dict[str, Any],
    *,
    document_id: str,
    table_index: int,
    page_images: dict[int, list[str]],
    enable_conservative_forward_fill: bool = True,
) -> ReconstructedTable:
    table_id = f"{document_id}_table_{table_index + 1}"
    page_number = table.get("page number")
    row_nodes = table.get("rows") or []
    all_cells = [
        cell
        for row in row_nodes
        for cell in (row.get("cells") or [])
        if isinstance(cell, dict)
    ]

    observed_rows = [int(cell.get("row number") or 0) for cell in all_cells]
    observed_columns = [
        int(cell.get("column number") or 0) for cell in all_cells
    ]
    declared_rows = int(table.get("number of rows") or 0)
    declared_columns = int(table.get("number of columns") or 0)

    placements: list[tuple[int, int, int, int, dict[str, Any]]] = []
    maximum_row = declared_rows
    maximum_column = declared_columns
    for cell in all_cells:
        row_index = _zero_based_index(cell.get("row number"), observed_rows)
        column_index = _zero_based_index(
            cell.get("column number"), observed_columns
        )
        row_span = _positive_int(cell.get("row span"))
        column_span = _positive_int(cell.get("column span"))
        placements.append(
            (row_index, column_index, row_span, column_span, cell)
        )
        maximum_row = max(maximum_row, row_index + row_span)
        maximum_column = max(maximum_column, column_index + column_span)

    missing = ReconstructedCell(
        value=None,
        provenance=CellProvenance(
            origin="missing",
            source_row=None,
            source_column=None,
        ),
    )
    grid = [
        [missing for _ in range(maximum_column)]
        for _ in range(maximum_row)
    ]

    table_warnings: list[str] = []
    for row_index, column_index, row_span, column_span, cell in placements:
        value = _node_text(cell)
        cell_id = cell.get("id")
        for row_offset in range(row_span):
            for column_offset in range(column_span):
                target_row = row_index + row_offset
                target_column = column_index + column_offset
                if row_offset and column_offset:
                    origin: CellOrigin = "row_and_column_span"
                elif row_offset:
                    origin = "row_span"
                elif column_offset:
                    origin = "column_span"
                else:
                    origin = "explicit"
                grid[target_row][target_column] = ReconstructedCell(
                    value=value or None,
                    provenance=CellProvenance(
                        origin=origin,
                        source_row=row_index,
                        source_column=column_index,
                        source_cell_id=cell_id,
                        inherited_from_row=(
                            row_index if row_offset else None
                        ),
                    ),
                )

    header_row_count = _detect_header_row_count(grid)
    headers = _flatten_headers(grid, header_row_count, maximum_column)

    if enable_conservative_forward_fill:
        for column, header in enumerate(headers):
            if not _is_inheritable_header(header):
                continue
            previous: ReconstructedCell | None = None
            for row in range(header_row_count, len(grid)):
                current = grid[row][column]
                if current.value:
                    previous = current
                    continue
                if previous and previous.value:
                    grid[row][column] = ReconstructedCell(
                        value=previous.value,
                        provenance=CellProvenance(
                            origin="forward_fill",
                            source_row=previous.provenance.source_row,
                            source_column=(
                                previous.provenance.source_column
                            ),
                            source_cell_id=(
                                previous.provenance.source_cell_id
                            ),
                            inherited_from_row=(
                                previous.provenance.source_row
                            ),
                        ),
                    )

    product_rows: list[ReconstructedProductRow] = []
    page_image_references = page_images.get(int(page_number or 0), [])
    for row_index in range(header_row_count, len(grid)):
        cells = {
            headers[column]: grid[row_index][column]
            for column in range(maximum_column)
        }
        values = {header: cell.value for header, cell in cells.items()}
        if not _is_probable_product_row(values):
            continue

        warnings: list[str] = []
        inherited_headers = [
            header
            for header, cell in cells.items()
            if cell.provenance.origin == "forward_fill"
        ]
        if inherited_headers:
            warnings.append(
                "Conservatively inherited: " + ", ".join(inherited_headers)
            )
        if page_image_references:
            warnings.append(
                "Images are page-level candidates; row association "
                "requires layout or VLM verification"
            )

        product_rows.append(
            ReconstructedProductRow(
                row_id=f"{table_id}_row_{row_index + 1}",
                document_id=document_id,
                table_id=table_id,
                page_number=(int(page_number) if page_number else None),
                source_row=row_index,
                values=values,
                cells=cells,
                image_references=page_image_references,
                warnings=warnings,
            )
        )

    if not product_rows:
        table_warnings.append("No probable product rows were identified")

    return ReconstructedTable(
        table_id=table_id,
        page_number=(int(page_number) if page_number else None),
        headers=headers,
        header_row_count=header_row_count,
        rows=product_rows,
        warnings=table_warnings,
    )


def reconstruct_document_tables(
    source_json_path: str | Path,
    *,
    document_id: str,
    enable_conservative_forward_fill: bool = True,
) -> ReconstructedDocumentTables:
    path = Path(source_json_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    elements = data.get("kids") or []

    page_images: dict[int, list[str]] = {}
    tables: list[dict[str, Any]] = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        if element.get("type") == "image" and element.get("source"):
            page = int(element.get("page number") or 0)
            page_images.setdefault(page, []).append(str(element["source"]))
        elif element.get("type") == "table":
            tables.append(element)

    reconstructed = [
        reconstruct_table(
            table,
            document_id=document_id,
            table_index=index,
            page_images=page_images,
            enable_conservative_forward_fill=(
                enable_conservative_forward_fill
            ),
        )
        for index, table in enumerate(tables)
    ]

    warnings: list[str] = []
    if not reconstructed:
        warnings.append("OpenDataLoader JSON contained no tables")

    return ReconstructedDocumentTables(
        document_id=document_id,
        source_json_path=str(path),
        tables=reconstructed,
        warnings=warnings,
    )


def reconstruct_from_document_output(
    document_id: str,
    *,
    output_root: str | Path = "data/output",
    persist: bool = True,
) -> ReconstructedDocumentTables:
    parser_directory = Path(output_root) / document_id / "opendataloader"
    candidates = sorted(parser_directory.glob("*.json"))
    if not candidates:
        raise FileNotFoundError(
            f"No OpenDataLoader JSON found under {parser_directory}"
        )

    result = reconstruct_document_tables(
        candidates[0],
        document_id=document_id,
    )
    if persist:
        output_path = (
            Path(output_root)
            / document_id
            / "normalized_tables.json"
        )
        output_path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return result
