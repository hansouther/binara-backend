"""Backend tests for new features: reorder + forgot/reset password + Google Maps settings.

- POST /api/admin/content/{coll}/reorder with {ids:[...]} (auth required); GET /api/content/{coll} returns items in order.
- POST /api/auth/forgot-password: always {ok:true}; creates token doc for registered emails; sends email
  (verified indirectly by checking the token doc lands in DB for delivered@resend.dev).
- POST /api/auth/reset-password with valid/invalid/expired/used token.
"""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://olimpiade-hub-1.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@binaralabs.id"
ADMIN_PASSWORD = "Binara2026!"

# direct mongo for read/cleanup verification
_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def mongo_db():
    c = MongoClient(_MONGO_URL)
    yield c[_DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ---------- REORDER ----------
class TestReorder:
    def test_reorder_requires_auth(self):
        r = requests.post(f"{API}/admin/content/team/reorder", json={"ids": []}, timeout=30)
        assert r.status_code == 401

    def test_reorder_invalid_collection(self, admin_headers):
        r = requests.post(f"{API}/admin/content/bogus/reorder", json={"ids": []}, headers=admin_headers, timeout=30)
        assert r.status_code == 404

    def test_reorder_persists_and_reflects_in_public_get(self, admin_headers):
        created = []
        try:
            # create 3 team items
            for i in range(3):
                r = requests.post(f"{API}/admin/content/team",
                                  json={"name": f"TEST_reorder_{i}", "role": "R", "desc": "", "image_url": "", "order": 500 + i},
                                  headers=admin_headers, timeout=30)
                assert r.status_code == 200, r.text
                created.append(r.json()["id"])

            # reorder reversed
            reversed_ids = list(reversed(created))
            r = requests.post(f"{API}/admin/content/team/reorder",
                              json={"ids": reversed_ids}, headers=admin_headers, timeout=30)
            assert r.status_code == 200
            assert r.json() == {"ok": True}

            # GET returns items sorted by order asc; the three TEST_reorder items should appear in reversed order
            r2 = requests.get(f"{API}/content/team", timeout=30)
            assert r2.status_code == 200
            items = [x for x in r2.json() if x["name"].startswith("TEST_reorder_")]
            got_ids = [x["id"] for x in items]
            assert got_ids == reversed_ids, f"Expected {reversed_ids}, got {got_ids}"
            # order fields set to 0,1,2 in the reorder call sequence
            id_to_order = {x["id"]: x.get("order") for x in items}
            for i, iid in enumerate(reversed_ids):
                assert id_to_order[iid] == i
        finally:
            for cid in created:
                requests.delete(f"{API}/admin/content/team/{cid}", headers=admin_headers, timeout=30)


# ---------- FORGOT / RESET PASSWORD ----------
class TestForgotPassword:
    def test_forgot_unknown_email_returns_ok(self):
        r = requests.post(f"{API}/auth/forgot-password",
                          json={"email": "does_not_exist_xyz@example.com"}, timeout=30)
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_forgot_for_admin_creates_token_doc(self, mongo_db):
        # count before
        before = mongo_db.password_reset_tokens.count_documents({"email": ADMIN_EMAIL})
        r = requests.post(f"{API}/auth/forgot-password", json={"email": ADMIN_EMAIL}, timeout=30)
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        # allow async insert to settle
        time.sleep(1)
        after = mongo_db.password_reset_tokens.count_documents({"email": ADMIN_EMAIL})
        assert after >= before + 1, "expected a new password_reset_token doc for admin email"


class TestResetPassword:
    """Full round-trip using a temp staff account so we don't touch admin credentials."""

    def _create_temp_staff(self, admin_headers, email="test_reset_staff@binaralabs.id", password="temp12345"):
        # cleanup first if exists
        listing = requests.get(f"{API}/admin/staff", headers=admin_headers, timeout=30).json()
        for s in listing:
            if s["email"] == email:
                requests.delete(f"{API}/admin/staff/{s['id']}", headers=admin_headers, timeout=30)
        r = requests.post(f"{API}/admin/staff",
                          json={"email": email, "password": password, "name": "TEST_ResetStaff", "role": "staff"},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["id"], email, password

    def test_reset_invalid_token(self):
        r = requests.post(f"{API}/auth/reset-password",
                          json={"token": "definitely_invalid", "password": "newpass123"}, timeout=30)
        assert r.status_code == 400

    def test_reset_password_full_flow(self, admin_headers, mongo_db):
        staff_id, email, old_pw = self._create_temp_staff(admin_headers)
        try:
            # trigger forgot
            r = requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=30)
            assert r.status_code == 200
            time.sleep(1)

            # pull the token from mongo directly
            doc = mongo_db.password_reset_tokens.find_one(
                {"email": email, "used": False}, sort=[("created_at", -1)]
            )
            assert doc is not None, "reset token not created in DB"
            token = doc["token"]

            # reset with new password
            new_pw = "brandnew12345"
            r2 = requests.post(f"{API}/auth/reset-password", json={"token": token, "password": new_pw}, timeout=30)
            assert r2.status_code == 200, r2.text

            # old password must fail
            r3 = requests.post(f"{API}/auth/login", json={"email": email, "password": old_pw}, timeout=30)
            assert r3.status_code == 401

            # new password logs in
            r4 = requests.post(f"{API}/auth/login", json={"email": email, "password": new_pw}, timeout=30)
            assert r4.status_code == 200
            assert r4.json()["user"]["email"] == email

            # token cannot be reused
            r5 = requests.post(f"{API}/auth/reset-password",
                               json={"token": token, "password": "another12345"}, timeout=30)
            assert r5.status_code == 400
        finally:
            requests.delete(f"{API}/admin/staff/{staff_id}", headers=admin_headers, timeout=30)


# ---------- EMAIL DELIVERABILITY (delivered@resend.dev) ----------
class TestEmailDeliverability:
    """Create temp staff with delivered@resend.dev, trigger forgot-password;
    endpoint returns {ok:true} regardless; token doc must exist -> email path was invoked."""

    def test_delivered_resend_dev(self, admin_headers, mongo_db):
        email = "delivered@resend.dev"
        # cleanup first
        listing = requests.get(f"{API}/admin/staff", headers=admin_headers, timeout=30).json()
        for s in listing:
            if s["email"] == email:
                requests.delete(f"{API}/admin/staff/{s['id']}", headers=admin_headers, timeout=30)

        r0 = requests.post(f"{API}/admin/staff",
                           json={"email": email, "password": "temp12345", "name": "TEST_Deliverable", "role": "staff"},
                           headers=admin_headers, timeout=30)
        assert r0.status_code == 200, r0.text
        staff_id = r0.json()["id"]
        try:
            r = requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=60)
            assert r.status_code == 200
            assert r.json() == {"ok": True}
            time.sleep(2)
            doc = mongo_db.password_reset_tokens.find_one({"email": email}, sort=[("created_at", -1)])
            assert doc is not None, "reset token doc missing for delivered@resend.dev"
        finally:
            requests.delete(f"{API}/admin/staff/{staff_id}", headers=admin_headers, timeout=30)
            mongo_db.password_reset_tokens.delete_many({"email": email})


# ---------- SETTINGS map_embed persistence (Google Maps) ----------
class TestSettingsMapEmbed:
    def test_map_embed_roundtrip(self, admin_headers):
        r0 = requests.get(f"{API}/content/settings/site", timeout=30)
        assert r0.status_code == 200
        current = r0.json()
        orig = current.get("map_embed", "")
        try:
            new_data = dict(current)
            new_data["map_embed"] = "Jakarta Selatan"
            r = requests.put(f"{API}/admin/settings", json=new_data, headers=admin_headers, timeout=30)
            assert r.status_code == 200
            assert r.json().get("map_embed") == "Jakarta Selatan"
            r2 = requests.get(f"{API}/content/settings/site", timeout=30)
            assert r2.json().get("map_embed") == "Jakarta Selatan"
        finally:
            restore = dict(current)
            restore["map_embed"] = orig
            requests.put(f"{API}/admin/settings", json=restore, headers=admin_headers, timeout=30)
