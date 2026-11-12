"""Access control. ONE place defines "which documents may this person see".
Everything else (chunks, nodes, edges) derives its visibility from documents via provenance,
so there is no second ACL copy that can drift out of sync."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    id: int
    org_id: int
    role: str
    email: str = ""

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


# Default-deny: a doc is visible only if the user is admin of that org OR shares a group with doc_acl.
VISIBLE_DOCS = """
SELECT d.id FROM documents d
WHERE d.org_id = :org AND d.status = 'ready' AND (:admin = 1 OR EXISTS (
  SELECT 1 FROM doc_acl a JOIN user_groups ug ON ug.group_id = a.group_id
  WHERE a.doc_id = d.id AND ug.user_id = :uid))"""

# Deliberately UNSAFE variant, only used by the eval harness to demonstrate leaks (acl_mode != "enforced").
ALL_ORG_DOCS = "SELECT d.id FROM documents d WHERE d.org_id = :org AND d.status = 'ready'"


def params(p: Principal) -> dict:
    return {"org": p.org_id, "admin": 1 if p.is_admin else 0, "uid": p.id}


def docs_sql(enforce: bool) -> str:
    return VISIBLE_DOCS if enforce else ALL_ORG_DOCS
