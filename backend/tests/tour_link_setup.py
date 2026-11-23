# Setup helper for Tour Share Link UI tests: prints JSON with tickets + workspace ids
import json, os, sys, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
from smoke_test import bapi, token_for

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
out = {}
# User A: fresh, no workspaces
tokA, uidA = token_for("agos.t4tourA+clerk_test@example.com")
out["A"] = {"uid": uidA, "ticket": bapi("/sign_in_tokens", {"user_id": uidA, "expires_in_seconds": 900})["token"],
            "ws": requests.get(f"{API}/me", headers={"Authorization": f"Bearer {tokA}"}).json()["workspaces"]}
# User B: demo + real workspace
tokB, uidB = token_for("agos.t4tourB+clerk_test@example.com")
H = {"Authorization": f"Bearer {tokB}"}
me = requests.get(f"{API}/me", headers=H).json()
demo = [w for w in me["workspaces"] if w["is_demo"]]
demo_id = demo[0]["id"] if demo else requests.post(f"{API}/workspaces/demo", headers=H).json()["id"]
real = [w for w in me["workspaces"] if not w["is_demo"]]
real_id = real[0]["id"] if real else requests.post(f"{API}/workspaces", headers=H, json={
    "name": "TEST_Real Co", "category": "Services", "industry": "Consulting", "location": "Manila",
    "business_email": "test_real@example.com", "admin_name": "Test Owner", "team_size": "1-10"}).json()["id"]
info = requests.get(f"{API}/workspace", headers={**H, "X-Workspace-Id": demo_id}).json()
persona = next(p["id"] for p in info["personas"] if p["id"] != info["real_member_id"])
out["B"] = {"uid": uidB, "demo": demo_id, "real": real_id, "persona": persona,
            "ticket": bapi("/sign_in_tokens", {"user_id": uidB, "expires_in_seconds": 900})["token"]}
print(json.dumps(out))
