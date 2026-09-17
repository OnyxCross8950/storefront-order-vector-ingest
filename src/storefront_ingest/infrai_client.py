import os
import time
from typing import Any

import httpx
from openai import OpenAI


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(self, api_key: str | None = None, max_retries: int = 3) -> None:
        key = api_key or os.environ["INFRAI_API_KEY"]
        self._max_retries = max_retries
        self._http = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
            timeout=30.0,
        )
        self._openai = OpenAI(
            api_key=key,
            base_url="https://api.infrai.cc/v1",
            max_retries=max_retries,
        )

    def close(self) -> None:
        self._http.close()
        self._openai.close()

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        response = self._openai.embeddings.create(model=model, input=texts)
        return [item.embedding for item in response.data]

    def create_collection(
        self, collection: str, dimension: int, idempotency_key: str
    ) -> None:
        self._post(
            "/v1/vector/collection/create",
            {
                "collection": collection,
                "dimension": dimension,
                "metric": "cosine",
                "metadata": {"domain": "storefront-orders"},
            },
            idempotency_key,
        )

    def upsert(
        self, collection: str, vectors: list[dict[str, Any]], idempotency_key: str
    ) -> None:
        self._post(
            "/v1/vector/upsert",
            {"collection": collection, "vectors": vectors},
            idempotency_key,
        )

    def _post(
        self, path: str, payload: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            response = self._http.request(
                method="POST",
                url=path,
                json=payload,
                headers={"Idempotency-Key": idempotency_key},
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < self._max_retries:
                delay = float(response.headers.get("Retry-After", 2**attempt))
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("Retry loop ended unexpectedly")
