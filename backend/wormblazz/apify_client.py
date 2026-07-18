from __future__ import annotations

import asyncio
from typing import Any

import httpx


APIFY_BASE = "https://api.apify.com/v2"


async def run_actor(
    token: str,
    actor_id: str,
    payload: dict[str, Any],
    *,
    dataset_limit: int,
    timeout_seconds: float = 600.0,
) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    timeout = httpx.Timeout(timeout_seconds, connect=30.0)

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        start = await client.post(
            f"{APIFY_BASE}/acts/{actor_id}/runs",
            params={"waitForFinish": 120},
            json=payload,
        )
        if start.status_code >= 400:
            raise ValueError(
                f"Apify actor `{actor_id}` failed ({start.status_code}): {start.text[:500]}"
            )

        run = start.json().get("data") or {}
        run_id = run.get("id")
        status = run.get("status")
        if not run_id:
            raise ValueError("Apify did not return a run id.")

        while status in {"READY", "RUNNING"}:
            await asyncio.sleep(3)
            poll = await client.get(f"{APIFY_BASE}/actor-runs/{run_id}")
            poll.raise_for_status()
            run = poll.json().get("data") or {}
            status = run.get("status")

        if status != "SUCCEEDED":
            raise ValueError(
                f"Apify run `{run_id}` ended with status `{status}`. "
                "Check actor logs in the Apify console."
            )

        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            raise ValueError("Apify run completed without a dataset.")

        response = await client.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"format": "json", "clean": "true", "limit": dataset_limit},
        )
        response.raise_for_status()
        items = response.json()
        if not isinstance(items, list):
            raise ValueError("Unexpected Apify dataset payload.")
        return [item for item in items if isinstance(item, dict)]

