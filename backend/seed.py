import random
from datetime import datetime, timedelta, timezone

from core import db, new_id, now_iso, to_php, DEFAULT_DEPARTMENTS
import stellar_service as stellar

PEOPLE = [
    ("Andrea Villanueva", "finance_manager", "Finance", "Finance Manager", 150000),
    ("Paolo Mendoza", "employee", "Engineering", "Senior Software Engineer", 60000),
    ("Bea Cruz", "employee", "Marketing", "Marketing Lead", 80000),
    ("Miguel Santos", "employee", "Operations", "Operations Associate", 40000),
]

EXPENSES = [
    ("Engineering", "Paolo Mendoza", "AWS Asia Pacific", "Cloud & Hosting", 420, "USD"),
    ("Engineering", "Paolo Mendoza", "GitHub", "Software & SaaS", 84, "USD"),
    ("Engineering", "Paolo Mendoza", "PLDT Fibr", "Utilities & Internet", 3499, "PHP"),
    ("Marketing", "Bea Cruz", "Meta Ads", "Advertising", 25000, "PHP"),
    ("Marketing", "Bea Cruz", "Google Ads", "Advertising", 18500, "PHP"),
    ("Marketing", "Bea Cruz", "Canva Pro", "Software & SaaS", 1290, "PHP"),
    ("Marketing", "Bea Cruz", "Manila Marriott — Client Event", "Events", 46800, "PHP"),
    ("Operations", "Miguel Santos", "Grab Business", "Transportation", 2340, "PHP"),
    ("Operations", "Miguel Santos", "National Book Store", "Office Supplies", 1875, "PHP"),
    ("Operations", "Miguel Santos", "Lalamove", "Logistics", 960, "PHP"),
    ("Operations", "Miguel Santos", "Meralco", "Utilities & Internet", 8420, "PHP"),
    ("Executive", None, "Cebu Pacific", "Travel", 12650, "PHP"),
    ("Executive", None, "Seda BGC", "Travel", 9800, "PHP"),
    ("Finance", "Andrea Villanueva", "Xero", "Software & SaaS", 52, "USD"),
    ("Finance", "Andrea Villanueva", "SGV Advisory (demo)", "Professional Services", 35000, "PHP"),
]

STATUS_PLAN = ["paid", "paid", "approved", "approved", "paid", "pending_approval", "rejected", "draft"]


def _d(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).date().isoformat()


def _month(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m")


async def seed_demo(user: dict) -> str:
    rnd = random.Random(7)
    ws_id = new_id()
    await db.workspaces.insert_one({
        "id": ws_id, "name": "Isla Digital Solutions", "category": "Startup", "industry": "Technology Services",
        "location": "Metro Manila, Philippines", "business_email": "finance@isladigital.example",
        "admin_name": user["name"], "team_size": "11-50", "default_currency": "PHP", "is_demo": True,
        "approval_threshold": 50000, "departments": DEFAULT_DEPARTMENTS, "owner_user_id": user["user_id"],
        "created_at": now_iso(),
    })
    owner = {"id": new_id(), "workspace_id": ws_id, "user_id": user["user_id"], "name": user["name"],
             "email": user.get("email", ""), "role": "owner", "department": "Executive", "title": "Founder & CEO",
             "spending_limit": 250000, "status": "active", "is_synthetic": False, "created_at": now_iso()}
    members = [owner]
    for name, role, dept, title, limit in PEOPLE:
        members.append({"id": new_id(), "workspace_id": ws_id, "user_id": None, "name": name,
                        "email": f"{name.split()[0].lower()}@isladigital.example", "role": role, "department": dept,
                        "title": title, "spending_limit": limit, "status": "active", "is_synthetic": True,
                        "created_at": now_iso()})
    await db.members.insert_many([dict(m) for m in members])
    by_name = {m["name"]: m for m in members}

    budgets = [("Company Operating Budget", "business", None, None, 650000),
               ("Engineering", "department", "Engineering", None, 120000),
               ("Marketing & Growth", "department", "Marketing", None, 150000),
               ("Operations", "department", "Operations", None, 50000),
               ("Bea Cruz — Ad Spend Limit", "employee", "Marketing", by_name["Bea Cruz"]["id"], 60000)]
    docs = []
    for period_offset in (0, 31):
        for name, scope, dept, mid, amt in budgets:
            docs.append({"id": new_id(), "workspace_id": ws_id, "name": name, "scope": scope, "department": dept,
                         "member_id": mid, "amount": amt, "currency": "PHP", "period": _month(period_offset),
                         "alert_pct": 80, "assigned_member_ids": [mid] if mid else [m["id"] for m in members if m["department"] == dept],
                         "is_synthetic": True, "created_at": now_iso()})
    await db.budgets.insert_many(docs)

    expenses = []
    for i in range(36):
        dept, person, merchant, cat, amt, cur = EXPENSES[i % len(EXPENSES)]
        m = by_name[person] if person else owner
        amount = round(amt * rnd.uniform(0.8, 1.2), 2)
        days_ago = rnd.randint(1, 120)
        status = STATUS_PLAN[i % len(STATUS_PLAN)] if days_ago < 30 else ("paid" if i % 5 else "approved")
        hist = [{"status": "draft", "actor_name": m["name"], "actor_member_id": m["id"], "at": now_iso(), "note": "Synthetic demo record"}]
        if status != "draft":
            hist += [{"status": "submitted", "actor_name": m["name"], "actor_member_id": m["id"], "at": now_iso(), "note": ""},
                     {"status": "pending_approval", "actor_name": "AGOS Workflow", "actor_member_id": None, "at": now_iso(), "note": "Routed for approval"}]
        if status in ("approved", "paid", "rejected"):
            hist.append({"status": status if status != "paid" else "approved", "actor_name": "Andrea Villanueva",
                         "actor_member_id": by_name["Andrea Villanueva"]["id"], "at": now_iso(),
                         "note": "Missing official receipt" if status == "rejected" else ""})
        if status == "paid":
            hist.append({"status": "paid", "actor_name": "Andrea Villanueva", "actor_member_id": by_name["Andrea Villanueva"]["id"], "at": now_iso(), "note": "Recorded as paid (demo)"})
        expenses.append({"id": new_id(), "workspace_id": ws_id, "member_id": m["id"], "member_name": m["name"],
                         "department": dept, "merchant": merchant, "category": cat, "amount": amount, "currency": cur,
                         "amount_php": to_php(amount, cur), "date": _d(days_ago), "description": f"{cat} — {merchant}",
                         "notes": "", "status": status, "receipts": [], "card_id": None, "history": hist,
                         "reconciled": False, "is_synthetic": True, "created_by": m["id"], "created_at": now_iso()})
    await db.expenses.insert_many(expenses)

    cards, txns = [], []
    for name, nick, limit, last4 in [("Bea Cruz", "Marketing Ads Card", 60000, "4291"), ("Paolo Mendoza", "Cloud & SaaS Card", 40000, "7730"),
                                    ("Miguel Santos", "Ops Petty Card", 15000, "1184"), (owner["name"], "Founder Travel Card", 100000, "5502")]:
        m = by_name[name]
        card = {"id": new_id(), "workspace_id": ws_id, "member_id": m["id"], "member_name": m["name"], "nickname": nick,
                "last4": last4, "spending_limit": limit, "status": "frozen" if last4 == "1184" else "active",
                "budget_id": None, "expiry": "12/28", "is_simulated": True, "created_at": now_iso()}
        cards.append(card)
        for j in range(4):
            dept, person, merchant, cat, amt, cur = EXPENSES[(j * 3 + len(cards)) % len(EXPENSES)]
            amount = round(min(amt, limit / 6) * rnd.uniform(0.6, 1.0), 2)
            exp_id = new_id()
            declined = j == 3 and last4 == "4291"
            txns.append({"id": new_id(), "workspace_id": ws_id, "card_id": card["id"], "member_id": m["id"],
                         "merchant": merchant, "category": cat, "amount": amount, "currency": "PHP", "amount_php": amount,
                         "date": _d(rnd.randint(0, 20)), "status": "declined" if declined else "posted",
                         "decline_reason": "Exceeds remaining card limit" if declined else None,
                         "expense_id": None if declined else exp_id, "is_simulated": True, "created_at": now_iso()})
            if not declined:
                await db.expenses.insert_one({
                    "id": exp_id, "workspace_id": ws_id, "member_id": m["id"], "member_name": m["name"], "department": m["department"],
                    "merchant": merchant, "category": cat, "amount": amount, "currency": "PHP", "amount_php": amount,
                    "date": txns[-1]["date"], "description": f"Simulated card spend — {nick}", "notes": "",
                    "status": "approved" if j % 2 == 0 else "pending_approval", "receipts": [], "card_id": card["id"],
                    "card_txn_id": txns[-1]["id"], "history": [{"status": "pending_approval", "actor_name": "AGOS Workflow",
                    "actor_member_id": None, "at": now_iso(), "note": "Created from simulated card transaction"}],
                    "reconciled": False, "is_synthetic": True, "created_by": m["id"], "created_at": now_iso()})
    await db.cards.insert_many(cards)
    await db.card_transactions.insert_many(txns)

    pays = []
    for rec, bank, amt, purpose, status, requester in [
        ("Cruz Printing Services", "BDO", 18500, "Event collateral printing", "recorded_as_paid", "Bea Cruz"),
        ("Makati Co-Working Hub", "BPI", 45000, "Monthly office lease", "approved", "Miguel Santos"),
        ("Juan Dela Cruz (Contractor)", "UnionBank", 32000, "UI design sprint", "pending_approval", "Paolo Mendoza"),
        ("Lakbay Travel Agency", "Metrobank", 76000, "Team offsite booking", "pending_approval", owner["name"])]:
        m = by_name[requester]
        pays.append({"id": new_id(), "workspace_id": ws_id, "type": "domestic", "rail": "demo_bank_transfer",
                     "recipient_name": rec, "recipient_bank": bank, "recipient_account_last4": str(rnd.randint(1000, 9999)),
                     "destination_address": None, "asset_code": None, "amount": amt, "currency": "PHP", "amount_php": amt,
                     "purpose": purpose, "status": status, "requested_by": m["id"], "requested_by_name": m["name"],
                     "history": [{"status": "pending_approval", "actor_name": m["name"], "actor_member_id": m["id"], "at": now_iso(), "note": "Synthetic demo record"}],
                     "stellar": None, "reconciled": False, "is_synthetic": True, "created_at": now_iso()})
    dest, _ = stellar.new_keypair()
    pays.append({"id": new_id(), "workspace_id": ws_id, "type": "international", "rail": "stellar_testnet",
                 "recipient_name": "Singapore Design Contractor (demo)", "recipient_bank": None, "recipient_account_last4": None,
                 "destination_address": dest, "asset_code": "XLM", "asset_issuer": None, "amount": 25, "currency": "XLM",
                 "amount_php": 0, "purpose": "Testnet settlement demo — contractor invoice", "status": "pending_approval",
                 "requested_by": by_name["Paolo Mendoza"]["id"], "requested_by_name": "Paolo Mendoza",
                 "history": [{"status": "pending_approval", "actor_name": "Paolo Mendoza", "actor_member_id": by_name["Paolo Mendoza"]["id"], "at": now_iso(), "note": "Ready for a real Testnet submission once approved"}],
                 "stellar": None, "reconciled": False, "is_synthetic": False, "created_at": now_iso()})
    await db.payments.insert_many(pays)
    return ws_id
