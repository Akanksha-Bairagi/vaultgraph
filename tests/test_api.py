"""HTTP-level tests (FastAPI TestClient). Skipped automatically if FastAPI/httpx aren't installed; CI installs them."""
import os, tempfile, unittest, uuid

try:
    from fastapi.testclient import TestClient
    HAVE = True
except Exception:  # pragma: no cover
    HAVE = False

PW = "Passw0rd!demo"


@unittest.skipUnless(HAVE, "fastapi/httpx not installed")
class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vaultgraph import config
        config.DB_PATH = os.path.join(tempfile.mkdtemp(), "t.db")
        config.LLM_PROVIDER, config.GROQ_API_KEY, config.DEMO_MODE = "mock", "", False  # never call Groq from tests
        from vaultgraph import api
        for lim in (api.login_limiter, api.register_limiter, api.query_limiter):
            lim.limit = 10_000
        cls.api, cls.config = api, config
        cls.client = TestClient(api.app, raise_server_exceptions=False)

    # ---- helpers
    def login(self, email, pw=PW):
        r = self.client.post("/auth/login", json={"email": email, "password": pw})
        self.assertEqual(r.status_code, 200, r.text)
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def make_org(self, name=None, groups=("eng", "hr")):
        tag = uuid.uuid4().hex[:6]
        name = name or f"Org{tag}"
        email = f"boss@{tag}.test"
        self.assertEqual(self.client.post("/auth/register", json={"email": email, "password": PW, "org_name": name}).status_code, 201)
        h = self.login(email)
        for g in groups:
            self.assertEqual(self.client.post("/groups", json={"name": g}, headers=h).status_code, 201)
        return tag, email, h

    def add_user(self, admin_h, tag, who, groups):
        email = f"{who}@{tag}.test"
        r = self.client.post("/users", json={"email": email, "password": PW, "groups": list(groups)}, headers=admin_h)
        self.assertEqual(r.status_code, 201, r.text)
        return email, r.json()["user_id"]

    # ---- tests
    def test_health_and_security_headers(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["x-content-type-options"], "nosniff")
        self.assertIn("frame-ancestors", r.headers["content-security-policy"])
        self.assertNotIn("content-security-policy", self.client.get("/docs").headers)  # Swagger needs a CDN

    def test_auth_workflow(self):
        c = self.client
        tag, email, h = self.make_org()
        me = c.get("/me", headers=h).json()
        self.assertEqual((me["email"], me["role"]), (email, "admin"))
        self.assertEqual(c.post("/auth/login", json={"email": email, "password": "wrong-password"}).status_code, 401)
        self.assertEqual(c.get("/me").status_code, 401)
        self.assertEqual(c.get("/me", headers={"Authorization": "Bearer garbage"}).status_code, 401)
        self.assertEqual(c.post("/auth/register", json={"email": email, "password": PW, "org_name": "Dup"}).status_code, 422)
        self.assertEqual(c.post("/auth/register", json={"email": "x@y.test", "password": "short", "org_name": "S"}).status_code, 422)

    def test_end_to_end_acl(self):
        c = self.client
        tag, _, h = self.make_org()
        dev_email, _ = self.add_user(h, tag, "dev", ["eng"])
        r = c.post("/documents", json={"title": "Pay", "text": "Sam earns a salary of 99999. Sam reports to Kim.", "groups": ["hr"]}, headers=h)
        self.assertEqual(r.status_code, 202)
        dev = self.login(dev_email)
        out = c.post("/query", json={"question": "What is Sam's salary?"}, headers=dev).json()
        self.assertNotIn("99999", str(out))
        self.assertIn("99999", str(c.post("/query", json={"question": "What is Sam's salary?"}, headers=h).json()))
        self.assertEqual(c.get("/audit", headers=dev).status_code, 403)
        self.assertEqual(c.get("/audit").status_code, 401)
        self.assertEqual(c.get("/audit", headers=h).status_code, 200)

    def test_upload_workflow_and_status(self):
        c = self.client
        tag, _, h = self.make_org()
        r = c.post("/documents/upload", headers=h, data={"groups": "eng", "title": "Orion notes"},
                   files={"file": ("notes.txt", b"Project Orion depends on Atlas Database.", "text/plain")})
        self.assertEqual(r.status_code, 202, r.text)
        job = c.get(f"/jobs/{r.json()['job_id']}", headers=h).json()
        self.assertEqual(job["status"], "done")
        docs = c.get("/documents", headers=h).json()
        self.assertEqual([(d["title"], d["status"], d["groups"]) for d in docs], [("Orion notes", "ready", ["eng"])])

    def test_upload_validation(self):
        c = self.client
        tag, _, h = self.make_org()
        def up(name, data): return c.post("/documents/upload", headers=h, data={"groups": "eng"}, files={"file": (name, data, "application/octet-stream")})
        self.assertEqual(up("evil.exe", b"MZ").status_code, 422)
        self.assertEqual(up("fake.pdf", b"not really a pdf").status_code, 422)
        self.assertEqual(up("bin.txt", b"abc\x00def").status_code, 422)
        old = self.config.MAX_UPLOAD_BYTES
        self.config.MAX_UPLOAD_BYTES = 100
        try:
            self.assertEqual(up("big.txt", b"a" * 500).status_code, 422)
        finally:
            self.config.MAX_UPLOAD_BYTES = old
        self.assertEqual(c.post("/documents/upload", headers=h, data={"groups": "nope"}, files={"file": ("a.txt", b"hello", "text/plain")}).status_code, 422)
        self.assertEqual(c.post("/documents/upload", data={"groups": "eng"}, files={"file": ("a.txt", b"hello", "text/plain")}).status_code, 401)

    def test_query_returns_citations_and_sources(self):
        c = self.client
        tag, _, h = self.make_org()
        c.post("/documents", json={"title": "Arch", "text": "Project Orion is built by Platform Team. Project Orion depends on Atlas Database.", "groups": ["eng"]}, headers=h)
        r = c.post("/query", json={"question": "Project Orion depends on which database?"}, headers=h).json()
        self.assertIn("Atlas Database", r["answer"])
        self.assertTrue(r["sources"] and r["sources"][0]["doc_title"] == "Arch")
        self.assertEqual({s["chunk_id"] for s in r["sources"]}, set(r["citations"]))
        self.assertEqual(r["provider"], "mock")
        self.assertNotIn("context", r)
        self.assertNotIn("dropped_chunks", r)
        self.assertEqual(c.post("/query", json={"question": ""}, headers=h).status_code, 422)

    def test_group_permission_management(self):
        c = self.client
        tag, _, h = self.make_org()
        email, uid = self.add_user(h, tag, "ann", ["eng"])
        ann = self.login(email)
        c.post("/documents", json={"title": "HR", "text": "Bo earns a salary of 5555.", "groups": ["hr"]}, headers=h)
        self.assertNotIn("5555", str(c.post("/query", json={"question": "Bo salary"}, headers=ann).json()))
        self.assertEqual(c.put(f"/users/{uid}/groups", json={"groups": ["eng", "hr"]}, headers=ann).status_code, 403)  # no self-escalation
        self.assertEqual(c.get("/users", headers=ann).status_code, 403)
        self.assertEqual(c.put(f"/users/{uid}/groups", json={"groups": ["eng", "hr"]}, headers=h).status_code, 200)
        self.assertIn("5555", str(c.post("/query", json={"question": "Bo salary"}, headers=ann).json()))
        users = {u["email"]: u["groups"] for u in c.get("/users", headers=h).json()}
        self.assertEqual(users[email], ["eng", "hr"])
        self.assertEqual(c.put(f"/users/{uid}/groups", json={"groups": ["ghost"]}, headers=h).status_code, 422)
        self.assertEqual({g["name"] for g in c.get("/groups", headers=ann).json()}, {"eng", "hr"})

    def test_graph_visualization_data_and_acl(self):
        c = self.client
        tag, _, h = self.make_org()
        email, _ = self.add_user(h, tag, "dev", ["eng"])
        c.post("/documents", json={"title": "Arch", "text": "Project Orion depends on Atlas Database.", "groups": ["eng"]}, headers=h)
        c.post("/documents", json={"title": "Secret", "text": "Project Phoenix affects Atlas Database.", "groups": ["hr"]}, headers=h)
        dev = self.login(email)
        g = c.get("/graph", headers=dev).json()
        names = {n["name"] for n in g["nodes"]}
        self.assertEqual(names, {"Project Orion", "Atlas Database"})
        self.assertTrue(all(e["doc_title"] == "Arch" and e["evidence"] for e in g["edges"]))
        full = c.get("/graph", headers=h).json()
        phoenix = [n["id"] for n in full["nodes"] if n["name"] == "Project Phoenix"][0]
        atlas = [n["id"] for n in g["nodes"] if n["name"] == "Atlas Database"][0]
        self.assertEqual(c.get(f"/graph/entity/{phoenix}", headers=dev).status_code, 404)
        self.assertNotIn("Phoenix", str(c.get(f"/graph/entity/{atlas}", headers=dev).json()))

   
    def test_multi_tenant_isolation(self):
        c = self.client
        tagA, _, a = self.make_org()
        tagB, _, b = self.make_org()

        job = c.post(
            "/documents",
            json={
                "title": "A-only",
                "text": "Zorblax Prime is owned by Acme Corp.",
                "groups": ["eng"]
            },
            headers=a
        ).json()["job_id"]

        self.assertEqual(c.get(f"/jobs/{job}", headers=b).status_code, 404)
        self.assertEqual(c.get("/documents", headers=b).json(), [])
        self.assertEqual(c.get("/graph", headers=b).json()["nodes"], [])

        self.assertNotIn(
            "Zorblax",
            str(c.post(
                "/query",
                json={"question": "Tell me about Zorblax Prime"},
                headers=b
            ).json())
        )

        _, uid = self.add_user(a, tagA, "x", [])
        self.assertEqual(
            c.put(f"/users/{uid}/groups", json={"groups": ["eng"]}, headers=b).status_code,
            404
        )

        audit_b = c.get("/audit", headers=b).json()
        self.assertTrue(audit_b, "Tenant B should have its own audit entries")
        self.assertTrue(
            all(row["actor"] != f"boss@{tagA}.test" for row in audit_b),
            "Tenant B's audit log must not contain Tenant A's actor",
        )
        self.assertTrue(
            all(row["actor"] == f"boss@{tagB}.test" for row in audit_b),
            "Tenant B's audit log should contain only Tenant B's actor",
        )


    def test_error_handling(self):
        from vaultgraph.llm import LLMError
        c = self.client
        tag, _, h = self.make_org()
        original = self.api.get_llm
        try:
            def boom(): raise LLMError("The Groq API key is invalid or revoked (401). Check GROQ_API_KEY.")
            self.api.get_llm = boom
            r = c.post("/query", json={"question": "hello"}, headers=h)
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.json()["code"], "llm_unavailable")
            self.assertNotIn("gsk_", r.text)
        finally:
            self.api.get_llm = original
        orig_dash = self.api.service.dashboard
        try:
            def explode(*a, **k): raise RuntimeError("sqlite path /secret/db.sqlite password=hunter2")
            self.api.service.dashboard = explode
            r = c.get("/dashboard", headers=h)
            self.assertEqual(r.status_code, 500)
            self.assertNotIn("hunter2", r.text)
            self.assertIn("ref", r.json()["detail"])
        finally:
            self.api.service.dashboard = orig_dash
        self.assertEqual(c.get("/jobs/999999", headers=h).status_code, 404)
        self.assertEqual(c.post("/auth/login", json={"email": "a"}).status_code, 422)

    def test_status_dashboard_and_auth_config(self):
        c = self.client
        tag, _, h = self.make_org()
        st = c.get("/status", headers=h).json()
        self.assertEqual(st["llm"]["provider"], "mock")
        self.assertIn("active", st["embedder"])
        self.assertEqual(c.get("/status").status_code, 401)
        d = c.get("/dashboard", headers=h).json()
        self.assertIn("documents", d)
        cfg = c.get("/auth/config").json()
        self.assertFalse(cfg["demo_mode"])
        self.assertIsNone(cfg["demo_password"])
        self.config.DEMO_MODE = True
        try:
            cfg = c.get("/auth/config").json()
            self.assertTrue(cfg["demo_accounts"] and cfg["demo_password"])
        finally:
            self.config.DEMO_MODE = False

    def test_registration_can_be_disabled(self):
        self.config.ALLOW_REGISTRATION = False
        try:
            r = self.client.post("/auth/register", json={"email": "z@z.test", "password": PW, "org_name": "Nope"})
            self.assertEqual(r.status_code, 403)
            self.assertFalse(self.client.get("/auth/config").json()["registration_open"])
        finally:
            self.config.ALLOW_REGISTRATION = True


if __name__ == "__main__":
    unittest.main()
