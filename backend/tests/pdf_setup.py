# Setup for Pitch Summary PDF tests: user A (demo ws + 1 confirmed Stellar payment, idempotent), user B (own demo ws). Writes /tmp/pdf_state.json
import json, os, sys, time, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
from smoke_test import bapi, token_for

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"


def demo_ws(tok):
    H = {"Authorization": f"Bearer {tok}"}
    ws = [w for w in requests.get(f"{API}/me", headers=H).json()["workspaces"] if w["is_demo"]]
    return ws[0]["id"] if ws else requests.post(f"{API}/workspaces/demo", headers=H).json()["id"]


tokA, uidA = token_for("agos.t5pdfA+clerk_test@example.com")
tokB, uidB = token_for("agos.t5pdfB+clerk_test@example.com")
wsA, wsB = demo_ws(tokA), demo_ws(tokB)
HA = {"Authorization": f"Bearer {tokA}", "X-Workspace-Id": wsA}
pays = requests.get(f"{API}/payments", headers=HA, params={"type": "international"}).json()
confirmed = [p for p in pays if p["status"] == "confirmed"]
unconfirmed = [p for p in pays if p["status"] != "confirmed"]
exp = requests.get(f"{API}/expenses", headers=HA, params={"status": "approved"}).json()[0]
if not confirmed:
    requests.post(f"{API}/stellar/account", headers=HA)
    time.sleep(3)
    p = unconfirmed.pop(0)
    requests.post(f"{API}/payments/{p['id']}/decision", headers=HA, json={"action": "approve"})
    r = requests.post(f"{API}/payments/{p['id']}/stellar/submit", headers=HA, json={"confirm": True, "idempotency_key": "t5-pdf-key-0001"}).json()
    print("submit", r["payment"]["status"], file=sys.stderr)
    requests.post(f"{API}/payments/{p['id']}/stellar/verify", headers=HA)
    confirmed = [p]
if not unconfirmed:
    rec = requests.post(f"{API}/stellar/demo-recipient", headers=HA).json()
    unconfirmed = [requests.post(f"{API}/payments", headers=HA, json={
        "type": "international", "recipient_name": "TEST_Pending contractor", "destination_address": rec["public_key"],
        "asset_code": "XLM", "amount": "1", "purpose": "TEST_pending for 409"}).json()]
out = {"uidA": uidA, "uidB": uidB, "wsA": wsA, "wsB": wsB, "confirmed": confirmed[0]["id"],
       "unconfirmed": unconfirmed[0]["id"] if unconfirmed else None, "expense": exp["id"],
       "ticketA": bapi("/sign_in_tokens", {"user_id": uidA, "expires_in_seconds": 900})["token"]}
json.dump(out, open("/tmp/pdf_state.json", "w"))
print(json.dumps(out))
