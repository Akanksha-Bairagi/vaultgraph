"""First-stage retrieval: BM25 (keywords) + cosine (vectors), merged with Reciprocal Rank Fusion."""
import math, re
from collections import Counter
import numpy as np

STOP = set("a an the of to in on for and or is are was were be by with at as it this that from what who which how do does did".split())


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


class BM25:
    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.corpus, self.k1, self.b = corpus, k1, b
        self.n = len(corpus)
        self.avgdl = (sum(len(d) for d in corpus) / self.n) if self.n else 0.0
        self.tf = [Counter(d) for d in corpus]
        self.df = Counter(t for d in corpus for t in set(d))

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for i, d in enumerate(self.corpus):
            s = 0.0
            for t in set(query):
                f = self.tf[i].get(t, 0)
                if not f:
                    continue
                idf = math.log(1 + (self.n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / (self.avgdl or 1)))
            out.append(s)
        return out


def cosine_scores(qvec: list[float], vecs: list[list[float]]) -> list[float]:
    if not vecs:
        return []
    return (np.array(vecs) @ np.array(qvec)).tolist()  # vectors are L2-normalised


def rank_ids(ids: list[int], scores: list[float]) -> list[int]:
    return [i for i, s in sorted(zip(ids, scores), key=lambda x: -x[1]) if s > 0]


def rrf(rank_lists: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """score(d) = sum over lists of 1/(k + rank). Needs no score normalisation across retrievers."""
    agg: dict[int, float] = {}
    for lst in rank_lists:
        for r, i in enumerate(lst, start=1):
            agg[i] = agg.get(i, 0.0) + 1.0 / (k + r)
    return sorted(agg.items(), key=lambda x: -x[1])
