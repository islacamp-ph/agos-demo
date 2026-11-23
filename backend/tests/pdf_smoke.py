import requests
from smoke_test import token_for, BASE

if __name__ == "__main__":
    tok, _ = token_for("agos.pdf+clerk_test@example.com")
    H = {"Authorization": f"Bearer {tok}"}
    H["X-Workspace-Id"] = requests.post(f"{BASE}/workspaces/demo", headers=H).json()["id"]
    exp = requests.get(f"{BASE}/expenses", headers=H, params={"status": "approved"}).json()[0]
    requests.post(f"{BASE}/stellar/account", headers=H)
    p = requests.get(f"{BASE}/payments", headers=H, params={"type": "international"}).json()[0]
    print("early", requests.get(f"{BASE}/payments/{p['id']}/pitch-summary", headers=H).status_code)
    requests.post(f"{BASE}/payments/{p['id']}/decision", headers=H, json={"action": "approve"})
    r = requests.post(f"{BASE}/payments/{p['id']}/stellar/submit", headers=H, json={"confirm": True, "idempotency_key": "pdf-key-1234"}).json()
    print("status", r["payment"]["status"])
    requests.post(f"{BASE}/payments/{p['id']}/stellar/verify", headers=H)
    res = requests.get(f"{BASE}/payments/{p['id']}/pitch-summary", headers=H, params={"expense_id": exp["id"], "duration": 104})
    print("pdf", res.status_code, res.headers.get("content-type"), len(res.content))
    open("/tmp/pitch.pdf", "wb").write(res.content)
