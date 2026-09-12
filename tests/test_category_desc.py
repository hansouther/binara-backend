"""Backend tests: 'desc' field persistence on categories."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break

ADMIN_EMAIL = "admin@binaralabs.id"
ADMIN_PASSWORD = "Binara2026!"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_default_categories_have_desc():
    r = requests.get(f"{BASE_URL}/api/content/categories")
    assert r.status_code == 200
    cats = r.json()
    by_label = {c["label"]: c for c in cats}
    assert "Siswa" in by_label and "Perusahaan" in by_label
    for label in ("Siswa", "Perusahaan"):
        assert "desc" in by_label[label], f"Category {label} missing desc field"
        assert isinstance(by_label[label]["desc"], str) and by_label[label]["desc"].strip(), \
            f"Category {label} has empty desc"


def test_content_all_includes_categories_with_desc():
    r = requests.get(f"{BASE_URL}/api/content/all")
    assert r.status_code == 200
    payload = r.json()
    assert "categories" in payload
    for c in payload["categories"]:
        # desc key must be present on default seeded items
        if c["label"] in ("Siswa", "Perusahaan"):
            assert c.get("desc"), f"desc missing on {c['label']} in /content/all"


def test_create_update_category_persists_desc(auth_headers):
    # create with desc
    payload = {"label": "TEST_DescCat", "icon": "Users", "desc": "TEST desc initial", "order": 99}
    r = requests.post(f"{BASE_URL}/api/admin/content/categories", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    created = r.json()
    cid = created["id"]
    assert created.get("desc") == "TEST desc initial"

    try:
        # verify GET
        r2 = requests.get(f"{BASE_URL}/api/content/categories")
        item = next(c for c in r2.json() if c["id"] == cid)
        assert item["desc"] == "TEST desc initial"

        # update desc
        r3 = requests.put(f"{BASE_URL}/api/admin/content/categories/{cid}",
                          json={"label": "TEST_DescCat", "icon": "Users",
                                "desc": "TEST desc updated", "order": 99},
                          headers=auth_headers)
        assert r3.status_code == 200
        assert r3.json()["desc"] == "TEST desc updated"

        # verify persistence
        r4 = requests.get(f"{BASE_URL}/api/content/categories")
        item = next(c for c in r4.json() if c["id"] == cid)
        assert item["desc"] == "TEST desc updated"
    finally:
        requests.delete(f"{BASE_URL}/api/admin/content/categories/{cid}", headers=auth_headers)


def test_empty_desc_is_accepted(auth_headers):
    payload = {"label": "TEST_NoDesc", "icon": "Users", "desc": "", "order": 98}
    r = requests.post(f"{BASE_URL}/api/admin/content/categories", json=payload, headers=auth_headers)
    assert r.status_code == 200
    cid = r.json()["id"]
    try:
        assert r.json().get("desc") == ""
    finally:
        requests.delete(f"{BASE_URL}/api/admin/content/categories/{cid}", headers=auth_headers)
