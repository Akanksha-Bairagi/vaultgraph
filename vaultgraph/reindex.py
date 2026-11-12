"""Re-embed every chunk with the currently configured embedder:  python -m vaultgraph.reindex"""
import json
from . import config, db
from .embeddings import get_embedder


def reindex(conn) -> int:
    emb = get_embedder()
    rows = conn.execute("SELECT id, text FROM chunks WHERE embedder != ?", (emb.name,)).fetchall()
    for r in rows:
        conn.execute("UPDATE chunks SET embedding=?, embedder=? WHERE id=?", (json.dumps(emb.embed(r["text"])), emb.name, r["id"]))
    conn.commit()
    return len(rows)


if __name__ == "__main__":
    c = db.connect(config.DB_PATH)
    print(f"re-embedded {reindex(c)} chunks with {get_embedder().name}")
