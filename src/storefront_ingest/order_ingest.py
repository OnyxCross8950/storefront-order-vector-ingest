from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import IngestRequest, IngestResult, OrderDocument

if TYPE_CHECKING:
    from .infrai_client import InfraiClient


@dataclass(frozen=True)
class OrderChunk:
    vector_id: str
    text: str
    order_id: str
    event_type: str
    occurred_at: str
    chunk_index: int
    customer_id: str | None


def chunk_document(document: OrderDocument, max_chars: int = 700) -> list[OrderChunk]:
    words = document.text.split()
    pieces: list[str] = []
    current: list[str] = []
    current_length = 0
    for word in words:
        added = len(word) + (1 if current else 0)
        if current and current_length + added > max_chars:
            pieces.append(" ".join(current))
            current = [word]
            current_length = len(word)
        else:
            current.append(word)
            current_length += added
    if current:
        pieces.append(" ".join(current))

    chunks: list[OrderChunk] = []
    for index, text in enumerate(pieces):
        identity = f"{document.order_id}:{document.event_type}:{document.occurred_at}:{index}"
        vector_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        chunks.append(
            OrderChunk(
                vector_id=vector_id,
                text=text,
                order_id=document.order_id,
                event_type=document.event_type,
                occurred_at=document.occurred_at,
                chunk_index=index,
                customer_id=document.customer_id,
            )
        )
    return chunks


class OrderIngestor:
    def __init__(self, client: InfraiClient, embedding_model: str) -> None:
        self._client = client
        self._embedding_model = embedding_model

    def ingest(self, request: IngestRequest) -> IngestResult:
        chunks = [
            chunk
            for document in request.documents
            for chunk in chunk_document(document)
        ]
        embeddings = self._client.embed(
            [chunk.text for chunk in chunks], self._embedding_model
        )
        if not embeddings or len(embeddings) != len(chunks):
            raise RuntimeError("Embedding count does not match chunk count")

        collection_key = hashlib.sha256(request.collection.encode("utf-8")).hexdigest()
        self._client.create_collection(
            request.collection, len(embeddings[0]), f"collection-{collection_key}"
        )
        vectors = [
            {
                "id": chunk.vector_id,
                "values": embedding,
                "metadata": {
                    "order_id": chunk.order_id,
                    "event_type": chunk.event_type,
                    "occurred_at": chunk.occurred_at,
                    "chunk_index": chunk.chunk_index,
                    "customer_id": chunk.customer_id,
                    "text": chunk.text,
                },
            }
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        batch_identity = ":".join(sorted(chunk.vector_id for chunk in chunks))
        batch_key = hashlib.sha256(batch_identity.encode("utf-8")).hexdigest()
        self._client.upsert(request.collection, vectors, f"order-batch-{batch_key}")
        return IngestResult(
            collection=request.collection,
            documents_received=len(request.documents),
            vectors_upserted=len(vectors),
            vector_ids=[chunk.vector_id for chunk in chunks],
        )
