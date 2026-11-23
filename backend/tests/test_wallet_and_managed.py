# Wallet-connect (Freighter simulated with local Keypair) + managed Stellar regression. Submits 2 small Testnet txs.
import time
import uuid
import pytest
import requests
from stellar_sdk import Keypair, TransactionEnvelope, Network, TransactionBuilder, Account
from pymongo import MongoClient
import os

from conftest import API, _session, act

PASS = Network.TESTNET_NETWORK_PASSPHRASE
EMAIL = "agos.t2wallet+clerk_test@example.com"
ST = {}


def fb(pk):
    requests.get("https://friendbot.stellar.org", params={"addr": pk}, timeout=40)


@pytest.fixture(scope="module")
def s():
    sess, _ = _session(EMAIL)
    sess.get(f"{API}/me")
    r = sess.post(f"{API}/workspaces/demo")
    assert r.status_code == 200, r.text
    sess.headers["X-Workspace-Id"] = r.json()["id"]
    ws = sess.get(f"{API}/workspace").json()
    ST["personas"] = {p["role"]: p["id"] for p in ws["personas"] if p["id"] != ws["real_member_id"]}
    ST["ws_id"] = r.json()["id"]
    return sess


@pytest.fixture(scope="module")
def kp():
    k = Keypair.random()
    fb(k.public_key)
    return k


def sign(xdr, key):
    env = TransactionEnvelope.from_xdr(xdr, PASS)
    env.sign(key)
    return env.to_xdr()


class TestWallet:
    def test_challenge_invalid_key(self, s):
        r = s.post(f"{API}/stellar/wallet/challenge", json={"public_key": "G" + "A" * 55})
        assert r.status_code == 422

    def test_employee_challenge_forbidden(self, s, kp):
        r = s.post(f"{API}/stellar/wallet/challenge", json={"public_key": kp.public_key}, headers=act(s, ST["personas"]["employee"]))
        assert r.status_code == 403

    def test_connect_flow(self, s, kp):
        r = s.post(f"{API}/stellar/wallet/challenge", json={"public_key": kp.public_key})
        assert r.status_code == 200, r.text
        ch = r.json()
        assert ch["network_passphrase"] == PASS and ch["challenge_id"] and ch["xdr"]
        bad = s.post(f"{API}/stellar/wallet/connect", json={"challenge_id": ch["challenge_id"], "signed_xdr": sign(ch["xdr"], Keypair.random())})
        assert bad.status_code == 422
        # unrelated tx signed by the right key must not pass
        other = TransactionBuilder(Account(kp.public_key, -1), network_passphrase=PASS, base_fee=100).append_manage_data_op("agos_auth", b"x").set_timeout(300).build()
        other.sign(kp)
        r2 = s.post(f"{API}/stellar/wallet/connect", json={"challenge_id": ch["challenge_id"], "signed_xdr": other.to_xdr()})
        assert r2.status_code == 422
        ok = s.post(f"{API}/stellar/wallet/connect", json={"challenge_id": ch["challenge_id"], "signed_xdr": sign(ch["xdr"], kp)})
        assert ok.status_code == 200, ok.text
        assert ok.json() == {"public_key": kp.public_key, "mode": "wallet"}
        reuse = s.post(f"{API}/stellar/wallet/connect", json={"challenge_id": ch["challenge_id"], "signed_xdr": sign(ch["xdr"], kp)})
        assert reuse.status_code == 410
        unknown = s.post(f"{API}/stellar/wallet/connect", json={"challenge_id": str(uuid.uuid4()), "signed_xdr": sign(ch["xdr"], kp)})
        assert unknown.status_code == 410

    def test_account_wallet_mode_no_secrets(self, s, kp):
        r = s.get(f"{API}/stellar/account")
        assert r.status_code == 200
        a = r.json()["account"]
        assert a["mode"] == "wallet" and a["public_key"] == kp.public_key and a["wallet"] == "freighter"
        txt = r.text.lower()
        assert "encrypted_secret" not in txt and kp.secret.lower() not in txt and '"secret' not in txt

    def test_second_challenge_and_managed_create_blocked(self, s):
        r = s.post(f"{API}/stellar/wallet/challenge", json={"public_key": Keypair.random().public_key})
        assert r.status_code == 409
        assert s.post(f"{API}/stellar/account").status_code == 409

    def test_wallet_payment_flow(self, s, kp):
        rec = s.post(f"{API}/stellar/demo-recipient").json()
        assert rec["funded"] is True
        p = s.post(f"{API}/payments", json={"type": "international", "recipient_name": "TEST_wallet recipient", "destination_address": rec["public_key"],
                                           "asset_code": "XLM", "amount": "1.25", "purpose": "TEST wallet flow"}).json()
        pid = p["id"]
        # prepare before approval -> 409
        assert s.post(f"{API}/payments/{pid}/stellar/prepare", json={"confirm": True, "idempotency_key": "k-early-123"}).status_code == 409
        assert s.post(f"{API}/payments/{pid}/decision", json={"action": "approve"}).status_code == 200
        r = s.post(f"{API}/payments/{pid}/stellar/submit", json={"confirm": True, "idempotency_key": "k-managed-1"})
        assert r.status_code == 409
        r = s.post(f"{API}/payments/{pid}/stellar/prepare", json={"confirm": True, "idempotency_key": "k-emp-12345"}, headers=act(s, ST["personas"]["employee"]))
        assert r.status_code in (403, 404) and r.status_code == 403
        assert s.post(f"{API}/payments/{pid}/stellar/prepare", json={"confirm": False, "idempotency_key": "k-12345678"}).status_code == 422
        prep = s.post(f"{API}/payments/{pid}/stellar/prepare", json={"confirm": True, "idempotency_key": "k-wallet-1"})
        assert prep.status_code == 200, prep.text
        prep = prep.json()
        assert prep["payment"]["status"] == "awaiting_signature" and prep["xdr"] and prep["address"] == kp.public_key
        assert prep["network_passphrase"] == PASS
        # verify on awaiting_signature -> 409
        assert s.post(f"{API}/payments/{pid}/stellar/verify").status_code == 409
        # disconnect blocked while in-flight
        assert s.post(f"{API}/stellar/account/disconnect").status_code == 409
        # wrong signer
        assert s.post(f"{API}/payments/{pid}/stellar/submit-signed", json={"signed_xdr": sign(prep["xdr"], Keypair.random())}).status_code == 422
        # tampered tx (different amount) signed by right key
        env = TransactionEnvelope.from_xdr(prep["xdr"], PASS)
        env.transaction.operations[0].amount = "999"
        env.signatures = []
        env.sign(kp)
        assert s.post(f"{API}/payments/{pid}/stellar/submit-signed", json={"signed_xdr": env.to_xdr()}).status_code == 422
        assert s.post(f"{API}/payments/{pid}/stellar/submit-signed", json={"signed_xdr": "A" * 60}).status_code == 422
        signed = sign(prep["xdr"], kp)
        r = s.post(f"{API}/payments/{pid}/stellar/submit-signed", json={"signed_xdr": signed})
        assert r.status_code == 200, r.text
        pay = r.json()["payment"]
        assert pay["status"] == "confirmed", pay.get("stellar")
        assert len(pay["stellar"]["tx_hash"]) == 64 and isinstance(pay["stellar"]["ledger"], int)
        again = s.post(f"{API}/payments/{pid}/stellar/submit-signed", json={"signed_xdr": signed}).json()
        assert again["idempotent"] is True and again["payment"]["stellar"]["tx_hash"] == pay["stellar"]["tx_hash"]
        again2 = s.post(f"{API}/payments/{pid}/stellar/prepare", json={"confirm": True, "idempotency_key": "k-wallet-1"}).json()
        assert again2["idempotent"] is True and again2["xdr"] is None
        v = s.post(f"{API}/payments/{pid}/stellar/verify").json()
        assert v["status"] == "confirmed" and v["stellar"]["verification"]["matches_request"] is True
        assert v["stellar"]["verification"]["source"] == kp.public_key

    def test_disconnect_rbac_and_archive(self, s, kp):
        assert s.post(f"{API}/stellar/account/disconnect", headers=act(s, ST["personas"]["finance_manager"])).status_code == 403
        assert s.post(f"{API}/stellar/account/disconnect", headers=act(s, ST["personas"]["employee"])).status_code == 403
        r = s.post(f"{API}/stellar/account/disconnect")
        assert r.status_code == 200 and r.json()["ok"] is True
        assert s.get(f"{API}/stellar/account").json()["account"] is None
        db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        arch = db.stellar_accounts_archive.find_one({"workspace_id": ST["ws_id"], "public_key": kp.public_key})
        assert arch and arch.get("archived_at")
        assert s.post(f"{API}/stellar/account/disconnect").status_code == 404

    # Managed (AGOS-held key) regression after disconnect
    def test_managed_after_disconnect(self, s):
        r = s.post(f"{API}/stellar/account")
        assert r.status_code == 200, r.text
        assert r.json()["funded"] is True
        time.sleep(3)
        a = s.get(f"{API}/stellar/account").json()["account"]
        assert a["mode"] == "managed" and "encrypted_secret" not in a
        rec = s.post(f"{API}/stellar/demo-recipient").json()
        p = s.post(f"{API}/payments", json={"type": "international", "recipient_name": "TEST_managed recipient", "destination_address": rec["public_key"],
                                           "asset_code": "XLM", "amount": "1.5", "purpose": "TEST managed flow"}).json()
        pid = p["id"]
        assert s.post(f"{API}/payments/{pid}/stellar/submit", json={"confirm": True, "idempotency_key": "k-m-early1"}).status_code == 409
        assert s.post(f"{API}/payments/{pid}/stellar/prepare", json={"confirm": True, "idempotency_key": "k-m-prep01"}).status_code == 409
        assert s.post(f"{API}/payments/{pid}/decision", json={"action": "approve"}).status_code == 200
        r = s.post(f"{API}/payments/{pid}/stellar/submit", json={"confirm": True, "idempotency_key": "k-managed-01"})
        assert r.status_code == 200
        pay = r.json()["payment"]
        assert pay["status"] == "confirmed", pay.get("stellar")
        r2 = s.post(f"{API}/payments/{pid}/stellar/submit", json={"confirm": True, "idempotency_key": "k-managed-01"}).json()
        assert r2["idempotent"] is True and r2["payment"]["stellar"]["tx_hash"] == pay["stellar"]["tx_hash"]
        v = s.post(f"{API}/payments/{pid}/stellar/verify").json()
        assert v["status"] == "confirmed" and v["stellar"]["verification"]["matches_request"] is True
