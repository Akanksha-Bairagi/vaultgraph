"""Knowledge graph in plain tables (nodes/edges) + ACL-aware k-hop traversal via a recursive CTE.

Visibility by provenance:
  * an EDGE is visible iff the chunk that is its evidence is in a document the user can see
  * a NODE is visible iff at least one visible chunk mentions it
  * traversal only walks visible edges to visible nodes
So a restricted fact can never be reached through an allowed neighbour."""
import json
from . import acl
from .acl import Principal


def upsert_node(conn, org_id: int, name: str, ntype: str) -> int:
    key = " ".join(name.lower().split())
    conn.execute("INSERT OR IGNORE INTO nodes(org_id,key,name,type) VALUES(?,?,?,?)", (org_id, key, name, ntype))
    return conn.execute("SELECT id FROM nodes WHERE org_id=? AND key=?", (org_id, key)).fetchone()["id"]


def store_triples(conn, org_id: int, chunk_id: int, triples, type_fn) -> int:
    n = 0
    for a, rel, b in triples:
        ia, ib = upsert_node(conn, org_id, a, type_fn(a)), upsert_node(conn, org_id, b, type_fn(b))
        for nid in (ia, ib):
            conn.execute("INSERT OR IGNORE INTO node_sources(node_id,chunk_id) VALUES(?,?)", (nid, chunk_id))
        conn.execute("INSERT OR IGNORE INTO edges(org_id,src,dst,rel,chunk_id) VALUES(?,?,?,?,?)", (org_id, ia, ib, rel, chunk_id))
        n += 1
    return n


def _prefix(enforce: bool) -> str:
    return f"""
    vd(id) AS ({acl.docs_sql(enforce)}),
    vc(id) AS (SELECT c.id FROM chunks c WHERE c.doc_id IN (SELECT id FROM vd) AND c.flagged = 0),
    ve AS (SELECT e.id, e.src, e.dst, e.rel, e.chunk_id FROM edges e
           WHERE e.org_id = :org AND e.chunk_id IN (SELECT id FROM vc)),
    vn(id) AS (SELECT DISTINCT ns.node_id FROM node_sources ns WHERE ns.chunk_id IN (SELECT id FROM vc))"""


def visible_nodes(conn, p: Principal, enforce: bool = True):
    sql = "WITH RECURSIVE" + _prefix(enforce) + " SELECT n.id, n.name, n.type FROM nodes n WHERE n.id IN (SELECT id FROM vn)"
    return conn.execute(sql, acl.params(p)).fetchall()


def khop(conn, p: Principal, seeds: list[int], k: int = 2, enforce: bool = True) -> dict:
    """Nodes/edges within k hops of the seeds. enforce=False is the leaky baseline used only by the eval."""
    if not seeds:
        return {"nodes": [], "edges": []}
    args = {**acl.params(p), "seeds": json.dumps(sorted(set(seeds))), "k": int(k)}
    walk = f"""
    WITH RECURSIVE {_prefix(enforce)},
    walk(node_id, depth) AS (
      SELECT id, 0 FROM vn WHERE id IN (SELECT value FROM json_each(:seeds))
      UNION
      SELECT CASE WHEN e.src = w.node_id THEN e.dst ELSE e.src END, w.depth + 1
      FROM walk w JOIN ve e ON (e.src = w.node_id OR e.dst = w.node_id)
      WHERE w.depth < :k
        AND (CASE WHEN e.src = w.node_id THEN e.dst ELSE e.src END) IN (SELECT id FROM vn)
    )
    SELECT n.id, n.name, n.type, MIN(w.depth) AS depth
    FROM walk w JOIN nodes n ON n.id = w.node_id GROUP BY n.id ORDER BY depth, n.name"""
    nodes = [dict(r) for r in conn.execute(walk, args).fetchall()]
    ids = json.dumps([n["id"] for n in nodes])
    edge_sql = f"""
    WITH RECURSIVE {_prefix(enforce)}
    SELECT e.id, e.src, e.dst, e.rel, e.chunk_id, a.name AS src_name, b.name AS dst_name,
           c.doc_id, d.title AS doc_title, substr(c.text, 1, 300) AS evidence
    FROM ve e JOIN nodes a ON a.id = e.src JOIN nodes b ON b.id = e.dst
    JOIN chunks c ON c.id = e.chunk_id JOIN documents d ON d.id = c.doc_id
    WHERE e.src IN (SELECT value FROM json_each(:ids)) AND e.dst IN (SELECT value FROM json_each(:ids))"""
    edges = [dict(r) for r in conn.execute(edge_sql, {**acl.params(p), "ids": ids}).fetchall()]
    return {"nodes": nodes, "edges": edges}


def visible_graph(conn, p: Principal, limit: int = 150) -> dict:
    """Everything the caller may see (capped to the `limit` best-connected nodes), with provenance on every edge."""
    edge_sql = f"""
    WITH RECURSIVE {_prefix(True)}
    SELECT e.id, e.src, e.dst, e.rel, e.chunk_id, a.name AS src_name, b.name AS dst_name,
           c.doc_id, d.title AS doc_title, substr(c.text, 1, 300) AS evidence
    FROM ve e JOIN nodes a ON a.id = e.src JOIN nodes b ON b.id = e.dst
    JOIN chunks c ON c.id = e.chunk_id JOIN documents d ON d.id = c.doc_id"""
    edges = [dict(r) for r in conn.execute(edge_sql, acl.params(p)).fetchall()]
    nodes = {r["id"]: {**dict(r), "degree": 0} for r in visible_nodes(conn, p, True)}
    for e in edges:
        for k in (e["src"], e["dst"]):
            if k in nodes:
                nodes[k]["degree"] += 1
    keep = {n["id"] for n in sorted(nodes.values(), key=lambda n: (-n["degree"], n["name"]))[:limit]}
    return {"nodes": [n for n in nodes.values() if n["id"] in keep],
            "edges": [e for e in edges if e["src"] in keep and e["dst"] in keep],
            "truncated": len(nodes) > len(keep)}
