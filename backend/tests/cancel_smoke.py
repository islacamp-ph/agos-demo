import requests
from stellar_sdk import Keypair, TransactionEnvelope, Network
from smoke_test import token_for, BASE

PASS = Network.TESTNET_NETWORK_PASSPHRASE

if __name__ == "__main__":
    tok, _ = token_for("agos.cancel+clerk_test@example.com")
    H = {"Authorization": f"Bearer {tok}"}
    H["X-Workspace-Id"] = requests.post(f"{BASE}/workspaces/demo", headers=H).json()["id"]
    kp = Keypair.random()
    requests.get("https://friendbot.stellar.org", params={"addr": kp.public_key}, timeout=30)
    ch = requests.post(f"{BASE}/stellar/wallet/challenge", headers=H, json={"public_key": kp.public_key}).json()
    env = TransactionEnvelope.from_xdr(ch["xdr"], PASS); env.sign(kp)
    requests.post(f"{BASE}/stellar/wallet/connect", headers=H, json={"challenge_id": ch["challenge_id"], "signed_xdr": env.to_xdr()})
    p = requests.get(f"{BASE}/payments", headers=H, params={"type": "international"}).json()[0]
    requests.post(f"{BASE}/payments/{p['id']}/decision", headers=H, json={"action": "approve"})
    print("prepare", requests.post(f"{BASE}/payments/{p['id']}/stellar/prepare", headers=H, json={"confirm": True, "idempotency_key": "k-abcdefgh"}).json()["payment"]["status"])
    print("disconnect blocked", requests.post(f"{BASE}/stellar/account/disconnect", headers=H).status_code)
    print("cancel", requests.post(f"{BASE}/payments/{p['id']}/stellar/cancel-signature", headers=H).json()["status"])
    print("cancel again", requests.post(f"{BASE}/payments/{p['id']}/stellar/cancel-signature", headers=H).status_code)
    print("disconnect", requests.post(f"{BASE}/stellar/account/disconnect", headers=H).status_code)
