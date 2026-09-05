from __future__ import annotations

import os
from uuid import NAMESPACE_URL, uuid5

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

from src.extraction.models import DocumentChunk


EMBEDDING_MODEL = "BAAI/bge-small-en"


class QdrantConfigurationError(Exception):
    """Raised when Qdrant configuration is missing."""


def create_qdrant_client() -> QdrantClient:
    load_dotenv()

    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")

    if not url or not api_key:
        raise QdrantConfigurationError(
            "QDRANT_URL and QDRANT_API_KEY are required"
        )

    return QdrantClient(
        url=url,
        api_key=api_key,
    )


def get_collection_name() -> str:
    load_dotenv()

    return os.getenv(
        "QDRANT_COLLECTION",
        "catalog_chunks",
    )

def ensure_collection(
    client: QdrantClient,
    collection_name: str,
) -> None:
    if client.collection_exists(collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=client.get_embedding_size(
                EMBEDDING_MODEL
            ),
            distance=models.Distance.COSINE,
        ),
    )

def qdrant_point_id(chunk: DocumentChunk) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            chunk.chunk_id,
        )
    )

def index_chunks(
    client: QdrantClient,
    collection_name: str,
    chunks: list[DocumentChunk],
) -> None:
    if not chunks:
        return

    documents = [
        models.Document(
            text=chunk.text,
            model=EMBEDDING_MODEL,
        )
        for chunk in chunks
    ]

    payloads = [
        {
            "document": chunk.text,
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "source_file": chunk.source_file,
            "page_numbers": chunk.page_numbers,
            "section_title": chunk.section_title,
            "element_types": chunk.element_types,
            "image_references": chunk.image_references,
            **chunk.metadata,
        }
        for chunk in chunks
    ]

    point_ids = [
        qdrant_point_id(chunk)
        for chunk in chunks
    ]

    client.upload_collection(
        collection_name=collection_name,
        vectors=documents,
        payload=payloads,
        ids=point_ids,
    )

def search_chunks(
    client: QdrantClient,
    collection_name: str,
    query: str,
    limit: int = 5,
):
    return client.query_points(
        collection_name=collection_name,
        query=models.Document(
            text=query,
            model=EMBEDDING_MODEL,
        ),
        limit=limit,
    ).points