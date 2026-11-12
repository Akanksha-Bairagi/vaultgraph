"""Service-level tests for v0.2 features (run without FastAPI)."""
import json, os, subprocess, sys, unittest
from vaultgraph import config, db, demo, embeddings, graph, llm, service, uploads
from vaultgraph.errors import Forbidden, Invalid, NotFound
from vaultgraph.llm import LLMError, MockLLM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def titles(docs):
    return {d["title"] for d in docs}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = db.connect(":memory:")
        cls.P = demo.build_company(cls.conn)
        cls.rival = demo.build_rival(cls.conn)


class TestDocumentListing(Base):
    def test_members_only_see_accessible_documents(self):
        self.assertEqual(titles(service.list_documents(self.conn, self.P["intern"])), {"Employee Handbook"})
        self.assertEqual(titles(service.list_documents(self.conn, self.P["ava"])),
                         {"Employee Handbook", "Orion Architecture", "Infrastructure Notes"})
        self.assertNotIn("People Confidential", titles(service.list_documents(self.conn, self.P["fin"])))

    def test_admin_sees_all_org_docs_but_not_other_tenants(self):
        t = titles(service.list_documents(self.conn, self.P["admin"]))
        self.assertIn("People Confidential", t)
        self.assertNotIn("Rival Secrets", t)
        self.assertEqual(titles(service.list_documents(self.conn, self.rival)), {"Rival Secrets"})

    def test_group_metadata_not_leaked_to_non_owners(self):
        handbook = [d for d in service.list_documents(self.conn, self.P["ava"]) if d["title"] == "Employee Handbook"][0]
        self.assertEqual(handbook["groups"], ["all"])
        arch = [d for d in service.list_documents(self.conn, self.P["intern"]) if d["title"] == "Employee Handbook"][0]
        self.assertIsNone(arch["owner"])

    def test_owner_sees_own_pending_upload_status(self):
        job = service.submit_document(self.conn, self.P["intern"], "Draft", "Some text here.", ["all"])
        mine = [d for d in service.list_documents(self.conn, self.P["intern"]) if d["title"] == "Draft"][0]
        self.assertEqual(mine["status"], "queued")
        self.assertNotIn("Draft", titles(service.list_documents(self.conn, self.P["ava"])))  # not visible until ready
        service.process_job(self.conn, job)
        self.assertIn("Draft", titles(service.list_documents(self.conn, self.P["ava"])))


class TestUsersAndGroups(Base):
    def test_admin_lists_users_member_forbidden(self):
        self.assertEqual(len(service.list_users(self.conn, self.P["admin"])), 5)
        with self.assertRaises(Forbidden):
            service.list_users(self.conn, self.P["ava"])

    def test_set_user_groups_changes_access_immediately(self):
        service.set_user_groups(self.conn, self.P["admin"], self.P["intern"].id, ["all", "hr"])
        self.assertIn("People Confidential", titles(service.list_documents(self.conn, self.P["intern"])))
        r = service.query(self.conn, self.P["intern"], "What is Marcus Lee's salary?", MockLLM())
        self.assertIn("182000", r["answer"] + str(r["facts"]) + str(r["sources"]))
        service.set_user_groups(self.conn, self.P["admin"], self.P["intern"].id, ["all"])
        r = service.query(self.conn, self.P["intern"], "What is Marcus Lee's salary?", MockLLM())
        self.assertNotIn("182000", json.dumps({k: v for k, v in r.items() if k != "context"}))

    def test_cannot_manage_other_tenants_users_or_use_foreign_groups(self):
        with self.assertRaises(NotFound):
            service.set_user_groups(self.conn, self.rival, self.P["ava"].id, ["all"])
        with self.assertRaises(Forbidden):
            service.set_user_groups(self.conn, self.P["ava"], self.P["ava"].id, ["hr"])  # privilege escalation attempt
        with self.assertRaises(Invalid):
            service.set_user_groups(self.conn, self.P["admin"], self.P["ava"].id, ["nonexistent"])

    def test_member_group_list_is_limited_to_own_groups(self):
        self.assertEqual({g["name"] for g in service.list_groups(self.conn, self.P["ava"])}, {"all", "eng"})
        self.assertEqual({g["name"] for g in service.list_groups(self.conn, self.P["admin"])}, {"all", "eng", "finance", "hr"})


class TestGraphVisibility(Base):
    def test_overview_respects_acl_and_has_provenance(self):
        g = service.graph_overview(self.conn, self.P["ava"])
        names = {n["name"] for n in g["nodes"]}
        self.assertIn("Platform Team", names)
        self.assertTrue({"Project Phoenix", "Q4 Capital Plan", "Zephyr"}.isdisjoint(names))
        self.assertTrue(all(e["doc_title"] and e["evidence"] for e in g["edges"]))
        self.assertNotIn("182000", json.dumps(g))
        full = {n["name"] for n in service.graph_overview(self.conn, self.P["admin"])["nodes"]}
        self.assertIn("Project Phoenix", full)
        self.assertNotIn("Project Zephyr", full)  # other tenant

    def test_entity_neighbors_include_provenance(self):
        nid = self.conn.execute("SELECT id FROM nodes WHERE name='Platform Team'").fetchone()["id"]
        sub = service.entity_neighbors(self.conn, self.P["ava"], nid)
        self.assertTrue(sub["edges"] and all(e["doc_title"] for e in sub["edges"]))
        self.assertNotIn("Project Phoenix", json.dumps(sub))


class TestQueryShape(Base):
    def test_sources_cover_citations_and_hide_restricted(self):
        r = service.query(self.conn, self.P["ava"], "Who is responsible for the infrastructure underneath Project Orion?", MockLLM(), top_k=2)
        self.assertEqual({s["chunk_id"] for s in r["sources"]}, set(r["citations"]))
        self.assertTrue(all(s["doc_title"] for s in r["sources"]))
        self.assertEqual(r["provider"], "mock")
        self.assertNotIn("People Confidential", json.dumps(r["sources"]))

    def test_llm_failure_is_audited_and_raised(self):
        class Boom:
            name = "groq"
            def complete(self, s, u): raise LLMError("The Groq API key is invalid or revoked (401). Check GROQ_API_KEY.")
        with self.assertRaises(LLMError):
            service.query(self.conn, self.P["ava"], "anything", Boom())
        last = service.list_audit(self.conn, self.P["admin"], 3, "query_error")[0]
        self.assertIn("invalid", last["detail"]["error"])

    def test_dashboard_counts_are_scoped(self):
        service.query(self.conn, self.P["fin"], "Who approves the plan?", MockLLM())
        d = service.dashboard(self.conn, self.P["fin"])
        self.assertGreaterEqual(d["queries"]["total"], 1)
        self.assertIsNone(d["users"])
        self.assertEqual(d["recent_activity"], [])
        self.assertEqual(service.dashboard(self.conn, self.P["admin"])["users"], 5)

    def test_audit_has_actor_and_filter(self):
        rows = service.list_audit(self.conn, self.P["admin"], 50, "login")
        self.assertTrue(rows and all(r["action"] == "login" and r["actor"] for r in rows))
        self.assertTrue(rows[0]["ts"].endswith("Z"))


class TestUploads(unittest.TestCase):
    @staticmethod
    def make_pdf(text: str) -> bytes:
        """Builds a minimal valid one-page PDF with a correct xref table (no external libs needed)."""
        stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
        objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
                b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
                b"<</Length %d>>\nstream\n" % len(stream) + stream + b"\nendstream",
                b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
        out, offsets = bytearray(b"%PDF-1.4\n"), []
        for i, o in enumerate(objs, 1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += f"trailer<</Root 1 0 R/Size {len(objs) + 1}>>\nstartxref\n{xref}\n%%EOF".encode()
        return bytes(out)

    def test_text_ok_and_rejections(self):
        self.assertEqual(uploads.extract_text("a.txt", b"hello"), "hello")
        for name, data in [("a.exe", b"hi"), ("a.txt", b""), ("a.txt", b"\xff\xfe\x00bad"), ("a.pdf", b"not a pdf"), ("a.txt", b"   \n  ")]:
            with self.assertRaises(Invalid, msg=name):
                uploads.extract_text(name, data)

    def test_size_cap(self):
        with self.assertRaises(Invalid):
            uploads.extract_text("big.txt", b"a" * (config.MAX_UPLOAD_BYTES + 1))

    def test_pdf_text_extraction(self):
        self.assertIn("Hello Vault", uploads.extract_text("x.pdf", self.make_pdf("Hello Vault")))

    def test_safe_title_strips_paths(self):
        self.assertEqual(uploads.safe_title("../../etc/passwd.txt"), "passwd.txt")
        self.assertEqual(uploads.safe_title("C:\\evil\\x.md"), "x.md")


class TestEmbeddersAndMigration(unittest.TestCase):
    def test_bge_request_falls_back_gracefully_when_dependency_missing(self):
        old = config.EMBEDDER
        config.EMBEDDER = "bge"
        embeddings._bge_or_none.cache_clear()
        try:
            st = embeddings.embedder_status()
            if not embeddings.bge_available():
                self.assertTrue(st["fallback"])
                self.assertEqual(embeddings.get_embedder().name, "hash256")
        finally:
            config.EMBEDDER = old
            embeddings._bge_or_none.cache_clear()

    def test_vector_search_only_uses_matching_embedder_and_reindex(self):
        conn = db.connect(":memory:")
        P = demo.build_company(conn)
        conn.execute("UPDATE chunks SET embedder='other-model'")
        r = service.retrieve(conn, P["admin"], "Atlas Database hosted", top_k=2, use_graph=False)
        self.assertTrue(r["chunks"])  # still found via BM25
        from vaultgraph.reindex import reindex
        self.assertGreater(reindex(conn), 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) c FROM chunks WHERE embedder='hash256'").fetchone()["c"],
                         conn.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"])

    def test_old_database_is_migrated(self):
        import sqlite3, tempfile
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        c = sqlite3.connect(path)
        c.executescript("CREATE TABLE chunks(id INTEGER PRIMARY KEY, doc_id INT, org_id INT, idx INT, text TEXT, embedding TEXT, flagged INT DEFAULT 0, flags TEXT DEFAULT '');")
        c.commit(); c.close()
        conn = db.connect(path)
        self.assertIn("embedder", {r["name"] for r in conn.execute("PRAGMA table_info(chunks)")})


class TestConfigAndLLM(unittest.TestCase):
    def run_py(self, env, code="import vaultgraph.config as c; print('OK', len(c.JWT_SECRET))"):
        e = {k: v for k, v in os.environ.items() if k not in ("JWT_SECRET", "ENV", "GROQ_API_KEY")}
        e.update(env)
        return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=e, capture_output=True, text=True)

    def test_production_requires_strong_jwt_secret(self):
        for bad in ("", "short", "dev-secret-change-me", "x" * 31):
            r = self.run_py({"ENV": "production", "JWT_SECRET": bad})
            self.assertNotEqual(r.returncode, 0, bad)
            self.assertIn("JWT_SECRET", r.stderr)
        ok = self.run_py({"ENV": "production", "JWT_SECRET": "k" * 40})
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_development_never_uses_a_default_secret(self):
        a, b = self.run_py({}), self.run_py({})
        self.assertIn("OK", a.stdout)
        self.assertNotEqual(a.stdout, "")  # random per-process secret of length >= 32
        self.assertGreaterEqual(int(a.stdout.split()[1]), 32)

    def test_llm_provider_selection(self):
        old = (config.LLM_PROVIDER, config.GROQ_API_KEY)
        try:
            config.LLM_PROVIDER, config.GROQ_API_KEY = "auto", ""
            self.assertEqual(llm.get_llm().name, "mock")
            self.assertEqual(llm.llm_status()["provider"], "mock")
            config.GROQ_API_KEY = "gsk_test"
            self.assertEqual(llm.get_llm().name, "groq")
            config.LLM_PROVIDER, config.GROQ_API_KEY = "groq", ""
            with self.assertRaises(LLMError):
                llm.get_llm()
            st = llm.llm_status()
            self.assertEqual((st["provider"], st["healthy"]), ("groq", False))
            self.assertIn("GROQ_API_KEY", st["detail"])
            config.LLM_PROVIDER = "mock"
            self.assertEqual(llm.get_llm().name, "mock")
        finally:
            config.LLM_PROVIDER, config.GROQ_API_KEY = old

    def test_groq_error_messages_never_include_the_key(self):
        for code in (400, 401, 403, 404, 429, 500):
            self.assertNotIn("gsk_", llm._http_message(code))
        self.assertIn("invalid", llm._http_message(401))

    def test_registration_gating(self):
        conn = db.connect(":memory:")
        old = (config.ALLOW_REGISTRATION, config.MAX_ORGS)
        try:
            config.ALLOW_REGISTRATION = False
            with self.assertRaises(Forbidden):
                service.check_registration_open(conn)
            config.ALLOW_REGISTRATION, config.MAX_ORGS = True, 1
            service.check_registration_open(conn)
            service.register_org_admin(conn, "a@b.test", "Passw0rd!demo", "One")
            with self.assertRaises(Forbidden):
                service.check_registration_open(conn)
        finally:
            config.ALLOW_REGISTRATION, config.MAX_ORGS = old


if __name__ == "__main__":
    unittest.main()
