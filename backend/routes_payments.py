import asyncio
import logging
import secrets
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
FM_XLM_LIMIT = 100.0


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
    if not err and p["currency"] == "XLM" and ctx["role"] == "finance_manager" and p["amount"] > FM_XLM_LIMIT:
        err = f"Stellar payments above {FM_XLM_LIMIT:g} XLM require owner approval"
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
    if not h or not st.get("submitted_at"):
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
    if p["status"] not in ("approved", "failed"):
        raise HTTPException(status_code=409, detail="Payment must be approved before submission")
    acct = await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}, P)
    if not acct:
        raise HTTPException(status_code=409, detail="Create the workspace Stellar Testnet account first")
    if acct.get("mode") == "wallet":
        raise HTTPException(status_code=409, detail="This workspace signs with its connected wallet; use wallet signing")
    claimed = await _claim(ctx, pid, ["approved", "failed"], "submitting", body.idempotency_key)
    if not claimed:
        return {"payment": await _get_payment(ctx, pid), "idempotent": True}
    prev = claimed.get("stellar") or {}
    if await _already_settled(ctx, claimed):
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
    await _send(pid, tx)
    return {"payment": await _get_payment(ctx, pid), "idempotent": False}


async def _claim(ctx: dict, pid: str, from_statuses: list, to_status: str, key: str):
    await db.payments.update_one({"id": pid, "stellar": None}, {"$set": {"stellar": {}}})
    return await db.payments.find_one_and_update(
        {"id": pid, "workspace_id": ctx["ws_id"], "status": {"$in": from_statuses}},
        {"$set": {"status": to_status, "stellar.idempotency_key": key}},
        projection=P, return_document=ReturnDocument.AFTER)


async def _already_settled(ctx: dict, claimed: dict) -> bool:
    prev = claimed.get("stellar") or {}
    if not prev.get("tx_hash"):
        return False
    try:
        found = await stellar.get_transaction(prev["tx_hash"])
    except Exception:
        await _set_stellar(claimed["id"], "failed", {"last_error": "Could not check previous attempt; network unavailable"}, "Retry blocked")
        raise HTTPException(status_code=504, detail="Stellar network unreachable; try again")
    if found and found["successful"]:
        await refresh_stellar({**claimed, "status": "submitting"})
        return True
    return False


async def _send(pid: str, tx) -> None:
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


@router.post("/payments/{pid}/stellar/prepare")
async def stellar_prepare(pid: str, body: SubmitIn, ctx: dict = Depends(require_roles(*MANAGERS))):
    if not body.confirm:
        raise HTTPException(status_code=422, detail="Explicit confirmation is required")
    p = await _get_payment(ctx, pid)
    if p["type"] != "international":
        raise HTTPException(status_code=409, detail="Only international payments settle on Stellar")
    if p["status"] in ("submitting", "pending_verification", "confirmed"):
        return {"payment": p, "idempotent": True, "xdr": None}
    if p["status"] not in ("approved", "failed", "awaiting_signature"):
        raise HTTPException(status_code=409, detail="Payment must be approved before submission")
    acct = await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}, P)
    if not acct or acct.get("mode") != "wallet":
        raise HTTPException(status_code=409, detail="Connect a Stellar wallet for this workspace first")
    claimed = await _claim(ctx, pid, ["approved", "failed", "awaiting_signature"], "awaiting_signature", body.idempotency_key)
    if not claimed:
        return {"payment": await _get_payment(ctx, pid), "idempotent": True, "xdr": None}
    if await _already_settled(ctx, claimed):
        return {"payment": await _get_payment(ctx, pid), "idempotent": True, "xdr": None}
    prev = claimed.get("stellar") or {}
    amount = claimed.get("amount_str") or f"{Decimal(str(claimed['amount'])):.7f}"
    try:
        tx, tx_hash, xdr, op = await stellar.build_unsigned(acct["public_key"], claimed["destination_address"],
                                                            amount, f"AGOS {pid[:8]}", claimed["asset_code"])
    except ValueError as e:
        await _set_stellar(pid, "failed", {"last_error": str(e)}, "Validation failed before signing")
        return {"payment": await _get_payment(ctx, pid), "idempotent": False, "xdr": None}
    except Exception as e:
        log.warning("stellar prepare failed: %s", type(e).__name__)
        await _set_stellar(pid, "failed", {"last_error": "Could not load the wallet account from Stellar (unfunded or network unavailable)"}, "Prepare failed")
        return {"payment": await _get_payment(ctx, pid), "idempotent": False, "xdr": None}
    st = {"network": stellar.NETWORK, "source": acct["public_key"], "destination": claimed["destination_address"],
          "asset_code": claimed["asset_code"], "asset_issuer": claimed.get("asset_issuer"), "amount": amount,
          "tx_hash": tx_hash, "unsigned_xdr": xdr, "operation": op, "ledger": None, "prepared_at": now_iso(),
          "submitted_at": None, "confirmed_at": None, "status": "awaiting_signature", "signing": "wallet",
          "attempts": prev.get("attempts", 0), "last_error": None, "idempotency_key": body.idempotency_key,
          "verification": None, "submitted_by": ctx["actor_name"]}
    await db.payments.update_one({"id": pid}, {"$set": {"stellar": st}, "$push": {
        "history": history_entry(ctx, "awaiting_signature", "Confirmed; prepared for wallet signature")}})
    return {"payment": await _get_payment(ctx, pid), "idempotent": False, "xdr": xdr,
            "network_passphrase": stellar.PASSPHRASE, "address": acct["public_key"]}


class SignedIn(BaseModel):
    signed_xdr: str = Field(min_length=50, max_length=20000)


@router.post("/payments/{pid}/stellar/submit-signed")
async def stellar_submit_signed(pid: str, body: SignedIn, ctx: dict = Depends(require_roles(*MANAGERS))):
    p = await _get_payment(ctx, pid)
    if p["status"] in ("submitting", "pending_verification", "confirmed"):
        return {"payment": p, "idempotent": True}
    if p["status"] != "awaiting_signature":
        raise HTTPException(status_code=409, detail="Prepare the payment for signing first")
    acct = await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}, P)
    if not acct or acct.get("mode") != "wallet":
        raise HTTPException(status_code=409, detail="No connected wallet")
    try:
        env = stellar.parse_signed(body.signed_xdr)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid signed transaction")
    if env.hash_hex() != p["stellar"]["tx_hash"]:
        raise HTTPException(status_code=422, detail="Signed transaction does not match the prepared payment")
    if not stellar.signed_by(env, acct["public_key"]):
        raise HTTPException(status_code=422, detail="Transaction is not signed by the connected wallet")
    claimed = await db.payments.find_one_and_update(
        {"id": pid, "status": "awaiting_signature"},
        {"$set": {"status": "submitting", "stellar.status": "submitting", "stellar.submitted_at": now_iso(),
                  "stellar.attempts": (p["stellar"].get("attempts") or 0) + 1},
         "$push": {"history": history_entry(ctx, "submitting", f"Signed in wallet; tx {env.hash_hex()[:12]}…")}},
        projection=P)
    if not claimed:
        return {"payment": await _get_payment(ctx, pid), "idempotent": True}
    await audit(ctx, "stellar.submitted_wallet", "payment", pid, env.hash_hex())
    await _send(pid, env)
    return {"payment": await _get_payment(ctx, pid), "idempotent": False}


@router.post("/payments/{pid}/stellar/verify")
async def stellar_verify(pid: str, ctx: dict = Depends(ws_ctx)):
    p = await _get_payment(ctx, pid)
    if not (p.get("stellar") or {}).get("tx_hash") or p["status"] == "awaiting_signature":
        raise HTTPException(status_code=409, detail="No submitted Stellar transaction to verify")
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
            "mode": a.get("mode", "managed"), "wallet": a.get("wallet"),
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


# ---------------- Connected wallet (Freighter) ----------------
class ChallengeIn(BaseModel):
    public_key: str = Field(min_length=56, max_length=56)


class ConnectIn(BaseModel):
    challenge_id: str
    signed_xdr: str = Field(min_length=50, max_length=20000)


@router.post("/stellar/wallet/challenge")
async def wallet_challenge(body: ChallengeIn, ctx: dict = Depends(require_roles(*MANAGERS))):
    if not stellar.valid_address(body.public_key):
        raise HTTPException(status_code=422, detail="Invalid Stellar public key")
    if await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}):
        raise HTTPException(status_code=409, detail="Disconnect the current Stellar account first")
    tx_hash, xdr = stellar.challenge_tx(body.public_key, secrets.token_hex(16))
    cid = new_id()
    await db.stellar_challenges.insert_one({"id": cid, "workspace_id": ctx["ws_id"], "public_key": body.public_key,
                                            "hash": tx_hash, "used": False, "created_at": now_iso()})
    return {"challenge_id": cid, "xdr": xdr, "network_passphrase": stellar.PASSPHRASE}


@router.post("/stellar/wallet/connect")
async def wallet_connect(body: ConnectIn, ctx: dict = Depends(require_roles(*MANAGERS))):
    ch = await db.stellar_challenges.find_one({"id": body.challenge_id, "workspace_id": ctx["ws_id"], "used": False}, P)
    if not ch or datetime.now(timezone.utc) - datetime.fromisoformat(ch["created_at"]) > timedelta(minutes=5):
        raise HTTPException(status_code=410, detail="Challenge expired; try connecting again")
    try:
        env = stellar.parse_signed(body.signed_xdr)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid signed challenge")
    if env.hash_hex() != ch["hash"] or not stellar.signed_by(env, ch["public_key"]):
        raise HTTPException(status_code=422, detail="Wallet signature could not be verified")
    await db.stellar_challenges.update_one({"id": ch["id"]}, {"$set": {"used": True}})
    if await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}):
        raise HTTPException(status_code=409, detail="Disconnect the current Stellar account first")
    doc = {"id": new_id(), "workspace_id": ctx["ws_id"], "public_key": ch["public_key"], "encrypted_secret": None,
           "mode": "wallet", "wallet": "freighter", "network": stellar.NETWORK, "created_at": now_iso(), "verified_at": now_iso()}
    await db.stellar_accounts.insert_one(doc)
    await audit(ctx, "stellar.wallet_connected", "stellar_account", doc["id"], ch["public_key"])
    return {"public_key": ch["public_key"], "mode": "wallet"}


@router.post("/stellar/account/disconnect")
async def disconnect_account(ctx: dict = Depends(require_roles("owner"))):
    a = await db.stellar_accounts.find_one({"workspace_id": ctx["ws_id"]}, P)
    if not a:
        raise HTTPException(status_code=404, detail="No Stellar account")
    if await db.payments.count_documents({"workspace_id": ctx["ws_id"], "status": {"$in": ["submitting", "awaiting_signature", "pending_verification"]}}):
        raise HTTPException(status_code=409, detail="Finish or verify in-flight Stellar payments first")
    await db.stellar_accounts_archive.insert_one({**a, "archived_at": now_iso(), "archived_by": ctx["actor_name"]})
    await db.stellar_accounts.delete_one({"workspace_id": ctx["ws_id"], "id": a["id"]})
    await audit(ctx, "stellar.account_disconnected", "stellar_account", a["id"], a["public_key"])
    return {"ok": True}
