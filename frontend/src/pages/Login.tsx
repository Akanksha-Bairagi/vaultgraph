import { useState, type FormEvent } from "react";
import { Loader2, Lock, Network, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth } from "../auth.tsx";
import { messageOf, useAsync } from "../hooks.ts";
import { api } from "../lib/client.ts";
import { ErrorNote } from "../components/ui.tsx";

export function Login() {
  const { login, register } = useAuth();
  const cfg = useAsync(() => api.authConfig(), []);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [org, setOrg] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canRegister = cfg.data?.registration_open ?? true;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, org);
    } catch (err) { setError(messageOf(err)); setBusy(false); }
  }
  async function demo(addr: string) {
    if (!cfg.data?.demo_password) return;
    setBusy(true); setError(null);
    try { await login(addr, cfg.data.demo_password); } catch (err) { setError(messageOf(err)); setBusy(false); }
  }

  return (
    <div className="auth-shell">
      <section className="auth-hero">
        <div className="brand"><ShieldCheck size={26} aria-hidden /><span>VaultGraph</span></div>
        <h1>Answers from your documents.<br />Only the ones you’re allowed to see.</h1>
        <p>A knowledge graph and hybrid search over your company’s documents, with permissions enforced inside every query, not in the prompt.</p>
        <ul className="hero-points">
          <li><Lock size={18} aria-hidden /><span><strong>Access control at the data layer</strong>Restricted facts can’t leak through the graph.</span></li>
          <li><Network size={18} aria-hidden /><span><strong>Multi-hop answers</strong>Connected subgraphs preserve relationships between facts.</span></li>
          <li><Sparkles size={18} aria-hidden /><span><strong>Attack-tested</strong>Prompt-injection defenses with every answer audited.</span></li>
        </ul>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <div className="tabs" role="tablist">
            <button role="tab" aria-selected={mode === "login"} className={mode === "login" ? "on" : ""} onClick={() => { setMode("login"); setError(null); }}>Sign in</button>
            {canRegister && <button role="tab" aria-selected={mode === "register"} className={mode === "register" ? "on" : ""} onClick={() => { setMode("register"); setError(null); }}>Create workspace</button>}
          </div>
          <form onSubmit={submit} className="form">
            {mode === "register" && (
              <label>Organisation name<input value={org} onChange={(e) => setOrg(e.target.value)} required maxLength={100} autoComplete="organization" placeholder="Acme Inc." /></label>
            )}
            <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" placeholder="you@company.com" /></label>
            <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={mode === "register" ? 10 : 1}
              autoComplete={mode === "login" ? "current-password" : "new-password"} placeholder={mode === "register" ? "At least 10 characters" : "••••••••"} /></label>
            {error && <ErrorNote message={error} />}
            <button className="btn btn-primary btn-lg" disabled={busy}>{busy ? <Loader2 size={16} className="spin" /> : null}{mode === "login" ? "Sign in" : "Create workspace"}</button>
            {mode === "register" && <p className="muted small">You become the administrator of a new, isolated workspace.</p>}
          </form>

          {cfg.data?.demo_mode && (
            <div className="demo-box">
              <h3>Try the demo workspace</h3>
              <p className="muted small">A fictional company with documents split across Engineering, Finance and HR. Sign in as different people to see what each is allowed to find.</p>
              <div className="demo-grid">
                {cfg.data.demo_accounts.map((a) => (
                  <button key={a.email} className="demo-btn" disabled={busy} onClick={() => demo(a.email)}><strong>{a.label}</strong><span>{a.blurb}</span></button>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
