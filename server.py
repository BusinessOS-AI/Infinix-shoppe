        try:
            self.require_same_origin()
            data = self.body_json()
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            if path == "/api/register":
                username = str(data.get("username", "")).strip()
                email = str(data.get("email", "")).strip().lower()
                name = str(data.get("name", "")).strip()
                password = str(data.get("password", ""))
                role = str(data.get("role", ""))
                if len(username) < 3 or len(username) > 32 or not username.replace("_", "").isalnum():
                    raise ValueError("Username must be 3–32 letters, numbers, or underscores")
                if len(email) > 254 or "@" not in email or not name or len(name) > 100:
                    raise ValueError("Enter a valid email and name")
                if len(password) < 8 or len(password) > 200:
                    raise ValueError("Password must be at least 8 characters")
                if role not in {"customer", "shopkeeper"}:
                    raise ValueError("Choose customer or seller")
                if username.casefold() == ADMIN_USERNAME.casefold() and ADMIN_USERNAME:
                    raise ValueError("That username is reserved")
                salt, digest = password_digest(password)
                try:
                    with connect_db() as conn:
                        cur = conn.execute("INSERT INTO users(username,email,name,role,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?)", (username, email, name, role, salt, digest, now_iso()))
                        uid = cur.lastrowid
                except sqlite3.IntegrityError:
                    self.send_json(409, {"error": "That username or email is already registered"}); return
                user = public_user({"id": uid, "username": username, "email": email, "name": name, "role": role, "created_at": now_iso()})
                token = issue_session(uid)
                export_excel(read_global())
                self.send_json(201, {"user": user}, cookie=token)
            elif path == "/api/login":
                identifier = str(data.get("identifier", "")).strip()
                password = str(data.get("password", ""))
                if not identifier or not password:
                    raise ValueError("Enter your username or email and password")
                if ADMIN_USERNAME and identifier.casefold() == ADMIN_USERNAME.casefold() and ADMIN_PASSWORD and hmac.compare_digest(password, ADMIN_PASSWORD):
                    salt, digest = password_digest(ADMIN_PASSWORD)
                    with connect_db() as conn:
                        row = conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
                        if row:
                            uid = row["id"]
                            conn.execute("UPDATE users SET username=?,email=?,name=?,salt=?,password_hash=? WHERE id=?", (ADMIN_USERNAME, "admin@infinix.invalid", "Administrator", salt, digest, uid))
                        else:
                            uid = conn.execute("INSERT INTO users(username,email,name,role,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?)", (ADMIN_USERNAME, "admin@infinix.invalid", "Administrator", "admin", salt, digest, now_iso())).lastrowid
                    token = issue_session(uid)
                    user = get_user_by_session(token)
                    export_excel(read_global())
                    self.send_json(200, {"user": user}, cookie=token); return
                with connect_db() as conn:
                    row = conn.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE OR email=? COLLATE NOCASE", (identifier, identifier)).fetchone()
                if not row or row["role"] == "admin" or not verify_password(password, row["salt"], row["password_hash"]):
                    self.send_json(401, {"error": "Invalid username or password"}); return
                token = issue_session(row["id"])
                self.send_json(200, {"user": get_user_by_session(token)}, cookie=token)
            elif path == "/api/logout":
                token = self.cookie_token()
                with connect_db() as conn:
                    conn.execute("DELETE FROM sessions WHERE token_hash=?", (token_digest(token),))
                self.send_json(200, {"ok": True}, clear_cookie=True)
            elif path == "/api/state":
                user = self.current_user()
                if not user:
                    self.send_json(401, {"error": "Sign in required"}); return
                apply_state(data, user)
                self.send_json(200, {"saved": True})
            elif path == "/api/users/delete":
                user = self.current_user()
                if not user or user["role"] != "admin":
                    self.send_json(403, {"error": "Administrator access required"}); return
                target = str(data.get("username", "")).strip()
                with connect_db() as conn:
                    victim = conn.execute("SELECT id,role FROM users WHERE username=? COLLATE NOCASE", (target,)).fetchone()
                    if not victim or victim["role"] == "admin":
                        self.send_json(404, {"error": "User not found"}); return
                    conn.execute("DELETE FROM sessions WHERE user_id=?", (victim["id"],))
                    conn.execute("DELETE FROM user_state WHERE user_id=?", (victim["id"],))
                    conn.execute("DELETE FROM users WHERE id=?", (victim["id"],))
                export_excel(read_global())
                self.send_json(200, {"deleted": True})
            else:
                self.send_json(404, {"error": "Not found"})
        except PermissionError as error:
            self.send_json(403, {"error": str(error)})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except Exception:
            self.send_json(500, {"error": "Server could not complete the request"})

    do_PUT = do_POST


if __name__ == "__main__":
    if len(SESSION_SECRET) < 32:
        if os.environ.get("RENDER"):
            raise RuntimeError("Set SESSION_SECRET to a random value at least 32 characters long in Render environment variables")
        SESSION_SECRET = secrets.token_urlsafe(48)
    if os.environ.get("RENDER") and (not ADMIN_USERNAME or len(ADMIN_PASSWORD) < 12):
        raise RuntimeError("Set ADMIN_USERNAME and an ADMIN_PASSWORD of at least 12 characters in Render environment variables")
    connect_db().close()
    export_excel(read_global())
    port = int(os.environ.get("PORT", "8000"))
    ThreadingHTTPServer(("0.0.0.0", port), ShopHandler).serve_forever()
