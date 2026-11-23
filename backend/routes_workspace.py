from typing import Literal, Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, EmailStr

from core import (db, new_id, now_iso, current_user, ws_ctx, require_roles, audit, ROLES, MANAGERS,
                  DEFAULT_DEPARTMENTS)
from seed import seed_demo

router = APIRouter(prefix="/api")
P = {"_id": 0}


async def _my_workspaces(user: dict) -> list:
    mems = await db.members.find({"user_id": user["user_id"], "status": "active"}, P).to_list(200)
    ids = [m["id"] for m in mems]
    by_ws = {m["workspace_id"]: m for m in mems}
    wss = await db.workspaces.find({"id": {"$in": list(by_ws)}}, P).to_list(200)
    return [{"id": w["id"], "name": w["name"], "is_demo": w.get("is_demo", False), "role": by_ws[w["id"]]["role"],
             "member_id": by_ws[w["id"]]["id"], "industry": w.get("industry")} for w in wss] if ids else []


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    # Link workspace invitations addressed to this user's verified email.
    if user.get("emails"):
        await db.members.update_many({"email": {"$in": user["emails"]}, "user_id": None, "status": "invited", "is_synthetic": False},
                                     {"$set": {"user_id": user["user_id"], "status": "active", "joined_at": now_iso()}})
    return {"name": user["name"], "email": user.get("email"), "platform_role": user.get("platform_role", "user"),
            "workspaces": await _my_workspaces(user)}


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=60)
    industry: str = Field(min_length=2, max_length=80)
    location: str = Field(min_length=2, max_length=120)
    business_email: EmailStr
    admin_name: str = Field(min_length=2, max_length=80)
    team_size: Literal["1-10", "11-50", "51-200", "200+"]
    default_currency: Literal["PHP", "USD"] = "PHP"


@router.post("/workspaces")
async def create_workspace(body: WorkspaceIn, user: dict = Depends(current_user)):
    ws_id = new_id()
    await db.workspaces.insert_one({**body.model_dump(), "id": ws_id, "is_demo": False, "approval_threshold": 50000,
                                    "departments": DEFAULT_DEPARTMENTS, "owner_user_id": user["user_id"], "created_at": now_iso()})
    await db.members.insert_one({"id": new_id(), "workspace_id": ws_id, "user_id": user["user_id"], "name": body.admin_name,
                                 "email": user.get("email", ""), "role": "owner", "department": "Executive", "title": "Administrator",
                                 "spending_limit": 0, "status": "active", "is_synthetic": False, "created_at": now_iso()})
    return {"id": ws_id}


@router.post("/workspaces/demo")
async def create_demo(user: dict = Depends(current_user)):
    existing = await db.workspaces.count_documents({"owner_user_id": user["user_id"], "is_demo": True})
    if existing >= 3:
        raise HTTPException(status_code=409, detail="You already have the maximum of 3 demo workspaces")
    return {"id": await seed_demo(user)}


@router.get("/workspace")
async def get_workspace(ctx: dict = Depends(ws_ctx)):
    personas = []
    if ctx["ws"].get("is_demo") and ctx["real_member"]["role"] == "owner":
        personas = await db.members.find({"workspace_id": ctx["ws_id"], "status": "active"},
                                         {"_id": 0, "id": 1, "name": 1, "role": 1, "department": 1}).to_list(50)
    ws = {k: v for k, v in ctx["ws"].items() if k != "owner_user_id"}
    return {"workspace": ws, "member": ctx["member"], "role": ctx["role"], "real_member_id": ctx["real_member"]["id"],
            "acting_as_persona": ctx["member"]["id"] != ctx["real_member"]["id"], "personas": personas}


class WorkspacePatch(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    category: Optional[str] = Field(None, max_length=60)
    industry: Optional[str] = Field(None, max_length=80)
    location: Optional[str] = Field(None, max_length=120)
    business_email: Optional[EmailStr] = None
    default_currency: Optional[Literal["PHP", "USD"]] = None
    approval_threshold: Optional[float] = Field(None, ge=0, le=100_000_000)
    departments: Optional[List[str]] = Field(None, max_length=30)


@router.patch("/workspace")
async def patch_workspace(body: WorkspacePatch, ctx: dict = Depends(require_roles("owner"))):
    upd = body.model_dump(exclude_none=True)
    if "departments" in upd:
        upd["departments"] = [d.strip()[:40] for d in upd["departments"] if d.strip()]
    await db.workspaces.update_one({"id": ctx["ws_id"]}, {"$set": upd})
    await audit(ctx, "workspace.updated", "workspace", ctx["ws_id"], ", ".join(upd))
    return {"ok": True}


@router.get("/team")
async def list_team(ctx: dict = Depends(ws_ctx)):
    proj = {"_id": 0, "user_id": 0} if ctx["role"] in MANAGERS else {"_id": 0, "user_id": 0, "email": 0, "spending_limit": 0}
    return await db.members.find({"workspace_id": ctx["ws_id"], "status": {"$ne": "removed"}}, proj).sort("created_at", 1).to_list(500)


class MemberIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    role: Literal["owner", "finance_manager", "employee"]
    department: str = Field(min_length=1, max_length=40)
    title: str = Field("", max_length=80)
    spending_limit: float = Field(0, ge=0, le=100_000_000)


@router.post("/team")
async def add_member(body: MemberIn, ctx: dict = Depends(require_roles("owner"))):
    email = body.email.lower()
    if await db.members.find_one({"workspace_id": ctx["ws_id"], "email": email, "status": {"$ne": "removed"}}):
        raise HTTPException(status_code=409, detail="A member with this email already exists")
    doc = {**body.model_dump(), "email": email, "id": new_id(), "workspace_id": ctx["ws_id"], "user_id": None,
           "status": "invited", "is_synthetic": False, "created_at": now_iso()}
    await db.members.insert_one(dict(doc))
    await audit(ctx, "member.invited", "member", doc["id"], f"{body.name} as {body.role}")
    doc.pop("_id", None)
    return doc


class MemberPatch(BaseModel):
    role: Optional[Literal["owner", "finance_manager", "employee"]] = None
    department: Optional[str] = Field(None, max_length=40)
    title: Optional[str] = Field(None, max_length=80)
    spending_limit: Optional[float] = Field(None, ge=0, le=100_000_000)
    status: Optional[Literal["active", "removed"]] = None


@router.patch("/team/{member_id}")
async def patch_member(member_id: str, body: MemberPatch, ctx: dict = Depends(require_roles("owner"))):
    target = await db.members.find_one({"id": member_id, "workspace_id": ctx["ws_id"]}, P)
    if not target:
        raise HTTPException(status_code=404, detail="Not found")
    upd = body.model_dump(exclude_none=True)
    if upd.get("status") == "active" and target["status"] == "invited":
        upd.pop("status")
    losing_owner = target["role"] == "owner" and (upd.get("role", "owner") != "owner" or upd.get("status") == "removed")
    if losing_owner and await db.members.count_documents({"workspace_id": ctx["ws_id"], "role": "owner", "status": "active"}) <= 1:
        raise HTTPException(status_code=409, detail="A workspace must keep at least one owner")
    await db.members.update_one({"id": member_id}, {"$set": upd})
    await audit(ctx, "member.updated", "member", member_id, ", ".join(f"{k}={v}" for k, v in upd.items()))
    return {"ok": True}


@router.get("/audit")
async def audit_log(ctx: dict = Depends(require_roles(*MANAGERS))):
    return await db.audit_logs.find({"workspace_id": ctx["ws_id"]}, P).sort("at", -1).limit(200).to_list(200)


@router.get("/roles")
async def roles():
    return {"roles": ROLES}
