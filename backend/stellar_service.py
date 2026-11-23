import os
import asyncio

import requests
from cryptography.fernet import Fernet
from starlette.concurrency import run_in_threadpool
from stellar_sdk import Asset, Keypair, Network, Server, StrKey, TransactionBuilder
from stellar_sdk.exceptions import NotFoundError

HORIZON_URL = os.environ["STELLAR_HORIZON_URL"]
NETWORK = os.environ["STELLAR_NETWORK"]
PASSPHRASE = Network.TESTNET_NETWORK_PASSPHRASE
FRIENDBOT_URL = "https://friendbot.stellar.org"
EXPLORER = "https://stellar.expert/explorer/testnet"
TIMEOUT = 45
TX_VALIDITY_SECONDS = 120

# Asset registry: future Stellar-issued stablecoins plug in here once real issuers and partners exist.
ASSETS = {
    "XLM": {"code": "XLM", "issuer": None, "type": "native", "label": "Testnet XLM", "enabled": True},
}

_fernet = Fernet(os.environ["STELLAR_ENCRYPTION_KEY"].encode())
server = Server(HORIZON_URL)


async def _run(fn, *args):
    return await asyncio.wait_for(run_in_threadpool(fn, *args), TIMEOUT)


def valid_address(address: str) -> bool:
    return StrKey.is_valid_ed25519_public_key(address or "")


def asset_for(code: str) -> Asset:
    meta = ASSETS[code]
    return Asset.native() if meta["type"] == "native" else Asset(meta["code"], meta["issuer"])


def new_keypair() -> tuple[str, str]:
    kp = Keypair.random()
    return kp.public_key, _fernet.encrypt(kp.secret.encode()).decode()


def tx_links(tx_hash: str) -> dict:
    return {"explorer": f"{EXPLORER}/tx/{tx_hash}", "horizon": f"{HORIZON_URL}/transactions/{tx_hash}"}


def _friendbot(public_key: str) -> dict:
    r = requests.get(FRIENDBOT_URL, params={"addr": public_key}, timeout=30)
    return {"ok": r.status_code == 200, "status": r.status_code}


async def friendbot(public_key: str) -> dict:
    return await _run(_friendbot, public_key)


def _account(public_key: str):
    try:
        return server.accounts().account_id(public_key).call()
    except NotFoundError:
        return None


async def account_info(public_key: str) -> dict:
    acc = await _run(_account, public_key)
    if acc is None:
        return {"exists": False, "balances": []}
    balances = [{"asset": "XLM" if b["asset_type"] == "native" else b.get("asset_code"),
                 "issuer": b.get("asset_issuer"), "balance": b["balance"]} for b in acc["balances"]]
    return {"exists": True, "balances": balances, "sequence": acc["sequence"]}


def _payments(public_key: str) -> list:
    try:
        recs = server.payments().for_account(public_key).order(desc=True).limit(20).call()["_embedded"]["records"]
    except NotFoundError:
        return []
    out = []
    for r in recs:
        out.append({
            "id": r["id"], "type": r["type"], "tx_hash": r["transaction_hash"], "created_at": r["created_at"],
            "from": r.get("from") or r.get("funder") or r.get("source_account"),
            "to": r.get("to") or r.get("account"),
            "amount": r.get("amount") or r.get("starting_balance"),
            "asset": "XLM" if r.get("asset_type", "native") == "native" else r.get("asset_code"),
            "successful": r.get("transaction_successful", True), **tx_links(r["transaction_hash"]),
        })
    return out


async def recent_payments(public_key: str) -> list:
    return await _run(_payments, public_key)


def _build(enc_secret: str, destination: str, amount: str, memo: str, asset_code: str):
    kp = Keypair.from_secret(_fernet.decrypt(enc_secret.encode()).decode())
    source = server.load_account(kp.public_key)
    dest_exists = _account(destination) is not None
    builder = TransactionBuilder(source, network_passphrase=PASSPHRASE, base_fee=server.fetch_base_fee())
    if dest_exists:
        builder.append_payment_op(destination=destination, asset=asset_for(asset_code), amount=amount)
        op = "payment"
    else:
        if asset_code != "XLM" or float(amount) < 1:
            raise ValueError("Destination account does not exist yet; send at least 1 XLM to create it")
        builder.append_create_account_op(destination=destination, starting_balance=amount)
        op = "create_account"
    tx = builder.add_text_memo(memo[:28]).set_timeout(TX_VALIDITY_SECONDS).build()
    tx.sign(kp)
    return tx, tx.hash_hex(), kp.public_key, op


async def build_signed(enc_secret: str, destination: str, amount: str, memo: str, asset_code: str):
    return await _run(_build, enc_secret, destination, amount, memo, asset_code)


async def submit(tx) -> dict:
    return await _run(server.submit_transaction, tx)


def _get_tx(tx_hash: str):
    try:
        tx = server.transactions().transaction(tx_hash).call()
    except NotFoundError:
        return None
    ops = server.operations().for_transaction(tx_hash).call()["_embedded"]["records"]
    return {"successful": tx["successful"], "ledger": tx["ledger"], "created_at": tx["created_at"],
            "source": tx["source_account"], "fee_charged": tx.get("fee_charged"), "memo": tx.get("memo"),
            "operations": [{"type": o["type"], "to": o.get("to") or o.get("account"),
                            "amount": o.get("amount") or o.get("starting_balance")} for o in ops]}


async def get_transaction(tx_hash: str):
    return await _run(_get_tx, tx_hash)
