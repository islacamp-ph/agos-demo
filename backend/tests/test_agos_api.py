import os
import time
import uuid
import pymongo
import pytest
import requests
from conftest import API, ADMIN_EMAIL, SUPER_EMAIL, _session, act

MONGO = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TODAY = time.strftime("%Y-%m-%d")
MONTH = TODAY[:7]


# ---------- Public / health / auth ----------
class TestPublicAuth:
    def test_health(self):
        r = requests.get(f"{API}/health")
        assert r.status_code == 200

    def test_waitlist_requires_consent(self):
        r = requests.post(f"{API}/waitlist", json={"name": "TEST_N", "business_name": "TEST_B", "email": "t1nc@example.com",
                                                   "category": "Retail", "challenge": "cash flow", "consent": False})
        assert r.status_code == 422

    def test_waitlist_persists(self):
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/waitlist", json={"name": "TEST_Wait", "business_name": "TEST_Biz", "email": email,
                                                   "category": "Retail", "challenge": "cash flow", "consent": True})
        assert r.status_code == 200 and r.json()["ok"]
        assert MONGO.waitlist.find_one({"email": email}) is not None
        MONGO.waitlist.delete_one({"email": email})

    @pytest.mark.parametrize("path", ["/me", "/expenses", "/dashboard", "/payments", "/admin/waitlist"])
    def test_protected_401(self, path):
        assert requests.get(f"{API}{path}").status_code == 401

    def test_admin_emails_not_in_public(self):
        sa = os.environ.get("SUPER_ADMIN_EMAIL", "")
        pa = os.environ.get("PLATFORM_ADMIN_EMAIL", "")
        for p in ["/health", "/roles"]:
            body = requests.get(f"{API}{p}").text
            for e in [x for x in (sa + "," + pa).split(",") if x.strip()]:
                assert e.strip().lower() not in body.lower()


# ---------- Platform admin ----------
class TestPlatformAdmin:
    def test_normal_user_forbidden(self, owner):
        h = {"Authorization": owner.headers["Authorization"]}
        assert requests.get(f"{API}/admin/waitlist", headers=h).status_code == 403
        assert requests.get(f"{API}/admin/overview", headers=h).status_code == 403

    def test_platform_admin(self):
        s, uid = _session(ADMIN_EMAIL)
        s.get(f"{API}/me")
        MONGO.users.update_one({"user_id": uid}, {"$set": {"platform_role": "platform_admin"}})
        assert s.get(f"{API}/admin/waitlist").status_code == 200
        assert s.get(f"{API}/admin/overview").status_code == 403

    def test_super_admin(self):
        s, uid = _session(SUPER_EMAIL)
        s.get(f"{API}/me")
        MONGO.users.update_one({"user_id": uid}, {"$set": {"platform_role": "super_admin"}})
        assert s.get(f"{API}/admin/waitlist").status_code == 200
        r = s.get(f"{API}/admin/overview")
        assert r.status_code == 200 and "workspaces" in r.json()


# ---------- Workspace isolation ----------
class TestIsolation:
    def test_b_cannot_read_a(self, owner, user_b):
        a_ws = owner.headers["X-Workspace-Id"]
        h = {"Authorization": user_b.headers["Authorization"], "X-Workspace-Id": a_ws}
        for p in ["/workspace", "/expenses", "/payments", "/dashboard", "/team"]:
            assert requests.get(f"{API}{p}", headers=h).status_code == 404, p
        exp = owner.get(f"{API}/expenses").json()[0]
        assert requests.get(f"{API}/expenses", headers={**dict(user_b.headers)}).status_code == 200
        ids_b = [e["id"] for e in user_b.get(f"{API}/expenses").json()]
        assert exp["id"] not in ids_b
        # B using own ws cannot decide A's expense
        r = user_b.post(f"{API}/expenses/{exp['id']}/decision", json={"action": "approve"})
        assert r.status_code == 404

    def test_create_empty_workspace(self, user_b):
        h = {"Authorization": user_b.headers["Authorization"]}
        r = requests.post(f"{API}/workspaces", headers=h, json={"name": "TEST_Empty Co", "category": "Services", "industry": "Tech",
                          "location": "Manila", "business_email": "test_b@example.com", "admin_name": "TEST Admin", "team_size": "1-10"})
        assert r.status_code == 200
        wid = r.json()["id"]
        me = requests.get(f"{API}/me", headers=h).json()
        assert any(w["id"] == wid and not w["is_demo"] for w in me["workspaces"])
        exps = requests.get(f"{API}/expenses", headers={**h, "X-Workspace-Id": wid}).json()
        assert exps == []


# ---------- Expenses & roles ----------
class TestExpenses:
    def test_full_flow(self, owner, personas):
        emp = personas["employee"]
        r = owner.post(f"{API}/expenses", headers=act(owner, emp), json={"merchant": "TEST_Grab", "category": "Travel",
                       "amount": 1234.5, "currency": "PHP", "date": TODAY, "submit": False})
        assert r.status_code == 200, r.text
        e = r.json()
        assert e["status"] == "draft" and e["member_id"] == emp
        r = owner.post(f"{API}/expenses/{e['id']}/submit", headers=act(owner, emp))
        assert r.json()["status"] == "pending_approval"
        # employee cannot approve
        r = owner.post(f"{API}/expenses/{e['id']}/decision", headers=act(owner, emp), json={"action": "approve"})
        assert r.status_code == 403
        # employee sees only own
        mine = owner.get(f"{API}/expenses", headers=act(owner, emp)).json()
        assert all(x["member_id"] == emp for x in mine)
        # reject needs note
        r = owner.post(f"{API}/expenses/{e['id']}/decision", json={"action": "reject", "note": ""})
        assert r.status_code == 422
        # FM approves
        fm = personas["finance_manager"]
        r = owner.post(f"{API}/expenses/{e['id']}/decision", headers=act(owner, fm), json={"action": "approve"})
        assert r.status_code == 200 and r.json()["status"] == "approved"
        r = owner.post(f"{API}/expenses/{e['id']}/mark-paid")
        assert r.status_code == 200 and r.json()["status"] == "paid"
        hist = r.json()["history"]
        assert [h["status"] for h in hist][:3] == ["draft", "submitted", "pending_approval"]
        assert any("(demo persona)" in h["actor_name"] for h in hist)

    def test_fm_threshold_and_self(self, owner, personas):
        fm = personas["finance_manager"]
        emp = personas["employee"]
        big = owner.post(f"{API}/expenses", headers=act(owner, emp), json={"merchant": "TEST_Big", "category": "Equipment",
                         "amount": 60000, "date": TODAY, "submit": True}).json()
        r = owner.post(f"{API}/expenses/{big['id']}/decision", headers=act(owner, fm), json={"action": "approve"})
        assert r.status_code == 403
        own = owner.post(f"{API}/expenses", headers=act(owner, fm), json={"merchant": "TEST_Own", "category": "Meals",
                         "amount": 500, "date": TODAY, "submit": True}).json()
        r = owner.post(f"{API}/expenses/{own['id']}/decision", headers=act(owner, fm), json={"action": "approve"})
        assert r.status_code == 403
        assert owner.post(f"{API}/expenses/{big['id']}/decision", json={"action": "approve"}).status_code == 200
        assert owner.post(f"{API}/expenses/{own['id']}/decision", json={"action": "reject", "note": "TEST reject"}).json()["status"] == "rejected"

    def test_receipts(self, owner):
        e = owner.post(f"{API}/expenses", json={"merchant": "TEST_Receipt", "category": "Meals", "amount": 100, "date": TODAY}).json()
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
        r = owner.post(f"{API}/expenses/{e['id']}/receipts", files={"file": ("r.png", png, "image/png")})
        assert r.status_code == 200, r.text
        fid = r.json()["id"]
        d = owner.get(f"{API}/files/{fid}")
        assert d.status_code == 200 and d.content == png
        r = owner.post(f"{API}/expenses/{e['id']}/receipts", files={"file": ("x.txt", b"hello", "text/plain")})
        assert r.status_code == 415

    def test_filters_export(self, owner):
        r = owner.get(f"{API}/expenses", params={"q": "TEST_Grab"})
        assert r.status_code == 200 and all("TEST_Grab" in x["merchant"] for x in r.json())
        r = owner.get(f"{API}/expenses", params={"status": "paid"})
        assert all(x["status"] == "paid" for x in r.json())
        r = owner.get(f"{API}/expenses/export")
        assert r.status_code == 200 and "text/csv" in r.headers["content-type"] and r.text.startswith("id,date,merchant")


# ---------- Budgets ----------
class TestBudgets:
    def test_budget_crud_and_utilization(self, owner, personas):
        emp = personas["employee"]
        assert owner.post(f"{API}/budgets", headers=act(owner, emp), json={"name": "TEST_x", "scope": "business",
                          "amount": 1000, "period": MONTH}).status_code == 403
        dept = "Finance"
        b = owner.post(f"{API}/budgets", json={"name": "TEST_Budget", "scope": "department", "department": dept,
                       "amount": 999999, "period": MONTH})
        assert b.status_code == 200, b.text
        b = b.json()
        used0 = b["used"]
        e = owner.post(f"{API}/expenses", json={"merchant": "TEST_BudgetExp", "category": "Software", "amount": 777,
                       "date": TODAY, "department": dept, "submit": True}).json()
        after_pending = [x for x in owner.get(f"{API}/budgets").json() if x["id"] == b["id"]][0]
        assert after_pending["used"] == used0
        owner.post(f"{API}/expenses/{e['id']}/decision", json={"action": "approve"})
        after = [x for x in owner.get(f"{API}/budgets").json() if x["id"] == b["id"]][0]
        assert round(after["used"] - used0, 2) == 777
        r = owner.put(f"{API}/budgets/{b['id']}", json={"name": "TEST_Budget2", "scope": "department", "department": dept,
                      "amount": 500000, "period": MONTH})
        assert r.status_code == 200 and r.json()["name"] == "TEST_Budget2"
        assert owner.delete(f"{API}/budgets/{b['id']}").status_code == 200
        assert owner.delete(f"{API}/budgets/{b['id']}").status_code == 404


# ---------- Cards ----------
class TestCards:
    def test_freeze_simulate(self, owner, personas):
        c = owner.post(f"{API}/cards", json={"member_id": personas["employee"], "nickname": "TEST_Card", "spending_limit": 1000})
        assert c.status_code == 200, c.text
        cid = c.json()["id"]
        assert owner.post(f"{API}/cards/{cid}/status", json={"action": "freeze"}).json()["status"] == "frozen"
        t = owner.post(f"{API}/cards/{cid}/simulate", json={"merchant": "TEST_M", "category": "Meals", "amount": 10}).json()
        assert t["status"] == "declined"
        assert owner.post(f"{API}/cards/{cid}/status", json={"action": "unfreeze"}).json()["status"] == "active"
        t = owner.post(f"{API}/cards/{cid}/simulate", json={"merchant": "TEST_M", "category": "Meals", "amount": 5000}).json()
        assert t["status"] == "declined"
        t = owner.post(f"{API}/cards/{cid}/simulate", json={"merchant": "TEST_M", "category": "Meals", "amount": 200}).json()
        assert t["status"] == "posted" and t["expense_id"]
        e = [x for x in owner.get(f"{API}/expenses").json() if x["id"] == t["expense_id"]][0]
        assert e["status"] == "pending_approval"
        assert owner.get(f"{API}/cards/{cid}").status_code in (200, 405)


# ---------- Payments ----------
class TestPayments:
    def test_domestic(self, owner):
        p = owner.post(f"{API}/payments", json={"type": "domestic", "recipient_name": "TEST_Vendor", "recipient_bank": "BDO",
                       "recipient_account_last4": "1234", "amount": "1500", "purpose": "TEST supplies"})
        assert p.status_code == 200, p.text
        pid = p.json()["id"]
        assert owner.post(f"{API}/payments/{pid}/decision", json={"action": "approve"}).json()["status"] == "approved"
        r = owner.post(f"{API}/payments/{pid}/record-paid").json()
        assert r["status"] == "recorded_as_paid" and "no bank transfer" in r["history"][-1]["note"].lower()
        assert owner.post(f"{API}/payments/{pid}/stellar/submit", json={"confirm": True, "idempotency_key": "abcdefgh12"}).status_code == 409

    def test_international_validation(self, owner):
        base = {"type": "international", "recipient_name": "TEST_Intl", "amount": "1", "purpose": "TEST validation"}
        assert owner.post(f"{API}/payments", json={**base, "destination_address": "GBADADDRESS"}).status_code == 422
        good = owner.post(f"{API}/stellar/demo-recipient").json()["public_key"]
        assert owner.post(f"{API}/payments", json={**base, "destination_address": good, "amount": "-1"}).status_code == 422
        assert owner.post(f"{API}/payments", json={**base, "destination_address": good, "amount": "5000"}).status_code == 422
        assert owner.post(f"{API}/payments", json={**base, "destination_address": good, "amount": "abc"}).status_code == 422

    def test_stellar_e2e(self, owner):
        acct = owner.get(f"{API}/stellar/account")
        assert acct.status_code == 200
        assert "secret" not in acct.text.lower() and "encrypted" not in acct.text.lower()
        assert acct.json()["account"]["balances"]
        assert owner.post(f"{API}/stellar/account").status_code == 409
        dest = owner.post(f"{API}/stellar/demo-recipient").json()["public_key"]
        p = owner.post(f"{API}/payments", json={"type": "international", "recipient_name": "TEST_Stellar", "destination_address": dest,
                       "amount": "1.5", "purpose": "TEST stellar payment"}).json()
        pid = p["id"]
        # not approved -> cannot submit
        r = owner.post(f"{API}/payments/{pid}/stellar/submit", json={"confirm": True, "idempotency_key": "k" * 10})
        assert r.status_code in (409, 200) and (r.status_code == 409 or r.json()["payment"]["status"] == "pending_approval")
        assert owner.post(f"{API}/payments/{pid}/decision", json={"action": "approve"}).status_code == 200
        assert owner.post(f"{API}/payments/{pid}/stellar/submit", json={"confirm": False, "idempotency_key": "k" * 10}).status_code == 422
        key = uuid.uuid4().hex
        r = owner.post(f"{API}/payments/{pid}/stellar/submit", json={"confirm": True, "idempotency_key": key}, timeout=90)
        assert r.status_code == 200, r.text
        assert "secret" not in r.text.lower()
        st = r.json()["payment"]
        assert st["status"] == "confirmed", st
        h = st["stellar"]["tx_hash"]
        assert len(h) == 64 and st["stellar"]["ledger"]
        assert "stellar.expert" in st["stellar"]["links"]["explorer"] and "testnet" in st["stellar"]["links"]["explorer"]
        r2 = owner.post(f"{API}/payments/{pid}/stellar/submit", json={"confirm": True, "idempotency_key": key}).json()
        assert r2["idempotent"] is True and r2["payment"]["stellar"]["tx_hash"] == h
        v = owner.post(f"{API}/payments/{pid}/stellar/verify").json()
        assert v["stellar"]["verification"]["matches_request"] is True
        # persisted
        again = owner.get(f"{API}/payments/{pid}").json()
        assert again["stellar"]["tx_hash"] == h
        rec = owner.get(f"{API}/reconciliation").json()
        row = [x for x in rec["rows"] if x["id"] == pid][0]
        assert row["reconciliation_status"] == "verified_on_chain" and row["evidence"] == h
        assert owner.post(f"{API}/reconciliation/{pid}", json={"kind": "payment", "reconciled": True}).status_code == 200
        row = [x for x in owner.get(f"{API}/reconciliation").json()["rows"] if x["id"] == pid][0]
        assert row["reconciliation_status"] == "reconciled"

    def test_no_secret_anywhere(self, owner):
        for p in ["/payments", "/stellar/account", "/stellar/transactions", "/reconciliation", "/workspace", "/audit"]:
            t = owner.get(f"{API}{p}").text.lower()
            assert "encrypted_secret" not in t and '"secret' not in t, p


# ---------- Reports / team / settings ----------
class TestReportsTeam:
    @pytest.mark.parametrize("kind", ["monthly", "departments", "employees", "budget_vs_actual", "pending", "payments", "stellar"])
    def test_exports(self, owner, kind):
        r = owner.get(f"{API}/reports/export/{kind}", params={"date_from": "2020-01-01", "date_to": "2030-12-31"})
        assert r.status_code == 200 and "text/csv" in r.headers["content-type"]

    def test_reports_and_recon_export(self, owner):
        assert owner.get(f"{API}/reports").status_code == 200
        assert owner.get(f"{API}/reports/export/bogus").status_code == 404
        r = owner.get(f"{API}/reconciliation/export")
        assert r.status_code == 200 and r.text.startswith("reference")

    def test_team(self, user_b):
        me = user_b.get(f"{API}/workspace").json()
        r = user_b.post(f"{API}/team", json={"name": "TEST_Member", "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
                        "role": "employee", "department": "Finance"})
        assert r.status_code == 200 and r.json()["status"] == "invited"
        mid = r.json()["id"]
        assert user_b.patch(f"{API}/team/{mid}", json={"role": "finance_manager"}).status_code == 200
        team = user_b.get(f"{API}/team").json()
        assert [m for m in team if m["id"] == mid][0]["role"] == "finance_manager"
        r = user_b.patch(f"{API}/team/{me['real_member_id']}", json={"role": "employee"})
        assert r.status_code == 409
        r = user_b.patch(f"{API}/team/{me['real_member_id']}", json={"status": "removed"})
        assert r.status_code == 409
        user_b.patch(f"{API}/team/{mid}", json={"status": "removed"})

    def test_settings_audit(self, user_b):
        r = user_b.patch(f"{API}/workspace", json={"approval_threshold": 60000})
        assert r.status_code == 200
        assert user_b.get(f"{API}/workspace").json()["workspace"]["approval_threshold"] == 60000
        user_b.patch(f"{API}/workspace", json={"approval_threshold": 50000})
        a = user_b.get(f"{API}/audit")
        assert a.status_code == 200 and any(x["action"] == "workspace.updated" for x in a.json())

    def test_employee_no_audit(self, owner, personas):
        assert owner.get(f"{API}/audit", headers=act(owner, personas["employee"])).status_code == 403
