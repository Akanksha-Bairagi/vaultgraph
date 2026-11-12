"""FastAPI layer: thin HTTP wrapper over service.py (auth, validation, rate limits, error mapping)
plus static hosting of the built React frontend (single deployable app)."""
import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, config, db, demo, service, uploads
from .embeddings import embedder_status
from .errors import AuthError, Forbidden, Invalid, NotFound
from .llm import LLMError, get_llm, llm_status
from .security import create_token

log = logging.getLogger("vaultgraph")


@asynccontextmanager
async def lifespan(app):
    conn = db.connect(config.DB_PATH)  # creates schema / runs migrations on boot
    try:
        if config.DEMO_MODE and demo.seed_if_empty(conn):
            log.info("DEMO_MODE: seeded the Northwind Labs sandbox org")
    finally:
        conn.close()
    yield


app = FastAPI(title="VaultGraph", version=__version__, lifespan=lifespan,
              description="Permission-aware GraphRAG API: ACLs enforced inside retrieval and graph traversal.")
bearer = HTTPBearer(auto_error=False)

if config.CORS_ORIGINS:  # off by default: production is same-origin. Bearer tokens (no cookies) => no credentialed CORS.
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET", "POST", "PUT"],
                       allow_headers=["Authorization", "Content-Type"], allow_credentials=False)

_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")  # Swagger UI loads assets from a CDN, so it gets no strict CSP
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'self' https://huggingface.co https://*.hf.space")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if not request.url.path.startswith(_DOC_PATHS):
        resp.headers.setdefault("Content-Security-Policy", CSP)
    if request.url.path.startswith("/assets/"):
        resp.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    elif request.url.path in ("/", "/index.html") or not request.url.path.startswith(_DOC_PATHS):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


class RateLimiter:
    """Sliding window, in-memory. Single-process only; use Redis for multiple workers (see README)."""
    def __init__(self, limit: int, window_s: int):
        self.limit, self.window, self.hits = limit, window_s, defaultdict(deque)

    def check(self, key: str):
        now, q = time.monotonic(), self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise HTTPException(429, "Too many requests. Please wait a minute and try again.")
        q.append(now)


login_limiter = RateLimiter(config.RATE_LOGIN_PER_MIN, 60)
register_limiter = RateLimiter(5, 60)
query_limiter = RateLimiter(config.RATE_QUERY_PER_MIN, 60)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_conn():
    conn = db.connect(config.DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), conn=Depends(get_conn)):
    if not creds:
        raise AuthError("missing token")
    return service.principal_from_token(conn, creds.credentials)


# ---- error mapping: never leak internals ------------------------------------------------------------------------
@app.exception_handler(AuthError)
async def _auth(_, e): return JSONResponse({"detail": str(e)}, 401, headers={"WWW-Authenticate": "Bearer"})
@app.exception_handler(Forbidden)
async def _forbidden(_, e): return JSONResponse({"detail": str(e)}, 403)
@app.exception_handler(NotFound)
async def _nf(_, e): return JSONResponse({"detail": str(e)}, 404)
@app.exception_handler(Invalid)
async def _inv(_, e): return JSONResponse({"detail": str(e)}, 422)
@app.exception_handler(LLMError)
async def _llm(_, e): return JSONResponse({"detail": str(e), "code": "llm_unavailable"}, 503)


@app.exception_handler(Exception)
async def _unhandled(request: Request, e: Exception):
    rid = uuid.uuid4().hex[:8]
    log.exception("unhandled error [%s] %s %s", rid, request.method, request.url.path)
    return JSONResponse({"detail": f"Internal server error (ref {rid}).", "code": "internal_error"}, 500)


# ---- schemas ------------------------------------------------------------------------------------------------------
class RegisterIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=10, max_length=200)
    org_name: str = Field(min_length=1, max_length=100)

class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)

class GroupIn(BaseModel):
    name: str = Field(max_length=50)

class UserIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=10, max_length=200)
    groups: list[str] = Field(default_factory=list, max_length=20)
    role: str = "member"

class UserGroupsIn(BaseModel):
    groups: list[str] = Field(default_factory=list, max_length=50)

class DocIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=200_000)
    groups: list[str] = Field(default_factory=list, max_length=20)

class QueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(4, ge=1, le=10)
    hops: int = Field(3, ge=0, le=4)
    use_graph: bool = True


def run_job(job_id: int):  # background worker with its own connection
    conn = db.connect(config.DB_PATH)
    try:
        service.process_job(conn, job_id)
    finally:
        conn.close()


# ---- public ---------------------------------------------------------------------------------------------------------
@app.get("/health")
def health(): return {"status": "ok", "version": __version__}


@app.get("/auth/config")
def auth_config(conn=Depends(get_conn)):
    """What the login screen needs. Demo credentials are published ONLY when DEMO_MODE=true (public sandbox)."""
    open_ = config.ALLOW_REGISTRATION and conn.execute("SELECT COUNT(*) c FROM orgs").fetchone()["c"] < config.MAX_ORGS
    out = {"registration_open": open_, "demo_mode": config.DEMO_MODE, "demo_accounts": [], "demo_password": None, "example_questions": []}
    if config.DEMO_MODE:
        out.update(demo_accounts=demo.PERSONAS, demo_password=config.DEMO_PASSWORD, example_questions=demo.EXAMPLE_QUESTIONS)
    return out


@app.post("/auth/register", status_code=201)
def register(body: RegisterIn, request: Request, conn=Depends(get_conn)):
    register_limiter.check(client_ip(request))
    service.check_registration_open(conn)
    p = service.register_org_admin(conn, body.email, body.password, body.org_name)
    return {"user_id": p.id, "org_id": p.org_id, "role": p.role}


@app.post("/auth/login")
def login(body: LoginIn, request: Request, conn=Depends(get_conn)):
    login_limiter.check(client_ip(request))
    p = service.authenticate(conn, body.email, body.password)
    return {"access_token": create_token(p.id), "token_type": "bearer", "expires_in": config.JWT_TTL_MIN * 60}


# ---- authenticated --------------------------------------------------------------------------------------------------
@app.get("/me")
def me(p=Depends(current_user), conn=Depends(get_conn)):
    return service.whoami(conn, p)


@app.get("/status")
def status(p=Depends(current_user)):
    return {"version": __version__, "environment": config.ENV, "llm": llm_status(), "embedder": embedder_status(),
            "database": {"engine": "sqlite", "persistent": False if config.IS_PROD else None,
                         "note": "SQLite on ephemeral container storage: data is lost on restart/redeploy unless a persistent volume is mounted."},
            "demo_mode": config.DEMO_MODE}


@app.get("/dashboard")
def dashboard(p=Depends(current_user), conn=Depends(get_conn)):
    return service.dashboard(conn, p)


@app.get("/groups")
def groups(p=Depends(current_user), conn=Depends(get_conn)):
    return service.list_groups(conn, p)


@app.post("/groups", status_code=201)
def new_group(body: GroupIn, p=Depends(current_user), conn=Depends(get_conn)):
    return {"group_id": service.create_group(conn, p, body.name)}


@app.get("/users")
def users(p=Depends(current_user), conn=Depends(get_conn)):
    return service.list_users(conn, p)


@app.post("/users", status_code=201)
def new_user(body: UserIn, p=Depends(current_user), conn=Depends(get_conn)):
    return {"user_id": service.create_user(conn, p, body.email, body.password, body.groups, body.role)}


@app.put("/users/{user_id}/groups")
def put_user_groups(user_id: int, body: UserGroupsIn, p=Depends(current_user), conn=Depends(get_conn)):
    return service.set_user_groups(conn, p, user_id, body.groups)


@app.get("/documents")
def documents(p=Depends(current_user), conn=Depends(get_conn)):
    return service.list_documents(conn, p)


@app.post("/documents", status_code=202)
def upload_json(body: DocIn, bg: BackgroundTasks, p=Depends(current_user), conn=Depends(get_conn)):
    job_id = service.submit_document(conn, p, body.title, body.text, body.groups)
    bg.add_task(run_job, job_id)
    return {"job_id": job_id, "status": "queued"}


@app.post("/documents/upload", status_code=202)
async def upload_file(bg: BackgroundTasks, file: UploadFile = File(...), groups: str = Form(""), title: str = Form(""),
                      p=Depends(current_user), conn=Depends(get_conn)):
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)  # bounded read: never buffer an unbounded body
    text = uploads.extract_text(file.filename or "", data)
    doc_title = (title.strip() or uploads.safe_title(file.filename or ""))[:200]
    job_id = service.submit_document(conn, p, doc_title, text, [g.strip() for g in groups.split(",") if g.strip()])
    bg.add_task(run_job, job_id)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def job(job_id: int, p=Depends(current_user), conn=Depends(get_conn)):
    return service.get_job(conn, p, job_id)


@app.post("/query")
def query(body: QueryIn, p=Depends(current_user), conn=Depends(get_conn)):
    query_limiter.check(f"user:{p.id}")
    r = service.query(conn, p, body.question, get_llm(), top_k=body.top_k, hops=body.hops, use_graph=body.use_graph)
    r.pop("context")  # internal
    r["quarantined"] = len(r.pop("dropped_chunks"))  # count only: no chunk ids for content the model never saw
    return r


@app.get("/graph")
def graph_overview(limit: int = 150, p=Depends(current_user), conn=Depends(get_conn)):
    return service.graph_overview(conn, p, limit)


@app.get("/graph/entity/{node_id}")
def entity(node_id: int, p=Depends(current_user), conn=Depends(get_conn)):
    return service.entity_neighbors(conn, p, node_id)


@app.get("/audit")
def audit(limit: int = 100, action: str | None = None, p=Depends(current_user), conn=Depends(get_conn)):
    return service.list_audit(conn, p, limit, action)


# ---- frontend (built by `npm run build` into frontend/dist) ------------------------------------------------------
_dist = Path(config.FRONTEND_DIST)
if (_dist / "index.html").is_file():
    if (_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(_dist / "index.html")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        f = _dist / "favicon.svg"
        if not f.is_file():
            raise HTTPException(404)
        return FileResponse(f)
else:
    @app.get("/", include_in_schema=False)
    def index_missing():
        return {"app": "VaultGraph API", "docs": "/docs",
                "note": "Frontend not built. Run `cd frontend && npm install && npm run build`, or use the Vite dev server."}
