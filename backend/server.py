# Supervisor shim: expose FastAPI `app` from main.py.
# Emergent supervisor is fixed to `uvicorn server:app`; BRIEFR's entry is main.py.
from main import app  # noqa: F401
