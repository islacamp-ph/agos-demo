# Regression: simulated card issuance (last4 via secrets.randbelow) - iteration 3
import re
import pytest
from conftest import API, _session, act

EMAIL = "agos.t3cards+clerk_test@example.com"
ST = {}


@pytest.fixture(scope="module")
def s():
    sess, _ = _session(EMAIL)
    sess.get(f"{API}/me")
    r = sess.post(f"{API}/workspaces/demo")
    assert r.status_code == 200, r.text
    sess.headers["X-Workspace-Id"] = r.json()["id"]
    ST["ws_id"] = r.json()["id"]
    ws = sess.get(f"{API}/workspace").json()
    ST["personas"] = {p["role"]: p["id"] for p in ws["personas"] if p["id"] != ws["real_member_id"]}
    ST["member"] = ws["real_member_id"]
    return sess


class TestCards:
    def test_issue_cards_last4(self, s):
        last4s = []
        for i in range(3):
            r = s.post(f"{API}/cards", json={"member_id": ST["member"], "nickname": f"TEST_card {i}", "spending_limit": 500})
            assert r.status_code == 200, r.text
            c = r.json()
            assert re.fullmatch(r"\d{4}", c["last4"]), c["last4"]
            assert c["is_simulated"] is True and c["status"] == "active"
            assert c["nickname"] == f"TEST_card {i}"
            last4s.append(c["last4"])
        cards = s.get(f"{API}/cards").json()
        items = cards if isinstance(cards, list) else cards.get("items", cards.get("cards", []))
        got = {c["last4"] for c in items if c["nickname"].startswith("TEST_card")}
        assert set(last4s) <= got
        print("last4s", last4s)

    def test_issue_card_validation(self, s):
        assert s.post(f"{API}/cards", json={"member_id": "nope", "nickname": "TEST_x", "spending_limit": 5}).status_code == 404
        assert s.post(f"{API}/cards", json={"member_id": ST["member"], "nickname": "TEST_x", "spending_limit": 0}).status_code == 422

    def test_employee_cannot_issue(self, s):
        r = s.post(f"{API}/cards", json={"member_id": ST["member"], "nickname": "TEST_emp", "spending_limit": 5},
                   headers=act(s, ST["personas"]["employee"]))
        assert r.status_code == 403
