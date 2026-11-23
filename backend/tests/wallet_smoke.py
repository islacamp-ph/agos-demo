import time
import requests
from stellar_sdk import Keypair, TransactionEnvelope, Network
from smoke_test import token_for, BASE

PASS = Network.TESTNET_NETWORK_PASSPHRASE

if __name__ == "__main__":
    tok, _ = token_for("agos.wallet+clerk_test@example.com")
    H = {"Authorization": f"Bearer {tok}"}
    H["X-Workspace-Id"] = requests.post(f"{BASE}/workspaces/demo", headers=H).json()["id"]
    kp = Keypair.random()
    requests.get("https://friendbot.stellar.org", params={"addr": kp.public_key}, timeout=30)
    ch = requests.post(f"{BASE}/stellar/wallet/challenge", headers=H, json={"public_key": kp.public_key}).json()
    bad = Keypair.random()
    env = TransactionEnvelope.from_xdr(ch["xdr"], PASS); env.sign(bad)
    print("wrong signer", requests.post(f"{BASE}/stellar/wallet/connect", headers=H, json={"challenge_id": ch["challenge_id"], "signed_xdr": env.to_xdr()}).status_code)
    env = TransactionEnvelope.from_xdr(ch["xdr"], PASS); env.sign(kp)
    print("connect", requests.post(f"{BASE}/stellar/wallet/connect", headers=H, json={"challenge_id": ch["challenge_id"], "signed_xdr": env.to_xdr()}).json())
    print("reuse challenge", requests.post(f"{BASE}/stellar/wallet/connect", headers=H, json={"challenge_id": ch["challenge_id"], "signed_xdr": env.to_xdr()}).status_code)
    a = requests.get(f"{BASE}/stellar/account", headers=H).json()["account"]
    print("account", a["mode"], a["balances"], "encrypted_secret" in a)
    p = requests.get(f"{BASE}/payments", headers=H, params={"type": "international"}).json()[0]
    print("approve", requests.post(f"{BASE}/payments/{p['id']}/decision", headers=H, json={"action": "approve"}).status_code)
    print("managed submit blocked", requests.post(f"{BASE}/payments/{p['id']}/stellar/submit", headers=H, json={"confirm": True, "idempotency_key": "k-12345678"}).status_code)
    prep = requests.post(f"{BASE}/payments/{p['id']}/stellar/prepare", headers=H, json={"confirm": True, "idempotency_key": "k-12345678"}).json()
    print("prepared", prep["payment"]["status"], bool(prep["xdr"]))
    env = TransactionEnvelope.from_xdr(prep["xdr"], PASS); env.sign(bad)
    print("bad sig", requests.post(f"{BASE}/payments/{p['id']}/stellar/submit-signed", headers=H, json={"signed_xdr": env.to_xdr()}).status_code)
    env = TransactionEnvelope.from_xdr(prep["xdr"], PASS); env.sign(kp)
    r = requests.post(f"{BASE}/payments/{p['id']}/stellar/submit-signed", headers=H, json={"signed_xdr": env.to_xdr()}).json()
    print("submitted", r["payment"]["status"], r["payment"]["stellar"]["ledger"], r["payment"]["stellar"]["tx_hash"])
    print("again", requests.post(f"{BASE}/payments/{p['id']}/stellar/submit-signed", headers=H, json={"signed_xdr": env.to_xdr()}).json()["idempotent"])
    v = requests.post(f"{BASE}/payments/{p['id']}/stellar/verify", headers=H).json()
    print("verify", v["status"], v["stellar"]["verification"]["matches_request"])
    print("disconnect", requests.post(f"{BASE}/stellar/account/disconnect", headers=H).status_code)
