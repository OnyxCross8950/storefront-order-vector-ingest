from typing import Any

from storefront_ingest.models import IngestRequest
from storefront_ingest.order_ingest import OrderIngestor, chunk_document


class RecordingClient:
    def __init__(self) -> None:
        self.vectors: list[dict[str, Any]] = []
        self.upsert_key = ""

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        return [[float(len(text)), 1.0, 0.5] for text in texts]

    def create_collection(self, collection: str, dimension: int, idempotency_key: str) -> None:
        assert dimension == 3

    def upsert(
        self, collection: str, vectors: list[dict[str, Any]], idempotency_key: str
    ) -> None:
        self.vectors = vectors
        self.upsert_key = idempotency_key


def test_retry_keeps_order_vector_ids_and_batch_key_stable() -> None:
    request = IngestRequest.model_validate(
        {
            "collection": "orders",
            "documents": [
                {
                    "order_id": "order-7",
                    "event_type": "fulfillment",
                    "occurred_at": "2026-08-30T10:00:00Z",
                    "text": "Packed at station 4 and handed to the carrier.",
                }
            ],
        }
    )
    first_client = RecordingClient()
    second_client = RecordingClient()

    first = OrderIngestor(first_client, "test-model").ingest(request)
    second = OrderIngestor(second_client, "test-model").ingest(request)

    assert first.vector_ids == second.vector_ids
    assert first_client.upsert_key == second_client.upsert_key
    assert first_client.vectors[0]["metadata"]["event_type"] == "fulfillment"


def test_chunking_preserves_words_and_event_order() -> None:
    document = IngestRequest.model_validate(
        {
            "collection": "orders",
            "documents": [
                {
                    "order_id": "order-8",
                    "event_type": "customer_update",
                    "occurred_at": "2026-08-30T11:00:00Z",
                    "text": "Parcel left depot and will arrive tomorrow morning",
                }
            ],
        }
    ).documents[0]

    chunks = chunk_document(document, max_chars=20)

    assert " ".join(chunk.text for chunk in chunks) == document.text
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
