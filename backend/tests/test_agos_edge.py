import time
import uuid
from conftest import API, act

TODAY = time.strftime("%Y-%m-%d")


# ---------- Edge cases: role/persona hardening ----------
class TestEdge:
    def test_act_as_ignored_in_non_demo(self, user_b):
        h = {"Authorization": user_b.headers["Authorization"]}
        me = user_b.get(f"{API}/me").json()
        real = [w for w in me["workspaces"] if not w["is_demo"]][0]
        r = user_b.post(f"{API}/team", headers={**h, "X-Workspace-Id": real["id"]},
                        json={"name": "TEST_Persona", "email": f"test_{uuid.uuid4().hex[:6]}@example.com", "role": "employee", "department": "Finance"})
        mid = r.json()["id"]
        w = user_b.get(f"{API}/workspace", headers={**h, "X-Workspace-Id": real["id"], "X-Act-As": mid}).json()
        assert w["role"] == "owner" and w["acting_as_persona"] is False

    def test_act_as_foreign_member_ignored(self, owner, user_b, personas):
        w = user_b.get(f"{API}/workspace", headers={**dict(user_b.headers), "X-Act-As": personas["employee"]}).json()
        assert w["role"] == "owner"

    def test_fm_cannot_create_budget(self, owner, personas):
        r = owner.post(f"{API}/budgets", headers=act(owner, personas["finance_manager"]),
                       json={"name": "TEST_fm", "scope": "business", "amount": 100, "period": TODAY[:7]})
        assert r.status_code == 403

    def test_fm_threshold_applies_to_international(self, owner, personas):
        """International XLM payments have amount_php=0, so FM threshold never applies (reported, not fixed)."""
        dest = owner.post(f"{API}/stellar/demo-recipient").json()["public_key"]
        emp = personas["employee"]
        p = owner.post(f"{API}/payments", headers=act(owner, emp), json={"type": "international", "recipient_name": "TEST_Thresh",
                       "destination_address": dest, "amount": "999", "purpose": "TEST threshold"}).json()
        r = owner.post(f"{API}/payments/{p['id']}/decision", headers=act(owner, personas["finance_manager"]),
                       json={"action": "reject", "note": "TEST cleanup"})
        print("FM decision on 999 XLM:", r.status_code, "amount_php:", p.get("amount_php"))
        assert p["amount_php"] == 0

    def test_card_budget_cross_workspace(self, owner, user_b, personas):
        fb = user_b.post(f"{API}/budgets", json={"name": "TEST_Foreign", "scope": "business", "amount": 100, "period": TODAY[:7]})
        foreign_budget = fb.json()["id"]
        r = owner.post(f"{API}/cards", json={"member_id": personas["employee"], "nickname": "TEST_XBudget",
                       "spending_limit": 100, "budget_id": foreign_budget})
        print("card with foreign budget_id:", r.status_code)
        assert r.status_code in (404, 422), "foreign budget_id accepted"

    def test_remove_invited_owner(self, user_b):
        me = user_b.get(f"{API}/workspace").json()
        r = user_b.post(f"{API}/team", json={"name": "TEST_InvOwner", "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
                        "role": "owner", "department": "Finance"})
        mid = r.json()["id"]
        r = user_b.patch(f"{API}/team/{mid}", json={"status": "removed"})
        print("remove invited owner:", r.status_code, me["role"])
        assert r.status_code == 200, "cannot remove an invited (not active) owner while 1 active owner exists"
