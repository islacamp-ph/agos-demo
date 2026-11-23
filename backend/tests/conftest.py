import os
import sys
import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
from smoke_test import token_for  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = BASE_URL + "/api"

OWNER_EMAIL = "agos.owner+clerk_test@example.com"
USER_B_EMAIL = "agos.t1userb+clerk_test@example.com"
ADMIN_EMAIL = "agos.t1padmin+clerk_test@example.com"
SUPER_EMAIL = "agos.t1super+clerk_test@example.com"


def _session(email):
    tok, uid = token_for(email)
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s, uid


@pytest.fixture(scope="session")
def owner():
    s, uid = _session(OWNER_EMAIL)
    me = s.get(f"{API}/me").json()
    demo = [w for w in me["workspaces"] if w["is_demo"]]
    assert demo, "owner has no demo workspace"
    s.headers["X-Workspace-Id"] = demo[0]["id"]
    return s


@pytest.fixture(scope="session")
def personas(owner):
    ws = owner.get(f"{API}/workspace").json()
    out = {"owner": ws["real_member_id"]}
    for p in ws["personas"]:
        if p["id"] == ws["real_member_id"]:
            continue
        out.setdefault(p["role"], p["id"])
    return out


@pytest.fixture(scope="session")
def user_b():
    s, uid = _session(USER_B_EMAIL)
    me = s.get(f"{API}/me").json()
    if not me["workspaces"]:
        r = s.post(f"{API}/workspaces/demo")
        assert r.status_code == 200, r.text
        wid = r.json()["id"]
    else:
        wid = me["workspaces"][0]["id"]
    s.headers["X-Workspace-Id"] = wid
    return s


def act(session, member_id):
    h = dict(session.headers)
    h["X-Act-As"] = member_id
    return h
