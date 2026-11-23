import csv
import io
from datetime import datetime, timezone
from typing import Literal, Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from core import db, new_id, now_iso, to_php, ws_ctx, require_roles, audit, history_entry, system_entry, MANAGERS
import storage

router = APIRouter(prefix="/api")
P = {"_id": 0}
COUNTED = ["approved", "paid"]  # accounting rule: only approved or recorded-as-paid expenses consume budgets
ALLOWED_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}
MAX_UPLOAD = 10 * 1024 * 1024


def this_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def csv_response(rows: list, columns: list, filename: str) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    for r in rows:
        w.writerow([r.get(c, "") for c in columns])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def budget_matches(b: dict, e: dict) -> bool:
    if not e["date"].startswith(b["period"]):
        return False
    if b["scope"] == "department":
        return e.get("department") == b["department"]
    if b["scope"] == "employee":
        return e.get("member_id") == b["member_id"]
    return True


async def budgets_with_usage(ws_id: str, query: dict | None = None) -> list:
    budgets = await db.budgets.find({"workspace_id": ws_id, **(query or {})}, P).sort("period", -1).to_list(500)
    periods = {b["period"] for b in budgets}
    exps = await db.expenses.find({"workspace_id": ws_id, "status": {"$in": COUNTED},
                                   "date": {"$regex": "^(" + "|".join(periods) + ")"}} if periods else {"_id": None},
                                  {"_id": 0, "date": 1, "department": 1, "member_id": 1, "amount_php": 1}).to_list(10000)
    for b in budgets:
        used = round(sum(e["amount_php"] for e in exps if budget_matches(b, e)), 2)
        b["used"] = used
        b["remaining"] = round(b["amount"] - used, 2)
        b["utilization"] = round(used / b["amount"] * 100, 1) if b["amount"] else 0
        b["state"] = "over" if used > b["amount"] else ("warning" if b["utilization"] >= b.get("alert_pct", 80) else "ok")
    return budgets


async def budget_warnings(ws_id: str, exp: dict) -> list:
    out = []
    for b in await budgets_with_usage(ws_id, {"period": exp["date"][:7]}):
        if budget_matches(b, exp) and b["used"] + exp["amount_php"] > b["amount"]:
            out.append(f"Would exceed budget '{b['name']}' (₱{b['remaining']:,.2f} remaining)")
    return out


def can_decide(ctx: dict, amount_php: float, requester_id: str) -> Optional[str]:
    if ctx["role"] not in MANAGERS:
        return "Only owners and finance managers can approve"
    if requester_id == ctx["member"]["id"] and ctx["role"] != "owner":
        return "You cannot approve your own request"
    if ctx["role"] == "finance_manager" and amount_php > ctx["ws"].get("approval_threshold", 50000):
        return "Amount exceeds your approval threshold; owner approval required"
    return None


# ---------------- Expenses ----------------
class ExpenseIn(BaseModel):
    merchant: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    amount: float = Field(gt=0, le=100_000_000)
    currency: Literal["PHP", "USD"] = "PHP"
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str = Field("", max_length=500)
    notes: str = Field("", max_length=1000)
    member_id: Optional[str] = None
    department: Optional[str] = Field(None, max_length=40)
    submit: bool = False


def _scope(ctx: dict) -> dict:
    return {} if ctx["role"] in MANAGERS else {"member_id": ctx["member"]["id"]}


async def _get_expense(ctx: dict, exp_id: str) -> dict:
    e = await db.expenses.find_one({"id": exp_id, "workspace_id": ctx["ws_id"], **_scope(ctx)}, P)
    if not e:
        raise HTTPException(status_code=404, detail="Not found")
    return e


def _expense_query(ctx, status, department, member_id, q, date_from, date_to) -> dict:
    query = {"workspace_id": ctx["ws_id"], **_scope(ctx)}
    if status:
        query["status"] = status
    if department:
        query["department"] = department
    if member_id and ctx["role"] in MANAGERS:
        query["member_id"] = member_id
    if q:
        import re
        rx = {"$regex": re.escape(q[:60]), "$options": "i"}
        query["$or"] = [{"merchant": rx}, {"description": rx}, {"category": rx}, {"member_name": rx}]
    if date_from or date_to:
        query["date"] = {k: v for k, v in (("$gte", date_from), ("$lte", date_to)) if v}
    return query


@router.get("/expenses")
async def list_expenses(ctx: dict = Depends(ws_ctx), status: Optional[str] = None, department: Optional[str] = None,
                        member_id: Optional[str] = None, q: Optional[str] = None,
                        date_from: Optional[str] = None, date_to: Optional[str] = None):
    query = _expense_query(ctx, status, department, member_id, q, date_from, date_to)
    return await db.expenses.find(query, P).sort("date", -1).to_list(2000)


@router.get("/expenses/export")
async def export_expenses(ctx: dict = Depends(ws_ctx), status: Optional[str] = None, department: Optional[str] = None,
                          q: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None):
    rows = await db.expenses.find(_expense_query(ctx, status, department, None, q, date_from, date_to), P).sort("date", -1).to_list(5000)
    for r in rows:
        r["data_type"] = "Simulated demo record" if r.get("is_synthetic") else "Recorded"
        r["receipt_count"] = len(r.get("receipts", []))
    return csv_response(rows, ["id", "date", "merchant", "category", "department", "member_name", "amount", "currency",
                               "amount_php", "status", "receipt_count", "description", "data_type"], "agos-expenses.csv")


async def _route_for_approval(ctx: dict, exp: dict) -> None:
    exp["history"].append(history_entry(ctx, "submitted"))
    exp["history"].append(system_entry("pending_approval", "Routed to " + (
        "Owner (above approval threshold)" if exp["amount_php"] > ctx["ws"].get("approval_threshold", 50000) else "Finance Manager or Owner")))
    exp["status"] = "pending_approval"


@router.post("/expenses")
async def create_expense(body: ExpenseIn, ctx: dict = Depends(ws_ctx)):
    member = ctx["member"]
    if body.member_id and body.member_id != member["id"]:
        if ctx["role"] not in MANAGERS:
            raise HTTPException(status_code=403, detail="Only managers can assign expenses to others")
        member = await db.members.find_one({"id": body.member_id, "workspace_id": ctx["ws_id"], "status": {"$ne": "removed"}}, P)
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
    exp = {**body.model_dump(exclude={"submit", "member_id"}), "id": new_id(), "workspace_id": ctx["ws_id"],
           "member_id": member["id"], "member_name": member["name"], "department": body.department or member["department"],
           "amount_php": to_php(body.amount, body.currency), "status": "draft", "receipts": [], "card_id": None,
           "history": [history_entry(ctx, "draft")], "reconciled": False, "is_synthetic": False,
           "created_by": ctx["member"]["id"], "created_at": now_iso()}
    if body.submit:
        await _route_for_approval(ctx, exp)
    warnings = await budget_warnings(ctx["ws_id"], exp)
    limit = member.get("spending_limit") or 0
    if limit:
        spent = sum(e["amount_php"] for e in await db.expenses.find(
            {"workspace_id": ctx["ws_id"], "member_id": member["id"], "status": {"$in": COUNTED},
             "date": {"$regex": "^" + exp["date"][:7]}}, {"_id": 0, "amount_php": 1}).to_list(5000))
        if spent + exp["amount_php"] > limit:
            warnings.append(f"Exceeds {member['name']}'s monthly spending limit of ₱{limit:,.0f}")
    exp["warnings"] = warnings
    await db.expenses.insert_one(dict(exp))
    await audit(ctx, "expense.created", "expense", exp["id"], f"{exp['merchant']} {exp['amount']} {exp['currency']}")
    exp.pop("_id", None)
    return exp


class ExpensePatch(BaseModel):
    merchant: Optional[str] = Field(None, min_length=1, max_length=120)
    category: Optional[str] = Field(None, max_length=60)
    amount: Optional[float] = Field(None, gt=0, le=100_000_000)
    currency: Optional[Literal["PHP", "USD"]] = None
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=1000)


@router.patch("/expenses/{exp_id}")
async def patch_expense(exp_id: str, body: ExpensePatch, ctx: dict = Depends(ws_ctx)):
    e = await _get_expense(ctx, exp_id)
    if e["status"] not in ("draft", "rejected"):
        raise HTTPException(status_code=409, detail="Only draft or rejected expenses can be edited")
    upd = body.model_dump(exclude_none=True)
    merged = {**e, **upd}
    upd["amount_php"] = to_php(merged["amount"], merged["currency"])
    await db.expenses.update_one({"id": exp_id}, {"$set": upd})
    return await _get_expense(ctx, exp_id)


@router.post("/expenses/{exp_id}/submit")
async def submit_expense(exp_id: str, ctx: dict = Depends(ws_ctx)):
    e = await _get_expense(ctx, exp_id)
    if e["status"] not in ("draft", "rejected"):
        raise HTTPException(status_code=409, detail="Expense is already submitted")
    await _route_for_approval(ctx, e)
    res = await db.expenses.update_one({"id": exp_id, "status": {"$in": ["draft", "rejected"]}},
                                       {"$set": {"status": e["status"], "history": e["history"]}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="Expense changed; refresh and retry")
    await audit(ctx, "expense.submitted", "expense", exp_id)
    return await _get_expense(ctx, exp_id)


class Decision(BaseModel):
    action: Literal["approve", "reject"]
    note: str = Field("", max_length=500)


@router.post("/expenses/{exp_id}/decision")
async def decide_expense(exp_id: str, body: Decision, ctx: dict = Depends(require_roles(*MANAGERS))):
    e = await _get_expense(ctx, exp_id)
    if e["status"] != "pending_approval":
        raise HTTPException(status_code=409, detail="Expense is not pending approval")
    err = can_decide(ctx, e["amount_php"], e["member_id"])
    if err:
        raise HTTPException(status_code=403, detail=err)
    if body.action == "reject" and not body.note.strip():
        raise HTTPException(status_code=422, detail="A reason is required to reject")
    status = "approved" if body.action == "approve" else "rejected"
    res = await db.expenses.update_one({"id": exp_id, "status": "pending_approval"},
                                       {"$set": {"status": status}, "$push": {"history": history_entry(ctx, status, body.note)}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="Already decided")
    await audit(ctx, f"expense.{status}", "expense", exp_id, body.note)
    return await _get_expense(ctx, exp_id)


@router.post("/expenses/{exp_id}/mark-paid")
async def mark_paid(exp_id: str, ctx: dict = Depends(require_roles(*MANAGERS))):
    res = await db.expenses.update_one({"id": exp_id, "workspace_id": ctx["ws_id"], "status": "approved"},
                                       {"$set": {"status": "paid"}, "$push": {"history": history_entry(ctx, "paid", "Recorded as paid — no funds moved by AGOS")}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="Only approved expenses can be recorded as paid")
    await audit(ctx, "expense.recorded_paid", "expense", exp_id)
    return await _get_expense(ctx, exp_id)


@router.post("/expenses/{exp_id}/receipts")
async def upload_receipt(exp_id: str, file: UploadFile = File(...), ctx: dict = Depends(ws_ctx)):
    e = await _get_expense(ctx, exp_id)
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Receipts must be JPG, PNG, WEBP or PDF")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    fid = new_id()
    path = f"{storage.APP_NAME}/receipts/{ctx['ws_id']}/{fid}.{ALLOWED_TYPES[file.content_type]}"
    try:
        result = await storage.put_object(path, data, file.content_type)
    except Exception:
        raise HTTPException(status_code=502, detail="Receipt storage is unavailable; try again")
    rec = {"id": fid, "workspace_id": ctx["ws_id"], "expense_id": exp_id, "storage_path": result["path"],
           "filename": (file.filename or "receipt")[:120], "content_type": file.content_type, "size": len(data),
           "uploaded_by": ctx["actor_name"], "is_deleted": False, "created_at": now_iso()}
    await db.files.insert_one(dict(rec))
    meta = {k: rec[k] for k in ("id", "filename", "content_type", "size", "created_at")}
    await db.expenses.update_one({"id": exp_id}, {"$push": {"receipts": meta}})
    await audit(ctx, "receipt.uploaded", "expense", e["id"], meta["filename"])
    return meta


@router.get("/files/{file_id}")
async def download_file(file_id: str, ctx: dict = Depends(ws_ctx)):
    f = await db.files.find_one({"id": file_id, "workspace_id": ctx["ws_id"], "is_deleted": False}, P)
    if not f:
        raise HTTPException(status_code=404, detail="Not found")
    await _get_expense(ctx, f["expense_id"])
    data, _ = await storage.get_object(f["storage_path"])
    return Response(content=data, media_type=f["content_type"])


# ---------------- Budgets ----------------
class BudgetIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    scope: Literal["business", "department", "employee"]
    department: Optional[str] = Field(None, max_length=40)
    member_id: Optional[str] = None
    amount: float = Field(gt=0, le=1_000_000_000)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    alert_pct: int = Field(80, ge=10, le=100)
    assigned_member_ids: List[str] = Field(default_factory=list, max_length=200)


async def _validate_budget(ctx, body: BudgetIn) -> dict:
    doc = body.model_dump()
    if body.scope == "department" and not body.department:
        raise HTTPException(status_code=422, detail="Department is required")
    if body.scope == "employee":
        m = await db.members.find_one({"id": body.member_id, "workspace_id": ctx["ws_id"]}, P)
        if not m:
            raise HTTPException(status_code=422, detail="Employee is required")
        doc["department"] = m["department"]
        doc["assigned_member_ids"] = [m["id"]]
    else:
        valid = await db.members.distinct("id", {"workspace_id": ctx["ws_id"], "id": {"$in": body.assigned_member_ids}})
        doc["assigned_member_ids"] = valid
        if body.scope == "business":
            doc["department"] = None
        doc["member_id"] = None
    return doc


@router.get("/budgets")
async def list_budgets(ctx: dict = Depends(ws_ctx), period: Optional[str] = None):
    q = {"period": period} if period else {}
    if ctx["role"] not in MANAGERS:
        m = ctx["member"]
        q["$or"] = [{"assigned_member_ids": m["id"]}, {"member_id": m["id"]}, {"scope": "department", "department": m["department"]}]
    return await budgets_with_usage(ctx["ws_id"], q)


@router.post("/budgets")
async def create_budget(body: BudgetIn, ctx: dict = Depends(require_roles("owner"))):
    doc = {**await _validate_budget(ctx, body), "id": new_id(), "workspace_id": ctx["ws_id"], "currency": "PHP",
           "is_synthetic": False, "created_at": now_iso()}
    await db.budgets.insert_one(dict(doc))
    await audit(ctx, "budget.created", "budget", doc["id"], f"{doc['name']} ₱{doc['amount']:,.0f} {doc['period']}")
    return (await budgets_with_usage(ctx["ws_id"], {"id": doc["id"]}))[0]


@router.put("/budgets/{budget_id}")
async def update_budget(budget_id: str, body: BudgetIn, ctx: dict = Depends(require_roles("owner"))):
    res = await db.budgets.update_one({"id": budget_id, "workspace_id": ctx["ws_id"]}, {"$set": await _validate_budget(ctx, body)})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Not found")
    await audit(ctx, "budget.updated", "budget", budget_id, body.name)
    return (await budgets_with_usage(ctx["ws_id"], {"id": budget_id}))[0]


@router.delete("/budgets/{budget_id}")
async def delete_budget(budget_id: str, ctx: dict = Depends(require_roles("owner"))):
    res = await db.budgets.delete_one({"id": budget_id, "workspace_id": ctx["ws_id"]})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Not found")
    await audit(ctx, "budget.deleted", "budget", budget_id)
    return {"ok": True}


# ---------------- Approvals ----------------
@router.get("/approvals")
async def approvals(ctx: dict = Depends(ws_ctx)):
    scope_e = _scope(ctx)
    scope_p = {} if ctx["role"] in MANAGERS else {"requested_by": ctx["member"]["id"]}
    pend_e = await db.expenses.find({"workspace_id": ctx["ws_id"], "status": "pending_approval", **scope_e}, P).sort("date", -1).to_list(500)
    pend_p = await db.payments.find({"workspace_id": ctx["ws_id"], "status": "pending_approval", **scope_p}, P).sort("created_at", -1).to_list(500)
    items = []
    for e in pend_e:
        items.append({"kind": "expense", "id": e["id"], "title": e["merchant"], "requester": e["member_name"],
                      "requester_id": e["member_id"], "department": e["department"], "amount": e["amount"],
                      "currency": e["currency"], "amount_php": e["amount_php"], "date": e["date"],
                      "is_synthetic": e.get("is_synthetic"), "blocked_reason": can_decide(ctx, e["amount_php"], e["member_id"])})
    for p in pend_p:
        items.append({"kind": "payment", "id": p["id"], "title": p["recipient_name"], "requester": p["requested_by_name"],
                      "requester_id": p["requested_by"], "department": p["type"].title() + " payment", "amount": p["amount"],
                      "currency": p["currency"], "amount_php": p["amount_php"], "date": p["created_at"][:10], "rail": p["rail"],
                      "is_synthetic": p.get("is_synthetic"), "blocked_reason": can_decide(ctx, p["amount_php"], p["requested_by"])})
    history = []
    for coll, kind, title_key in ((db.expenses, "expense", "merchant"), (db.payments, "payment", "recipient_name")):
        sc = scope_e if kind == "expense" else scope_p
        docs = await coll.find({"workspace_id": ctx["ws_id"], "history.status": {"$in": ["approved", "rejected"]}, **sc},
                               {"_id": 0, "id": 1, title_key: 1, "amount": 1, "currency": 1, "history": 1}).to_list(1000)
        for d in docs:
            for h in d["history"]:
                if h["status"] in ("approved", "rejected"):
                    history.append({"kind": kind, "id": d["id"], "title": d[title_key], "amount": d["amount"],
                                    "currency": d["currency"], **h})
    history.sort(key=lambda h: h["at"], reverse=True)
    return {"pending": items, "history": history[:100], "threshold": ctx["ws"].get("approval_threshold", 50000)}


# ---------------- Simulated cards ----------------
class CardIn(BaseModel):
    member_id: str
    nickname: str = Field(min_length=2, max_length=60)
    spending_limit: float = Field(gt=0, le=10_000_000)
    budget_id: Optional[str] = None


class CardPatch(BaseModel):
    nickname: Optional[str] = Field(None, min_length=2, max_length=60)
    spending_limit: Optional[float] = Field(None, gt=0, le=10_000_000)


class SimTxnIn(BaseModel):
    merchant: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    amount: float = Field(gt=0, le=10_000_000)


async def _card_spend(card_id: str) -> float:
    month = this_month()
    txns = await db.card_transactions.find({"card_id": card_id, "status": "posted", "date": {"$regex": "^" + month}},
                                           {"_id": 0, "amount_php": 1}).to_list(5000)
    return round(sum(t["amount_php"] for t in txns), 2)


async def _get_card(ctx, card_id) -> dict:
    scope = {} if ctx["role"] in MANAGERS else {"member_id": ctx["member"]["id"]}
    c = await db.cards.find_one({"id": card_id, "workspace_id": ctx["ws_id"], **scope}, P)
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    c["spent_this_month"] = await _card_spend(card_id)
    c["available"] = round(c["spending_limit"] - c["spent_this_month"], 2)
    return c


@router.get("/cards")
async def list_cards(ctx: dict = Depends(ws_ctx)):
    scope = {} if ctx["role"] in MANAGERS else {"member_id": ctx["member"]["id"]}
    ids = await db.cards.distinct("id", {"workspace_id": ctx["ws_id"], **scope})
    return [await _get_card(ctx, i) for i in ids]


@router.post("/cards")
async def create_card(body: CardIn, ctx: dict = Depends(require_roles(*MANAGERS))):
    import random
    m = await db.members.find_one({"id": body.member_id, "workspace_id": ctx["ws_id"], "status": {"$ne": "removed"}}, P)
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    card = {"id": new_id(), "workspace_id": ctx["ws_id"], "member_id": m["id"], "member_name": m["name"],
            "nickname": body.nickname, "last4": f"{random.randint(0, 9999):04d}", "spending_limit": body.spending_limit,
            "status": "active", "budget_id": body.budget_id, "expiry": "12/28", "is_simulated": True, "created_at": now_iso()}
    await db.cards.insert_one(dict(card))
    await audit(ctx, "card.issued_simulated", "card", card["id"], f"{body.nickname} for {m['name']}")
    return await _get_card(ctx, card["id"])


@router.patch("/cards/{card_id}")
async def patch_card(card_id: str, body: CardPatch, ctx: dict = Depends(require_roles(*MANAGERS))):
    await _get_card(ctx, card_id)
    await db.cards.update_one({"id": card_id}, {"$set": body.model_dump(exclude_none=True)})
    await audit(ctx, "card.updated", "card", card_id, str(body.model_dump(exclude_none=True)))
    return await _get_card(ctx, card_id)


class CardStatusIn(BaseModel):
    action: Literal["freeze", "unfreeze"]


@router.post("/cards/{card_id}/status")
async def card_action(card_id: str, body: CardStatusIn, ctx: dict = Depends(ws_ctx)):
    action = body.action
    await _get_card(ctx, card_id)
    if action == "unfreeze" and ctx["role"] not in MANAGERS:
        raise HTTPException(status_code=403, detail="Only managers can unfreeze cards")
    await db.cards.update_one({"id": card_id}, {"$set": {"status": "frozen" if action == "freeze" else "active"}})
    await audit(ctx, f"card.{action}", "card", card_id)
    return await _get_card(ctx, card_id)


@router.get("/cards/{card_id}/transactions")
async def card_transactions(card_id: str, ctx: dict = Depends(ws_ctx)):
    await _get_card(ctx, card_id)
    return await db.card_transactions.find({"card_id": card_id}, P).sort("date", -1).to_list(500)


@router.post("/cards/{card_id}/simulate")
async def simulate_txn(card_id: str, body: SimTxnIn, ctx: dict = Depends(ws_ctx)):
    card = await _get_card(ctx, card_id)
    reason = None
    if card["status"] == "frozen":
        reason = "Card is frozen"
    elif body.amount > card["available"]:
        reason = f"Exceeds remaining card limit (₱{card['available']:,.2f} available)"
    txn = {"id": new_id(), "workspace_id": ctx["ws_id"], "card_id": card_id, "member_id": card["member_id"],
           "merchant": body.merchant, "category": body.category, "amount": body.amount, "currency": "PHP",
           "amount_php": body.amount, "date": datetime.now(timezone.utc).date().isoformat(),
           "status": "declined" if reason else "posted", "decline_reason": reason, "expense_id": None,
           "is_simulated": True, "created_at": now_iso()}
    if not reason:
        member = await db.members.find_one({"id": card["member_id"]}, P)
        exp = {"id": new_id(), "workspace_id": ctx["ws_id"], "member_id": member["id"], "member_name": member["name"],
               "department": member["department"], "merchant": body.merchant, "category": body.category,
               "amount": body.amount, "currency": "PHP", "amount_php": body.amount, "date": txn["date"],
               "description": f"Simulated card spend — {card['nickname']}", "notes": "", "status": "pending_approval",
               "receipts": [], "card_id": card_id, "card_txn_id": txn["id"],
               "history": [system_entry("pending_approval", "Created from simulated card transaction")],
               "reconciled": False, "is_synthetic": True, "created_by": ctx["member"]["id"], "created_at": now_iso()}
        await db.expenses.insert_one(exp)
        txn["expense_id"] = exp["id"]
    await db.card_transactions.insert_one(dict(txn))
    await audit(ctx, "card.simulated_txn", "card", card_id, f"{body.merchant} ₱{body.amount:,.2f} {txn['status']}")
    txn.pop("_id", None)
    return txn
