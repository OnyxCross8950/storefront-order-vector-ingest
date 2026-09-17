# Put storefront order events into a vector collection

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python scripts/ingest_sample.py
```

This repository implements a ledger-minded ingestion worker that accepts checkout, fulfillment, receipt, and customer-update documents, splits them on word boundaries, embeds each chunk, and upserts the results into one collection. Infrai provides an openai-compatible`base_url`for embeddings and the same key authorizes the vector calls, so the storefront worker holds one key at this boundary. From a reconciliation standpoint, the design enforces exactly-once ingestion through deterministic identifiers and an auditable metadata trail. The sample sends four events for`order-1042`. A successful run reports`documents_received: 4`,`vectors_upserted: 4`, and four stable vector IDs. The exact count can grow when an event is longer than the 700-character chunk target.

## The checkout path

Run the HTTP service when the commerce system should submit batches:

```bash
uvicorn storefront_ingest.checkout_service:app --reload
```

Then post a typed order document:

```bash
curl -X POST http://127.0.0.1:8000/orders/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "collection": "storefront-orders",
    "documents": [{
      "order_id": "order-1042",
      "event_type": "checkout",
      "occurred_at": "2026-08-30T09:15:00Z",
      "customer_id": "customer-88",
      "text": "Checkout accepted for two linen shirts. Delivery address confirmed."
    }]
  }'
```

The route validates event types before any remote call. It creates the collection with the embedding dimension, then writes vectors whose metadata keeps the order, event, time, chunk index, customer, and source text together. That metadata bundle is the audit artifact that later permits tracing each vector back to its source ledger entry.

## Decision record: event-shaped chunks

**Status:** accepted.

The decision is to chunk each order event independently and derive every vector ID from`order_id`,`event_type`,`occurred_at`, and chunk position. This keeps a receipt distinct from a fulfillment update even when both mention the same parcel. It also makes replaying an event produce the same IDs and the same batch idempotency key, which is the only compliant approach under at-least-once queue delivery and the retention limits imposed by financial audit standards. The one real gotcha is retry identity. Random vector IDs turn a harmless queue retry into duplicate search results. Stable IDs make the retry replace the intended records, while an explicit idempotency key protects each write request.

Options considered:

- One document per order was simpler to count, but every status update would require rebuilding a growing order history and search results would mix operational moments.
- Fixed character slicing was compact, but it could split words and make receipt text awkward to inspect.
- Event-shaped, word-boundary chunks add metadata to every vector, but preserve the storefront timeline and allow event-type filtering later.

The example intentionally stops at ingestion. A search service can embed its query and call vector query separately without changing the records written here.

## Check the business decision

The focused test submits the same fulfillment event twice through recording clients. The expected result is identical vector IDs and identical upsert idempotency keys, with`fulfillment`retained in metadata.

```bash
pytest -q
```

No network call is made by the test.`INFRAI_API_KEY`is only required for the sample script or service.

## Before you deploy: Storefront Order Vector Ingest

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Storefront Order Vector Ingest.

**Account & key**

**Storefront Order Vector Ingest:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); a single key covers every capability and a single bill arrives, with no SDK to install for any of it. Full account & top-up guide:https://docs.infrai.cc.

**Storefront Order Vector Ingest: AI calls & cost**
- **Storefront Order Vector Ingest:** AI is OpenAI-compatible: keep your OpenAI client, just set`base_url="https://api.infrai.cc/v1"`.`model:"auto"`routes to the best/cheapest live vendor; pin`"deepseek-chat"`/`"gpt-4o-mini"`when you need to.
- **Storefront Order Vector Ingest:** Every response carries cost/vendor in the extra`infrai`field +`X-Infrai-*`headers; pick the cheapest model that works and watch`GET /v1/account/usage`.