"""Embedders. Default is an offline feature-hashing embedder (no downloads, deterministic).
EMBEDDER=bge uses sentence-transformers BAAI/bge-small-en-v1.5 if the optional dependency is installed
(pip install -r requirements-bge.txt); otherwise we fall back to hashing and report why in /status.

Every chunk stores the name of the embedder that produced its vector. Vector search only compares vectors from the
SAME model as the query embedding; chunks from another model are still found by BM25 until re-indexed
(python -m vaultgraph.reindex)."""
import importlib.util
import logging
import math
import zlib
from functools import lru_cache

from . import config
from .search import tokenize

log = logging.getLogger("vaultgraph.embeddings")


class HashEmbedder:
    name, dim = "hash256", 256

    def embed(self, text: str) -> list[float]:
        toks = tokenize(text)
        feats = toks + [a + "_" + b for a, b in zip(toks, toks[1:])]
        v = [0.0] * self.dim
        for f in feats:
            h = zlib.crc32(f.encode())
            v[h % self.dim] += 1.0 if (h >> 16) & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]


class BGEEmbedder:
    name = "bge-small-en-v1.5"

    def __init__(self):
        from sentence_transformers import SentenceTransformer  # heavy import, only when requested
        self.model = SentenceTransformer("BAAI/bge-small-en-v1.5")

    def embed(self, text: str) -> list[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()


def bge_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


@lru_cache(maxsize=1)
def _bge_or_none():
    try:
        return BGEEmbedder()
    except Exception as e:  # missing dep, no network for model download, out of memory, ...
        log.warning("BGE embedder unavailable (%s); falling back to hash embedder", type(e).__name__)
        return None


def get_embedder():
    if config.EMBEDDER == "bge":
        emb = _bge_or_none()
        if emb is not None:
            return emb
    return HashEmbedder()


def embedder_status() -> dict:
    """Cheap, never loads the model."""
    requested = config.EMBEDDER
    if requested != "bge":
        return {"requested": requested, "active": HashEmbedder.name, "fallback": False, "detail": "offline hashing embedder"}
    if not bge_available():
        return {"requested": requested, "active": HashEmbedder.name, "fallback": True,
                "detail": "sentence-transformers not installed; pip install -r requirements-bge.txt"}
    loaded = _bge_or_none.cache_info().currsize > 0 and _bge_or_none() is None
    if loaded:
        return {"requested": requested, "active": HashEmbedder.name, "fallback": True, "detail": "BGE model failed to load; see server logs"}
    return {"requested": requested, "active": BGEEmbedder.name, "fallback": False, "detail": "local BGE model (loads on first use)"}
