import json
import os
import sys
from pathlib import Path

# Allow the documented repository-root invocation to resolve the src-layout package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storefront_ingest.infrai_client import InfraiClient
from storefront_ingest.models import IngestRequest
from storefront_ingest.order_ingest import OrderIngestor


def main() -> None:
    request = IngestRequest.model_validate(
        {
            "collection": "storefront-orders",
            "documents": [
                {
                    "order_id": "order-1042",
                    "event_type": "checkout",
                    "occurred_at": "2026-08-30T09:15:00Z",
                    "customer_id": "customer-88",
                    "text": "Checkout accepted for two linen shirts. Delivery address confirmed.",
                },
                {
                    "order_id": "order-1042",
                    "event_type": "fulfillment",
                    "occurred_at": "2026-08-30T12:40:00Z",
                    "customer_id": "customer-88",
                    "text": "Warehouse packed both shirts and assigned carrier tracking.",
                },
                {
                    "order_id": "order-1042",
                    "event_type": "receipt",
                    "occurred_at": "2026-08-30T12:42:00Z",
                    "customer_id": "customer-88",
                    "text": "Receipt issued for the completed payment and emailed to the customer.",
                },
                {
                    "order_id": "order-1042",
                    "event_type": "customer_update",
                    "occurred_at": "2026-08-30T12:45:00Z",
                    "customer_id": "customer-88",
                    "text": "Customer received a dispatch update with tracking details.",
                },
            ],
        }
    )
    client = InfraiClient()
    try:
        result = OrderIngestor(
            client, os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
        ).ingest(request)
        print(json.dumps(result.model_dump(), indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
