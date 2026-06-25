# API reference

The canonical endpoint catalog lives in the repository root:

**[`API_REFERENCE.md`](../../API_REFERENCE.md)**

Interactive docs (development only): `http://localhost:8000/api/docs`

## Quick links

| Area | Endpoints |
|------|-----------|
| Health / stats | `GET /api/health`, `/api/stats` |
| CVEs | `GET /api/cves`, `GET /api/cves/{id}`, sub-routes |
| IOC | `POST /api/ioc/lookup` |
| Refresh | `POST /api/refresh`, `/api/refresh/nvd`, … |
| Auth | `/api/auth/setup`, `/api/auth/login`, … |
| Admin | `/api/admin/*` |

> **Note:** `API_REFERENCE.md` auth section may lag — app login is shipped; see [PRODUCT_STATUS.md](../PRODUCT_STATUS.md).
