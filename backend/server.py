import asyncio
import os
import time
import logging
from collections import defaultdict, deque
from contextlib import suppress
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pymongo import ASCENDING, DESCENDING, IndexModel  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

try:
    from backend.clerk_auth import clerk_router
except ModuleNotFoundError:
    from clerk_auth import clerk_router
from core import db, client  # noqa: E402
import storage  # noqa: E402
import routes_workspace, routes_finance, routes_payments, routes_insights, routes_public  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("agos")

INDEXES = {
    "users": [IndexModel([("user_id", ASCENDING)], name="user_id", unique=True)],
    "workspaces": [IndexModel([("id", ASCENDING)], name="id", unique=True), IndexModel([("owner_user_id", ASCENDING)], name="owner")],
    "members": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                IndexModel([("workspace_id", ASCENDING), ("user_id", ASCENDING)], name="ws_user"),
                IndexModel([("email", ASCENDING)], name="email")],
    "expenses": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                 IndexModel([("workspace_id", ASCENDING), ("date", DESCENDING)], name="ws_date")],
    "budgets": [IndexModel([("workspace_id", ASCENDING), ("period", DESCENDING)], name="ws_period")],
    "cards": [IndexModel([("id", ASCENDING)], name="id", unique=True), IndexModel([("workspace_id", ASCENDING)], name="ws")],
    "card_transactions": [IndexModel([("card_id", ASCENDING), ("date", DESCENDING)], name="card_date"),
                          IndexModel([("workspace_id", ASCENDING)], name="ws")],
    "payments": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                 IndexModel([("workspace_id", ASCENDING), ("created_at", DESCENDING)], name="ws_created"),
                 IndexModel([("stellar.tx_hash", ASCENDING)], name="tx_hash", sparse=True)],
    "stellar_accounts": [IndexModel([("workspace_id", ASCENDING)], name="ws", unique=True)],
    "files": [IndexModel([("id", ASCENDING)], name="id", unique=True)],
    "audit_logs": [IndexModel([("workspace_id", ASCENDING), ("at", DESCENDING)], name="ws_at")],
    "waitlist": [IndexModel([("email", ASCENDING)], name="email", unique=True)],
}


async def ensure_indexes() -> None:
    for coll, models in INDEXES.items():
        for m in models:
            try:
                await db[coll].create_indexes([m])
            except Exception as exc:
                logger.error("ensure_indexes(%s.%s): %s", coll, m.document["name"], exc)


app = FastAPI(title="AGOS API")

# Basic in-memory rate limiting per client IP.
_hits: dict = defaultdict(deque)
LIMITS = {"/api/waitlist": (5, 60), "default": (240, 60)}


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api") and not path.startswith("/api/__clerk"):
        ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
        key = path if path in LIMITS else "default"
        limit, window = LIMITS[key]
        if key != "default" and request.method == "GET":
            key, (limit, window) = "default", LIMITS["default"]
        q = _hits[(ip, key)]
        now = time.monotonic()
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return JSONResponse({"detail": "Too many requests; slow down"}, status_code=429)
        q.append(now)
    return await call_next(request)


@app.exception_handler(Exception)
async def safe_errors(request: Request, exc: Exception):
    logger.error("Unhandled error on %s: %s", request.url.path, type(exc).__name__)
    return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "AGOS"}


app.include_router(clerk_router)
for r in (routes_workspace, routes_finance, routes_payments, routes_insights, routes_public):
    app.include_router(r.router)

app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    app.state.index_task = asyncio.create_task(ensure_indexes())
    app.state.refresh_task = asyncio.create_task(routes_payments.refresh_pending_on_startup())
    await asyncio.get_running_loop().run_in_executor(None, storage.safe_init)


@app.on_event("shutdown")
async def shutdown():
    for t in (app.state.index_task, app.state.refresh_task):
        t.cancel()
        with suppress(asyncio.CancelledError):
            await t
    client.close()
