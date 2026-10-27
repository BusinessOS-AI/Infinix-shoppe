import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None


# =========================
# CONFIGURATION
# =========================

PORT = int(os.environ.get("PORT", "8000"))

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = Path(
    os.environ.get(
        "INFINIX_DB_PATH",
        str(BASE_DIR / "infinix_shopee.db")
    )
)

EXCEL_PATH = Path(
    os.environ.get(
        "INFINIX_EXCEL_PATH",
        str(BASE_DIR / "Infinix_Shopee_Database.xlsx")
    )
)

FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN",
    "https://infinix-shoppe.onrender.com"
).rstrip("/")

SESSION_SECRET = os.environ.get("SESSION_SECRET", "")

if len(SESSION_SECRET) < 32:
    raise RuntimeError(
        "Set SESSION_SECRET in Render environment variables "
        "to a private random value of at least 32 characters."
    )

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Rockstar")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

SESSION_COOKIE = "infinix_session"
SESSION_DURATION = 7 * 24 * 60 * 60


# =========================
# DATABASE INITIALIZATION
# =========================

def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(DB_PATH),
        timeout=30
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'customer',
                created_at INTEGER NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                account_id INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY (account_id)
                    REFERENCES accounts(id)
                    ON DELETE CASCADE
            )
        """)

        db.commit()


# =========================
# PASSWORD SECURITY
# =========================

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        310000
    ).hex()

    return salt, password_hash


def verify_password(password, salt, stored_hash):
    _, calculated_hash = hash_password(password, salt)

    return hmac.compare_digest(
        calculated_hash,
        stored_hash
    )


# =========================
# SESSION HELPERS
# =========================

def hash_session_token(token):
    return hmac.new(
        SESSION_SECRET.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def create_session(account_id):
    token = secrets.token_urlsafe(32)
    token_hash = hash_session_token(token)
    expires_at = int(time.time()) + SESSION_DURATION

    with get_db() as db:
        db.execute(
            """
            INSERT INTO sessions
                (token_hash, account_id, expires_at)
            VALUES (?, ?, ?)
            """,
            (token_hash, account_id, expires_at)
        )
        db.commit()

    return token


def get_session_account(token):
    if not token:
        return None

    token_hash = hash_session_token(token)
    now = int(time.time())

    with get_db() as db:
        row = db.execute(
            """
            SELECT accounts.*
            FROM sessions
            JOIN accounts
                ON accounts.id = sessions.account_id
            WHERE sessions.token_hash = ?
              AND sessions.expires_at > ?
            """,
            (token_hash, now)
        ).fetchone()

    return dict(row) if row else None


# =========================
# EXCEL EXPORT
# =========================

def export_database_to_excel():
    if Workbook is None:
        return

    EXCEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Accounts"

    with get_db() as db:
        rows = db.execute(
            """
            SELECT id, username, email, role, created_at
            FROM accounts
            ORDER BY id
            """
        ).fetchall()

    sheet.append([
        "ID",
        "Username",
        "Email",
        "Role",
        "Created At"
    ])

    for row in rows:
        sheet.append(list(row))

    workbook.save(str(EXCEL_PATH))


if path == "/api/logout":
            delete_session(self)
            self.send_json(
                200,
                {"ok": True, "message": "Signed out."},
                {"Set-Cookie": self.expired_cookie()}
            )
            return


if path == "/api/state":
            user = current_user(self)
            state = data.get("state", data.get("appState", {}))

            if not isinstance(state, dict):
                self.send_json(
                    400,
                    {"ok": False, "error": "State must be a JSON object."}
                )
                return

            now = time.time()

            with connect_db() as db:
                db.execute(
                    """INSERT INTO app_state
                       (state_key, state_json, updated_at)
                       VALUES ('main', ?, ?)
                       ON CONFLICT(state_key) DO UPDATE SET
                       state_json=excluded.state_json,
                       updated_at=excluded.updated_at""",
                    (json.dumps(state, ensure_ascii=False), now)
                )

                user_state = data.get("userState")
                if user and isinstance(user_state, dict):
                    db.execute(
                        """INSERT INTO user_state
                           (username, state_json, updated_at)
                           VALUES (?, ?, ?)
                           ON CONFLICT(username) DO UPDATE SET
                           state_json=excluded.state_json,
                           updated_at=excluded.updated_at""",
                        (
                            user["username"],
                            json.dumps(user_state, ensure_ascii=False),
                            now
                        )
                    )

                db.commit()

            export_excel()
            self.send_json(200, {"ok": True, "state": state})
            return

        if path == "/api/users/delete":
            user = current_user(self)

            if not user or user["role"] != "admin":
                self.send_json(
                    403,
                    {
                        "ok": False,
                        "error": "Administrator access required."
                    }
                )
                return

            target = str(data.get("username", "")).strip()

            if (
                not target
                or target.casefold() == ADMIN_USERNAME.casefold()
            ):
                self.send_json(
                    400,
                    {
                        "ok": False,
                        "error": "A valid non-admin username is required."
                    }
                )
                return

            with connect_db() as db:
                db.execute(
                    "DELETE FROM sessions WHERE username = ? COLLATE NOCASE",
                    (target,)
                )
                db.execute(
                    "DELETE FROM users WHERE username = ? COLLATE NOCASE",
                    (target,)
                )
                db.execute(
                    "DELETE FROM user_state WHERE username = ? COLLATE NOCASE",
                    (target,)
                )
                db.commit()

            export_excel()
            self.send_json(200, {"ok": True})
            return

        self.send_json(
            404, {"ok": False, "error": "API route not found."}
        )


def main():
    ensure_configuration()
    init_db()

    try:
        export_excel()
    except Exception as exc:
        print("Excel export warning:", exc)

    server = ThreadingHTTPServer(
        ("0.0.0.0", PORT),
        ShopHandler
    )

    print("Infinix Shopee backend is running.")
    print("Port:", PORT)
    print("Database:", DB_PATH)
    print("Excel export:", EXCEL_PATH)
    print("Allowed frontend origin:", FRONTEND_ORIGIN)

    server.serve_forever()


if __name__ == "__main__":
    main()
  class ShopHandler(BaseHTTPRequestHandler):
    server_version = "InfinixShopeeAPI/1.0"

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def origin_allowed(self):
        origin = self.headers.get("Origin")
        return not origin or origin.rstrip("/") == FRONTEND_ORIGIN

    def add_cors_headers(self):
        origin = self.headers.get("Origin")

        if origin and origin.rstrip("/") == FRONTEND_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", FRONTEND_ORIGIN)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")

        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, OPTIONS"
        )
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type"
        )
        self.send_header("Cache-Control", "no-store")

    def send_json(self, status, payload, extra_headers=None):
        body = json.dumps(
            payload, ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type", "application/json; charset=utf-8"
        )
        self.send_header("Content-Length", str(len(body)))
        self.add_cors_headers()

        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)

        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid Content-Length.")

        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("Request body is too large.")

        raw = self.rfile.read(length) if length else b"{}"

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Request body must be valid JSON.")

        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object.")

        return data

    def session_cookie(self, token):
        return (
            f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; "
            "Secure; SameSite=None; Max-Age=604800"
        )

    def expired_cookie(self):
        return (
            f"{SESSION_COOKIE}=; Path=/; HttpOnly; "
            "Secure; SameSite=None; Max-Age=0"
        )

    def do_OPTIONS(self):
        if not self.origin_allowed():
            self.send_json(
                403, {"ok": False, "error": "Origin not allowed."}
            )
            return

        self.send_response(204)
        self.add_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/health":
            self.send_json(
                200,
                {"ok": True, "service": "infinix-shopee-backend"}
            )
            return

        if path.startswith("/api/"):
            if not self.origin_allowed():
                self.send_json(
                    403,
                    {
                        "ok": False,
                        "error": (
                            "Origin not allowed. Check FRONTEND_ORIGIN."
                        )
                    }
                )
                return

            if path == "/api/session":
                user = current_user(self)
                self.send_json(
                    200,
                    {
                        "ok": True,
                        "user": user,
                        "authenticated": user is not None
                    }
                )
                return

            if path == "/api/state":
                user = current_user(self)

                with connect_db() as db:
                    row = db.execute(
                        """SELECT state_json FROM app_state
                           WHERE state_key = 'main'"""
                    ).fetchone()

                    app_state = (
                        json.loads(row["state_json"]) if row else {}
                    )

                    user_row = None
                    if user:
                        user_row = db.execute(
                            """SELECT state_json FROM user_state
                               WHERE username = ? COLLATE NOCASE""",
                            (user["username"],)
                        ).fetchone()

                self.send_json(
                    200,
                    {
                        "ok": True,
                        "state": app_state,
                        "userState": (
                            json.loads(user_row["state_json"])
                            if user_row else {}
                        ),
                        "user": user
                    }
                )
                return

            self.send_json(
                404, {"ok": False, "error": "API route not found."}
            )
            return

        relative = unquote(path.lstrip("/")) or "index.html"
        requested = (ROOT / relative).resolve()

        try:
            requested.relative_to(ROOT.resolve())
        except ValueError:
            self.send_error(403)
            return

        if not requested.is_file():
            self.send_error(404, "File not found.")
            return

        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".ico": "image/x-icon",
        }

        body = requested.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            content_types.get(
                requested.suffix.lower(),
                "application/octet-stream"
            )
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path

        if not path.startswith("/api/"):
            self.send_json(
                404, {"ok": False, "error": "Route not found."}
            )
            return

        if not self.origin_allowed():
            self.send_json(
                403,
                {
                    "ok": False,
                    "error": (
                        "Origin not allowed. Check FRONTEND_ORIGIN."
                    )
                }
            )
            return

        try:
            data = self.read_json()
        except ValueError as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
            return

        if path == "/api/register":
            username = str(data.get("username", "")).strip()
            email = str(data.get("email", "")).strip().lower() or None
            password = str(data.get("password", ""))

            if not 3 <= len(username) <= 40:
                self.send_json(
                    400,
                    {
                        "ok": False,
                        "error": "Username must be 3–40 characters."
                    }
                )
                return

            if len(password) < 8:
                self.send_json(
                    400,
                    {
                        "ok": False,
                        "error": "Password must be at least 8 characters."
                    }
                )
                return

            if email and ("@" not in email or len(email) > 254):
                self.send_json(
                    400,
                    {
                        "ok": False,
                        "error": "Enter a valid email address."
                    }
                )
                return

            salt, digest = hash_password(password)
            now = time.time()

            try:
                with connect_db() as db:
                    db.execute(
                        """INSERT INTO users
                           (username, email, password_salt,
                            password_hash, role, created_at)
                           VALUES (?, ?, ?, ?, 'customer', ?)""",
                        (username, email, salt, digest, now)
                    )
                    db.execute(
                        """INSERT OR IGNORE INTO user_state
                           (username, state_json, updated_at)
                           VALUES (?, '{}', ?)""",
                        (username, now)
                    )
                    db.commit()
            except sqlite3.IntegrityError:
                self.send_json(
                    409,
                    {
                        "ok": False,
                        "error": (
                            "That username or email is already registered."
                        )
                    }
                )
                return

            token = create_session(username)
            export_excel()

            self.send_json(
                201,
                {
                    "ok": True,
                    "user": {
                        "username": username,
                        "email": email,
                        "role": "customer"
                    }
                },
                {"Set-Cookie": self.session_cookie(token)}
            )
            return

        if path == "/api/login":
            username = str(
                data.get("username", data.get("email", ""))
            ).strip()
            password = str(data.get("password", ""))

            if not username or not password:
                self.send_json(
                    400,
                    {
                        "ok": False,
                        "error": "Enter your username/email and password."
                    }
                )
                return

            if (
                ADMIN_PASSWORD
                and username.casefold() == ADMIN_USERNAME.casefold()
                and hmac.compare_digest(password, ADMIN_PASSWORD)
            ):
                with connect_db() as db:
                    row = db.execute(
                        """SELECT * FROM users
                           WHERE username = ? COLLATE NOCASE""",
                        (ADMIN_USERNAME,)
                    ).fetchone()

                    if row is None:
                        salt, digest = hash_password(ADMIN_PASSWORD)
                        db.execute(
                            """INSERT INTO users
                               (username, email, password_salt,
                                password_hash, role, created_at)
                               VALUES (?, NULL, ?, ?, 'admin', ?)""",
                            (
                                ADMIN_USERNAME, salt, digest, time.time()
                            )
                        )
                        db.commit()
                    elif row["role"] != "admin":
                        db.execute(
                            """UPDATE users SET role='admin'
                               WHERE username = ? COLLATE NOCASE""",
                            (ADMIN_USERNAME,)
                        )
                        db.commit()

                token = create_session(ADMIN_USERNAME)
                export_excel()

                self.send_json(
                    200,
                    {
                        "ok": True,
                        "user": {
                            "username": ADMIN_USERNAME,
                            "email": None,
                            "role": "admin"
                        }
                    },
                    {"Set-Cookie": self.session_cookie(token)}
                )
                return

            with connect_db() as db:
                row = db.execute(
                    """SELECT * FROM users
                       WHERE username = ? COLLATE NOCASE
                          OR email = ? COLLATE NOCASE LIMIT 1""",
                    (username, username)
                ).fetchone()

            if (
                row is None
                or not password_matches(
                    password, row["password_salt"], row["password_hash"]
                )
            ):
                self.send_json(
                    401,
                    {
                        "ok": False,
                        "error": "Incorrect username/email or password."
                    }
                )
                return

            token = create_session(row["username"])
            self.send_json(
                200,
                {"ok": True, "user": safe_user(row)},
                {"Set-Cookie": self.session_cookie(token)}
            )
            return
                  if path == "/api/logout":
            delete_session(self)
            self.send_json(
                200,
                {"ok": True, "message": "Signed out."},
                {"Set-Cookie": self.expired_cookie()}
            )
            return

        if path == "/api/state":
            user = current_user(self)
            state = data.get("state", data.get("appState", {}))

            if not isinstance(state, dict):
                self.send_json(
                    400,
                    {"ok": False, "error": "State must be a JSON object."}
                )
                return

            now = time.time()

            with connect_db() as db:
                db.execute(
                    """INSERT INTO app_state
                       (state_key, state_json, updated_at)
                       VALUES ('main', ?, ?)
                       ON CONFLICT(state_key) DO UPDATE SET
                       state_json=excluded.state_json,
                       updated_at=excluded.updated_at""",
                    (json.dumps(state, ensure_ascii=False), now)
                )

                user_state = data.get("userState")

                if user and isinstance(user_state, dict):
                    db.execute(
                        """INSERT INTO user_state
                           (username, state_json, updated_at)
                           VALUES (?, ?, ?)
                           ON CONFLICT(username) DO UPDATE SET
                           state_json=excluded.state_json,
                           updated_at=excluded.updated_at""",
                        (
                            user["username"],
                            json.dumps(user_state, ensure_ascii=False),
                            now
                        )
                    )

                db.commit()

            export_excel()
            self.send_json(200, {"ok": True, "state": state})
            return

        if path == "/api/users/delete":
            user = current_user(self)

            if not user or user["role"] != "admin":
                self.send_json(
                    403,
                    {
                        "ok": False,
                        "error": "Administrator access required."
                    }
                )
                return

            target = str(data.get("username", "")).strip()

            if (
                not target
                or target.casefold() == ADMIN_USERNAME.casefold()
            ):
                self.send_json(
                    400,
                    {
                        "ok": False,
                        "error": "A valid non-admin username is required."
                    }
                )
                return

            with connect_db() as db:
                db.execute(
                    "DELETE FROM sessions WHERE username = ? COLLATE NOCASE",
                    (target,)
                )
                db.execute(
                    "DELETE FROM users WHERE username = ? COLLATE NOCASE",
                    (target,)
                )
                db.execute(
                    "DELETE FROM user_state WHERE username = ? COLLATE NOCASE",
                    (target,)
                )
                db.commit()

            export_excel()
            self.send_json(200, {"ok": True})
            return

        self.send_json(
            404,
            {"ok": False, "error": "API route not found."}
        )


def main():
    ensure_configuration()
    init_db()

    try:
        export_excel()
    except Exception as exc:
        print("Excel export warning:", exc)

    server = ThreadingHTTPServer(
        ("0.0.0.0", PORT),
        ShopHandler
    )

    print("Infinix Shopee backend is running.")
    print("Port:", PORT)
    print("Database:", DB_PATH)
    print("Excel export:", EXCEL_PATH)
    print("Allowed frontend origin:", FRONTEND_ORIGIN)

    server.serve_forever()


if __name__ == "__main__":
    main()
