"""SQLite schema. Portable SQL (recursive CTEs, json_each) so the same design maps to Postgres."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, org_id INTEGER NOT NULL REFERENCES orgs(id),
  email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','member')));
CREATE TABLE IF NOT EXISTS groups(
  id INTEGER PRIMARY KEY, org_id INTEGER NOT NULL REFERENCES orgs(id),
  name TEXT NOT NULL, UNIQUE(org_id, name));
CREATE TABLE IF NOT EXISTS user_groups(
  user_id INTEGER NOT NULL REFERENCES users(id),
  group_id INTEGER NOT NULL REFERENCES groups(id),
  PRIMARY KEY(user_id, group_id));
CREATE TABLE IF NOT EXISTS documents(
  id INTEGER PRIMARY KEY, org_id INTEGER NOT NULL REFERENCES orgs(id),
  owner_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL, raw_text TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','processing','ready','failed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS doc_acl(
  doc_id INTEGER NOT NULL REFERENCES documents(id),
  group_id INTEGER NOT NULL REFERENCES groups(id),
  PRIMARY KEY(doc_id, group_id));
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY, doc_id INTEGER NOT NULL REFERENCES documents(id),
  org_id INTEGER NOT NULL, status TEXT NOT NULL, error TEXT);
CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY, doc_id INTEGER NOT NULL REFERENCES documents(id),
  org_id INTEGER NOT NULL, idx INTEGER NOT NULL, text TEXT NOT NULL,
  embedding TEXT NOT NULL, flagged INTEGER NOT NULL DEFAULT 0, flags TEXT NOT NULL DEFAULT '',
  embedder TEXT NOT NULL DEFAULT 'hash256');
CREATE TABLE IF NOT EXISTS nodes(
  id INTEGER PRIMARY KEY, org_id INTEGER NOT NULL, key TEXT NOT NULL,
  name TEXT NOT NULL, type TEXT NOT NULL, UNIQUE(org_id, key));
CREATE TABLE IF NOT EXISTS node_sources(
  node_id INTEGER NOT NULL REFERENCES nodes(id),
  chunk_id INTEGER NOT NULL REFERENCES chunks(id),
  PRIMARY KEY(node_id, chunk_id));
CREATE TABLE IF NOT EXISTS edges(
  id INTEGER PRIMARY KEY, org_id INTEGER NOT NULL,
  src INTEGER NOT NULL REFERENCES nodes(id), dst INTEGER NOT NULL REFERENCES nodes(id),
  rel TEXT NOT NULL, chunk_id INTEGER NOT NULL REFERENCES chunks(id),
  UNIQUE(src, dst, rel, chunk_id));
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  org_id INTEGER, user_id INTEGER, action TEXT NOT NULL, detail TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS ix_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS ix_edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS ix_edges_chunk ON edges(chunk_id);
CREATE INDEX IF NOT EXISTS ix_nsrc_chunk ON node_sources(chunk_id);
CREATE INDEX IF NOT EXISTS ix_audit_org ON audit_log(org_id, id);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Tiny forward-only migrations for databases created by earlier versions."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(chunks)")}
    if "embedder" not in cols:  # v0.1 -> v0.2: remember which model produced each vector
        conn.execute("ALTER TABLE chunks ADD COLUMN embedder TEXT NOT NULL DEFAULT 'hash256'")
        conn.commit()
