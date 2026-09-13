from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict

from auth import hash_password, verify_password, create_access_token, decode_token
from storage import init_storage, put_object, get_object, MIME_TYPES, APP_NAME
from seed import seed_content
from emailer import send_reset_email

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------- Auth ----------------
async def require_auth(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Tidak terautentikasi")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token tidak valid atau kedaluwarsa")
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Pengguna tidak ditemukan")
    return user


async def require_admin(user: dict = Depends(require_auth)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Akses khusus admin")
    return user


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class StaffCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str
    role: str = "staff"


@api_router.post("/auth/login")
async def login(body: LoginBody):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah")
    token = create_access_token(user["id"], user["email"], user.get("role", "staff"))
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user.get("name"), "role": user.get("role")},
    }


@api_router.get("/auth/me")
async def me(user: dict = Depends(require_auth)):
    return user


class ForgotBody(BaseModel):
    email: EmailStr


class ResetBody(BaseModel):
    token: str
    password: str = Field(..., min_length=6)


@api_router.post("/auth/forgot-password")
async def forgot_password(body: ForgotBody, request: Request):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if user:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.password_reset_tokens.insert_one({
            "token": token, "user_id": user["id"], "email": email,
            "expires_at": expires, "used": False, "created_at": _iso(),
        })
        origin = request.headers.get("origin") or os.environ.get("FRONTEND_URL", "")
        reset_link = f"{origin.rstrip('/')}/admin/reset-password?token={token}"
        try:
            await send_reset_email(to=email, name=user.get("name", "Admin"), reset_link=reset_link)
        except Exception as e:
            logger.error(f"Reset email failed: {e}")
    return {"ok": True}


@api_router.post("/auth/reset-password")
async def reset_password(body: ResetBody):
    doc = await db.password_reset_tokens.find_one({"token": body.token})
    if not doc or doc.get("used"):
        raise HTTPException(status_code=400, detail="Token tidak valid atau sudah digunakan")
    exp = doc["expires_at"]
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token sudah kedaluwarsa. Minta tautan baru.")
    await db.users.update_one({"id": doc["user_id"]}, {"$set": {"password_hash": hash_password(body.password)}})
    await db.password_reset_tokens.update_one({"token": body.token}, {"$set": {"used": True}})
    return {"ok": True}


@api_router.get("/admin/staff")
async def list_staff(user: dict = Depends(require_admin)):
    return await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(200)


@api_router.post("/admin/staff")
async def create_staff(body: StaffCreate, user: dict = Depends(require_admin)):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    doc = {
        "id": str(uuid.uuid4()), "email": email, "password_hash": hash_password(body.password),
        "name": body.name, "role": body.role if body.role in ("admin", "staff") else "staff",
        "created_at": _iso(),
    }
    await db.users.insert_one(dict(doc))
    await log_audit(user, "create", "staff", doc["email"], doc["id"])
    return {"id": doc["id"], "email": doc["email"], "name": doc["name"], "role": doc["role"], "created_at": doc["created_at"]}


@api_router.delete("/admin/staff/{staff_id}")
async def delete_staff(staff_id: str, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"id": staff_id})
    if not target:
        raise HTTPException(status_code=404, detail="Staf tidak ditemukan")
    if target.get("role") == "admin" and await db.users.count_documents({"role": "admin"}) <= 1:
        raise HTTPException(status_code=400, detail="Tidak dapat menghapus satu-satunya admin")
    await db.users.delete_one({"id": staff_id})
    await log_audit(user, "delete", "staff", target.get("email"), staff_id)
    return {"ok": True}


# ---------------- Content CRUD ----------------
COLLECTIONS = {"team", "services", "partners", "stats", "albums", "categories", "news"}


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


def _label_of(payload):
    if not payload:
        return None
    for k in ("name", "title", "label"):
        if payload.get(k):
            return payload[k]
    return None


async def log_audit(user: dict, action: str, target: str, label=None, item_id=None):
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "user_email": user.get("email"),
        "user_name": user.get("name"),
        "action": action,
        "target": target,
        "label": label,
        "item_id": item_id,
        "created_at": _iso(),
    })


@api_router.get("/admin/audit")
async def list_audit(user: dict = Depends(require_auth)):
    return await db.audit_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)


@api_router.get("/content/all")
async def content_all():
    out = {}
    for c in COLLECTIONS:
        out[c] = await db[c].find({}, {"_id": 0}).sort([("order", 1), ("created_at", 1)]).to_list(1000)
    settings = await db.settings.find_one({"_key": "site"}, {"_id": 0})
    out["settings"] = settings or {}
    return out


@api_router.get("/content/{coll}")
async def list_content(coll: str):
    if coll not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Koleksi tidak ditemukan")
    return await db[coll].find({}, {"_id": 0}).sort([("order", 1), ("created_at", 1)]).to_list(1000)


@api_router.post("/admin/content/{coll}")
async def create_item(coll: str, payload: dict, user: dict = Depends(require_auth)):
    if coll not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Koleksi tidak ditemukan")
    payload.pop("_id", None)
    payload["id"] = str(uuid.uuid4())
    payload.setdefault("order", 999)
    payload["created_at"] = _iso()
    await db[coll].insert_one(dict(payload))
    await log_audit(user, "create", coll, _label_of(payload), payload["id"])
    return _clean(payload)


@api_router.put("/admin/content/{coll}/{item_id}")
async def update_item(coll: str, item_id: str, payload: dict, user: dict = Depends(require_auth)):
    if coll not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Koleksi tidak ditemukan")
    payload.pop("_id", None)
    payload.pop("id", None)
    await db[coll].update_one({"id": item_id}, {"$set": payload})
    doc = await db[coll].find_one({"id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Item tidak ditemukan")
    await log_audit(user, "update", coll, _label_of(doc), item_id)
    return doc


@api_router.delete("/admin/content/{coll}/{item_id}")
async def delete_item(coll: str, item_id: str, user: dict = Depends(require_auth)):
    if coll not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Koleksi tidak ditemukan")
    existing = await db[coll].find_one({"id": item_id}, {"_id": 0})
    await db[coll].delete_one({"id": item_id})
    await log_audit(user, "delete", coll, _label_of(existing), item_id)
    return {"ok": True}


class ReorderBody(BaseModel):
    ids: List[str]


@api_router.post("/admin/content/{coll}/reorder")
async def reorder_items(coll: str, body: ReorderBody, user: dict = Depends(require_auth)):
    if coll not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Koleksi tidak ditemukan")
    for i, item_id in enumerate(body.ids):
        await db[coll].update_one({"id": item_id}, {"$set": {"order": i}})
    await log_audit(user, "reorder", coll, f"{len(body.ids)} item")
    return {"ok": True}


@api_router.get("/content/settings/site")
async def get_settings():
    s = await db.settings.find_one({"_key": "site"}, {"_id": 0})
    return s or {}


@api_router.put("/admin/settings")
async def update_settings(payload: dict, user: dict = Depends(require_auth)):
    payload.pop("_id", None)
    payload["_key"] = "site"
    await db.settings.update_one({"_key": "site"}, {"$set": payload}, upsert=True)
    s = await db.settings.find_one({"_key": "site"}, {"_id": 0})
    await log_audit(user, "update", "settings", "Pengaturan situs")
    return s


# ---------------- Uploads ----------------
@api_router.post("/admin/upload")
async def upload(file: UploadFile = File(...), user: dict = Depends(require_auth)):
    ext = (file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "bin")
    content_type = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    path = f"{APP_NAME}/uploads/{uuid.uuid4()}.{ext}"
    data = await file.read()
    result = put_object(path, data, content_type)
    stored_path = result["path"]
    await db.files.insert_one({
        "id": str(uuid.uuid4()), "storage_path": stored_path, "original_filename": file.filename,
        "content_type": content_type, "size": result.get("size"), "is_deleted": False, "created_at": _iso(),
    })
    return {"url": f"/api/files/{stored_path}", "path": stored_path}


@api_router.get("/files/{path:path}")
async def serve_file(path: str):
    record = await db.files.find_one({"storage_path": path, "is_deleted": False})
    try:
        data, content_type = get_object(path)
    except Exception:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    ct = (record or {}).get("content_type") or content_type
    return Response(content=data, media_type=ct, headers={"Cache-Control": "public, max-age=86400"})


# ---------------- Contact ----------------
class ContactCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    category: str = Field(..., min_length=1, max_length=80)
    message: str = Field(..., min_length=5, max_length=2000)


@api_router.get("/")
async def root():
    return {"message": "Binara Labs API"}


@api_router.post("/contact")
async def create_contact(payload: ContactCreate):
    cats = await db.categories.find({}, {"_id": 0, "label": 1}).to_list(100)
    labels = [c.get("label") for c in cats]
    if labels and payload.category not in labels:
        raise HTTPException(status_code=422, detail="Kategori tidak valid")
    doc = payload.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = _iso()
    await db.contacts.insert_one(dict(doc))
    return _clean(doc)


@api_router.get("/contact")
async def list_contacts(user: dict = Depends(require_auth)):
    return await db.contacts.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


app.include_router(api_router)

origins = [
    "http://localhost:3000",
    "https://binaralab.netlify.app",
    "https://binara.site",
    "https://www.binara.site"
]
    
app.add_middleware(
    CORSMiddleware,

    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


async def seed_admin():
    email = os.environ.get("ADMIN_EMAIL", "admin@binaralabs.id").lower()
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": email})
    if existing is None:
        await db.users.insert_one({
            "id": str(uuid.uuid4()), "email": email, "password_hash": hash_password(password),
            "name": "Administrator", "role": "admin", "created_at": _iso(),
        })
    elif not verify_password(password, existing.get("password_hash", "")):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})


@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    try:
        await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    except Exception:
        pass
    await seed_admin()
    await seed_content(db)
    try:
        # init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
