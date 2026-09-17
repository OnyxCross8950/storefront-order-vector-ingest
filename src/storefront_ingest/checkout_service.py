import os

from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiClient, InfraiError
from .models import IngestRequest, IngestResult
from .order_ingest import OrderIngestor

app = FastAPI(title="Storefront order ingest")


@app.post("/orders/ingest", response_model=IngestResult)
def ingest_orders(request: IngestRequest) -> IngestResult:
    client = InfraiClient()
    try:
        ingestor = OrderIngestor(client, os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small"))
        return ingestor.ingest(request)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=exc.detail) from exc
    finally:
        client.close()
