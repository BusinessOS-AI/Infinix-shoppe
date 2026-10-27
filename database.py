"""
Infinix Shopee backend
----------------------
A small JSON API for the Infinix Shopee storefront.

Render settings:
  Build command: pip install -r requirements.txt
  Start command: python database.py

Environment variables recommended on Render:
  FRONTEND_ORIGIN=https://infinix-shoppe.onrender.com
  SESSION_SECRET=<a random secret of at least 32 characters>
  ADMIN_USERNAME=Rockstar
  ADMIN_PASSWORD=<set a strong private password>
  INFINIX_DB_PATH=/var/data/infinix_shopee.db   (only if a persistent disk is mounted)
  INFINIX_EXCEL_PATH=/var/data/Infinix_Shopee_Database.xlsx

Important:
- SQLite is the live database. The Excel workbook is a readable export/backup.
- If you use a Render persistent disk, mount it at /var/data and use the paths above.
- Set FRONTEND_ORIGIN to the exact origin of your deployed Static Site.
"""

from __future__ import annotations

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
    from openpyxl import Workbook, load_workbook
except ImportError:
    Workbook = None
    load_workbook = None

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8000"))
DB_PATH = Path(os.environ.get("INFINIX_DB_PATH", str(ROOT / "infinix_shopee.db")))
EXCEL_PATH = Path(os.environ.get("INFINIX_EXCEL_PATH", str(ROOT / "Infinix_Shopee_Database.xlsx")))
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "https://infinix-shoppe.onrender.com").rstrip("/")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Rockstar").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

SESSION_COOKIE = "infinix_session"
SESSION_DAYS = 7
MAX_BODY_BYTES = 2 * 1024 * 1024


def ensure_configuration() -> None:
    if not SESSION_SECRET:
        # Local development convenience. Set a stable secret in Render.
        generated = secrets.token_urlsafe(48)
        os.environ["SESSION_SECRET"] = generated
        globals()["SESSION_SECRET"] = generated
        print("WARNING: SESSION_SECRET was generated for this run. Set it in Render for stable sessions.")
    if len(SESSION_SECRET) < 32:
        raise RuntimeError("SESSION_SECRET must be at least 32 characters.")
    if not ADMIN_PASSWORD:
        # Avoid silently making an insecure production admin account.
        if os.environ.get("RENDER"):
            raise RuntimeError("Set ADMIN_PASSWORD in Render Environment variables.")
        print("WARNING: ADMIN_PASSWORD is not set. Admin login will be unavailable until you set it.")


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                state_key TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_state (
                username TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                email TEXT UNIQUE COLLATE NOCASE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'customer',
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                username TEXT NOT NULL COLLATE NOCASE,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE
            );
            """
        )
        db.execute(
            "INSERT OR IGNORE INTO app_state(state_key, state_json, updated_at) VALUES(?, ?, ?)",
            ("main", "{}", time.time()),
        )
        db.commit()


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return salt.hex(), digest.hex()


def password_matches(password: str, salt_hex: str, digest_hex: str) -> bool:
    _, candidate = hash_password(password, salt_hex)
    return hmac.compare_digest(candidate, digest_hex)


def token_digest(token: str) -> str:
    return hashlib.sha256((SESSION_SECRET + token).encode("utf-8")).hexdigest()


def safe_user(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "createdAt": row["created_at"],
    }


def get_cookie_token(handler: BaseHTTPRequestHandler) -> str | None:
    raw = handler.headers.get("Cookie", "")
    cookie = SimpleCookie()
    try:
        cookie.load(raw)
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else None
    except Exception:
        return None


def current_user(handler: BaseHTTPRequestHandler) -> dict | None:
    token = get_cookie_token(handler)
    if not token:
        return None
    now = time.time()
    with connect_db() as db:
        row = db.execute(
            """SELECT u.* FROM sessions s
               JOIN users u ON u.username = s.username COLLATE NOCASE
               WHERE s.token_hash = ? AND s.expires_at > ?""",
            (token_digest(token), now),
        ).fetchone()
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        db.commit()
    return safe_user(row)


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(36)
    now = time.time()
    with connect_db() as db:
        db.execute(
            "INSERT INTO sessions(token_hash, username, expires_at, created_at) VALUES(?, ?, ?, ?)",
            (token_digest(token), username, now + SESSION_DAYS * 86400, now),
        )
        db.commit()
    return token


def delete_session(handler: BaseHTTPRequestHandler) -> None:
    token = get_cookie_token(handler)
    if token:
        with connect_db() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_digest(token),))
            db.commit()


def export_excel() -> None:
    """Export current app state and user records without exporting password hashes."""
    if Workbook is None:
        return
    EXCEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as db:
        state_rows = db.execute("SELECT state_key, state_json, updated_at FROM app_state").fetchall()
        user_state_rows = db.execute("SELECT username, state_json, updated_at FROM user_state").fetchall()
        user_rows = db.execute(
            "SELECT username, email, role, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "App State"
    ws.append(["State Key", "JSON Data", "Updated At"])
    for row in state_rows:
        ws.append([row["state_key"], row["state_json"], row["updated_at"]])

    ws2 = wb.create_sheet("User State")
    ws2.append(["Username", "JSON Data", "Updated At"])
    for row in user_state_rows:
        ws2.append([row["username"], row["state_json"], row["updated_at"]])

    ws3 = wb.create_sheet("Users")
    ws3.append(["Username", "Email", "Role", "Created At"])
    for row in user_rows:
        ws3.append([row["username"], row["email"], row["role"], row["created_at"]])

    for sheet in wb.worksheets:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column in sheet.columns:
            values = [len(str(cell.value or "")) for cell in column]
            letter = column[0].column_letter
            sheet.column_dimensions[letter].width = min(max(max(values, default=10) + 2, 12), 60)
    temp_path = EXCEL_PATH.with_suffix(".tmp.xlsx")
    wb.save(temp_path)
    temp_path.replace(EXCEL_PATH)


class ShopHandler(BaseHTTPRequestHandler):
    server_version = "InfinixShopeeAPI/1.0"

    def log_message(self, fmt: str, *args) -> None:
        # Keep useful request logs on Render without noisy tracebacks.
        print("%s - %s" % (self.address_string(), fmt % args))

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True  # local scripts/health checks may omit Origin
        return origin.rstrip("/") == FRONTEND_ORIGIN

    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin and origin.rstrip("/") == FRONTEND_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", FRONTEND_ORIGIN)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")

    def _send_json(self, status: int, payload: dict, extra_headers: dict | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
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

    def _set_session_cookie(self, token: str) -> str:
        # Cross-origin frontend/backend deployments need SameSite=None; Secure.
        return (
            f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; Secure; SameSite=None; "
            f"Max-Age={SESSION_DAYS * 86400}"
        )

    def _clear_session_cookie(self) -> str:
        return f"{SESSION_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=None; Max-Age=0"

    def do_OPTIONS(self) -> None:
        if not self._origin_allowed():
            self._send_json(403, {"ok": False, "error": "Origin not allowed."})
            return
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/health":
            self._send_json(200, {"ok": True, "service": "infinix-shopee-backend"})
            return

        if path.startswith("/api/"):
            if not self._origin_allowed():
                self._send_json(403, {"ok": False, "error": "Origin not allowed. Check FRONTEND_ORIGIN."})
                return

            if path == "/api/session":
                user = current_user(self)
                self._send_json(200, {"ok": True, "user": user, "authenticated": user is not None})
                return

            if path == "/api/state":
                user = current_user(self)
                with connect_db() as db:
                    row = db.execute(
                        "SELECT state_json FROM app_state WHERE state_key = 'main'"
                    ).fetchone()
                    app_state = json.loads(row["state_json"]) if row else {}
                    user_row = None
                    if user:
                        user_row = db.execute(
                            "SELECT state_json FROM user_state WHERE username = ? COLLATE NOCASE",
                            (user["username"],),
                        ).fetchone()
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "state": app_state,
                        "userState": json.loads(user_row["state_json"]) if user_row else {},
                        "user": user,
                    },
                )
                return

            self._send_json(404, {"ok": False, "error": "API route not found."})
            return

        # Serve frontend files too when the backend folder contains them.
        relative = unquote(path.lstrip("/")) or "index.html"
        requested = (ROOT / relative).resolve()
        try:
            requested.relative_to(ROOT.resolve())
        except ValueError:
            self.send_error(403)
            return
        if not requested.is_file():
            self.send_error(404)
            return
        content_type = {
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
        }.get(requested.suffix.lower(), "application/octet-stream")
        body = requested.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            self._send_json(404, {"ok": False, "error": "Route not found."})
            return
        if not self._origin_allowed():
            self._send_json(403, {"ok": False, "error": "Origin not allowed. Check FRONTEND_ORIGIN."})
            return

        try:
            data = self._read_json()
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return

        if path == "/api/register":
            username = str(data.get("username", "")).strip()
            email = str(data.get("email", "")).strip().lower() or None
            password = str(data.get("password", ""))
            if len(username) < 3 or len(username) > 40:
                self._send_json(400, {"ok": False, "error": "Username must be 3–40 characters."})
                return
            if not password or len(password) < 8:
                self._send_json(400, {"ok": False, "error": "Password must be at least 8 characters."})
                return
            if email and ("@" not in email or len(email) > 254):
                self._send_json(400, {"ok": False, "error": "Enter a valid email address."})
                return
            salt, digest = hash_password(password)
            now = time.time()
            try:
                with connect_db() as db:
                    db.execute(
                        """INSERT INTO users(username, email, password_salt, password_hash, role, created_at)
                           VALUES(?, ?, ?, ?, 'customer', ?)""",
                        (username, email, salt, digest, now),
                    )
                    db.execute(
                        "INSERT OR IGNORE INTO user_state(username, state_json, updated_at) VALUES(?, '{}', ?)",
                        (username, now),
                    )
                    db.commit()
            except sqlite3.IntegrityError:
                self._send_json(409, {"ok": False, "error": "That username or email is already registered."})
                return
            token = create_session(username)
            export_excel()
            self._send_json(
                201,
                {"ok": True, "user": {"username": username, "email": email, "role": "customer"}},
                {"Set-Cookie": self._set_session_cookie(token)},
            )
            return

        if path == "/api/login":
            username = str(data.get("username", data.get("email", ""))).strip()
            password = str(data.get("password", ""))
            if not username or not password:
                self._send_json(400, {"ok": False, "error": "Enter your username/email and password."})
                return

            # The admin credentials are server-side only; never send the password to the browser.
            if (
                ADMIN_PASSWORD
                and username.casefold() == ADMIN_USERNAME.casefold()
                and hmac.compare_digest(password, ADMIN_PASSWORD)
            ):
                with connect_db() as db:
                    row = db.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (ADMIN_USERNAME,)).fetchone()
                    if row is None:
                        salt, digest = hash_password(ADMIN_PASSWORD)
                        db.execute(
                            """INSERT INTO users(username, email, password_salt, password_hash, role, created_at)
                               VALUES(?, NULL, ?, ?, 'admin', ?)""",
                            (ADMIN_USERNAME, salt, digest, time.time()),
                        )
                        db.commit()
                token = create_session(ADMIN_USERNAME)
                with connect_db() as db:
                    row = db.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (ADMIN_USERNAME,)).fetchone()
                    if row and row["role"] != "admin":
                        db.execute("UPDATE users SET role='admin' WHERE username = ? COLLATE NOCASE", (ADMIN_USERNAME,))
                        db.commit()
                export_excel()
                self._send_json(
                    200,
                    {"ok": True, "user": {"username": ADMIN_USERNAME, "email": None, "role": "admin"}},
                    {"Set-Cookie": self._set_session_cookie(token)},
                )
                return

            with connect_db() as db:
                row = db.execute(
                    "SELECT * FROM users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE LIMIT 1",
                    (username, username),
                ).fetchone()
            if row is None or not password_matches(password, row["password_salt"], row["password_hash"]):
                self._send_json(401, {"ok": False, "error": "Incorrect username/email or password."})
                return
            token = create_session(row["username"])
            self._send_json(
                200,
                {"ok": True, "user": safe_user(row)},
                {"Set-Cookie": self._set_session_cookie(token)},
            )
            return

        if path == "/api/logout":
            delete_session(self)
            self._send_json(200, {"ok": True, "message": "Signed out."}, {"Set-Cookie": self._clear_session_cookie()})
            return

        if path == "/api/state":
            user = current_user(self)
            # Preserve storefront state support; optionally require login for user-specific state.
            state = data.get("state", data.get("appState", {}))
            if not isinstance(state, dict):
                self._send_json(400, {"ok": False, "error": "State must be a JSON object."})
                return
            now = time.time()
            with connect_db() as db:
                db.execute(
                    "INSERT INTO app_state(state_key, state_json, updated_at) VALUES('main', ?, ?) "
                    "ON CONFLICT(state_key) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at",
                    (json.dumps(state, ensure_ascii=False), now),
                )
                user_state = data.get("userState")
                if user and isinstance(user_state, dict):
                    db.execute(
                        "INSERT INTO user_state(username, state_json, updated_at) VALUES(?, ?, ?) "
                        "ON CONFLICT(username) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at",
                        (user["username"], json.dumps(user_state, ensure_ascii=False), now),
                    )
                db.commit()
            export_excel()
            self._send_json(200, {"ok": True, "state": state})
            return

        if path == "/api/users/delete":
            user = current_user(self)
            if not user or user["role"] != "admin":
                self._send_json(403, {"ok": False, "error": "Administrator access required."})
                return
            target = str(data.get("username", "")).strip()
            if not target or target.casefold() == ADMIN_USERNAME.casefold():
                self._send_json(400, {"ok": False, "error": "A valid non-admin username is required."})
                return
            with connect_db() as db:
                db.execute("DELETE FROM users WHERE username = ? COLLATE NOCASE", (target,))
                db.execute("DELETE FROM user_state WHERE username = ? COLLATE NOCASE", (target,))
                db.commit()
            export_excel()
            self._send_json(200, {"ok": True})
            return

        self._send_json(404, {"ok": False, "error": "API route not found."})


def main() -> None:
    ensure_configuration()
    init_db()
    try:
        export_excel()
    except Exception as exc:
        print(f"Excel export warning: {exc}")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), ShopHandler)
    print(f"Infinix Shopee backend listening on 0.0.0.0:{PORT}")
    print(f"Database: {DB_PATH}")
    print(f"Excel export: {EXCEL_PATH}")
    print(f"Allowed frontend origin: {FRONTEND_ORIGIN}")
    server.serve_forever()


if __name__ == "__main__":
    main()
