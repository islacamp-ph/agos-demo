import os
import uuid
import logging
from datetime import datetime, timezone

import requests
from fastapi import Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.concurrency import run_in_threadpool

try:
    from backend.clerk_auth import require_user
except ModuleNotFoundError:
    from clerk_auth import require_user

logger = logging.getLogger("agos")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

ENV = "live" if os.environ.get("CLERK_PUBLISHABLE_KEY", "").startswith("pk_live_") else "preview"
USD_PHP = 58.0  # fixed demo conversion rate, not a market rate
ROLES = ["owner", "finance_manager", "employee"]
MANAGERS = ("owner", "finance_manager")
DEFAULT_DEPARTMENTS = ["Executive", "Engineering", "Marketing", "Operations", "Finance"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def to_php(amount: float, currency: str) -> float:
    if currency == "PHP":
        return round(amount, 2)
    if currency == "USD":
        return round(amount * USD_PHP, 2)
    return 0.0


async def audit(ctx: dict, action: str, entity: str, entity_id: str, details: str = "") -> None:
    await db.audit_logs.insert_one({
        "id": new_id(), "workspace_id": ctx["ws_id"], "actor_member_id": ctx["member"]["id"],
        "actor_name": ctx["actor_name"], "action": action, "entity": entity,
        "entity_id": entity_id, "details": details, "at": now_iso(),
    })


def _email_set(var: str) -> set:
    return {e.strip().lower() for e in os.environ.get(var, "").split(",") if e.strip()}


def _clerk_profile(user_id: str) -> dict:
    r = requests.get(f"https://api.clerk.com/v1/users/{user_id}", timeout=10,
                     headers={"Authorization": f"Bearer {os.environ['CLERK_SECRET_KEY']}", "User-Agent": "agos-app"})
    r.raise_for_status()
    data = r.json()
    verified = [e["email_address"].lower() for e in data.get("email_addresses", [])
                if (e.get("verification") or {}).get("status") == "verified"]
    name = " ".join(x for x in [data.get("first_name"), data.get("last_name")] if x) or (verified[0].split("@")[0] if verified else "AGOS User")
    return {"emails": verified, "name": name}


async def current_user(user: dict = Depends(require_user)) -> dict:
    uid = user["user_id"]
    doc = await db.users.find_one({"user_id": uid}, {"_id": 0})
    if doc is None or "emails" not in doc:
        prof = await run_in_threadpool(_clerk_profile, uid)
        emails = set(prof["emails"])
        role = "super_admin" if emails & _email_set("SUPER_ADMIN_EMAIL") else (
            "platform_admin" if emails & _email_set("PLATFORM_ADMIN_EMAIL") else "user")
        doc = {"user_id": uid, "emails": prof["emails"], "email": prof["emails"][0] if prof["emails"] else "",
               "name": prof["name"], "platform_role": role, "env": ENV, "created_at": now_iso()}
        await db.users.update_one({"user_id": uid}, {"$setOnInsert": doc}, upsert=True)
        doc = await db.users.find_one({"user_id": uid}, {"_id": 0})
    return doc


def require_platform(*roles: str):
    async def check(user: dict = Depends(current_user)) -> dict:
        if user.get("platform_role") not in roles:
            raise HTTPException(status_code=403, detail="Not allowed")
        return user
    return check


async def ws_ctx(request: Request, user: dict = Depends(current_user)) -> dict:
    ws_id = request.headers.get("x-workspace-id")
    if not ws_id:
        raise HTTPException(status_code=400, detail="Workspace not selected")
    member = await db.members.find_one({"workspace_id": ws_id, "user_id": user["user_id"], "status": "active"}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws = await db.workspaces.find_one({"id": ws_id}, {"_id": 0})
    acting = member
    act_as = request.headers.get("x-act-as")
    if act_as and act_as != member["id"] and ws.get("is_demo") and member["role"] == "owner":
        persona = await db.members.find_one({"id": act_as, "workspace_id": ws_id, "status": "active"}, {"_id": 0})
        if persona:
            acting = persona
    actor_name = acting["name"] if acting is member else f"{acting['name']} (demo persona)"
    return {"ws": ws, "ws_id": ws_id, "member": acting, "real_member": member, "user": user,
            "role": acting["role"], "actor_name": actor_name}


def require_roles(*roles: str):
    async def check(ctx: dict = Depends(ws_ctx)) -> dict:
        if ctx["role"] not in roles:
            raise HTTPException(status_code=403, detail="Your role cannot perform this action")
        return ctx
    return check


def history_entry(ctx: dict, status: str, note: str = "") -> dict:
    return {"status": status, "actor_name": ctx["actor_name"], "actor_member_id": ctx["member"]["id"],
            "at": now_iso(), "note": note}


def system_entry(status: str, note: str) -> dict:
    return {"status": status, "actor_name": "AGOS Workflow", "actor_member_id": None, "at": now_iso(), "note": note}
