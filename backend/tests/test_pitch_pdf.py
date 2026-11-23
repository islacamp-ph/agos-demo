# Pitch Summary PDF endpoint tests. Run pdf_setup.py first (writes /tmp/pdf_state.json; does at most 1 Testnet tx)
import json, os, sys
import fitz
import pytest
import requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
from smoke_test import token_for

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
S = json.load(open("/tmp/pdf_state.json"))


@pytest.fixture(scope="module")
def HA():
    return {"Authorization": f"Bearer {token_for('agos.t5pdfA+clerk_test@example.com')[0]}", "X-Workspace-Id": S["wsA"]}


@pytest.fixture(scope="module")
def HB():
    return {"Authorization": f"Bearer {token_for('agos.t5pdfB+clerk_test@example.com')[0]}", "X-Workspace-Id": S["wsB"]}


@pytest.fixture(scope="module")
def pdf(HA):
    r = requests.get(f"{API}/payments/{S['confirmed']}/pitch-summary", headers=HA, params={"expense_id": S["expense"], "duration": 104})
    assert r.status_code == 200, r.text
    open("/tmp/pitch_full.pdf", "wb").write(r.content)
    return r


def text_of(content):
    doc = fitz.open(stream=content, filetype="pdf")
    return doc, "\n".join(p.get_text() for p in doc)


# Status / validation
def test_unconfirmed_409(HA):
    if not S["unconfirmed"]:
        pytest.skip("no unconfirmed payment")
    r = requests.get(f"{API}/payments/{S['unconfirmed']}/pitch-summary", headers=HA)
    assert r.status_code == 409 and "confirmed" in r.json()["detail"]


def test_pdf_basic(pdf):
    assert pdf.headers["content-type"] == "application/pdf"
    assert "agos-pitch-summary.pdf" in pdf.headers["content-disposition"]
    doc, _ = text_of(pdf.content)
    assert doc.page_count == 1


@pytest.mark.parametrize("d", [0, 7201, -5, "abc"])
def test_duration_out_of_range_422(HA, d):
    r = requests.get(f"{API}/payments/{S['confirmed']}/pitch-summary", headers=HA, params={"duration": d})
    assert r.status_code == 422


@pytest.mark.parametrize("d,label", [(1, "0:01"), (7200, "120:00")])
def test_duration_bounds(HA, d, label):
    r = requests.get(f"{API}/payments/{S['confirmed']}/pitch-summary", headers=HA, params={"duration": d})
    assert r.status_code == 200
    assert f"in {label}" in text_of(r.content)[1]


# Content
def test_pdf_content(pdf, HA):
    _, t = text_of(pdf.content)
    p = requests.get(f"{API}/payments/{S['confirmed']}", headers=HA).json()
    st = p["stellar"]
    assert "From expense to verified settlement in 1:44" in t
    assert "synthetic" in t.lower()
    for s in ["Expense submitted", "Payment requested", "Payment approved", "Signed & submitted", "Confirmed on ledger",
              "Verified via Horizon", "stellar.expert", "IMPORTANT", "not a bank"]:
        assert s in t, s
    flat = t.replace("\n", "")
    assert st["tx_hash"] in flat
    assert st["source"] in flat and st["destination"] in flat
    assert str(st["ledger"]) in t
    assert st["links"]["explorer"] in flat


def test_no_expense_no_duration(HA):
    r = requests.get(f"{API}/payments/{S['confirmed']}/pitch-summary", headers=HA)
    assert r.status_code == 200
    doc, t = text_of(r.content)
    assert doc.page_count == 1
    assert "Expense submitted" not in t and "Payment requested" in t
    assert "From expense to verified settlement\n" in t or "settlement in" not in t


def test_foreign_expense_ignored(HA, HB):
    eb = requests.get(f"{API}/expenses", headers=HB).json()[0]["id"]
    r = requests.get(f"{API}/payments/{S['confirmed']}/pitch-summary", headers=HA, params={"expense_id": eb})
    assert r.status_code == 200 and "Expense submitted" not in text_of(r.content)[1]


# Isolation / auth
def test_other_user_404(HB):
    r = requests.get(f"{API}/payments/{S['confirmed']}/pitch-summary", headers=HB)
    assert r.status_code == 404


def test_other_user_with_victim_ws_404(HB):
    r = requests.get(f"{API}/payments/{S['confirmed']}/pitch-summary", headers={**HB, "X-Workspace-Id": S["wsA"]})
    assert r.status_code == 404


def test_no_auth_401():
    r = requests.get(f"{API}/payments/{S['confirmed']}/pitch-summary", headers={"X-Workspace-Id": S["wsA"]})
    assert r.status_code == 401


def test_unknown_payment_404(HA):
    assert requests.get(f"{API}/payments/nope/pitch-summary", headers=HA).status_code == 404
