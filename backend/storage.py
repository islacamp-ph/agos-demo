import os
import logging

import requests
from starlette.concurrency import run_in_threadpool

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = os.environ["APP_NAME"]
_key = None


def init_storage(force: bool = False) -> str:
    global _key
    if _key and not force:
        return _key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ.get("EMERGENT_LLM_KEY")}, timeout=30)
    r.raise_for_status()
    _key = r.json()["storage_key"]
    return _key


def _put(path: str, data: bytes, content_type: str) -> dict:
    for attempt in range(2):
        r = requests.put(f"{STORAGE_URL}/objects/{path}", data=data, timeout=120,
                         headers={"X-Storage-Key": init_storage(force=attempt > 0), "Content-Type": content_type})
        if r.status_code == 404 and attempt == 0:
            continue
        r.raise_for_status()
        return r.json()


def _get(path: str) -> tuple:
    for attempt in range(2):
        r = requests.get(f"{STORAGE_URL}/objects/{path}", timeout=60,
                         headers={"X-Storage-Key": init_storage(force=attempt > 0)})
        if r.status_code == 404 and attempt == 0:
            continue
        r.raise_for_status()
        return r.content, r.headers.get("Content-Type", "application/octet-stream")


async def put_object(path: str, data: bytes, content_type: str) -> dict:
    return await run_in_threadpool(_put, path, data, content_type)


async def get_object(path: str) -> tuple:
    return await run_in_threadpool(_get, path)


def safe_init() -> None:
    try:
        init_storage()
        logging.getLogger("agos").info("Storage initialized")
    except Exception as exc:
        logging.getLogger("agos").error("Storage init failed: %s", type(exc).__name__)
