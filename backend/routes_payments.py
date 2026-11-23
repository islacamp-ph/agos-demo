import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from pymongo import ReturnDocument
from stellar_sdk.exceptions import BadRequestError, BaseHorizonError

from core import db, new_id, now_iso, to_php, ws_ctx, require_roles, audit, history_entry, MANAGERS
from routes_finance import Decision, can_decide
import stellar_service as stellar

router = APIRouter(prefix="/api")
P = {"_id": 0}
log = logging.getLogger("agos.stellar")
MAX_XLM = Decimal("1000")


class PaymentIn(BaseModel):
    type: Literal["domestic", "international"]
    recipient_name: str = Field(min_length=2, max_length=120)
    recipient_bank: Optional[str] = Field(None, max_length=60)
    recipient_account_last4: Optional[str] = Field(None, pattern=r"^\d{4}$")
    destination_address: Optional[str] = Field(None, max_length=56)
    asset_code: Optional[str] = "XLM"
    amount: str = Field(min_length=1, max_length=20)
    purpose: str = Field(min_length=3, max_length=200)

    @field_validator("amount")
    @classmethod
    def _amount(cls, v):
        try:
            d = Decimal(v)
        except InvalidOperation:
            raise ValueError("Amount must be a number")
        if d <= 0 or d.as_tuple().exponent < -7:
            raise ValueError("Amount must be positive with at most 7 decimals")
        return v


async def _get_payment(ctx: dict, pid: str) -> dict:
    scope = {} if ctx["role"] in MANAGERS else {"requested_by": ctx["member"]["id"]}
    p = await db.payments.find_one({"id": pid, "workspace_id": ctx["ws_id"], **scope}, P)
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    if p.get("stellar") and p["stellar"].get("tx_hash"):
        p["stellar"]["links"] = stellar.tx_links(p["stellar"]["tx_hash"])
    return p


@router.get("/payments")
async def list_payments(ctx: dict = Depends(ws_ctx), type: Optional[str] = None):
    q = {"workspace_id": ctx["ws_id"]}
    if ctx["role"] not in MANAGERS:
        q["requested_by"] = ctx["member"]["id"]
    if type:
        q["type"] = type
    docs = await db.payments.find(q, P).sort("created_at", -1).to_list(1000)
    for p in docs:
        if p.get("stellar") and p["stellar"].get("tx_hash"):
            p["stellar"]["links"] = stellar.tx_links(p["stellar"]["tx_hash"])
    return docs


@router.get("/payments/{pid}")
async def get_payment(pid: str, ctx: dict = Depends(ws_ctx)):
    return await _get_payment(ctx, pid)


@router.post("/payments")
async def create_payment(body: PaymentIn, ctx: dict = Depends(ws_ctx)):
    amount = Decimal(body.amount)
    doc = {"id": new_id(), "workspace_id": ctx["ws_id"], "type": body.type, "recipient_name": body.recipient_name,
           "purpose": body.purpose, "status": "pending_approval", "requested_by": ctx["member"]["id"],
           "requested_by_name": ctx["member"]["name"], "stellar": None, "reconciled": False, "is_synthetic": False,
           "created_at": now_iso()}
    if body.type == "domestic":
        doc.update({"rail": "demo_bank_transfer", "recipient_bank": body.recipient_bank or "Demo Bank",
                    "recipient_account_last4": body.recipient_account_last4, "destination_address": None,
                    "asset_code": None, "amount": float(amount), "currency": "PHP", "amount_php": to_php(float(amount), "PHP")})
    else:
        if body.asset_code not in stellar.ASSETS or not stellar.ASSETS[body.asset_code]["enabled"]:
            raise HTTPException(status_code=422, detail="Unsupported asset")
        if not stellar.valid_address(body.destination_address):
            raise HTTPException(status_code=422, detail="Destination must be a valid Stellar public key (G…, 56 characters)")
        if amount > MAX_XLM:
            raise HTTPException(status_code=422, detail="Testnet demo payments are capped at 1,000 XLM")
        acct = await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}, {"_id": 0, "public_key": 1})
        if acct and acct["public_key"] == body.destination_address:
            raise HTTPException(status_code=422, detail="Destination cannot be the workspace's own account")
        meta = stellar.ASSETS[body.asset_code]
        doc.update({"rail": "stellar_testnet", "recipient_bank": None, "recipient_account_last4": None,
                    "destination_address": body.destination_address, "asset_code": meta["code"],
                    "asset_issuer": meta["issuer"], "amount": float(amount), "amount_str": f"{amount:.7f}",
                    "currency": meta["code"], "amount_php": 0})
    doc["history"] = [history_entry(ctx, "pending_approval", "Payment request submitted")]
    await db.payments.insert_one(dict(doc))
    await audit(ctx, "payment.requested", "payment", doc["id"], f"{body.type} {body.amount} {doc['currency']}")
    return await _get_payment(ctx, doc["id"])


@router.post("/payments/{pid}/decision")
async def decide_payment(pid: str, body: Decision, ctx: dict = Depends(require_roles(*MANAGERS))):
    p = await _get_payment(ctx, pid)
    if p["status"] != "pending_approval":
        raise HTTPException(status_code=409, detail="Payment is not pending approval")
    err = can_decide(ctx, p["amount_php"], p["requested_by"])
    if err:
        raise HTTPException(status_code=403, detail=err)
    if body.action == "reject" and not body.note.strip():
        raise HTTPException(status_code=422, detail="A reason is required to reject")
    status = "approved" if body.action == "approve" else "rejected"
    res = await db.payments.update_one({"id": pid, "status": "pending_approval"},
                                       {"$set": {"status": status}, "$push": {"history": history_entry(ctx, status, body.note)}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="Already decided")
    await audit(ctx, f"payment.{status}", "payment", pid, body.note)
    return await _get_payment(ctx, pid)


@router.post("/payments/{pid}/record-paid")
async def record_domestic(pid: str, ctx: dict = Depends(require_roles(*MANAGERS))):
    res = await db.payments.update_one(
        {"id": pid, "workspace_id": ctx["ws_id"], "type": "domestic", "status": "approved"},
        {"$set": {"status": "recorded_as_paid"},
         "$push": {"history": history_entry(ctx, "recorded_as_paid", "Demo record only — no bank transfer was made")}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="Only approved domestic payments can be recorded")
    await audit(ctx, "payment.recorded_demo", "payment", pid)
    return await _get_payment(ctx, pid)


# ---------------- Stellar ----------------
async def _set_stellar(pid: str, status: str, fields: dict, note: str, actor: str = "AGOS Workflow") -> None:
    upd = {"status": status, **{f"stellar.{k}": v for k, v in fields.items()}}
    await db.payments.update_one({"id": pid}, {"$set": upd, "$push": {"history": {
        "status": status, "actor_name": actor, "actor_member_id": None, "at": now_iso(), "note": note}}})


def _ops_match(p: dict, found: dict) -> bool:
    return any(o.get("to") == p["destination_address"] and o.get("amount") is not None
               and Decimal(o["amount"]) == Decimal(str(p["amount"])) for o in found["operations"])


async def refresh_stellar(p: dict) -> None:
    st = p.get("stellar") or {}
    h = st.get("tx_hash")
    if not h:
        return
    found = await stellar.get_transaction(h)
    verification = {"checked_at": now_iso(), "found": found is not None}
    if found is None:
        submitted = datetime.fromisoformat(st["submitted_at"])
        expired = datetime.now(timezone.utc) - submitted > timedelta(seconds=stellar.TX_VALIDITY_SECONDS + 30)
        if p["status"] in ("submitting", "pending_verification") and expired:
            await _set_stellar(p["id"], "failed", {"status": "not_found", "verification": verification,
                               "last_error": "Not found on ledger and validity window expired — safe to retry"},
                               "Transaction never reached the ledger")
        else:
            await db.payments.update_one({"id": p["id"]}, {"$set": {"stellar.verification": verification}})
        return
    verification.update({"successful": found["successful"], "ledger": found["ledger"], "source": found["source"],
                         "operations": found["operations"], "fee_charged": found["fee_charged"],
                         "matches_request": _ops_match(p, found)})
    if found["successful"]:
        if p["status"] != "confirmed":
            await _set_stellar(p["id"], "confirmed", {"status": "confirmed", "ledger": found["ledger"],
                               "confirmed_at": found["created_at"], "verification": verification},
                               f"Confirmed on Stellar Testnet ledger {found['ledger']}")
        else:
            await db.payments.update_one({"id": p["id"]}, {"$set": {"stellar.verification": verification}})
    else:
        await _set_stellar(p["id"], "failed", {"status": "failed_on_ledger", "ledger": found["ledger"],
                           "verification": verification, "last_error": "Transaction failed on ledger"}, "Failed on ledger")


class SubmitIn(BaseModel):
    confirm: bool
    idempotency_key: str = Field(min_length=8, max_length=64)


@router.post("/payments/{pid}/stellar/submit")
async def stellar_submit(pid: str, body: SubmitIn, ctx: dict = Depends(require_roles(*MANAGERS))):
    if not body.confirm:
        raise HTTPException(status_code=422, detail="Explicit confirmation is required")
    p = await _get_payment(ctx, pid)
    if p["type"] != "international":
        raise HTTPException(status_code=409, detail="Only international payments settle on Stellar")
    if p["status"] in ("submitting", "pending_verification", "confirmed"):
        return {"payment": p, "idempotent": True}
    acct = await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}, P)
    if not acct:
        raise HTTPException(status_code=409, detail="Create the workspace Stellar Testnet account first")
    await db.payments.update_one({"id": pid, "stellar": None}, {"$set": {"stellar": {}}})
    claimed = await db.payments.find_one_and_update(
        {"id": pid, "workspace_id": ctx["ws_id"], "status": {"$in": ["approved", "failed"]}},
        {"$set": {"status": "submitting", "stellar.idempotency_key": body.idempotency_key}},
        projection=P, return_document=ReturnDocument.AFTER)
    if not claimed:
        return {"payment": await _get_payment(ctx, pid), "idempotent": True}
    prev = claimed.get("stellar") or {}
    if prev.get("tx_hash"):
        try:
            found = await stellar.get_transaction(prev["tx_hash"])
        except Exception:
            await _set_stellar(pid, "failed", {"last_error": "Could not check previous attempt; network unavailable"}, "Retry blocked")
            raise HTTPException(status_code=504, detail="Stellar network unreachable; try again")
        if found and found["successful"]:
            await refresh_stellar(claimed)
            return {"payment": await _get_payment(ctx, pid), "idempotent": True}
    amount = claimed.get("amount_str") or f"{Decimal(str(claimed['amount'])):.7f}"
    try:
        tx, tx_hash, source, op = await stellar.build_signed(acct["encrypted_secret"], claimed["destination_address"],
                                                             amount, f"AGOS {pid[:8]}", claimed["asset_code"])
    except ValueError as e:
        await _set_stellar(pid, "failed", {"last_error": str(e)}, "Validation failed before submission")
        return {"payment": await _get_payment(ctx, pid), "idempotent": False}
    except Exception as e:
        log.warning("stellar build failed: %s", type(e).__name__)
        await _set_stellar(pid, "failed", {"last_error": "Could not load workspace account from Stellar (unfunded or network unavailable)"}, "Build failed")
        return {"payment": await _get_payment(ctx, pid), "idempotent": False}
    st = {"network": stellar.NETWORK, "source": source, "destination": claimed["destination_address"],
          "asset_code": claimed["asset_code"], "asset_issuer": claimed.get("asset_issuer"), "amount": amount,
          "tx_hash": tx_hash, "operation": op, "ledger": None, "submitted_at": now_iso(), "confirmed_at": None,
          "status": "submitting", "attempts": prev.get("attempts", 0) + 1, "last_error": None,
          "idempotency_key": body.idempotency_key, "verification": None, "submitted_by": ctx["actor_name"]}
    await db.payments.update_one({"id": pid}, {"$set": {"stellar": st}, "$push": {
        "history": history_entry(ctx, "submitting", f"Confirmed and signed; tx {tx_hash[:12]}…")}})
    await audit(ctx, "stellar.submitted", "payment", pid, tx_hash)
    try:
        res = await stellar.submit(tx)
        if res.get("successful"):
            p2 = await db.payments.find_one({"id": pid}, P)
            try:
                await refresh_stellar(p2)
            except Exception:
                await _set_stellar(pid, "pending_verification", {"status": "submitted", "ledger": res.get("ledger")},
                                   "Accepted by Horizon; verification pending")
        else:
            await _set_stellar(pid, "failed", {"status": "failed", "last_error": "Horizon reported unsuccessful"}, "Failed")
    except BadRequestError as e:
        codes = (e.extras or {}).get("result_codes") if hasattr(e, "extras") else None
        await _set_stellar(pid, "failed", {"status": "rejected_by_network", "last_error": f"Rejected by network: {codes or e.status}"}, "Rejected by Stellar network")
    except (asyncio.TimeoutError, BaseHorizonError, Exception) as e:
        log.warning("stellar submit uncertain: %s", type(e).__name__)
        await _set_stellar(pid, "pending_verification", {"status": "unknown", "last_error": "Network timeout — use Verify to reconcile"},
                           "Submission outcome unknown; awaiting verification")
    return {"payment": await _get_payment(ctx, pid), "idempotent": False}


@router.post("/payments/{pid}/stellar/verify")
async def stellar_verify(pid: str, ctx: dict = Depends(ws_ctx)):
    p = await _get_payment(ctx, pid)
    if not (p.get("stellar") or {}).get("tx_hash"):
        raise HTTPException(status_code=409, detail="No Stellar transaction to verify")
    try:
        await refresh_stellar(p)
    except Exception:
        raise HTTPException(status_code=504, detail="Stellar network unreachable; try again")
    await audit(ctx, "stellar.verified", "payment", pid, p["stellar"]["tx_hash"])
    return await _get_payment(ctx, pid)


async def refresh_pending_on_startup() -> None:
    docs = await db.payments.find({"status": {"$in": ["submitting", "pending_verification"]}, "stellar.tx_hash": {"$ne": None}}, P).to_list(200)
    for p in docs:
        try:
            await refresh_stellar(p)
        except Exception as e:
            log.warning("startup refresh failed: %s", type(e).__name__)


def _public_acct(a: dict) -> dict:
    return {"public_key": a["public_key"], "network": a["network"], "created_at": a["created_at"],
            "explorer": f"{stellar.EXPLORER}/account/{a['public_key']}"}


@router.get("/stellar/account")
async def get_account(ctx: dict = Depends(ws_ctx)):
    a = await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}, {"_id": 0, "encrypted_secret": 0})
    if not a:
        return {"account": None, "assets": list(stellar.ASSETS.values()), "network": stellar.NETWORK}
    try:
        info = await stellar.account_info(a["public_key"])
    except Exception:
        info = {"exists": None, "balances": [], "error": "Stellar network unreachable"}
    return {"account": {**_public_acct(a), **info}, "assets": list(stellar.ASSETS.values()), "network": stellar.NETWORK}


@router.post("/stellar/account")
async def create_account(ctx: dict = Depends(require_roles(*MANAGERS))):
    if await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}):
        raise HTTPException(status_code=409, detail="This workspace already has a Stellar Testnet account")
    pub, enc = stellar.new_keypair()
    doc = {"id": new_id(), "workspace_id": ctx["ws_id"], "public_key": pub, "encrypted_secret": enc,
           "network": stellar.NETWORK, "created_at": now_iso()}
    await db.stellar_accounts.insert_one(doc)
    try:
        fb = await stellar.friendbot(pub)
    except Exception:
        fb = {"ok": False}
    await audit(ctx, "stellar.account_created", "stellar_account", doc["id"], pub)
    return {"public_key": pub, "funded": fb["ok"]}


@router.post("/stellar/account/fund")
async def fund_account(ctx: dict = Depends(require_roles(*MANAGERS))):
    a = await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}, {"_id": 0, "public_key": 1})
    if not a:
        raise HTTPException(status_code=404, detail="No Stellar account")
    try:
        fb = await stellar.friendbot(a["public_key"])
    except Exception:
        raise HTTPException(status_code=504, detail="Friendbot unreachable; try again")
    if not fb["ok"]:
        raise HTTPException(status_code=409, detail="Friendbot declined (account is likely already funded)")
    return {"ok": True}


@router.get("/stellar/transactions")
async def account_transactions(ctx: dict = Depends(ws_ctx)):
    a = await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}, {"_id": 0, "public_key": 1})
    if not a:
        return []
    try:
        return await stellar.recent_payments(a["public_key"])
    except Exception:
        raise HTTPException(status_code=504, detail="Stellar network unreachable")


@router.post("/stellar/demo-recipient")
async def demo_recipient(ctx: dict = Depends(ws_ctx)):
    pub, _ = stellar.new_keypair()  # secret is discarded; this address is receive-only for demos
    try:
        fb = await stellar.friendbot(pub)
    except Exception:
        fb = {"ok": False}
    await db.stellar_recipients.insert_one({"id": new_id(), "workspace_id": ctx["ws_id"], "public_key": pub,
                                            "funded": fb["ok"], "created_at": now_iso()})
    return {"public_key": pub, "funded": fb["ok"]}
