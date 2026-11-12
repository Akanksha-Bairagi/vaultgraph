"""Synthetic company 'Northwind Labs' used by tests, eval and the live demo.
Designed so the classic GraphRAG leak is reproducible: restricted HR facts hang off nodes that engineers CAN see."""
import argparse, sys
from . import config, db, service

PW = "Passw0rd!demo"
DOCS = [
    ("Employee Handbook", ["all"],
     "Northwind Labs holds an all-hands meeting every Friday. Employees submit expense reports through the Expense Portal. "
     "Project Orion is the flagship product of Northwind Labs. The office closes at 6pm."),
    ("Orion Architecture", ["eng"],
     "Project Orion is built by Platform Team. Project Orion depends on Atlas Database. Platform Team is led by Priya Nair."),
    ("Infrastructure Notes", ["eng"],
     "Atlas Database is hosted on Helios Cluster. Helios Cluster is managed by Marcus Lee."),
    ("Orion Funding", ["finance"],
     "Project Orion is funded by Q4 Capital Plan. Q4 Capital Plan is approved by Dana Whitfield."),
    ("People Confidential", ["hr"],
     "Marcus Lee reports to Priya Nair. Marcus Lee earns a salary of 182000. Project Phoenix affects Platform Team. "
     "Project Phoenix is a confidential layoff plan."),
]
USERS = {"ava": ["all", "eng"], "fin": ["all", "finance"], "hr": ["all", "hr"], "intern": ["all"]}


def build_company(conn, org="Northwind Labs", password=PW) -> dict:
    admin = service.register_org_admin(conn, f"admin@{org.split()[0].lower()}.test", password, org)
    for g in ("all", "eng", "finance", "hr"):
        service.create_group(conn, admin, g)
    people = {"admin": admin}
    for name, groups in USERS.items():
        service.create_user(conn, admin, f"{name}@{org.split()[0].lower()}.test", password, groups)
        people[name] = service.authenticate(conn, f"{name}@{org.split()[0].lower()}.test", password)
    for title, groups, text in DOCS:
        service.ingest_document(conn, admin, title, text, groups)
    return people


def build_rival(conn):
    admin = service.register_org_admin(conn, "admin@rival.test", PW, "Rival Corp")
    service.create_group(conn, admin, "all")
    service.ingest_document(conn, admin, "Rival Secrets", "Project Zephyr is owned by Rival Corp. Project Zephyr uses Quantum Ledger.", ["all"])
    return admin


PERSONAS = [  # shown on the login page in DEMO_MODE only
    {"email": "admin@northwind.test", "label": "Admin", "blurb": "Sees everything, manages people, reads the audit log"},
    {"email": "ava@northwind.test", "label": "Ava (Engineering)", "blurb": "Engineering docs only"},
    {"email": "fin@northwind.test", "label": "Fiona (Finance)", "blurb": "Finance docs only"},
    {"email": "hr@northwind.test", "label": "Hana (HR)", "blurb": "Confidential HR docs"},
    {"email": "intern@northwind.test", "label": "Intern", "blurb": "Public handbook only"},
]
EXAMPLE_QUESTIONS = [
    "Who is responsible for the infrastructure underneath Project Orion?",
    "Who approves the plan funding the product built by Platform Team?",
    "What is Marcus Lee's salary?",
    "Tell me about the Platform Team",
]


def seed_if_empty(conn) -> bool:
    """Used on app start when DEMO_MODE=true. Creates the public sandbox org once."""
    if conn.execute("SELECT COUNT(*) c FROM orgs").fetchone()["c"]:
        return False
    build_company(conn, password=config.DEMO_PASSWORD)
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seed the public demo org (DEMO_MODE=true or --force)")
    ap.add_argument("--if-empty", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not (config.DEMO_MODE or a.force):
        sys.exit("DEMO_MODE is not enabled; refusing to create demo accounts. Use --force for local experiments.")
    conn = db.connect(config.DB_PATH)
    if a.if_empty:
        print("seeded" if seed_if_empty(conn) else "database not empty; skipped")
    else:
        build_company(conn, password=config.DEMO_PASSWORD)
        print(f"Seeded Northwind Labs. Demo password: {config.DEMO_PASSWORD}. Accounts: " + ", ".join(p["email"] for p in PERSONAS))
