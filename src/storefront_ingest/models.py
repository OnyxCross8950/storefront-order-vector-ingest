from typing import Any, Literal

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # Keep pure ingestion utilities usable without extras.
    class BaseModel:
        def __init__(self, **values: Any) -> None:
            for key, value in values.items():
                setattr(self, key, value)

        @classmethod
        def model_validate(cls, value: dict[str, Any]):
            if not isinstance(value, dict):
                raise TypeError("model input must be a mapping")
            if cls is OrderDocument:
                required = ("order_id", "event_type", "occurred_at", "text")
                if any(not isinstance(value.get(key), str) or not value[key] for key in required):
                    raise ValueError("invalid order document")
                if value["event_type"] not in {"checkout", "fulfillment", "receipt", "customer_update"}:
                    raise ValueError("invalid event type")
                return cls(**value)
            if cls is IngestRequest:
                collection = value.get("collection")
                documents = value.get("documents")
                if not isinstance(collection, str) or not collection or not isinstance(documents, list) or not documents:
                    raise ValueError("invalid ingest request")
                return cls(collection=collection, documents=[OrderDocument.model_validate(doc) for doc in documents])
            return cls(**value)

    def Field(**_: Any) -> Any:
        return None


class OrderDocument(BaseModel):
    order_id: str = Field(min_length=1)
    event_type: Literal["checkout", "fulfillment", "receipt", "customer_update"]
    occurred_at: str = Field(min_length=1)
    text: str = Field(min_length=1)
    customer_id: str | None = None


class IngestRequest(BaseModel):
    collection: str = Field(min_length=1)
    documents: list[OrderDocument] = Field(min_length=1)


class IngestResult(BaseModel):
    collection: str
    documents_received: int
    vectors_upserted: int
    vector_ids: list[str]
