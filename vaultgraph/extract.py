"""Entity/relationship extraction -> (subject, RELATION, object) triples.
Rule-based by default (deterministic, free, offline). An LLM extractor can sit behind the same function;
its output must be validated exactly like this module validates names (LLM output is untrusted)."""
import re

REL = {
    "depends on": "DEPENDS_ON", "is built by": "BUILT_BY", "is led by": "LED_BY",
    "is hosted on": "HOSTED_ON", "is managed by": "MANAGED_BY", "reports to": "REPORTS_TO",
    "is funded by": "FUNDED_BY", "is approved by": "APPROVED_BY", "affects": "AFFECTS",
    "owns": "OWNS", "uses": "USES",
}
ENT = r"[A-Z][A-Za-z0-9\-']*(?:\s+[A-Z][A-Za-z0-9\-']*)*"
_PHRASES = "|".join(sorted((re.escape(p) for p in REL), key=len, reverse=True))
PATTERN = re.compile(rf"(?P<a>{ENT})\s+(?P<r>{_PHRASES})\s+(?P<b>{ENT})")
MAX_SENTENCE = 500  # input cap: keeps regex work bounded (ReDoS hygiene)


def clean(name: str) -> str:
    return re.sub(r"^(The|A|An)\s+", "", name.strip())


def entity_type(name: str) -> str:
    for word, t in (("Project", "project"), ("Team", "team"), ("Database", "system"), ("Cluster", "system"), ("Plan", "plan")):
        if word in name:
            return t
    return "entity"


def extract_triples(text: str) -> list[tuple[str, str, str]]:
    out = []
    for sent in re.split(r"(?<=[.!?])\s+|\n", text):
        sent = sent[:MAX_SENTENCE]
        for m in PATTERN.finditer(sent):
            a, b = clean(m.group("a")), clean(m.group("b"))
            if a and b and a.lower() != b.lower() and len(a) <= 80 and len(b) <= 80:
                out.append((a, REL[m.group("r")], b))
    return out
