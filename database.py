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
