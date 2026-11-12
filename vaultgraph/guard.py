"""Prompt-injection defences. Honest framing: a regex scanner is a speed bump, not a wall.
The real security boundary is ACL enforcement (the LLM never sees data the user may not see) plus
output validation and giving the LLM no tools/network. Scanner = cheap signal + quarantine."""
import re, secrets, unicodedata

CANARY = "CANARY-" + secrets.token_hex(4)

PATTERNS = {
    "ignore_instructions": r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
    "disregard": r"disregard (all |any )?(the )?(previous|prior|above|earlier)",
    "role_override": r"you are now\b|act as (an? )?(unrestricted|jailbroken)",
    "reveal_prompt": r"(reveal|print|show|repeat|output) (your |the )?(system|hidden|initial) (prompt|instructions)",
    "append_payload": r"(append|include|add) (this|the following) (markdown|image|link)",
    "external_image": r"!\[[^\]]*\]\(https?://",
    "chat_markers": r"<\s*(system|assistant)\s*>|\[inst\]|<\|im_start\|>",
}
_COMPILED = {k: re.compile(v) for k, v in PATTERNS.items()}


# Common Cyrillic/Greek look-alikes -> Latin (not exhaustive; NFKC does not map these).
_CONFUSABLES = str.maketrans({
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0445": "x", "\u0443": "y",
    "\u0456": "i", "\u0458": "j", "\u0455": "s", "\u03bf": "o", "\u03b1": "a", "\u03b5": "e", "\u03b9": "i"})
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
# "i g n o r e", "i.g.n.o.r.e", "i-g-n-o-r-e", "i_g_n_o_r_e" -> "ignore"
_SPACED = re.compile(r"\b(?:[a-z][\s.\-_*]+){3,}[a-z]\b")


def normalize(text: str) -> str:
    """NFKC + strip zero-width/format chars (category Cf) + fold look-alike letters + lowercase + collapse whitespace."""
    t = unicodedata.normalize("NFKC", text)
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Cf")
    t = t.translate(_CONFUSABLES)
    return " ".join(t.lower().split())


def _variants(text: str) -> list[str]:
    base = normalize(text)
    despaced = _SPACED.sub(lambda m: re.sub(r"[\s.\-_*]+", "", m.group(0)), base)
    return list({base, despaced, despaced.translate(_LEET)})


def scan(text: str) -> list[str]:
    """Returns the names of matched patterns. Heuristic: catches known phrasings and common obfuscations
    (zero-width chars, look-alike letters, letter-spacing, leetspeak) but NOT paraphrases, other languages or encodings."""
    hits: list[str] = []
    for v in _variants(text):
        for name, rx in _COMPILED.items():
            if name not in hits and rx.search(v):
                hits.append(name)
    return hits


_URL = re.compile(r"https?://[^\s)\]>\"']+")
_IMAGE = re.compile(r"!\[[^\]]*\]\s*\(")
_CITE = re.compile(r"\[c(\d+)\]")
REFUSAL = "I can't provide that response."


def validate_output(answer: str, allowed_chunk_ids: set[int], context_text: str):
    """Returns (safe_answer, violations). Blocks canary leaks and exfil URLs not present in the context;
    strips citations that point at chunks the model was never given."""
    violations = []
    if CANARY in answer:
        violations.append("canary_leak")
    if _IMAGE.search(answer):  # auto-rendered images are a classic exfil channel; never allowed, even if the URL is in context
        violations.append("markdown_image")
    ctx = context_text
    for url in _URL.findall(answer):
        if url not in ctx:
            violations.append("foreign_url")
            break
    if violations:
        return REFUSAL, violations
    def fix(m):
        if int(m.group(1)) in allowed_chunk_ids:
            return m.group(0)
        violations.append("bad_citation")
        return ""
    return _CITE.sub(fix, answer), violations
