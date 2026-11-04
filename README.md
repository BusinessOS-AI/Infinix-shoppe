# Infinix Shopee — all current source files

This bundle contains the latest source files you shared in this conversation:
- `index.html` — storefront structure
- `style.css` — storefront styling
- `script.js` — storefront behaviour and client-side dashboards
- `database.py` — Python backend API
- `requirements.txt` — Python dependency list

## Where to use the files

### Frontend (Render Static Site)
Upload/replace `index.html`, `style.css`, and `script.js` in your frontend repository, preserving the existing filenames.

### Backend (Render Web Service)
Upload/replace `database.py` and `requirements.txt` in your backend repository. The backend service must use its existing Python start command and environment variables.

## Important notes

- Keep the frontend and backend as separate Render services, as in your current setup.
- Set `FRONTEND_ORIGIN` to `https://infinix-shoppe.onrender.com` on the backend.
- Set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and a strong `SESSION_SECRET` in Render environment variables. Do not put admin credentials in `script.js`.
- The current JavaScript still stores many catalog, cart, order, voucher, and dashboard values in browser `localStorage`. This bundle collects your current code; it does **not** by itself turn every dashboard feature into shared, server-authorized data. Do not treat client-side role checks as security.
- Back up the current deployed files before replacing anything.
