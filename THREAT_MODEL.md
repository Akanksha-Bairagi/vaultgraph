# Threat model & OWASP LLM Top 10 mapping (v0.2)

**Assets:** documents a user may not see (salary, layoffs), other tenants' data, the system prompt, API keys, audit integrity.
**Attackers:** (1) low-privilege insider uploading poisoned documents, (2) curious member probing for restricted data, (3) another tenant, (4) anonymous internet user, (5) XSS/CSRF-style browser attacker.

## Controls and tests
| Risk | Where it applies | Mitigation (file) | Test |
|---|---|---|---|
| LLM01 Prompt injection (indirect) | Poisoned uploads reach the prompt | Ingest scan + quarantine, query-time rescan, nonce delimiters, "context is data" system prompt (`guard.py`, `service.py`) | `TestInjection.*` |
| LLM02 Sensitive info disclosure | Restricted docs/edges via search or graph expansion | ACL in SQL; provenance-derived node/edge visibility (`acl.py`, `graph.py`) | `test_graph_expansion_does_not_leak`, `test_overview_respects_acl_and_has_provenance`, API `test_graph_visualization_data_and_acl` |
| LLM03 Supply chain | Models/packages | Minimum versions, CI on two Python versions, lockfile recommended (`npm install` generates one), Groq model id verified live | CI |
| LLM04 Data poisoning | False facts in the graph | Flagged chunks never feed the graph; every edge keeps its evidence chunk (traceable, removable) | `process_job` |
| LLM05 Improper output handling | Answer rendered in a browser | React escapes text (no `dangerouslySetInnerHTML`), validator blocks markdown images, foreign URLs, canary leaks, fake citations | `test_output_validator`, exfil tests |
| LLM06 Excessive agency | LLM actions | The model has **no tools, no network, no DB access**; text only | by design |
| LLM07 System-prompt leakage | "Reveal your prompt" | No secrets in the prompt; canary detects leaks | `test_output_validator` |
| LLM08 Vector weaknesses | Cross-tenant/cross-model vector recall | Candidates ACL-filtered *before* ranking; vectors compared only within one embedder | ACL tests, `test_vector_search_only_uses_matching_embedder_and_reindex` |
| LLM09 Misinformation | Hallucination | Answer-from-context prompt, citations required and validated, sources and graph facts shown | eval part A |
| LLM10 Unbounded consumption | Cost / DoS | Size, page, top-k, hop and question-length caps; rate limits; bounded upload reads; sentence cap in extractor | `test_upload_validation`, `test_size_cap` |

## Web/API controls added in v0.2
| Risk | Mitigation | Test |
|---|---|---|
| Weak/default secrets | `ENV=production` refuses to start unless `JWT_SECRET` ≥ 32 chars and not a known default; dev uses a random per-process secret; no default admin exists (demo logins only with `DEMO_MODE=true`) | `test_production_requires_strong_jwt_secret`, `test_development_never_uses_a_default_secret` |
| Broken access control / BOLA | Every object lookup scoped by org + ACL; invisible == 404; admin-only endpoints return 403; no self-escalation of groups | `test_cannot_manage_other_tenants_users_or_use_foreign_groups`, API `test_group_permission_management`, `test_multi_tenant_isolation` |
| Malicious uploads | Extension allow-list, PDF magic bytes, UTF-8/NUL checks, size + page limits, encrypted PDFs rejected, filenames reduced to a safe title | `TestUploads`, API `test_upload_validation` |
| Information leakage via errors | Generic 500 with reference id; LLM errors mapped to safe messages; keys never in messages | API `test_error_handling`, `test_groq_error_messages_never_include_the_key` |
| XSS / clickjacking / sniffing | CSP (`script-src 'self'`), `nosniff`, `Referrer-Policy: no-referrer`, `frame-ancestors` limited to self + Hugging Face | API `test_health_and_security_headers` |
| CORS misuse | No CORS unless `CORS_ORIGINS` is set; never credentialed; bearer tokens only | review |
| Session theft | Token in `sessionStorage` (tab-scoped), 60-min expiry, role re-read on every request, 401 → forced logout in the UI | `api.test.ts` |
| Brute force / abuse | Login (10/min/IP), register (5/min/IP), query (30/min/user) limits; failed logins audited; same error for unknown user and bad password; registration can be closed (`ALLOW_REGISTRATION`) and capped (`MAX_ORGS`) | API `test_auth_workflow`, `test_registration_can_be_disabled` |
| Secret exposure | Groq key read server-side only; frontend contains no secrets; `.env` git-ignored | review |

## Prompt-injection status (history matters)
- **v0.1 known gap:** letter-spaced instructions (`i g n o r e previous instructions`) evaded the scanner.
- **v0.2:** scanner normalises NFKC, strips zero-width characters, folds common Cyrillic/Greek look-alikes, removes letter-spacing (`i.g.n.o.r.e`, `i-g-n-o-r-e`) and tries a leetspeak variant. The former gap is now detected (`test_letter_spaced_hijack_now_detected`).
- **Residual risk (still real, still tested):** paraphrases ("Forget everything you were told…"), other languages, encodings, and instructions split across chunks are **not** detected (`test_known_residual_gap`).
  Defence in depth reduces impact: output validation blocks exfiltration channels; ACLs ensure a hijacked model only ever saw data the user could already read; the model has no tools.
  What remains possible: a hijacked answer can still *say wrong things* using visible data. Do not claim perfect protection.

## Other known residual risks
Admins see all documents in their workspace; in-memory rate limiter (single process); SQLite single writer; JWTs not revocable before expiry; a user with upload rights can add false-but-visible facts to groups they belong to;
rule-based extraction can be fooled by crafted sentences (graph poisoning within the attacker's own visibility); no CSRF surface exists because auth is a bearer header, but XSS would expose the `sessionStorage` token.
