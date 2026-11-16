import os
import re
import json
import subprocess
import sys
import threading
from urllib.parse import urlparse
import uuid
import hmac
import hashlib
import secrets
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from starlette.concurrency import run_in_threadpool

from extractors import FIELDS, DOC_TYPES, FILE_ONLY_TYPES, EXTRA_FIELDS, extract_fields, read_text

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "exam_buddy.db"
UPLOAD_DIR = ROOT / "uploads"
STATIC_DIR = ROOT / "static"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Exam Buddy API", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
STATUSES = {"Not Started", "In Progress", "Needs Correction", "Ready for Review", "Completed", "Cancelled"}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return salt.hex() + "$" + digest.hex()

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 240_000).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except Exception:
        return False

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            phone TEXT DEFAULT '',
            city TEXT DEFAULT '',
            date_of_birth TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            extracted_text TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            exam_name TEXT NOT NULL,
            exam_session TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Not Started',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS support_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL
        );
        """)
        row = db.execute("SELECT id FROM users WHERE email = ?", ("admin@exambuddy.local",)).fetchone()
        if not row:
            db.execute(
                "INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                ("Exam Buddy Admin", "admin@exambuddy.local", hash_password("ChangeMe123!"), "admin", now_iso())
            )

def add_column(db, table, column, ddl):
    """Adds a column to an existing table if it is not there yet (keeps old databases working)."""
    existing = [r["name"] for r in db.execute(f"PRAGMA table_info({table})")]
    if column not in existing:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

def migrate_db():
    with connect() as db:
        add_column(db, "documents", "doc_type", "TEXT DEFAULT ''")
        add_column(db, "documents", "application_id", "INTEGER")
        add_column(db, "applications", "fields_json", "TEXT DEFAULT '{}'")
        add_column(db, "applications", "fields_confirmed", "INTEGER DEFAULT 0")

init_db()
migrate_db()
SESSION_DAYS = 7

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

class LoginIn(BaseModel):
    email: str
    password: str

class ProfileIn(BaseModel):
    phone: str = Field(default="", max_length=30)
    city: str = Field(default="", max_length=100)
    date_of_birth: str = Field(default="", max_length=20)

class ApplicationIn(BaseModel):
    exam_name: str = Field(min_length=2, max_length=100)
    exam_session: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=2000)

class ApplicationUpdate(BaseModel):
    status: str
    notes: Optional[str] = Field(default=None, max_length=2000)  # None = leave notes unchanged

class FieldsIn(BaseModel):
    fields: dict            # {"aadhaar": {"name": "..."}, "class10": {...}, ...}
    confirmed: bool = False

class SupportIn(BaseModel):
    subject: str = Field(min_length=2, max_length=150)
    message: str = Field(min_length=5, max_length=3000)

def normalize_email(email: str) -> str:
    return email.strip().lower()

def validate_email(email: str):
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Enter a valid email address.")

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def get_current_user(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please log in.")
    token = authorization.split(" ", 1)[1].strip()
    with connect() as db:
        row = db.execute("""
            SELECT u.id, u.name, u.email, u.role, u.created_at
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.created_at > ?
        """, (token_hash(token), (datetime.now(timezone.utc) - timedelta(days=SESSION_DAYS)).isoformat())).fetchone()
    if not row:
        raise HTTPException(401, "Session expired. Please log in again.")
    return dict(row)

def require_admin(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required.")
    return user

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Exam Buddy API"}

@app.post("/api/auth/register")
def register(data: RegisterIn):
    email = normalize_email(data.email)
    validate_email(email)
    if len(data.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    with connect() as db:
        if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(409, "An account with this email already exists.")
        cur = db.execute(
            "INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
            (data.name.strip(), email, hash_password(data.password), "student", now_iso())
        )
        user_id = cur.lastrowid
        db.execute("INSERT INTO profiles (user_id,updated_at) VALUES (?,?)", (user_id, now_iso()))
    return {"message": "Account created. You can now log in."}

@app.post("/api/auth/login")
def login(data: LoginIn):
    email = normalize_email(data.email)
    with connect() as db:
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(401, "Incorrect email or password.")
        token = secrets.token_urlsafe(32)
        db.execute("INSERT INTO sessions (token_hash,user_id,created_at) VALUES (?,?,?)",
                   (token_hash(token), user["id"], now_iso()))
        return {
            "token": token,
            "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}
        }

@app.post("/api/auth/logout")
def logout(user=Depends(get_current_user), authorization: Optional[str] = Header(default=None)):
    token = authorization.split(" ", 1)[1].strip()
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
    return {"message": "Logged out."}

@app.get("/api/me")
def me(user=Depends(get_current_user)):
    with connect() as db:
        profile = db.execute("SELECT phone,city,date_of_birth,updated_at FROM profiles WHERE user_id = ?",
                              (user["id"],)).fetchone()
    return {"user": user, "profile": dict(profile) if profile else {}}

@app.put("/api/profile")
def update_profile(data: ProfileIn, user=Depends(get_current_user)):
    with connect() as db:
        db.execute("""
            INSERT INTO profiles (user_id,phone,city,date_of_birth,updated_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
            phone=excluded.phone, city=excluded.city,
            date_of_birth=excluded.date_of_birth, updated_at=excluded.updated_at
        """, (user["id"], data.phone.strip(), data.city.strip(), data.date_of_birth.strip(), now_iso()))
    return {"message": "Profile saved."}

def load_fields(row) -> dict:
    try:
        return json.loads(row["fields_json"] or "{}")
    except ValueError:
        return {}

def get_application_for(db, application_id: int, user):
    """Returns the application row if this user owns it (admins can open any)."""
    row = db.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Application not found.")
    if user["role"] != "admin" and row["user_id"] != user["id"]:
        raise HTTPException(403, "This is not your application.")
    return row

@app.post("/api/documents")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(""),                      # "aadhaar", "class10" or "class12" (empty = plain upload)
    application_id: Optional[int] = Form(None),
    user=Depends(get_current_user),
):
    original = Path(file.filename or "upload").name
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Supported formats: PNG, JPG, JPEG, WEBP, PDF.")
    if doc_type and doc_type not in DOC_TYPES and doc_type not in FILE_ONLY_TYPES:
        raise HTTPException(400, "Unknown document type.")
    if doc_type in FILE_ONLY_TYPES and ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(400, "Photo and signature must be an image (PNG, JPG or WEBP).")
    if doc_type and application_id is None:
        raise HTTPException(400, "Choose which application this document belongs to.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(400, "The selected file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is too large. Maximum size is 8 MB.")
    # Basic signature checks to avoid trusting the extension alone.
    signatures = {
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".jpeg": content.startswith(b"\xff\xd8\xff"),
        ".webp": len(content) > 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP",
        ".pdf": content.startswith(b"%PDF")
    }
    if not signatures.get(ext, False):
        raise HTTPException(400, "The file contents do not match the selected file type.")

    # Only the owner may attach documents to an application.
    if application_id is not None:
        with connect() as db:
            app_row = db.execute("SELECT user_id FROM applications WHERE id = ?", (application_id,)).fetchone()
        if not app_row or app_row["user_id"] != user["id"]:
            raise HTTPException(403, "This is not your application.")

    stored = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / stored
    path.write_bytes(content)

    # Read the document (runs in a thread so the server stays responsive while OCR works).
    if doc_type in FILE_ONLY_TYPES:
        found, extracted = {}, ""                      # photo / signature: just store the picture
    elif doc_type:
        found, extracted = await run_in_threadpool(extract_fields, path, doc_type)
    else:
        found, extracted = {}, await run_in_threadpool(read_text, path)

    old_file = None
    with connect() as db:
        if doc_type:
            # A newer upload of the same document type replaces the older one.
            old = db.execute("SELECT id, stored_name FROM documents WHERE application_id=? AND doc_type=?",
                             (application_id, doc_type)).fetchone()
            if old:
                db.execute("DELETE FROM documents WHERE id=?", (old["id"],))
                old_file = old["stored_name"]
        cur = db.execute("""
            INSERT INTO documents (user_id,original_name,stored_name,file_type,size_bytes,extracted_text,created_at,doc_type,application_id)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (user["id"], original, stored, ext, len(content), extracted, now_iso(), doc_type, application_id))
        doc_id = cur.lastrowid
        if doc_type in DOC_TYPES:
            app_row = db.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
            all_fields = load_fields(app_row)
            all_fields[doc_type] = found
            db.execute("UPDATE applications SET fields_json=?, fields_confirmed=0, updated_at=? WHERE id=?",
                       (json.dumps(all_fields), now_iso(), application_id))
    if old_file:
        (UPLOAD_DIR / old_file).unlink(missing_ok=True)

    msg = "File uploaded."
    if doc_type in FILE_ONLY_TYPES:
        msg = "Photo uploaded." if doc_type == "photo" else "Signature uploaded."
    elif not extracted:
        msg += " We could not read any text automatically. Please type the details in yourself, or upload a clearer image."
    elif doc_type:
        msg += f" We found {len(found)} detail(s). Please check them carefully."
    return {"message": msg, "document": {
        "id": doc_id, "original_name": original, "file_type": ext, "doc_type": doc_type,
        "size_bytes": len(content), "extracted_text": extracted, "fields": found,
        "verification_required": True, "created_at": now_iso()
    }}

@app.get("/api/documents")
def list_documents(user=Depends(get_current_user)):
    with connect() as db:
        rows = db.execute("""
            SELECT id,original_name,file_type,size_bytes,extracted_text,created_at,doc_type,application_id
            FROM documents WHERE user_id = ? ORDER BY id DESC
        """, (user["id"],)).fetchall()
    return [dict(row) for row in rows]

@app.get("/api/documents/{document_id}/file")
def download_document(document_id: int, user=Depends(get_current_user)):
    """Owner or admin can open the original uploaded file."""
    with connect() as db:
        row = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found.")
    if row["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "You cannot open this document.")
    return FileResponse(UPLOAD_DIR / row["stored_name"], filename=row["original_name"])

@app.delete("/api/documents/{document_id}")
def delete_document(document_id: int, user=Depends(get_current_user)):
    with connect() as db:
        row = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Document not found.")
        if row["user_id"] != user["id"] and user["role"] != "admin":
            raise HTTPException(403, "You cannot delete this document.")
        db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    try:
        (UPLOAD_DIR / row["stored_name"]).unlink(missing_ok=True)
    except OSError:
        pass
    return {"message": "Document deleted."}

@app.get("/api/applications/{application_id}/details")
def application_details(application_id: int, user=Depends(get_current_user)):
    """Everything the review screen needs: documents, extracted fields and the field names."""
    with connect() as db:
        row = get_application_for(db, application_id, user)
        docs = db.execute("""SELECT id,doc_type,original_name,file_type,created_at,extracted_text
                             FROM documents WHERE application_id=?""", (application_id,)).fetchall()
    return {
        "application": {"id": row["id"], "exam_name": row["exam_name"], "status": row["status"]},
        "documents": [dict(d) for d in docs],
        "fields": load_fields(row),
        "confirmed": bool(row["fields_confirmed"]),
        "field_defs": {k: [{"key": key, "label": label} for key, label in v] for k, v in FIELDS.items()},
        "extra_defs": EXTRA_FIELDS,
    }

@app.put("/api/applications/{application_id}/fields")
def save_fields(application_id: int, data: FieldsIn, user=Depends(get_current_user)):
    """Student saves (and optionally confirms) the corrected details."""
    clean = {}
    extra_keys = {f["key"] for f in EXTRA_FIELDS}
    for doc_type, values in data.fields.items():
        if doc_type == "extra" and isinstance(values, dict):
            clean["extra"] = {k: str(v).strip()[:300] for k, v in values.items() if k in extra_keys and v is not None}
            continue
        if doc_type not in FIELDS or not isinstance(values, dict):
            continue
        allowed = {key for key, _ in FIELDS[doc_type]}
        clean[doc_type] = {k: str(v).strip()[:100] for k, v in values.items() if k in allowed and v is not None}
    with connect() as db:
        row = get_application_for(db, application_id, user)
        if row["user_id"] != user["id"]:
            raise HTTPException(403, "Only the student can edit their own details.")
        status = row["status"]
        if data.confirmed and status in {"Not Started", "Needs Correction"}:
            status = "Ready for Review"
        db.execute("UPDATE applications SET fields_json=?, fields_confirmed=?, status=?, updated_at=? WHERE id=?",
                   (json.dumps(clean), 1 if data.confirmed else 0, status, now_iso(), application_id))
    return {"message": "Details confirmed and sent to Exam Buddy." if data.confirmed else "Details saved."}

@app.post("/api/applications")
def create_application(data: ApplicationIn, user=Depends(get_current_user)):
    with connect() as db:
        cur = db.execute("""
            INSERT INTO applications (user_id,exam_name,exam_session,status,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)
        """, (user["id"], data.exam_name.strip(), data.exam_session.strip(), "Not Started",
              data.notes.strip(), now_iso(), now_iso()))
        app_id = cur.lastrowid
        row = db.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    return dict(row)

@app.get("/api/applications")
def list_applications(user=Depends(get_current_user)):
    with connect() as db:
        if user["role"] == "admin":
            rows = db.execute("""
                SELECT a.*, u.name AS student_name, u.email AS student_email
                FROM applications a JOIN users u ON u.id=a.user_id ORDER BY a.id DESC
            """).fetchall()
        else:
            rows = db.execute("SELECT * FROM applications WHERE user_id = ? ORDER BY id DESC",
                              (user["id"],)).fetchall()
    return [dict(row) for row in rows]

@app.patch("/api/applications/{application_id}")
def update_application(application_id: int, data: ApplicationUpdate, user=Depends(get_current_user)):
    if data.status not in STATUSES:
        raise HTTPException(400, "Invalid application status.")
    with connect() as db:
        row = db.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Application not found.")
        if user["role"] != "admin" and row["user_id"] != user["id"]:
            raise HTTPException(403, "You cannot edit this application.")
        if user["role"] != "admin" and data.status not in {"Not Started", "Cancelled"}:
            raise HTTPException(403, "Only Exam Buddy staff can set this status.")
        notes = row["notes"] if data.notes is None else data.notes.strip()
        db.execute("UPDATE applications SET status=?, notes=?, updated_at=? WHERE id=?",
                   (data.status, notes, now_iso(), application_id))
        updated = db.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
    return dict(updated)

@app.post("/api/support")
def create_support(data: SupportIn, user=Depends(get_current_user)):
    with connect() as db:
        cur = db.execute("""
            INSERT INTO support_requests (user_id,subject,message,status,created_at)
            VALUES (?,?,?,?,?)
        """, (user["id"], data.subject.strip(), data.message.strip(), "Open", now_iso()))
    return {"message": "Support request submitted.", "id": cur.lastrowid}

@app.get("/api/support")
def list_support(user=Depends(get_current_user)):
    with connect() as db:
        if user["role"] == "admin":
            rows = db.execute("""
                SELECT s.*, u.name AS student_name, u.email AS student_email
                FROM support_requests s JOIN users u ON u.id=s.user_id ORDER BY s.id DESC
            """).fetchall()
        else:
            rows = db.execute("SELECT * FROM support_requests WHERE user_id=? ORDER BY id DESC",
                              (user["id"],)).fetchall()
    return [dict(row) for row in rows]

@app.get("/api/admin/summary")
def admin_summary(user=Depends(require_admin)):
    with connect() as db:
        users = db.execute("SELECT COUNT(*) n FROM users WHERE role='student'").fetchone()["n"]
        applications = db.execute("SELECT COUNT(*) n FROM applications").fetchone()["n"]
        pending = db.execute("SELECT COUNT(*) n FROM applications WHERE status NOT IN ('Completed','Cancelled')").fetchone()["n"]
        documents = db.execute("SELECT COUNT(*) n FROM documents").fetchone()["n"]
        support = db.execute("SELECT COUNT(*) n FROM support_requests WHERE status='Open'").fetchone()["n"]
    return {"students": users, "applications": applications, "pending_applications": pending,
            "documents": documents, "open_support_requests": support}

@app.get("/api/admin/users")
def admin_users(user=Depends(require_admin)):
    with connect() as db:
        rows = db.execute("""
            SELECT u.id,u.name,u.email,u.role,u.created_at,
            (SELECT COUNT(*) FROM applications a WHERE a.user_id=u.id) AS application_count
            FROM users u ORDER BY u.id DESC
        """).fetchall()
    return [dict(row) for row in rows]

@app.patch("/api/admin/support/{request_id}")
def update_support(request_id: int, status: str, user=Depends(require_admin)):
    if status not in {"Open", "In Progress", "Resolved"}:
        raise HTTPException(400, "Invalid support status.")
    with connect() as db:
        cur = db.execute("UPDATE support_requests SET status=? WHERE id=?", (status, request_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Support request not found.")
    return {"message": "Support status updated."}


# ---------------------------------------------------------------- filling an online form (admin only)
# The browser runs in a separate helper program (form_worker.py) so it can never freeze the website.
WORKER = {"proc": None}
WORKER_LOCK = threading.Lock()
REPLY_PREFIX = "@@REPLY@@"

class FormOpenIn(BaseModel):
    application_id: int
    url: str = Field(min_length=8, max_length=2000)
    allow_unconfirmed: bool = False

class FormFillIn(BaseModel):
    application_id: int
    allow_unconfirmed: bool = False

def worker_call(command: dict) -> dict:
    """Sends one command to the helper program and waits for its answer."""
    with WORKER_LOCK:
        proc = WORKER["proc"]
        if proc is None or proc.poll() is not None:
            proc = subprocess.Popen(
                [sys.executable, str(ROOT / "form_worker.py")], cwd=str(ROOT),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
            WORKER["proc"] = proc
        try:
            proc.stdin.write(json.dumps(command) + "\n")
            proc.stdin.flush()
            while True:
                line = proc.stdout.readline()
                if not line:
                    raise RuntimeError("stopped")
                if line.startswith(REPLY_PREFIX):
                    return json.loads(line[len(REPLY_PREFIX):])
        except (BrokenPipeError, OSError, RuntimeError):
            WORKER["proc"] = None
            raise HTTPException(500, "The form helper stopped. Look at the terminal for the reason. "
                                     "Did you run: python -m pip install -r requirements.txt ?")

def form_values(application_id: int, allow_unconfirmed: bool) -> dict:
    """Collects the student's confirmed details into one dictionary for the form filler."""
    with connect() as db:
        row = db.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Application not found.")
        if not row["fields_confirmed"] and not allow_unconfirmed:
            raise HTTPException(400, "The student has not confirmed their details yet. "
                                     "Tick 'fill even if not confirmed' to continue anyway.")
        files = {d["doc_type"]: d["stored_name"] for d in db.execute(
            "SELECT doc_type, stored_name FROM documents WHERE application_id = ? AND doc_type IN ('photo','signature')",
            (application_id,)).fetchall()}
        student = db.execute("SELECT name,email FROM users WHERE id = ?", (row["user_id"],)).fetchone()
        profile = db.execute("SELECT phone,city FROM profiles WHERE user_id = ?", (row["user_id"],)).fetchone()
    fields = load_fields(row)

    def pick(key, order):
        for doc_type in order:
            value = (fields.get(doc_type) or {}).get(key)
            if value:
                return value
        return ""

    values = {
        "name": pick("name", ["aadhaar", "class10", "class12"]) or student["name"],
        "dob": pick("dob", ["aadhaar", "class10", "class12"]),
        "gender": pick("gender", ["aadhaar"]),
        "aadhaar_number": pick("aadhaar_number", ["aadhaar"]),
        "father_name": pick("father_name", ["class12", "class10"]),
        "mother_name": pick("mother_name", ["class12", "class10"]),
        "email": student["email"],
        "phone": (profile["phone"] if profile else "") or "",
        "city": (profile["city"] if profile else "") or "",
    }
    # details typed by the student on the "Extra details" form win over the older profile values
    for key, value in (fields.get("extra") or {}).items():
        if value:
            values[key] = value
    if not values.get("nationality"):
        values["nationality"] = ""
    for kind in ("photo", "signature"):
        if kind in files:
            values[f"{kind}_path"] = str(UPLOAD_DIR / files[kind])
    for number, doc_type in (("10", "class10"), ("12", "class12")):
        for key in ("board", "roll_no", "year", "school"):
            values[f"{key}_{number}"] = (fields.get(doc_type) or {}).get(key, "")
    return values

@app.post("/api/admin/form/open")
def form_open(data: FormOpenIn, user=Depends(require_admin)):
    parsed = urlparse(data.url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "Paste a full link that starts with https://")
    values = form_values(data.application_id, data.allow_unconfirmed)
    result = worker_call({"cmd": "open", "url": data.url.strip(), "values": values})
    if not result.get("ok"):
        raise HTTPException(500, result.get("error", "Could not open the form."))
    return result["report"]

@app.post("/api/admin/form/fill")
def form_fill(data: FormFillIn, user=Depends(require_admin)):
    """Fills the page that is showing right now (use it again after pressing Next in the form)."""
    values = form_values(data.application_id, data.allow_unconfirmed)
    result = worker_call({"cmd": "fill", "values": values})
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Could not fill this page."))
    return result["report"]

@app.post("/api/admin/form/check")
def form_check(user=Depends(require_admin)):
    """Tells the admin whether the form-filling browser can start on this computer."""
    result = worker_call({"cmd": "check"})
    if not result.get("ok"):
        raise HTTPException(500, result.get("error", "The browser could not be started."))
    return {"message": result["message"]}

@app.post("/api/admin/form/close")
def form_close(user=Depends(require_admin)):
    if WORKER["proc"] is not None and WORKER["proc"].poll() is None:
        worker_call({"cmd": "close"})
    return {"message": "Form window closed."}