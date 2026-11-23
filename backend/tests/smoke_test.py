import os, json, time, urllib.request, urllib.parse
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
SK = os.environ["CLERK_SECRET_KEY"]
BASE = "http://localhost:8001/api"


def bapi(path, body=None, method="POST"):
    req = urllib.request.Request("https://api.clerk.com/v1" + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": "Bearer " + SK, "Content-Type": "application/json", "User-Agent": "agos-test"})
    return json.load(urllib.request.urlopen(req))


def token_for(email):
    users = bapi("/users?email_address=" + urllib.parse.quote(email), None, "GET")
    user = users[0] if users else bapi("/users", {"email_address": [email], "password": "Agos-Test-pass-12345!", "skip_password_checks": True, "first_name": "Test", "last_name": "Owner"})
    s = bapi("/sessions", {"user_id": user["id"]})
    return bapi(f"/sessions/{s['id']}/tokens", {"expires_in_seconds": 1800})["jwt"], user["id"]


if __name__ == "__main__":
    tok, uid = token_for("agos.owner+clerk_test@example.com")
    H = {"Authorization": f"Bearer {tok}"}
    me = requests.get(f"{BASE}/me", headers=H).json()
    print("me", me["platform_role"], len(me["workspaces"]))
    ws = me["workspaces"][0]["id"] if me["workspaces"] else requests.post(f"{BASE}/workspaces/demo", headers=H).json()["id"]
    H["X-Workspace-Id"] = ws
    print("dash", requests.get(f"{BASE}/dashboard", headers=H).json()["kpis"])
    print("acct", requests.post(f"{BASE}/stellar/account", headers=H).json())
    time.sleep(3)
    print("acct info", requests.get(f"{BASE}/stellar/account", headers=H).json()["account"]["balances"])
    pays = requests.get(f"{BASE}/payments", headers=H, params={"type": "international"}).json()
    p = pays[0]
    print("decide", requests.post(f"{BASE}/payments/{p['id']}/decision", headers=H, json={"action": "approve"}).status_code)
    r = requests.post(f"{BASE}/payments/{p['id']}/stellar/submit", headers=H, json={"confirm": True, "idempotency_key": "test-key-123456"}).json()
    print("submit", r["payment"]["status"], r["payment"]["stellar"])
    r2 = requests.post(f"{BASE}/payments/{p['id']}/stellar/submit", headers=H, json={"confirm": True, "idempotency_key": "test-key-123456"}).json()
    print("resubmit idempotent", r2["idempotent"], r2["payment"]["stellar"]["tx_hash"] == r["payment"]["stellar"]["tx_hash"])
    v = requests.post(f"{BASE}/payments/{p['id']}/stellar/verify", headers=H).json()
    print("verify", v["status"], v["stellar"]["verification"].get("matches_request"))
    print("recon", requests.get(f"{BASE}/reconciliation", headers=H).json()["summary"])
    print("reports", requests.get(f"{BASE}/reports", headers=H).json()["totals"])
    print("noauth", requests.get(f"{BASE}/expenses", headers={"X-Workspace-Id": ws}).status_code)
