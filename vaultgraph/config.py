"""All settings come from environment variables (12-factor). A local .env file is loaded if present
(never overrides real environment variables). ENV=production enforces strict startup checks."""
import os
import secrets
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split(" #")[0].strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


_load_dotenv()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


ENV = os.getenv("ENV", "development").strip().lower()
IS_PROD = ENV == "production"
_WEAK = {"", "dev-secret-change-me", "change-me", "secret", "change-me-to-a-long-random-string"}


def _jwt_secret() -> str:
    s = os.getenv("JWT_SECRET", "")
    if IS_PROD:
        if s in _WEAK or len(s) < 32:
            raise RuntimeError(
                "ENV=production requires JWT_SECRET to be set to a random string of at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")
        return s
    # Development: random per-process secret if unset (sessions reset on restart; no default secret ever ships).
    return s if len(s) >= 32 else secrets.token_urlsafe(48)


JWT_SECRET = _jwt_secret()
JWT_TTL_MIN = int(os.getenv("JWT_TTL_MIN", "60"))

DB_PATH = os.getenv("VAULTGRAPH_DB", "vaultgraph.db")

# LLM: "auto" = Groq if GROQ_API_KEY is set, else offline mock. "groq" requires a key. "mock" forces offline.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
# llama-3.3-70b-versatile was shut down by Groq on 2026-08-16; Groq's recommended replacements are
# openai/gpt-oss-120b and qwen/qwen3.6-27b. /status verifies the configured model against Groq's live model list.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()

EMBEDDER = os.getenv("EMBEDDER", "hash").strip().lower()  # "hash" (offline default) or "bge" (optional extra)

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024)))
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "100"))

ALLOW_REGISTRATION = _bool("ALLOW_REGISTRATION", True)
MAX_ORGS = int(os.getenv("MAX_ORGS", "200"))  # protects a small free instance from sign-up abuse

# Public sandbox: seeds the fictional Northwind org with shared demo accounts. Never enable for real data.
DEMO_MODE = _bool("DEMO_MODE", False)
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "VaultGraph-Demo-2026")

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]  # empty = same-origin only
FRONTEND_DIST = os.getenv("FRONTEND_DIST", str(Path(__file__).resolve().parent.parent / "frontend" / "dist"))
RATE_LOGIN_PER_MIN = int(os.getenv("RATE_LOGIN_PER_MIN", "10"))
RATE_QUERY_PER_MIN = int(os.getenv("RATE_QUERY_PER_MIN", "30"))
