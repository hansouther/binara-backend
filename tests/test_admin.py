"""Backend tests for Binara Labs admin CMS + auth + upload."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://olimpiade-hub-1.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@binaralabs.id"
ADMIN_PASSWORD = "Binara2026!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and data["user"]["role"] == "admin"
    return data["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---- AUTH ----
class TestAuth:
    def test_login_success(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == ADMIN_EMAIL
        assert d["user"]["role"] == "admin"
        assert isinstance(d["token"], str) and len(d["token"]) > 20

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}, timeout=30)
        assert r.status_code == 401

    def test_me_with_token(self, admin_headers):
        r = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_me_without_token(self):
        r = requests.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 401


# ---- AUTH GUARDS ----
class TestGuards:
    @pytest.mark.parametrize("method,path", [
        ("POST", "/admin/content/team"),
        ("PUT", "/admin/settings"),
        ("POST", "/admin/upload"),
        ("GET", "/admin/staff"),
        ("GET", "/contact"),
    ])
    def test_requires_auth(self, method, path):
        r = requests.request(method, f"{API}{path}", json={} if method != "GET" else None, timeout=30)
        assert r.status_code == 401, f"{method} {path} -> {r.status_code}"


# ---- CONTENT CRUD ----
class TestContentCRUD:
    def test_team_crud(self, admin_headers):
        payload = {"name": "TEST_John Doe", "role": "Tester", "desc": "Test", "image_url": "", "order": 99}
        r = requests.post(f"{API}/admin/content/team", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        item = r.json()
        item_id = item["id"]
        assert item["name"] == "TEST_John Doe"

        # verify via public GET
        r2 = requests.get(f"{API}/content/team", timeout=30)
        assert r2.status_code == 200
        assert any(x["id"] == item_id for x in r2.json())

        # update
        r3 = requests.put(f"{API}/admin/content/team/{item_id}",
                          json={"name": "TEST_Updated", "role": "Tester", "desc": "Updated", "image_url": "", "order": 99},
                          headers=admin_headers, timeout=30)
        assert r3.status_code == 200
        assert r3.json()["name"] == "TEST_Updated"

        # delete
        r4 = requests.delete(f"{API}/admin/content/team/{item_id}", headers=admin_headers, timeout=30)
        assert r4.status_code == 200

        r5 = requests.get(f"{API}/content/team", timeout=30)
        assert not any(x["id"] == item_id for x in r5.json())

    def test_invalid_collection(self, admin_headers):
        r = requests.post(f"{API}/admin/content/bogus", json={"x": 1}, headers=admin_headers, timeout=30)
        assert r.status_code == 404


# ---- SETTINGS ----
class TestSettings:
    def test_update_settings(self, admin_headers):
        # get current
        r0 = requests.get(f"{API}/content/settings/site", timeout=30)
        assert r0.status_code == 200
        current = r0.json()
        orig_title = current.get("hero_title")
        orig_subtitle = current.get("hero_subtitle")

        new_data = dict(current)
        new_data["hero_title"] = "TEST_HERO_TITLE"
        new_data["hero_subtitle"] = "TEST_SUB"
        r = requests.put(f"{API}/admin/settings", json=new_data, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["hero_title"] == "TEST_HERO_TITLE"

        r2 = requests.get(f"{API}/content/settings/site", timeout=30)
        assert r2.json()["hero_title"] == "TEST_HERO_TITLE"
        assert r2.json()["hero_subtitle"] == "TEST_SUB"

        # restore
        restore = dict(current)
        restore["hero_title"] = orig_title
        restore["hero_subtitle"] = orig_subtitle
        rr = requests.put(f"{API}/admin/settings", json=restore, headers=admin_headers, timeout=30)
        assert rr.status_code == 200


# ---- UPLOAD ----
class TestUpload:
    def test_upload_and_serve(self, admin_headers):
        # 1x1 PNG
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
        )
        files = {"file": ("test.png", io.BytesIO(png), "image/png")}
        r = requests.post(f"{API}/admin/upload", headers=admin_headers, files=files, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["url"].startswith("/api/files/")

        # public serve
        r2 = requests.get(f"{BASE_URL}{d['url']}", timeout=60)
        assert r2.status_code == 200
        assert "image" in r2.headers.get("Content-Type", "")


# ---- STAFF ----
class TestStaff:
    def test_staff_crud(self, admin_headers):
        # list
        r = requests.get(f"{API}/admin/staff", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        # create
        payload = {"email": "test_staff_new@binaralabs.id", "password": "abc12345", "name": "TEST_Staff", "role": "staff"}
        r2 = requests.post(f"{API}/admin/staff", json=payload, headers=admin_headers, timeout=30)
        if r2.status_code == 400:
            # already exists; delete first
            listing = requests.get(f"{API}/admin/staff", headers=admin_headers, timeout=30).json()
            for s in listing:
                if s["email"] == payload["email"]:
                    requests.delete(f"{API}/admin/staff/{s['id']}", headers=admin_headers, timeout=30)
            r2 = requests.post(f"{API}/admin/staff", json=payload, headers=admin_headers, timeout=30)
        assert r2.status_code == 200, r2.text
        new_id = r2.json()["id"]

        # verify in listing
        listing = requests.get(f"{API}/admin/staff", headers=admin_headers, timeout=30).json()
        assert any(s["id"] == new_id for s in listing)

        # delete
        r3 = requests.delete(f"{API}/admin/staff/{new_id}", headers=admin_headers, timeout=30)
        assert r3.status_code == 200

    def test_cannot_delete_last_admin(self, admin_headers):
        listing = requests.get(f"{API}/admin/staff", headers=admin_headers, timeout=30).json()
        admins = [s for s in listing if s.get("role") == "admin"]
        if len(admins) == 1:
            r = requests.delete(f"{API}/admin/staff/{admins[0]['id']}", headers=admin_headers, timeout=30)
            assert r.status_code == 400


# ---- PUBLIC CONTENT ----
class TestPublicContent:
    def test_content_all(self):
        r = requests.get(f"{API}/content/all", timeout=30)
        assert r.status_code == 200
        data = r.json()
        for key in ["team", "services", "partners", "stats", "albums", "settings"]:
            assert key in data
        assert len(data["team"]) >= 1
        assert len(data["albums"]) >= 1
        assert data["settings"].get("hero_title")


# ---- CONTACT ----
class TestContact:
    def test_contact_submit_and_list(self, admin_headers):
        payload = {"name": "TEST_Contact", "email": "test@example.com", "category": "Siswa", "message": "Halo test message"}
        r = requests.post(f"{API}/contact", json=payload, timeout=30)
        assert r.status_code == 200
        cid = r.json()["id"]

        r2 = requests.get(f"{API}/contact", headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        assert any(c["id"] == cid for c in r2.json())
