
import os
import json
import sqlite3
import hashlib
import hmac
import secrets
import time
import threading
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

# ==========================================
# INFINIX SHOPEE CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

DB_FILE = Path(os.environ.get(
    "INFINIX_DB_PATH",
    str(BASE_DIR / "infinix_shopee.db")
))

EXCEL_FILE = Path(os.environ.get(
    "INFINIX_EXCEL_PATH",
    str(BASE_DIR / "infinix_shopee_database.xlsx")
))

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Rockstar")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "").rstrip("/")

PORT = int(os.environ.get("PORT", "8000"))
SESSION_SECONDS = 7 * 24 * 60 * 60
PBKDF2_ROUNDS = 310000

LOCK = threading.RLock()

DB_FILE.parent.mkdir(parents=True, exist_ok=True)
EXCEL_FILE.parent.mkdir(parents=True, exist_ok=True)

# ==========================================
# DATABASE
# ==========================================

def connect_db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE COLLATE NOCASE NOT NULL,
            email TEXT UNIQUE COLLATE NOCASE NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_state (
            storage_key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_state (
            user_id INTEGER NOT NULL,
            storage_key TEXT NOT NULL,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(user_id, storage_key)
        )
    """)

    return conn


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ==========================================
# PASSWORD SECURITY
# ==========================================

def password_digest(password, salt=None):
    salt = salt or secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ROUNDS
    )

    return salt.hex(), digest.hex()


def verify_password(password, salt, expected):
    try:
        _, digest = password_digest(
            password,
            bytes.fromhex(salt)
        )

        return hmac.compare_digest(digest, expected)

    except (ValueError, TypeError):
        return False


def token_digest(token):
    return hmac.new(
        SESSION_SECRET.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


# ==========================================
# USERS AND SESSIONS
# ==========================================

def public_user(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "createdAt": row["created_at"]
    }


def create_admin():
    if not ADMIN_USERNAME or len(ADMIN_PASSWORD) < 12:
        raise RuntimeError(
            "Configure ADMIN_USERNAME and ADMIN_PASSWORD "
            "in Render environment variables."
        )

    salt, digest = password_digest(ADMIN_PASSWORD)

    with connect_db() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE role='admin' LIMIT 1"
        ).fetchone()

        if row:
            conn.execute("""
                UPDATE users
                SET username=?, salt=?, password_hash=?
                WHERE id=?
            """, (
                ADMIN_USERNAME,
                salt,
                digest,
                row["id"]
            ))
        else:
            conn.execute("""
                INSERT INTO users
                (username,email,name,role,salt,password_hash,created_at)
                VALUES(?,?,?,?,?,?,?)
            """, (
                ADMIN_USERNAME,
                "admin@infinix.invalid",
                "Administrator",
                "admin",
                salt,
                digest,
                now_iso()
            ))


def issue_session(user_id):
    token = secrets.token_urlsafe(40)

    with connect_db() as conn:
        conn.execute("""
            INSERT INTO sessions(token_hash,user_id,expires_at)
            VALUES(?,?,?)
        """, (
            token_digest(token),
            user_id,
            int(time.time()) + SESSION_SECONDS
        ))

        conn.execute(
            "DELETE FROM sessions WHERE expires_at <= ?",
            (int(time.time()),)
        )

    return token


def get_user(token):
    if not token:
        return None

    with connect_db() as conn:
        row = conn.execute("""
            SELECT users.*
            FROM sessions
            JOIN users ON users.id=sessions.user_id
            WHERE sessions.token_hash=?
            AND sessions.expires_at>?
        """, (
            token_digest(token),
            int(time.time())
        )).fetchone()

    return public_user(row) if row else None


# ==========================================
# APPLICATION STATE
# ==========================================

PRIVATE_KEYS = {
    "shoply-cart",
    "shoply-wish",
    "infinix-delivery-locations",
    "infinix-applied-voucher",
    "infinix-theme",
    "infinix-country"
}

PUBLIC_KEYS = {
    "infinix-products",
    "infinix-vouchers",
    "infinix-promotion-settings",
    "infinix-plus-plan-prices"
}

ADMIN_KEYS = {
    "infinix-vouchers",
    "infinix-promotion-settings",
    "infinix-plus-plan-prices",
    "infinix-plus-members",
    "infinix-activity-log"
}


def read_global():
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT storage_key,value_json FROM app_state"
        ).fetchall()

    return {r["storage_key"]: r["value_json"] for r in rows}


def get_visible_state(user):
    global_state = read_global()
    result = {}

    if not user:
        allowed = PUBLIC_KEYS

    elif user["role"] == "admin":
        allowed = set(global_state)

    else:
        allowed = PUBLIC_KEYS | {"infinix-orders"}

    for key in allowed:
        if key in global_state:
            result[key] = global_state[key]

    if not user:
        return result

    with connect_db() as conn:
        private = conn.execute("""
            SELECT storage_key,value_json
            FROM user_state
            WHERE user_id=?
        """, (user["id"],)).fetchall()

    for row in private:
        result[row["storage_key"]] = row["value_json"]

    if user["role"] == "admin":
        with connect_db() as conn:
            accounts = conn.execute(
                "SELECT * FROM users ORDER BY created_at"
            ).fetchall()

        result["infinix-accounts"] = json.dumps(
            [public_user(a) for a in accounts]
        )

    return result


def save_state(payload, user):
    if not isinstance(payload, dict) or len(payload) > 100:
        raise ValueError("Invalid state")

    timestamp = now_iso()

    with connect_db() as conn:
        for key, value in payload.items():

            if not isinstance(key, str):
                continue

            if not isinstance(value, str) or len(value) > 2000000:
                continue

            if key == "infinix-accounts":
                continue

            if key in PRIVATE_KEYS:
                conn.execute("""
                    INSERT INTO user_state
                    (user_id,storage_key,value_json,updated_at)
                    VALUES(?,?,?,?)
                    ON CONFLICT(user_id,storage_key)
                    DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=excluded.updated_at
                """, (
                    user["id"],
                    key,
                    value,
                    timestamp
                ))

            elif user["role"] == "admin":
                conn.execute("""
                    INSERT INTO app_state
                    (storage_key,value_json,updated_at)
                    VALUES(?,?,?)
                    ON CONFLICT(storage_key)
                    DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=excluded.updated_at
                """, (key, value, timestamp))


# ==========================================
# EXCEL DATABASE EXPORT
# ==========================================

def export_excel():
    with LOCK:
        book = Workbook()

        sheet = book.active
        sheet.title = "App Data"

        sheet.append([
            "Data Key",
            "Saved Data",
            "Updated At"
        ])

        with connect_db() as conn:
            states = conn.execute(
                "SELECT * FROM app_state"
            ).fetchall()

            users = conn.execute("""
                SELECT username,email,name,role,created_at
                FROM users
            """).fetchall()

        for row in states:
            sheet.append([
                row["storage_key"],
                row["value_json"],
                row["updated_at"]
            ])

        users_sheet = book.create_sheet("Users")

        users_sheet.append([
            "Username",
            "Email",
            "Name",
            "Role",
            "Created At"
        ])

        for row in users:
            users_sheet.append(list(row))

        for ws in book.worksheets:
            ws.freeze_panes = "A2"

            for cell in ws[1]:
                cell.font = Font(
                    bold=True,
                    color="FFFFFF"
                )
                cell.fill = PatternFill(
                    "solid",
                    fgColor="155E4B"
                )

            for column in ws.columns:
                width = max(
                    len(str(cell.value or ""))
                    for cell in column
                )
                ws.column_dimensions[
                    column[0].column_letter
                ].width = min(max(width + 2, 14), 45)

        temp = EXCEL_FILE.with_suffix(".tmp.xlsx")
        book.save(temp)
        os.replace(temp, EXCEL_FILE)


# ==========================================
# HTTP HANDLER
# ==========================================

class ShopHandler(BaseHTTPRequestHandler):

    def send_json(self, status, data, cookie=None, clear=False):
        body = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")

        if FRONTEND_ORIGIN:
            self.send_header(
                "Access-Control-Allow-Origin",
                FRONTEND_ORIGIN
            )
            self.send_header(
                "Access-Control-Allow-Credentials",
                "true"
            )
            self.send_header(
                "Vary",
                "Origin"
            )

        if cookie:
            self.send_header(
                "Set-Cookie",
                "infinix_session=" + cookie +
                "; Path=/; HttpOnly; Secure; SameSite=None; Max-Age=" +
                str(SESSION_SECONDS)
            )

        if clear:
            self.send_header(
                "Set-Cookie",
                "infinix_session=; Path=/; HttpOnly; Secure; SameSite=None; Max-Age=0"
            )

        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)

        if FRONTEND_ORIGIN:
            self.send_header(
                "Access-Control-Allow-Origin",
                FRONTEND_ORIGIN
            )
            self.send_header(
                "Access-Control-Allow-Credentials",
                "true"
            )
            self.send_header(
                "Access-Control-Allow-Methods",
                "GET, POST, OPTIONS"
            )
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type"
            )
            self.send_header("Vary", "Origin")

        self.end_headers()

    def body_json(self):
        length = int(self.headers.get("Content-Length", "0"))

        if length < 1 or length > 2000000:
            raise ValueError("Invalid request size")

        return json.loads(self.rfile.read(length))

    def cookie_token(self):
        for item in self.headers.get("Cookie", "").split(";"):
            name, sep, value = item.strip().partition("=")

            if sep and name == "infinix_session":
                return value

        return ""

    def current_user(self):
        return get_user(self.cookie_token())

    def do_GET(self):
        path = urlsplit(self.path).path

        if path == "/api/health":
            self.send_json(200, {"ok": True})
            return

        if path == "/api/session":
            self.send_json(
                200,
                {"user": self.current_user()}
            )
            return

        if path == "/api/state":
            self.send_json(
                200,
                get_visible_state(self.current_user())
            )
            return

        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlsplit(self.path).path

        try:
            data = self.body_json()

            if not isinstance(data, dict):
                raise ValueError("Invalid request")

            if path == "/api/register":
                username = str(data.get("username", "")).strip()
                email = str(data.get("email", "")).strip().lower()
                name = str(data.get("name", "")).strip()
                password = str(data.get("password", ""))
                role = str(data.get("role", ""))

                if not 3 <= len(username) <= 32:
                    raise ValueError("Invalid username")

                if not username.replace("_", "").isalnum():
                    raise ValueError("Invalid username")

                if "@" not in email or len(email) > 254:
                    raise ValueError("Enter a valid email")

                if not name or len(name) > 100:
                    raise ValueError("Enter a valid name")

                if len(password) < 8 or len(password) > 200:
                    raise ValueError("Password must be at least 8 characters")

                if role not in ("customer", "shopkeeper"):
                    raise ValueError("Invalid account type")

                if username.casefold() == ADMIN_USERNAME.casefold():
                    raise ValueError("Username reserved")

                salt, digest = password_digest(password)

                with connect_db() as conn:
                    cur = conn.execute("""
                        INSERT INTO users
                        (username,email,name,role,salt,password_hash,created_at)
                        VALUES(?,?,?,?,?,?,?)
                    """, (
                        username,
                        email,
                        name,
                        role,
                        salt,
                        digest,
                        now_iso()
                    ))

                    uid = cur.lastrowid

                token = issue_session(uid)

                export_excel()

                self.send_json(
                    201,
                    {"user": self.get_user_for_token(token)},
                    cookie=token
                )
                return

            if path == "/api/login":
                identifier = str(data.get("identifier", "")).strip()
                password = str(data.get("password", ""))

                if not identifier or not password:
                    raise ValueError("Enter your login details")

                with connect_db() as conn:
                    row = conn.execute("""
                        SELECT * FROM users
                        WHERE username=? COLLATE NOCASE
                        OR email=? COLLATE NOCASE
                    """, (identifier, identifier)).fetchone()

                if not row or not verify_password(
                    password,
                    row["salt"],
                    row["password_hash"]
                ):
                    self.send_json(
                        401,
                        {"error": "Invalid username or password"}
                    )
                    return

                token = issue_session(row["id"])

                self.send_json(
                    200,
                    {"user": self.get_user_for_token(token)},
                    cookie=token
                )
                return

            if path == "/api/logout":
                token = self.cookie_token()

                with connect_db() as conn:
                    conn.execute(
                        "DELETE FROM sessions WHERE token_hash=?",
                        (token_digest(token),)
                    )

                self.send_json(
                    200,
                    {"ok": True},
                    clear=True
                )
                return

            if path == "/api/state":
                user = self.current_user()

                if not user:
                    self.send_json(401, {"error": "Sign in required"})
                    return

                save_state(data, user)
                export_excel()

                self.send_json(200, {"saved": True})
                return

            if path == "/api/users/delete":
                user = self.current_user()

                if not user or user["role"] != "admin":
                    self.send_json(
                        403,
                        {"error": "Administrator access required"}
                    )
                    return

                username = str(data.get("username", "")).strip()

                with connect_db() as conn:
                    target = conn.execute("""
                        SELECT id,role FROM users
                        WHERE username=? COLLATE NOCASE
                    """, (username,)).fetchone()

                    if not target or target["role"] == "admin":
                        self.send_json(404, {"error": "User not found"})
                        return

                    conn.execute(
                        "DELETE FROM sessions WHERE user_id=?",
                        (target["id"],)
                    )

                    conn.execute(
                        "DELETE FROM user_state WHERE user_id=?",
                        (target["id"],)
                    )

                    conn.execute(
                        "DELETE FROM users WHERE id=?",
                        (target["id"],)
                    )

                export_excel()
                self.send_json(200, {"deleted": True})
                return

            self.send_json(404, {"error": "Not found"})

        except sqlite3.IntegrityError:
            self.send_json(
                409,
                {"error": "Username or email already exists"}
            )

        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})

        except Exception as error:
            print("SERVER ERROR:", repr(error))
            self.send_json(
                500,
                {"error": "Server could not complete the request"}
            )

    def get_user_for_token(self, token):
        return get_user(token)


# ==========================================
# START SERVER
# ==========================================

if __name__ == "__main__":

    if len(SESSION_SECRET) < 32:
        if os.environ.get("RENDER"):
            raise RuntimeError(
                "Set SESSION_SECRET in Render environment variables"
            )

        SESSION_SECRET = secrets.token_urlsafe(48)

    connect_db().close()
    create_admin()
    export_excel()

    print("====================================")
    print("INFINIX SHOPEE BACKEND STARTED")
    print("Database:", DB_FILE)
    print("Excel:", EXCEL_FILE)
    print("Port:", PORT)
    print("====================================")

    server = ThreadingHTTPServer(
        ("0.0.0.0", PORT),
        ShopHandler
    )

    server.serve_forever()
