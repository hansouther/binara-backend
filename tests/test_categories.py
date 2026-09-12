"""Backend tests for dynamic Contact Categories feature."""
import os
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if os.environ.get('REACT_APP_BACKEND_URL') else None
if not BASE_URL:
    # fallback: read frontend/.env
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break

ADMIN_EMAIL = "admin@binaralabs.id"
ADMIN_PASSWORD = "Binara2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- Categories CRUD ----------------
class TestCategoriesCRUD:
    created_ids = []

    def test_get_categories_default(self):
        r = requests.get(f"{BASE_URL}/api/content/categories")
        assert r.status_code == 200
        data = r.json()
        labels = [c["label"] for c in data]
        assert "Siswa" in labels
        assert "Perusahaan" in labels

    def test_create_category_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/admin/content/categories", json={"label": "TEST_NoAuth", "icon": "Users", "order": 5})
        assert r.status_code == 401

    def test_create_category(self, auth_headers):
        payload = {"label": "TEST_Guru / Sekolah", "icon": "Users", "order": 2}
        r = requests.post(f"{BASE_URL}/api/admin/content/categories", json=payload, headers=auth_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["label"] == payload["label"]
        assert d["icon"] == "Users"
        assert "id" in d
        TestCategoriesCRUD.created_ids.append(d["id"])

        # verify via GET
        r2 = requests.get(f"{BASE_URL}/api/content/categories")
        labels = [c["label"] for c in r2.json()]
        assert payload["label"] in labels

    def test_update_category(self, auth_headers):
        cid = TestCategoriesCRUD.created_ids[0]
        r = requests.put(f"{BASE_URL}/api/admin/content/categories/{cid}",
                         json={"label": "TEST_Guru Updated", "icon": "GraduationCap", "order": 3},
                         headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["label"] == "TEST_Guru Updated"

    def test_reorder_categories(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/content/categories")
        items = r.json()
        ids = [c["id"] for c in items]
        reversed_ids = list(reversed(ids))
        r2 = requests.post(f"{BASE_URL}/api/admin/content/categories/reorder",
                           json={"ids": reversed_ids}, headers=auth_headers)
        assert r2.status_code == 200
        r3 = requests.get(f"{BASE_URL}/api/content/categories")
        new_ids = [c["id"] for c in r3.json()]
        assert new_ids == reversed_ids

    def test_reorder_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/admin/content/categories/reorder", json={"ids": []})
        assert r.status_code == 401

    def test_content_all_includes_categories(self):
        r = requests.get(f"{BASE_URL}/api/content/all")
        assert r.status_code == 200
        assert "categories" in r.json()

    def test_delete_category(self, auth_headers):
        cid = TestCategoriesCRUD.created_ids[0]
        r = requests.delete(f"{BASE_URL}/api/admin/content/categories/{cid}", headers=auth_headers)
        assert r.status_code == 200
        # verify gone
        r2 = requests.get(f"{BASE_URL}/api/content/categories")
        ids = [c["id"] for c in r2.json()]
        assert cid not in ids
        TestCategoriesCRUD.created_ids.remove(cid)


# ---------------- Contact validation dinamis ----------------
class TestContactValidation:
    created_contact_ids = []

    def test_contact_valid_category_siswa(self):
        payload = {"name": "TEST_User", "email": "test@example.com", "category": "Siswa", "message": "Halo tim Binara"}
        r = requests.post(f"{BASE_URL}/api/contact", json=payload)
        assert r.status_code == 200, r.text
        assert r.json()["category"] == "Siswa"
        TestContactValidation.created_contact_ids.append(r.json()["id"])

    def test_contact_invalid_category(self):
        payload = {"name": "TEST_User", "email": "test@example.com", "category": "NotARealCategory_XYZ", "message": "Should fail"}
        r = requests.post(f"{BASE_URL}/api/contact", json=payload)
        assert r.status_code == 422, r.text

    def test_contact_valid_after_dynamic_add(self, auth_headers):
        # add new category
        new_label = "TEST_DynamicCat"
        r = requests.post(f"{BASE_URL}/api/admin/content/categories",
                          json={"label": new_label, "icon": "Users", "order": 10}, headers=auth_headers)
        assert r.status_code == 200
        cat_id = r.json()["id"]
        try:
            # contact with this category should succeed now
            r2 = requests.post(f"{BASE_URL}/api/contact", json={
                "name": "TEST_User2", "email": "t2@example.com", "category": new_label, "message": "dynamic ok"
            })
            assert r2.status_code == 200, r2.text
            TestContactValidation.created_contact_ids.append(r2.json()["id"])
        finally:
            requests.delete(f"{BASE_URL}/api/admin/content/categories/{cat_id}", headers=auth_headers)

    @classmethod
    def teardown_class(cls):
        # cleanup contacts via admin API? no delete endpoint for contacts -> drop directly via Mongo
        # Best-effort: leave test contacts (prefix TEST_) - low volume.
        pass
