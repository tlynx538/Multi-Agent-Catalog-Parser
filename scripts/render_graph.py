from pathlib import Path

from src.workflow.catalog_graph import build_catalog_graph


def main() -> None:
    output_path = Path("data/runtime/catalog_graph.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    graph = build_catalog_graph()

    png_bytes = graph.get_graph().draw_mermaid_png()
    output_path.write_bytes(png_bytes)

    print(f"Graph image saved to: {output_path.resolve()}")


if __name__ == "__main__":
    main()